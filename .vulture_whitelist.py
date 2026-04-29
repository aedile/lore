"""Vulture whitelist — declare names that vulture should treat as used.

Bare identifiers reference attributes/functions whose use is not visible
to vulture's static analysis (e.g. FastAPI route decorators, pydantic
model attributes accessed via .model_dump(), pytest fixtures resolved by
name at runtime).

Each entry should be commented with the runtime call site. The lint
ignores for F821/B018/E501 on this file are configured in pyproject.toml.
"""

# CLI subcommand registered via @cli.command(); invoked as
# `lore-eligibility version` through the [project.scripts] entry point.
version

# Referenced by tests/unit/test_auth_coverage.py and consumed at runtime
# by the FastAPI auth-dependency wiring to flag exempt routes.
AUTH_EXEMPT_ROUTES

# Public exception type intentionally exported from shared.errors for
# downstream module use; raised by data-layer code added in later phases.
DataIntegrityError

# Public exception type intentionally exported from shared.errors for
# downstream module use; raised by identity-resolution code added in
# later phases.
IdentityResolutionError
