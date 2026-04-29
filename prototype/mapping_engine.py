"""Per-partner mapping engine — A2 from PROTOTYPE_PRD.md.

Loads a partner YAML mapping (the declarative half of AD-016) and projects
adapter-output rows onto canonical staging records. The contract is:

- The YAML is the only place a partner's column names, date format, SSN
  representation, and field tiers are declared. Adding partner #3 is a YAML
  drop, not a code change.
- This module performs the structural mapping plus light normalization
  (date parsing to ISO, SSN-last-4 derivation, whitespace strip).
- *Validation* — required-field presence, feed-level threshold checks,
  schema drift — is the DQ engine's job (A3). The mapping engine's role is
  to produce a clean intermediate representation plus a per-record
  ``parse_errors`` map that A3 reads.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PartnerMapping:
    """Loaded YAML mapping for a single partner."""

    partner_id: str
    format: str  # "csv" for the prototype; format adapters per AD-016 are per-format-family
    date_format: str  # primary strptime format (e.g. "%m/%d/%Y")
    date_format_alternates: list[str]  # fallback formats tried in order
    ssn_field: str  # "full" | "last4"
    mapping: dict[str, str]  # canonical_field -> source column name
    field_tiers: dict[str, str]  # canonical_field -> "required" | "verification" | "enrichment"


@dataclass(frozen=True)
class StagingRecord:
    """One source row projected onto canonical fields, plus diagnostic metadata."""

    partner_id: str
    raw_source: dict[str, str]
    canonical: dict[str, Any]
    parse_errors: dict[str, str] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# YAML loading
# ---------------------------------------------------------------------------


def load_mapping(yaml_path: Path | str) -> PartnerMapping:
    """Read a partner-mapping YAML file into a typed ``PartnerMapping``."""
    p = Path(yaml_path)
    raw = yaml.safe_load(p.read_text(encoding="utf-8"))

    return PartnerMapping(
        partner_id=raw["partner_id"],
        format=raw["format"],
        date_format=raw["date_format"],
        date_format_alternates=list(raw.get("date_format_alternates", [])),
        ssn_field=raw["ssn_field"],
        mapping=dict(raw["mapping"]),
        field_tiers=dict(raw["field_tiers"]),
    )


# ---------------------------------------------------------------------------
# Mapping
# ---------------------------------------------------------------------------


def map_row(row: dict[str, str], mapping: PartnerMapping) -> StagingRecord:
    """Project one source row onto a canonical staging record."""
    canonical: dict[str, Any] = {}
    parse_errors: dict[str, str] = {}

    for canonical_field, source_col in mapping.mapping.items():
        raw_value = (row.get(source_col) or "").strip()

        if canonical_field == "dob":
            parsed_dob, err = _parse_date(raw_value, mapping)
            canonical["dob"] = parsed_dob.isoformat() if parsed_dob else ""
            if err:
                parse_errors["dob"] = err
            continue

        if canonical_field == "ssn":
            # Partner sends full SSN; we keep both ssn and ssn_last4.
            canonical["ssn"] = raw_value
            canonical["ssn_last4"] = raw_value[-4:] if raw_value else ""
            continue

        if canonical_field == "ssn_last4":
            # Partner sends only ssn_last4.
            canonical["ssn_last4"] = raw_value
            continue

        if canonical_field == "email":
            canonical["email"] = raw_value.lower()
            continue

        canonical[canonical_field] = raw_value

    return StagingRecord(
        partner_id=mapping.partner_id,
        raw_source=row,
        canonical=canonical,
        parse_errors=parse_errors,
    )


def map_feed(rows: Iterable[dict[str, str]], mapping: PartnerMapping) -> Iterator[StagingRecord]:
    """Project a whole feed onto staging records."""
    for row in rows:
        yield map_row(row, mapping)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_date(value: str, mapping: PartnerMapping) -> tuple[date | None, str | None]:
    """Try the primary date format, then alternates. Return (date|None, error|None)."""
    if not value:
        return None, "empty"
    formats = [mapping.date_format, *mapping.date_format_alternates]
    for fmt in formats:
        try:
            return datetime.strptime(value, fmt).date(), None
        except ValueError:
            continue
    return None, f"unparseable: tried {formats}"
