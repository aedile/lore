# Phase 00 — Governance / Harness Foundation

| Field | Value |
|-------|-------|
| **Status** | IN PROGRESS |
| **Started** | 2026-04-29 |
| **Owner** | PM (this Claude session) |
| **Classification** | Lightweight (governance-only, per CLAUDE.md Rule 30) |

---

## Goal

Stand up the development harness so that subsequent phases (BRD authorship,
ARD authorship, domain implementation) operate inside a fully-enforced
quality envelope.

ADR-0001 is the architectural decision record for this phase.

---

## Tasks

| ID | Status | Description | Acceptance |
|----|--------|-------------|------------|
| T0.1 | DONE | Layer 1 — top-level config (pyproject, pre-commit, Makefile, .gitignore, .gitleaks.toml, .markdownlint.yaml, .secrets.baseline, .env.example, .dockerignore, conftest.py, alembic.ini) | All files present at repo root; `chore: bootstrap layer 1` commit lands. |
| T0.2 | DONE | Layer 2 — CONSTITUTION.md, CLAUDE.md, .claude/agents/ (10 agents), .claude/hooks/, .claude/standards/test-quality.md | All operating docs present; `chore: bootstrap layer 2` commit lands. |
| T0.3 | DONE | Layer 3 — scripts/ (16 scripts) and .github/workflows/ci.yml | All scripts executable; CI workflow committed. |
| T0.4 | DONE | Layer 4 — src/lore_eligibility/ scaffold (bootstrapper, modules, shared) and tests/ (unit, integration, fixtures) with smoke tests | `poetry run pytest tests/unit/` collects ≥ 9 tests; `poetry run lore-eligibility version` works. |
| T0.5 | DONE | Layer 5 — Dockerfile, docker-compose.yml + override, alembic/, pgbouncer/, entrypoint.sh | `docker compose config` validates; alembic env.py imports cleanly. |
| T0.6 | DONE | Layer 6 — docs/adr/ADR-0001 + ADR-template, docs/RETRO_LOG, docs/backlog/phase-00, docs/spec-challenges + retros READMEs, BRD/ASSUMPTIONS skeletons, CHANGELOG, README. The ARCHITECTURE.md skeleton was removed when the authored ARD landed at docs/ARCHITECTURE_REQUIREMENTS.md. | All scaffold docs land; ADR-0001 records the harness decision. |
| T0.7 | TODO | Validate harness end-to-end: `poetry install`, `poetry run pytest tests/unit/`, `poetry run pre-commit run --all-files`, `poetry check --lock` | All gates green on the local machine. |
| T0.8 | TODO | Write Phase 00 retrospective to `docs/retros/phase-00.md`; update RETRO_LOG. | Retro file references advisories raised during the migration. |
| T0.9 | DONE | Pre-BRD harness hardening — fix make dev (broken docker network), Dockerfile HEALTHCHECK, PII-redacting structlog, PII-in-fixtures gate, auth-coverage gate, production-config startup validation. See PR #1 (folder merge), PR #2 (HIPAA hardening). | All committed via PRs with audit trail; HIPAA_POSTURE.md inventories live vs stubbed vs deferred controls. |
| T0.10 | TODO | Enable branch protection on `main`. Confirmed via `gh api` to be HTTP 404 currently. CONSTITUTION assumes it is on. | Required status checks include `Detect Changes`, `Security Scan (gitleaks)`, `Documentation Gate`, and (when Python work resumes) `Lint`, `Unit Tests`. |

---

## Phase Entry Gate

(Not applicable — Phase 00 is the bootstrap.)

---

## Phase Exit Criteria

- All quality gates pass on `main` (`make ci-local` returns 0)
- ADR-0001 reflects what actually shipped
- RETRO_LOG entry for Phase 00 exists with advisories logged (if any)
- `docs/retros/phase-00.md` written

---

## Out of scope for this phase

- Domain decomposition under `src/lore_eligibility/modules/` — Phase 02 (ARD)
- BRD authorship — Phase 01
- Database schema for eligibility data — Phase 03+
- Identity resolution prototype — Phase 03+
- Identity verification API — Phase 04+
