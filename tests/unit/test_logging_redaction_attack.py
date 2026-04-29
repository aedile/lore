"""Negative tests for the PII redaction processors.

These tests assert that PII does NOT appear in log output. Each test
captures the redacted event dict directly from the processor (not via
the renderer) so failures point at the redactor, not at downstream
serialization.

Per Rule 22, attack tests precede feature tests for any security-
critical primitive.
"""

from __future__ import annotations

import pytest

from lore_eligibility.bootstrapper.logging_config import (
    PII_KEYS,
    REDACTED_VALUE,
    redact_pii_keys,
    redact_pii_patterns,
)


# ---------------------------------------------------------------------------
# Key-based redaction — attack tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.attack
@pytest.mark.parametrize(
    "key",
    [
        "ssn",
        "SSN",
        "Social_Security_Number",
        "dob",
        "date_of_birth",
        "first_name",
        "last_name",
        "full_name",
        "address",
        "phone",
        "email",
        "member_id",
        "patient_id",
        "password",
        "api_key",
    ],
)
def test_redact_pii_keys_masks_known_field(key: str) -> None:
    """Every known PII key has its value replaced with the redaction marker."""
    event = {key: "value-that-must-not-leak"}
    out = redact_pii_keys(None, "info", event)
    assert out[key] == REDACTED_VALUE
    assert "value-that-must-not-leak" not in str(out)


@pytest.mark.unit
@pytest.mark.attack
def test_redact_pii_keys_handles_nested_mapping() -> None:
    """Nested PII keys one level deep are also redacted."""
    event = {
        "user": {
            "ssn": "123-45-6789",
            "tier": "platinum",
        }
    }
    out = redact_pii_keys(None, "info", event)
    assert out["user"]["ssn"] == REDACTED_VALUE
    assert out["user"]["tier"] == "platinum"
    assert "123-45-6789" not in str(out)


@pytest.mark.unit
@pytest.mark.attack
def test_redact_pii_keys_is_case_insensitive() -> None:
    """Capitalization variations are all caught."""
    event = {"FIRST_NAME": "Jane", "Last_Name": "Doe"}
    out = redact_pii_keys(None, "info", event)
    assert out["FIRST_NAME"] == REDACTED_VALUE
    assert out["Last_Name"] == REDACTED_VALUE
    assert "Jane" not in str(out)
    assert "Doe" not in str(out)


# ---------------------------------------------------------------------------
# Pattern-based redaction — attack tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.attack
@pytest.mark.parametrize(
    "ssn",
    [
        "123-45-6789",
        "987-65-4321",
        "555-12-3456",
    ],
)
def test_redact_pii_patterns_masks_hyphenated_ssn(ssn: str) -> None:
    """SSN with hyphens never appears verbatim in output."""
    event = {"event": f"user lookup completed for {ssn}", "trace_id": "abc"}
    out = redact_pii_patterns(None, "info", event)
    assert ssn not in out["event"]
    assert "***SSN***" in out["event"]
    assert out["trace_id"] == "abc"


@pytest.mark.unit
@pytest.mark.attack
def test_redact_pii_patterns_masks_email_in_message() -> None:
    """Email addresses interpolated into log messages are redacted."""
    event = {"event": "verification request from user@example.com failed"}
    out = redact_pii_patterns(None, "info", event)
    assert "user@example.com" not in out["event"]
    assert "***EMAIL***" in out["event"]
    assert "verification request from" in out["event"]


@pytest.mark.unit
@pytest.mark.attack
@pytest.mark.parametrize(
    "phone",
    [
        "555-123-4567",
        "(555) 123-4567",
        "+1 555-123-4567",
        "555.123.4567",
    ],
)
def test_redact_pii_patterns_masks_phone(phone: str) -> None:
    """US-shaped phone numbers are redacted in any common format."""
    event = {"event": f"contact attempted at {phone}"}
    out = redact_pii_patterns(None, "info", event)
    assert phone not in out["event"]
    assert "***PHONE***" in out["event"]


@pytest.mark.unit
@pytest.mark.attack
def test_redact_pii_patterns_masks_iso_dob() -> None:
    """ISO-formatted dates of birth are redacted."""
    event = {"event": "member born 1985-03-15 verified"}
    out = redact_pii_patterns(None, "info", event)
    assert "1985-03-15" not in out["event"]
    assert "***DATE***" in out["event"]


@pytest.mark.unit
@pytest.mark.attack
def test_redact_pii_patterns_handles_multiple_in_one_string() -> None:
    """Multiple PII tokens in the same string are all redacted."""
    event = {
        "event": "user user@example.com (SSN 123-45-6789) called 555-123-4567"
    }
    out = redact_pii_patterns(None, "info", event)
    assert "user@example.com" not in out["event"]
    assert "123-45-6789" not in out["event"]
    assert "555-123-4567" not in out["event"]
    assert out["event"].count("***") >= 6  # 3 redactions × 2 markers each


@pytest.mark.unit
@pytest.mark.attack
def test_redact_pii_patterns_leaves_non_string_values_alone() -> None:
    """Non-string values pass through pattern redaction unchanged."""
    event = {"count": 42, "ratio": 0.95, "flags": [1, 2, 3]}
    out = redact_pii_patterns(None, "info", event)
    assert out["count"] == 42
    assert out["ratio"] == 0.95
    assert out["flags"] == [1, 2, 3]


# ---------------------------------------------------------------------------
# Defense-in-depth: combining both processors
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.attack
def test_full_chain_redacts_both_keyed_and_patterned_pii() -> None:
    """Running both processors in sequence catches both PII channels."""
    event = {
        "ssn": "123-45-6789",  # caught by key
        "event": "lookup for jane@example.com",  # caught by pattern
        "trace_id": "ok-12345",  # untouched
    }
    keyed = redact_pii_keys(None, "info", event)
    patterned = redact_pii_patterns(None, "info", keyed)
    assert patterned["ssn"] == REDACTED_VALUE
    assert "jane@example.com" not in patterned["event"]
    assert "***EMAIL***" in patterned["event"]
    assert patterned["trace_id"] == "ok-12345"


# ---------------------------------------------------------------------------
# Coverage of PII_KEYS — tripwire if a key is added without a test
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_pii_keys_set_contains_minimum_required_fields() -> None:
    """Sanity check: PII_KEYS contains the case-prompt-required PII fields."""
    required = {"ssn", "dob", "first_name", "last_name", "address", "phone", "email", "member_id"}
    missing = required - PII_KEYS
    assert not missing, f"PII_KEYS is missing required fields: {missing}"
    assert len(PII_KEYS) >= len(required)
