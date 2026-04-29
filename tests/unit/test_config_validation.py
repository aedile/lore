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


# ---------------------------------------------------------------------------
# Mutation-killing tests
#
# These tests pin the *exact* canonical wording of each error message and
# the precise boundary semantics of length/equality checks. They exist to
# kill mutmut survivors that flip case, wrap strings in XX...XX sentinels,
# replace string literals with ``None``, or shift comparison operators by
# one. Without them, the validator would still "raise on bad config" but
# the error messages operators see would silently drift, defeating the
# point of fail-fast startup validation.
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.attack
def test_secret_key_at_minimum_length_passes() -> None:
    """SECRET_KEY at exactly the minimum length is accepted (boundary).

    Pins ``len(secret_key) < SECRET_KEY_MIN_LENGTH`` rather than ``<=`` —
    a mutation flipping the operator would reject an exactly-32-char key
    that this rule intentionally permits.
    """
    boundary_key = "a" * SECRET_KEY_MIN_LENGTH
    assert len(boundary_key) == SECRET_KEY_MIN_LENGTH
    settings = _valid_production_settings(secret_key=boundary_key)
    # Must NOT raise — exactly-min-length is allowed.
    validate_settings(settings)
    assert settings.secret_key == boundary_key


@pytest.mark.unit
@pytest.mark.attack
def test_secret_key_one_below_minimum_reports_actual_length() -> None:
    """SECRET_KEY one below the minimum is rejected and reports got=N.

    Locks the f-string ``(got {len(...)})`` content against length-arg
    swaps and confirms the comparison rejects the value just below the
    threshold (the strict ``<`` boundary).
    """
    short_key = "a" * (SECRET_KEY_MIN_LENGTH - 1)
    settings = _valid_production_settings(secret_key=short_key)
    with pytest.raises(ConfigurationError) as exc_info:
        validate_settings(settings)
    message = str(exc_info.value)
    assert f"at least {SECRET_KEY_MIN_LENGTH} characters" in message
    assert f"(got {SECRET_KEY_MIN_LENGTH - 1})" in message


@pytest.mark.unit
@pytest.mark.attack
def test_database_url_error_uses_canonical_phrase() -> None:
    """Empty DATABASE_URL emits the canonical, case-sensitive message."""
    settings = _valid_production_settings(database_url="")
    with pytest.raises(ConfigurationError) as exc_info:
        validate_settings(settings)
    message = str(exc_info.value)
    assert "DATABASE_URL is required in non-dev environments." in message
    # Negative checks pin case-sensitivity — silent case flips would drift docs.
    assert "DATABASE_URL IS REQUIRED" not in message
    assert "XXDATABASE_URL" not in message


@pytest.mark.unit
@pytest.mark.attack
def test_secret_key_error_uses_canonical_generate_hint() -> None:
    """SECRET_KEY error includes the operator-facing 'Generate via:' hint."""
    settings = _valid_production_settings(secret_key="too-short")
    with pytest.raises(ConfigurationError) as exc_info:
        validate_settings(settings)
    message = str(exc_info.value)
    assert 'Generate via: python -c "import secrets; print(secrets.token_hex(32))"' in message
    assert "GENERATE VIA" not in message
    assert "generate via:" not in message


@pytest.mark.unit
@pytest.mark.attack
def test_auth_mode_error_first_line_canonical() -> None:
    """AUTH_MODE error first line is the exact forbidden-phrase wording."""
    settings = _valid_production_settings(auth_mode="none")
    with pytest.raises(ConfigurationError) as exc_info:
        validate_settings(settings)
    message = str(exc_info.value)
    assert "AUTH_MODE='none' is forbidden in staging and production." in message
    assert "auth_mode='none'" not in message
    assert "AUTH_MODE='NONE'" not in message


@pytest.mark.unit
@pytest.mark.attack
def test_auth_mode_error_second_line_canonical() -> None:
    """AUTH_MODE error second line names JWT_PUBLIC_KEY / JWT_PRIVATE_KEY."""
    settings = _valid_production_settings(auth_mode="none")
    with pytest.raises(ConfigurationError) as exc_info:
        validate_settings(settings)
    message = str(exc_info.value)
    assert "Set AUTH_MODE=jwt and provision JWT_PUBLIC_KEY / JWT_PRIVATE_KEY." in message
    assert "set auth_mode=jwt" not in message
    assert "SET AUTH_MODE=JWT" not in message


@pytest.mark.unit
@pytest.mark.attack
def test_database_tls_error_lines_canonical() -> None:
    """DATABASE_TLS_ENABLED error contains all three canonical fragments."""
    settings = _valid_production_settings(database_tls_enabled=False)
    with pytest.raises(ConfigurationError) as exc_info:
        validate_settings(settings)
    message = str(exc_info.value)
    assert "DATABASE_TLS_ENABLED must be true in non-dev environments." in message
    assert "HIPAA Security Rule §164.312(e)(1) requires encryption in" in message
    assert "transit for PHI." in message
    # Pin case so silent uppercasing of HIPAA text is detected.
    assert "transit for phi." not in message
    assert "TRANSIT FOR PHI." not in message


@pytest.mark.unit
@pytest.mark.attack
def test_audit_key_error_lines_canonical() -> None:
    """AUDIT_KEY error names the expected length, hex format, and hint."""
    settings = _valid_production_settings(audit_key="too-short")
    with pytest.raises(ConfigurationError) as exc_info:
        validate_settings(settings)
    message = str(exc_info.value)
    assert f"AUDIT_KEY must be a {AUDIT_KEY_EXPECTED_LENGTH}-character" in message
    assert "lowercase hex string (32 raw bytes)." in message
    assert 'Generate via: python -c "import secrets; print(secrets.token_hex(32))"' in message
    assert "LOWERCASE HEX STRING" not in message


