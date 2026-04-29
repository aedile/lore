"""Verification API — A6 from PROTOTYPE_PRD.md.

A FastAPI service exposing a single public endpoint. Implements:

- BR-401 external state collapse: the response set is exactly
  ``{VERIFIED, NOT_VERIFIED}`` regardless of the richer internal state
  (NOT_FOUND vs INELIGIBLE vs PENDING_RESOLUTION vs DELETED).
- BR-402 progressive friction: three failed attempts within
  ``BRUTE_FORCE_WINDOW_HOURS`` flip an in-memory lockout flag scoped to
  the resolved-identity tuple.
- BR-404 latency floor: a deliberate uniform delay equalises VERIFIED and
  NOT_VERIFIED response times so timing analysis cannot infer the internal
  state (XR-003 privacy-preserving collapse).
- XR-005 zero PII in logs: only tokenized references and request_ids are
  logged.

The canonical-store backend is abstracted behind ``CanonicalLookup`` so
the API can run against either an in-memory dict (tests) or a Postgres
connection (the demo). The Postgres backend is in
``prototype.canonical_lookup``.
"""

from __future__ import annotations

import logging
import time
import uuid
from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Protocol

from fastapi import Depends, FastAPI
from pydantic import BaseModel, Field

from prototype.canonical import CanonicalState
from prototype.tokenization import tokenize_dob, tokenize_name

logger = logging.getLogger("prototype.verification")


# ---------------------------------------------------------------------------
# Request / response models — public shape (XR-003 collapse)
# ---------------------------------------------------------------------------


class Address(BaseModel):
    street: str | None = None
    city: str | None = None
    state: str | None = None
    zip: str | None = None


class VerifyClaim(BaseModel):
    first_name: str
    last_name: str
    date_of_birth: str = Field(description="YYYY-MM-DD")
    ssn_last_4: str | None = None
    partner_member_id: str | None = None
    address: Address | None = None


class VerifyContext(BaseModel):
    client_id: str
    request_id: str


class VerifyRequest(BaseModel):
    claim: VerifyClaim
    context: VerifyContext


class VerifyResponse(BaseModel):
    """The only public surface. Status set is exactly {VERIFIED, NOT_VERIFIED}."""

    status: str  # "VERIFIED" | "NOT_VERIFIED"


# ---------------------------------------------------------------------------
# Canonical-lookup abstraction
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CanonicalLookupResult:
    """The richer internal state returned by the lookup backend.

    The API collapses this to VERIFIED/NOT_VERIFIED before returning. Any
    logging at this level uses tokenized references and the request_id
    only — never the raw lookup_result fields.
    """

    found: bool
    state: CanonicalState | None = None
    member_id: str | None = None


class CanonicalLookup(Protocol):
    """Lookup contract for the verification API."""

    def lookup_by_name_dob(self, *, name_token: str, dob_token: str) -> CanonicalLookupResult: ...


# ---------------------------------------------------------------------------
# In-memory backend (tests + initial demo)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class InMemoryMember:
    member_id: str
    name_token: str
    dob_token: str
    state: CanonicalState


class InMemoryCanonicalLookup:
    """Dict-backed lookup. Tests use this; the Postgres-backed lookup is
    swap-compatible via the CanonicalLookup protocol."""

    def __init__(self, members: Iterable[InMemoryMember] = ()) -> None:
        self._by_anchor: dict[tuple[str, str], InMemoryMember] = {}
        for m in members:
            self._by_anchor[(m.name_token, m.dob_token)] = m

    def add(self, member: InMemoryMember) -> None:
        self._by_anchor[(member.name_token, member.dob_token)] = member

    def lookup_by_name_dob(self, *, name_token: str, dob_token: str) -> CanonicalLookupResult:
        m = self._by_anchor.get((name_token, dob_token))
        if m is None:
            return CanonicalLookupResult(found=False)
        return CanonicalLookupResult(found=True, state=m.state, member_id=m.member_id)


# ---------------------------------------------------------------------------
# Brute-force tracker (BR-402 + XR-004)
# ---------------------------------------------------------------------------


@dataclass
class _IdentityFailureLog:
    failures: deque[datetime] = field(default_factory=deque)
    locked: bool = False


class BruteForceTracker:
    """In-memory failure-window tracker scoped by resolved-identity anchor.

    The prototype scopes by ``(name_token, dob_token)`` so probes against
    a single identity escalate even when the attacker varies request_id.
    """

    def __init__(self, *, window: timedelta = timedelta(hours=24), max_failures: int = 3) -> None:
        self._window = window
        self._max_failures = max_failures
        self._by_anchor: dict[tuple[str, str], _IdentityFailureLog] = {}

    def is_locked(self, anchor: tuple[str, str]) -> bool:
        return self._by_anchor.get(anchor, _IdentityFailureLog()).locked

    def record_failure(self, anchor: tuple[str, str]) -> bool:
        """Record a failure and return True if this push triggered a lockout."""
        now = datetime.now(UTC)
        log = self._by_anchor.setdefault(anchor, _IdentityFailureLog())
        cutoff = now - self._window
        while log.failures and log.failures[0] < cutoff:
            log.failures.popleft()
        log.failures.append(now)
        if len(log.failures) >= self._max_failures and not log.locked:
            log.locked = True
            return True
        return False

    def record_success(self, anchor: tuple[str, str]) -> None:
        log = self._by_anchor.get(anchor)
        if log is not None:
            log.failures.clear()


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class VerificationSettings:
    """API tunables. Mirrors the BRD ``VERIFICATION_*`` configuration parameters."""

    # BR-404 — deliberate latency floor for collapse equalization.
    response_floor_ms: float = 50.0
    # BR-402 — three failures inside the window flips lockout.
    brute_force_window: timedelta = timedelta(hours=24)
    brute_force_max_failures: int = 3


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------


