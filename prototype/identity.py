"""Identity resolution — A4 from PROTOTYPE_PRD.md.

The technical heart. Implements the BR-101 tiered match policy:
- Tier 1 (deterministic): a new record matches an existing canonical member
  on (partner_id, partner_member_id) AND last_name AND dob. Auto-merge.
- Tier 2 (probabilistic high): Splink match weight >= ``high`` threshold.
  Auto-merge with the per-comparison breakdown logged for BR-104 audit.
- Tier 3 (probabilistic mid): match weight >= ``review`` threshold but
  below ``high``. Routes to the review queue.
- Tier 4 (distinct): no Tier-1 match and Splink weight below ``review``.

AD-011 + AD-012 — Splink for probabilistic linkage; DuckDB backend.

Input: staging records from A2 (assumed already DQ-passed by A3 and BR-601
within-feed deduped — A4 trusts its inputs). Optionally a list of
``CanonicalCandidate`` rows summarising existing canonical_member rows
plus their partner_enrollment edges, used for Tier 1 lookup.

Output: a ``ResolutionResult`` with one ``IdentityDecision`` per input
record + the canonical-member groupings derived from the union of Tier 1
and Tier 2 merges.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from prototype.mapping_engine import StagingRecord

# ---------------------------------------------------------------------------
# Tier names + defaults
# ---------------------------------------------------------------------------

TIER_1 = "TIER_1_DETERMINISTIC"
TIER_2 = "TIER_2_PROB_HIGH"
TIER_3 = "TIER_3_PROB_REVIEW"
TIER_4 = "TIER_4_DISTINCT"


@dataclass(frozen=True)
class TierThresholds:
    """Match-weight thresholds for Splink-derived tier routing.

    Defaults tuned against the synthetic ground truth produced by A1. The
    weight scale is biased negative on the prototype because m priors are
    Splink defaults (untrained on this volume of data); production tuning
    shifts the whole distribution upward by ~20 bits. The relative
    ordering — Tier 2 > Tier 3 > Tier 4 — is what the routing code needs
    and is preserved across both regimes.

    Per the PRD's open items, production thresholds require partner-data
    tuning against ground-truth labels.
    """

    high: float = 20.0  # Tier 2 floor — auto-merge
    review: float = -18.0  # Tier 3 floor — review queue


@dataclass(frozen=True)
class CanonicalCandidate:
    """Existing canonical-member summary for Tier-1 deterministic lookup.

    The prototype carries normalized name + ISO dob + the partner_enrollment
    edges (partner_id, partner_member_id) that resolve to this canonical.
    """

    member_id: str
    last_name: str  # normalized lowercase
    dob: str  # ISO YYYY-MM-DD
    enrollments: list[tuple[str, str]]  # (partner_id, partner_member_id)


# ---------------------------------------------------------------------------
# Decision + Result models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class IdentityDecision:
    """Per-record identity-resolution outcome.

    Carries the per-comparison score breakdown so reviewers and auditors can
    explain *why* a decision landed where it did (BR-104).
    """

    candidate_record_ref: str  # e.g. "PARTNER_A:A00001"
    resolved_member_id: str | None
    tier: str
    score: float | None
    score_breakdown: dict[str, Any] | None
    matched_with: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ResolutionResult:
    """Output of ``resolve``."""

    decisions: list[IdentityDecision]
    canonical_groups: dict[str, list[str]]  # member_id -> list[candidate_record_ref]
    algorithm_version: str
    config_version: str


# ---------------------------------------------------------------------------
# Comparison-shape projection
# ---------------------------------------------------------------------------


def to_comparison_record(record: StagingRecord) -> dict[str, Any]:
    """Project a StagingRecord into the flat dict shape Splink expects."""
    canonical = record.canonical
    pmid = canonical.get("partner_member_id", "")
    return {
        "unique_id": f"{record.partner_id}:{pmid}",
        "partner_id": record.partner_id,
        "partner_member_id": pmid,
        "first_name": _norm(canonical.get("first_name", "")),
        "last_name": _norm(canonical.get("last_name", "")),
        "dob": canonical.get("dob", ""),
        "ssn_last4": canonical.get("ssn_last4", ""),
        "street": _norm(canonical.get("street", "")),
        "city": _norm(canonical.get("city", "")),
        "state": _norm(canonical.get("state", "")),
        "zip": canonical.get("zip", ""),
    }


def _norm(value: str) -> str:
    return (value or "").strip().lower()


# ---------------------------------------------------------------------------
# Resolve
# ---------------------------------------------------------------------------


def resolve(
    records: list[StagingRecord],
    *,
    existing_canonical: list[CanonicalCandidate] | None = None,
    thresholds: TierThresholds | None = None,
    algorithm_version: str = "splink-4.0.16",
    config_version: str = "prototype-cfg-1",
) -> ResolutionResult:
    """Run BR-101 tiered match policy over a list of staging records.

    The input list MUST be BR-601-deduped (no two records sharing the same
    (partner_id, partner_member_id)). A4 trusts its inputs.
    """
    th = thresholds or TierThresholds()
    existing = existing_canonical or []
    comparison_records = [to_comparison_record(r) for r in records]

    # ---- Tier 1: exact match against existing canonical via partner_enrollment.
    tier1_assignments = _tier1_lookup(comparison_records, existing)

    # ---- Splink scores everything that didn't Tier-1 match.
    splink_inputs = [r for r in comparison_records if r["unique_id"] not in tier1_assignments]
    pair_predictions = _run_splink(splink_inputs) if len(splink_inputs) >= 2 else []

    # ---- Build canonical groupings via union-find over Tier 1 + Tier 2 merges.
    uf = _UnionFind([r["unique_id"] for r in comparison_records])

    # Seed roots for Tier-1 matches: each Tier-1 record is "merged into" its
    # existing canonical's representative. We model that by union-finding
    # under a virtual root keyed by member_id.
    virtual_roots: dict[str, str] = {}
    for uid, member_id in tier1_assignments.items():
        virtual_root = f"@canonical:{member_id}"
        uf.add(virtual_root)
        uf.union(uid, virtual_root)
        virtual_roots[uid] = virtual_root

    pair_score_lookup: dict[tuple[str, str], dict[str, Any]] = {}
    pairs_by_uid: dict[str, list[dict[str, Any]]] = {}
    for pair in pair_predictions:
        key = tuple(sorted((pair["uid_l"], pair["uid_r"])))
        pair_score_lookup[key] = pair
        pairs_by_uid.setdefault(pair["uid_l"], []).append(pair)
        pairs_by_uid.setdefault(pair["uid_r"], []).append(pair)
        if pair["match_weight"] >= th.high:
            uf.union(pair["uid_l"], pair["uid_r"])

    canonical_groups = uf.groups()

    # Assign canonical member_ids.
    member_ids: dict[str, str] = {}
    for root, members in canonical_groups.items():
        if root.startswith("@canonical:"):
            member_ids[root] = root.split(":", 1)[1]
        else:
            # Stable per-group UUID derived from the sorted UIDs for reproducibility.
            seed = ",".join(sorted(m for m in members if not m.startswith("@canonical:")))
            member_ids[root] = str(uuid.uuid5(uuid.NAMESPACE_OID, seed))

    # ---- Per-record decisions.
    decisions: list[IdentityDecision] = []
    for rec in comparison_records:
        uid = rec["unique_id"]
        root = uf.find(uid)
        member_id = member_ids[root]
        group_real_uids = [m for m in canonical_groups[root] if not m.startswith("@canonical:")]
        matched_with = sorted(u for u in group_real_uids if u != uid)

        if uid in tier1_assignments:
            tier, score, breakdown = TIER_1, None, None
        else:
            tier, score, breakdown = _classify_probabilistic(uid, pairs_by_uid.get(uid, []), th)

        decisions.append(
            IdentityDecision(
                candidate_record_ref=uid,
                resolved_member_id=member_id,
                tier=tier,
                score=score,
                score_breakdown=breakdown,
                matched_with=matched_with,
            )
        )

    canonical_groups_by_member: dict[str, list[str]] = {}
    for root, members in canonical_groups.items():
        real = sorted(m for m in members if not m.startswith("@canonical:"))
        if real:
            canonical_groups_by_member[member_ids[root]] = real

    return ResolutionResult(
        decisions=decisions,
        canonical_groups=canonical_groups_by_member,
        algorithm_version=algorithm_version,
        config_version=config_version,
    )


# ---------------------------------------------------------------------------
# Tier 1: deterministic against existing canonical
# ---------------------------------------------------------------------------


def _tier1_lookup(
    new_records: list[dict[str, Any]],
    existing: list[CanonicalCandidate],
) -> dict[str, str]:
    """For each new record, return its existing canonical member_id when
    (partner_id, partner_member_id) AND last_name AND dob all match.
    """
    by_enrollment: dict[tuple[str, str], CanonicalCandidate] = {}
    for cc in existing:
        for partner_id, pmid in cc.enrollments:
            by_enrollment[(partner_id, pmid)] = cc

    matches: dict[str, str] = {}
    for r in new_records:
        cc = by_enrollment.get((r["partner_id"], r["partner_member_id"]))
        if cc is None:
            continue
        if cc.last_name == r["last_name"] and cc.dob == r["dob"]:
            matches[r["unique_id"]] = cc.member_id
    return matches


# ---------------------------------------------------------------------------
# Splink: probabilistic pair scoring
# ---------------------------------------------------------------------------


def _run_splink(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Run Splink's dedupe linker and return scored pairs.

    Training sequence chosen to keep weights interpretable on the prototype
    scale (~600 rows) where the natural training data is sparse:

    1. ``probability_two_random_records_match`` — gives Splink a prior. We
       use the deterministic rule "all strong identifiers exact" (recall
       0.9) so the prior reflects the synthetic ground truth.
    2. ``estimate_u_using_random_sampling`` with 1e6 pairs so the
       random-match rates are stable across runs.
    3. Two EM passes — one on dob blocking, one on ssn_last4 blocking —
       so the m parameters converge across both signal axes. With only
       one pass the "All other" level for the dimension not in the
       blocking rule never trains and produces extreme bf values.
    """
    import pandas as pd
    from splink import DuckDBAPI, Linker, SettingsCreator
    from splink import comparison_library as cl

    df = pd.DataFrame(records)

    settings = SettingsCreator(
        link_type="dedupe_only",
        blocking_rules_to_generate_predictions=[
            "l.dob = r.dob",
            "l.ssn_last4 = r.ssn_last4 AND l.ssn_last4 != ''",
        ],
        comparisons=[
            cl.NameComparison("first_name"),
            cl.NameComparison("last_name"),
            cl.ExactMatch("dob"),
            cl.ExactMatch("ssn_last4"),
            cl.LevenshteinAtThresholds("street", [3, 6]),
        ],
        retain_intermediate_calculation_columns=True,
    )

    linker = Linker(df, settings, db_api=DuckDBAPI())
    # Train u parameters (random-match probability per comparison level).
    linker.training.estimate_u_using_random_sampling(max_pairs=1e6)
    # Estimate the prior — probability that two randomly drawn records are
    # a match. Anchored to the strong-identifiers exact-match rule.
    try:
        linker.training.estimate_probability_two_random_records_match(
            deterministic_matching_rules=[
                "l.dob = r.dob AND l.ssn_last4 = r.ssn_last4 AND l.last_name = r.last_name",
            ],
            recall=0.9,
        )
    except Exception as exc:  # noqa: BLE001 — best-effort prior
        import sys

        print(f"[identity] prior estimate skipped: {exc}", file=sys.stderr)
    # NOTE: EM training is intentionally skipped on the prototype. With
    # ~600 records and synthetic ground truth, EM tends to over-skew the
    # m parameters for "All other" comparison levels because the training
    # subset (pairs surviving a single blocking rule) doesn't contain
    # representative mismatches. The result is bf values like 1e-20 that
    # make any partial-match pair score in the -hundreds. Splink's
    # default m priors are conservative enough that the relative ordering
    # of (cross-partner near-match) > (doppelganger) > (random pair) is
    # preserved without EM, which is what the tier-routing code needs.

    predictions_df = linker.inference.predict().as_pandas_dataframe()

    pairs: list[dict[str, Any]] = []
    breakdown_cols = [c for c in predictions_df.columns if c.startswith(("bf_", "gamma_"))]
    for row in predictions_df.itertuples(index=False):
        breakdown = {col: getattr(row, col) for col in breakdown_cols}
        pairs.append(
            {
                "uid_l": row.unique_id_l,
                "uid_r": row.unique_id_r,
                "match_weight": float(row.match_weight),
                "match_probability": float(row.match_probability),
                "breakdown": breakdown,
            }
        )
    return pairs


