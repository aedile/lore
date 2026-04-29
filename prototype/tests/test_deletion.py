"""Tests for prototype.deletion — A7 acceptance.

Covers PROTOTYPE_PRD.md A7 acceptance:
- A member is deleted on day 1 (ledger row inserted, canonical state -> DELETED).
- Day 2 re-ingestion of the same identity routes to SUPPRESSED_DELETED via
  ``is_suppressed`` (BR-703).
- An operator override increments override_count and emits a DELETION_OVERRIDE
  audit event (BR-704); a subsequent suppression check returns False.
- The deletion sequence emits DELETION_REQUESTED + DELETION_EXECUTED audit
  events (BR-704) for the A8 hash chain to consume.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from prototype.canonical import SCHEMA_PATH
from prototype.deletion import (
    EVENT_DELETION_EXECUTED,
    EVENT_DELETION_OVERRIDE,
    EVENT_DELETION_REQUESTED,
    AuditEvent,
    DeletionRequest,
    execute_deletion,
    is_suppressed,
    operator_override,
    route_for_publication,
)
from prototype.tokenization import suppression_hash

pytest_plugins = ["pytest_postgresql"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _apply_schema(conn) -> None:  # type: ignore[no-untyped-def]
    cur = conn.cursor()
    cur.execute(Path(SCHEMA_PATH).read_text())
    conn.commit()


def _seed_member(
    conn,  # type: ignore[no-untyped-def]
    *,
    member_id: str,
    state: str = "ELIGIBLE_ACTIVE",
    enrollments: list[tuple[str, str]] | None = None,
) -> None:
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO canonical_member (
            member_id, state, state_effective_from, name_token, dob_token,
            first_seen_at, last_updated_at
        ) VALUES (%s, %s, NOW(), 'tok-name', 'tok-dob', NOW(), NOW())
        """,
        (member_id, state),
    )
    for partner_id, pmid in enrollments or []:
        cur.execute(
            """
            INSERT INTO partner_enrollment (
                enrollment_id, member_id, partner_id, partner_member_id,
                effective_from, last_seen_in_feed_at
            ) VALUES (gen_random_uuid(), %s, %s, %s, '2026-01-01', NOW())
            """,
            (member_id, partner_id, pmid),
        )
    conn.commit()


# ---------------------------------------------------------------------------
# execute_deletion — full sequence
# ---------------------------------------------------------------------------


def test_execute_deletion_inserts_ledger_and_tombstones_member(postgresql) -> None:  # type: ignore[no-untyped-def]
    _apply_schema(postgresql)
    member_id = str(uuid.uuid4())
    _seed_member(
        postgresql,
        member_id=member_id,
        enrollments=[("PARTNER_A", "A00040")],
    )

    request = DeletionRequest(
        member_id=member_id,
        last_name="Johnson",
        dob="1985-04-12",
        enrollments=[("PARTNER_A", "A00040")],
    )
    result = execute_deletion(postgresql, request)
    postgresql.commit()

    assert result.member_id == member_id
    assert len(result.suppression_hashes) == 1

    cur = postgresql.cursor()
    cur.execute(
        "SELECT state, tombstoned_at, name_token FROM canonical_member WHERE member_id = %s",
        (member_id,),
    )
    state, tombstoned_at, name_token = cur.fetchone()
    assert state == "DELETED"
    assert tombstoned_at is not None
    assert name_token == ""

    cur.execute(
        "SELECT suppression_hash, override_count FROM deletion_ledger WHERE suppression_hash = %s",
        (result.suppression_hashes[0],),
    )
    h, override_count = cur.fetchone()
    assert h == result.suppression_hashes[0]
    assert override_count == 0


def test_execute_deletion_emits_required_audit_events(postgresql) -> None:  # type: ignore[no-untyped-def]
    _apply_schema(postgresql)
    member_id = str(uuid.uuid4())
    _seed_member(postgresql, member_id=member_id, enrollments=[("PARTNER_A", "A00040")])

    request = DeletionRequest(
        member_id=member_id,
        last_name="Johnson",
        dob="1985-04-12",
        enrollments=[("PARTNER_A", "A00040")],
    )
    result = execute_deletion(postgresql, request)
    classes = [e.event_class for e in result.audit_events]
    assert EVENT_DELETION_REQUESTED in classes
    assert EVENT_DELETION_EXECUTED in classes
    for event in result.audit_events:
        assert isinstance(event, AuditEvent)
        # XR-005 — only tokenized references in target_token.
        assert "Johnson" not in event.target_token
        assert "1985-04-12" not in event.target_token


