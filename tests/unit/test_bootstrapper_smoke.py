"""Smoke tests for the bootstrapper package.

These tests verify that the harness scaffold is wired correctly: imports
resolve, the FastAPI app factory builds an instance, and /health
responds. Domain-specific tests live in modules-specific files added in
later phases.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from lore_eligibility import __version__
from lore_eligibility.bootstrapper.main import create_app
from lore_eligibility.bootstrapper.settings import Settings, get_settings


@pytest.mark.unit
def test_version_is_semver_string() -> None:
    """The package version is a non-empty SemVer-shaped string."""
    assert isinstance(__version__, str)
    assert __version__ == "0.1.0"
    assert __version__.count(".") == 2


@pytest.mark.unit
def test_create_app_returns_fastapi_instance() -> None:
    """create_app builds a FastAPI app with the project metadata."""
    app = create_app()
    assert isinstance(app, FastAPI)
    assert app.title == "lore-eligibility"
    assert app.version == __version__


@pytest.mark.unit
def test_health_endpoint_returns_ok() -> None:
    """GET /health returns 200 with the project status payload."""
    client = TestClient(create_app())
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["version"] == __version__


@pytest.mark.unit
def test_settings_loads_with_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """Settings instantiates with the documented defaults when env is empty."""
    # Clear any inherited values so we exercise the defaults explicitly.
    for key in (
        "ENVIRONMENT",
        "DATABASE_URL",
        "SECRET_KEY",
        "AUDIT_KEY",
        "PII_ENCRYPTION_KEY",
        "ARTIFACT_SIGNING_KEY",
        "AUTH_MODE",
    ):
        monkeypatch.delenv(key, raising=False)

    # Disable .env file loading so the test asserts pure defaults.
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    assert settings.environment == "dev"
    assert settings.auth_mode == "jwt"
    assert settings.telemetry_enabled is True


@pytest.mark.unit
def test_get_settings_returns_settings_instance() -> None:
    """get_settings returns a populated Settings instance."""
    settings = get_settings()
    assert isinstance(settings, Settings)
    assert settings.auth_mode in {"jwt", "none"}
