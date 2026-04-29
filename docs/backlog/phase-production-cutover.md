# Phase 2 — Production Cutover Backlog

| Field | Value |
|-------|-------|
| **ARD reference** | §"Phased Delivery" / Phase 2 |
| **Goal** | All v1 BRs satisfied. System is production-defensible. |
| **Status** | LIVE BACKLOG |

---

## Phase 2 Goal

All v1 BRs satisfied. System is production-defensible.

## Phase 2 Entry Gate

- All Phase 1 exit criteria met (per `phase-single-partner.md`).
- Privacy Officer + Security Officer Phase 1 sign-off on file.
- First partner production traffic stable for ≥ N days (defined in Phase 1 retro; default ≥ 30 days continuous green).
- Reviewer interface decision (RR-010) closed via P0-ADR-003.
- Member portal scope decision (RR-009) closed via P0-ADR-002.
- Brute-force friction mechanism decision closed via P0-ADR-004.

## Phase 2 Exit Criteria (per ARD)

- Every BR in the BRD is satisfied with passing tests.
- Hash chain validator runs continuously, no breaks; external anchors verified.
- Deletion ledger suppression demonstrated end-to-end on synthetic re-introduction scenarios.
- Splink match weights are reproducible across runs given fixed configuration (per R2 F-135).
- All `[ADVISORY]` BRs have a documented process owner and review cadence.
- Member rights workflow tested end-to-end (synthetic member submitting Right of Access; fulfillment within SLA).
- Member rights `[ADVISORY]` enforcement plan documented (counsel + compliance program ownership).
- HIPAA Privacy Rule infrastructure operational (NPP delivery, complaints, authorization tracking).
- Breach notification templates approved by counsel; tabletop exercise completed.
- 50-state breach notification matrix authored.
- Annual third-party security review completed (or scheduled).
- Two-person authorization for high-risk operations LIVE (AD-026).

---

## Epics

| Key | Epic | Description |
|-----|------|-------------|
| SPK | Splink Integration | Tier 2/3/4 probabilistic matching with explainable weights |
| REV | Manual Review Queue + Reviewer Interface | Queue, UI, decision support |
| BFP | Brute Force Protection | BR-402 progression, friction challenge, lockout |
| DEL | Deletion Workflow + Ledger | BR-701..704; HMAC-keyed ledger; suppression LIVE |
| REC | Reconciliation Jobs | Cross-stage row-count + state-coherence validation |
| DRF | Drift Detection (Enhanced) | Schema + profile drift with auto-quarantine |
| ANC | Audit Chain Hardening | GCS Bucket Lock retention LOCKED; chain validator continuous |
| MR  | Member Rights Workflows | BR-901..908 + BR-1301..1308 LIVE |
| UMR | Unmerge / Canonical Split | AD-033 — split a wrongly-merged canonical identity |
| TWP | Two-Person Authorization | AD-026 LIVE for deletion-override + Vault-admin actions |
| COM | Compliance Phase 2 | Breach notification (federal + 50-state), training program LIVE, third-party security review |
| UX  | UX Phase 2 | Reviewer interface, audit-forensic-search UX, member portal phase-1 |
| ADV | `[ADVISORY]` BR Owners | Document process owner + review cadence per advisory rule |
| BRR | BR Coverage Closure | Final pass: every BR has implementing story + passing test |

---

## Stories

### Epic SPK — Splink Integration

#### P2-SPK-001 — Splink Runner (Cloud Run job, batch)
- **As** the Identity Resolution squad
  **I want** a Splink-on-DuckDB runner deployed as a Cloud Run job, triggered per match-orchestrator request
  **So that** Tier 2/3/4 probabilistic matching runs against canonical state with bounded compute envelope.
- **AC**
  - Given a batch of staging records + the canonical mirror, when the runner executes, then it produces match predictions with per-pair `match_weight` and `bf_<comparison>` decompositions.
  - Given a fixed configuration + fixed input, when run twice, then identical predictions emit (R2 F-135 reproducibility).
  - Given a runner crash, when it restarts, then it idempotently resumes (per ADR-0005 idempotency contract).
- **Originating** BR-101 (Tier 2/3/4), BR-104, AD-011, AD-012
- **Depends on** P1-CAN-001, P1-IDR-001
- **Tier** CRITICAL · **Size** L · **Owner** Identity Resolution

#### P2-SPK-002 — Tier evaluation policy (BR-101 Tier 2/3/4 routing)
- **As** the Identity Resolution squad
  **I want** a tier-evaluation policy that routes Splink predictions to MERGE / REVIEW / DISTINCT based on `MATCH_THRESHOLD_HIGH` and `MATCH_THRESHOLD_REVIEW`
  **So that** BR-101 holds: Tier 2 auto-merges; Tier 3 enters review; Tier 4 stays distinct.
- **AC**
  - Given a Splink prediction with `match_weight ≥ MATCH_THRESHOLD_HIGH`, when evaluated, then it auto-merges and emits `MATCH_TIER_2` with the score breakdown.
  - Given a Splink prediction with `MATCH_THRESHOLD_REVIEW ≤ match_weight < MATCH_THRESHOLD_HIGH`, when evaluated, then it lands in the review queue.
  - Given a Splink prediction with `match_weight < MATCH_THRESHOLD_REVIEW`, when evaluated, then it is treated as DISTINCT (no merge, no queue).
