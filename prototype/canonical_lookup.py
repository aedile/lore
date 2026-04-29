"""Postgres-backed CanonicalLookup — A6 wiring for live-demo verification.

Implements the ``CanonicalLookup`` protocol against a real
``canonical_member`` table. The verification API uses this when the demo
runs against the populated day-1 ingest output; tests can still use
``InMemoryCanonicalLookup`` for unit-scope speed.

Lookup is by (name_token, dob_token) — the deterministic-non-FPE
joinable identifiers from AD-009. The verification request body is
plaintext; the API tokenizes before calling lookup_by_name_dob, so the
DB query parameters never leak the plaintext claim.

Indexed on canonical_member(name_token, dob_token) per the A5 schema
(``idx_canonical_member_anchor``) so lookup is O(log n) at partner scale.
"""

from __future__ import annotations

from typing import Any

from prototype.canonical import CanonicalState
from prototype.verification import CanonicalLookupResult


class PostgresCanonicalLookup:
    """CanonicalLookup backed by canonical_member rows in Postgres."""

    def __init__(self, conn: Any) -> None:
        self._conn = conn

    def lookup_by_name_dob(
        self,
        *,
        name_token: str,
        dob_token: str,
    ) -> CanonicalLookupResult:
        """Return the first canonical_member matching (name_token, dob_token).

        On collision (multiple canonicals share the same anchor — extremely
        rare for HMAC-tokenized inputs but possible if ingest produced a
        false-merge that was later split) the lookup returns the
        most-recently-updated record.
        """
        cur = self._conn.cursor()
        cur.execute(
            """
            SELECT member_id, state
              FROM canonical_member
             WHERE name_token = %s AND dob_token = %s
             ORDER BY last_updated_at DESC
             LIMIT 1
            """,
            (name_token, dob_token),
        )
        row = cur.fetchone()
        if row is None:
            return CanonicalLookupResult(found=False)
        member_id, state_value = row
        try:
            state = CanonicalState(state_value)
        except ValueError:
            # Unknown state in DB — defensive fallback to "not found".
            return CanonicalLookupResult(found=False)
        return CanonicalLookupResult(
            found=True,
            state=state,
            member_id=str(member_id),
        )


__all__ = ["PostgresCanonicalLookup"]
