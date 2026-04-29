"""Vulture whitelist — declare names that vulture should treat as used.

Bare identifiers reference attributes/functions whose use is not visible
to vulture's static analysis (e.g. FastAPI route decorators, pydantic
model attributes accessed via .model_dump(), pytest fixtures resolved by
name at runtime).

Each entry should be commented with the runtime call site.
"""

# noqa: F821, B018, E501  — bare identifiers are intentional

# Placeholder — populated as vulture flags false positives.
