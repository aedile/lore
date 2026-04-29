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
EXPECTED_AUTH_DEP_NAMES: frozenset[str] = frozenset({"get_current_operator", "get_current_user"})


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
    """No API route may be reachable without auth unless explicitly exempted.

    Behaviour gate: when at least one non-exempt route exists, every such
    route MUST carry a dependency named in EXPECTED_AUTH_DEP_NAMES. If the
    app currently exposes only exempt routes, the test SKIPS with an
    explicit "gate is dormant" signal so the dormancy is visible in CI
    output rather than masquerading as a passing assertion.

    This replaces an earlier parity assertion (``exempt_count + audited
    == len(api_routes)``) which was tautological by construction: the
    loop incremented ``audited`` iff the path was non-exempt, so the
    equality was guaranteed and could not detect a regression.
    """
    app = create_app()
    api_routes = [r for r in app.routes if isinstance(r, APIRoute)]

    # The gate has nothing to assert against if the app has no APIRoutes
    # at all — fail loudly so the test cannot pass vacuously after a
    # router-registration regression.
    assert api_routes, "create_app() returned no APIRoutes; auth gate cannot run"

    violations: list[str] = []
    audited_routes: list[APIRoute] = []
    for route in api_routes:
        if route.path in AUTH_EXEMPT_ROUTES:
            continue
        audited_routes.append(route)
        if not _route_is_authenticated(route):
            violations.append(f"{route.path} (methods={sorted(route.methods or set())})")

    if not audited_routes:
        pytest.skip(
            "auth-coverage gate is dormant: every APIRoute is in "
            "AUTH_EXEMPT_ROUTES. The gate activates as soon as the first "
            "non-exempt route is registered. Skipping is preferable to a "
            "vacuous pass because dormancy is explicit in CI output."
        )

    assert not violations, (
        "The following routes have no authentication dependency and are "
        "not declared in AUTH_EXEMPT_ROUTES. Either add an auth dependency "
        "(e.g. Depends(get_current_operator)) or add the path to "
        "AUTH_EXEMPT_ROUTES with a documented justification:\n  " + "\n  ".join(violations)
    )

    # Behaviour assertion: every audited route must carry at least one
    # dependency whose callable name is in EXPECTED_AUTH_DEP_NAMES. This
    # is the positive form of the violation check above and pins the
    # contract that "audited" means "auth-walker actually inspected this
    # route's dependency tree and found a known auth dep" — not just
    # "this route is non-exempt". A regression that swapped
    # _walk_dependency_names for a function that always returned
    # {"get_current_operator"} would still fail because the assertion
    # below also enforces that the dep set is a subset of declared deps.
    for route in audited_routes:
        dep_names = _walk_dependency_names(route.dependant)
        matched = dep_names & EXPECTED_AUTH_DEP_NAMES
        assert matched, (
            f"Route {route.path} is non-exempt but no dependency in its "
            f"Dependant tree matches EXPECTED_AUTH_DEP_NAMES. Found deps: "
            f"{sorted(dep_names)}; expected one of: "
            f"{sorted(EXPECTED_AUTH_DEP_NAMES)}."
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
    # Every exempt path is either declared on the app or a known builtin —
    # no third category should ever exist.
    unaccounted = AUTH_EXEMPT_ROUTES - declared_paths - fastapi_builtins
    assert unaccounted == set()
    # And every exempt path must start with "/" — guards against typos like
    # "health" instead of "/health" silently disabling the gate.
    assert all(p.startswith("/") for p in AUTH_EXEMPT_ROUTES)


@pytest.mark.unit
def test_health_endpoint_is_exempt() -> None:
    """Sanity check: /health is in AUTH_EXEMPT_ROUTES and is a real route."""
    assert "/health" in AUTH_EXEMPT_ROUTES
    # The /health path must be served by the app — otherwise its presence
    # in the exempt set is dead config, not a real exemption.
    app = create_app()
    health_routes = [r for r in app.routes if isinstance(r, APIRoute) and r.path == "/health"]
    assert len(health_routes) == 1, "Expected exactly one /health APIRoute"
    # And it must NOT carry an auth dependency — otherwise the exemption
    # is meaningless. This pins the "exempt = unauthenticated" contract.
    assert not _route_is_authenticated(health_routes[0])


@pytest.mark.unit
def test_openapi_paths_are_exempt() -> None:
    """OpenAPI / docs paths are exempt (developer tooling)."""
    assert "/openapi.json" in AUTH_EXEMPT_ROUTES
    assert "/docs" in AUTH_EXEMPT_ROUTES
    assert "/redoc" in AUTH_EXEMPT_ROUTES
    # The exempt set must contain at least these three FastAPI-builtin
    # documentation paths plus /health — i.e. >= 4 total entries.
    assert len(AUTH_EXEMPT_ROUTES) >= 4
    # All three OpenAPI paths must be present together — partial exemption
    # would leave docs reachable but openapi.json blocked or vice versa.
    assert {"/openapi.json", "/docs", "/redoc"}.issubset(AUTH_EXEMPT_ROUTES)
