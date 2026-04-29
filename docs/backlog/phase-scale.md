# Phase 3 — Scale to N Partners Backlog

| Field | Value |
|-------|-------|
| **ARD reference** | §"Phased Delivery" / Phase 3 |
| **Goal** | Demonstrate the configuration-driven onboarding path with multiple partners and varied formats. |
| **Status** | LIVE BACKLOG |

---

## Phase 3 Goal

Onboard 5–10 partners with mixed formats. Tune Splink thresholds against real cross-partner data. Establish DQ baselines per partner. Validate reconciliation flows. Subprocessor reviews. Partner-side deletion contracts.

## Phase 3 Entry Gate

- All Phase 2 exit criteria met.
- First-partner production traffic stable for the post-Phase-2 soak window.
- Phase 1 onboarding runbook (P1-ONB-002) revised based on first-partner retros.
- Subprocessor BAA chain (P1-COM-004) reviewed for additional GCP-side managed services that come into scope at scale (e.g., Memorystore, Datastream as data plane).

## Phase 3 Exit Criteria (per ARD)

- Onboarding a new partner is achievable in under one engineering-day from YAML PR to production-live.
- No partner-specific code paths exist in production code (BR-802 enforcement).
- Cross-partner identity resolution (same person, two partners) is detected and handled correctly per BR-205.
- Cross-partner correlation prevention verified (per ADR-0003 per-partner salts).
- Partner-side deletion notification path operational.

---

## Epics

| Key | Epic | Description |
|-----|------|-------------|
| FMT | Multi-Format Adapters | X12 834, fixed-width, JSON adapters added; AD-016 contract held |
| TUNE | Splink Tuning at Scale | Threshold tuning across cross-partner ground truth |
| MPI | Multi-Partner Identity | Cross-partner identity resolution + dedup at scale |
| ISO | Per-Partner Cryptographic Isolation | Validation under N-partner load |
| ONB | Onboarding Path Industrialized | <1 engineering-day onboarding |
| SUB | Subprocessor Reviews | Per-partner subprocessor disclosure + BAA chain review |
| DEL | Partner-Side Deletion Contracts | Forward and inbound deletion notification |
| OBS | Per-Partner SLO + Observability | Per-partner dashboards + SLOs |
| UX  | Multi-Partner Reviewer Workload | Reviewer queue prioritization + workload balance |
| GOV | Governance at Scale | BR-802 enforcement gate; per-partner ADR template |

---

## Stories

### Epic FMT — Multi-Format Adapters

#### P3-FMT-001 — X12 834 format adapter
- **As** the Ingestion squad
  **I want** an X12 834 (Benefit Enrollment and Maintenance) format adapter
  **So that** the most common real-world health-plan enrollment format is supported.
- **AC**
  - Given a well-formed 834 file, when adapted, then segments map to row dicts per the documented 834-loop structure.
  - Given a malformed 834 (missing required loop), when adapted, then it produces a parse_error record (not a silent drop) and the feed fails the schema-drift check (P1-DQ-003) if the missing loop is required.
  - Given the adapter, when integrated with the mapping engine (P1-ING-003), then 834 → canonical staging records flow without partner-specific code in the engine.
- **Originating** AD-016, AD-001, BR-301
- **Depends on** P1-ING-001, P1-ING-003
- **Tier** CRITICAL · **Size** L · **Owner** Ingestion

#### P3-FMT-002 — Fixed-width format adapter
- **As** the Ingestion squad
  **I want** a fixed-width format adapter parameterized by a width-spec YAML
  **So that** legacy partners using fixed-width can be onboarded without bespoke engineering.
- **AC**
  - Given a fixed-width file + width-spec YAML, when adapted, then row dicts emerge with correct column boundaries.
  - Given a row violating the width spec, when adapted, then it produces a parse_error.
- **Originating** AD-016
- **Depends on** P1-ING-001
- **Tier** IMPORTANT · **Size** M · **Owner** Ingestion

#### P3-FMT-003 — JSON Lines format adapter
- **As** the Ingestion squad
  **I want** a JSON Lines / NDJSON adapter
  **So that** modern API-based partners delivering JSON snapshots can be onboarded.
- **AC**
  - Given a JSON Lines file, when adapted, then each object becomes a row dict with parse-error rows separated.
  - Given a JSON object missing fields the mapping requires, when processed, then per-record quarantine fires per BR-302.
