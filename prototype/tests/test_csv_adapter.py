"""Tests for prototype.csv_adapter — A2 format adapter."""

from __future__ import annotations

from pathlib import Path

from prototype.csv_adapter import read_csv, read_csv_columns

REPO_ROOT = Path(__file__).resolve().parents[2]
PARTNER_A_FIXTURE = REPO_ROOT / "prototype" / "fixtures" / "partner_a_day1.csv"
PARTNER_B_FIXTURE = REPO_ROOT / "prototype" / "fixtures" / "partner_b_day1.csv"


def test_read_csv_yields_dicts_keyed_by_source_columns() -> None:
    rows = list(read_csv(PARTNER_A_FIXTURE))
    assert len(rows) >= 200
    sample = rows[0]
    assert "member_id" in sample
    assert "FirstName" in sample
    assert "LastName" in sample


def test_read_csv_columns_returns_header_in_order() -> None:
    cols = read_csv_columns(PARTNER_A_FIXTURE)
    assert cols[0] == "member_id"
    assert cols[1] == "FirstName"
    assert "EligibilityStartDate" not in cols  # day-1, no schema drift yet


def test_partner_b_columns_use_snake_case() -> None:
    cols = read_csv_columns(PARTNER_B_FIXTURE)
    assert "ext_id" in cols
    assert "date_of_birth" in cols
    assert "ssn_last4" in cols


def test_read_csv_writes_no_state(tmp_path: Path) -> None:
    """Reading a feed twice yields equivalent rows — adapter is stateless."""
    rows1 = list(read_csv(PARTNER_A_FIXTURE))
    rows2 = list(read_csv(PARTNER_A_FIXTURE))
    assert rows1 == rows2