- **Originating** BR-101, BR-104, RR-005
- **Depends on** P2-SPK-001, P0-CFG-001
- **Tier** CRITICAL · **Size** M · **Owner** Identity Resolution

#### P2-SPK-003 — Match Orchestrator (Cloud Run service, Pub/Sub)
- **As** the Identity Resolution squad
  **I want** a Cloud Run service consuming canonical-staging events and orchestrating: Tier 1 deterministic → Splink runner if needed → Tier evaluation → outcome publish
  **So that** identity resolution is a single coordinated pipeline rather than a chain of cron jobs.
- **AC**
  - Given a canonical-staging event, when consumed, then the orchestrator runs Tier 1 first, only invokes Splink if Tier 1 didn't resolve, applies Tier evaluation, and publishes the resolved-event.
  - Given a stuck pair (orchestrator timeout), when investigated, then it lands in dead-letter with full context for manual triage.
- **Originating** AD-011, ADR-0007 (Cloud Run Pub/Sub push), R5 D-046
- **Depends on** P2-SPK-001, P2-SPK-002, P1-IDR-001
- **Tier** CRITICAL · **Size** L · **Owner** Identity Resolution

#### P2-SPK-004 — Splink threshold tuning + ground truth
- **As** the Identity Resolution squad + ML lead
  **I want** Splink thresholds tuned against synthetic + early-production ground truth with documented precision/recall
  **So that** RR-005 is closed with evidence and BR-104 thresholds are defensible.
- **AC**
  - Given a labeled ground-truth set (P1-TST-001 + production samples), when thresholds are tuned, then chosen `MATCH_THRESHOLD_HIGH` produces ≥ 99% precision on Tier 2 and `MATCH_THRESHOLD_REVIEW` produces a balanced review-queue volume.
  - Given the tuning, when documented, then the precision/recall curve + chosen operating points are in an ADR or BR-104 evidence file.
  - Given a future tuning change, when applied, then it follows the XR-010 promotion path with audit emission.
- **Originating** RR-005, BR-104, R2 F-135
- **Depends on** P2-SPK-001, P2-SPK-002, P1-TST-001
- **Tier** CRITICAL · **Size** M · **Owner** Identity Resolution

#### P2-SPK-005 — Match-weight reproducibility test gate
- **As** the Identity Resolution squad
  **I want** a CI gate that runs a fixed-seed Splink test and asserts byte-identical predictions across runs
  **So that** R2 F-135 (reproducibility) is enforced continuously.
- **AC**
  - Given the gate, when run on a clean repo, then predictions are byte-identical across runs.
  - Given a regression (non-determinism introduced), when CI runs, then the gate fails with the diff.
- **Originating** R2 F-135, BR-104
- **Depends on** P2-SPK-001
- **Tier** CRITICAL · **Size** S · **Owner** Identity Resolution

---

### Epic REV — Manual Review Queue + Reviewer Interface

#### P2-REV-001 — Review queue table + service API
- **As** the Identity Resolution squad
  **I want** the `review_queue` table populated by Tier 3 outcomes + a service API for reviewer actions
  **So that** BR-105 (manual review queue) is implemented with stable enqueue/dequeue contracts.
- **AC**
  - Given a Tier 3 outcome from match orchestrator, when persisted, then a `review_queue` row is created with score breakdown + correlation_id.
  - Given a reviewer claim action, when issued, then exactly one reviewer holds the lock (advisory lock prevents double-handling).
  - Given a reviewer-resolve action (MERGE / KEEP_DISTINCT / NEEDS_MORE), when issued, then it audits, updates `match_decision`, and either auto-applies the merge or routes back to orchestrator.
- **Originating** BR-105, AD-011
- **Depends on** P2-SPK-002, P1-CAN-001
- **Tier** CRITICAL · **Size** L · **Owner** Identity Resolution

#### P2-REV-002 — Reviewer interface frontend (per `[reviewer-decision-support]` ADR)
- **As** the UX squad + Identity Resolution
  **I want** a reviewer web UI rendering: side-by-side records (tokenized), score breakdown (per-comparison weights), action controls
  **So that** BR-105 + R6 U-017 hold and reviewers can resolve cases efficiently.
- **AC**
  - Given a Tier 3 review case, when rendered, then the side-by-side comparison shows tokenized fields (no plaintext) and per-comparison weights.
  - Given keyboard-only navigation, when used, then full review-flow is reachable (XR-009 WCAG 2.1 AA).
  - Given a usability test with synthetic Tier-3 cases, when run, then 80%+ of synthetic reviewers resolve correctly with rationale.
- **Originating** BR-105, R6 U-017, P0-ADR-003
- **Depends on** P2-REV-001, P0-ADR-003, P0-UX-001
- **Tier** CRITICAL · **Size** XL · **Owner** UX
- **Note** Splittable: P2-REV-002a (read-only render), P2-REV-002b (action controls), P2-REV-002c (a11y hardening).

#### P2-REV-003 — Reviewer authentication + RBAC (BR-105, AD-025)
- **As** the Security squad
  **I want** reviewer access enforced via PEP/PDP with role `reviewer` (BRD taxonomy)
  **So that** AD-025 holds and only authorized reviewers can resolve cases.