- **Originating** AD-016
- **Depends on** P1-ING-001
- **Tier** IMPORTANT · **Size** S · **Owner** Ingestion

#### P3-FMT-004 — Adapter contract test (BR-802 enforcement)
- **As** the Architecture team
  **I want** a contract test verifying that all adapters produce identical canonical output for equivalent inputs across formats
  **So that** AD-016 + BR-802 hold: the canonical schema is format-agnostic.
- **AC**
  - Given equivalent records expressed in CSV, X12 834, fixed-width, and JSON, when each is adapted + mapped, then the canonical staging records are equivalent (allowing for format-specific metadata).
  - Given a regression introducing format-specific bias, when CI runs, then the contract test fails.
- **Originating** AD-016, BR-802, R3 S-006
- **Depends on** P3-FMT-001..003
- **Tier** CRITICAL · **Size** M · **Owner** Architecture

---

### Epic TUNE — Splink Tuning at Scale

#### P3-TUNE-001 — Cross-partner ground truth set
- **As** the Identity Resolution squad
  **I want** a curated cross-partner ground truth set assembled from production data + manual review
  **So that** Splink threshold tuning at scale (P3-TUNE-002) has a defensible baseline.
- **AC**
  - Given the ground truth, when reviewed, then it has documented inclusion criteria, manual-reviewer attribution, and ≥ 1000 same-person and ≥ 1000 different-person pairs across at least 3 partners.
  - Given a tuning run against ground truth, when evaluated, then precision/recall metrics are produced.
- **Originating** RR-005, BR-104
- **Depends on** P2-SPK-004, multi-partner production data
- **Tier** CRITICAL · **Size** L · **Owner** Identity Resolution

#### P3-TUNE-002 — Re-tune thresholds against cross-partner ground truth
- **As** the Identity Resolution squad
  **I want** Splink thresholds re-tuned against the P3-TUNE-001 ground truth
  **So that** Phase 2 thresholds (tuned on synthetic + Phase 1 data) hold or are corrected at scale.
- **AC**
  - Given the re-tuning, when documented, then the precision/recall delta vs. Phase 2 is captured + the new operating point is justified.
  - Given the change, when promoted, then it follows XR-010 and emits a `CONFIG_CHANGE_PROD` audit event with reviewer principals.
- **Originating** RR-005, BR-104
- **Depends on** P3-TUNE-001
- **Tier** CRITICAL · **Size** M · **Owner** Identity Resolution

#### P3-TUNE-003 — Per-partner DQ baselines tuned
- **As** the Ingestion squad
  **I want** per-partner profile baselines tuned against several months of partner data
  **So that** BR-305 drift detection has partner-realistic baselines, not generic synthetic ones.
- **AC**
  - Given a partner with ≥ 90 days of feed history, when the baseline is tuned, then the drift-alert false-positive rate drops to < 5%.
  - Given a tuning run, when documented, then the baseline + its rationale are stored alongside the partner schema registry.
- **Originating** BR-305
- **Depends on** P1-DQ-004
- **Tier** IMPORTANT · **Size** M · **Owner** Ingestion

---

### Epic MPI — Multi-Partner Identity

#### P3-MPI-001 — Cross-partner identity correlation (BR-205)
- **As** the Identity Resolution squad
  **I want** cross-partner identity resolution: when the same person appears at two partners, the canonical identity is shared while preserving per-partner enrollment
  **So that** BR-205 holds at multi-partner scale.
- **AC**
  - Given two partners both enrolling the same person, when both feeds are processed, then one canonical_member row exists with two partner_enrollment rows.
  - Given a Tier 2 cross-partner match, when audited, then it carries `match_class=CROSS_PARTNER` + the score breakdown for explainability.
- **Originating** BR-205, BR-101
- **Depends on** P2-SPK-001..003, P3-TUNE-002
- **Tier** CRITICAL · **Size** L · **Owner** Identity Resolution

#### P3-MPI-002 — Cross-partner correlation prevention verification
- **As** the Security squad
  **I want** an automated verification that two partners' tokenized data cannot be joined externally on the token, only inside TokenizationService
  **So that** ADR-0003 per-partner salt isolation holds at scale.
- **AC**
  - Given partner-A tokenized data + partner-B tokenized data, when joined externally on token columns, then zero matches result.
  - Given the same plaintext attribute submitted to TokenizationService under both partner contexts, when tokenized, then distinct tokens emerge.
  - Given the verification, when scheduled in CI nightly, then any regression (e.g., shared salt accidentally introduced) trips the gate.
