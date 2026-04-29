"""End-to-end demo runner — orchestrates A1 → A8.

Two callable entry points:

- ``run_full_demo(conn, *, fixtures_dir, output_dir)`` — orchestrates the
  panel-walkthrough flow: load fixtures, run day-1 pipeline, delete a
  member, run day-2 pipeline (with suppression), validate the audit chain,
  scan for redaction leaks. Returns a structured ``DemoResult`` so
  acceptance criteria can be asserted programmatically.
- ``run_day1`` and ``run_day2`` — the same flow split per-day for callers
  that want to drive the lifecycle manually (e.g., the panel demo
  ``make`` target).

PRD acceptance criteria targeted:
1. Single command runs day-1 pipeline end-to-end on synthetic data.
2. Single command runs day-2 pipeline producing SCD2 history, suppression,
   and re-resolution events.
5. Hash chain validates clean across the full run.
6. Redaction scanner reports zero matches.
7. Deletion + reintroduce produces SUPPRESSED_DELETED routing without
   operator intervention.
"""

from __future__ import annotations

import json
import uuid
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from prototype.audit import (
    AuditChain,
    AuditEvent,
    ChainValidationResult,
    PIIMatch,
    RedactionScanner,
)
from prototype.canonical import SCHEMA_PATH
from prototype.csv_adapter import read_csv, read_csv_columns
from prototype.deletion import (
    DeletionRequest,
    execute_deletion,
    is_suppressed,
)
from prototype.dq import (
    DQResult,
)
from prototype.dq import (
    run as run_dq,
)
from prototype.identity import (
    ResolutionResult,
    TierThresholds,
    resolve,
)
from prototype.mapping_engine import (
    PartnerMapping,
    StagingRecord,
    load_mapping,
    map_feed,
)
from prototype.persistence import (
    persist_canonical_members,
)
from prototype.vault import Vault

# ---------------------------------------------------------------------------
# Result models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FeedRunSummary:
    partner_id: str
    raw_records: int
    after_dedup: int
    quarantined: int
    feed_quarantined: bool
    schema_drift: str


@dataclass(frozen=True)
class Day1Result:
    feeds: list[FeedRunSummary]
    canonical_inserted: int
    enrollments_inserted: int
    match_decisions_inserted: int
    tier_histogram: dict[str, int]


@dataclass(frozen=True)
class Day2Result:
    feeds: list[FeedRunSummary]
    suppressed_count: int
    canonical_inserted: int
    enrollments_inserted: int
    match_decisions_inserted: int
    member_history_inserted: int
    tier_histogram: dict[str, int]


@dataclass(frozen=True)
class DemoResult:
    day1: Day1Result
    day2: Day2Result
    deletion_target_member_id: str
    audit_chain_validation: ChainValidationResult
    audit_event_count: int
    redaction_matches: list[PIIMatch] = field(default_factory=list)
    audit_chain_path: Path = field(default_factory=Path)


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------


def setup_db(conn: Any) -> None:
    """Apply A5 schema. Idempotent: drops the prototype tables first so
    the demo can re-run against the same Postgres instance."""
    cur = conn.cursor()
    cur.execute(
        """
        DROP TABLE IF EXISTS
            review_queue, match_decision, member_history,
            partner_enrollment, deletion_ledger, canonical_member
        CASCADE
        """
    )
    cur.execute(Path(SCHEMA_PATH).read_text())
    conn.commit()


# ---------------------------------------------------------------------------
# Day 1
# ---------------------------------------------------------------------------


