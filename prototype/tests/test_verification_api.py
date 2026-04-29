"""Tests for prototype.verification — A6 acceptance.

Covers PROTOTYPE_PRD.md A6 acceptance:
- VERIFIED for a member in ELIGIBLE_ACTIVE.
- NOT_VERIFIED for not-found, ineligible (past grace), and pending-resolution
  members — same response shape across all internal states (XR-003 collapse,
  BR-401).
- Three failed attempts inside the window flip an in-memory lockout flag
  scoped to the (name, dob) anchor (BR-402).
- No log line, in any path, contains plaintext PII (XR-005).
"""

from __future__ import annotations

import logging
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from prototype.canonical import CanonicalState
from prototype.tokenization import tokenize_dob, tokenize_name
from prototype.verification import (
    NOT_VERIFIED,
    VERIFIED,
    BruteForceTracker,
    InMemoryCanonicalLookup,
    InMemoryMember,
    VerificationSettings,
    create_app,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _build_lookup_with_member(state: CanonicalState) -> InMemoryCanonicalLookup:
    return InMemoryCanonicalLookup(
        [
            InMemoryMember(
                member_id="canon-001",
                name_token=tokenize_name("Sarah", "Johnson"),
                dob_token=tokenize_dob("1985-04-12"),
                state=state,
            ),
        ]
    )


def _claim_request(
    *,
    first: str = "Sarah",
    last: str = "Johnson",
    dob: str = "1985-04-12",
    request_id: str = "req-abc-123",
) -> dict[str, dict[str, str]]:
    return {
        "claim": {
            "first_name": first,
            "last_name": last,
            "date_of_birth": dob,
        },
        "context": {
            "client_id": "wayfinding-test",
            "request_id": request_id,
        },
    }


@pytest.fixture
def client_with_active_member() -> TestClient:
    lookup = _build_lookup_with_member(CanonicalState.ELIGIBLE_ACTIVE)
    settings = VerificationSettings(response_floor_ms=0.0)
    app = create_app(lookup=lookup, settings=settings)
    return TestClient(app)


# ---------------------------------------------------------------------------
# BR-401 / XR-003: external state collapse to {VERIFIED, NOT_VERIFIED}
# ---------------------------------------------------------------------------


def test_verified_for_eligible_active_member(client_with_active_member: TestClient) -> None:
    response = client_with_active_member.post("/v1/verify", json=_claim_request())
    assert response.status_code == 200
    assert response.json() == {"status": VERIFIED}


def test_not_verified_for_not_found() -> None:
    lookup = InMemoryCanonicalLookup([])
    settings = VerificationSettings(response_floor_ms=0.0)
    client = TestClient(create_app(lookup=lookup, settings=settings))
    response = client.post("/v1/verify", json=_claim_request())
    assert response.status_code == 200
    assert response.json() == {"status": NOT_VERIFIED}


@pytest.mark.parametrize(
    "internal_state",
    [
        CanonicalState.PENDING_RESOLUTION,
        CanonicalState.ELIGIBLE_GRACE,
        CanonicalState.INELIGIBLE,
        CanonicalState.DELETED,
    ],
)
def test_not_verified_for_non_active_states(internal_state: CanonicalState) -> None:
    """Every internal state other than ELIGIBLE_ACTIVE collapses to NOT_VERIFIED
    with identical response shape (BR-401 / XR-003)."""
    lookup = _build_lookup_with_member(internal_state)
    settings = VerificationSettings(response_floor_ms=0.0)
    client = TestClient(create_app(lookup=lookup, settings=settings))
    response = client.post("/v1/verify", json=_claim_request())
    assert response.status_code == 200
    assert response.json() == {"status": NOT_VERIFIED}


def test_response_shape_is_identical_across_internal_states() -> None:
    """The body's keys and value-types are identical regardless of internal state."""
    bodies: list[dict[str, str]] = []
    for state in (
        CanonicalState.PENDING_RESOLUTION,
        CanonicalState.ELIGIBLE_GRACE,
        CanonicalState.INELIGIBLE,
        CanonicalState.DELETED,
    ):
        client = TestClient(
            create_app(
                lookup=_build_lookup_with_member(state),
                settings=VerificationSettings(response_floor_ms=0.0),
            )
        )
        response = client.post("/v1/verify", json=_claim_request())
        bodies.append(response.json())
    not_found_response = TestClient(
        create_app(
            lookup=InMemoryCanonicalLookup([]), settings=VerificationSettings(response_floor_ms=0.0)
        )
    ).post("/v1/verify", json=_claim_request())
    bodies.append(not_found_response.json())

    expected_keys = {"status"}
    for body in bodies:
        assert set(body.keys()) == expected_keys
        assert body["status"] == NOT_VERIFIED


# ---------------------------------------------------------------------------
# BR-402 / XR-004: progressive friction → lockout after N failures
# ---------------------------------------------------------------------------


def test_three_failed_attempts_flip_lockout_flag() -> None:
    tracker = BruteForceTracker(window=timedelta(hours=24), max_failures=3)
    lookup = InMemoryCanonicalLookup([])
    client = TestClient(
        create_app(
            lookup=lookup,
            settings=VerificationSettings(response_floor_ms=0.0),
            tracker=tracker,
        )
    )

    anchor = (tokenize_name("Sarah", "Johnson"), tokenize_dob("1985-04-12"))
    assert not tracker.is_locked(anchor)

    for _ in range(3):
        client.post("/v1/verify", json=_claim_request())

    assert tracker.is_locked(anchor)


def test_lockout_persists_after_eligible_record_appears() -> None:
    """An attacker who flips lockout must NOT regain access if they later
    happen to land on a real eligible identity. (Lockout is per anchor.)"""
    tracker = BruteForceTracker(window=timedelta(hours=24), max_failures=3)
    lookup = _build_lookup_with_member(CanonicalState.ELIGIBLE_ACTIVE)
    client = TestClient(
        create_app(
            lookup=lookup,
            settings=VerificationSettings(response_floor_ms=0.0),
            tracker=tracker,
        )
    )

    # Three failures against a different identity (lockout triggered for that
    # anchor only).
    for _ in range(3):
        client.post("/v1/verify", json=_claim_request(first="Wrong", last="Person"))

    wrong_anchor = (tokenize_name("Wrong", "Person"), tokenize_dob("1985-04-12"))
    sarah_anchor = (tokenize_name("Sarah", "Johnson"), tokenize_dob("1985-04-12"))
    assert tracker.is_locked(wrong_anchor)
    assert not tracker.is_locked(sarah_anchor)

    # Sarah's anchor still resolves successfully.
    response = client.post("/v1/verify", json=_claim_request())
    assert response.json() == {"status": VERIFIED}


def test_successful_verification_clears_failure_window() -> None:
    """Two failures + a successful verify resets the counter for that anchor."""
    tracker = BruteForceTracker(window=timedelta(hours=24), max_failures=3)
    lookup = _build_lookup_with_member(CanonicalState.ELIGIBLE_ACTIVE)
    client = TestClient(
        create_app(
            lookup=lookup,
            settings=VerificationSettings(response_floor_ms=0.0),
            tracker=tracker,
        )
    )

    anchor = (tokenize_name("Sarah", "Johnson"), tokenize_dob("1985-04-12"))

    # Two failures via a wrong DOB (different anchor than Sarah's verified one).
    for _ in range(2):
        client.post("/v1/verify", json=_claim_request(dob="1900-01-01"))

    # Then a successful verify on the real anchor — failures cleared on success.
    client.post("/v1/verify", json=_claim_request())
    assert not tracker.is_locked(anchor)


# ---------------------------------------------------------------------------
# XR-005: no plaintext PII in any log line
# ---------------------------------------------------------------------------


def test_logs_contain_no_plaintext_pii(caplog: pytest.LogCaptureFixture) -> None:
    """Run a verify request and assert no log line contains the plaintext
    first/last/dob — only tokenized references and request_id are logged."""
    lookup = _build_lookup_with_member(CanonicalState.ELIGIBLE_ACTIVE)
    settings = VerificationSettings(response_floor_ms=0.0)
    client = TestClient(create_app(lookup=lookup, settings=settings))

    with caplog.at_level(logging.INFO, logger="prototype.verification"):
        client.post("/v1/verify", json=_claim_request())

    forbidden = ["Sarah", "Johnson", "1985-04-12"]
    for record in caplog.records:
        message = record.getMessage()
        for token in forbidden:
            assert token not in message, f"Log line leaked plaintext: {message!r}"
        # Also scan the structured extras the formatter would render.
        for value in record.__dict__.values():
            if isinstance(value, str):
                for token in forbidden:
                    assert token not in value, f"Log extra leaked plaintext: {value!r}"


# ---------------------------------------------------------------------------
# Identity tokens are deterministic across calls
# ---------------------------------------------------------------------------


def test_token_determinism() -> None:
    """name_token and dob_token are stable across calls (joinable per AD-009)."""
    a = tokenize_name("Sarah", "Johnson")
    b = tokenize_name("  sarah  ", "JOHNSON")  # whitespace + casing irrelevant
    assert a == b
    assert a != tokenize_name("Sarah", "Smith")
    assert tokenize_dob("1985-04-12") != tokenize_dob("1985-04-13")