- **Originating** ADR-0003, BR-XR-005, RR-002
- **Depends on** P0-TOK-003, P2-SPK-001
- **Tier** CRITICAL · **Size** M · **Owner** Security

#### P3-MPI-003 — Multi-partner reconciliation (cross-partner total ≠ sum-of-singletons)
- **As** the Ingestion squad
  **I want** reconciliation to handle the cross-partner-merge case (one canonical, two partner_enrollments) without false alarms
  **So that** P2-REC-001 alerting at scale is signal, not noise.
- **AC**
  - Given a feed run where some staging records cross-partner-merge to existing canonicals, when reconciliation runs, then it correctly accounts for canonical-merge events as `cross_partner_merges` (not as silent loss).
  - Given a known-broken state (test injection), when reconciliation runs, then it correctly alerts.
- **Originating** BR-605, BR-205
- **Depends on** P3-MPI-001, P2-REC-001
- **Tier** IMPORTANT · **Size** S · **Owner** Ingestion

---

### Epic ISO — Per-Partner Cryptographic Isolation Validation

#### P3-ISO-001 — Per-partner KEK derivation verification
- **As** the Security squad
  **I want** a verification that per-partner KEK-derivation context labels correctly include `partner_id`
  **So that** an inadvertent shared-key bug is caught.
- **AC**
  - Given an audit of all key-derivation call sites, when reviewed, then `partner_id` is in the HKDF info parameter at every site.
  - Given a code-lint rule, when run, then any KDF call missing `partner_id` in info fails CI.
- **Originating** ADR-0003, RR-002
- **Depends on** P0-KMS-002, P0-TOK-003
- **Tier** CRITICAL · **Size** S · **Owner** Security

#### P3-ISO-002 — Per-partner audit isolation
- **As** the Audit squad
  **I want** audit events to carry partner_id in the principal context such that partner-A's reviewer cannot detok partner-B tokens
  **So that** even with cross-partner-merge, the operator-visibility boundary is partner-scoped.
- **AC**
  - Given a reviewer assigned to partner A, when they attempt to detok a partner-B-only token, then PEP denies and an audit event captures the attempt.
  - Given a reviewer working a cross-partner-merge case, when authorized, then they see a token resolvable in both partner contexts (explicit cross-partner case).
- **Originating** AD-025, BR-506
- **Depends on** P2-REV-003
- **Tier** IMPORTANT · **Size** M · **Owner** Security

---

### Epic ONB — Onboarding Path Industrialized

#### P3-ONB-001 — Sub-engineering-day onboarding (industrialized)
- **As** the Partnership Operations squad
  **I want** the partner onboarding runbook (P1-ONB-002) industrialized so onboarding takes under one engineering-day from YAML PR to live
  **So that** ARD Phase 3 exit is closed.
- **AC**
  - Given a new partner, when the runbook is followed, then the elapsed time from "YAML PR opened" to "first feed processed in prod" is < 8 engineering-hours.
  - Given a stopwatch test, when conducted on the 6th and 10th partner, then both meet the bar.
- **Originating** ARD §"Phase 3 exit", BR-801, BR-802
- **Depends on** P1-ONB-002
- **Tier** CRITICAL · **Size** L · **Owner** Partnership Operations

#### P3-ONB-002 — Per-partner ADR template + governance
- **As** the Architecture team
  **I want** a per-partner ADR template covering: data scope, format, schema, transport, mapping, retention/deletion, BAA reference
  **So that** each partner has a governed onboarding artifact (not just a YAML file).
- **AC**
  - Given a new partner onboarding, when the ADR is authored, then it is reviewed + approved before production-live.
  - Given the partner-ADR set, when reviewed in aggregate, then variation between partners is bounded (no scope creep).
- **Originating** R8 P-027, BR-801
- **Depends on** —
- **Tier** IMPORTANT · **Size** S · **Owner** Architecture

#### P3-ONB-003 — Onboarding stress test
- **As** the Platform/SRE squad
  **I want** a stress test running 3 partners onboarded back-to-back within a week
  **So that** the onboarding path holds under realistic concurrent demand.
- **AC**
  - Given the test, when run, then 3 partners are onboarded with no manual cross-partner intervention.
  - Given the test, when reviewed, then a postmortem captures any operational frictions for runbook updates.
- **Originating** ARD §"Phase 3 exit"
- **Depends on** P3-ONB-001
- **Tier** IMPORTANT · **Size** M · **Owner** Platform/SRE