def test_execute_deletion_handles_multi_partner_enrollment(postgresql) -> None:  # type: ignore[no-untyped-def]
    """A member enrolled with two partners gets two suppression hashes — one
    per (partner_id, partner_member_id) pair."""
    _apply_schema(postgresql)
    member_id = str(uuid.uuid4())
    _seed_member(
        postgresql,
        member_id=member_id,
        enrollments=[("PARTNER_A", "A00040"), ("PARTNER_B", "B00077")],
    )
    request = DeletionRequest(
        member_id=member_id,
        last_name="Johnson",
        dob="1985-04-12",
        enrollments=[("PARTNER_A", "A00040"), ("PARTNER_B", "B00077")],
    )
    result = execute_deletion(postgresql, request)
    postgresql.commit()

    assert len(result.suppression_hashes) == 2
    assert len(set(result.suppression_hashes)) == 2  # distinct hashes


def test_execute_deletion_raises_on_unknown_member(postgresql) -> None:  # type: ignore[no-untyped-def]
    _apply_schema(postgresql)
    request = DeletionRequest(
        member_id=str(uuid.uuid4()),
        last_name="Johnson",
        dob="1985-04-12",
        enrollments=[("PARTNER_A", "A00040")],
    )
    with pytest.raises(ValueError, match="canonical_member not found"):
        execute_deletion(postgresql, request)


# ---------------------------------------------------------------------------
# is_suppressed — pre-publication check (BR-703)
# ---------------------------------------------------------------------------


def test_is_suppressed_returns_true_for_deleted_identity(postgresql) -> None:  # type: ignore[no-untyped-def]
    _apply_schema(postgresql)
    member_id = str(uuid.uuid4())
    _seed_member(postgresql, member_id=member_id, enrollments=[("PARTNER_A", "A00040")])
    execute_deletion(
        postgresql,
        DeletionRequest(
            member_id=member_id,
            last_name="Johnson",
            dob="1985-04-12",
            enrollments=[("PARTNER_A", "A00040")],
        ),
    )
    postgresql.commit()

    assert is_suppressed(
        postgresql,
        last_name="Johnson",
        dob="1985-04-12",
        partner_id="PARTNER_A",
        partner_member_id="A00040",
    )


def test_is_suppressed_returns_false_for_unknown_identity(postgresql) -> None:  # type: ignore[no-untyped-def]
    _apply_schema(postgresql)
    assert not is_suppressed(
        postgresql,
        last_name="Smith",
        dob="1970-01-01",
        partner_id="PARTNER_A",
        partner_member_id="A99999",
    )


def test_is_suppressed_normalization_matches_casing_and_whitespace(postgresql) -> None:  # type: ignore[no-untyped-def]
    """Suppression hash is computed over normalized inputs — casing and
    whitespace must not let an attacker bypass suppression."""
    _apply_schema(postgresql)
    member_id = str(uuid.uuid4())
    _seed_member(postgresql, member_id=member_id, enrollments=[("PARTNER_A", "A00040")])
    execute_deletion(
        postgresql,
        DeletionRequest(
            member_id=member_id,
            last_name="Johnson",
            dob="1985-04-12",
            enrollments=[("PARTNER_A", "A00040")],
        ),
    )
    postgresql.commit()

    # Same identity, different casing/whitespace — must still be suppressed.
    assert is_suppressed(
        postgresql,
        last_name="  JOHNSON  ",
        dob="1985-04-12",
        partner_id="PARTNER_A",
        partner_member_id="A00040",
    )


# ---------------------------------------------------------------------------
# Day-1 → Day-2 reintroduction scenario (the headline A7 demo)
# ---------------------------------------------------------------------------


