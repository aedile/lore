"""Deletion executor + suppression check — A7 from PROTOTYPE_PRD.md.

Implements BR-701..BR-704 around the right-to-deletion path:

- ``execute_deletion`` takes a member_id and:
  1. Computes one suppression_hash per partner_enrollment (BR-703 — the
     ledger holds no recoverable PII; only a SHA-256 of the salted,
     normalized (last_name, dob, partner_id, partner_member_id) tuple).
  2. Tombstones the canonical_member: state -> DELETED, tombstoned_at = now.
  3. Inserts a deletion_ledger row per suppression_hash.
- ``is_suppressed`` queries the ledger by hash; identity resolution calls
  this on every staging record before publication. A hit routes the record
  to SUPPRESSED_DELETED (i.e. don't publish; don't merge).
- ``operator_override`` increments override_count on a ledger row so a
  subsequent ingestion of the same identity proceeds. BR-704 audit event
  (``DELETION_OVERRIDE``) is emitted (returned to the caller for A8 chain
  insertion).

The audit-event integration is a return-shape contract: this module
returns the list of audit events the caller must persist. A8 will build
the JSONL hash chain that consumes them.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from prototype.canonical import CanonicalState, assert_transition_allowed
from prototype.tokenization import suppression_hash, suppression_hash_broad

# ---------------------------------------------------------------------------
# Audit event types emitted by this module (BR-704)
# ---------------------------------------------------------------------------

EVENT_DELETION_REQUESTED = "DELETION_REQUESTED"
EVENT_DELETION_EXECUTED = "DELETION_EXECUTED"
EVENT_SUPPRESSED_DELETED = "SUPPRESSED_DELETED"
EVENT_DELETION_OVERRIDE = "DELETION_OVERRIDE"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DeletionRequest:
    """Caller's input for a right-to-deletion execution."""

    member_id: str
    last_name: str
    dob: str  # ISO YYYY-MM-DD
    # Each (partner_id, partner_member_id) pair becomes one strict
    # suppression_hash so re-introduction via the same partner+ID is caught.
    enrollments: list[tuple[str, str]]
    # When provided, also writes a broad (dob, ssn_last4) suppression hash
    # so re-introduction across partners with name typos is also caught.
    ssn_last4: str | None = None
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))


@dataclass(frozen=True)
class AuditEvent:
    """Plain-data audit event consumed by A8's hash chain."""

    event_class: str
    actor_role: str
    target_token: str  # tokenized reference; never plaintext PII
    timestamp: str  # ISO timestamp
    outcome: str
    trigger: str
    context: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DeletionResult:
    """Outcome of ``execute_deletion``."""

    member_id: str
    suppression_hashes: list[str]
    audit_events: list[AuditEvent]


# ---------------------------------------------------------------------------
# Suppression check + execution
# ---------------------------------------------------------------------------


def is_suppressed(
    conn: Any,
    *,
    last_name: str,
    dob: str,
    partner_id: str,
    partner_member_id: str,
    ssn_last4: str | None = None,
) -> bool:
    """Return True if any suppression-hash variant for this identity is in
    the ledger with override_count == 0.

    Variants tried (in order):
    1. Strict per-enrollment (last_name, dob, partner_id, partner_member_id).
    2. Broad (dob, ssn_last4) — catches cross-partner re-introduction with
       name typos when ssn_last4 is known.
    """
    candidates: list[str] = [
        suppression_hash(
            last_name=last_name,
            dob=dob,
            partner_id=partner_id,
            partner_member_id=partner_member_id,
        ),
    ]
    if ssn_last4:
        candidates.append(suppression_hash_broad(dob=dob, ssn_last4=ssn_last4))

    cur = conn.cursor()
    cur.execute(
        "SELECT override_count FROM deletion_ledger WHERE suppression_hash = ANY(%s)",
        (candidates,),
    )
    rows = cur.fetchall()
    return any(override_count == 0 for (override_count,) in rows)


