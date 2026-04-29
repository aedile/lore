# ADR-0002: Monorepo with Multi-Service Build

| Field | Value |
|-------|-------|
| **Status** | ACCEPTED |
| **Date** | 2026-04-29 |
| **Phase** | Phase 00 (synthesis pre-Phase 1) |
| **Originating findings** | R2 F-143 (monorepo decision), R2 F-131 (cross-service type sharing), R5 D-007 (artifact promotion), R5 D-008 (image lifecycle) |

---

## Context

The system is a modular monolith with seven bounded contexts (per ADR-0001-derived
decomposition). Each context is a deployable unit (Cloud Run service or job). The
question of code organization — single repository with many deployable artifacts,
versus separate repositories per service — has not been answered.

Code sharing across services is non-trivial: shared model types (member_id,
token shapes), shared error catalog, shared logging conventions, shared message
schemas (Pub/Sub topics), shared security primitives (HMAC, audit emission).
Without an explicit code-organization decision, two failure modes are likely:

- **Fragmentation**: each service reinvents shared primitives, inconsistently.
- **Coupling**: shared code lives in one service that other services depend on,
  blocking independent deploys.

Considerations:

- Team size: small to medium engineering team (Sequelae PH + US-side specialists)
- Service count: 7-10 services (Cloud Run services + jobs)
- Coordination overhead vs. independent deploy capacity
- CI/CD: monorepo builds can be expensive; selective builds mitigate
- Tooling familiarity: Python ecosystem; Poetry; Cloud Build / GitHub Actions
- Auditability: SLSA provenance, image signing, and supply chain controls
  benefit from a single build origin

## Decision

**The repository is a single Python monorepo with multiple Cloud Run services
built from one shared codebase.**

### Structure

```
src/lore_eligibility/
├── shared/                     ← shared library (types, errors, audit, logging)
│   ├── errors.py
│   ├── constants.py
│   ├── telemetry.py
│   ├── security/
│   ├── messages/               ← Protobuf message schemas (per ADR-0006)
│   └── outbox/                 ← outbox primitives (per ADR-0005)
├── bootstrapper/               ← FastAPI app factory, settings, lifespan
└── modules/
    ├── ingestion/              ← bounded context: ingestion + DQ
    ├── identity_resolution/    ← bounded context: matching
    ├── canonical_eligibility/  ← bounded context: canonical model
    ├── pii_vault/              ← bounded context: tokenization
    ├── verification/           ← bounded context: verification API
    ├── deletion/               ← bounded context: deletion lifecycle
    └── audit/                  ← bounded context: audit pipeline
```

Each `modules/<context>/` is the implementation surface for a single Cloud Run
deployable. Shared code lives in `shared/`. Inter-context communication is via
Pub/Sub (no direct imports between contexts; enforced by import-linter
contracts in `pyproject.toml`).

### Build and deploy artifacts

- One container image per deployable (per Cloud Run service or job).
- Image tag includes git-SHA: `lore-eligibility/<service>:<git-sha>`.
- Same git-SHA promoted across environments (dev → staging → prod).
- Image signing via Cosign / Sigstore; Binary Authorization on Cloud Run.

### CI/CD

- GitHub Actions workflow per service detects changed paths; builds only
  affected services (selective build).
- All services rebuild when `shared/` changes (transitively dependent).
- Test matrix: per-service unit tests + cross-service integration tests +
  end-to-end pipeline tests.

### Code sharing rules

- `shared/` MAY be imported by any module.
- `shared/` MUST NOT import from any module.
- Modules MUST NOT import from each other (enforced by import-linter
  `Module independence` contract).
- Modules MAY import from `bootstrapper/` only for FastAPI wiring (verified
  by import-linter `Bootstrapper isolation` contract).

## Consequences

### Positive

- **Single source of truth for types and contracts.** Member ID, token shapes,
  error categories, message schemas — declared once.
- **Atomic refactors** of cross-cutting concerns (rename a field, update all
  consumers in one PR).
- **Simpler dependency management.** One `pyproject.toml`; one Poetry lock;
  one mypy / ruff / pytest config.
- **Better code review context.** Reviewers see how a change affects multiple
  services in one PR.
- **SLSA provenance simplicity.** One build origin; one signing identity.

### Negative

- **Build time grows with codebase.** Mitigated by selective builds and
  parallelization.
- **Coupling risk.** A single careless import in `shared/` can pull in
  unintended dependencies. Mitigated by import-linter contracts and code review.
- **Permission granularity.** All-or-nothing on repository access; per-service
  permissions require additional tooling. Acceptable for current team size.

### Mitigations

- Import-linter contracts in `pyproject.toml` enforce boundaries at build time.
- CODEOWNERS file (per R3 S-040) requires per-context review for security-
  sensitive paths.
- Selective build in CI prevents the build-time problem at the per-PR level.

## Alternatives considered

1. **Multiple repositories (one per service).** Rejected: requires shared
   library to be a separate package versioned and published; cross-service
   refactors are multi-PR; cumulative coordination cost is high for the
   current team size.
2. **Bazel monorepo with hermetic builds.** Rejected for v1: significant
   tooling investment; learning curve for the team; not justified at current
   scale. May revisit at 10x team size.
3. **Single deployable monolith (no per-context Cloud Run services).**
   Rejected: violates the bounded-context decomposition (ADR-0001) and the
   independent-deploy capacity it enables.

## References

- Originating findings: R2 F-143, R2 F-131, R5 D-007, R5 D-008
- ADR-0001 (Harness Foundation)
- import-linter contracts in `pyproject.toml`