- **AC**
  - Given a non-reviewer principal, when accessing the reviewer UI, then PEP denies before the UI renders any case.
  - Given a reviewer principal, when accessing only their assigned cases (or the open queue), then access is allowed.
  - Given a reviewer's session, when audited, then every action carries `actor_role=reviewer` + principal in the audit event.
- **Originating** AD-025, BR-105, R3 S-058
- **Depends on** P2-REV-001
- **Tier** CRITICAL · **Size** M · **Owner** Security

#### P2-REV-004 — Reviewer SLA + queue-health dashboard
- **As** the Operations team
  **I want** a dashboard showing queue depth, oldest unresolved case age, reviewer throughput
  **So that** SLA breaches are detected before they become member-impacting.
- **AC**
  - Given the dashboard, when queue depth exceeds `REVIEW_QUEUE_DEPTH_ALERT`, then a P2 alert fires.
  - Given oldest case age > `REVIEW_QUEUE_AGE_ALERT_HRS`, then a P1 alert fires.
- **Originating** R8 P-008, R6 U-053
- **Depends on** P2-REV-001, P0-OBS-006
- **Tier** IMPORTANT · **Size** S · **Owner** Operations

---

### Epic BFP — Brute Force Protection

#### P2-BFP-001 — Per-claim rate-limit cache (Memorystore Redis)
- **As** the Verification squad
  **I want** a Memorystore Redis cluster holding per-claim failure counters and rate-limit windows
  **So that** BR-402 progression has a low-latency state store.
- **AC**
  - Given a verification request, when handled, then the rate-limit lookup completes in < 5ms p99.
  - Given the Redis cluster, when reviewed, then it is inside the prod VPC-SC perimeter, with TLS, and auth enabled.
- **Originating** BR-402, AD-024
- **Depends on** P0-VPC-001, P1-VER-001
- **Tier** CRITICAL · **Size** M · **Owner** Verification

#### P2-BFP-002 — First-failure rate limiting (BR-402 first tier)
- **As** the Verification squad
  **I want** first-failure rate limits applied per-claim within a rolling window
  **So that** BR-402 first-tier progression is enforced.
- **AC**
  - Given N+1 failed verifications for the same claim within the window, when issued, then the (N+1)th is rate-limited (response: NOT_VERIFIED, latency-floor enforced).
  - Given a successful verification, when followed by a failure, then the counter behavior matches the BR-402 spec.
- **Originating** BR-402
- **Depends on** P2-BFP-001
- **Tier** CRITICAL · **Size** S · **Owner** Verification

#### P2-BFP-003 — Second-failure friction challenge (per `[friction-mechanism]` ADR)
- **As** the Verification squad
  **I want** the friction challenge from P0-ADR-004 implemented and triggered on second-failure
  **So that** BR-402 second-tier progression is enforced.
- **AC**
  - Given a second failure, when handled, then HTTP 401 + a friction-challenge token is returned (padded to fixed length per ADR-0009 §3).
  - Given a friction-challenge response, when the member completes the challenge, then a fresh verification attempt is allowed.
  - Given an accessibility audit, when run on the friction surface, then it passes WCAG 2.1 AA.
- **Originating** BR-402, P0-ADR-004, XR-009
- **Depends on** P0-ADR-004, P2-BFP-002, P1-VER-004
- **Tier** CRITICAL · **Size** L · **Owner** Verification

#### P2-BFP-004 — Third-failure lockout
- **As** the Verification squad
  **I want** a third-failure lockout with `LOCKOUT_DURATION_MINUTES` configured
  **So that** BR-402 / BR-403 third-tier protection is enforced.
- **AC**
  - Given a third failure, when handled, then the claim is locked out for the configured duration; subsequent verifications return NOT_VERIFIED with the same response shape.
  - Given an in-lockout claim attempting verification, when handled, then the lockout is enforced (no leakage of "you're locked out") — same shape, same latency.
  - Given a documented operator path (P1-UX-002 lockout recovery service blueprint), when followed, then a member can recover access.
- **Originating** BR-402, BR-403, P1-UX-002
- **Depends on** P2-BFP-002, P2-BFP-003
- **Tier** CRITICAL · **Size** M · **Owner** Verification

#### P2-BFP-005 — Lockout recovery service (operator path) LIVE
- **As** the Operations team
  **I want** a documented + tooled lockout-recovery procedure (operator action: identity-proof + restore)
  **So that** BR-1308 holds operationally.
- **AC**
  - Given a member contacting the lockout recovery channel, when their identity is proven per the standard, then an operator can clear the lockout via an audited admin action.
  - Given the admin action, when audited, then it carries actor, member token, identity-proof method, justification, two-person review (if required by AD-026 for the action class).
- **Originating** BR-1308, P1-UX-002
- **Depends on** P2-BFP-004, P1-UX-002, P2-TWP-001
- **Tier** CRITICAL · **Size** M · **Owner** Operations

---

### Epic DEL — Deletion Workflow + Ledger + Suppression

#### P2-DEL-001 — Deletion request API + workflow
- **As** the Member Rights squad
  **I want** an API + workflow accepting deletion requests, validating identity, executing the deletion sequence, emitting audit events
  **So that** BR-701 is implemented with a clean boundary.
