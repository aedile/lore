"""Canonical eligibility store (A5) — schema + state machine.

The DDL is in ``schema.sql`` and applies to a fresh Postgres instance.
The state-machine engine in ``state_machine`` enforces BR-202 transitions
in application code (per ARD deliberate choice — not in DB triggers — so
the table is testable in isolation).
"""

from __future__ import annotations

from pathlib import Path

from prototype.canonical.state_machine import (
    ALLOWED_TRANSITIONS,
    CanonicalState,
    ForbiddenTransitionError,
    assert_transition_allowed,
)

SCHEMA_PATH: Path = Path(__file__).parent / "schema.sql"

EXPECTED_TABLES: list[str] = [
    "canonical_member",
    "deletion_ledger",
    "match_decision",
    "member_history",
    "partner_enrollment",
    "review_queue",
]

__all__ = [
    "ALLOWED_TRANSITIONS",
    "EXPECTED_TABLES",
    "SCHEMA_PATH",
    "CanonicalState",
    "ForbiddenTransitionError",
    "assert_transition_allowed",
]
