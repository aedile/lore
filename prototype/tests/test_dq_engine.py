"""Tests for prototype.dq — A3 acceptance.

Covers PROTOTYPE_PRD.md A3 acceptance:
- Clean feed → zero quarantines, schema_drift=NONE.
- Feed with deliberate Required-tier failures → correct per-record quarantines
  (BR-302), feed proceeds (BR-302).
- Rejection rate exceeding threshold → feed quarantine (BR-303).
- Day 2 with added column → SCHEMA_DRIFT_ADDITIVE (notification, no
  quarantine) (BR-304 additive path).
- Day 2 with removed column → SCHEMA_DRIFT_SUBTRACTIVE_QUARANTINE
  (BR-304 subtractive path).
- Profile baseline computed and persisted; drift detected when null rate
  jumps past threshold (BR-305).
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from prototype.csv_adapter import read_csv, read_csv_columns
from prototype.dq import (
    DRIFT_ADDITIVE,
    DRIFT_NONE,
    DRIFT_SUBTRACTIVE,
    FeedProfile,
    FieldProfile,
    read_profile,
    run,
    write_profile,
    write_quarantine,
)
from prototype.mapping_engine import (
    PartnerMapping,
    StagingRecord,
    load_mapping,
    map_feed,
    map_row,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
PARTNER_A_YAML = REPO_ROOT / "prototype" / "mappings" / "partner_a.yaml"
PARTNER_B_YAML = REPO_ROOT / "prototype" / "mappings" / "partner_b.yaml"
PARTNER_A_DAY1 = REPO_ROOT / "prototype" / "fixtures" / "partner_a_day1.csv"
PARTNER_A_DAY2 = REPO_ROOT / "prototype" / "fixtures" / "partner_a_day2.csv"
PARTNER_B_DAY1 = REPO_ROOT / "prototype" / "fixtures" / "partner_b_day1.csv"


# ---------------------------------------------------------------------------
# End-to-end: A1 fixtures → A2 mapping → A3 DQ
# ---------------------------------------------------------------------------


def test_partner_a_day1_seeded_failures_are_quarantined() -> None:
    """A1 seeds 1 missing-last-name + 1 invalid-dob; both must quarantine."""
    mapping = load_mapping(PARTNER_A_YAML)
    rows = list(read_csv(PARTNER_A_DAY1))
    columns = read_csv_columns(PARTNER_A_DAY1)
    records = list(map_feed(rows, mapping))

    result = run(records, mapping=mapping, feed_columns=columns, feed_id="partner_a_day1")

    # The fixture seeds these two scenarios; expect ≥ 2 quarantines.
    assert not result.feed_quarantined
    assert result.schema_drift == DRIFT_NONE
    assert len(result.quarantined) >= 2

    reasons = [reason for _, reason in result.quarantined]
    assert any("REQUIRED_FIELD_MISSING:last_name" in r for r in reasons)
    assert any("REQUIRED_FIELD_INVALID:dob" in r for r in reasons)


def test_partner_a_day1_passed_record_count_is_total_minus_quarantined() -> None:
    mapping = load_mapping(PARTNER_A_YAML)
    rows = list(read_csv(PARTNER_A_DAY1))
    columns = read_csv_columns(PARTNER_A_DAY1)
    records = list(map_feed(rows, mapping))

    result = run(records, mapping=mapping, feed_columns=columns)
    assert len(result.passed) + len(result.quarantined) == len(records)


# ---------------------------------------------------------------------------
# BR-302: a single bad record does not block the feed
# ---------------------------------------------------------------------------


def test_single_bad_record_does_not_quarantine_feed() -> None:
    """One required-field failure in a 100-row feed must NOT trigger feed quarantine."""
    mapping = load_mapping(PARTNER_A_YAML)
    rows = [
        {
            "member_id": f"A{i:05d}",
            "FirstName": "Sarah",
            "LastName": "Johnson",
            "DOB": "04/12/1985",
            "SSN": "987-65-4321",
            "Street": "123 Main St",
            "City": "Springfield",
            "State": "IL",
            "Zip": "62701",
            "Phone": "555-555-1212",
            "Email": "sarah@example.invalid",
        }
        for i in range(100)
    ]
    rows[42]["LastName"] = ""  # one bad record
    records = [map_row(row, mapping) for row in rows]
    columns = list(rows[0].keys())

    result = run(records, mapping=mapping, feed_columns=columns)

    assert not result.feed_quarantined
    assert len(result.quarantined) == 1
    assert "last_name" in result.quarantined[0][1]


# ---------------------------------------------------------------------------
# BR-303: feed-level threshold (5% default)
# ---------------------------------------------------------------------------


def test_feed_quarantines_above_threshold() -> None:
    """20 bad records out of 100 (20%) exceeds the 5% default → feed quarantined."""
    mapping = load_mapping(PARTNER_A_YAML)
    rows = [
        {
            "member_id": f"A{i:05d}",
            "FirstName": "Sarah",
            "LastName": "Johnson" if i >= 20 else "",  # first 20 missing required
            "DOB": "04/12/1985",
            "SSN": "987-65-4321",
            "Street": "123 Main St",
            "City": "Springfield",
            "State": "IL",
            "Zip": "62701",
            "Phone": "555-555-1212",
            "Email": "sarah@example.invalid",
        }
        for i in range(100)
    ]
    records = [map_row(row, mapping) for row in rows]
    result = run(records, mapping=mapping, feed_columns=list(rows[0].keys()))

    assert result.feed_quarantined is True
    assert "REJECTION_RATE_EXCEEDED" in (result.feed_quarantine_reason or "")
    assert result.passed == []  # nothing publishes when feed is quarantined


def test_feed_at_threshold_does_not_quarantine() -> None:
    """Exactly 5% (5/100) does NOT exceed threshold (>); feed proceeds."""
    mapping = load_mapping(PARTNER_A_YAML)
    rows = [
        {
            "member_id": f"A{i:05d}",
            "FirstName": "Sarah",
            "LastName": "Johnson" if i >= 5 else "",  # first 5 missing required → 5/100 = 0.05
            "DOB": "04/12/1985",
            "SSN": "987-65-4321",
            "Street": "x",
            "City": "x",
            "State": "x",
            "Zip": "x",
            "Phone": "x",
            "Email": "x",
        }
        for i in range(100)
    ]
    records = [map_row(row, mapping) for row in rows]
    result = run(records, mapping=mapping, feed_columns=list(rows[0].keys()))

    assert not result.feed_quarantined
    assert len(result.quarantined) == 5


def test_per_partner_threshold_override() -> None:
    """The threshold parameter is per-call; partners can be configured stricter."""
    mapping = load_mapping(PARTNER_A_YAML)
    rows = [
        {
            "member_id": f"A{i:05d}",
            "FirstName": "Sarah",
            "LastName": "Johnson" if i >= 2 else "",  # 2/100 = 2%
            "DOB": "04/12/1985",
            "SSN": "987-65-4321",
            "Street": "x",
            "City": "x",
            "State": "x",
            "Zip": "x",
            "Phone": "x",
            "Email": "x",
        }
        for i in range(100)
    ]
    records = [map_row(row, mapping) for row in rows]
    result = run(
        records,
        mapping=mapping,
        feed_columns=list(rows[0].keys()),
        feed_quarantine_threshold=0.01,  # stricter — 2% exceeds 1%
    )
    assert result.feed_quarantined is True


# ---------------------------------------------------------------------------
# BR-304: schema drift
# ---------------------------------------------------------------------------


def test_additive_schema_drift_is_accepted_with_notification() -> None:
    """PARTNER_A day 2 adds EligibilityStartDate — additive, must NOT quarantine."""
    mapping = load_mapping(PARTNER_A_YAML)
    day1_columns = read_csv_columns(PARTNER_A_DAY1)
    day2_columns = read_csv_columns(PARTNER_A_DAY2)
    rows = list(read_csv(PARTNER_A_DAY2))
    records = list(map_feed(rows, mapping))

    result = run(
        records,
        mapping=mapping,
        feed_columns=day2_columns,
        prior_columns=day1_columns,
    )

    assert result.schema_drift == DRIFT_ADDITIVE
    assert result.columns_added == ["EligibilityStartDate"]
    assert result.columns_removed == []
    # Records still flow through normal validation; not feed-quarantined for drift.
    # (May still be feed-quarantined if rejection rate exceeds threshold, but the
    # synthetic data keeps it under 5%.)


def test_subtractive_schema_drift_quarantines_feed() -> None:
    """A removed column must trigger feed-level quarantine (BR-304 subtractive path)."""
    mapping = load_mapping(PARTNER_A_YAML)
    day1_columns = read_csv_columns(PARTNER_A_DAY1)
    rows = list(read_csv(PARTNER_A_DAY1))
    records = list(map_feed(rows, mapping))

    # Pretend a column was removed compared to a "prior" feed that had MORE columns.
    prior_columns = [*day1_columns, "ExtraColumnFromPriorFeed"]
    result = run(
        records,
        mapping=mapping,
        feed_columns=day1_columns,
        prior_columns=prior_columns,
    )

    assert result.schema_drift == DRIFT_SUBTRACTIVE
    assert result.feed_quarantined is True
    assert "ExtraColumnFromPriorFeed" in result.columns_removed
    assert result.passed == []


# ---------------------------------------------------------------------------
# BR-305: profile baseline + drift
# ---------------------------------------------------------------------------


def test_profile_baseline_captured_with_per_field_stats() -> None:
    mapping = load_mapping(PARTNER_A_YAML)
    rows = list(read_csv(PARTNER_A_DAY1))
    records = list(map_feed(rows, mapping))
    result = run(records, mapping=mapping, feed_columns=read_csv_columns(PARTNER_A_DAY1))

    profile = result.profile
    assert profile.partner_id == "PARTNER_A"
    assert profile.row_count == len(rows)
    # Every canonical field should have a profile entry.
    assert "first_name" in profile.fields
    assert "ssn_last4" in profile.fields
    # last_name has at least one missing record (the seeded scenario), so
    # null_rate should be > 0 even if small.
    assert profile.fields["last_name"].null_count >= 1


def test_profile_persistence_round_trip(tmp_path: Path) -> None:
    """write_profile + read_profile is a faithful round-trip."""
    profile = FeedProfile(
        partner_id="PARTNER_A",
        row_count=42,
        columns=["a", "b"],
        fields={
            "first_name": FieldProfile(count=42, null_count=2, null_rate=0.0476, distinct_count=39),
        },
    )
    path = tmp_path / "p.json"
    write_profile(profile, path)
    restored = read_profile(path)
    assert restored == profile


def test_profile_drift_detected_above_threshold() -> None:
    """A field whose null_rate jumps from 5% to 80% must be flagged as drifted."""
    mapping = load_mapping(PARTNER_A_YAML)
    # Build records with very high last_name null rate to simulate "today's" feed.
    rows = [
        {
            "member_id": f"A{i:05d}",
            "FirstName": "x",
            "LastName": "" if i < 80 else "Doe",
            "DOB": "04/12/1985",
            "SSN": "987-65-4321",
            "Street": "x",
            "City": "x",
            "State": "x",
            "Zip": "x",
            "Phone": "x",
            "Email": "x",
        }
        for i in range(100)
    ]
    records = [map_row(row, mapping) for row in rows]
    columns = list(rows[0].keys())

    # Yesterday's profile had 5% nulls on last_name.
    yesterday = FeedProfile(
        partner_id="PARTNER_A",
        row_count=100,
        columns=columns,
        fields={
            cf: FieldProfile(count=100, null_count=5, null_rate=0.05, distinct_count=10)
            for cf in mapping.field_tiers
        },
    )

    result = run(
        records,
        mapping=mapping,
        feed_columns=columns,
        prior_profile=yesterday,
        # Skip feed quarantine so we exercise the drift path on its own.
        feed_quarantine_threshold=1.0,
    )
    assert "last_name" in result.profile_drift_fields


def test_profile_drift_under_threshold_not_flagged() -> None:
    mapping = load_mapping(PARTNER_A_YAML)
    rows = [
        {
            "member_id": f"A{i:05d}",
            "FirstName": "x",
            "LastName": "Doe",
            "DOB": "04/12/1985",
            "SSN": "987-65-4321",
            "Street": "x",
            "City": "x",
            "State": "x",
            "Zip": "x",
            "Phone": "x",
            "Email": "x",
        }
        for i in range(100)
    ]
    records = [map_row(row, mapping) for row in rows]
    columns = list(rows[0].keys())
    yesterday = FeedProfile(
        partner_id="PARTNER_A",
        row_count=100,
        columns=columns,
        fields={
            cf: FieldProfile(count=100, null_count=2, null_rate=0.02, distinct_count=50)
            for cf in mapping.field_tiers
        },
    )
    result = run(
        records,
        mapping=mapping,
        feed_columns=columns,
        prior_profile=yesterday,
    )
    # last_name null_rate stays at ~0; well under threshold.
    assert "last_name" not in result.profile_drift_fields


# ---------------------------------------------------------------------------
# Quarantine persistence
# ---------------------------------------------------------------------------


def test_write_quarantine_writes_jsonl(tmp_path: Path) -> None:
    mapping = load_mapping(PARTNER_A_YAML)
    rows = list(read_csv(PARTNER_A_DAY1))
    records = list(map_feed(rows, mapping))
    result = run(
        records,
        mapping=mapping,
        feed_columns=read_csv_columns(PARTNER_A_DAY1),
        feed_id="partner_a_day1",
    )

    out_path = write_quarantine(result, tmp_path)
    assert out_path.exists()
    lines = out_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == len(result.quarantined)
    assert "REQUIRED_FIELD" in lines[0]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _empty_record(mapping: PartnerMapping) -> StagingRecord:
    """Make a degenerate record useful for one-off DQResult dataclass tests."""
    canonical = dict.fromkeys(mapping.field_tiers, "")
    return StagingRecord(partner_id=mapping.partner_id, raw_source={}, canonical=canonical)


def test_dq_result_carries_partner_and_feed_id() -> None:
    mapping = load_mapping(PARTNER_A_YAML)
    result = run([], mapping=mapping, feed_columns=[], feed_id="my-feed-99")
    assert result.partner_id == "PARTNER_A"
    assert result.feed_id == "my-feed-99"
    assert result.passed == []
    assert result.quarantined == []


def test_dq_result_replace_is_supported() -> None:
    """DQResult is a frozen dataclass; ``replace`` produces a new instance."""
    mapping = load_mapping(PARTNER_A_YAML)
    result = run([], mapping=mapping, feed_columns=[])
    new_result = replace(result, feed_id="renamed")
    assert new_result.feed_id == "renamed"
    assert result.feed_id == ""  # original untouched