- **AC**
  - Given an authenticated deletion request, when validated, then the request is queued and a `DELETION_REQUESTED` audit event is emitted.
  - Given the workflow, when it executes, then the sequence is: vault tombstone → canonical record nulling → ledger insert → audit emission, in a saga that is replayable.
  - Given the workflow, when reviewed, then it is idempotent (a re-submitted deletion for the same member is a no-op for already-deleted state).
- **Originating** BR-701, BR-702, BR-703, ADR-0003
- **Depends on** P1-TOK-002, P1-CAN-001, P1-AUD-001
- **Tier** CRITICAL · **Size** L · **Owner** Member Rights

#### P2-DEL-002 — Deletion ledger HMAC-keyed (ADR-0003)
- **As** the Security squad
  **I want** the deletion_ledger entries hashed via HMAC-keyed-SHA-256 (not bare salted SHA-256)
  **So that** ADR-0003 holds: an attacker with read access to the ledger cannot brute-force identity-hashes via dictionary attack on common identity-tuples.
- **AC**
  - Given a deletion, when the ledger entry is computed, then it uses HMAC keyed by an HSM-bound secret (per ADR-0003) — not a stored salt.
  - Given two ledger entries for the same identity-tuple, when compared, then they are byte-identical (deterministic-by-design).
  - Given an attacker with read access to the ledger but no HSM key, when they attempt brute force, then the entries are computationally indistinguishable from random.
- **Originating** ADR-0003, BR-703
- **Depends on** P0-KMS-002, P2-DEL-001
- **Tier** CRITICAL · **Size** S · **Owner** Security

#### P2-DEL-003 — Deletion suppression-on-reingest LIVE
- **As** the Identity Resolution squad
  **I want** the pre-publication ledger consult (P1-IDR-003 stub) replaced with a LIVE check against the HMAC-keyed ledger
  **So that** BR-703 holds: a re-introduced deleted identity is suppressed.
- **AC**
  - Given a deletion executed at time T, when a re-introduction feed arrives at T+Δ, then the staging record's identity-hash matches a ledger entry and routes to `SUPPRESSED_DELETED`.
  - Given a suppression, when audited, then it carries the original deletion's correlation_id (forensic linkage) and a `SUPPRESSED_REINGEST` event emits.
  - Given an operator override (BR-704), when invoked, then a `DELETION_OVERRIDE` event emits with two-person authorization and the suppression is bypassed.
- **Originating** BR-703, BR-704, ADR-0003
- **Depends on** P2-DEL-001, P2-DEL-002, P1-IDR-003, P2-TWP-001
- **Tier** CRITICAL · **Size** M · **Owner** Identity Resolution

#### P2-DEL-004 — Deletion executor (Cloud Run job, scheduled)
- **As** the Member Rights squad
  **I want** a Cloud Run job draining the deletion queue with bounded batch size and per-step audit
  **So that** the deletion saga executes asynchronously without blocking the request path.
- **AC**
  - Given a deletion queue with N entries, when the job runs, then it processes them with bounded concurrency (default 5) and emits per-step audit.
  - Given a partial failure mid-saga, when the job restarts, then it resumes the in-flight saga at the right step (idempotency at each step).
- **Originating** BR-701, ADR-0007
- **Depends on** P2-DEL-001, P2-DEL-002, P2-DEL-003
- **Tier** CRITICAL · **Size** M · **Owner** Member Rights

#### P2-DEL-005 — Deletion fulfillment SLA + dashboard
- **As** the Privacy Officer
  **I want** a dashboard showing time-to-fulfill for deletion requests + an SLA gate (e.g., 30 days HIPAA-aligned)
  **So that** BR-701 SLA is observable.
- **AC**
  - Given a deletion request, when its lifecycle is tracked, then time-to-fulfill is computed and surfaced.
  - Given any deletion approaching SLA breach, when detected, then a P1 alert fires for Privacy Officer.
- **Originating** BR-701, R6 U-007
- **Depends on** P2-DEL-001, P0-OBS-006
- **Tier** IMPORTANT · **Size** S · **Owner** Privacy Officer

---

### Epic REC — Reconciliation Jobs

#### P2-REC-001 — Cross-stage reconciliation (rows-in vs. rows-out)
- **As** the Ingestion squad
  **I want** a daily reconciliation job that asserts: feed rows = canonical inserts + canonical updates + quarantines + suppressed-deletions + reviews-pending
  **So that** BR-605 holds at the daily roll-up scale.
- **AC**
  - Given a day's processing, when the job runs, then the equality holds; otherwise a P1 alert fires with per-stage counts.
  - Given a known-broken run (deliberate test), when the job runs, then the alert fires correctly.
- **Originating** BR-605
- **Depends on** P1-DQ-005, P1-CAN-005
- **Tier** CRITICAL · **Size** M · **Owner** Ingestion

#### P2-REC-002 — Vault ↔ canonical reconciliation
- **As** the Vault squad
  **I want** a daily check that every token referenced in canonical_member exists in the vault and vice versa
  **So that** orphan tokens / orphan vault rows are detected within 24 hours.
- **AC**
  - Given the check, when run, then orphan tokens (canonical refs missing in vault) and orphan vault rows (vault refs missing in canonical) are zero in steady state.
  - Given a non-zero count, when alerted, then the on-call has a runbook to triage (deletion in flight, race condition, etc.).
