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
| T0.6 | IN PROGRESS | Layer 6 — docs/adr/ADR-0001 + ADR-template, docs/RETRO_LOG, docs/backlog/phase-00, docs/spec-challenges + retros READMEs, ARCHITECTURE/BRD/ASSUMPTIONS skeletons, CHANGELOG, README | All scaffold docs land; ADR-0001 records the harness decision. |
| T0.7 | TODO | Validate harness end-to-end: `poetry install`, `poetry run pytest tests/unit/`, `poetry run pre-commit run --all-files`, `poetry check --lock` | All gates green on the local machine. |
| T0.8 | TODO | Write Phase 00 retrospective to `docs/retros/phase-00.md`; update RETRO_LOG. | Retro file references advisories raised during the migration. |

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