def run_day1(
    conn: Any,
    *,
    fixtures_dir: Path | str,
    audit_chain: AuditChain,
    vault: Vault | None = None,
    thresholds: TierThresholds | None = None,
) -> Day1Result:
    """Day-1 ingest: map → DQ → BR-601 dedup → Splink resolve → persist."""
    fixtures = Path(fixtures_dir)
    feeds, all_records = _read_partner_feeds(fixtures, day=1)

    feed_summaries: list[FeedRunSummary] = []
    publishable: list[StagingRecord] = []

    for feed_id, mapping, raw_rows, columns in feeds:
        records = list(map_feed(raw_rows, mapping))
        deduped = _br601_dedup(records)
        dq_result = run_dq(
            deduped,
            mapping=mapping,
            feed_columns=columns,
            feed_id=feed_id,
        )
        feed_summaries.append(
            FeedRunSummary(
                partner_id=mapping.partner_id,
                raw_records=len(records),
                after_dedup=len(deduped),
                quarantined=len(dq_result.quarantined),
                feed_quarantined=dq_result.feed_quarantined,
                schema_drift=dq_result.schema_drift,
            )
        )
        if not dq_result.feed_quarantined:
            publishable.extend(dq_result.passed)
        _emit_feed_audit(audit_chain, feed_id, dq_result, day=1)

    resolution = resolve(publishable, thresholds=thresholds)
    persist_result = persist_canonical_members(conn, resolution=resolution, records=publishable)

    audit_chain.append(
        AuditEvent(
            event_class="DAY1_RESOLUTION_COMPLETE",
            actor_role="prototype-pipeline",
            target_token="day1-batch",
            outcome="SUCCESS",
            trigger="ingest",
            context={
                "canonical_inserted": persist_result.canonical_inserted,
                "tier_histogram": _histogram(resolution),
            },
        )
    )

    # Vault any non-joinable PII for the demo (street, phone, email).
    if vault is not None:
        for r in publishable:
            for field_name in ("street", "phone", "email"):
                value = r.canonical.get(field_name, "")
                if value:
                    vault.store(field_class=field_name, plaintext=value)

    return Day1Result(
        feeds=feed_summaries,
        canonical_inserted=persist_result.canonical_inserted,
        enrollments_inserted=persist_result.enrollments_inserted,
        match_decisions_inserted=persist_result.match_decisions_inserted,
        tier_histogram=_histogram(resolution),
    )


# ---------------------------------------------------------------------------
# Deletion
# ---------------------------------------------------------------------------


def run_deletion(
    conn: Any,
    *,
    fixtures_dir: Path | str,
    audit_chain: AuditChain,
) -> str:
    """Execute the BR-701..BR-704 deletion path on the deletion fixture
    member from PARTNER_A day 1. Returns the deleted member_id."""
    fixtures = Path(fixtures_dir)
    inventory = json.loads((fixtures / "scenario_inventory.json").read_text())
    deletion_records = [
        e
        for e in inventory["records"]
        if e["scenario"] == "deletion_fixture" and "partner_a_day1" in e["feed"]
    ]
    if not deletion_records:
        raise RuntimeError("No deletion fixture found in scenario inventory")
    target = deletion_records[0]
    target_pmid = target["partner_member_id"]

    # Look up the canonical_member created during day-1 ingest from
    # partner_enrollment.
    cur = conn.cursor()
    cur.execute(
        """
        SELECT cm.member_id
          FROM canonical_member cm
          JOIN partner_enrollment pe ON pe.member_id = cm.member_id
         WHERE pe.partner_id = %s AND pe.partner_member_id = %s
        """,
        ("PARTNER_A", target_pmid),
    )
    row = cur.fetchone()
    if row is None:
        raise RuntimeError(f"Deletion fixture PARTNER_A:{target_pmid} not in canonical_member")
    member_id = str(row[0])

    # Read fixtures to get the actual last_name + dob + ssn_last4 for the
    # deletion target — the demo uses real synthetic values.
    rows_a = list(read_csv(fixtures / "partner_a_day1.csv"))
    target_row = next(r for r in rows_a if r["member_id"] == target_pmid)

    # Capture prior_state BEFORE execute_deletion mutates the row, so we
    # can stamp it on the SCD2 closure.
    cur.execute(
        "SELECT state, name_token, dob_token FROM canonical_member WHERE member_id = %s",
        (member_id,),
    )
    prior_state, prior_name_token, prior_dob_token = cur.fetchone()

    # Execute deletion — emits both strict (per-enrollment) and broad
    # (dob, ssn_last4) suppression hashes so the day-2 reintroduction
    # via PARTNER_B with a name typo is still suppressed.
    request = DeletionRequest(
        member_id=member_id,
        last_name=target_row["LastName"],
        dob=_parse_us_date(target_row["DOB"]),
        enrollments=[("PARTNER_A", target_pmid)],
        ssn_last4=target_row["SSN"][-4:] if target_row["SSN"] else None,
    )
    result = execute_deletion(conn, request)
    conn.commit()

    # SCD2 closure on the deletion: write a member_history row capturing
    # the pre-deletion state with state_effective_to = now.
    cur.execute(
        """
        INSERT INTO member_history (
            member_id, state, state_effective_from, state_effective_to,
            name_token, dob_token, change_trigger, change_event_id
        ) VALUES (%s, %s, NOW() - INTERVAL '1 second', NOW(), %s, %s, %s, %s)
        """,
        (
            member_id,
            prior_state,
            prior_name_token,
            prior_dob_token,
            "DELETION",
            str(uuid.uuid4()),
        ),
    )
    conn.commit()

    for event in result.audit_events:
        audit_chain.append(
            AuditEvent(
                event_class=event.event_class,
                actor_role=event.actor_role,
                target_token=event.target_token,
                outcome=event.outcome,
                trigger=event.trigger,
                context=event.context,
            )
        )
    return member_id