- **Originating** BR-502, BR-605
- **Depends on** P1-TOK-001, P1-CAN-001
- **Tier** IMPORTANT · **Size** M · **Owner** Vault

---

### Epic DRF — Drift Detection Enhanced

#### P2-DRF-001 — Profile drift auto-quarantine path
- **As** the Ingestion squad
  **I want** profile drift exceeding `PROFILE_DRIFT_QUARANTINE_PCT` to feed-quarantine instead of just alert
  **So that** BR-305 has a hard-fail path when degradation is severe.
- **AC**
  - Given a feed with profile drift > the quarantine threshold, when processed, then the feed is quarantined (not just alerted) and partner-onboarding is paged.
  - Given a feed within drift tolerance, when processed, then it proceeds normally.
- **Originating** BR-305
- **Depends on** P1-DQ-004
- **Tier** IMPORTANT · **Size** S · **Owner** Ingestion

#### P2-DRF-002 — Schema drift PR-driven contract update
- **As** the Ingestion squad
  **I want** ADDITIVE schema drift to auto-open a PR proposing the schema-registry update + a notification to partner-onboarding
  **So that** BR-304 makes drift visible and reviewable, not silently swallowed.
- **AC**
  - Given an ADDITIVE drift detection, when processed, then a PR is auto-opened containing the registry update, with the drift evidence in the description.
  - Given the PR, when merged, then the schema registry is updated and a `SCHEMA_REGISTRY_UPDATE` audit event emits.
- **Originating** BR-304
- **Depends on** P1-DQ-003, P1-ONB-001
- **Tier** IMPORTANT · **Size** M · **Owner** Ingestion

---

### Epic ANC — Audit Chain Hardening

#### P2-ANC-001 — GCS Bucket Lock retention LOCKED
- **As** the Audit squad
  **I want** the GCS audit-chain bucket retention policy LOCKED (irrevocable retention)
  **So that** ADR-0008 §1 holds: bucket retention cannot be reduced, even by an org admin.
- **AC**
  - Given the bucket, when its retention policy is queried, then `effective` is `true` and `retention_period` is set to the BR-503 minimum (≥ 6 years).
  - Given an attempt to reduce retention, when made, then GCS denies (Bucket Lock prevents).
- **Originating** ADR-0008, BR-503, BR-504
- **Depends on** P0-DAT-005, P1-AUD-003
- **Tier** CRITICAL · **Size** S · **Owner** Audit

#### P2-ANC-002 — Anchor verification gate (chain ↔ Compliance-org registry)
- **As** the Audit squad
  **I want** an hourly verification that each anchor in the Compliance-org registry matches the chain head at that snapshot
  **So that** ADR-0008 §4 holds.
- **AC**
  - Given an anchor mismatch, when detected, then the forensic preservation procedure (P1-ANC-004) auto-triggers.
  - Given a match, when verified, then a `ANCHOR_VERIFIED` metric advances.
- **Originating** ADR-0008 §4
- **Depends on** P1-ANC-001, P1-ANC-002
- **Tier** CRITICAL · **Size** M · **Owner** Audit

---

### Epic MR — Member Rights Workflows

#### P2-MR-001 — Right of Access workflow (BR-903)
- **As** the Member Rights squad
  **I want** a Right of Access workflow (request → identity-proof → assemble PHI → deliver in chosen format) within HIPAA SLA
  **So that** BR-903 holds end-to-end.
- **AC**
  - Given a member-submitted Right of Access request, when validated, then the assembly job runs and produces a deliverable in member-chosen format (PDF, secure download, etc.).
  - Given the SLA window (default 30 days; configurable), when fulfillment exceeds the threshold, then a P1 alert fires.
  - Given a delivery, when audited, then the audit event records the format, delivery channel, and acknowledgment.
- **Originating** BR-903
- **Depends on** P0-ADR-002, P1-UX-003
- **Tier** CRITICAL · **Size** XL · **Owner** Member Rights

#### P2-MR-002 — Authorization tracking (BR-902)
- **As** the Member Rights squad
  **I want** a service tracking active member authorizations (purpose, scope, expiration, revocation)
  **So that** BR-902 + HIPAA §164.508 hold.
- **AC**
  - Given an authorization, when registered, then it is queryable by member token, scope, expiration.
  - Given an expired authorization, when accessed-against, then access is denied and a `AUTHZ_EXPIRED` audit fires.
  - Given a revocation, when issued, then dependent uses/disclosures stop within `AUTHZ_REVOCATION_PROPAGATION_SECONDS`.
- **Originating** BR-902
- **Depends on** P1-CAN-001
- **Tier** CRITICAL · **Size** L · **Owner** Member Rights

#### P2-MR-003 — Complaint workflow (BR-908)
- **As** the Member Rights squad + Privacy Officer
  **I want** a complaint submission + triage workflow with documented response SLAs
  **So that** BR-908 holds.
- **AC**
  - Given a complaint, when submitted, then a ticket lands in the Privacy Officer queue with auto-acknowledgment to the member.
  - Given the workflow, when reviewed, then it covers acknowledgment SLA, resolution SLA, retention of complaint records, and counsel-escalation triggers.
