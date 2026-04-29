"""Tests for prototype.synthetic_data — A1 acceptance criteria.

Covers PROTOTYPE_PRD.md A1 acceptance:
- Same seed produces identical output (reproducibility)
- 200–500 records per partner
- Deliberate scenarios documented in inventory: within-feed duplicate,
  cross-partner near-match, missing required field, format errors,
  additive schema drift on day 2, deletion fixture
"""

from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

from prototype.synthetic_data import (
    PARTNER_A_DAY1_COLUMNS,
    PARTNER_A_DAY2_COLUMNS,
    PARTNER_B_COLUMNS,
    generate,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def dataset(tmp_path: Path) -> Any:
    return generate(tmp_path, seed=42, count_per_partner=300)


# ---------------------------------------------------------------------------
# File generation
# ---------------------------------------------------------------------------


def test_generate_creates_four_feeds(dataset: Any) -> None:
    expected = {"partner_a_day1", "partner_a_day2", "partner_b_day1", "partner_b_day2"}
    assert set(dataset.feed_paths) == expected
    for path in dataset.feed_paths.values():
        assert path.exists() and path.stat().st_size > 0


def test_generate_creates_inventory(dataset: Any) -> None:
    assert dataset.inventory_path.exists()
    inventory = json.loads(dataset.inventory_path.read_text())
    assert inventory["seed"] == 42
    assert inventory["partners"] == ["PARTNER_A", "PARTNER_B"]
    assert "records" in inventory and len(inventory["records"]) > 0
    assert "scenarios" in inventory and len(inventory["scenarios"]) > 0


# ---------------------------------------------------------------------------
# Reproducibility
# ---------------------------------------------------------------------------


def test_same_seed_produces_byte_identical_output(tmp_path: Path) -> None:
    out1 = tmp_path / "run1"
    out2 = tmp_path / "run2"
    ds1 = generate(out1, seed=42, count_per_partner=200)
    ds2 = generate(out2, seed=42, count_per_partner=200)
    for key in ds1.feed_paths:
        assert ds1.feed_paths[key].read_bytes() == ds2.feed_paths[key].read_bytes(), (
            f"Feed {key} differs between runs with same seed"
        )
    assert ds1.inventory_path.read_bytes() == ds2.inventory_path.read_bytes()


def test_different_seeds_produce_different_output(tmp_path: Path) -> None:
    out1 = tmp_path / "run1"
    out2 = tmp_path / "run2"
    ds1 = generate(out1, seed=42, count_per_partner=200)
    ds2 = generate(out2, seed=99, count_per_partner=200)
    assert (
        ds1.feed_paths["partner_a_day1"].read_bytes()
        != ds2.feed_paths["partner_a_day1"].read_bytes()
    )


# ---------------------------------------------------------------------------
# Partner schema differences (exercises A2 mapping engine)
# ---------------------------------------------------------------------------


def test_partner_a_day1_columns(dataset: Any) -> None:
    cols = _csv_header(dataset.feed_paths["partner_a_day1"])
    assert cols == PARTNER_A_DAY1_COLUMNS


def test_partner_b_columns(dataset: Any) -> None:
    cols = _csv_header(dataset.feed_paths["partner_b_day1"])
    assert cols == PARTNER_B_COLUMNS


def test_partner_a_day2_has_additive_schema_drift(dataset: Any) -> None:
    day1_cols = _csv_header(dataset.feed_paths["partner_a_day1"])
    day2_cols = _csv_header(dataset.feed_paths["partner_a_day2"])
    new_cols = set(day2_cols) - set(day1_cols)
    assert "EligibilityStartDate" in new_cols
    assert day2_cols == PARTNER_A_DAY2_COLUMNS


def test_partner_a_uses_us_date_format(dataset: Any) -> None:
    rows = _read_csv(dataset.feed_paths["partner_a_day1"])
    populated = [r["DOB"] for r in rows if r["DOB"]]
    assert populated, "Expected at least one populated DOB"
    sample = populated[0]
    parts = sample.split("/")
    assert len(parts) == 3, f"Expected MM/DD/YYYY format, got {sample}"
    assert len(parts[2]) == 4


def test_partner_b_uses_iso_date_format(dataset: Any) -> None:
    rows = _read_csv(dataset.feed_paths["partner_b_day1"])
    populated = [r["date_of_birth"] for r in rows if r["date_of_birth"]]
    assert populated, "Expected at least one populated DOB"
    sample = populated[0]
    parts = sample.split("-")
    assert len(parts) == 3, f"Expected YYYY-MM-DD format, got {sample}"
    assert len(parts[0]) == 4


def test_partner_b_ssn_is_last_four_only(dataset: Any) -> None:
    rows = _read_csv(dataset.feed_paths["partner_b_day1"])
    populated = [r["ssn_last4"] for r in rows if r["ssn_last4"]]
    assert populated, "Expected at least one populated SSN"
    for ssn in populated[:10]:
        assert ssn.isdigit() and len(ssn) == 4, f"Expected 4-digit ssn_last4, got {ssn!r}"


def test_partner_a_ssn_is_full_format(dataset: Any) -> None:
    rows = _read_csv(dataset.feed_paths["partner_a_day1"])
    populated = [r["SSN"] for r in rows if r["SSN"]]
    assert populated, "Expected at least one populated SSN"
    sample = populated[0]
    parts = sample.split("-")
    assert len(parts) == 3 and len(parts[2]) == 4, f"Expected XXX-XX-XXXX, got {sample!r}"


# ---------------------------------------------------------------------------
# Volume
# ---------------------------------------------------------------------------


def test_partner_a_record_count_in_expected_range(dataset: Any) -> None:
    rows = _read_csv(dataset.feed_paths["partner_a_day1"])
    assert 200 <= len(rows) <= 600, (
        f"PRD says 200–500/partner; allow slack for injected rows. Got {len(rows)}"
    )


def test_partner_b_record_count_in_expected_range(dataset: Any) -> None:
    rows = _read_csv(dataset.feed_paths["partner_b_day1"])
    assert 200 <= len(rows) <= 600


# ---------------------------------------------------------------------------
# Deliberate scenarios (acceptance: 5–10 problematic rows per feed)
# ---------------------------------------------------------------------------


def test_within_feed_duplicate_present_in_partner_a_day1(dataset: Any) -> None:
    rows = _read_csv(dataset.feed_paths["partner_a_day1"])
    member_ids = [r["member_id"] for r in rows]
    counts = Counter(member_ids)
    duplicates = {mid for mid, n in counts.items() if n > 1}
    assert duplicates, "Expected at least one within-feed duplicate"


def test_cross_partner_near_match_inventoried(dataset: Any) -> None:
    """At least one truth_id appears in BOTH partner_a and partner_b feeds with mutation."""
    inventory = json.loads(dataset.inventory_path.read_text())
    near_matches = [
        r for r in inventory["records"] if r.get("scenario") == "cross_partner_near_match"
    ]
    by_truth: dict[str, set[str]] = {}
    for entry in near_matches:
        tid = entry.get("truth_id")
        if not tid:
            continue
        feed = entry["feed"]
        partner = "a" if "partner_a" in feed else "b"
        by_truth.setdefault(tid, set()).add(partner)
    cross_pairs = [tid for tid, partners in by_truth.items() if {"a", "b"}.issubset(partners)]
    assert cross_pairs, (
        "Expected at least one truth_id present in both partner_a and partner_b feeds"
    )


def test_missing_required_field_inventoried(dataset: Any) -> None:
    inventory = json.loads(dataset.inventory_path.read_text())
    missing = [r for r in inventory["records"] if r.get("scenario") == "missing_required_last_name"]
    assert len(missing) >= 1


def test_invalid_required_field_inventoried(dataset: Any) -> None:
    inventory = json.loads(dataset.inventory_path.read_text())
    invalid = [r for r in inventory["records"] if r.get("scenario") == "invalid_required_dob"]
    assert len(invalid) >= 1


def test_format_error_short_year_inventoried(dataset: Any) -> None:
    inventory = json.loads(dataset.inventory_path.read_text())
    format_errors = [
        r for r in inventory["records"] if r.get("scenario") == "format_error_short_year"
    ]
    assert len(format_errors) >= 1


def test_deletion_fixture_spans_a_day1_and_b_day2(dataset: Any) -> None:
    """The deletion-then-reintroduce fixture lives across two feeds."""
    inventory = json.loads(dataset.inventory_path.read_text())
    fixtures = [r for r in inventory["records"] if r.get("scenario") == "deletion_fixture"]
    feeds = {entry["feed"] for entry in fixtures}
    assert "partner_a_day1.csv" in feeds, "Deletion fixture must originate on PARTNER_A day 1"
    assert "partner_b_day2.csv" in feeds, "Deletion fixture must reintroduce on PARTNER_B day 2"


def test_deletion_fixture_absent_from_partner_a_day2(dataset: Any) -> None:
    """The fixture record must NOT appear on PARTNER_A day 2 (the 'deletion' between days)."""
    inventory = json.loads(dataset.inventory_path.read_text())
    fixture_a_day1 = next(
        r
        for r in inventory["records"]
        if r.get("scenario") == "deletion_fixture" and r["feed"] == "partner_a_day1.csv"
    )
    member_id = fixture_a_day1["partner_member_id"]
    rows_day2 = _read_csv(dataset.feed_paths["partner_a_day2"])
    day2_ids = {r["member_id"] for r in rows_day2}
    assert member_id not in day2_ids, (
        f"Deletion fixture {member_id} must be absent from PARTNER_A day 2"
    )


def test_each_feed_has_at_least_five_problematic_rows(dataset: Any) -> None:
    """PRD acceptance: 5–10 deliberately problematic rows per feed."""
    inventory = json.loads(dataset.inventory_path.read_text())
    by_feed: Counter[str] = Counter()
    for entry in inventory["records"]:
        if entry.get("scenario") and entry["scenario"] != "clean":
            by_feed[entry["feed"]] += 1
    for feed in (
        "partner_a_day1.csv",
        "partner_a_day2.csv",
        "partner_b_day1.csv",
        "partner_b_day2.csv",
    ):
        assert by_feed[feed] >= 5, (
            f"{feed} has only {by_feed[feed]} problematic rows; PRD requires >= 5"
        )


# ---------------------------------------------------------------------------
# PII shape (no real PII — Faker uses fictional ranges)
# ---------------------------------------------------------------------------


def test_no_real_ssn_prefixes(dataset: Any) -> None:
    """Faker en_US uses non-issued SSN prefixes (e.g., 9XX, 666). Sanity-check."""
    rows = _read_csv(dataset.feed_paths["partner_a_day1"])
    for r in rows:
        ssn = r.get("SSN", "")
        if not ssn:
            continue
        prefix = ssn.split("-")[0]
        # Real issued SSNs never start with 000, 666, or 9XX.
        # Faker is supposed to use these reserved ranges — sanity check.
        assert prefix in ("000", "666") or prefix.startswith("9"), (
            f"SSN {ssn!r} has prefix {prefix} which may be a real issued range"
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def _csv_header(path: Path) -> list[str]:
    with path.open(newline="") as f:
        return next(csv.reader(f))
