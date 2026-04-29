"""Project exception hierarchy.

Module-specific exceptions inherit from these base classes so that
upstream handlers can pattern-match on category rather than concrete type.
"""

from __future__ import annotations


class LoreEligibilityError(Exception):
    """Base class for all project-raised exceptions."""


class ConfigurationError(LoreEligibilityError):
    """Raised when configuration is missing or invalid at startup."""


class DataIntegrityError(LoreEligibilityError):
    """Raised when an invariant on stored or in-flight data is violated."""


class IdentityResolutionError(LoreEligibilityError):
    """Raised when identity resolution cannot produce a defensible match."""
