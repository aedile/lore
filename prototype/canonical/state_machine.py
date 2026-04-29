"""Canonical-member state machine — BR-202 enforcement.

The state machine is application-level (not enforced via DB trigger) per the
ARD's deliberate choice: keeping it in code makes the transition table
testable in isolation. Every transition that mutates ``canonical_member.state``
must route through this module so violations raise rather than silently
update.

States and the allowed-transition table are defined directly from BRD §BR-201
and §BR-202.
"""

from __future__ import annotations

from enum import StrEnum


class CanonicalState(StrEnum):
    """States enumerated by BR-201."""

    PENDING_RESOLUTION = "PENDING_RESOLUTION"
    ELIGIBLE_ACTIVE = "ELIGIBLE_ACTIVE"
    ELIGIBLE_GRACE = "ELIGIBLE_GRACE"
    INELIGIBLE = "INELIGIBLE"
    DELETED = "DELETED"


# BR-202 transition table. Key is the FROM state (or None for initial creation
# from no prior state); value is the set of allowed TO states.
ALLOWED_TRANSITIONS: dict[CanonicalState | None, frozenset[CanonicalState]] = {
    None: frozenset(
        {
            CanonicalState.PENDING_RESOLUTION,
            CanonicalState.ELIGIBLE_ACTIVE,
        }
    ),
    CanonicalState.PENDING_RESOLUTION: frozenset(
        {
            CanonicalState.ELIGIBLE_ACTIVE,
            CanonicalState.DELETED,
        }
    ),
    CanonicalState.ELIGIBLE_ACTIVE: frozenset(
        {
            CanonicalState.ELIGIBLE_GRACE,
            CanonicalState.DELETED,
        }
    ),
    CanonicalState.ELIGIBLE_GRACE: frozenset(
        {
            CanonicalState.ELIGIBLE_ACTIVE,
            CanonicalState.INELIGIBLE,
            CanonicalState.DELETED,
        }
    ),
    CanonicalState.INELIGIBLE: frozenset(
        {
            CanonicalState.ELIGIBLE_ACTIVE,
            CanonicalState.DELETED,
        }
    ),
    CanonicalState.DELETED: frozenset(),  # terminal: no outbound transitions
}


class ForbiddenTransitionError(Exception):
    """Raised when a transition is not in the BR-202 allowed table."""

    def __init__(self, from_state: CanonicalState | None, to_state: CanonicalState) -> None:
        self.from_state = from_state
        self.to_state = to_state
        super().__init__(f"Forbidden state transition: {from_state} -> {to_state}")


def assert_transition_allowed(
    from_state: CanonicalState | None,
    to_state: CanonicalState,
) -> None:
    """Raise ``ForbiddenTransitionError`` if (from, to) is not in BR-202.

    ``from_state=None`` represents creation from no prior state.
    """
    allowed = ALLOWED_TRANSITIONS.get(from_state, frozenset())
    if to_state not in allowed:
        raise ForbiddenTransitionError(from_state, to_state)
