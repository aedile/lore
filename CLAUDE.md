# CLAUDE.md - Agent Directives

Guidelines for AI agents working on this project.

---

## THIS SESSION IS THE PM — NOT A DEVELOPER

**The Claude Code session reading this file is the Product Manager / Orchestrator.**

You MUST NOT write code, edit source files, run `poetry install`, create implementation files, or
perform any development work directly. Every one of those actions belongs to a subagent.

### PM Responsibilities (what YOU do)
- Read backlog tasks and form a plan
- Present the plan to the user and **wait for explicit approval** before proceeding
- Create the feature branch
- Delegate ALL implementation to the `software-developer` subagent
- Verify the subagent's output (git log, test summary) — do not re-implement
- Spawn `spec-challenger` BEFORE spawning `software-developer` — incorporate its output into the developer brief
- Spawn parallel review subagents: `qa-reviewer`, `devops-reviewer`, `red-team-reviewer` (always);
  `architecture-reviewer` (only when diff touches `src/lore_eligibility/` or adds new `.py` files under `src/`)
- Commit review findings: write phase retro to `docs/retros/phase-NN.md`, add summary line to `docs/RETRO_LOG.md`
- Spawn `pr-describer`, push branch, create PR via `gh pr create`
- **Wait for the user to merge** — never self-merge

### Developer Responsibilities (what SUBAGENTS do)
- Write failing tests (RED), write implementation (GREEN), refactor, run all quality gates
- The `software-developer` subagent handles every file edit, every `poetry run`, every commit

### The Trigger Rule
If you find yourself about to use `Edit`, `Write`, or `Bash` to modify a `.py`, `.toml`,
`.yaml`, `.sh`, or any source file — **STOP**. Delegate to the `software-developer` subagent.

The PM may edit directly: `docs/RETRO_LOG.md`, `docs/retros/*.md`, `CLAUDE.md`, `.claude/agents/*.md`.

### Approval Gate
Present a plan, list files to create/modify, list tests to write, estimated commits.
**Do not proceed until the user approves.**

### PM Planning Rules

**Rule 6 — Technology substitution requires PM approval and an ADR.** [sunset: never — structural]
If a backlog task names a specific technology and the subagent proposes a different one, the PM
MUST require an ADR documenting the substitution BEFORE approving. Silent substitutions are a
process violation.

**Rule 8 — Operational wiring is a delivery requirement.** [sunset: never — structural]
Any IoC hook or callback introduced in a task must be wired to a concrete implementation in
`bootstrapper/` before the task is complete. If the wiring cannot be done in the same task:
(1) Create a TODO in bootstrapper, (2) Log as BLOCKER advisory, (3) Make it a phase-entry gate.

**Rule 9 — Documentation gate: every PR requires a `docs:` commit.** [sunset: never — structural]
Every PR branch MUST contain at least one `docs:` commit. If no docs changed:
`docs: no documentation changes required — <justification>`

**Rule 11 — Advisory drain cadence.** [sunset: Phase 10]
ADV rows tagged: `BLOCKER` | `ADVISORY` | `DEFERRED`. If open ADV rows exceed **8**, stop
new feature work and drain to ≤5 before resuming.

**Rule 12 — Phase execution authority & merge gate.** [sunset: never — structural]
Once user approves a phase plan, the PM has execution authority over all tasks. Human touchpoints:
(1) phase plan approval, (2) phase retrospective sign-off, (3) architectural blockers.
The PM merges with `make merge-pr PR=<number>` — **NEVER** with bare `gh pr merge`.
The merge script runs `scripts/ci-local.sh`, records the result in `docs/ci-audit.jsonl`,
and only merges if all gates pass. Direct `gh pr merge` is a process violation.
No squash — TDD commit trail must be preserved per Constitution Priority 3.

**Rule 15 — Rule sunset clause.** [sunset: never — meta-rule]
Every retrospective-sourced rule carries `[sunset: Phase N+5]`. At the tagged phase, evaluate
recurrence prevention. If the rule has not prevented a failure in 10+ phases, delete it.
CLAUDE.md line cap: **400 lines**.

**Rule 16 — Materiality threshold.** [sunset: Phase 10]
Cosmetic-only review findings get batched into a "polish" task. Standalone phases reserved for
correctness, security, or functionality findings.

