# lore-eligibility

A strategic data system for trusted partner eligibility ingestion, cleansing,
identity resolution, and identity verification — built as the prototype
deliverable for the Lore Health Staff Data Engineer panel interview, Case
Study 3.

## What this repo contains

This repository tracks both the **deliverable** (problem framing, BRD, ARD,
prototype code) and the **engineering harness** that enforces quality,
security, and HIPAA-aware PII handling on every change.

- `docs/` — all committed documentation: problem brief, tech-stack
  research, BRD, ARD, ADRs, retros, phase backlogs, spec challenges,
  runbooks
- `IGNORE/` — local-only research notes and panel context (gitignored)
- `src/lore_eligibility/` — Python package: `bootstrapper/` (FastAPI app,
  settings, lifecycle), `modules/` (domain — populated post-ARD), `shared/`
  (cross-cutting infrastructure including PII security primitives)
- `tests/` — `unit/`, `integration/`, `fixtures/`
- `alembic/` — database migration scripts (dual-driver: psycopg2 for
  migrations, asyncpg at runtime)
- `pgbouncer/` — connection pooler config
- `scripts/` — CI gates, mutation testing, assertion-density tooling,
  doc audits
- `.claude/` — agent governance (CLAUDE.md, CONSTITUTION.md, 10
  specialized review agents)

## Operating documents

- `CONSTITUTION.md` — binding directives in priority order. HIPAA / PHI
  handling is Priority 0.
- `CLAUDE.md` — PM rules, TDD workflow, two-gate test policy, commit
  conventions, emergency PII protocol.

## Quick reference

```bash
# Install
poetry install --with dev

# Bring up the local stack (Postgres + pgbouncer + app)
make dev          # docker compose up + alembic upgrade + uvicorn --reload
make dev-down

# Quality gates
make lint                 # ruff, ruff-format, mypy strict, bandit, vulture
make test                 # unit tests with 95% coverage gate
make test-integration     # integration tests (PostgreSQL via pytest-postgresql)
make assert-density       # assertion-density check
make doc-audit            # README.md accuracy gate
make mutmut-gate          # mutation testing on shared/security/ + auth
make ci-local             # full local CI mirror

# Merge a PR (programmatic gate — never bare gh pr merge)
make merge-pr PR=<number>

# CLI
poetry run lore-eligibility --help
poetry run lore-eligibility version
```

## Status

**Phase 00 — Harness foundation.** ADR-0001 records the cherry-picked
harness decision (A2Tensor base, SYNTHETIC_DATA accents). Phase 01 (BRD
authorship) begins after Phase 00 retrospective sign-off.

Track active phase: `docs/backlog/phase-00-governance.md`.
Track open advisories and prior phases: `docs/RETRO_LOG.md`.

## Python version

Python 3.12. HIPAA-conscious deployment targets typically lag latest;
Lore's stack signals are conservative.

## License

Proprietary — case-study deliverable.
