"""Project-wide constants.

Add new constants here only when they are used by 2+ modules. Module-local
constants belong in the module's own constants.py.
"""

from __future__ import annotations

# Routes that do not require authentication. Used by the auth-coverage
# test in tests/unit/ to assert that every other route has a
# get_current_operator dependency wired in.
AUTH_EXEMPT_ROUTES: frozenset[str] = frozenset(
    {
        "/health",
        "/docs",
        "/redoc",
        "/openapi.json",
    }
)