---

### Epic SUB — Subprocessor Reviews

#### P3-SUB-001 — Subprocessor disclosure list per partner
- **As** the Privacy Officer
  **I want** per-partner subprocessor disclosure: which Lore subprocessors handle which partner's data
  **So that** partner-side BAA chain transparency is operational.
- **AC**
  - Given a partner, when their subprocessor list is queried, then it matches the BAA-disclosed list and counsel-approved subprocessors.
  - Given a new subprocessor coming online (e.g., new GCP service in scope), when added, then partners are notified per BAA terms.
- **Originating** BR-1101, P1-COM-004
- **Depends on** P1-COM-004
- **Tier** CRITICAL · **Size** M · **Owner** Privacy Officer

#### P3-SUB-002 — Subprocessor security review (annual)
- **As** the Security Officer
  **I want** an annual subprocessor security review (SOC 2 / HITRUST attestations collected, gaps documented)
  **So that** subprocessor risk is monitored, not assumed-static.
- **AC**
  - Given the review, when conducted, then each subprocessor's current attestation report is on file and reviewed.
  - Given a subprocessor with a material attestation gap, when identified, then a remediation or replacement plan is documented.
- **Originating** R3 S-068, BR-1101
- **Depends on** P3-SUB-001
- **Tier** IMPORTANT · **Size** M · **Owner** Security Officer

---

### Epic DEL — Partner-Side Deletion Contracts

#### P3-DEL-001 — Forward partner-side deletion notification
- **As** the Member Rights squad
  **I want** when Lore deletes a member upstream, a notification is forwarded to the affected partner per BAA terms
  **So that** partner-side data is not orphaned post-deletion.
- **AC**
  - Given a deletion of a member with active partner_enrollment, when executed, then a `MEMBER_DELETION_NOTIFY` event is emitted to the partner-notification topic with token-only payload.
  - Given the notification, when consumed by a partner integration, then the partner's documented deletion contract takes over.
- **Originating** BR-701, BR-702, P1-COM-003 (DSA)
- **Depends on** P2-DEL-001, P1-COM-003
- **Tier** CRITICAL · **Size** M · **Owner** Member Rights

#### P3-DEL-002 — Inbound partner deletion (partner notifies us)
- **As** the Member Rights squad
  **I want** a path where a partner notifies Lore that a member has revoked consent / been deleted on their side
  **So that** Lore's canonical state honors partner-driven removal per BAA terms.
- **AC**
  - Given a partner-deletion notification, when received, then it is validated, queued, and processed via the canonical deletion path with partner-driven attribution.
  - Given the audit event, when reviewed, then it carries `actor_role=partner` + the partner principal + the deletion rationale.
- **Originating** BR-701, P1-COM-003
- **Depends on** P2-DEL-001, P1-COM-003
- **Tier** CRITICAL · **Size** M · **Owner** Member Rights

#### P3-DEL-003 — Partner-side deletion contract template
- **As** the Privacy Officer + counsel
  **I want** a documented partner-side deletion contract template referenced from the DSA
  **So that** contractual obligations are uniform across partners.
- **AC**
  - Given the template, when reviewed by counsel, then it covers partner SLA for processing forwarded deletions, partner audit obligations, dispute resolution.
- **Originating** BR-701, P1-COM-003
- **Depends on** P1-COM-003
- **Tier** IMPORTANT · **Size** M · **Owner** Privacy Officer

---

### Epic OBS — Per-Partner SLO + Observability

#### P3-OBS-001 — Per-partner SLO targets + dashboard
- **As** the Platform/SRE squad
  **I want** SLO targets defined per partner (feed cadence adherence, DQ pass rate, cross-partner-merge rate) + a dashboard
  **So that** N-partner production health is observable per-partner.
- **AC**
  - Given each partner, when the dashboard renders, then the SLO targets + current burn rate are visible.
  - Given an SLO breach, when fired, then the appropriate alert tier (P1/P2) routes to the owning squad.
- **Originating** AD-021, BR-801
- **Depends on** P1-ONB-003, P0-OBS-006
- **Tier** IMPORTANT · **Size** M · **Owner** Platform/SRE

#### P3-OBS-002 — Per-partner cost attribution
- **As** the Finance + Platform/SRE
  **I want** per-partner cost attribution from GCP billing labels (Cloud Run, AlloyDB, Pub/Sub, BigQuery, Datastream)
  **So that** unit-economics decisions per partner have data, not estimation.
