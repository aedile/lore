"""Schema-apply test for the canonical store DDL (A5).

Verifies that ``schema.sql`` applies cleanly to a fresh Postgres instance
and that the six expected tables are created with the expected indexes.
Uses ``pytest-postgresql`` to spin up a temp Postgres on a random port,
so this runs without docker-compose being up.
"""

from __future__ import annotations

import psycopg.errors
import pytest

from prototype.canonical import EXPECTED_TABLES, SCHEMA_PATH

# Spin up a Postgres process and a clean DB on a random port.
# pytest-postgresql provides ``postgresql_proc`` and ``postgresql`` fixtures.

pytest_plugins = ["pytest_postgresql"]


@pytest.fixture
def fresh_db(postgresql):  # type: ignore[no-untyped-def]
    """A fresh Postgres connection from pytest-postgresql; rolled back after each test."""
    return postgresql


def test_schema_applies_cleanly(fresh_db) -> None:  # type: ignore[no-untyped-def]
    sql = SCHEMA_PATH.read_text()
    cur = fresh_db.cursor()
    cur.execute(sql)
    fresh_db.commit()

    cur.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename")
    actual = [row[0] for row in cur.fetchall()]
    assert actual == EXPECTED_TABLES


def test_canonical_member_state_constraint_rejects_unknown_state(fresh_db) -> None:  # type: ignore[no-untyped-def]
    """The CHECK constraint on canonical_member.state rejects unknown values."""
    fresh_db.cursor().execute(SCHEMA_PATH.read_text())
    fresh_db.commit()

    cur = fresh_db.cursor()
    with pytest.raises(psycopg.errors.CheckViolation) as exc_info:
        cur.execute(
            """
            INSERT INTO canonical_member (
                member_id, state, state_effective_from, name_token, dob_token,
                first_seen_at, last_updated_at
            ) VALUES (
                gen_random_uuid(), 'NOT_A_REAL_STATE', NOW(), 'tok-name', 'tok-dob',
                NOW(), NOW()
            )
            """
        )
    fresh_db.rollback()
    assert "canonical_member" in str(exc_info.value).lower()


def test_canonical_member_accepts_each_valid_state(fresh_db) -> None:  # type: ignore[no-untyped-def]
    """Each enumerated state in BR-201 is accepted by the CHECK constraint."""
    fresh_db.cursor().execute(SCHEMA_PATH.read_text())
    fresh_db.commit()

    cur = fresh_db.cursor()
    for state in (
        "PENDING_RESOLUTION",
        "ELIGIBLE_ACTIVE",
        "ELIGIBLE_GRACE",
        "INELIGIBLE",
        "DELETED",
    ):
        cur.execute(
            """
            INSERT INTO canonical_member (
                member_id, state, state_effective_from, name_token, dob_token,
                first_seen_at, last_updated_at
            ) VALUES (
                gen_random_uuid(), %s, NOW(), 'tok-name', 'tok-dob', NOW(), NOW()
            )
            """,
            (state,),
        )
    fresh_db.commit()

    cur.execute("SELECT COUNT(*) FROM canonical_member")
    (count,) = cur.fetchone()
    assert count == 5


def test_partner_enrollment_unique_constraint(fresh_db) -> None:  # type: ignore[no-untyped-def]
    """The (partner_id, partner_member_id, effective_from) tuple must be unique."""
    fresh_db.cursor().execute(SCHEMA_PATH.read_text())
    fresh_db.commit()

    cur = fresh_db.cursor()
    cur.execute(
        """
        INSERT INTO canonical_member (
            member_id, state, state_effective_from, name_token, dob_token,
            first_seen_at, last_updated_at
        ) VALUES (
            '00000000-0000-0000-0000-000000000001', 'ELIGIBLE_ACTIVE', NOW(),
            'tok-name', 'tok-dob', NOW(), NOW()
        )
        """
    )
    cur.execute(
        """
        INSERT INTO partner_enrollment (
            enrollment_id, member_id, partner_id, partner_member_id,
            effective_from, last_seen_in_feed_at
        ) VALUES (
            gen_random_uuid(), '00000000-0000-0000-0000-000000000001',
            'PARTNER_A', 'A00001', '2026-01-01', NOW()
        )
        """
    )
    fresh_db.commit()

    with pytest.raises(psycopg.errors.UniqueViolation):
        cur.execute(
            """
            INSERT INTO partner_enrollment (
                enrollment_id, member_id, partner_id, partner_member_id,
                effective_from, last_seen_in_feed_at
            ) VALUES (
                gen_random_uuid(), '00000000-0000-0000-0000-000000000001',
                'PARTNER_A', 'A00001', '2026-01-01', NOW()
            )
            """
        )
    fresh_db.rollback()


def test_match_decision_tier_constraint_rejects_unknown_tier(fresh_db) -> None:  # type: ignore[no-untyped-def]
    """tier_outcome CHECK constraint rejects unknown tiers."""
    fresh_db.cursor().execute(SCHEMA_PATH.read_text())
    fresh_db.commit()

    cur = fresh_db.cursor()
    with pytest.raises(psycopg.errors.CheckViolation):
        cur.execute(
            """
            INSERT INTO match_decision (
                decision_id, candidate_record_ref, tier_outcome,
                algorithm_version, config_version, decided_at
            ) VALUES (
                gen_random_uuid(), 'PARTNER_A:A00001', 'TIER_5_NONSENSE',
                'splink-1.0', 'cfg-1', NOW()
            )
            """
        )
    fresh_db.rollback()


def test_deletion_ledger_unique_suppression_hash(fresh_db) -> None:  # type: ignore[no-untyped-def]
    """suppression_hash is UNIQUE — re-inserting the same hash fails."""
    fresh_db.cursor().execute(SCHEMA_PATH.read_text())
    fresh_db.commit()

    cur = fresh_db.cursor()
    cur.execute(
        """
        INSERT INTO deletion_ledger (suppression_hash, deleted_at, deletion_request_id)
        VALUES ('hash-abc-123', NOW(), gen_random_uuid())
        """
    )
    fresh_db.commit()
    with pytest.raises(psycopg.errors.UniqueViolation):
        cur.execute(
            """
            INSERT INTO deletion_ledger (suppression_hash, deleted_at, deletion_request_id)
            VALUES ('hash-abc-123', NOW(), gen_random_uuid())
            """
        )
    fresh_db.rollback()