@pytest.mark.unit
@pytest.mark.attack
def test_pii_encryption_key_error_lines_canonical() -> None:
    """PII_ENCRYPTION_KEY error preserves the exact Fernet-generation hint."""
    settings = _valid_production_settings(pii_encryption_key="")
    with pytest.raises(ConfigurationError) as exc_info:
        validate_settings(settings)
    message = str(exc_info.value)
    assert "PII_ENCRYPTION_KEY is required in non-dev environments." in message
    assert 'Generate via: python -c "from cryptography.fernet import Fernet;' in message
    assert 'print(Fernet.generate_key().decode())"' in message
    # Mutation that lowercases ``Fernet`` would break the operator hint.
    assert "from cryptography.fernet import fernet" not in message
    assert "print(fernet.generate_key()" not in message


@pytest.mark.unit
@pytest.mark.attack
def test_artifact_signing_key_required_error_lines_canonical() -> None:
    """Empty ARTIFACT_SIGNING_KEY raises ConfigurationError, not TypeError.

    A mutation that replaces the string literal with ``None`` would cause
    ``"\\n  - ".join(errors)`` to raise ``TypeError`` instead — this test
    pins the exception type and the canonical wording.
    """
    settings = _valid_production_settings(artifact_signing_key="")
    with pytest.raises(ConfigurationError) as exc_info:
        validate_settings(settings)
    message = str(exc_info.value)
    # Both fragments must appear — proves the multi-line literal survived intact.
    assert "ARTIFACT_SIGNING_KEY is required in non-dev environments and" in message
    assert "must be distinct from SECRET_KEY." in message
    assert "artifact_signing_key is required" not in message
    assert "must be distinct from secret_key." not in message


@pytest.mark.unit
@pytest.mark.attack
def test_artifact_signing_key_distinct_error_canonical_when_equal_to_secret_key() -> None:
    """When ARTIFACT_SIGNING_KEY equals SECRET_KEY, the elif-branch fires."""
    shared_key = secrets.token_hex(32)
    settings = _valid_production_settings(
        secret_key=shared_key,
        artifact_signing_key=shared_key,
    )
    with pytest.raises(ConfigurationError) as exc_info:
        validate_settings(settings)
    message = str(exc_info.value)
    # Exact wording from the elif branch — distinct from the if-branch message.
    assert "ARTIFACT_SIGNING_KEY must be distinct from SECRET_KEY." in message
    assert "ARTIFACT_SIGNING_KEY MUST BE DISTINCT" not in message
    assert "XXARTIFACT_SIGNING_KEY" not in message


@pytest.mark.unit
@pytest.mark.attack
def test_configuration_error_header_canonical() -> None:
    """The ConfigurationError header uses the exact 'Configuration validation failed for' phrase."""
    settings = _valid_production_settings(database_url="")
    with pytest.raises(ConfigurationError) as exc_info:
        validate_settings(settings)
    message = str(exc_info.value)
    assert message.startswith("Configuration validation failed for ")
    assert "ENVIRONMENT='production'" in message
    assert "configuration validation failed" not in message
    assert "CONFIGURATION VALIDATION FAILED" not in message


@pytest.mark.unit
@pytest.mark.attack
def test_multiple_violations_use_newline_bullet_separator() -> None:
    """Each violation appears on its own ``\\n  - `` bulleted line."""
    settings = _valid_production_settings(
        database_url="",
        auth_mode="none",
        database_tls_enabled=False,
    )
    with pytest.raises(ConfigurationError) as exc_info:
        validate_settings(settings)
    message = str(exc_info.value)
    # The header is followed by the first bullet, and each subsequent
    # violation is glued on with the same "\n  - " separator.
    assert ":\n  - " in message
    # Three distinct violations -> at least two separator occurrences AFTER
    # the header bullet.
    assert message.count("\n  - ") >= 3
    # Each bullet introduces a violation, so the joined separator must
    # not have been mutated to wrap (XX...XX) sentinels.
    assert "XX\n  - XX" not in message


@pytest.mark.unit
@pytest.mark.attack
def test_all_error_branches_message_has_no_sentinel_markers() -> None:
    """Triggering every validation branch yields a message free of ``XX`` sentinels.

    A real ``ConfigurationError`` message contains operator instructions and
    HIPAA citations — it never contains the substring ``"XX"``. Mutating any
    branch's error literal to wrap it in ``XX...XX`` (mutmut's empty-string
    marker) would surface here. Triggering every branch in one call means
    one assertion locks down every branch's literal content.
    """
    # Every field is invalid: empty url/pii/signing key, short secret, "none"
    # auth, TLS off, malformed audit key. This forces every if/elif branch.
    short_secret = "x" * (SECRET_KEY_MIN_LENGTH - 1)
    settings = _valid_production_settings(
        database_url="",
        secret_key=short_secret,
        auth_mode="none",
        database_tls_enabled=False,
        audit_key="not-hex-and-wrong-length",
        pii_encryption_key="",
        artifact_signing_key="",
    )
    with pytest.raises(ConfigurationError) as exc_info:
        validate_settings(settings)
    message = str(exc_info.value)
    # Every branch's primary identifier must appear — confirms each branch ran.
    assert "DATABASE_URL" in message
    assert "SECRET_KEY" in message
    assert "AUTH_MODE" in message
    assert "DATABASE_TLS_ENABLED" in message
    assert "AUDIT_KEY" in message
    assert "PII_ENCRYPTION_KEY" in message
    assert "ARTIFACT_SIGNING_KEY" in message
    # Critical: no mutmut empty-marker sentinels anywhere in the joined message.
    assert "XX" not in message