# ---------------------------------------------------------------------------
# Day 2
# ---------------------------------------------------------------------------


def run_day2(
    conn: Any,
    *,
    fixtures_dir: Path | str,
    audit_chain: AuditChain,
    thresholds: TierThresholds | None = None,
) -> Day2Result:
    """Day-2 ingest: map → DQ → dedup → suppression check → resolve → persist
    → SCD2 history rows for any new canonical members."""
    fixtures = Path(fixtures_dir)
    feeds, all_records = _read_partner_feeds(fixtures, day=2)

    feed_summaries: list[FeedRunSummary] = []
    publishable: list[StagingRecord] = []
    suppressed_count = 0

    for feed_id, mapping, raw_rows, columns in feeds:
        records = list(map_feed(raw_rows, mapping))
        deduped = _br601_dedup(records)

        # Schema drift check: compare against day-1 columns.
        day1_columns = read_csv_columns(
            fixtures / f"partner_{mapping.partner_id[-1].lower()}_day1.csv"
        )
        dq_result = run_dq(
            deduped,
            mapping=mapping,
            feed_columns=columns,
            feed_id=feed_id,
            prior_columns=day1_columns,
        )
        feed_summaries.append(
            FeedRunSummary(
                partner_id=mapping.partner_id,
                raw_records=len(records),
                after_dedup=len(deduped),
                quarantined=len(dq_result.quarantined),
                feed_quarantined=dq_result.feed_quarantined,
                schema_drift=dq_result.schema_drift,
            )
        )
        if dq_result.feed_quarantined:
            _emit_feed_audit(audit_chain, feed_id, dq_result, day=2)
            continue

        # Pre-publication BR-703 suppression check.
        for record in dq_result.passed:
            partner_member_id = record.canonical.get("partner_member_id", "")
            last_name = record.canonical.get("last_name", "")
            dob = record.canonical.get("dob", "")
            ssn_last4 = record.canonical.get("ssn_last4", "")
            if is_suppressed(
                conn,
                last_name=last_name,
                dob=dob,
                partner_id=record.partner_id,
                partner_member_id=partner_member_id,
                ssn_last4=ssn_last4 or None,
            ):
                suppressed_count += 1
                audit_chain.append(
                    AuditEvent(
                        event_class="SUPPRESSED_DELETED",
                        actor_role="prototype-pipeline",
                        target_token=f"{record.partner_id}:{partner_member_id}",
                        outcome="SUPPRESSED",
                        trigger="day2_pre_publication",
                        context={"reason": "deletion_ledger_hit"},
                    )
                )
                continue
            publishable.append(record)

        _emit_feed_audit(audit_chain, feed_id, dq_result, day=2)

    resolution = resolve(publishable, thresholds=thresholds)
    persist_result = persist_canonical_members(conn, resolution=resolution, records=publishable)

    # SCD2 history rows for the new canonical members produced on day 2.
    cur = conn.cursor()
    history_count = 0
    for member_id in resolution.canonical_groups:
        cur.execute(
            """
            INSERT INTO member_history (
                member_id, state, state_effective_from,
                name_token, dob_token, change_trigger, change_event_id
            )
            SELECT member_id, state, NOW(), name_token, dob_token, 'DAY2_INGEST', %s
              FROM canonical_member
             WHERE member_id = %s
            """,
            (str(uuid.uuid4()), member_id),
        )
        history_count += cur.rowcount or 0
    conn.commit()

    audit_chain.append(
        AuditEvent(
            event_class="DAY2_RESOLUTION_COMPLETE",
            actor_role="prototype-pipeline",
            target_token="day2-batch",
            outcome="SUCCESS",
            trigger="ingest",
            context={
                "suppressed_count": suppressed_count,
                "tier_histogram": _histogram(resolution),
                "member_history_inserted": history_count,
            },
        )
    )

    return Day2Result(
        feeds=feed_summaries,
        suppressed_count=suppressed_count,
        canonical_inserted=persist_result.canonical_inserted,
        enrollments_inserted=persist_result.enrollments_inserted,
        match_decisions_inserted=persist_result.match_decisions_inserted,
        member_history_inserted=history_count,
        tier_histogram=_histogram(resolution),
    )


