# HIPAA Posture — Control Inventory

This document is the single source of truth for *which HIPAA-relevant
controls are enforced today*, *which are scaffolded but not yet
active*, and *which are deferred to specific upcoming phases*.

The harness has many configured-but-not-enforced controls. Reading
`.env.example` plus `CONSTITUTION.md` can give the false impression that
redaction, audit, tokenization, and key-rotation primitives are all
live. This inventory keeps that perception aligned with reality.

**Status legend:**

- **LIVE** — actively enforced today; failing the control fails CI or
  startup.
- **STUBBED** — primitive exists but is empty / vacuously passing;
  the gate is wired and will activate when the primitive contains code.
- **CONFIGURED-ONLY** — environment variable or constant exists but
  no code consumes it yet; presence on disk is not enforcement.
- **DEFERRED to Phase NN** — not yet started; named in the roadmap
  with the phase that owns it.
- **NOT-APPLICABLE** — out of scope for v1 (e.g. physical safeguards
  for a software project).

Each row cites the BRD or HIPAA Security Rule clause that owns it.

---

## HIPAA Security Rule — Technical Safeguards

### §164.312(a)(1) Access Control

| Control | Status | Where | Activation |
|---|---|---|---|
| Authentication required on all non-exempt routes | **STUBBED** | `tests/unit/test_auth_coverage.py` introspects `app.routes`; `AUTH_EXEMPT_ROUTES` declares the public set. Today only `/health` exists and is exempt — vacuous pass. The `get_current_operator` dependency itself doesn't exist yet. | Activates as soon as the first non-exempt route is added. ARD (Phase 02) decides the JWT integration. |
| `AUTH_MODE='none'` forbidden in non-dev | **LIVE** | `bootstrapper/config_validation.py::validate_settings` raises `ConfigurationError` at app startup if `ENVIRONMENT in {staging, production}` and `AUTH_MODE='none'`. | Now. |
| Role taxonomy (BR-505/506: 7 roles, residency-bound PII access) | **DEFERRED to Phase 02 (ARD) / Phase 03+** | BRD §"Role Taxonomy" specifies. No implementation. | After ARD decides RBAC mechanism. |
| Session management / token rotation | **DEFERRED** | Not started. | When auth primitive is implemented. |

### §164.312(b) Audit Controls

| Control | Status | Where | Activation |
|---|---|---|---|
| Audit log primitive | **STUBBED** | `shared/security/` is empty. `AUDIT_KEY` env var is required in non-dev (validator catches missing) but no code emits audit events yet. | Phase 03+ when the audit-event-bus is authored. Per BR-501 the system must emit events for 12 classes. |
| Hash-chained audit integrity (BR-504) | **DEFERRED to Phase 03+** | No impl. | After audit primitive lands. |
| Append-only audit access (BR-504) | **DEFERRED** | No DB schema yet. | First migration that creates the audit_log table. |
| 7-year retention for PII access events (BR-503) | **CONFIGURED-ONLY** | `AUDIT_RETENTION_DAYS=2555` in `.env.example`. No retention enforcement job exists. | When the retention/erasure pipeline is authored (Phase 03+). |

### §164.312(c)(1) Integrity

| Control | Status | Where | Activation |
|---|---|---|---|
| Artifact signing (HMAC / Ed25519) | **STUBBED** | `ARTIFACT_SIGNING_KEY` env required; validator checks distinct from `SECRET_KEY`. No signing primitive yet. | Phase 03+ when curated artifacts (eligibility snapshots, identity-resolution outputs) start being exported. |
| Mutation testing on security-critical code | **STUBBED** | `mutmut` configured to target `shared/security/` and `bootstrapper/auth.py` with 60%/50% kill-rate thresholds. Both targets empty — vacuously passes today. | Activates when the first security primitive is committed. |
| Schema drift detection (BR-304) | **DEFERRED to Phase 03+** | Named in BRD. No impl. | When ingestion pipeline is authored. |

### §164.312(d) Person or Entity Authentication

| Control | Status | Where | Activation |
|---|---|---|---|
| JWT authentication | **DEFERRED** | `JWT_PUBLIC_KEY` / `JWT_PRIVATE_KEY` env vars exist. `auth_mode` setting exists. No `bootstrapper/auth.py` impl. | ARD (Phase 02) decides JWT vs OIDC; impl follows. |
| Brute force lockout (BR-402: 3-tier progressive) | **DEFERRED to Phase 03+** | Named in BRD. `AUTH_BRUTE_FORCE_*` env vars exist. No impl. | When verification API is authored. |
| Identity-scoped rate limits (XR-004) | **DEFERRED** | `RATE_LIMIT_REQUESTS_PER_MINUTE` env var exists. No middleware. | Phase 03+. |

### §164.312(e)(1) Transmission Security

| Control | Status | Where | Activation |
|---|---|---|---|
| TLS in transit on database (`DATABASE_TLS_ENABLED`) | **LIVE** | `bootstrapper/config_validation.py` raises `ConfigurationError` at startup if `DATABASE_TLS_ENABLED=false` in staging/production. Cited HIPAA reference in the error message. | Now. Tested in `tests/unit/test_config_validation.py::test_production_with_database_tls_disabled_fails`. |
| HTTPS redirect (T8.1 in `.env.example`) | **CONFIGURED-ONLY** | `HTTPS_REDIRECT_ENABLED` env var exists. No middleware. | Phase 03+ when reverse proxy is in front of the app. |
| mTLS between services | **NOT-APPLICABLE for v1** | ADR-0001 explicitly skipped the mTLS variant. | Reintroduce if Phase 03+ adds inter-service traffic that warrants it. |

