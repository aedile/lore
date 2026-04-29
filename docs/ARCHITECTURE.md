# Architecture — lore-eligibility

> **Status:** Skeleton. Populated in Phase 02 (ARD authorship).

This document describes the architectural decomposition of the
`lore-eligibility` system: module boundaries, data flow, integration
points, and the rationale behind each.

It is the engineering counterpart to `docs/PROBLEM_BRIEF.md` (problem
framing) and `docs/BUSINESS_REQUIREMENTS.md` (functional contract).

---

## Module Decomposition

_To be authored in Phase 02. The placeholder under
`src/lore_eligibility/modules/` will be replaced with the concrete
modules decided here, and the `import-linter` `independence` contract
will be added to `pyproject.toml` to enforce them._

---

## Data Flow

_To be authored in Phase 02._

---

## PII Tokenization Boundary

_To be authored in Phase 02. The chosen tokenization pattern (Fernet
field-level encryption vs. format-preserving encryption vs. external
KMS+vault) determines the surface area of `shared/security/`._

---

## Identity Resolution

_To be authored in Phase 02. The chosen approach (deterministic SSN
keys, Fellegi-Sunter probabilistic via Splink, learned embedding model)
determines the modules under `src/lore_eligibility/modules/`._

---

## Bulk vs. Incremental Ingestion

_To be authored in Phase 02. Both must share a code path per the brief's
Success Criterion 4._

---

## API Contracts

_To be authored in Phase 02. Includes the identity-verification API
contract requested by the case prompt._

---

## Non-Functional Requirements Mapping

_To be authored in Phase 02 with reference to
`docs/PROBLEM_BRIEF.md` §"Non-Functional Requirements". Each NFR
must map to an architectural mechanism that delivers it._

---

## ADR Index

| ADR | Status | Topic |
|-----|--------|-------|
| ADR-0001 | ACCEPTED | Harness foundation (this document's predecessor) |