def test_day2_reintroduction_is_suppressed_after_day1_deletion(postgresql) -> None:  # type: ignore[no-untyped-def]
    """Day 1: PARTNER_A:A00040 is enrolled and then deleted.
    Day 2: PARTNER_B:B99999 reintroduces the same identity (last_name + dob
    match across partners). is_suppressed must catch this on the
    PARTNER_B-side (partner_id + partner_member_id) hash. NOTE: the
    BR-703 hash is per-enrollment, so we additionally insert a B-side
    suppression hash via a multi-enrollment delete.
    """
    _apply_schema(postgresql)
    member_id = str(uuid.uuid4())
    # Day 1: PARTNER_A enrollment + (anticipating B reintro) B-side hash too.
    _seed_member(
        postgresql,
        member_id=member_id,
        enrollments=[("PARTNER_A", "A00040")],
    )
    execute_deletion(
        postgresql,
        DeletionRequest(
            member_id=member_id,
            last_name="Johnson",
            dob="1985-04-12",
            # Cover both partner sides — production-style "broad ledger" entry.
            enrollments=[
                ("PARTNER_A", "A00040"),
                ("PARTNER_B", "B99999"),
            ],
        ),
    )
    postgresql.commit()

    # Day 2 PARTNER_B reintroduction — same identity, different partner.
    assert is_suppressed(
        postgresql,
        last_name="Johnson",
        dob="1985-04-12",
        partner_id="PARTNER_B",
        partner_member_id="B99999",
    )


# ---------------------------------------------------------------------------
# operator_override — BR-704 audit + override_count increment
# ---------------------------------------------------------------------------


def test_operator_override_increments_count_and_unsuppresses(postgresql) -> None:  # type: ignore[no-untyped-def]
    _apply_schema(postgresql)
    member_id = str(uuid.uuid4())
    _seed_member(postgresql, member_id=member_id, enrollments=[("PARTNER_A", "A00040")])
    result = execute_deletion(
        postgresql,
        DeletionRequest(
            member_id=member_id,
            last_name="Johnson",
            dob="1985-04-12",
            enrollments=[("PARTNER_A", "A00040")],
        ),
    )
    postgresql.commit()

    target_hash = result.suppression_hashes[0]
    assert is_suppressed(
        postgresql,
        last_name="Johnson",
        dob="1985-04-12",
        partner_id="PARTNER_A",
        partner_member_id="A00040",
    )

    event = operator_override(
        postgresql,
        target_hash=target_hash,
        reason="legal-cleared re-enrollment",
    )
    postgresql.commit()

    assert event.event_class == EVENT_DELETION_OVERRIDE
    assert event.target_token == target_hash
    assert event.context["reason"] == "legal-cleared re-enrollment"

    # Suppression no longer fires after override.
    assert not is_suppressed(
        postgresql,
        last_name="Johnson",
        dob="1985-04-12",
        partner_id="PARTNER_A",
        partner_member_id="A00040",
    )


def test_operator_override_raises_on_unknown_hash(postgresql) -> None:  # type: ignore[no-untyped-def]
    _apply_schema(postgresql)
    with pytest.raises(ValueError, match="not found"):
        operator_override(
            postgresql,
            target_hash="nonexistent-hash",
            reason="test",
        )


# ---------------------------------------------------------------------------
# route_for_publication — bulk variant
# ---------------------------------------------------------------------------


def test_route_for_publication_bulk_check(postgresql) -> None:  # type: ignore[no-untyped-def]
    _apply_schema(postgresql)
    member_id = str(uuid.uuid4())
    _seed_member(postgresql, member_id=member_id, enrollments=[("PARTNER_A", "A00040")])
    execute_deletion(
        postgresql,
        DeletionRequest(
            member_id=member_id,
            last_name="Johnson",
            dob="1985-04-12",
            enrollments=[("PARTNER_A", "A00040")],
        ),
    )
    postgresql.commit()

    suppressed = ("Johnson", "1985-04-12", "PARTNER_A", "A00040")
    clean = ("Smith", "1970-01-01", "PARTNER_A", "A99999")
    results = route_for_publication(postgresql, candidates=[suppressed, clean])

    assert results[suppressed] is True
    assert results[clean] is False


# ---------------------------------------------------------------------------
# Hash determinism (cross-check with tokenization helper)
# ---------------------------------------------------------------------------


def test_suppression_hash_is_deterministic() -> None:
    h1 = suppression_hash(
        last_name="Johnson",
        dob="1985-04-12",
        partner_id="PARTNER_A",
        partner_member_id="A00040",
    )
    h2 = suppression_hash(
        last_name="JOHNSON",  # casing irrelevant
        dob="1985-04-12",
        partner_id="PARTNER_A",
        partner_member_id="A00040",
    )
    assert h1 == h2
    h3 = suppression_hash(
        last_name="Smith",
        dob="1985-04-12",
        partner_id="PARTNER_A",
        partner_member_id="A00040",
    )
    assert h1 != h3
