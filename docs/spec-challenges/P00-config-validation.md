# Spec Challenge — Production Config Validation (T0.9)

| Field | Value |
|-------|-------|
| **Phase** | Phase 00 (governance / harness hardening) |
| **Task** | T0.9 — DATABASE_TLS + production config startup validation |
| **Date** | 2026-04-29 |

---

## Original spec

Add a `validate_settings()` function called from `create_app()` that fails
fast in staging / production when:

- `DATABASE_URL` is empty
- `SECRET_KEY` is shorter than 32 chars
- `AUTH_MODE == 'none'`
- `DATABASE_TLS_ENABLED == false`
- `AUDIT_KEY` is not 64 lowercase hex chars
- `PII_ENCRYPTION_KEY` is empty
- `ARTIFACT_SIGNING_KEY` is empty
- `ARTIFACT_SIGNING_KEY == SECRET_KEY` (must be distinct)

Dev environment is exempted (loose defaults are intentional for local
work and tests).

---

## Missing acceptance criteria

1. **Multiple violations must be reported together.** A user staging an
   environment with three issues should see all three at once, not
   fix-and-rerun three times.
2. **The error message must include remediation hints.** "SECRET_KEY too
   short" without telling the operator how to generate one is hostile.
   Include the generation command in the error.
3. **The HIPAA citation must be in the message.** The TLS rule, in
   particular, is grounded in HIPAA Security Rule §164.312(e)(1).
   Including the citation in the error message helps operators
   understand the *why*, not just the *what*.
4. **The validator must not import from `bootstrapper/main.py`** (would
   create a circular import). It can import from `settings.py` and
   `shared/errors.py` only.
5. **The validator must work with an empty .env file** (Settings is
   loaded from `_env_file=None` in tests). Don't rely on .env being
   present.

## Negative test cases (attack tests)

Each must be an independent test so failures point at the specific
rule that broke:

- `test_dev_environment_skips_validation_with_empty_config` — dev is
  loose
- `test_production_with_complete_config_passes` — happy path
- `test_staging_environment_is_enforced` — staging uses the same
  rules as production
- `test_production_with_database_tls_disabled_fails` — HIPAA TLS rule
- `test_production_with_auth_mode_none_fails` — auth required outside
  dev
- `test_production_with_short_secret_key_fails` — minimum length
- `test_production_with_empty_database_url_fails` — required in non-dev
- `test_production_with_empty_pii_encryption_key_fails` — required
- `test_production_with_wrong_length_audit_key_fails` — exact 64 chars
- `test_production_with_non_hex_audit_key_fails` — content shape
- `test_production_with_signing_key_equal_to_secret_key_fails` — must
  be distinct
- `test_production_with_multiple_violations_reports_all` — all-at-once
  reporting

## Attack vectors

1. **Operator forgets to set DATABASE_TLS_ENABLED in production.**
   Defaults to false in env.example so a fresh `.env` would fail. The
   validator catches this; logging warning alone (which is what the
   .env.example previously documented) was insufficient.
2. **Operator copy-pastes SECRET_KEY into ARTIFACT_SIGNING_KEY.** The
   validator detects equality and refuses to start.
3. **Operator forgets to convert hex output (64 chars) to bytes
   somewhere.** AUDIT_KEY length is checked exactly, so a 32-char
   accidental truncation or a non-hex character fails.
4. **AUTH_MODE=none accidentally promoted from dev to staging.** The
   validator refuses to start in staging or production.

## Out of scope (deferred)

- JWT key validation (length, format, presence). The validator does
  NOT check `JWT_PUBLIC_KEY` / `JWT_PRIVATE_KEY` because the JWT
  primitive itself is not yet implemented. When JWT auth lands, those
  checks belong here too.
- Cross-key entropy/uniqueness audit. Out of scope for v1.
- Vault-side key rotation grace period validation. Out of scope until
  the vault primitive lands.
