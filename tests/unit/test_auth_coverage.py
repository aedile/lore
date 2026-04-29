"""Auth coverage gate — every non-exempt route MUST require authentication.

CONSTITUTION Priority 0: enforces that no API route can be added
without explicit authentication unless its path is declared in
``shared.constants.AUTH_EXEMPT_ROUTES``.

This test is structural, not behavioural — it inspects the route
graph at app construction time and asserts every APIRoute outside the
exempt set has a dependency call named in ``EXPECTED_AUTH_DEP_NAMES``.

Today the test passes vacuously: only ``/health`` exists and it is in
the exempt set. As soon as the first non-exempt route is added, the
test activates as a real gate. This is by design — the gate is
declared and live now, so a future contributor cannot ship an
unauthenticated route without the test failing.

If you need to add a public route deliberately:
1. Add its path to ``AUTH_EXEMPT_ROUTES``
2. Document the justification in the same commit (in the ADR or
   the route's docstring)
"""

from __future__ import annotations

import pytest
from fastapi.routing import APIRoute

from lore_eligibility.bootstrapper.main import create_app
from lore_eligibility.shared.constants import AUTH_EXEMPT_ROUTES

#: Names of dependency callables that satisfy the auth requirement.
#: Add new names here when a new auth wrapper is introduced (e.g. a
#: stricter ``get_current_admin`` for admin-only endpoints).
EXPECTED_AUTH_DEP_NAMES: frozenset[str] = frozenset(
    {"get_current_operator", "get_current_user"}
)


def _walk_dependency_names(dependant: object) -> set[str]:
    """Return the set of callable names found in a FastAPI Dependant tree.

    FastAPI's ``Dependant`` carries a ``.call`` (the dependency function)
    and ``.dependencies`` (sub-dependants). We walk the full tree so an
    auth dependency declared at any nesting level counts.
    """
    found: set[str] = set()
    stack: list[object] = [dependant]
    while stack:
        current = stack.pop()
        call = getattr(current, "call", None)
        if call is not None and hasattr(call, "__name__"):
            found.add(call.__name__)
        sub = getattr(current, "dependencies", None) or []
        stack.extend(sub)
    return found


def _route_is_authenticated(route: APIRoute) -> bool:
    """True if the route has at least one dependency in EXPECTED_AUTH_DEP_NAMES."""
    dep_names = _walk_dependency_names(route.dependant)
    return bool(dep_names & EXPECTED_AUTH_DEP_NAMES)


@pytest.mark.unit
def test_every_non_exempt_route_has_auth_dependency() -> None:
    """No API route may be reachable without auth unless explicitly exempted."""
    app = create_app()
    api_routes = [r for r in app.routes if isinstance(r, APIRoute)]

    violations: list[str] = []
    for route in api_routes:
        if route.path in AUTH_EXEMPT_ROUTES:
            continue
        if not _route_is_authenticated(route):
            violations.append(f"{route.path} (methods={sorted(route.methods or set())})")

    assert not violations, (
        "The following routes have no authentication dependency and are "
        "not declared in AUTH_EXEMPT_ROUTES. Either add an auth dependency "
        "(e.g. Depends(get_current_operator)) or add the path to "
        "AUTH_EXEMPT_ROUTES with a documented justification:\n  "
        + "\n  ".join(violations)
    )


@pytest.mark.unit
def test_auth_exempt_routes_actually_correspond_to_real_routes() -> None:
    """Every entry in AUTH_EXEMPT_ROUTES is a path that exists or is FastAPI built-in.

    This catches stale entries: if a route is removed but its path is
    left in AUTH_EXEMPT_ROUTES, future contributors might assume the
    set still reflects reality.
    """
    app = create_app()
    declared_paths = {r.path for r in app.routes}
    # FastAPI built-ins that are added on attribute access, not at
    # construction. They appear in app.routes once the app is created
    # with default openapi_url/docs_url settings.
    fastapi_builtins = {"/openapi.json", "/docs", "/redoc"}

    stale = AUTH_EXEMPT_ROUTES - declared_paths - fastapi_builtins
    assert not stale, (
        f"AUTH_EXEMPT_ROUTES contains paths that no longer exist: {stale}. "
        "Remove them so the exempt list stays accurate."
    )


@pytest.mark.unit
def test_health_endpoint_is_exempt() -> None:
    """Sanity check: /health is in AUTH_EXEMPT_ROUTES."""
    assert "/health" in AUTH_EXEMPT_ROUTES


@pytest.mark.unit
def test_openapi_paths_are_exempt() -> None:
    """OpenAPI / docs paths are exempt (developer tooling)."""
    assert "/openapi.json" in AUTH_EXEMPT_ROUTES
    assert "/docs" in AUTH_EXEMPT_ROUTES
    assert "/redoc" in AUTH_EXEMPT_ROUTES