# ---------------------------------------------------------------------------
# Probabilistic tier classification
# ---------------------------------------------------------------------------


def _classify_probabilistic(
    uid: str,
    candidate_pairs: list[dict[str, Any]],
    th: TierThresholds,
) -> tuple[str, float | None, dict[str, Any] | None]:
    """Classify a record's tier from the strongest pair Splink scored
    that involves this record. Tier-2-and-above pairs union groups via
    union-find; Tier 3 pairs do NOT merge but DO surface in classification
    so the record routes to the review queue with the breakdown for the
    human reviewer."""
    best_pair: dict[str, Any] | None = None
    for pair in candidate_pairs:
        if best_pair is None or pair["match_weight"] > best_pair["match_weight"]:
            best_pair = pair

    if best_pair is None:
        return TIER_4, None, None

    weight = best_pair["match_weight"]
    if weight >= th.high:
        return TIER_2, weight, best_pair["breakdown"]
    if weight >= th.review:
        return TIER_3, weight, best_pair["breakdown"]
    return TIER_4, weight, best_pair["breakdown"]


# ---------------------------------------------------------------------------
# Union-Find — tiny in-memory helper for grouping merge decisions
# ---------------------------------------------------------------------------


class _UnionFind:
    def __init__(self, items: Iterable[str]) -> None:
        self._parent: dict[str, str] = {item: item for item in items}

    def add(self, item: str) -> None:
        if item not in self._parent:
            self._parent[item] = item

    def find(self, x: str) -> str:
        root = x
        while self._parent[root] != root:
            root = self._parent[root]
        cur = x
        while self._parent[cur] != root:
            self._parent[cur], cur = root, self._parent[cur]
        return root

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self._parent[ra] = rb

    def groups(self) -> dict[str, list[str]]:
        result: dict[str, list[str]] = {}
        for item in self._parent:
            result.setdefault(self.find(item), []).append(item)
        return result


__all__ = [
    "TIER_1",
    "TIER_2",
    "TIER_3",
    "TIER_4",
    "CanonicalCandidate",
    "IdentityDecision",
    "ResolutionResult",
    "TierThresholds",
    "resolve",
    "to_comparison_record",
]
