"""Tests for prototype.canonical_lookup — A6 wiring.

Covers:
- The Postgres-backed lookup implements the CanonicalLookup protocol with
  the same shape as InMemoryCanonicalLookup (parametrised over both).
- Lookup returns the right CanonicalLookupResult for found and not-found.
- Lookup picks the most-recently-updated row on token collision.
- Lookup defends against unknown state values in the DB (fallback to
  not-found rather than crashing).
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from prototype.canonical import SCHEMA_PATH, CanonicalState
from prototype.canonical_lookup import PostgresCanonicalLookup
from prototype.tokenization import tokenize_dob, tokenize_name
from prototype.verification import (
    CanonicalLookup,
    CanonicalLookupResult,
    InMemoryCanonicalLookup,
    InMemoryMember,
)

pytest_plugins = ["pytest_postgresql"]


def _apply_schema(conn) -> None:  # type: ignore[no-untyped-def]
    cur = conn.cursor()
    cur.execute(Path(SCHEMA_PATH).read_text())
    conn.commit()


def _seed_member(
    conn,  # type: ignore[no-untyped-def]
    *,
    member_id: str,
    name_token: str,
    dob_token: str,
    state: str = "ELIGIBLE_ACTIVE",
) -> None:
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO canonical_member (
            member_id, state, state_effective_from, name_token, dob_token,
            first_seen_at, last_updated_at
        ) VALUES (%s, %s, NOW(), %s, %s, NOW(), NOW())
        """,
        (member_id, state, name_token, dob_token),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Both backends honour the CanonicalLookup protocol
# ---------------------------------------------------------------------------


def test_in_memory_lookup_satisfies_protocol() -> None:
    backend: CanonicalLookup = InMemoryCanonicalLookup([])
    result = backend.lookup_by_name_dob(name_token="x", dob_token="y")
    assert isinstance(result, CanonicalLookupResult)
    assert result.found is False


def test_postgres_lookup_satisfies_protocol(postgresql) -> None:  # type: ignore[no-untyped-def]
    _apply_schema(postgresql)
    backend: CanonicalLookup = PostgresCanonicalLookup(postgresql)
    result = backend.lookup_by_name_dob(name_token="x", dob_token="y")
    assert isinstance(result, CanonicalLookupResult)
    assert result.found is False


# ---------------------------------------------------------------------------
# Postgres-specific behaviours
# ---------------------------------------------------------------------------


def test_postgres_lookup_returns_active_member(postgresql) -> None:  # type: ignore[no-untyped-def]
    _apply_schema(postgresql)
    member_id = str(uuid.uuid4())
    name_tok = tokenize_name("Sarah", "Johnson")
    dob_tok = tokenize_dob("1985-04-12")
    _seed_member(postgresql, member_id=member_id, name_token=name_tok, dob_token=dob_tok)

    result = PostgresCanonicalLookup(postgresql).lookup_by_name_dob(
        name_token=name_tok, dob_token=dob_tok
    )
    assert result.found is True
    assert result.state == CanonicalState.ELIGIBLE_ACTIVE
    assert result.member_id == member_id


def test_postgres_lookup_carries_state_through(postgresql) -> None:  # type: ignore[no-untyped-def]
    """All BR-201 states map through correctly so the API can collapse them."""
    _apply_schema(postgresql)
    backend = PostgresCanonicalLookup(postgresql)
    for idx, state in enumerate(CanonicalState):
        member_id = str(uuid.uuid4())
        name_tok = f"name-tok-{idx}"
        dob_tok = f"dob-tok-{idx}"
        _seed_member(
            postgresql,
            member_id=member_id,
            name_token=name_tok,
            dob_token=dob_tok,
            state=state.value,
        )
        result = backend.lookup_by_name_dob(name_token=name_tok, dob_token=dob_tok)
        assert result.found is True
        assert result.state == state


def test_postgres_lookup_returns_not_found_for_missing(postgresql) -> None:  # type: ignore[no-untyped-def]
    _apply_schema(postgresql)
    result = PostgresCanonicalLookup(postgresql).lookup_by_name_dob(
        name_token="never-existed", dob_token="never-existed"
    )
    assert result.found is False
    assert result.state is None
    assert result.member_id is None