- **Originating** BR-908
- **Depends on** P1-COM-001, P1-UX-003
- **Tier** CRITICAL · **Size** L · **Owner** Member Rights

#### P2-MR-004 — Right to amend (BR-904) — `[ADVISORY]` decision
- **As** the Privacy Officer
  **I want** the BR-904 advisory closure: who owns the amendment workflow, what auth path, what review cadence
  **So that** the `[ADVISORY]` is no longer floating.
- **AC**
  - Given the closure document, when reviewed, then it specifies process owner, intake channel, decision authority, audit + retention model.
  - Given a member-submitted amendment, when handled per the documented process, then an audit event fires and the member receives the response within SLA.
- **Originating** BR-904 (ADVISORY)
- **Depends on** P0-COM-001
- **Tier** IMPORTANT · **Size** M · **Owner** Privacy Officer

#### P2-MR-005 — Right to accounting of disclosures (BR-905)
- **As** the Member Rights squad
  **I want** an accounting-of-disclosures query reading from BigQuery `audit_event` filtered to disclosure-class events
  **So that** BR-905 / HIPAA §164.528 holds.
- **AC**
  - Given a member request, when handled, then the accounting covers the BR-defined window (default 6 years) and includes all disclosure-class events.
  - Given the accounting, when delivered, then it follows BR-1306 portal pattern or BR-903-style fulfillment depending on the member's choice.
- **Originating** BR-905
- **Depends on** P1-AUD-002, P0-DAT-004
- **Tier** CRITICAL · **Size** L · **Owner** Member Rights

#### P2-MR-006 — Right to restrict + confidential communications (BR-906, BR-907)
- **As** the Member Rights squad
  **I want** workflows for BR-906 (restriction request) and BR-907 (confidential communications)
  **So that** the full HIPAA member-rights surface is implemented.
- **AC**
  - Given a restriction request, when granted (per Privacy Officer + counsel decision), then the canonical member carries the restriction flag + scope, and downstream disclosure paths honor it.
  - Given a confidential-communications request, when granted, then the member's contact-channel preference is honored across all member-facing communications.
- **Originating** BR-906, BR-907
- **Depends on** P1-CAN-001, P2-MR-002
- **Tier** CRITICAL · **Size** L · **Owner** Member Rights

#### P2-MR-007 — Personal Representative service (BR-1303)
- **As** the Member Rights squad
  **I want** a Personal-Representative-of-record service with documented onboarding + state-law variance handling
  **So that** BR-1303 holds.
- **AC**
  - Given a personal-rep registration, when validated, then the rep is recorded with scope + state-law-acknowledged document + expiration if any.
  - Given a personal-rep acting on behalf of a member, when audited, then the action's actor records both the rep's principal and the represented member token.
- **Originating** BR-1303, BR-1009 (state law)
- **Depends on** P2-MR-002
- **Tier** CRITICAL · **Size** L · **Owner** Member Rights

#### P2-MR-008 — Compliance dashboard (member rights queues)
- **As** the Privacy Officer
  **I want** a dashboard of all active member-rights workflows: queue depth, SLA-burn, oldest unresolved
  **So that** BR-1201/BR-1202 review surface is operational.
- **AC**
  - Given active workflows, when the dashboard renders, then per-workflow queues + SLA timers are visible.
  - Given any SLA-burn warning, when fired, then it pages Privacy Officer.
- **Originating** BR-1201, BR-1202, R8 P-008
- **Depends on** P2-MR-001..007, P0-OBS-006
- **Tier** IMPORTANT · **Size** M · **Owner** Privacy Officer

---

### Epic UMR — Unmerge / Canonical Identity Split

#### P2-UMR-001 — Unmerge service (AD-033)
- **As** the Identity Resolution squad
  **I want** a service that splits a previously-merged canonical identity back into two distinct canonicals with the original partner_enrollment + history reattached
  **So that** AD-033 holds: a wrong merge is recoverable without data loss.
- **AC**
  - Given a merged canonical with two underlying partner_enrollments, when unmerged, then the result is two canonicals with the partner_enrollments correctly reattached + member_history split coherently.
  - Given the unmerge, when audited, then it emits a `CANONICAL_SPLIT` event with the operator + rationale + two-person review.
  - Given a downstream consumer (BigQuery analytical), when it observes the split, then dependent rows update consistently.
- **Originating** AD-033, BR-103
- **Depends on** P1-CAN-002, P1-CAN-003, P2-TWP-001
- **Tier** CRITICAL · **Size** XL · **Owner** Identity Resolution

#### P2-UMR-002 — Unmerge runbook + UX
- **As** the Operations team + UX
  **I want** a documented runbook + supporting UI for the unmerge action
  **So that** the operator path is safe-by-default and reviewable.
- **AC**
  - Given the runbook, when followed, then the operator can split a canonical with confidence and full audit trail.
  - Given the UI, when rendered, then it shows pre/post state preview before commit and requires two-person sign-off.
- **Originating** AD-033, R6 U-074
- **Depends on** P2-UMR-001, P2-TWP-001
- **Tier** IMPORTANT · **Size** L · **Owner** Operations

---

### Epic TWP — Two-Person Authorization

