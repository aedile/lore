"""Bootstrapper — API wiring, dependency injection, middleware, settings, lifespan.

Modules under bootstrapper/ are responsible for application startup and
cross-cutting infrastructure. Domain logic lives under
``lore_eligibility.modules``; cross-module utilities live under
``lore_eligibility.shared``.

Boundary contract (enforced by import-linter):
- ``modules/`` and ``shared/`` MUST NOT import from ``bootstrapper/``
- ``shared/`` MUST NOT import from ``modules/`` or ``bootstrapper/``
"""
