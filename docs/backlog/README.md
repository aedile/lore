# Lore Eligibility — Comprehensive Backlog

| Field | Value |
|-------|-------|
| **Status** | LIVE |
| **Last synthesized** | 2026-04-29 |
| **Source documents** | BRD, ARD, ADR-0001..ADR-0009, HIPAA_POSTURE.md |
| **Methodology** | Hybrid scaled agile with agents-as-team-members (per R8 P-005) |
| **Timeline policy** | NO calendar dates. T-shirt sizes only. Phases gated by exit criteria, not dates. |

---

## Purpose

This backlog decomposes the production design (BRD + ARD + 8 ADRs) into INVEST-compliant stories grouped into epics, organized by ARD phase. It is the single source of truth for "what gets built next" across engineering, security, compliance, UX, and infrastructure tracks.

Each story carries:

- An ID (`P{phase}-E{epic}-{nnn}`) usable as a stable reference in PRs, retros, and traceability artifacts.
- An originating BR / ADR / risk-register entry, so the rationale chain is intact.
- Acceptance criteria phrased Given/When/Then so "done" is testable.
- A T-shirt size (XS/S/M/L/XL) that captures relative effort without committing to a date.
- A strategic tier (CRITICAL / IMPORTANT / SUPPORTIVE) inherited from the BRD rule it implements.
- An owner squad/role drawn from the BRD 13-role taxonomy.

---

## Phase index

| File | Phase | Goal |
|------|-------|------|
| [phase-00-governance.md](phase-00-governance.md) | Phase 00 (Harness) | Development substrate. Closing tasks tracked there; superseded by Phase 0 below for production. |
| [phase-foundation.md](phase-foundation.md) | Phase 0 — Foundation | Empty production substrate; governance roles designated; open ADRs scoped. |
| [phase-single-partner.md](phase-single-partner.md) | Phase 1 — Single-Partner E2E | One partner, full pipeline shape, minimal feature surface. |
| [phase-production-cutover.md](phase-production-cutover.md) | Phase 2 — Production Cutover | All v1 BRs satisfied. System is production-defensible. |
| [phase-scale.md](phase-scale.md) | Phase 3 — Scale to N Partners | Configuration-driven onboarding proven across 5–10 partners. |
| [phase-hardening.md](phase-hardening.md) | Phase 4 — Hardening & Attestation | SOC 2 Type II / HITRUST CSF readiness. |

The interview-deliverable prototype (a 22-hour scoped subset of Phase 1 running on the local substrate) is tracked separately in [`../PROTOTYPE_PRD.md`](../PROTOTYPE_PRD.md). It is **not** part of this backlog; that document is the panel-deliverable build spec.

---

## Story format

Stories are written in a compact block format. Example:

```
### P1-VER-003 — Latency floor enforcement (ADR-0009)
- **As** an operator concerned with timing-channel exposure
  **I want** every Verification API response held until VERIFICATION_LATENCY_FLOOR_MS elapses
  **So that** internal-state inference via response-time differential is closed.
- **AC**
  - Given a request that resolves in 30ms internally, when the response is emitted, then ≥ floor (250ms initial) has elapsed since request arrival.
  - Given a request that resolves in 220ms (rate-limited path), when the response is emitted, then ≥ floor has elapsed (no negative held time).
  - Given 10,000 representative requests across all internal-state combinations, when the latency distribution is measured, then per-state distributions are statistically indistinguishable (KS test p ≥ 0.05) above the floor.
- **Originating** BR-401, BR-404, ADR-0009, R3 S-074
- **Depends on** P1-VER-001 (API skeleton), P0-CFG-002 (config parameter ledger live)
- **Tier** CRITICAL  · **Size** M  · **Owner** Verification squad
```

### Field semantics

| Field | Meaning |
|-------|---------|
| **ID** | `P{phase}-{epic-key}-{nnn}`. Phase = 0–4. Epic key = 3-letter mnemonic (FND, GCP, OBS, VER, ID, …). Numbers are sparse to allow insertion. |
| **As / I want / So that** | INVEST: Independent, Negotiable, Valuable, Estimable, Small, Testable. The "so that" must trace to a BR or risk reduction. |
| **AC** | Given/When/Then triplets. Each AC must be machine-verifiable (test, scan, IaC plan, doc-presence check) — not "code reviewed" or "looks right". |
| **Originating** | BR / ADR / RR (risk register) / review-finding ID that motivates the story. Used by CI traceability gate. |
| **Depends on** | Other story IDs that must complete first. Dependency graph enables parallelism analysis. |
| **Tier** | CRITICAL = launch-blocking; IMPORTANT = launch-required-for-defensibility; SUPPORTIVE = quality-of-life / future-leverage. Inherited from the dominant originating BR. |
| **Size** | XS (≤ 0.5 day · 1 PR · trivial), S (≤ 2 days), M (≤ 1 week), L (≤ 2 weeks), XL (must split — flag for refinement). |
| **Owner** | Squad or role. Squads: Verification, Identity Resolution, Ingestion, Vault, Audit, Member Rights, Platform/SRE, Security, Compliance, UX, Data Engineering. Roles per BRD §"Role taxonomy". |

