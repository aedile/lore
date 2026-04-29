"""Cross-cutting infrastructure shared by 2+ modules.

Contains: HMAC signing, audit log, settings constants, exception types,
PII tokenization (under shared/security/), telemetry helpers.

Boundary contract (enforced by import-linter):
- shared/ MUST NOT import from modules/ or bootstrapper/
"""