#### P2-TWP-001 — Two-person authorization framework (AD-026)
- **As** the Security squad
  **I want** a generic two-person-authorization framework supporting: action class registry, principal pair selection, time-bounded approval window, audit emission
  **So that** AD-026 is implemented once and reused for deletion-override, Vault admin, unmerge, IaC prod-apply.
- **AC**
  - Given an action requiring two-person auth, when one principal initiates, then a second principal must approve within `TWO_PERSON_APPROVAL_WINDOW_MINUTES` for the action to execute.
  - Given the same principal attempting both initiate + approve, when detected, then the action is blocked + a security alert fires.
  - Given an executed action, when audited, then both principals are recorded with timestamps + the action class.
- **Originating** AD-026, BR-702, R3 S-029
- **Depends on** P0-IAM-002
- **Tier** CRITICAL · **Size** L · **Owner** Security

#### P2-TWP-002 — Action class registry (which actions require two-person)
- **As** the Security squad
  **I want** a documented + enforced registry of two-person-required actions
  **So that** scope is unambiguous.
- **AC**
  - Given the registry, when reviewed, then it includes: deletion-override, Vault key admin, IaC prod-apply, canonical unmerge, mass canonical mutation, KEK rotation.
  - Given a code path attempting a registered action without invoking the framework, when CI lints, then it fails (custom check verifies action-class decoration).
- **Originating** AD-026
- **Depends on** P2-TWP-001
- **Tier** CRITICAL · **Size** S · **Owner** Security

---

### Epic COM — Compliance Phase 2

#### P2-COM-001 — Breach notification infrastructure (federal)
- **As** the Privacy Officer + Security Officer
  **I want** breach-notification infrastructure: detection → severity classification → counsel review → notification template → individual + HHS + media flows
  **So that** BR-1001..1010 is operational and HIPAA Breach Notification Rule timelines are achievable.
- **AC**
  - Given a synthetic breach scenario, when triggered in tabletop, then the team executes the full chain within drill bounds with documented evidence.
  - Given the templates, when reviewed by counsel, then they are signed off and stored in the documentation retention store.
- **Originating** BR-1001..1010
- **Depends on** P0-COM-001, P0-COM-002, P0-COM-009
- **Tier** CRITICAL · **Size** XL · **Owner** Privacy Officer

#### P2-COM-002 — 50-state breach notification matrix (BR-1009)
- **As** the Privacy Officer + counsel
  **I want** a state-law matrix mapping each US state's breach-notification statute to: timing, harm threshold, notification recipients, AG-notification trigger, residual delta vs. HIPAA federal floor
  **So that** BR-1009 holds and breach response is jurisdiction-aware.
- **AC**
  - Given the matrix, when reviewed, then all 50 states + DC + applicable territories are present with counsel sign-off.
  - Given a synthetic breach scenario in state X, when the matrix is applied, then the correct notification path is generated automatically.
- **Originating** BR-1009
- **Depends on** P2-COM-001
- **Tier** CRITICAL · **Size** L · **Owner** Privacy Officer

#### P2-COM-003 — Tabletop breach exercise
- **As** the Privacy Officer + Security Officer
  **I want** a documented tabletop breach exercise executed
  **So that** ARD Phase 2 exit is closed with evidence the team can execute.
- **AC**
  - Given the exercise plan, when run, then the team produces a postmortem with action items.
  - Given the postmortem, when reviewed, then identified gaps result in BRD/runbook updates within 30 days.
- **Originating** ARD §"Phase 2 exit", BR-1010
- **Depends on** P2-COM-001, P2-COM-002
- **Tier** CRITICAL · **Size** L · **Owner** Privacy Officer

#### P2-COM-004 — Workforce HIPAA training program LIVE (BR-1103)
- **As** the Privacy Officer
  **I want** a workforce HIPAA training program with curriculum, completion tracking, refresher cadence
  **So that** BR-1103 holds.
- **AC**
  - Given a workforce member, when onboarded, then they complete training within `WORKFORCE_TRAINING_ONBOARDING_DAYS` and the completion is recorded.
  - Given the cadence (annual), when triggered, then existing workforce receives + completes refresher; non-completion triggers access-revocation per BR-1104 sanctions.
- **Originating** BR-1103, BR-1104
- **Depends on** P0-COM-005
- **Tier** CRITICAL · **Size** L · **Owner** Privacy Officer

#### P2-COM-005 — Annual third-party security review scheduled
- **As** the Security Officer
  **I want** an annual third-party security review scheduled (or completed)
  **So that** ARD Phase 2 exit is closed.
- **AC**
  - Given the engagement, when contracted, then scope, scheduled date, deliverable expectations are documented.
  - Given the review (when conducted), when reviewed, then findings are tracked to closure.
- **Originating** ARD §"Phase 2 exit", R3 S-052
- **Depends on** P0-COM-008
- **Tier** CRITICAL · **Size** M · **Owner** Security Officer

#### P2-COM-006 — Specialized data categories handling (BR-1401..1404)
- **As** the Privacy Officer
  **I want** documented handling for specialized data categories: 42 CFR Part 2 (per P0-ADR-001), GINA, COPPA, sensitive HIV/STI
  **So that** BR-1401..1404 hold with explicit per-category policies.
