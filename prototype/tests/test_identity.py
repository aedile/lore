"""Tests for prototype.identity — A4 acceptance.

Covers PROTOTYPE_PRD.md A4 acceptance:
- Tier 1 deterministic match against an existing canonical (auto-merge).
- Tier 2 / 3 probabilistic merges produced by Splink with a non-empty
  per-comparison score breakdown (BR-104 explainability).
- Tier 4 distinct identities (no match).
- The cross-partner near-match truths from A1 are detected by Splink.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from prototype.csv_adapter import read_csv
from prototype.identity import (
    TIER_1,
    TIER_2,
    TIER_3,
    TIER_4,
    CanonicalCandidate,
    IdentityDecision,
    ResolutionResult,
    TierThresholds,
    resolve,
    to_comparison_record,
)
from prototype.mapping_engine import StagingRecord, load_mapping, map_feed, map_row

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = REPO_ROOT / "prototype" / "fixtures"
PARTNER_A_YAML = REPO_ROOT / "prototype" / "mappings" / "partner_a.yaml"
PARTNER_B_YAML = REPO_ROOT / "prototype" / "mappings" / "partner_b.yaml"


# ---------------------------------------------------------------------------
# Comparison-shape projection
# ---------------------------------------------------------------------------


def test_to_comparison_record_builds_unique_id_and_normalizes() -> None:
    mapping = load_mapping(PARTNER_A_YAML)
    record = map_row(
        {
            "member_id": "A00042",
            "FirstName": "Sarah",
            "LastName": "Johnson",
            "DOB": "04/12/1985",
            "SSN": "987-65-4321",
            "Street": "123 Main St",
        },
        mapping,
    )
    cr = to_comparison_record(record)
    assert cr["unique_id"] == "PARTNER_A:A00042"
    assert cr["partner_id"] == "PARTNER_A"
    assert cr["first_name"] == "sarah"
    assert cr["last_name"] == "johnson"
    assert cr["dob"] == "1985-04-12"
    assert cr["ssn_last4"] == "4321"


# ---------------------------------------------------------------------------
# Tier 1: deterministic against existing canonical
# ---------------------------------------------------------------------------


def test_tier_1_fires_when_partner_enrollment_and_identity_match() -> None:
    """A new record whose (partner, member_id, last_name, dob) matches an
    existing canonical_member auto-merges as Tier 1."""
    mapping = load_mapping(PARTNER_A_YAML)
    new_row = {
        "member_id": "A00001",
        "FirstName": "Sarah",
        "LastName": "Johnson",
        "DOB": "04/12/1985",
        "SSN": "987-65-4321",
        "Street": "123 Main St",
    }
    new_record = map_row(new_row, mapping)
    existing = [
        CanonicalCandidate(
            member_id="canon-001",
            last_name="johnson",  # normalized
            dob="1985-04-12",
            enrollments=[("PARTNER_A", "A00001")],
        ),
    ]
    result = resolve([new_record], existing_canonical=existing)
    assert len(result.decisions) == 1
    decision = result.decisions[0]
    assert decision.tier == TIER_1
    assert decision.resolved_member_id == "canon-001"
    assert decision.score is None
    assert decision.score_breakdown is None


def test_tier_1_does_not_fire_on_partner_mismatch() -> None:
    """Same partner_member_id but different partner is NOT a Tier 1 match."""
    mapping = load_mapping(PARTNER_A_YAML)
    record = map_row(
        {"member_id": "A00001", "LastName": "Johnson", "DOB": "04/12/1985", "FirstName": "Sarah"},
        mapping,
    )
    existing = [
        CanonicalCandidate(
            member_id="canon-001",
            last_name="johnson",
            dob="1985-04-12",
            enrollments=[("PARTNER_B", "A00001")],  # different partner
        ),
    ]
    result = resolve([record], existing_canonical=existing)
    assert result.decisions[0].tier != TIER_1


def test_tier_1_does_not_fire_on_last_name_mismatch() -> None:
    """Same partner + member_id but last_name differs → not Tier 1 (would
    be probabilistic; here it's a singleton so Tier 4)."""
    mapping = load_mapping(PARTNER_A_YAML)
    record = map_row(
        {
            "member_id": "A00001",
            "FirstName": "Sarah",
            "LastName": "Smith",  # mismatch
            "DOB": "04/12/1985",
        },
        mapping,
    )
    existing = [
        CanonicalCandidate(
            member_id="canon-001",
            last_name="johnson",
            dob="1985-04-12",
            enrollments=[("PARTNER_A", "A00001")],
        ),
    ]
    result = resolve([record], existing_canonical=existing)
    assert result.decisions[0].tier != TIER_1


# ---------------------------------------------------------------------------
# Cross-partner near-matches over real A1 fixtures (Splink path)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def cross_partner_resolution() -> ResolutionResult:
    """Run A4 across PARTNER_A day 1 + PARTNER_B day 1 once and reuse the result."""
    mapping_a = load_mapping(PARTNER_A_YAML)
    mapping_b = load_mapping(PARTNER_B_YAML)

    records: list[StagingRecord] = []
    records.extend(map_feed(read_csv(FIXTURES / "partner_a_day1.csv"), mapping_a))
    records.extend(map_feed(read_csv(FIXTURES / "partner_b_day1.csv"), mapping_b))

    # A4 trusts its input is DQ-passed and BR-601-deduped. Filter out records
    # the DQ engine would quarantine (missing required fields) and dedupe by
    # (partner_id, partner_member_id) keeping last (BR-601 last-record-wins).
    records = [
        r
        for r in records
        if r.canonical.get("dob")
        and r.canonical.get("last_name")
        and r.canonical.get("partner_member_id")
    ]
    deduped: dict[tuple[str, str], StagingRecord] = {}
    for r in records:
        key = (r.partner_id, r.canonical["partner_member_id"])
        deduped[key] = r
    return resolve(list(deduped.values()), thresholds=TierThresholds(high=5.0, review=1.0))


def test_resolution_carries_algorithm_and_config_versions(
    cross_partner_resolution: ResolutionResult,
) -> None:
    """BR-104 — every result is stamped with linker version + config version."""
    assert "splink" in cross_partner_resolution.algorithm_version.lower()
    assert cross_partner_resolution.config_version


def test_every_record_has_a_decision(cross_partner_resolution: ResolutionResult) -> None:
    by_uid = {d.candidate_record_ref: d for d in cross_partner_resolution.decisions}
    for members in cross_partner_resolution.canonical_groups.values():
        for uid in members:
            assert uid in by_uid
            assert by_uid[uid].tier in (TIER_1, TIER_2, TIER_3, TIER_4)


def test_cross_partner_near_match_groups_with_explainable_score(
    cross_partner_resolution: ResolutionResult,
) -> None:
    """At least one of the seeded cross-partner near-match truth_ids must
    have its PARTNER_A and PARTNER_B sides resolved to the same canonical
    member_id, with a non-empty per-comparison score breakdown.
    """
    inventory = json.loads((FIXTURES / "scenario_inventory.json").read_text())
    by_truth: dict[str, list[str]] = {}
    for entry in inventory["records"]:
        if entry["scenario"] != "cross_partner_near_match":
            continue
        partner = "PARTNER_A" if "partner_a" in entry["feed"] else "PARTNER_B"
        by_truth.setdefault(entry["truth_id"], []).append(f"{partner}:{entry['partner_member_id']}")

    by_uid = {d.candidate_record_ref: d for d in cross_partner_resolution.decisions}

    merged_pair_count = 0
    for uids in by_truth.values():
        if len(uids) < 2:
            continue
        decisions = [by_uid[u] for u in uids if u in by_uid]
        if len(decisions) < 2:
            continue
        if len({d.resolved_member_id for d in decisions}) == 1:
            merged_pair_count += 1
            for d in decisions:
                assert d.tier in (TIER_2, TIER_3)
                assert d.score is not None
                assert d.score_breakdown is not None
                assert len(d.score_breakdown) > 0

    assert merged_pair_count >= 1, "Expected at least one cross-partner near-match merge"


def test_unrelated_records_dominate_tier_4(cross_partner_resolution: ResolutionResult) -> None:
    """Most records in a 600-row mixed feed have no real match — Tier 4 dominates."""
    counts = {TIER_1: 0, TIER_2: 0, TIER_3: 0, TIER_4: 0}
    for d in cross_partner_resolution.decisions:
        counts[d.tier] += 1
    assert counts[TIER_4] >= counts[TIER_2] + counts[TIER_3], counts


def test_score_breakdown_includes_per_comparison_weights(
    cross_partner_resolution: ResolutionResult,
) -> None:
    """BR-104 — the score breakdown carries Splink's per-comparison weights
    (gamma_<col> and bf_<col> entries) so reviewers see the contribution of
    each field to the final score."""
    scored = [d for d in cross_partner_resolution.decisions if d.score_breakdown]
    assert scored, "Expected at least one decision with a score breakdown"
    sample = scored[0].score_breakdown
    assert sample is not None
    keys = list(sample.keys())
    assert any(k.startswith("bf_") for k in keys), keys
    assert any(k.startswith("gamma_") for k in keys), keys


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


def test_identity_decision_is_immutable() -> None:
    d = IdentityDecision(
        candidate_record_ref="X:1",
        resolved_member_id=None,
        tier=TIER_4,
        score=None,
        score_breakdown=None,
    )
    with pytest.raises(AttributeError, match="frozen|cannot"):
        d.tier = TIER_2  # type: ignore[misc]


def test_canonical_groups_have_at_least_one_real_uid_per_member(
    cross_partner_resolution: ResolutionResult,
) -> None:
    for member_id, uids in cross_partner_resolution.canonical_groups.items():
        assert uids, f"Member {member_id} has no associated record refs"
        for uid in uids:
            assert ":" in uid  # "PARTNER_X:..." shape; never the @canonical: virtual root