def test_postgres_lookup_picks_most_recently_updated_on_anchor_collision(  # type: ignore[no-untyped-def]
    postgresql,
) -> None:
    """Two canonical_member rows share the same (name_token, dob_token).
    Lookup returns the one with the latest last_updated_at."""
    _apply_schema(postgresql)
    cur = postgresql.cursor()
    name_tok = tokenize_name("Alex", "Park")
    dob_tok = tokenize_dob("1992-02-29")
    older = str(uuid.uuid4())
    newer = str(uuid.uuid4())

    cur.execute(
        """
        INSERT INTO canonical_member (
            member_id, state, state_effective_from, name_token, dob_token,
            first_seen_at, last_updated_at
        ) VALUES (%s, 'ELIGIBLE_ACTIVE', NOW() - INTERVAL '2 days', %s, %s,
                  NOW() - INTERVAL '2 days', NOW() - INTERVAL '2 days')
        """,
        (older, name_tok, dob_tok),
    )
    cur.execute(
        """
        INSERT INTO canonical_member (
            member_id, state, state_effective_from, name_token, dob_token,
            first_seen_at, last_updated_at
        ) VALUES (%s, 'ELIGIBLE_ACTIVE', NOW(), %s, %s, NOW(), NOW())
        """,
        (newer, name_tok, dob_tok),
    )
    postgresql.commit()

    result = PostgresCanonicalLookup(postgresql).lookup_by_name_dob(
        name_token=name_tok, dob_token=dob_tok
    )
    assert result.found is True
    assert result.member_id == newer


def test_postgres_lookup_defends_against_unknown_state(postgresql) -> None:  # type: ignore[no-untyped-def]
    """If somehow the DB row has a state value outside the BR-201 enum,
    lookup falls back to not-found rather than crashing or leaking a
    bogus state to the API. Defensive only — the CHECK constraint on
    canonical_member.state should make this impossible in practice."""
    _apply_schema(postgresql)
    cur = postgresql.cursor()
    member_id = str(uuid.uuid4())
    # Drop the CHECK constraint to insert a deliberately-invalid state
    # for the test only.
    cur.execute("ALTER TABLE canonical_member DROP CONSTRAINT canonical_member_state_check")
    cur.execute(
        """
        INSERT INTO canonical_member (
            member_id, state, state_effective_from, name_token, dob_token,
            first_seen_at, last_updated_at
        ) VALUES (%s, 'NOT_A_VALID_STATE', NOW(), 'tok-name', 'tok-dob',
                  NOW(), NOW())
        """,
        (member_id,),
    )
    postgresql.commit()

    result = PostgresCanonicalLookup(postgresql).lookup_by_name_dob(
        name_token="tok-name", dob_token="tok-dob"
    )
    # Defensive fallback — return not-found rather than crash with ValueError
    # or hand the API an unknown CanonicalState.
    assert result.found is False


# ---------------------------------------------------------------------------
# Cross-backend equivalence — both InMemory and Postgres yield the same
# CanonicalLookupResult shape for the same logical state.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "state",
    [
        CanonicalState.ELIGIBLE_ACTIVE,
        CanonicalState.ELIGIBLE_GRACE,
        CanonicalState.INELIGIBLE,
        CanonicalState.DELETED,
    ],
)
def test_both_backends_return_identical_result_shape(  # type: ignore[no-untyped-def]
    postgresql,
    state: CanonicalState,
) -> None:
    _apply_schema(postgresql)
    member_id = str(uuid.uuid4())
    name_tok = tokenize_name("Pat", "Garcia")
    dob_tok = tokenize_dob("1988-08-08")

    in_mem = InMemoryCanonicalLookup(
        [
            InMemoryMember(
                member_id=member_id,
                name_token=name_tok,
                dob_token=dob_tok,
                state=state,
            ),
        ]
    )
    _seed_member(
        postgresql,
        member_id=member_id,
        name_token=name_tok,
        dob_token=dob_tok,
        state=state.value,
    )
    pg = PostgresCanonicalLookup(postgresql)

    in_mem_result = in_mem.lookup_by_name_dob(name_token=name_tok, dob_token=dob_tok)
    pg_result = pg.lookup_by_name_dob(name_token=name_tok, dob_token=dob_tok)

    assert in_mem_result.found == pg_result.found is True
    assert in_mem_result.state == pg_result.state == state
    assert in_mem_result.member_id == pg_result.member_id == member_id
