"""Startup configuration validation.

Settings has dev-friendly defaults (empty strings for required secrets,
``auth_mode='jwt'`` rather than ``'none'``) so local development and
tests work out of the box without provisioning a complete .env. This
module is the runtime gate that fails fast when the same loose config
is used in staging or production, where it would represent a real
security failure.

CONSTITUTION Priority 0:
- HIPAA Security Rule §164.312(e)(1) — encryption in transit
- HIPAA Security Rule §164.312(a)(1) — access control / authentication
- HIPAA Security Rule §164.312(b) — audit controls

The validator is called from ``create_app()`` so it runs before the
FastAPI app is even returned. Production never sees an app object
constructed against insecure config.
"""

from __future__ import annotations

import re

from lore_eligibility.bootstrapper.settings import Settings
from lore_eligibility.shared.errors import ConfigurationError

#: Environments where validation is enforced. ``dev`` is intentionally
#: not included — local devs and tests are allowed to run against
#: defaults.
ENFORCED_ENVIRONMENTS: frozenset[str] = frozenset({"staging", "production"})

#: Minimum length for SECRET_KEY (used as HMAC seed for sessions etc).
SECRET_KEY_MIN_LENGTH: int = 32

#: Expected length for AUDIT_KEY: 32 raw bytes hex-encoded = 64 chars.
AUDIT_KEY_EXPECTED_LENGTH: int = 64

#: Pattern for a lowercase hex string of any length.
_HEX_PATTERN = re.compile(r"^[0-9a-f]+$")


def validate_settings(settings: Settings) -> None:
    """Validate settings against the environment-specific contract.

    No-op when ``settings.environment == 'dev'``. In staging or
    production, raises :class:`ConfigurationError` listing every
    violation found (so operators see the full picture, not the first
    failure).

    Args:
        settings: The Settings instance to validate.

    Raises:
        ConfigurationError: If the environment is staging/production
            and one or more validation rules fail.
    """
    if settings.environment not in ENFORCED_ENVIRONMENTS:
        return

    errors: list[str] = []

    if not settings.database_url:
        errors.append("DATABASE_URL is required in non-dev environments.")

    if len(settings.secret_key) < SECRET_KEY_MIN_LENGTH:
        errors.append(
            f"SECRET_KEY must be at least {SECRET_KEY_MIN_LENGTH} characters "
            f"(got {len(settings.secret_key)}). "
            'Generate via: python -c "import secrets; print(secrets.token_hex(32))"'
        )

    if settings.auth_mode == "none":
        errors.append(
            "AUTH_MODE='none' is forbidden in staging and production. "
            "Set AUTH_MODE=jwt and provision JWT_PUBLIC_KEY / JWT_PRIVATE_KEY."
        )

    if not settings.database_tls_enabled:
        errors.append(
            "DATABASE_TLS_ENABLED must be true in non-dev environments. "
            "HIPAA Security Rule §164.312(e)(1) requires encryption in "
            "transit for PHI."
        )

    if not _is_valid_audit_key(settings.audit_key):
        errors.append(
            f"AUDIT_KEY must be a {AUDIT_KEY_EXPECTED_LENGTH}-character "
            "lowercase hex string (32 raw bytes). "
            'Generate via: python -c "import secrets; print(secrets.token_hex(32))"'
        )

    if not settings.pii_encryption_key:
        errors.append(
            "PII_ENCRYPTION_KEY is required in non-dev environments. "
            'Generate via: python -c "from cryptography.fernet import Fernet; '
            'print(Fernet.generate_key().decode())"'
        )

    if not settings.artifact_signing_key:
        errors.append(
            "ARTIFACT_SIGNING_KEY is required in non-dev environments and "
            "must be distinct from SECRET_KEY."
        )
    elif settings.artifact_signing_key == settings.secret_key:
        errors.append("ARTIFACT_SIGNING_KEY must be distinct from SECRET_KEY.")

    if errors:
        raise ConfigurationError(
            "Configuration validation failed for "
            f"ENVIRONMENT={settings.environment!r}:\n  - " + "\n  - ".join(errors)
        )


def _is_valid_audit_key(value: str) -> bool:
    """True if value is exactly 64 lowercase hex characters."""
    if len(value) != AUDIT_KEY_EXPECTED_LENGTH:
        return False
    return bool(_HEX_PATTERN.match(value))