---

## BRD-Specific Cross-Cutting Rules

| Rule | Status | Where | Activation |
|---|---|---|---|
| **XR-001** — Layered configurability of every threshold | **DEFERRED to Phase 03+** | No CI lint scanning for inline literals matching config-parameter names. | First domain feature that introduces a threshold. |
| **XR-002** — No magic numbers | **DEFERRED** | No CI lint. Tied to XR-001. | Same as XR-001. |
| **XR-003** — Privacy-preserving collapse on public surfaces | **DEFERRED to Phase 03+** | No public-facing routes yet. | When verification API is authored. |
| **XR-004** — Identity-scoped lockouts | **DEFERRED** | See §164.312(d) row. | Phase 03+. |
| **XR-005** — Zero PII / PHI in logs | **LIVE** | `bootstrapper/logging_config.py` configures structlog with two redaction processors: `redact_pii_keys` (drops PII-named fields) and `redact_pii_patterns` (regex-redacts SSN / phone / email / DOB shapes in any string value, including the event message). Tested in `tests/unit/test_logging_redaction_attack.py` (12 attack tests, parametrized). | Now. |
| **XR-005(a)** — PII-in-test-fixtures CI gate | **LIVE** | `scripts/check_pii_in_fixtures.py` runs in pre-commit and ci-local. Scans `tests/fixtures/`, `tests/integration/`, `sample_data/` for SSN/phone/email/DOB shapes. Per-line opt-out via `# pii-allowed: <reason>`. | Now. |
| **XR-005(b)** — Production log sampling job | **DEFERRED** | Named in BRD enforcement. No job. | Phase 03+ once the app emits real logs in a deployed environment. |
| **XR-006** — Irreversibility separation | **DEFERRED to Phase 03+** | No state-mutating operations yet. | First mutating operation (e.g. deletion, vault purge). |

---

## Operational / Supply Chain

| Control | Status | Where | Activation |
|---|---|---|---|
| **Branch protection on `main`** | **NOT ENABLED — FINDING** | `gh api repos/aedile/lore/branches/main/protection` returns HTTP 404 ("Branch not protected"). CONSTITUTION assumes branch protection is on. | **REMEDIATION REQUIRED**: enable in GitHub Settings → Branches → Add rule for `main`. Recommended: require PR before merge, require linear history, require status checks (CI), include administrators. |
| Secrets scanning (gitleaks) | **LIVE** | Pre-commit hook + CI job. | Now. |
| Secrets scanning (detect-secrets baseline) | **LIVE on hook, baseline must be regenerated on first install** | `.secrets.baseline` was authored by hand for the bootstrap commit; `detect-secrets scan > .secrets.baseline` should run once on first install to produce a tool-canonical baseline. | First `poetry install` + `pre-commit install`. |
| Dependency vulnerability scanning (pip-audit) | **LIVE** | `scripts/pip-audit.sh` runs in ci-local and CI. | Now. |
| Container image scanning (Trivy / SBOM) | **DEFERRED** | ADR-0001 explicitly skipped Trivy / SBOM CI jobs until there is a real Docker image to scan. | Phase 03+ once domain code is shipping. |
| Dockerfile HEALTHCHECK | **LIVE** | Dockerfile uses Python `urllib` to hit `/health` every 30s; 3 retries before unhealthy. | Now. |
| `make merge-pr` audit-logged merge | **STUBBED** | `scripts/merge-pr.sh` exists but requires `make ci-local` to pass. CI gates need a working poetry env first. Until then, GitHub PR auto-merge serves as the audit trail. | After T0.7 (harness end-to-end validation). |

---

## Required Operator Action Before Production

The following items are NOT optional once domain code starts handling
real partner data. They are listed here so they cannot be forgotten:

1. **Enable branch protection on `main`.** See "Operational / Supply
   Chain" table above.
2. **Provision a real `.secrets.baseline`** via `detect-secrets scan`.
3. **Generate distinct production secrets** for `SECRET_KEY`,
   `AUDIT_KEY`, `ARTIFACT_SIGNING_KEY`, `PII_ENCRYPTION_KEY`. Each
   must be unique. The `validate_settings` startup gate enforces
   distinctness between `SECRET_KEY` and `ARTIFACT_SIGNING_KEY`;
   distinctness across the others is operator-managed.
4. **Provision a real pgbouncer SCRAM-SHA-256 hash** in
   `pgbouncer/userlist.txt` (gitignored). The committed
   `userlist.txt.example` is a placeholder.
5. **Set `DATABASE_TLS_ENABLED=true`** in production. The
   `validate_settings` gate refuses to start otherwise.
6. **Author the audit log primitive** before any code path that reads
   PII. Per BR-501, audit emission for PII access is non-optional.
7. **Author a Business Associate Agreement (BAA) chain document**
   listing every subprocessor (per BRD §"Security and Privacy" NFR).
   Sequelae PH must be explicitly listed with the no-plaintext-PII
   scope per BR-506.

---

## Document Maintenance

This file is the source of truth for HIPAA control state. Update it when:

- A control moves from STUBBED to LIVE (a primitive is implemented).
- A new control is added (BRD amendment, new ADR).
- A deferred control's target phase changes.

Stale rows in this file are themselves a HIPAA risk: if "audit log
hash chain" stays "DEFERRED" after it ships, a future contributor
will assume it's not live and may not enforce its invariants.
