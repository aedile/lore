"""Tests for prototype.mapping_engine — A2 acceptance.

Covers PROTOTYPE_PRD.md A2 acceptance:
- Adding a third synthetic partner requires only a new YAML file (no code
  change). This test loads a synthetic partner_c YAML in a tmp dir and
  exercises the mapping engine against it.
- PARTNER_A's full-SSN format and PARTNER_B's last4-only format both produce
  a populated canonical ``ssn_last4`` field.
- Date formats normalize to canonical ISO YYYY-MM-DD across both partners.
- Format-error-short-year DOBs are caught by the alternate-format fallback.
- Empty required-tier values produce a parse_error entry that A3 will read.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from prototype.csv_adapter import read_csv
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
PARTNER_A_FIXTURE = REPO_ROOT / "prototype" / "fixtures" / "partner_a_day1.csv"
PARTNER_B_FIXTURE = REPO_ROOT / "prototype" / "fixtures" / "partner_b_day1.csv"


# ---------------------------------------------------------------------------
# YAML loading
# ---------------------------------------------------------------------------


def test_load_partner_a_mapping() -> None:
    m = load_mapping(PARTNER_A_YAML)
    assert m.partner_id == "PARTNER_A"
    assert m.date_format == "%m/%d/%Y"
    assert m.ssn_field == "full"
    assert m.mapping["partner_member_id"] == "member_id"
    assert m.field_tiers["last_name"] == "required"
    assert m.field_tiers["phone"] == "enrichment"


def test_load_partner_b_mapping() -> None:
    m = load_mapping(PARTNER_B_YAML)
    assert m.partner_id == "PARTNER_B"
    assert m.date_format == "%Y-%m-%d"
    assert m.ssn_field == "last4"
    assert m.mapping["partner_member_id"] == "ext_id"


# ---------------------------------------------------------------------------
# Per-row mapping
# ---------------------------------------------------------------------------


def test_map_row_partner_a_clean_record() -> None:
    m = load_mapping(PARTNER_A_YAML)
    row = {
        "member_id": "A00001",
        "FirstName": "Sarah",
        "LastName": "Johnson",
        "DOB": "04/12/1985",
        "SSN": "987-65-4321",
        "Street": "123 Main St",
        "City": "Springfield",
        "State": "IL",
        "Zip": "62701",
        "Phone": "555-555-1212",
        "Email": "Sarah.Johnson@Example.com",
    }
    record = map_row(row, m)
    assert record.partner_id == "PARTNER_A"
    assert record.canonical["partner_member_id"] == "A00001"
    assert record.canonical["first_name"] == "Sarah"
    assert record.canonical["last_name"] == "Johnson"
    assert record.canonical["dob"] == "1985-04-12"  # normalized to ISO
    assert record.canonical["ssn"] == "987-65-4321"
    assert record.canonical["ssn_last4"] == "4321"  # derived from full SSN
    assert record.canonical["email"] == "sarah.johnson@example.com"  # lowercased
    assert record.parse_errors == {}


def test_map_row_partner_b_clean_record() -> None:
    m = load_mapping(PARTNER_B_YAML)
    row = {
        "ext_id": "B00001",
        "given_name": "Sarah",
        "family_name": "Johnson",
        "date_of_birth": "1985-04-12",
        "ssn_last4": "4321",
        "address_line1": "123 Main St",
        "address_city": "Springfield",
        "address_state": "IL",
        "address_zip": "62701",
        "phone_number": "555-555-1212",
        "email_address": "Sarah.Johnson@Example.com",
    }
    record = map_row(row, m)
    assert record.canonical["partner_member_id"] == "B00001"
    assert record.canonical["dob"] == "1985-04-12"
    assert record.canonical["ssn_last4"] == "4321"
    assert "ssn" not in record.canonical  # PARTNER_B does not send full SSN


def test_short_year_dob_uses_alternate_format() -> None:
    """The format_error_short_year scenario from A1: '4/12/85' parses via alternate."""
    m = load_mapping(PARTNER_A_YAML)
    row = {"member_id": "A99999", "DOB": "4/12/85"}
    record = map_row(row, m)
    # 2-digit year resolves via %y; '85' -> 1985 by Python's century rules.
    assert record.canonical["dob"] == "1985-04-12"
    assert record.parse_errors == {}


def test_unparseable_dob_records_error() -> None:
    m = load_mapping(PARTNER_A_YAML)
    row = {"member_id": "A99998", "DOB": "not-a-date"}
    record = map_row(row, m)
    assert record.canonical["dob"] == ""
    assert "dob" in record.parse_errors


def test_empty_dob_records_error() -> None:
    """The invalid_required_dob scenario from A1: empty DOB → parse_error 'empty'."""
    m = load_mapping(PARTNER_A_YAML)
    row = {"member_id": "A99997", "DOB": ""}
    record = map_row(row, m)
    assert record.canonical["dob"] == ""
    assert record.parse_errors.get("dob") == "empty"


def test_empty_required_field_carried_through_canonical() -> None:
    """The missing_required_last_name scenario: empty LastName → empty in canonical."""
    m = load_mapping(PARTNER_A_YAML)
    row = {"member_id": "A99996", "LastName": "", "FirstName": "Sarah", "DOB": "04/12/1985"}
    record = map_row(row, m)
    assert record.canonical["last_name"] == ""
    assert record.canonical["first_name"] == "Sarah"


# ---------------------------------------------------------------------------
# Whole-feed mapping over the A1 fixtures
# ---------------------------------------------------------------------------


def test_map_partner_a_day1_fixture_round_trip() -> None:
    m = load_mapping(PARTNER_A_YAML)
    rows = list(read_csv(PARTNER_A_FIXTURE))
    assert len(rows) >= 200
    records = list(map_feed(rows, m))
    assert len(records) == len(rows)
    # At least one valid DOB normalized to ISO.
    iso_dobs = [r.canonical["dob"] for r in records if r.canonical["dob"]]
    assert iso_dobs, "Expected at least one record with a parsed DOB"
    sample = iso_dobs[0]
    parts = sample.split("-")
    assert len(parts) == 3
    assert len(parts[0]) == 4


def test_map_partner_b_day1_fixture_round_trip() -> None:
    m = load_mapping(PARTNER_B_YAML)
    rows = list(read_csv(PARTNER_B_FIXTURE))
    records = list(map_feed(rows, m))
    assert len(records) == len(rows)
    last4s = [r.canonical["ssn_last4"] for r in records if r.canonical["ssn_last4"]]
    assert last4s, "Expected at least one ssn_last4"
    for last4 in last4s[:5]:
        assert last4.isdigit()
        assert len(last4) == 4


# ---------------------------------------------------------------------------
# YAML-only-onboarding property (the A2 acceptance criterion)
# ---------------------------------------------------------------------------


def test_third_partner_onboarded_via_yaml_only(tmp_path: Path) -> None:
    """A net-new partner with totally different column names + date format
    is mapped using only a new YAML file — no code change."""
    partner_c_yaml = tmp_path / "partner_c.yaml"
    yaml_content = {
        "partner_id": "PARTNER_C",
        "format": "csv",
        "date_format": "%d-%b-%Y",  # e.g. "12-Apr-1985" — neither A nor B uses this
        "date_format_alternates": [],
        "ssn_field": "full",
        "mapping": {
            "partner_member_id": "MEMBER_NUMBER",
            "first_name": "GIVEN",
            "last_name": "SURNAME",
            "dob": "BIRTH_DATE",
            "ssn": "TAX_ID",
            "street": "ADDR1",
            "city": "TOWN",
            "state": "REGION",
            "zip": "POSTCODE",
            "phone": "TEL",
            "email": "EMAIL_ADDR",
        },
        "field_tiers": {
            "partner_member_id": "required",
            "first_name": "required",
            "last_name": "required",
            "dob": "required",
            "ssn": "verification",
            "ssn_last4": "verification",
            "street": "verification",
            "city": "verification",
            "state": "verification",
            "zip": "verification",
            "phone": "enrichment",
            "email": "enrichment",
        },
    }
    partner_c_yaml.write_text(yaml.safe_dump(yaml_content))

    m = load_mapping(partner_c_yaml)
    row = {
        "MEMBER_NUMBER": "C00001",
        "GIVEN": "Sarah",
        "SURNAME": "Johnson",
        "BIRTH_DATE": "12-Apr-1985",
        "TAX_ID": "987-65-4321",
        "ADDR1": "123 Main St",
        "TOWN": "Springfield",
        "REGION": "IL",
        "POSTCODE": "62701",
        "TEL": "555-555-1212",
        "EMAIL_ADDR": "sarah@example.com",
    }
    record = map_row(row, m)
    assert record.partner_id == "PARTNER_C"
    assert record.canonical["partner_member_id"] == "C00001"
    assert record.canonical["dob"] == "1985-04-12"
    assert record.canonical["ssn_last4"] == "4321"
    assert record.parse_errors == {}


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


def test_partner_mapping_is_frozen() -> None:
    """PartnerMapping is immutable so it can be passed safely between layers."""
    m = load_mapping(PARTNER_A_YAML)
    with pytest.raises(AttributeError, match="frozen|cannot"):
        m.partner_id = "MUTATED"  # type: ignore[misc]


def test_staging_record_carries_partner_id_and_raw_source() -> None:
    m = load_mapping(PARTNER_A_YAML)
    row = {"member_id": "A00001", "DOB": "04/12/1985"}
    record = map_row(row, m)
    assert isinstance(record, StagingRecord)
    assert record.partner_id == "PARTNER_A"
    assert record.raw_source["member_id"] == "A00001"


def test_partner_mapping_class_is_dataclass_frozen() -> None:
    assert PartnerMapping.__dataclass_fields__  # type: ignore[attr-defined]
