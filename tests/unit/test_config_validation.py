"""Tests for the production-config startup validator.

Asserts that ``validate_settings`` enforces the staging/production
contract while leaving dev untouched. Each violation is tested
independently so failures point at the specific rule that broke.
"""

from __future__ import annotations

import secrets

import pytest
from cryptography.fernet import Fernet

from lore_eligibility.bootstrapper.config_validation import (
    AUDIT_KEY_EXPECTED_LENGTH,
    ENFORCED_ENVIRONMENTS,
    SECRET_KEY_MIN_LENGTH,
    validate_settings,
)
from lore_eligibility.bootstrapper.settings import Settings
from lore_eligibility.shared.errors import ConfigurationError


def _valid_production_settings(**overrides: object) -> Settings:
    """Return a fully-populated Settings instance for production tests.

    Override individual fields to exercise specific failure modes.
    """
    base: dict[str, object] = {
        "environment": "production",
        "database_url": "postgresql+asyncpg://user:pw@host:5432/db",  # pragma: allowlist secret
        "secret_key": secrets.token_hex(32),
        "audit_key": secrets.token_hex(32),
        "pii_encryption_key": Fernet.generate_key().decode(),
        "artifact_signing_key": secrets.token_hex(32),
        "auth_mode": "jwt",
        "database_tls_enabled": True,
    }
    base.update(overrides)
    return Settings(_env_file=None, **base)  # type: ignore[arg-type, call-arg]


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_dev_environment_skips_validation_with_empty_config() -> None:
    """Dev environment is allowed to have empty / default config."""
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    assert settings.environment == "dev"
    # Should not raise.
    validate_settings(settings)


@pytest.mark.unit
def test_production_with_complete_config_passes() -> None:
    """A correctly-provisioned production config validates cleanly."""
    settings = _valid_production_settings()
    validate_settings(settings)  # No exception expected.
    assert settings.environment == "production"


@pytest.mark.unit
def test_staging_environment_is_enforced() -> None:
    """Staging is also subject to the full validation contract."""
    settings = _valid_production_settings(environment="staging")
    validate_settings(settings)
    assert "staging" in ENFORCED_ENVIRONMENTS


# ---------------------------------------------------------------------------
# Attack tests — each rule fails the configured way
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.attack
def test_production_with_database_tls_disabled_fails() -> None:
    """HIPAA §164.312(e)(1) — TLS in transit is mandatory in production."""
    settings = _valid_production_settings(database_tls_enabled=False)
    with pytest.raises(ConfigurationError) as exc_info:
        validate_settings(settings)
    assert "DATABASE_TLS_ENABLED" in str(exc_info.value)
    assert "HIPAA" in str(exc_info.value)


@pytest.mark.unit
@pytest.mark.attack
def test_production_with_auth_mode_none_fails() -> None:
    """AUTH_MODE=none is forbidden outside dev."""
    settings = _valid_production_settings(auth_mode="none")
    with pytest.raises(ConfigurationError) as exc_info:
        validate_settings(settings)
    assert "AUTH_MODE" in str(exc_info.value)
    assert "forbidden" in str(exc_info.value).lower()


@pytest.mark.unit
@pytest.mark.attack
def test_production_with_short_secret_key_fails() -> None:
    """SECRET_KEY shorter than the minimum is rejected."""
    settings = _valid_production_settings(secret_key="too-short")
    with pytest.raises(ConfigurationError) as exc_info:
        validate_settings(settings)
    assert "SECRET_KEY" in str(exc_info.value)
    assert str(SECRET_KEY_MIN_LENGTH) in str(exc_info.value)


@pytest.mark.unit
@pytest.mark.attack
def test_production_with_empty_database_url_fails() -> None:
    """Empty DATABASE_URL is rejected in production."""
    settings = _valid_production_settings(database_url="")
    with pytest.raises(ConfigurationError) as exc_info:
        validate_settings(settings)
    assert "DATABASE_URL" in str(exc_info.value)


@pytest.mark.unit
@pytest.mark.attack
def test_production_with_empty_pii_encryption_key_fails() -> None:
    """Empty PII_ENCRYPTION_KEY is rejected in production."""
    settings = _valid_production_settings(pii_encryption_key="")
    with pytest.raises(ConfigurationError) as exc_info:
        validate_settings(settings)
    assert "PII_ENCRYPTION_KEY" in str(exc_info.value)


@pytest.mark.unit
@pytest.mark.attack
def test_production_with_wrong_length_audit_key_fails() -> None:
    """AUDIT_KEY must be exactly the expected length."""
    settings = _valid_production_settings(audit_key="too-short")
    with pytest.raises(ConfigurationError) as exc_info:
        validate_settings(settings)
    assert "AUDIT_KEY" in str(exc_info.value)
    assert str(AUDIT_KEY_EXPECTED_LENGTH) in str(exc_info.value)


@pytest.mark.unit
@pytest.mark.attack
def test_production_with_non_hex_audit_key_fails() -> None:
    """AUDIT_KEY of correct length but non-hex characters is rejected."""
    settings = _valid_production_settings(audit_key="z" * AUDIT_KEY_EXPECTED_LENGTH)
    with pytest.raises(ConfigurationError) as exc_info:
        validate_settings(settings)
    assert "AUDIT_KEY" in str(exc_info.value)


@pytest.mark.unit
@pytest.mark.attack
def test_production_with_signing_key_equal_to_secret_key_fails() -> None:
    """ARTIFACT_SIGNING_KEY must be distinct from SECRET_KEY."""
    shared_key = secrets.token_hex(32)
    settings = _valid_production_settings(
        secret_key=shared_key,
        artifact_signing_key=shared_key,
    )
    with pytest.raises(ConfigurationError) as exc_info:
        validate_settings(settings)
    assert "ARTIFACT_SIGNING_KEY" in str(exc_info.value)
    assert "distinct" in str(exc_info.value).lower()


@pytest.mark.unit
@pytest.mark.attack
def test_production_with_multiple_violations_reports_all() -> None:
    """Multiple violations are reported together, not just the first."""
    settings = _valid_production_settings(
        database_url="",
        auth_mode="none",
        database_tls_enabled=False,
    )
    with pytest.raises(ConfigurationError) as exc_info:
        validate_settings(settings)
    message = str(exc_info.value)
    assert "DATABASE_URL" in message
    assert "AUTH_MODE" in message
    assert "DATABASE_TLS_ENABLED" in message
