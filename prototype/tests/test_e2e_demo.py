"""End-to-end demo test — covers PRD §"Acceptance Criteria for 'Done'".

Runs the full prototype pipeline against a temp Postgres (pytest-postgresql)
and asserts every numbered acceptance criterion the PRD lists. This is the
pre-flight check before the panel demo: if this passes, the live demo
should run.

We consolidate every PRD acceptance check into a single big test so we
only run the (slow) Splink-backed demo once. Each acceptance criterion is
a labelled assertion block.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from prototype.audit import AuditChain, RedactionScanner
from prototype.canonical import CanonicalState
from prototype.demo import run_full_demo
from prototype.identity import TIER_2, TIER_4
from prototype.tokenization import tokenize_dob, tokenize_name
from prototype.verification import (
    NOT_VERIFIED,
    VERIFIED,
    InMemoryCanonicalLookup,
    InMemoryMember,
    VerificationSettings,
    create_app,
)

pytest_plugins = ["pytest_postgresql"]

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = REPO_ROOT / "prototype" / "fixtures"


def test_e2e_demo_satisfies_prd_acceptance_criteria(postgresql, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    """PRD §Acceptance Criteria for 'Done' — all numbered items asserted here.

    Runs the full demo (~5-15 seconds) and asserts each acceptance criterion
    in a labelled block so failures point at the specific PRD item.
    """
    result = run_full_demo(
        postgresql,
        fixtures_dir=FIXTURES,
        output_dir=tmp_path,
    )

    # ----- PRD #1: Day-1 pipeline runs end-to-end without errors. -----
    assert len(result.day1.feeds) == 2, "Expected 2 partner feeds on day 1"
    for feed in result.day1.feeds:
        assert feed.feed_quarantined is False, (
            f"Day-1 {feed.partner_id} should not be feed-quarantined: drift={feed.schema_drift}"
        )
    assert result.day1.canonical_inserted >= 100, (
        f"Day-1 canonical_member inserts: {result.day1.canonical_inserted}"
    )
    assert result.day1.enrollments_inserted >= result.day1.canonical_inserted
    assert result.day1.match_decisions_inserted >= result.day1.canonical_inserted

    # ----- PRD #2: Day-2 pipeline runs producing SCD2 history + suppression. -----
    assert len(result.day2.feeds) == 2, "Expected 2 partner feeds on day 2"
    assert result.day2.member_history_inserted >= 1, "Day 2 must emit SCD2 history rows"
    partner_a_day2 = next(f for f in result.day2.feeds if f.partner_id == "PARTNER_A")
    assert partner_a_day2.schema_drift in ("ADDITIVE", "NONE"), (
        f"Day-2 PARTNER_A drift expected ADDITIVE/NONE, got {partner_a_day2.schema_drift}"
    )
    assert partner_a_day2.feed_quarantined is False

    # ----- PRD #3: Splink demo produces match weights for Tier 2/3/4 cases. -----
    from prototype.identity import TIER_1, TIER_3

    # Day 2 must produce TIER_1 matches — this is the Tier-1-against-existing-
    # canonical path. If 0, the existing_canonical wiring regressed.
    assert result.day2.tier_histogram.get(TIER_1, 0) >= 100, (
        f"Day-2 should auto-merge most repeat partner_member_ids via Tier 1; "
        f"got histogram={result.day2.tier_histogram}"
    )

    total_tier2 = result.day1.tier_histogram.get(TIER_2, 0) + result.day2.tier_histogram.get(
        TIER_2, 0
    )
    total_tier3 = result.day1.tier_histogram.get(TIER_3, 0) + result.day2.tier_histogram.get(
        TIER_3, 0
    )
    total_tier4 = result.day1.tier_histogram.get(TIER_4, 0) + result.day2.tier_histogram.get(
        TIER_4, 0
    )
    assert total_tier2 >= 1, (
        f"At least one Tier 2 match expected; got histogram "
        f"day1={result.day1.tier_histogram} day2={result.day2.tier_histogram}"
    )
    assert total_tier3 >= 1, (
        f"At least one Tier 3 review-queue case expected (engineered "
        f"doppelganger fixtures); got histogram day1={result.day1.tier_histogram} "
        f"day2={result.day2.tier_histogram}"
    )
    assert total_tier4 > total_tier2, "Tier 4 should dominate (most identities are unique)"
    # review_queue rows persisted for Tier 3 outcomes (PRD A4 acceptance).
    assert result.day1.review_queue_inserted >= 1, (
        "Day-1 should populate review_queue for engineered Tier 3 doppelgangers."
    )

    # ----- PRD #4: Verification API across internal-state combinations. -----
    members = [
        InMemoryMember(
            member_id="m-active",
            name_token=tokenize_name("Sarah", "Johnson"),
            dob_token=tokenize_dob("1985-04-12"),
            state=CanonicalState.ELIGIBLE_ACTIVE,
        ),
        InMemoryMember(
            member_id="m-grace",
            name_token=tokenize_name("Mark", "Smith"),
            dob_token=tokenize_dob("1970-01-01"),
            state=CanonicalState.ELIGIBLE_GRACE,
        ),
        InMemoryMember(
            member_id="m-ineligible",
            name_token=tokenize_name("Jane", "Doe"),
            dob_token=tokenize_dob("1960-06-15"),
            state=CanonicalState.INELIGIBLE,
        ),
        InMemoryMember(
            member_id="m-deleted",
            name_token=tokenize_name("John", "Smith"),
            dob_token=tokenize_dob("1955-12-31"),
            state=CanonicalState.DELETED,
        ),
    ]
    client = TestClient(
        create_app(
            lookup=InMemoryCanonicalLookup(members),
            settings=VerificationSettings(response_floor_ms=0.0),
        )
    )
    cases = [
        ("Sarah", "Johnson", "1985-04-12", VERIFIED),
        ("Mark", "Smith", "1970-01-01", NOT_VERIFIED),
        ("Jane", "Doe", "1960-06-15", NOT_VERIFIED),
        ("John", "Smith", "1955-12-31", NOT_VERIFIED),
        ("Unknown", "Person", "2000-01-01", NOT_VERIFIED),
    ]
    for first, last, dob, expected in cases:
        body = {
            "claim": {"first_name": first, "last_name": last, "date_of_birth": dob},
            "context": {"client_id": "e2e", "request_id": "req-x"},
        }
        response = client.post("/v1/verify", json=body)
        assert response.json() == {"status": expected}, (first, last, expected)

    # ----- PRD #5: Audit chain validates clean across the full run. -----
    assert result.audit_chain_validation.valid is True, (
        f"Chain validation failed: {result.audit_chain_validation.error} "
        f"at line {result.audit_chain_validation.broken_at_line}"
    )
    assert result.audit_event_count >= 7, (
        f"Expected meaningful audit volume; got {result.audit_event_count}"
    )

    # ----- PRD #6: Redaction scanner reports zero matches. -----
    assert result.redaction_matches == [], (
        f"PII leaked into audit chain: {result.redaction_matches}"
    )
    rerun = RedactionScanner().scan_jsonl(result.audit_chain_path)
    assert rerun == []

    # ----- PRD #7: Deletion → reintroduce → SUPPRESSED_DELETED automatic. -----
    assert result.day2.suppressed_count >= 1, (
        f"Day-2 suppression count: {result.day2.suppressed_count}; "
        "BR-703 should catch the deletion-fixture reintroduction"
    )
    chain = AuditChain(result.audit_chain_path)
    classes = [entry.get("event_class") for entry in chain]
    assert "SUPPRESSED_DELETED" in classes
    assert "DELETION_REQUESTED" in classes
    assert "DELETION_EXECUTED" in classes


def test_demo_chain_tampering_is_detected(postgresql, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    """Defensive: tamper one entry in the demo's audit chain; validate must fail."""
    import json

    from prototype.audit import AuditChain

    result = run_full_demo(
        postgresql,
        fixtures_dir=FIXTURES,
        output_dir=tmp_path,
    )
    path = result.audit_chain_path
    lines = path.read_text(encoding="utf-8").splitlines()
    target_index = next(
        i for i, line in enumerate(lines) if json.loads(line).get("event_class") == "FEED_INGESTED"
    )
    tampered = json.loads(lines[target_index])
    tampered["outcome"] = "TAMPERED"
    lines[target_index] = json.dumps(tampered, sort_keys=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    validation = AuditChain(path).validate()
    assert validation.valid is False
    assert validation.broken_at_line == target_index + 1


# Quiet F401 so the linter doesn't strip pytest's pre-imported helpers.
_ = pytest