### Status flags

Stories begin in **BACKLOG**. Lifecycle: BACKLOG → REFINED (AC tightened, deps confirmed) → IN-PROGRESS (assigned, branch open) → IN-REVIEW (PR open) → DONE. Statuses are tracked in the ticketing system (Linear / Jira), not in this file — this file is the design source of truth.

---

## Cross-functional balance (per R8 P-071, R8 P-072)

Compliance and UX stories are distributed across phases, not end-loaded. Each phase has at least one CRITICAL story in each of: Engineering, Security, Compliance, UX, Infrastructure. Phase exit gates explicitly check non-engineering tracks.

| Phase | Engineering | Security | Compliance | UX | Infra |
|-------|-------------|----------|------------|----|-------|
| 0     | Outbox tables; tokenization smoke | KMS HSM keyrings; VPC-SC perimeters | Privacy/Security Officers; PHI inventory; P&P drafts | Design system commit; user-research program | GCP projects, IaC, CI/CD, observability backbone |
| 1     | Format adapter, DQ Required tier, state machine, Verification API skeleton | Latency floor; JWT verifier; redaction scanner LIVE | NPP authoring; first BAA; partner data sharing agreement | Verification failure UX; lockout recovery service blueprint | Datastream→BigQuery; audit chain validator |
| 2     | Splink integration; reviewer queue; deletion workflow | Brute force progression; hash chain + external anchor; two-person rule | 50-state breach matrix; member rights workflows; training program LIVE | Reviewer interface; audit-forensic-search UX; member portal phase-1 | GCS Bucket Lock; cross-org Compliance project |
| 3     | Multi-format adapters; multi-partner ID resolution | Per-partner cryptographic isolation; subprocessor reviews | Partner BAA chain; partner-side deletion contracts | Multi-partner reviewer workload tuning | Per-partner config promotion path |
| 4     | DR drill orchestration; final reconciliation passes | Penetration test; third-party security review | BAA chain finalization; attestation evidence package | Comprehensive accessibility audit; user research summary | DR validation; runbook formalization |

---

## Traceability index

Every story declares its originating BR/ADR/RR. CI gate (per BRD XR-012) verifies the inverse: every BR has at least one story implementing it across all phases combined. The traceability matrix is generated, not maintained by hand:

```
scripts/build_traceability_matrix.py docs/backlog/*.md > docs/backlog/traceability.generated.md
```

Generated artifact is not committed; CI rebuilds and diffs to detect orphan rules.

(Script is itself a backlog item — see P0-OBS-009.)

---

## How phases gate

Per ARD §"Phased Delivery" (AD-018), no phase advances until **all** exit criteria are met. Exit criteria are explicit at the bottom of each phase file. Reviewers are scope-constrained: a Phase 1 PR may not introduce Phase 2 scope without an explicit ARD amendment.

### Phase entry gate

Each phase file lists its **entry gate** — the minimum upstream state that must hold before any story in this phase can be claimed. Entry gates exist primarily so that compliance/UX work products get their "enter Phase N" trigger captured.

### Mid-phase reordering

Inside a phase, stories may be re-ordered freely subject to the explicit `Depends on` graph. Squads pull from their lane in priority order; cross-squad dependencies are surfaced at refinement.

---

## Risk register linkage

Stories that exist primarily to retire a risk-register item (RR-001 through RR-010 in ARD §"Risk Register") declare it in `Originating`. Closing the story closes (or downgrades) the risk. The risk register is the index; this backlog is the work.

---

## Operating directives reflected here

- **Constitution Priority 0** (Security/HIPAA): every story handling PHI declares the redaction / tokenization / audit obligation in its AC.
- **No timelines** (per session feedback): T-shirt sizes only; no calendar dates anywhere in this backlog.
- **PR-based workflow**: every story ships as one PR. Cross-PR coordination is captured in `Depends on`.
- **Reviewers are scope-constrained**: a story declaring `Tier CRITICAL` cannot be merged with `Tier SUPPORTIVE` work in the same PR (cleaner audit trail; clearer rollback boundary).
- **Agents as squad members**: where a story names a "squad", an agent persona may staff it in part or in full per the methodology in R8 P-005. Agent-staffed stories still go through PR review by a human.