# ---------------------------------------------------------------------------
# Full demo
# ---------------------------------------------------------------------------


def run_full_demo(
    conn: Any,
    *,
    fixtures_dir: Path | str,
    output_dir: Path | str,
    thresholds: TierThresholds | None = None,
) -> DemoResult:
    """Full pipeline: setup → day1 → delete → day2 → validate → scan."""
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    audit_path = output / "audit_chain.jsonl"
    audit_path.unlink(missing_ok=True)
    chain = AuditChain(audit_path)
    vault = Vault(output / "vault.sqlite")

    setup_db(conn)

    day1 = run_day1(
        conn,
        fixtures_dir=fixtures_dir,
        audit_chain=chain,
        vault=vault,
        thresholds=thresholds,
    )
    deleted_member_id = run_deletion(conn, fixtures_dir=fixtures_dir, audit_chain=chain)
    day2 = run_day2(
        conn,
        fixtures_dir=fixtures_dir,
        audit_chain=chain,
        thresholds=thresholds,
    )

    chain_result = chain.validate()
    scanner = RedactionScanner()
    redaction_matches = scanner.scan_jsonl(audit_path)
    audit_event_count = sum(1 for _ in chain)

    return DemoResult(
        day1=day1,
        day2=day2,
        deletion_target_member_id=deleted_member_id,
        audit_chain_validation=chain_result,
        audit_event_count=audit_event_count,
        redaction_matches=redaction_matches,
        audit_chain_path=audit_path,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_partner_feeds(
    fixtures: Path,
    *,
    day: int,
) -> tuple[
    list[tuple[str, PartnerMapping, list[dict[str, str]], list[str]]],
    list[StagingRecord],
]:
    repo = fixtures.resolve().parents[1]
    mappings_dir = repo / "prototype" / "mappings"
    feeds: list[tuple[str, PartnerMapping, list[dict[str, str]], list[str]]] = []
    for partner_letter, yaml_name in (("a", "partner_a.yaml"), ("b", "partner_b.yaml")):
        path = fixtures / f"partner_{partner_letter}_day{day}.csv"
        if not path.exists():
            continue
        mapping = load_mapping(mappings_dir / yaml_name)
        feed_id = path.stem
        rows = list(read_csv(path))
        columns = read_csv_columns(path)
        feeds.append((feed_id, mapping, rows, columns))
    return feeds, []


def _br601_dedup(records: list[StagingRecord]) -> list[StagingRecord]:
    """Last-record-wins dedupe by (partner_id, partner_member_id)."""
    out: dict[tuple[str, str], StagingRecord] = {}
    for r in records:
        out[(r.partner_id, r.canonical.get("partner_member_id", ""))] = r
    return list(out.values())


def _histogram(resolution: ResolutionResult) -> dict[str, int]:
    counter: Counter[str] = Counter(d.tier for d in resolution.decisions)
    return dict(counter)


def _emit_feed_audit(
    audit_chain: AuditChain, feed_id: str, dq_result: DQResult, *, day: int
) -> None:
    audit_chain.append(
        AuditEvent(
            event_class="FEED_INGESTED",
            actor_role="prototype-pipeline",
            target_token=feed_id,
            outcome="QUARANTINED" if dq_result.feed_quarantined else "ACCEPTED",
            trigger=f"day{day}_ingest",
            context={
                "schema_drift": dq_result.schema_drift,
                "quarantined_records": len(dq_result.quarantined),
                "drift_columns_added": dq_result.columns_added,
            },
        )
    )


def _parse_us_date(value: str) -> str:
    """Convert MM/DD/YYYY (with possible single-digit month/day) to ISO."""
    parts = value.strip().split("/")
    if len(parts) != 3:
        return value
    m, d, y = parts
    if len(y) == 2:
        y = ("19" if int(y) > 30 else "20") + y
    return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"


__all__ = [
    "Day1Result",
    "Day2Result",
    "DemoResult",
    "FeedRunSummary",
    "run_day1",
    "run_day2",
    "run_deletion",
    "run_full_demo",
    "setup_db",
]