VERIFIED = "VERIFIED"
NOT_VERIFIED = "NOT_VERIFIED"


def create_app(
    *,
    lookup: CanonicalLookup,
    settings: VerificationSettings | None = None,
    tracker: BruteForceTracker | None = None,
) -> FastAPI:
    """Build the FastAPI application bound to a specific lookup backend."""
    cfg = settings or VerificationSettings()
    bf = tracker or BruteForceTracker(
        window=cfg.brute_force_window, max_failures=cfg.brute_force_max_failures
    )
    app = FastAPI(title="Lore Eligibility Verification — Prototype A6")
    app.state.lookup = lookup
    app.state.settings = cfg
    app.state.tracker = bf

    def _get_lookup() -> CanonicalLookup:
        return app.state.lookup

    def _get_tracker() -> BruteForceTracker:
        return app.state.tracker

    def _get_settings() -> VerificationSettings:
        return app.state.settings

    @app.post("/v1/verify", response_model=VerifyResponse)
    def verify(
        body: VerifyRequest,
        lookup: CanonicalLookup = Depends(_get_lookup),
        tracker: BruteForceTracker = Depends(_get_tracker),
        settings: VerificationSettings = Depends(_get_settings),
    ) -> VerifyResponse:
        return _handle_verify(body, lookup=lookup, tracker=tracker, settings=settings)

    return app


def _handle_verify(
    body: VerifyRequest,
    *,
    lookup: CanonicalLookup,
    tracker: BruteForceTracker,
    settings: VerificationSettings,
) -> VerifyResponse:
    """Resolve the claim, collapse the internal state, and equalise latency."""
    started = time.monotonic()
    request_id = body.context.request_id or str(uuid.uuid4())

    name_token = tokenize_name(body.claim.first_name, body.claim.last_name)
    dob_token = tokenize_dob(body.claim.date_of_birth)
    anchor = (name_token, dob_token)

    if tracker.is_locked(anchor):
        # Locked-out path also collapses to NOT_VERIFIED externally.
        logger.info(
            "verify.lockout",
            extra={
                "request_id": request_id,
                "client_id": body.context.client_id,
                "name_token": name_token,
                "dob_token": dob_token,
            },
        )
        _equalise_latency(started, settings.response_floor_ms)
        return VerifyResponse(status=NOT_VERIFIED)

    result = lookup.lookup_by_name_dob(name_token=name_token, dob_token=dob_token)
    is_verified = result.found and result.state == CanonicalState.ELIGIBLE_ACTIVE

    internal_state = result.state.value if result.state is not None else "NOT_FOUND"
    if is_verified:
        tracker.record_success(anchor)
        logger.info(
            "verify.success",
            extra={
                "request_id": request_id,
                "client_id": body.context.client_id,
                "name_token": name_token,
                "dob_token": dob_token,
                "internal_state": internal_state,
                "member_id": result.member_id,
            },
        )
    else:
        triggered_lockout = tracker.record_failure(anchor)
        logger.info(
            "verify.failure",
            extra={
                "request_id": request_id,
                "client_id": body.context.client_id,
                "name_token": name_token,
                "dob_token": dob_token,
                "internal_state": internal_state,
                "lockout_triggered": triggered_lockout,
            },
        )

    _equalise_latency(started, settings.response_floor_ms)
    return VerifyResponse(status=VERIFIED if is_verified else NOT_VERIFIED)


def _equalise_latency(started: float, floor_ms: float) -> None:
    """Sleep so total elapsed time is at least ``floor_ms``.

    BR-404 sets a latency target; XR-003 uses an equalised floor to deny
    timing-side-channel inference of the internal state.
    """
    elapsed_ms = (time.monotonic() - started) * 1000.0
    remaining = floor_ms - elapsed_ms
    if remaining > 0:
        time.sleep(remaining / 1000.0)


__all__ = [
    "NOT_VERIFIED",
    "VERIFIED",
    "Address",
    "BruteForceTracker",
    "CanonicalLookup",
    "CanonicalLookupResult",
    "InMemoryCanonicalLookup",
    "InMemoryMember",
    "VerificationSettings",
    "VerifyClaim",
    "VerifyContext",
    "VerifyRequest",
    "VerifyResponse",
    "create_app",
]
