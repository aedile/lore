"""Exhaustive BR-202 transition-pair tests.

Enumerates every (from_state, to_state) pair drawn from {None} ∪ States × States
and verifies that ``assert_transition_allowed`` matches the BR-202 table
exactly. The set of allowed transitions is hard-coded from BRD §BR-202 so a
drift in either direction (allowed becoming forbidden or vice versa) fails
loudly here.
"""

from __future__ import annotations

import pytest

from prototype.canonical import (
    ALLOWED_TRANSITIONS,
    CanonicalState,
    ForbiddenTransitionError,
    assert_transition_allowed,
)

# Hard-coded allowed transitions, lifted directly from BRD §BR-202.
# Pair format: (from_state | None, to_state).
EXPECTED_ALLOWED: set[tuple[CanonicalState | None, CanonicalState]] = {
    (None, CanonicalState.PENDING_RESOLUTION),
    (None, CanonicalState.ELIGIBLE_ACTIVE),
    (CanonicalState.PENDING_RESOLUTION, CanonicalState.ELIGIBLE_ACTIVE),
    (CanonicalState.PENDING_RESOLUTION, CanonicalState.DELETED),
    (CanonicalState.ELIGIBLE_ACTIVE, CanonicalState.ELIGIBLE_GRACE),
    (CanonicalState.ELIGIBLE_ACTIVE, CanonicalState.DELETED),
    (CanonicalState.ELIGIBLE_GRACE, CanonicalState.ELIGIBLE_ACTIVE),
    (CanonicalState.ELIGIBLE_GRACE, CanonicalState.INELIGIBLE),
    (CanonicalState.ELIGIBLE_GRACE, CanonicalState.DELETED),
    (CanonicalState.INELIGIBLE, CanonicalState.ELIGIBLE_ACTIVE),
    (CanonicalState.INELIGIBLE, CanonicalState.DELETED),
}

ALL_FROM_STATES: list[CanonicalState | None] = [None, *list(CanonicalState)]
ALL_TO_STATES: list[CanonicalState] = list(CanonicalState)


@pytest.mark.parametrize("from_state", ALL_FROM_STATES)
@pytest.mark.parametrize("to_state", ALL_TO_STATES)
def test_transition_pair_matches_br_202(
    from_state: CanonicalState | None,
    to_state: CanonicalState,
) -> None:
    """Every (from, to) pair must match the BR-202 expected-allowed set."""
    pair = (from_state, to_state)
    if pair in EXPECTED_ALLOWED:
        # Should not raise.
        assert_transition_allowed(from_state, to_state)
    else:
        with pytest.raises(ForbiddenTransitionError) as exc_info:
            assert_transition_allowed(from_state, to_state)
        assert exc_info.value.from_state == from_state
        assert exc_info.value.to_state == to_state


def test_deleted_is_terminal() -> None:
    """No transition out of DELETED is allowed (right-to-deletion is final)."""
    for to_state in CanonicalState:
        with pytest.raises(ForbiddenTransitionError):
            assert_transition_allowed(CanonicalState.DELETED, to_state)


def test_allowed_transitions_table_has_expected_states() -> None:
    """The table covers every CanonicalState plus the None initial state."""
    expected_keys: set[CanonicalState | None] = {None, *CanonicalState}
    assert set(ALLOWED_TRANSITIONS.keys()) == expected_keys


def test_allowed_transitions_table_matches_br_202() -> None:
    """Cross-check: the table's allowed pairs equal EXPECTED_ALLOWED."""
    flattened: set[tuple[CanonicalState | None, CanonicalState]] = {
        (from_state, to_state)
        for from_state, to_set in ALLOWED_TRANSITIONS.items()
        for to_state in to_set
    }
    assert flattened == EXPECTED_ALLOWED


def test_forbidden_transition_error_carries_states() -> None:
    """The exception preserves both endpoints for diagnostic logging."""
    with pytest.raises(ForbiddenTransitionError) as exc_info:
        assert_transition_allowed(CanonicalState.ELIGIBLE_ACTIVE, CanonicalState.PENDING_RESOLUTION)
    assert exc_info.value.from_state == CanonicalState.ELIGIBLE_ACTIVE
    assert exc_info.value.to_state == CanonicalState.PENDING_RESOLUTION
    assert "PENDING_RESOLUTION" in str(exc_info.value)


def test_initial_creation_to_intermediate_state_forbidden() -> None:
    """A newly-created member cannot start in INELIGIBLE, ELIGIBLE_GRACE, or DELETED."""
    for forbidden_initial in (
        CanonicalState.ELIGIBLE_GRACE,
        CanonicalState.INELIGIBLE,
        CanonicalState.DELETED,
    ):
        with pytest.raises(ForbiddenTransitionError):
            assert_transition_allowed(None, forbidden_initial)
