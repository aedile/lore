# lore-eligibility

A strategic data system for trusted partner eligibility ingestion, cleansing, identity resolution, and identity verification — designed and built as the Lore Health Staff Data Engineer panel deliverable for **Case Study 3**.

This repository carries three layers in one place:

1. **A runnable end-to-end prototype** — the panel demo (see [`prototype/`](prototype/) and [Quick start](#quick-start-running-the-prototype) below).
2. **A production-grade strategic design** — Problem Brief, BRD, ARD, 9 ADRs, HIPAA posture, 243-story backlog spanning ARD phases 0–4.
3. **A development harness** — quality + security + HIPAA-aware PII handling enforced on every change, with an auditable trail of every CI run that gated a merge.

The prototype is the deliverable. The strategic design and harness are the *evidence that the prototype was built deliberately, not improvised*.

---

## Quick start: running the prototype

The prototype is a self-contained, ~6-second end-to-end demo on synthetic data. It exercises every numbered acceptance criterion in [`docs/PROTOTYPE_PRD.md`](docs/PROTOTYPE_PRD.md) — ingestion through verification through deletion-with-suppression — with a hash-chained audit log validated at the end.

```bash
# 1. Install dependencies (one-time)
poetry install --with dev
poetry run pip install -r prototype/requirements.txt

# 2. Spawn a one-shot Postgres for the prototype on port 5440
make prototype-pg-up

# 3. Run the full panel demo (~4–7 seconds)
make prototype-demo

# 4. Tear down when finished
make prototype-pg-down
```

Optional one-shot:
```bash
make prototype-h2          # Splink near-duplicate detection snippet (panel hands-on artifact H2)
make prototype-test        # 153 prototype tests in ~8 seconds
```

**Read this next:** [`prototype/README.md`](prototype/README.md) — what each artifact does and how the relaxed prototype harness differs from the production-shaped harness under `src/lore_eligibility/`.

---

## What's in here

### The strategic design (panel-facing prose + specs)

| Doc | Purpose |
|---|---|
| [`docs/PROBLEM_BRIEF.md`](docs/PROBLEM_BRIEF.md) | The case as the panel posed it, plus inferred constraints a Staff response must address |
| [`docs/BUSINESS_REQUIREMENTS.md`](docs/BUSINESS_REQUIREMENTS.md) | The BRD — every rule, with originating findings, programmatic enforcement, and `[ADVISORY]` markers where enforcement is honest-not-yet |
| [`docs/ARCHITECTURE_REQUIREMENTS.md`](docs/ARCHITECTURE_REQUIREMENTS.md) | The ARD — 33 architectural decisions, threat model per bounded context, asset classification, deployment topology |
| [`docs/HIPAA_POSTURE.md`](docs/HIPAA_POSTURE.md) | What's LIVE today vs. STUBBED vs. PLANNED-PHASE-N — the inventory that keeps perception aligned with reality |
| [`docs/PROTOTYPE_PRD.md`](docs/PROTOTYPE_PRD.md) | The build spec the prototype satisfies, with traceability back to the PDF prompt |
| [`docs/adr/`](docs/adr/) | 9 ADRs covering harness, monorepo, tokenization, JWT, transactional outbox, logging, Cloud Run, audit anchoring, latency equalization |

### The backlog (how production gets built)

A 243-story INVEST-compliant backlog organized by ARD phase 0–4. Every story carries originating BR/ADR/risk-register citation, Given/When/Then acceptance criteria, T-shirt sizing (no calendar dates), and squad/role ownership. 100% citation coverage against BRD/ARD/risk register verified by a coverage script (script itself is P0-OBS-009 in the backlog).

| File | Phase | Goal |
|---|---|---|
| [`docs/backlog/README.md`](docs/backlog/README.md) | — | Format guide, story conventions, cross-track distribution |
| [`docs/backlog/phase-foundation.md`](docs/backlog/phase-foundation.md) | Phase 0 | Empty production substrate; governance roles; 8 deferred ADRs scoped |
| [`docs/backlog/phase-single-partner.md`](docs/backlog/phase-single-partner.md) | Phase 1 | One partner, full pipeline shape, minimal feature surface (carries the Phase 1.5 split policy) |
| [`docs/backlog/phase-production-cutover.md`](docs/backlog/phase-production-cutover.md) | Phase 2 | All v1 BRs satisfied; production-defensible |
| [`docs/backlog/phase-scale.md`](docs/backlog/phase-scale.md) | Phase 3 | Configuration-driven onboarding proven across 5–10 partners |
| [`docs/backlog/phase-hardening.md`](docs/backlog/phase-hardening.md) | Phase 4 | SOC 2 Type II / HITRUST CSF readiness |

### The methodology + audit trail

| Doc | Purpose |
|---|---|
| [`CONSTITUTION.md`](CONSTITUTION.md) | Binding directives in priority order. HIPAA/PHI handling is Priority 0 |
| [`CLAUDE.md`](CLAUDE.md) | PM agent rules — TDD, two-gate test policy, commit conventions, phase classification, emergency PII protocol |
| [`docs/RETRO_LOG.md`](docs/RETRO_LOG.md) | Phase summary table + open advisory rows (BLOCKER / DEFERRED / INFORMATIONAL) |
| [`docs/retros/`](docs/retros/) | Per-phase retrospectives |
| [`docs/ci-audit.jsonl`](docs/ci-audit.jsonl) | Append-only record of every local CI run that gated a `make merge-pr` invocation |
| [`docs/reviews/`](docs/reviews/) | The 8 review rounds (principal architect, chief programmer, security, compliance, devops, UI/UX, executive, project manager) that produced 522 findings synthesized into the BRD/ARD |
| [`.claude/agents/`](.claude/agents/) | 10 specialized review-agent personas used in the PR pipeline |

### The production-shaped package

```
src/lore_eligibility/
├── bootstrapper/        FastAPI app factory, settings, lifespan, PII-redacting structlog (LIVE)
├── modules/             Domain modules — populated post-ARD via the backlog
└── shared/              Cross-cutting: errors, telemetry, security primitives
```

Plus `tests/unit/` + `tests/integration/`, `alembic/` (psycopg2 for migrations, asyncpg at runtime), `pgbouncer/` (transaction-mode pooler), and `scripts/` (CI gates, mutation testing, assertion-density tooling, doc audit, traceability matrix).

---

## How to navigate by interest

- **Panel reviewer who wants the demo first.** [`prototype/README.md`](prototype/README.md) → `make prototype-demo` → [`prototype/docs/walkthrough.md`](prototype/docs/walkthrough.md).
- **Architect who wants the production design.** [`docs/PROBLEM_BRIEF.md`](docs/PROBLEM_BRIEF.md) → [`docs/BUSINESS_REQUIREMENTS.md`](docs/BUSINESS_REQUIREMENTS.md) → [`docs/ARCHITECTURE_REQUIREMENTS.md`](docs/ARCHITECTURE_REQUIREMENTS.md) → [`docs/adr/`](docs/adr/).
- **Compliance reviewer.** [`docs/HIPAA_POSTURE.md`](docs/HIPAA_POSTURE.md) → BRD §"HIPAA Privacy Rule / Breach Notification" → ARD §"Threat Model per Bounded Context".
- **Engineering lead asking "how would this actually be built?"** [`docs/backlog/README.md`](docs/backlog/README.md) → phase files in order.
- **Anyone auditing process discipline.** [`CONSTITUTION.md`](CONSTITUTION.md) + [`CLAUDE.md`](CLAUDE.md) + [`docs/RETRO_LOG.md`](docs/RETRO_LOG.md) + [`docs/ci-audit.jsonl`](docs/ci-audit.jsonl).

---

## Quick reference (production harness)

```bash
# Install
poetry install --with dev

# Local stack (Postgres + pgbouncer + app, hot reload)
make dev
make dev-down

# Quality gates
make lint                 # ruff, ruff-format, mypy strict, bandit, vulture
make test                 # unit tests (95% coverage gate)
make test-integration     # integration tests (PostgreSQL via pytest-postgresql)
make assert-density       # assertion-density check
make doc-audit            # README.md accuracy gate
make mutmut-gate          # mutation testing on shared/security/ + auth
make ci-local             # full local CI (17 gates; mirrors what merge-pr runs)

# Merge a PR (programmatic gate — never bare gh pr merge per CLAUDE.md Rule 12)
make merge-pr PR=<number>

# CLI
poetry run lore-eligibility --help
poetry run lore-eligibility version
```

The prototype harness is intentionally relaxed; the production harness is strict. See [`prototype/README.md`](prototype/README.md) §"Run-dirty profile" for the boundary.

---

## Status

**Strategic design + comprehensive backlog merged. Prototype runnable. Harness baseline green (17/17 CI gates).** Recent activity is captured in [`docs/RETRO_LOG.md`](docs/RETRO_LOG.md). The most recent retro is [`docs/retros/phase-harness-debt-drain.md`](docs/retros/phase-harness-debt-drain.md), which documents how the harness was restored to a clean baseline before any production-track Phase 0 work begins.

**Open advisories** (see RETRO_LOG):

- **ADV-001 (BLOCKER):** enforce `make merge-pr` as the only merge path. Target: enable main branch protection (Phase 00 T0.10) before next code-bearing PR work resumes.

Phase 0 production work has not started; per ADR-0001 and ADV-001, branch protection lands first.

---

## Python version

Python 3.12. HIPAA-conscious deployment targets typically lag latest; Lore's stack signals are conservative.

## License

Proprietary — case-study deliverable.