- **AC**
  - Given a billing month, when the report runs, then per-partner cost is allocated with documented allocation methodology.
  - Given an outlier partner (cost > N × median), when detected, then it is flagged for review.
- **Originating** R7 E-049, ARD §"Cost Engineering / FinOps"
- **Depends on** P3-OBS-001
- **Tier** IMPORTANT · **Size** M · **Owner** Platform/SRE

---

### Epic UX — Multi-Partner Reviewer Workload

#### P3-UX-001 — Reviewer queue prioritization across partners
- **As** the UX squad + Identity Resolution
  **I want** queue prioritization that balances reviewer workload across partners + age + criticality
  **So that** no partner's review queue starves and reviewer fatigue is monitored.
- **AC**
  - Given multiple active partner queues, when a reviewer claims, then the case-selection algorithm follows the documented prioritization.
  - Given reviewer-fatigue signals (claim-rate decline, error-rate increase), when detected, then a workload-rebalancing alert fires.
- **Originating** R6 U-053, BR-105
- **Depends on** P2-REV-001
- **Tier** IMPORTANT · **Size** M · **Owner** UX

#### P3-UX-002 — Partner self-service surface (if scoped)
- **As** the UX squad
  **I want** the decision on partner self-service UX (status views, self-service dashboard) made + a phase-1 surface built if scoped
  **So that** partner-side operational burden on Partnership Operations is reduced.
- **AC**
  - Given the scoping decision, when documented, then it specifies in-scope features + phasing.
  - Given the phase-1 surface, when built, then it follows XR-009 + design-system standards (P0-UX-001).
- **Originating** ARD §"Phase 3 UX", R6 U-068
- **Depends on** P0-UX-001
- **Tier** IMPORTANT · **Size** L · **Owner** UX

---

### Epic GOV — Governance at Scale

#### P3-GOV-001 — BR-802 enforcement gate (no partner-specific code)
- **As** the Architecture team
  **I want** a CI gate scanning production code for partner-id literals or partner-conditional branches
  **So that** BR-802 (no partner-specific code paths) is mechanically enforced.
- **AC**
  - Given a production code path, when scanned, then no partner literal (e.g., "PARTNER_A") appears.
  - Given the gate, when a violation is introduced, then it fails the PR with the offending file + line.
- **Originating** BR-802, ARD §"Phase 3 exit"
- **Depends on** —
- **Tier** CRITICAL · **Size** S · **Owner** Architecture

#### P3-GOV-002 — Partner config promotion automation
- **As** the Platform/SRE squad
  **I want** the per-partner config (mapping YAML, schema registry, SLO config) promoted via a single PR template
  **So that** onboarding is one PR end-to-end, not multiple repos.
- **AC**
  - Given a new partner, when the PR template is used, then all per-partner config lands in one PR with appropriate CODEOWNERS gating.
  - Given the merged PR, when CI runs, then deployment to dev/staging is automatic; prod is gated on Operations sign-off.
- **Originating** ARD §"Phase 3 exit", BR-801
- **Depends on** P3-ONB-001
- **Tier** CRITICAL · **Size** M · **Owner** Platform/SRE

---

## Phase 3 cross-track summary

| Track | Critical stories | Important / Supportive |
|-------|------------------|------------------------|
| Engineering | P3-FMT-001, P3-FMT-004, P3-TUNE-001..002, P3-MPI-001, P3-DEL-001..002, P3-GOV-001..002 | P3-FMT-002..003, P3-TUNE-003, P3-MPI-003 |
| Security | P3-MPI-002, P3-ISO-001 | P3-ISO-002, P3-SUB-002 |
| Compliance | P3-SUB-001, P3-DEL-003 | — |
| UX | — | P3-UX-001..002 |
| Infrastructure | P3-ONB-001 | P3-ONB-002..003, P3-OBS-001..002 |

## Phase 3 risk-register linkage

| Risk | Story closing it (or downgrading) |
|------|-----------------------------------|
| RR-002 (partner contract terms) | P3-DEL-003, P3-SUB-001 |
| RR-005 (Splink threshold defaults at scale) | P3-TUNE-001..002 |

---

## Out of scope for Phase 3

- Penetration testing (Phase 4)
- Comprehensive accessibility audit (Phase 4)
- DR validation drill (Phase 4 + recurring)
- BAA chain finalization across all partners (Phase 4)
- Attestation evidence pack assembly (Phase 4)
