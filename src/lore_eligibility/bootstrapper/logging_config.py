"""Structured logging configuration with two-layer PII redaction.

CONSTITUTION Priority 0 (HIPAA / PHI handling): PII fields MUST NOT
appear in log output. This module configures structlog with two
redacting processors that run BEFORE any renderer:

1. ``redact_pii_keys`` — drops values for any event-dict key whose name
   matches a known PII field (ssn, dob, first_name, last_name,
   full_name, address, phone, email, member_id, etc.).
2. ``redact_pii_patterns`` — replaces SSN-shaped, phone-shaped, and
   email-shaped substrings inside any string value (including the
   event message itself), catching cases where developers interpolate
   PII into a log message rather than passing it as a structured key.

Both processors are applied together — defense in depth. Neither is
sufficient alone:

- Key-based catches ``logger.info("fetched", ssn=record.ssn)`` but not
  ``logger.info(f"fetched user with SSN {record.ssn}")``.
- Pattern-based catches the f-string case but cannot catch a
  non-pattern-matching PII field (full name, partial address) when
  passed structurally.

To extend coverage, add new keys to ``PII_KEYS`` or new patterns to
``PII_PATTERNS`` rather than working around the redactor.
"""

from __future__ import annotations

import logging
import re
import sys
from collections.abc import Mapping, MutableMapping
from re import Pattern
from typing import Any

import structlog

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

#: Event-dict keys whose values are always redacted. Comparison is case-
#: insensitive. Add new keys here when introducing new PII-bearing fields.
PII_KEYS: frozenset[str] = frozenset(
    {
        # Identity
        "ssn",
        "social_security_number",
        "social_security",
        "tin",
        "ein",
        # Demographics
        "dob",
        "date_of_birth",
        "birth_date",
        "birthdate",
        "first_name",
        "last_name",
        "full_name",
        "fname",
        "lname",
        "name",
        "given_name",
        "family_name",
        "middle_name",
        # Contact
        "address",
        "street",
        "street_address",
        "home_address",
        "mailing_address",
        "city",
        "zip",
        "zip_code",
        "postal_code",
        "phone",
        "phone_number",
        "telephone",
        "mobile",
        "email",
        "email_address",
        # Healthcare identifiers
        "member_id",
        "patient_id",
        "subscriber_id",
        "medicare_id",
        "mbi",
        "hicn",
        # Credentials (defense in depth — gitleaks/bandit catch these
        # statically, but the runtime safety net is cheap)
        "password",
        "secret",
        "token",
        "api_key",
        "auth_token",
        "session_id",
    }
)

#: Marker substituted in place of a redacted value.
REDACTED_VALUE: str = "***REDACTED***"

#: Regex patterns matched against string values. Each pattern is paired
#: with a marker that replaces every match.
PII_PATTERNS: tuple[tuple[Pattern[str], str], ...] = (
    # SSN: 9 digits with optional hyphens. The leading word boundary plus
    # the structure prevents false positives on long numeric IDs.
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "***SSN***"),
    (re.compile(r"\b\d{9}\b(?=\D|$)"), "***SSN-OR-LONG-DIGIT***"),
    # Phone (US-shaped): 10 digits with optional country code, parens,
    # spaces, dots, hyphens.
    (
        re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}\b"),
        "***PHONE***",
    ),
    # Email
    (
        re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+\b"),
        "***EMAIL***",
    ),
    # Date of birth (YYYY-MM-DD or MM/DD/YYYY) — defensive only; structured
    # logging via the ``dob`` key is the better channel and is caught by
    # the key-based redactor.
    (
        re.compile(r"\b(?:19|20)\d{2}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])\b"),
        "***DATE***",
    ),
)


# ---------------------------------------------------------------------------
# Processors
# ---------------------------------------------------------------------------


def redact_pii_keys(
    _logger: Any,
    _method_name: str,
    event_dict: MutableMapping[str, Any],
) -> MutableMapping[str, Any]:
    """Redact values whose key matches a known PII field name.

    Walks the event dict (including one level of nested mappings) and
    replaces any value whose key is in ``PII_KEYS`` with
    ``REDACTED_VALUE``. Match is case-insensitive.

    Args:
        _logger: The bound logger (unused; required by structlog
            processor signature).
        _method_name: The logging method name (unused).
        event_dict: The event dict being assembled. Mutated in place.

    Returns:
        The same event_dict, with PII values replaced.
    """
    for key in list(event_dict.keys()):
        if key.lower() in PII_KEYS:
            event_dict[key] = REDACTED_VALUE
            continue
        value = event_dict[key]
        if isinstance(value, Mapping):
            event_dict[key] = {
                inner_key: (REDACTED_VALUE if inner_key.lower() in PII_KEYS else inner_value)
                for inner_key, inner_value in value.items()
            }
    return event_dict


def redact_pii_patterns(
    _logger: Any,
    _method_name: str,
    event_dict: MutableMapping[str, Any],
) -> MutableMapping[str, Any]:
    """Redact PII-shaped substrings inside string values.

    Applies every pattern in ``PII_PATTERNS`` to every string value in
    the event dict (including the event message itself). Order of
    patterns matters: the SSN pattern with hyphens runs first so it
    wins over the bare 9-digit pattern.

    Non-string values (int, dict, list, etc.) are left untouched —
    structured PII passing should be caught by ``redact_pii_keys``.

    Args:
        _logger: Unused.
        _method_name: Unused.
        event_dict: The event dict being assembled. Mutated in place.

    Returns:
        The same event_dict, with PII patterns replaced.
    """
    for key, value in event_dict.items():
        if not isinstance(value, str):
            continue
        for pattern, marker in PII_PATTERNS:
            value = pattern.sub(marker, value)
        event_dict[key] = value
    return event_dict


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------


def configure_logging(
    level: int = logging.INFO,
    *,
    json_format: bool = True,
) -> None:
    """Configure structlog with PII redaction in the processor chain.

    Idempotent: safe to call multiple times (e.g. from create_app()
    and from a test fixture).

    Args:
        level: Minimum log level. Levels below this are dropped.
        json_format: If True, emit JSON (production / containerized).
            If False, emit human-readable console output (local dev).
    """
    # stdlib logging is the underlying handler; route to stderr so log
    # output does not pollute application stdout.
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stderr,
        level=level,
    )

    renderer: Any = (
        structlog.processors.JSONRenderer()
        if json_format
        else structlog.dev.ConsoleRenderer(colors=True)
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            # PII redactors MUST run before any renderer so the
            # redacted values are what get serialized.
            redact_pii_keys,
            redact_pii_patterns,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Return a structlog logger bound to ``name``.

    Args:
        name: Logger name (typically ``__name__``).

    Returns:
        A structlog BoundLogger configured with PII redaction.
    """
    return structlog.get_logger(name)
