"""Data Quality engine — A3 from PROTOTYPE_PRD.md.

Implements:
- BR-301 Field Criticality Tiers (Required / Verification / Enrichment).
- BR-302 Record-Level Quarantine — required-tier failure quarantines that
  row only; the remainder of the feed proceeds.
- BR-303 Feed-Level Quarantine Threshold — when the per-feed rejection
  rate exceeds ``feed_quarantine_threshold`` (default 5%) the feed is
  quarantined wholesale.
- BR-304 Schema Drift — additive columns auto-accepted with a notification;
  subtractive columns quarantine the feed.
- BR-305 Profiling Baseline + drift detection vs the partner baseline
  (null-rate change above ``profile_drift_threshold``).

The engine is pure: inputs in, ``DQResult`` out. Optional persistence of
quarantined records and profile baselines is offered via helper functions.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from prototype.mapping_engine import PartnerMapping, StagingRecord

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FieldProfile:
    """Per-canonical-field statistics for BR-305."""

    count: int
    null_count: int
    null_rate: float
    distinct_count: int


@dataclass(frozen=True)
class FeedProfile:
    """Feed-level profile baseline per BR-305."""

    partner_id: str
    row_count: int
    columns: list[str]  # source column names from the adapter
    fields: dict[str, FieldProfile]  # canonical_field -> FieldProfile


# Schema-drift outcomes per BR-304.
DRIFT_NONE = "NONE"
DRIFT_ADDITIVE = "ADDITIVE"
DRIFT_SUBTRACTIVE = "SUBTRACTIVE_QUARANTINE"


@dataclass(frozen=True)
class DQResult:
    """Outcome of a single feed run through the DQ engine."""

    partner_id: str
    feed_id: str
    passed: list[StagingRecord]
    quarantined: list[tuple[StagingRecord, str]]
    feed_quarantined: bool
    feed_quarantine_reason: str | None
    schema_drift: str
    columns_added: list[str]
    columns_removed: list[str]
    profile: FeedProfile
    profile_drift_fields: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


def run(
    records: list[StagingRecord],
    *,
    mapping: PartnerMapping,
    feed_columns: list[str],
    feed_id: str = "",
    prior_columns: list[str] | None = None,
    prior_profile: FeedProfile | None = None,
    feed_quarantine_threshold: float = 0.05,
    profile_drift_threshold: float = 0.20,
) -> DQResult:
    """Validate a feed against BR-301..305 and return a structured result."""
    # 1. Schema drift (BR-304) — runs FIRST; subtractive drift quarantines
    #    the whole feed irrespective of per-record outcomes.
    drift, added, removed = _detect_schema_drift(feed_columns, prior_columns)

    if drift == DRIFT_SUBTRACTIVE:
        return DQResult(
            partner_id=mapping.partner_id,
            feed_id=feed_id,
            passed=[],
            quarantined=[],
            feed_quarantined=True,
            feed_quarantine_reason=f"SCHEMA_DRIFT_SUBTRACTIVE: removed columns {removed}",
            schema_drift=drift,
            columns_added=added,
            columns_removed=removed,
            profile=_compute_profile(records, mapping, feed_columns),
        )

    # 2. Per-record required-tier validation (BR-301, BR-302).
    passed: list[StagingRecord] = []
    quarantined: list[tuple[StagingRecord, str]] = []
    for record in records:
        reason = _record_quarantine_reason(record, mapping)
        if reason:
            quarantined.append((record, reason))
        else:
            passed.append(record)

    # 3. Feed-level threshold (BR-303).
    total = len(records)
    rejection_rate = (len(quarantined) / total) if total else 0.0
    feed_quarantined = rejection_rate > feed_quarantine_threshold
    feed_reason = (
        f"REJECTION_RATE_EXCEEDED: {rejection_rate:.4f} > {feed_quarantine_threshold:.4f}"
        if feed_quarantined
        else None
    )

    # 4. Profile baseline + drift (BR-305).
    profile = _compute_profile(records, mapping, feed_columns)
    drift_fields = _detect_profile_drift(profile, prior_profile, profile_drift_threshold)

    return DQResult(
        partner_id=mapping.partner_id,
        feed_id=feed_id,
        passed=passed if not feed_quarantined else [],
        quarantined=quarantined,
        feed_quarantined=feed_quarantined,
        feed_quarantine_reason=feed_reason,
        schema_drift=drift,
        columns_added=added,
        columns_removed=removed,
        profile=profile,
        profile_drift_fields=drift_fields,
    )


# ---------------------------------------------------------------------------
# Schema drift (BR-304)
# ---------------------------------------------------------------------------


def _detect_schema_drift(
    current: list[str],
    prior: list[str] | None,
) -> tuple[str, list[str], list[str]]:
    if prior is None:
        return DRIFT_NONE, [], []
    current_set = set(current)
    prior_set = set(prior)
    added = sorted(current_set - prior_set)
    removed = sorted(prior_set - current_set)
    if removed:
        return DRIFT_SUBTRACTIVE, added, removed
    if added:
        return DRIFT_ADDITIVE, added, removed
    return DRIFT_NONE, added, removed


# ---------------------------------------------------------------------------
# Per-record quarantine (BR-301, BR-302)
# ---------------------------------------------------------------------------


def _record_quarantine_reason(record: StagingRecord, mapping: PartnerMapping) -> str | None:
    """Return a quarantine reason string, or None if the record passes."""
    for canonical_field, tier in mapping.field_tiers.items():
        if tier != "required":
            continue
        if canonical_field in record.parse_errors:
            return (
                f"REQUIRED_FIELD_INVALID:{canonical_field}:{record.parse_errors[canonical_field]}"
            )
        value = record.canonical.get(canonical_field, "")
        if not value:
            return f"REQUIRED_FIELD_MISSING:{canonical_field}"
    return None


# ---------------------------------------------------------------------------
# Profiling (BR-305)
# ---------------------------------------------------------------------------


def _compute_profile(
    records: Iterable[StagingRecord],
    mapping: PartnerMapping,
    feed_columns: list[str],
) -> FeedProfile:
    records_list = list(records)
    canonical_fields = sorted(
        set(mapping.field_tiers.keys()) | {f for r in records_list for f in r.canonical}
    )
    fields: dict[str, FieldProfile] = {}
    for cf in canonical_fields:
        values = [r.canonical.get(cf, "") for r in records_list]
        non_null = [v for v in values if v != "" and v is not None]
        null_count = len(values) - len(non_null)
        distinct = len(set(non_null))
        count = len(values)
        null_rate = (null_count / count) if count else 0.0
        fields[cf] = FieldProfile(
            count=count,
            null_count=null_count,
            null_rate=null_rate,
            distinct_count=distinct,
        )
    return FeedProfile(
        partner_id=mapping.partner_id,
        row_count=len(records_list),
        columns=list(feed_columns),
        fields=fields,
    )


def _detect_profile_drift(
    current: FeedProfile,
    prior: FeedProfile | None,
    threshold: float,
) -> list[str]:
    if prior is None:
        return []
    drifted: list[str] = []
    for cf, profile in current.fields.items():
        prior_profile = prior.fields.get(cf)
        if prior_profile is None:
            continue
        if abs(profile.null_rate - prior_profile.null_rate) > threshold:
            drifted.append(cf)
    return drifted


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------


def write_quarantine(result: DQResult, quarantine_dir: Path | str) -> Path:
    """Write quarantined records as JSON Lines into quarantine_dir/{partner}/{feed}.jsonl.

    Returns the file path written.
    """
    base = Path(quarantine_dir) / result.partner_id
    base.mkdir(parents=True, exist_ok=True)
    out = base / f"{result.feed_id or 'feed'}.jsonl"
    with out.open("w", encoding="utf-8") as f:
        for record, reason in result.quarantined:
            payload = {
                "partner_id": record.partner_id,
                "raw_source": record.raw_source,
                "canonical": record.canonical,
                "parse_errors": record.parse_errors,
                "quarantine_reason": reason,
            }
            f.write(json.dumps(payload) + "\n")
    return out


def write_profile(profile: FeedProfile, path: Path | str) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "partner_id": profile.partner_id,
        "row_count": profile.row_count,
        "columns": profile.columns,
        "fields": {name: asdict(fp) for name, fp in profile.fields.items()},
    }
    p.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return p


def read_profile(path: Path | str) -> FeedProfile:
    p = Path(path)
    raw = json.loads(p.read_text(encoding="utf-8"))
    fields = {name: FieldProfile(**fp) for name, fp in raw["fields"].items()}
    return FeedProfile(
        partner_id=raw["partner_id"],
        row_count=raw["row_count"],
        columns=list(raw["columns"]),
        fields=fields,
    )


__all__ = [
    "DRIFT_ADDITIVE",
    "DRIFT_NONE",
    "DRIFT_SUBTRACTIVE",
    "DQResult",
    "FeedProfile",
    "FieldProfile",
    "read_profile",
    "run",
    "write_profile",
    "write_quarantine",
]


# Quiet ruff F401 for Counter (kept for future per-field cardinality work).
_ = Counter