- **AC**
  - Given a record matching a specialized category, when ingested, then it is routed per the documented per-category policy (segregation, additional consent, etc.).
  - Given the policies, when reviewed, then counsel sign-off is documented.
- **Originating** BR-1401, BR-1402, BR-1403, BR-1404
- **Depends on** P0-ADR-001, P0-COM-007
- **Tier** CRITICAL · **Size** L · **Owner** Privacy Officer

---

### Epic UX — UX Phase 2

#### P2-UX-001 — Reviewer interface a11y + decision support (full)
- (See P2-REV-002 for the build; a11y hardening is a sub-story.)

#### P2-UX-002 — Audit log forensic search UX
- **As** the Security squad + UX
  **I want** a forensic-search UI over BigQuery audit_event with filters: actor, target token, event class, time range, correlation_id
  **So that** R6 U-037 holds and incident response is faster than raw SQL.
- **AC**
  - Given a forensic question (e.g., "all detok events on member token X in the last 30 days"), when entered, then results render in < 5s with paginated drill-down.
  - Given the UI, when audited, then access to the UI itself emits an `AUDIT_LOG_ACCESS` event.
- **Originating** R6 U-037, BR-503
- **Depends on** P0-DAT-004, P1-AUD-002
- **Tier** IMPORTANT · **Size** L · **Owner** UX

#### P2-UX-003 — Member portal phase-1 functionality
- **As** the UX squad
  **I want** the member portal phase-1 surface (per P0-ADR-002 scope): submit Right of Access, submit complaint, view authorization status
  **So that** BR-1306 holds at phase-1 scope.
- **AC**
  - Given a member, when authenticated to the portal, then the in-scope rights workflows are usable end-to-end.
  - Given a usability test, when run with synthetic personas, then 80%+ complete each workflow without help.
  - Given an accessibility audit, when run, then it passes WCAG 2.1 AA.
- **Originating** BR-1306, P0-ADR-002, R6 U-068
- **Depends on** P0-ADR-002, P1-UX-003, P2-MR-001, P2-MR-003
- **Tier** CRITICAL · **Size** XL · **Owner** UX
- **Note** Splittable: P2-UX-003a (auth + rights submit), P2-UX-003b (status views), P2-UX-003c (a11y hardening).

---

### Epic ADV — `[ADVISORY]` BR Owners

#### P2-ADV-001 — Document process owner + cadence per `[ADVISORY]` BR
- **As** the Compliance squad
  **I want** every `[ADVISORY]` BR in the BRD to carry: process owner, review cadence, escalation path
  **So that** ARD Phase 2 exit ("All `[ADVISORY]` BRs have documented process owner and review cadence") is closed.
- **AC**
  - Given the BRD, when the audit script runs, then every `[ADVISORY]`-marked rule has the three fields populated.
  - Given a missing field, when CI runs, then a gate fails.
- **Originating** ARD §"Phase 2 exit", XR-006
- **Depends on** —
- **Tier** CRITICAL · **Size** M · **Owner** Compliance

---

### Epic BRR — BR Coverage Closure

#### P2-BRR-001 — BR-coverage gate (every BR has implementing story + passing test)
- **As** the Architecture team
  **I want** a CI gate that verifies every BR in the BRD has at least one implementing story + at least one passing test
  **So that** ARD Phase 2 exit ("Every BR satisfied with passing tests") is mechanically closed.
- **AC**
  - Given the gate, when run, then it lists every BR and the tests that cover it.
  - Given a BR with zero passing tests, when run, then the gate fails.
- **Originating** ARD §"Phase 2 exit", XR-012
- **Depends on** P0-OBS-009
- **Tier** CRITICAL · **Size** M · **Owner** Architecture

---

## Phase 2 cross-track summary

| Track | Critical stories | Important / Supportive |
|-------|------------------|------------------------|
| Engineering | P2-SPK-001..005, P2-REV-001..003, P2-BFP-001..005, P2-DEL-001..004, P2-REC-001, P2-DRF-002 (IMPORTANT), P2-ANC-001..002, P2-MR-001..003, P2-MR-005..007, P2-UMR-001, P2-TWP-001..002, P2-BRR-001 | P2-REV-004, P2-DEL-005, P2-REC-002, P2-DRF-001, P2-MR-004, P2-MR-008, P2-UMR-002 |
| Security | P2-TWP-001..002, P2-DEL-002, P2-REV-003, P2-ANC-001..002 | P0-SEC-003 (recurring) |
| Compliance | P2-COM-001..006, P2-MR-004, P2-ADV-001 | — |
| UX | P2-UX-003 | P2-UX-002 |
| Infrastructure | P2-ANC-001 | — |

## Phase 2 risk-register linkage

| Risk | Story closing it (or downgrading) |
|------|-----------------------------------|
| RR-005 (Splink threshold defaults) | P2-SPK-004 |
| RR-009 (member portal scope) | P2-UX-003 (per P0-ADR-002) |
| RR-010 (reviewer build vs buy) | P2-REV-002 (per P0-ADR-003) |

---

## Out of scope for Phase 2

- Multi-partner identity correlation (Phase 3)
- Per-partner cryptographic isolation validation at scale (Phase 3)
- Penetration testing (Phase 4)
- Comprehensive accessibility audit (Phase 4)
- BAA chain finalization across all partners (Phase 4)