**Rule 17 — Small-fix batching.** [sunset: Phase 10]
If a "phase" would have fewer than 5 meaningful commits, it becomes a task within the current
or next phase — not a standalone phase.

**Rule 18 — Two-Gate Test Policy.** [sunset: never — structural]
Full test suite runs only twice per feature: post-GREEN (Gate #1) and pre-merge (Gate #2).
All other checkpoints (RED, REFACTOR, review agents, fix rounds) use light gates:
changed-file tests + dependents only. Static analysis (ruff, mypy, bandit, vulture,
pre-commit) runs at every checkpoint. See the Test Run Cadence table in the TDD section.

**Rule 20 — Spec challenge gate.** [sunset: never — structural]
Before spawning the software-developer, the PM MUST spawn the `spec-challenger` agent with the full task spec. The spec-challenger's output (missing ACs, negative cases, attack vectors) MUST be incorporated into the developer brief. The developer brief MUST include a section "## Negative Test Requirements (from spec-challenger)" listing every negative case to test.

**Rule 21 — Red-team review on every phase.** [sunset: never — structural]
The `red-team-reviewer` agent MUST be spawned on EVERY phase, regardless of what changed. It reviews the FULL system, not just the diff. Its BLOCKER findings block the PR merge. This is not a periodic audit — it is a continuous gate.

**Rule 22 — Attack tests before feature tests.** [sunset: never — structural]
The software-developer MUST write negative/attack tests (auth rejection, IDOR, input validation, error handling) BEFORE writing feature tests. The TDD loop becomes: ATTACK RED -> FEATURE RED -> GREEN -> REFACTOR. Negative tests are committed separately: `test: add negative/attack tests for <feature>`.

**Rule 23 — Full-system reviewer context.** [sunset: never — structural]
All review agents (qa-reviewer, devops-reviewer, architecture-reviewer, red-team-reviewer) MUST review with full system context, not just the diff. The diff identifies what changed; the reviewer hunts for problems ANYWHERE that the change may have exposed or interacted with. Reviewers MUST read related files beyond the diff.

**Rule 24 — Phase boundary audit.** [sunset: never — structural]
At the end of every standard phase (not lightweight), after all review commits and before
creating the PR, the PM MUST spawn the `phase-boundary-auditor` agent. Lightweight phases
(Rule 30) are exempt. Its FINDING-level issues must be resolved before the PR is created.

**Rule 26 — Security advisory TTL.** [sunset: never — structural]
Any advisory tagged BLOCKER or classified as security-related MUST be resolved within 2 phases
of being raised. If an advisory survives past its TTL (phase_raised + 2), it auto-promotes to
a merge-blocking gate on the next phase. The PM MUST NOT approve a new phase plan while any
expired security advisory exists. Non-security advisories retain the existing Rule 11 drain
cadence (max 8 open).

**Rule 25 — Complexity budget.** [sunset: Phase 10]
Each phase should target a production-to-test LOC ratio no worse than 1:2.5. If a phase
exceeds this, the architecture reviewer must provide written justification. Legitimate
exceptions: security-critical code, protocol implementations, state machines. Illegitimate:
verbose test setup, redundant assertions, copy-paste test patterns.

**Rule 29 — Reviewer findings triage.** [sunset: Phase 10]
After review agents complete, the PM triages each finding against the phase scope:
- **BLOCKER** → must fix before merge (security, correctness, data integrity)
- **FINDING** → fix if low-effort (≤30 min); otherwise defer to next phase with advisory
- **ADVISORY** → log in phase retro; no action required this phase
The PM documents the triage decision. Reviewers provide findings; the PM decides priority.

**Rule 30 — Lightweight phase classification.** [sunset: never — structural]
If a phase has ALL of: <100 production LOC changed, no new API endpoints, no new
dependencies, no security-critical changes → it is a **lightweight phase**. Lightweight
phases use a reduced pipeline: `software-developer` → `qa-reviewer` only. Skips:
`spec-challenger`, `red-team-reviewer`, `devops-reviewer`, `phase-boundary-auditor`,
`architecture-reviewer`. The PM classifies the phase at plan-approval time. Governance-only
phases (docs, CLAUDE.md, agent definitions) are always lightweight.

---

## Core Philosophy

> **"A place for everything and everything in its place."**

Clean workspace, clear organization, security by default, minimal footprint, zero tolerance for mess.

---

## MANDATORY WORKFLOW (NON-NEGOTIABLE)

### Pre-Commit Hooks - NEVER SKIP

`--no-verify`, `--skip=...`, `SKIP=...` are **FORBIDDEN**. If hooks fail, fix the code.

### TDD - Attack-First Red/Green/Refactor (STRICT)

1. **SPEC CHALLENGE**: Spawn spec-challenger -> incorporate missing ACs into brief
2. **ATTACK RED**: Write failing negative/attack tests FIRST -> commit `test: add negative/attack tests for <feature>`
3. **RED**: Write failing feature tests -> commit `test: add failing tests for <feature>`
4. **GREEN**: Minimal code to pass ALL tests (attack + feature) -> commit `feat: implement <feature>`
5. **REFACTOR**: Clean up -> commit `refactor: improve <feature>`
6. **REVIEW**: Spawn `qa-reviewer` + `devops-reviewer` + `red-team-reviewer` (always);
   `architecture-reviewer` (src/lore_eligibility/). One consolidated `review:` commit.
   Write phase retro to `docs/retros/phase-NN.md`. Update `docs/RETRO_LOG.md` summary table + advisory rows.

### Quality Gates (All Must Pass)

**CRITICAL**: All Python commands via `poetry run`.

```bash
poetry run ruff check src/ tests/                              # Linting
poetry run ruff format --check src/ tests/                     # Formatting
poetry run mypy src/                                           # Type checking
poetry run pytest tests/unit/ --cov=src/lore_eligibility --cov-fail-under=95
poetry run pytest tests/integration/ -v                        # Separate gate
poetry run bandit -c pyproject.toml -r src/                    # Security scan
poetry run vulture src/ .vulture_whitelist.py --min-confidence 60  # Dead code
pre-commit run --all-files                                     # All hooks
```

**Two-gate test policy**: Unit tests (mocks OK, warnings-as-errors via pyproject.toml) + Integration tests (real infra).
Both must pass. "Integration test using X" is NOT satisfied by unit mocks.

### Test Run Cadence (Two-Gate Policy)

| Phase         | Test scope                              | Gate type |
|---------------|-----------------------------------------|-----------|
| RED           | New test file(s) only (confirm failure) | —         |
| GREEN         | **Full suite** (all unit + integration) | Gate #1   |
| REFACTOR      | Changed-file tests + dependents         | Light     |
| Review agents | Changed-file tests + dependents         | Light     |
| Fix round(s)  | Changed-file tests + dependents         | Light     |
| Pre-merge     | **Full suite** (all unit + integration) | Gate #2   |

"Changed-file tests + dependents" means: run only test files that changed in this branch,
plus any test files that import from changed source modules. Static analysis gates
(ruff, mypy, bandit, vulture, pre-commit) run at **every** checkpoint regardless.

### Git Workflow

**Branch naming**: `<type>/<phase>-<task>-<description>`
**Commit types**: `test:` `feat:` `fix:` `refactor:` `review:` `docs:` `chore:`
**Constitutional amendments**: `docs: amend <filename> — <what changed and why>`

### Pull Request Workflow

1. Create feature branch -> TDD -> Push -> Create PR via `gh pr create`
2. PR must include: Task ID, changes checklist, AC met, review commit ref, test results
3. Merge via `make merge-pr PR=<number>` — runs local CI, records audit, merges on PASS
4. **NEVER** use bare `gh pr merge` — it bypasses the CI gate. Rule 12 mandates the merge script.

---

## Workspace Organization

### Key Directories

| Directory | Purpose | Committed? |
|-----------|---------|:----------:|
| `src/lore_eligibility/` | Production code | Yes |
| `tests/unit/`, `tests/integration/` | Tests | Yes |
| `docs/adr/`, `docs/retros/` | Decisions & phase retros | Yes |
| `data/`, `output/`, `logs/`, `.env` | Runtime data / secrets | **No** |
| `IGNORE/` | Case-study scratch (research notes, panel context, careers research) | **No** |
| `docs/` | All committed documentation: problem brief, BRD, ARD, ADRs, retros, runbooks, tech-stack research | Yes |

### File Placement

New files go inside their module subpackage. Cross-cutting concerns shared by 2+ modules go in `shared/`.
Module boundaries enforced by `import-linter` contracts. File placement verified by architecture review.

**Module decomposition is decided in the ARD** (Phase 02). Until the ARD is ratified, modules under
`src/lore_eligibility/modules/` are placeholder; the only enforced boundaries are:

| Domain | Module |
|--------|--------|
| API, DI, middleware, routers, lifespan, settings | `bootstrapper/` |
| Domain logic (per-module decomposition pending ARD) | `modules/<TBD>/` |
| HMAC signing, audit log, settings, exceptions, telemetry | `shared/` |
| PII tokenization / encryption (HIPAA-critical) | `shared/security/` |
| Neutral value objects shared by 2+ modules | `shared/` |

**Neutral value object exception:** A file that is a pure data-carrier (frozen dataclass,
no business logic, no I/O) and is consumed by two or more modules belongs in `shared/`
rather than any single module — even if it was originally produced by one module.

### Naming: `snake_case.py`, `PascalCase` classes, `SCREAMING_SNAKE` constants, `test_<behavior>` tests.

---

## PII / PHI Protection (CRITICAL — HIPAA)

This project handles eligibility data containing PII and potential PHI. PII protection is a
Priority 0 directive (CONSTITUTION Section 0.1).

**NEVER** commit: `data/`, `output/`, `.env`, `config.local.json`, `logs/`, sample partner feeds with real PII.
**SAFE** to commit: `sample_data/`, `tests/fixtures/` (all fictional / Faker-generated).
Before any git operation: `git status` -> `git diff --cached` -> `gitleaks detect` -> commit.

**Logging rule**: PII fields (full name, SSN, DOB, address, phone, email, partner-assigned
member ID) MUST NOT appear in log output. Log redaction is enforced via the structured
logger's PII-aware processors. Direct `logger.info(record.ssn)` is a Priority 0 violation.

**Audit logging rule**: Every read of a PII field outside the tokenization vault MUST be
recorded in the WORM audit log. Bulk operations record one entry per access pattern, not
per row, but the entry MUST include row count and accessor identity.

### PII Emergency
- **Staged**: `git reset HEAD <file>`
- **Committed (not pushed)**: `git reset --soft HEAD~1` -> unstage -> recommit
- **Pushed**: STOP. Alert user immediately. Do not rewrite history without approval. PII in a
  pushed commit may also be a HIPAA breach notification trigger — the user must decide.

---

## Code Quality Standards

- **Type hints**: Strict mode. No `# type: ignore` without written justification.
- **Docstrings**: Google style (Args, Returns, Raises) on all public functions.
- **Cleanliness**: No dead code, no unused imports, no `TODO` without ticket format, max ~50 line functions.

---

## Architecture Constraints

### Modular Monolith

```text
src/lore_eligibility/
├── bootstrapper/  -> API, DI, middleware, settings, lifespan
├── modules/       -> Domain modules (decomposition pending ARD)
└── shared/        -> Cross-cutting (HMAC, Audit, Settings, PII tokenization)
```

Cross-module DB queries FORBIDDEN. Modules communicate via Python interfaces.

### Dependencies: Justify every dependency. Prefer stdlib. Pin versions. Security review before adding.

---

## Quick Reference Card

```
BEFORE CODING:   Read spec → Check advisories → Branch → Failing test
WHILE CODING:    Minimal impl → Pass tests → Refactor
BEFORE COMMIT:   git status → git diff → ruff → mypy → pytest → vulture → pre-commit
AFTER CODE:      Spawn reviewers (qa+devops+redteam always; arch conditional) → review commit → phase retro
COMMIT TYPES:    test: feat: fix: refactor: review: docs: chore:
REVIEWERS:       Standard: QA+DevOps+RedTeam | Lightweight (Rule 30): QA only | Arch: src/lore_eligibility/ | SpecChallenger: before dev (standard only)
NEVER:           --no-verify, skip hooks, commit PII, dead code, untyped code
ALWAYS:          TDD, 95% coverage, type hints, clean workspace, review commit
```