def execute_deletion(
    conn: Any,
    request: DeletionRequest,
    *,
    actor_role: str = "deletion_operator",
    trigger: str = "right_to_deletion_request",
) -> DeletionResult:
    """Execute the BR-701..BR-704 deletion sequence.

    Steps:
    1. Look up canonical_member to confirm existence + capture prior state.
    2. Insert deletion_ledger rows (one per enrollment).
    3. Update canonical_member: state -> DELETED, tombstoned_at = now,
       null all token columns (PII vault tombstone happens elsewhere).
    4. Return the suppression hashes + audit events the caller must persist.

    Raises:
        ForbiddenTransitionError: if the prior state cannot transition to
            DELETED per BR-202 (in practice it always can — DELETED is
            reachable from every state — but the assertion is here for
            symmetry with the rest of the state machine).
        ValueError: if the member_id does not exist.
    """
    cur = conn.cursor()

    cur.execute(
        "SELECT state FROM canonical_member WHERE member_id = %s",
        (request.member_id,),
    )
    row = cur.fetchone()
    if row is None:
        raise ValueError(f"canonical_member not found: {request.member_id}")
    (prior_state_str,) = row
    prior_state = CanonicalState(prior_state_str)

    # Validate the transition (defensive — DELETED is reachable from any state).
    assert_transition_allowed(prior_state, CanonicalState.DELETED)

    now_iso = datetime.now(UTC).isoformat()

    # 1. Insert ledger rows: one strict per enrollment, plus one broad
    #    (dob, ssn_last4) when ssn_last4 is provided.
    request_uuid = (
        uuid.UUID(request.request_id) if _looks_like_uuid(request.request_id) else uuid.uuid4()
    )
    suppression_hashes: list[str] = []
    for partner_id, partner_member_id in request.enrollments:
        h = suppression_hash(
            last_name=request.last_name,
            dob=request.dob,
            partner_id=partner_id,
            partner_member_id=partner_member_id,
        )
        cur.execute(
            """
            INSERT INTO deletion_ledger (suppression_hash, deleted_at, deletion_request_id)
            VALUES (%s, NOW(), %s)
            ON CONFLICT (suppression_hash) DO NOTHING
            """,
            (h, str(request_uuid)),
        )
        suppression_hashes.append(h)

    if request.ssn_last4:
        broad = suppression_hash_broad(dob=request.dob, ssn_last4=request.ssn_last4)
        cur.execute(
            """
            INSERT INTO deletion_ledger (suppression_hash, deleted_at, deletion_request_id)
            VALUES (%s, NOW(), %s)
            ON CONFLICT (suppression_hash) DO NOTHING
            """,
            (broad, str(request_uuid)),
        )
        suppression_hashes.append(broad)

    # 2. Tombstone the canonical_member.
    cur.execute(
        """
        UPDATE canonical_member
           SET state = 'DELETED',
               tombstoned_at = NOW(),
               last_updated_at = NOW(),
               name_token = '',
               dob_token = '',
               address_token = NULL,
               phone_token = NULL,
               email_token = NULL,
               ssn_token = NULL
         WHERE member_id = %s
        """,
        (request.member_id,),
    )

    # 3. Build audit events.
    events = [
        AuditEvent(
            event_class=EVENT_DELETION_REQUESTED,
            actor_role=actor_role,
            target_token=request.member_id,
            timestamp=now_iso,
            outcome="ACCEPTED",
            trigger=trigger,
            context={"prior_state": prior_state.value, "request_id": request.request_id},
        ),
        AuditEvent(
            event_class=EVENT_DELETION_EXECUTED,
            actor_role=actor_role,
            target_token=request.member_id,
            timestamp=now_iso,
            outcome="SUCCESS",
            trigger=trigger,
            context={
                "suppression_hash_count": len(suppression_hashes),
                "request_id": request.request_id,
            },
        ),
    ]

    return DeletionResult(
        member_id=request.member_id,
        suppression_hashes=suppression_hashes,
        audit_events=events,
    )


def operator_override(
    conn: Any,
    *,
    target_hash: str,
    actor_role: str = "deletion_operator",
    reason: str,
) -> AuditEvent:
    """Mark a deletion-ledger row overridden so the next re-ingestion
    proceeds. Returns the BR-704 ``DELETION_OVERRIDE`` audit event for
    the caller to chain into A8.
    """
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE deletion_ledger
           SET override_count = override_count + 1
         WHERE suppression_hash = %s
        """,
        (target_hash,),
    )
    if cur.rowcount == 0:
        raise ValueError(f"deletion_ledger entry not found for hash {target_hash}")

    return AuditEvent(
        event_class=EVENT_DELETION_OVERRIDE,
        actor_role=actor_role,
        target_token=target_hash,
        timestamp=datetime.now(UTC).isoformat(),
        outcome="SUCCESS",
        trigger="operator_override",
        context={"reason": reason},
    )


# ---------------------------------------------------------------------------
# Pre-publication routing (A4 wiring)
# ---------------------------------------------------------------------------


def route_for_publication(
    conn: Any,
    *,
    candidates: Iterable[tuple[str, str, str, str]],
    ssn_last4_by_candidate: dict[tuple[str, str, str, str], str] | None = None,
) -> dict[tuple[str, str, str, str], bool]:
    """Bulk variant of ``is_suppressed``.

    ``candidates`` are tuples of (last_name, dob, partner_id, partner_member_id).
    Optionally pass an ``ssn_last4_by_candidate`` map to also evaluate the
    broad (dob, ssn_last4) suppression hash per candidate.
    """
    ssn_lookup = ssn_last4_by_candidate or {}
    results: dict[tuple[str, str, str, str], bool] = {}
    for c in candidates:
        last_name, dob, partner_id, partner_member_id = c
        results[c] = is_suppressed(
            conn,
            last_name=last_name,
            dob=dob,
            partner_id=partner_id,
            partner_member_id=partner_member_id,
            ssn_last4=ssn_lookup.get(c),
        )
    return results


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _looks_like_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
    except (ValueError, AttributeError):
        return False
    return True


__all__ = [
    "EVENT_DELETION_EXECUTED",
    "EVENT_DELETION_OVERRIDE",
    "EVENT_DELETION_REQUESTED",
    "EVENT_SUPPRESSED_DELETED",
    "AuditEvent",
    "DeletionRequest",
    "DeletionResult",
    "execute_deletion",
    "is_suppressed",
    "operator_override",
    "route_for_publication",
]
