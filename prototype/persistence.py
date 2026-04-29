"""Postgres persistence — bridge between A4 ResolutionResult and A5 schema.

Two functions form the bridge:

- ``persist_canonical_members`` writes one canonical_member row per
  canonical group from the resolver, plus partner_enrollment rows for
  each constituent staging record, plus one match_decision row per
  Splink-scored pair. State machine: every new canonical lands in
  ``ELIGIBLE_ACTIVE`` (the demo treats day-1 ingest as fresh enrolment).
- ``load_canonical_candidates`` reads canonical_member + partner_enrollment
  back out as ``CanonicalCandidate`` rows for the day-2 Tier-1 lookup.

The day-2 SCD2 history-row write is a noted gap — the prototype demo
narrates it but doesn't emit ``member_history`` closure rows. The
production wiring is straightforward; A5 schema has the table.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from prototype.canonical import CanonicalState
from prototype.identity import (
    TIER_1,
    TIER_2,
    TIER_3,
    TIER_4,
    CanonicalCandidate,
    IdentityDecision,
    ResolutionResult,
)
from prototype.mapping_engine import StagingRecord
from prototype.tokenization import (
    tokenize_dob,
    tokenize_name,
    tokenize_ssn_last4,
)


@dataclass(frozen=True)
class PersistResult:
    canonical_inserted: int
    enrollments_inserted: int
    match_decisions_inserted: int
    review_queue_inserted: int = 0


# ---------------------------------------------------------------------------
# Persist
# ---------------------------------------------------------------------------


def persist_canonical_members(
    conn: Any,
    *,
    resolution: ResolutionResult,
    records: list[StagingRecord],
) -> PersistResult:
    """Insert canonical_member + partner_enrollment + match_decision rows
    derived from a ResolutionResult.

    Idempotency: existing canonical_member.member_id rows are skipped via
    ON CONFLICT. partner_enrollment uses ON CONFLICT (partner_id,
    partner_member_id, effective_from) DO NOTHING. match_decision is
    append-only.
    """
    cur = conn.cursor()
    by_uid = {f"{r.partner_id}:{r.canonical.get('partner_member_id', '')}": r for r in records}
    decisions_by_uid = {d.candidate_record_ref: d for d in resolution.decisions}

    canonical_inserted = 0
    enrollments_inserted = 0
    match_decisions_inserted = 0

    today = datetime.now(UTC).date().isoformat()

    for member_id, uids in resolution.canonical_groups.items():
        # Pick a "representative" staging record for the canonical anchor
        # (first uid that resolves to a real record).
        representative = None
        for uid in uids:
            rec = by_uid.get(uid)
            if rec is not None:
                representative = rec
                break
        if representative is None:
            continue

        canonical = representative.canonical
        cur.execute(
            """
            INSERT INTO canonical_member (
                member_id, state, state_effective_from,
                name_token, dob_token, ssn_token,
                first_seen_at, last_updated_at
            )
            VALUES (%s, %s, NOW(), %s, %s, %s, NOW(), NOW())
            ON CONFLICT (member_id) DO NOTHING
            """,
            (
                member_id,
                CanonicalState.ELIGIBLE_ACTIVE.value,
                tokenize_name(canonical.get("first_name", ""), canonical.get("last_name", "")),
                tokenize_dob(canonical.get("dob", "")),
                tokenize_ssn_last4(canonical.get("ssn_last4", ""))
                if canonical.get("ssn_last4")
                else None,
            ),
        )
        canonical_inserted += cur.rowcount or 0

        # Partner enrollment per uid in the group.
        for uid in uids:
            rec = by_uid.get(uid)
            if rec is None:
                continue
            partner_member_id = rec.canonical.get("partner_member_id", "")
            cur.execute(
                """
                INSERT INTO partner_enrollment (
                    enrollment_id, member_id, partner_id, partner_member_id,
                    effective_from, last_seen_in_feed_at, partner_attributes
                )
                VALUES (%s, %s, %s, %s, %s, NOW(), %s)
                ON CONFLICT (partner_id, partner_member_id, effective_from) DO NOTHING
                """,
                (
                    str(uuid.uuid4()),
                    member_id,
                    rec.partner_id,
                    partner_member_id,
                    today,
                    json.dumps({}),
                ),
            )
            enrollments_inserted += cur.rowcount or 0

    # Match decision rows — one per uid for traceability.
    review_queue_inserted = 0
    from prototype.identity import TIER_3

    for uid, decision in decisions_by_uid.items():
        score_breakdown = (
            json.dumps(_breakdown_to_jsonable(decision.score_breakdown))
            if decision.score_breakdown
            else None
        )
        decision_id = str(uuid.uuid4())
        cur.execute(
            """
            INSERT INTO match_decision (
                decision_id, candidate_record_ref, resolved_member_id,
                tier_outcome, score, algorithm_version, config_version,
                decided_at, score_breakdown
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), %s)
            """,
            (
                decision_id,
                uid,
                decision.resolved_member_id,
                decision.tier,
                decision.score,
                resolution.algorithm_version,
                resolution.config_version,
                score_breakdown,
            ),
        )
        match_decisions_inserted += 1

        # Tier 3 outcomes route to the review_queue with score breakdown
        # surfaced for the human reviewer (BR-101 + BR-105).
        if decision.tier == TIER_3 and decision.score is not None:
            candidate_member_ids = (
                [decision.resolved_member_id] if decision.resolved_member_id else []
            )
            cur.execute(
                """
                INSERT INTO review_queue (
                    queue_id, decision_id, candidate_record_ref,
                    candidate_member_ids, score, queued_at
                )
                VALUES (%s, %s, %s, %s, %s, NOW())
                """,
                (
                    str(uuid.uuid4()),
                    decision_id,
                    uid,
                    candidate_member_ids,
                    decision.score,
                ),
            )
            review_queue_inserted += 1

    conn.commit()
    return PersistResult(
        canonical_inserted=canonical_inserted,
        enrollments_inserted=enrollments_inserted,
        match_decisions_inserted=match_decisions_inserted,
        review_queue_inserted=review_queue_inserted,
    )


def _breakdown_to_jsonable(breakdown: dict[str, Any] | None) -> dict[str, Any]:
    if breakdown is None:
        return {}
    out: dict[str, Any] = {}
    for k, v in breakdown.items():
        try:
            out[k] = float(v)
        except (TypeError, ValueError):
            out[k] = str(v)
    return out


# ---------------------------------------------------------------------------
# Load (Tier-1 lookup support)
# ---------------------------------------------------------------------------


def load_canonical_candidates(conn: Any) -> list[CanonicalCandidate]:
    """Read canonical_member + partner_enrollment rows out as ``CanonicalCandidate``s.

    Used by day-2 ingest to populate Tier 1 deterministic lookup. Returns
    one candidate per canonical_member with all current enrollments
    aggregated.
    """
    cur = conn.cursor()
    cur.execute(
        """
        SELECT cm.member_id, cm.name_token, cm.dob_token, pe.partner_id, pe.partner_member_id
          FROM canonical_member cm
          JOIN partner_enrollment pe ON pe.member_id = cm.member_id
         WHERE cm.state != 'DELETED' AND pe.effective_to IS NULL
         ORDER BY cm.member_id
        """
    )
    by_member: dict[str, dict[str, Any]] = {}
    for member_id, name_token, dob_token, partner_id, partner_member_id in cur.fetchall():
        entry = by_member.setdefault(
            str(member_id),
            {"name_token": name_token, "dob_token": dob_token, "enrollments": []},
        )
        entry["enrollments"].append((partner_id, partner_member_id))

    candidates: list[CanonicalCandidate] = []
    for member_id, data in by_member.items():
        candidates.append(
            CanonicalCandidate(
                member_id=member_id,
                name_token=data["name_token"],
                dob_token=data["dob_token"],
                enrollments=data["enrollments"],
            )
        )
    return candidates


__all__ = [
    "PersistResult",
    "load_canonical_candidates",
    "persist_canonical_members",
]


# Quiet ruff F401 — these imports are part of the public surface used elsewhere.
_TIERS_KEEP = (TIER_1, TIER_2, TIER_3, TIER_4)
_DECISION_KEEP = IdentityDecision
_ITER_KEEP = Iterable
