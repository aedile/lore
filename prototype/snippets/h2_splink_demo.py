"""H2 hands-on snippet (headline) — Splink near-duplicate detection.

Runnable demonstration of probabilistic identity resolution catching a
near-duplicate that simple SQL deduplication cannot. The differentiator
is the per-comparison weight decomposition (BR-104) — the feature that
makes the decision auditable and defensible to a clinical-trust audience.

Run with:

    poetry run python -m prototype.snippets.h2_splink_demo

Output: a printed report listing 3+ pair scenarios across Tier 2 / Tier 3 /
Tier 4 with match weights and per-comparison breakdowns.
"""

from __future__ import annotations

import json
from pathlib import Path

from prototype.csv_adapter import read_csv
from prototype.identity import (
    TIER_2,
    TIER_3,
    TIER_4,
    TierThresholds,
    resolve,
)
from prototype.mapping_engine import StagingRecord, load_mapping, map_feed

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = REPO_ROOT / "prototype" / "fixtures"
MAPPINGS = REPO_ROOT / "prototype" / "mappings"


def _load_records() -> list[StagingRecord]:
    mapping_a = load_mapping(MAPPINGS / "partner_a.yaml")
    mapping_b = load_mapping(MAPPINGS / "partner_b.yaml")
    records: list[StagingRecord] = []
    records.extend(map_feed(read_csv(FIXTURES / "partner_a_day1.csv"), mapping_a))
    records.extend(map_feed(read_csv(FIXTURES / "partner_b_day1.csv"), mapping_b))
    # A4 trusts DQ-passed + dedup'd input; mirror the demo pipeline.
    records = [
        r
        for r in records
        if r.canonical.get("dob")
        and r.canonical.get("last_name")
        and r.canonical.get("partner_member_id")
    ]
    deduped: dict[tuple[str, str], StagingRecord] = {}
    for r in records:
        deduped[(r.partner_id, r.canonical["partner_member_id"])] = r
    return list(deduped.values())


def main() -> int:
    records = _load_records()
    print(
        f"Loaded {len(records)} BR-601-deduped staging records "
        f"across PARTNER_A + PARTNER_B day-1 feeds.\n"
    )

    result = resolve(records, thresholds=TierThresholds())
    print(
        f"Identity resolution: algorithm={result.algorithm_version} config={result.config_version}"
    )
    print(f"Canonical member groupings: {len(result.canonical_groups)}\n")

    # Pick representative pairs across tiers from the seeded ground truth.
    inventory = json.loads((FIXTURES / "scenario_inventory.json").read_text())
    cross_match_truths = {
        e["truth_id"] for e in inventory["records"] if e["scenario"] == "cross_partner_near_match"
    }

    by_uid = {d.candidate_record_ref: d for d in result.decisions}

    by_truth: dict[str, list[str]] = {}
    seen_uids: set[str] = set()
    for entry in inventory["records"]:
        if entry["scenario"] != "cross_partner_near_match":
            continue
        # Only consider day-1 feeds (this snippet runs day-1 dedupe).
        if "day1" not in entry["feed"]:
            continue
        partner = "PARTNER_A" if "partner_a" in entry["feed"] else "PARTNER_B"
        uid = f"{partner}:{entry['partner_member_id']}"
        if uid in seen_uids:
            continue
        seen_uids.add(uid)
        by_truth.setdefault(entry["truth_id"], []).append(uid)

    # Tier 2 / Tier 3 cases — cross-partner near-matches.
    print("=" * 78)
    print("CROSS-PARTNER NEAR-MATCH CASES (BR-101 Tier 2 / Tier 3)")
    print("=" * 78)
    for truth_id in sorted(cross_match_truths):
        uids = by_truth.get(truth_id, [])
        if len(uids) < 2:
            continue
        decisions = [by_uid[u] for u in uids if u in by_uid]
        if len(decisions) < 2:
            continue
        d = decisions[0]
        print(f"\nTruth {truth_id}: {' <-> '.join(uids)}")
        print(f"  tier   = {d.tier}")
        print(f"  weight = {d.score:.3f}" if d.score is not None else "  weight = (n/a)")
        merged_member_ids = {x.resolved_member_id for x in decisions}
        print(f"  resolved canonical = {merged_member_ids}")
        if d.score_breakdown:
            print("  per-comparison breakdown (BR-104 explainability):")
            for k in sorted(d.score_breakdown):
                if k.startswith("bf_"):
                    print(f"    {k:20s} = {d.score_breakdown[k]:.3f}")

    # Tier 4 cases — pick a couple of distinct identities for contrast.
    tier4 = [d for d in result.decisions if d.tier == TIER_4][:2]
    if tier4:
        print()
        print("=" * 78)
        print("DISTINCT-IDENTITY CASES (BR-101 Tier 4)")
        print("=" * 78)
        for d in tier4:
            print(f"\n{d.candidate_record_ref}")
            print(f"  tier   = {d.tier}")
            print("  weight = (n/a — singleton or below review threshold)")
            print(f"  resolved canonical = {d.resolved_member_id}")

    # Tier histogram.
    print("\n" + "=" * 78)
    print("TIER HISTOGRAM")
    print("=" * 78)
    counts: dict[str, int] = {}
    for d in result.decisions:
        counts[d.tier] = counts.get(d.tier, 0) + 1
    for tier in sorted(counts):
        print(f"  {tier:30s} {counts[tier]:5d}")

    # Sanity: assert at least one Tier 2 OR Tier 3 surfaced.
    if counts.get(TIER_2, 0) + counts.get(TIER_3, 0) == 0:
        print("\nWARNING: no Tier 2 / Tier 3 matches found — check thresholds.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
