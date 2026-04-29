# ADR-0001: Harness Foundation — Cherry-pick A2Tensor + SYNTHETIC_DATA

| Field | Value |
|-------|-------|
| **Status** | ACCEPTED |
| **Date** | 2026-04-29 |
| **Phase** | Phase 00 (governance) |

---

## Context

`lore-eligibility` is a greenfield project authored as a 24-hour Lore Health
case-study deliverable. The deliverable requires:

- SQL DDL for the curated eligibility data store
- A working prototype demonstrating identity resolution and PII cleansing on
  synthetic data
- An identity verification API contract
- HIPAA / HITECH–aware PII isolation

The author maintains two adjacent Python projects (A2Tensor and
SYNTHETIC_DATA) with mature, programmatically-enforced development harnesses.
Both share a consistent toolchain: Poetry, Ruff, Mypy strict, Pytest at 95%
coverage, Bandit, gitleaks, detect-secrets, import-linter, mutation testing
on security-critical modules, pydoclint, and a `.claude/` multi-agent
governance pattern (CONSTITUTION.md + CLAUDE.md + 10+ specialized review
agents).

Re-creating this harness from scratch for a 24-hour deliverable is wasteful;
adopting one of the existing harnesses verbatim ports A2Tensor- or
SYNTHETIC_DATA-specific scaffolding (frontend, mTLS, air-gap bundles, ML
optional groups, 50+ phase backlog files) that does not apply.

---

## Decision

Adopt a cherry-picked harness derived from A2Tensor as the primary template,
with selected accents from SYNTHETIC_DATA. Adapt to `lore_eligibility`
package name, Python 3.12, HIPAA-aligned defaults.

### What is ported (mostly mechanically)

| Layer | Source | Notes |
|---|---|---|
| `pyproject.toml` toolchain | A2Tensor | Drop ML optional groups; Python pin 3.12; rename to `lore_eligibility` |
| `.pre-commit-config.yaml` (12 hooks) | A2Tensor | poetry-check, gitleaks, detect-secrets, ruff, mypy, bandit, nbstripout, import-linter, pydoclint, assert-density, integration-mock, doc-audit |
| `Makefile` | A2Tensor | Drop airgap and hardware-test targets |
| `CONSTITUTION.md` | A2Tensor | Add HIPAA / PHI under Priority 0; reference the actual gates wired in this repo |
| `CLAUDE.md` | A2Tensor | Module-placement section stubbed pending ARD; tier model compressed for case-study cadence |
| `.claude/agents/` (10 agents) | A2Tensor | Skip ui-ux-reviewer (no frontend) |
| `.claude/hooks/` | A2Tensor | pre_tool_use.sh + worktree_create.sh |
| `scripts/` (16 scripts) | A2Tensor | ci-local, merge-pr, mutmut gate, assert-density tooling, doc-audit, integration-mock, vulture plugin |
| `.github/workflows/ci.yml` | SYNTHETIC_DATA | More mature than A2Tensor's; SHA-pinned actions; docs-only short-circuit |
| `Dockerfile` + `docker-compose.yml` | A2Tensor | Postgres + pgbouncer + app only — no redis, prometheus, grafana, alertmanager |
| `alembic/` + `pgbouncer/` | A2Tensor | Dual-driver migration env (psycopg2 / asyncpg) |
| `conftest.py` (root) | SYNTHETIC_DATA | Collection-time warning filters for pytest-asyncio |

### What is intentionally NOT ported

| Skipped | Why |
|---|---|
| `frontend/` (React/Vite SPA) | Brief does not request a UI |
| Air-gap bundle scripts (`build-airgap-bundle.sh`, `verify-airgap-bundle.sh`) | Production-ops feature, not relevant to case study |
| mTLS variant (`docker-compose.mtls.yml`, cert rotation scripts) | Mention in security posture docs without implementing |
| Prometheus / Grafana / Alertmanager | Observability stack not selected for Phase 00; can add later when the brief's "operational observability" requirement is implemented |
| Redis | No task queue yet; bulk loads can be synchronous until proven otherwise |
| ML optional dep groups (`teacher-mlx`, `teacher-ollama`, `trainer`, `serving`, `evaluator`) | No ML in this deliverable's scope |
| Pre-existing 58-phase backlog files | `lore-eligibility` starts at Phase 00 fresh |
| GPU compose variant (`docker-compose.gpu.yml`) | No GPU workload |
| ZAP / SBOM / Trivy CI jobs | Require running app; reintroduce when there is a real Docker image and routes to scan |

### Explicit project-specific deltas

- **Python 3.12** (not 3.13). HIPAA-conscious shops typically lag latest;
  Lore's stack signals (per `DOCUMENTS/TECH_STACK.md`) are conservative.
- **License = Proprietary** (case-study deliverable).
- **Mutation testing tool = mutmut** (A2Tensor's choice). Targets
  `shared/security/` (60% threshold) and `bootstrapper/auth.py` (50%
  threshold). Both vacuously pass until the targets contain code.
- **Module independence import-linter contract is intentionally absent**
  until the ARD (Phase 02) decides the domain decomposition. The
  bootstrapper-isolation and shared-constraints contracts are active now.
- **HIPAA / PHI elevated to Priority 0** in CONSTITUTION.md alongside
  the standard security and quality directives.

---

## Consequences

### Positive

- The harness is on day one: 95% coverage gate, mutation testing scaffolding,
  attack-test ordering audit, spec-challenge requirement, programmatic merge
  gate, and the full multi-reviewer agent pattern are all live.
- The author already has muscle memory for this harness across two adjacent
  projects; no relearning cost.
- HIPAA-aware defaults (7-year audit retention, mandatory PII encryption key
  in `.env.example`, Priority 0 PII handling) are baked in from the start
  rather than retrofitted.

### Negative

- Some imported scaffolding is "scaffolding for nothing yet": the
  `phase-boundary-auditor` agent, `mutmut-gate`, and several scripts assume
  state (test files, security modules, security advisories) that does not
  yet exist. They no-op or vacuously pass until populated. This is by
  design but is a moderate maintenance load.
- The 30 PM rules in CLAUDE.md are sized for a 50+ phase product, not a
  4-phase case study. Sunsets have been adjusted to Phase 10, but several
  rules will retire quickly. Acceptable cost.

### Mitigations

- ADR-0002 (BRD foundation) and ADR-0003 (ARD foundation) will populate the
  module decomposition so the placeholder import-linter contract can be
  replaced with the real one.
- `mutmut-gate` honors `SKIP_MUTMUT=1` for local development until the
  security modules contain code; merge-pr unsets the flag at merge time.

---

## Alternatives considered

1. **Adopt A2Tensor verbatim.** Rejected: ports irrelevant ML scaffolding
   and frontend tooling for a case-study deliverable.
2. **Adopt SYNTHETIC_DATA verbatim.** Rejected: ports a React frontend, mTLS
   variant, and cosmic-ray mutation testing that are not the author's
   current preference.
3. **Build a new lean case-study harness from scratch.** Rejected by the
   user: "the guardrails ARE the harness, there is no compromising on
   that." Rebuilding the guardrails from scratch is a 4-6 hour cost in a
   12-15 hour budget.
4. **Defer harness setup until after the BRD/ARD are written.** Rejected:
   without enforced gates, the BRD/ARD authoring itself can drift on
   process discipline (commit conventions, doc audits, retrospectives).
