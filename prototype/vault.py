"""Random-token PII vault — A8 from PROTOTYPE_PRD.md.

The non-joinable side of AD-009: random tokens whose plaintext lives only
in the vault. ``store`` returns a token; ``reveal`` returns the plaintext
for an authorized caller; ``tombstone`` purges plaintext while leaving
the token row in place so historical audit references continue to resolve
(to ``None``) without leaking the deleted PII.

Production target replaces the SQLite backing with a Cloud-KMS-wrapped
vault per the ARD's Stubbed-for-Prototype list. The interface here is
identical to the production contract.
"""

from __future__ import annotations

import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS vault_tokens (
    token         TEXT PRIMARY KEY,
    field_class   TEXT NOT NULL,
    plaintext     TEXT,
    created_at    TEXT NOT NULL,
    tombstoned_at TEXT
);
"""


class Vault:
    """SQLite-backed random-token vault. Threadsafe enough for the prototype."""

    def __init__(self, path: Path | str = ":memory:") -> None:
        self.path = str(path)
        self._conn = sqlite3.connect(self.path, isolation_level=None)  # autocommit
        self._conn.execute(_SCHEMA)

    # ------------------------------------------------------------------
    # Public API — matches the production TokenizationService contract.
    # ------------------------------------------------------------------

    def store(self, *, field_class: str, plaintext: str) -> str:
        """Insert plaintext under a fresh random token; return the token."""
        token = f"vt_{uuid.uuid4().hex}"
        self._conn.execute(
            "INSERT INTO vault_tokens (token, field_class, plaintext, created_at) VALUES (?, ?, ?, ?)",
            (token, field_class, plaintext, datetime.now(UTC).isoformat()),
        )
        return token

    def reveal(self, token: str) -> str | None:
        """Return plaintext for ``token``, or None if missing or tombstoned."""
        cur = self._conn.execute(
            "SELECT plaintext, tombstoned_at FROM vault_tokens WHERE token = ?", (token,)
        )
        row = cur.fetchone()
        if row is None:
            return None
        plaintext, tombstoned_at = row
        if tombstoned_at is not None:
            return None
        return plaintext  # type: ignore[no-any-return]

    def tombstone(self, token: str) -> bool:
        """Null the plaintext for ``token`` and stamp tombstoned_at.

        Returns True if a row was updated; False if the token is unknown.
        BR-702 + XR-006 — the token reference remains so historical audit
        events still resolve to "tombstoned" rather than dangling.
        """
        cur = self._conn.execute(
            """
            UPDATE vault_tokens
               SET plaintext = NULL,
                   tombstoned_at = ?
             WHERE token = ? AND tombstoned_at IS NULL
            """,
            (datetime.now(UTC).isoformat(), token),
        )
        return cur.rowcount > 0

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        self._conn.close()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """Yield the underlying connection inside a transaction."""
        try:
            self._conn.execute("BEGIN")
            yield self._conn
            self._conn.execute("COMMIT")
        except Exception:
            self._conn.execute("ROLLBACK")
            raise


__all__ = ["Vault"]
