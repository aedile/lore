"""Security primitives — HMAC signing, audit log, PII tokenization, key manager.

Modules in this package are mutation-tested (mutmut) with a 60% kill-rate
threshold per CONSTITUTION Priority 4. Adding a module here requires
adding a corresponding test file under tests/unit/ that exercises the
security-critical paths.
"""
