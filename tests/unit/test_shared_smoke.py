"""Smoke tests for the shared package.

Covers exception hierarchy, constants, and CLI surface. Domain-specific
tests live in module-specific files added in later phases.
"""

from __future__ import annotations

import pytest
from click.testing import CliRunner

from lore_eligibility import __version__
from lore_eligibility.cli import cli
from lore_eligibility.shared.constants import AUTH_EXEMPT_ROUTES
from lore_eligibility.shared.errors import (
    ConfigurationError,
    DataIntegrityError,
    IdentityResolutionError,
    LoreEligibilityError,
)


@pytest.mark.unit
def test_exception_hierarchy_inherits_from_base() -> None:
    """All project exceptions inherit from LoreEligibilityError."""
    assert issubclass(ConfigurationError, LoreEligibilityError)
    assert issubclass(DataIntegrityError, LoreEligibilityError)
    assert issubclass(IdentityResolutionError, LoreEligibilityError)
    assert issubclass(LoreEligibilityError, Exception)


@pytest.mark.unit
def test_auth_exempt_routes_contains_health() -> None:
    """The AUTH_EXEMPT_ROUTES set names every route that bypasses auth."""
    assert "/health" in AUTH_EXEMPT_ROUTES
    assert "/openapi.json" in AUTH_EXEMPT_ROUTES
    assert isinstance(AUTH_EXEMPT_ROUTES, frozenset)


@pytest.mark.unit
def test_cli_version_command_prints_version() -> None:
    """`lore-eligibility version` prints the package version."""
    runner = CliRunner()
    result = runner.invoke(cli, ["version"])
    assert result.exit_code == 0
    assert __version__ in result.output


@pytest.mark.unit
def test_cli_help_lists_subcommands() -> None:
    """`lore-eligibility --help` lists registered subcommands."""
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "version" in result.output
