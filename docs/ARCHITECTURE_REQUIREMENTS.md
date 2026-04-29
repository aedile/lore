# Architecture Requirements Document: Strategic Data System for Trusted Partner Eligibility and Identity Verification

## Document Purpose

This document specifies the architecture that satisfies the business rules in `BUSINESS_REQUIREMENTS.md`. It commits to specific technologies, deployment topology, service decomposition, data schemas, and integration patterns. Where the BRD says what must be true, this ARD says how the system is built to make it true.

Every architectural decision is numbered (AD-NNN), traceable, and reversible only by amendment to this document. The Architectural Decision Ledger near the top is the authoritative summary; the body sections elaborate. Major decisions live in standalone Architecture Decision Records (`docs/adr/ADR-NNNN-*.md`) referenced here.

The ARD is written to the production target. A separate Prototype Scope section near the end identifies the subset of the architecture that runs on the local substrate for the interview deliverable, and how the deviation from production is bounded.

This ARD has been synthesized from eight review rounds (principal architect, chief programmer, principal security, compliance/legal, principal DevOps, principal UI/UX, executive, project manager) covering 522 raw findings. Findings are referenced by ID throughout (R1 F-NNN, R3 S-NNN, R4 L-NNN, R5 D-NNN, R6 U-NNN, R7 E-NNN, R8 P-NNN). The `docs/reviews/` directory retains the diagnostic audit trail.

## Relationship to Other Documents

- **PROBLEM_BRIEF.md** captured the problem space. Upstream of everything technical.
- **BUSINESS_REQUIREMENTS.md** captured the business rules, cross-cutting policies, configuration parameters, NFRs, and assumptions. Direct upstream of this ARD. The ARD takes no position on business rules; conflicts with the BRD are resolved in favor of the BRD.
- **TECH_STACK.md** captured public signal on Lore's likely stack. Informs but does not constrain.
- **RESEARCH_NOTES.md** captured public signal on Lore's engineering organization.
- **CONTEXT.md** identifies the panel interviewers and squad mappings.
- **HIPAA_POSTURE.md** tracks the live-vs-stubbed-vs-deferred status of every control.
- **docs/adr/** contains ADRs codifying specific decisions referenced from this ARD.
- **docs/reviews/** contains the eight review rounds that informed the synthesis.

## Architectural Decision Ledger

Each AD names an approval tier per BRD XR-011:
- **Engineering Lead**: implementation-level decisions
- **Architecture Review Board (ARB)**: cross-cutting or material decisions
- **CTO**: strategic, board-relevant, or vendor-concentration-affecting
- **CEO**: existential-risk or external-commitment-bearing

| ID | Decision | Approval tier | Section / ADR |
| --- | --- | --- | --- |
| AD-001 | Eight bounded contexts: Ingestion & Profiling, Identity Resolution, Canonical Eligibility, PII Vault, Verification, Member Rights (synthesis addition), Deletion, Audit | ARB | Bounded Context Architecture |
| AD-002 | Wayfinding squad owns Verification end-to-end | CTO | Bounded Context Architecture / Verification |
| AD-003 | Sequelae PH staff may own Ingestion, Identity Resolution, Canonical Eligibility, Verification, Audit; Vault, Deletion, Member Rights, Break-Glass are US-only | CEO (residency commitment) | Deployment Topology / IAM |
| AD-004 | Pattern C: operational store canonical for verification, analytical store derived via CDC | ARB | Operational vs. Analytical Separation |
| AD-005 | Operational history window 90 days; older history is BigQuery-only | ARB | Operational vs. Analytical Separation |
| AD-006 | Datastream for production CDC; simple sync script in prototype | ARB | Operational vs. Analytical Separation |
| AD-007 | Prototype substrate: local Postgres in Docker plus DuckDB | Engineering Lead | Prototype Scope |
| AD-008 | PII Vault Option 1: Cloud KMS plus application-level tokenization plus hardened Cloud SQL inside VPC-SC, behind a `TokenizationService` interface | ARB | PII Vault Context; ADR-0003 |
| AD-009 | Keyed deterministic tokenization with HKDF-derived per-class HMAC keys; per-day DEK + per-class HSM-backed KEK envelope encryption (synthesis tightening per ADR-0003) | ARB | PII Vault Context; ADR-0003 |
| AD-010 | Synchronous per-record detokenization only for v1; batch detokenization roadmap | Engineering Lead | PII Vault Context |
| AD-011 | Splink for identity resolution; Fellegi-Sunter probabilistic record linkage with explainable per-pair match weights | ARB | Identity Resolution Context |
| AD-012 | Splink on DuckDB in prototype; Splink on BigQuery in production v1; Spark backend held in reserve | Engineering Lead | Identity Resolution Context |
| AD-013 | Tiered audit storage: BigQuery native for operational events; GCS Bucket Lock plus BigQuery external table for high-criticality events | ARB | Audit Context |
| AD-014 | GCS Bucket Lock retention `AUDIT_RETENTION_PII_YEARS`, matching HIPAA + buffer; one-way commit accepted | CTO | Audit Context |
| AD-015 | Single SQL query surface in BigQuery, with high-criticality events surfaced through external tables over GCS | Engineering Lead | Audit Context |
| AD-016 | Two-layer schema mapping: code-resident format adapters per format family; declarative YAML per-partner mapping in a versioned registry | ARB | Cross-Cutting Patterns / Schema Mapping |
| AD-017 | Single primary US region (us-central1), multi-AZ; cross-region DR replica in us-east1 (US-only); three environments (dev/staging/prod), VPC-SC perimeter with stricter inner perimeter around the Vault, Cloud Run for stateless services per ADR-0007, Cloud Composer for orchestration, Pub/Sub plus Dataflow for streaming | CTO | Deployment Topology; ADR-0007 |
| AD-018 | Five-phase delivery: foundation, single-partner end-to-end, production cutover, scale, hardening | CTO | Phased Delivery |
| AD-019 | Monorepo with multi-service build (synthesis addition) | ARB | ADR-0002 |
| AD-020 | Transactional outbox pattern for cross-context events (synthesis addition) | ARB | ADR-0005 |
| AD-021 | RS256 JWT contract for Verification API with strict claim validation (synthesis addition) | ARB | ADR-0004 |
| AD-022 | structlog logging schema with PII redaction; W3C Trace Context for distributed tracing; correlation_id distinct from trace_id; shared error catalog with retry policy by category (synthesis addition) | ARB | ADR-0006 |
| AD-023 | Audit chain external anchoring via cross-organization replication + RFC 3161 trusted timestamp (synthesis addition) | CTO | ADR-0008 |
| AD-024 | Verification API latency equalization with floor at `VERIFICATION_LATENCY_FLOOR_MS` (synthesis addition; reconciles BR-404) | ARB | ADR-0009 |
| AD-025 | PEP/PDP authorization model: shared Policy Decision Point library; Policy Enforcement Point at every API boundary (synthesis addition) | ARB | Cross-Cutting Patterns / Authentication & Authorization |
| AD-026 | Two-person authorization for high-risk operations | ARB | Cross-Cutting Patterns / Two-Person Rule |
| AD-027 | Audit event class routing: high-criticality classes → GCS Bucket Lock per ADR-0008; operational classes → BigQuery `audit_operational` | ARB | Audit Context |
| AD-028 | Cross-region backup replication: AlloyDB and Vault to us-east1 (US-only); Datastream replicating to BigQuery US multi-region | CTO | Deployment Topology |
| AD-029 | Member Rights as a distinct bounded context (synthesis addition; previously implicit) | ARB | Bounded Context Architecture |
| AD-030 | Privacy Officer + Security Officer designations are required before Phase 1 production traffic; both US-resident | CEO | BRD BR-1101, BR-1102 |
| AD-031 | Container hardening: non-root user, read-only root filesystem, signed images via Cosign; Binary Authorization on Cloud Run rejects unsigned (synthesis addition) | Engineering Lead | ADR-0007 |
| AD-032 | Identity Resolution Splink model lifecycle: model artifacts in Cloud Storage with versioning; shadow-mode evaluation before promotion; held-out evaluation set (synthesis addition; R1 F-009) | ARB | Identity Resolution Context |
| AD-033 | Canonical-identity unmerge / split path: irreversibility-classified per BR-XR-006; requires two-person authorization (AD-026); emits `IDENTITY_SPLIT` lifecycle event | ARB | Canonical Eligibility Context |

## System Topology Overview

```
                     +-------------------+
  Partner SFTP  -->  | Cloud Storage     |  raw landing zone (immutable, versioned)
                     +---------+---------+
                               |
                               v
                     +-------------------+
                     | Format Adapter    |  CSV / X12 834 / fixed-width / JSON / XML
                     | (Cloud Run job)   |  one per format family (AD-016)
                     +---------+---------+
                               |
                               v
                     +-------------------+
                     | Mapping Engine    |  reads per-partner YAML registry
                     | (Cloud Run job)   |  produces canonical staging records
                     +---------+---------+
                               |
                               v
                     +-------------------+         +---------------------+
                     | DQ + Profiling    |  --->   | Quarantine          |
                     | (Cloud Run job)   |         | (Cloud Storage)     |
                     +---------+---------+         +---------------------+
                               |
                               v (Pub/Sub: staging-records, ordered by source_file_id)
                     +-------------------+
                     | Identity Resolver |  Splink, comparing staging records
                     | (Cloud Run job,   |  against canonical history
                     |  Splink-on-BQ)    |
                     +---------+---------+
                               |
                               v (Pub/Sub: match-decisions, ordered by candidate_record_ref)
                     +-------------------+         +---------------------+
                     | Canonical         |  --->   | Manual Review Queue |
                     | Eligibility       |         | (Postgres-backed)   |
                     | (AlloyDB Postgres |         | + Reviewer interface|
                     |  + outbox)        |         +---------------------+
                     +---+--------+------+
                         |        |
              CDC        |        | direct read (sub-floor; ADR-0009)
              (Datastream)        v
                         |  +-------------------+
                         |  | Verification API  |  Wayfinding-owned (AD-002)
                         |  | (Cloud Run)       |  external states {VERIFIED, NOT_VERIFIED}
                         v  +---------+---------+
              +----------------+      |
              | BigQuery       |      v (Pub/Sub: lifecycle-events)
              | (analytical)   |
              +----------------+

  Member Rights context (Cloud Run): NPP, DSAR workflow, member portal back-end,
       complaint workflow → Pub/Sub events to Audit and Canonical Eligibility

  PII Vault (Cloud SQL + KMS HSM tier, inner VPC-SC perimeter, US-only IAM):
       ^                                                             ^
       | TokenizationService API (Cloud Run)                         | break-glass detok
       +-------------------------------------------------------------+ (two-person AD-026)
       all services token-only; vault is the only plaintext PII surface

  Audit emission: every service publishes to Pub/Sub `audit-events` topic via
  per-context outbox (ADR-0005); Dataflow consumer fans out to BigQuery
  (operational tier per AD-027) and GCS Bucket Lock (high-criticality tier
  with hash chain + cross-org replication + RFC 3161 timestamp per ADR-0008)
```

## Bounded Context Architecture

Each context is a deployable boundary, an ownership boundary, and a data product. Cross-context communication is through published contracts (API or event topic), never through shared databases. Each context lists the BRs it implements (component → BR mapping; BR → component mapping is in BRD §"Owning component" of each rule; both sides validated by CI gate per BRD XR-012).

### Ingestion & Profiling

**Purpose:** Convert raw partner files into validated canonical staging records, with per-feed quality assessment and quarantine of records or feeds that fail the rules in BR-301 through BR-306.

**Boundary:** "raw partner file" to "validated staging record awaiting identity resolution."

**Owner:** Data engineering. Sequelae PH eligible (operates on tokenized surfaces and pre-canonical staging only).

**Components:**

- **Landing zone.** Cloud Storage bucket per partner, versioned, lifecycle-policy-retained for `RAW_FEED_RETENTION_DAYS`. Source files immutable once landed; reprocessing reads from here (BR-606).
- **Format adapter (per format family).** Cloud Run jobs implementing the adapter pattern from AD-016. One adapter per format family, not per partner. Adapters parse to a common intermediate row representation. Adapters MUST NOT crash on row-level errors per R2 F-113; they emit synthetic parse-error rows.
- **Mapping engine.** Cloud Run job that reads the per-partner YAML mapping from the schema registry, applies normalization rules, and emits canonical staging records.
- **Schema registry.** Git repository of per-partner YAML files. Per ADR-0002 monorepo structure. Changes go through the same review pipeline as application code. Per BR-XR-011 amendments require named approver.
- **DQ engine.** Cloud Run job that applies field-tier validation (BR-301), record-level quarantine (BR-302), feed-level threshold gating (BR-303), schema drift detection (BR-304), and profile drift detection (BR-305). Emits DQ events to the audit topic via outbox.
- **Quarantine bucket.** Cloud Storage bucket for rejected records and quarantined feeds. Retention `RAW_FEED_RETENTION_DAYS`.
- **Reconciliation engine.** Cloud Composer DAG that runs on `RECONCILIATION_CADENCE_DAYS` per partner (BR-605).
- **Replay orchestrator.** Cloud Run job that performs full or partial replay (BR-606); requires confirmation token per BR-607; idempotent per ADR-0005.
- **Outbox table** (per ADR-0005) for `staging-records` events.

**Inbound contract:** Partner files arrive via SFTP (production) into the landing zone, or directly into the landing bucket via partner-side service account if the partner can write to GCS. SFTP credentials per partner, rotated on `PARTNER_SFTP_ROTATION_DAYS` (config parameter to be added; per R3 S-016).

**Outbound contract:** Validated staging records published via outbox to the `staging-records` Pub/Sub topic, partitioned by partner, ordering key = `source_file_id`.

**BRs implemented:** BR-301..306, BR-601..607.

### Identity Resolution

**Purpose:** Decide whether a staging record represents a known canonical identity (and which) or a new identity, per the tiered match policy in BR-101 through BR-105.

**Boundary:** "two records, same person?"

**Owner:** Data engineering / ML. Sequelae PH eligible (analytical surfaces only, with feature-engineering access path per ADR `[sequelae-ph-ml-access]` forthcoming addressing R1 F-014).

**Components:**

- **Match orchestrator.** Cloud Run service that consumes from `staging-records` (idempotent per ADR-0005), applies Tier 1 deterministic anchor evaluation in SQL against Canonical Eligibility, and routes ties or non-matches to Splink for Tier 2/3/4 evaluation. Per-partner concurrency limit per R2 F-109. Per-member advisory locking on canonical state mutations per R2 F-104 (`pg_advisory_xact_lock`; pgbouncer transaction-mode-safe per R2 F-121).
- **Splink runner.** Cloud Run job invoking Splink against the BigQuery backend (AD-012). Splink generates blocking and comparison SQL; BigQuery executes; scored pairs return. Match weights and per-comparison contributions persisted alongside each decision.
- **Splink model lifecycle.** Per AD-032: model artifacts versioned in Cloud Storage (KMS-encrypted); shadow-mode evaluation before promotion; held-out evaluation set with documented metrics (precision per tier, recall, calibration); promotion as deliberate decision; rollback path.
- **Match decision store.** Postgres table inside Canonical Eligibility holding `match_decision` rows with algorithm_version and config_version stamps (BR-104).
- **Manual review queue.** Postgres-backed work queue. Tier 3 outcomes produce queue entries (BR-105). Reviewer interface backend per AD-029 (Member Rights / Reviewer context); reviewers see tokenized identifiers + per-comparison feature contributions per ADR `[reviewer-decision-support]` forthcoming.
- **Deletion-ledger suppression check.** Reads from `deletion_ledger` (BR-703) on every staging record before publication.
- **Outbox table** for `match-decisions` events.

**Inbound contract:** Subscribes to `staging-records`. Idempotent consumer per ADR-0005.

**Outbound contract:** Publishes `match-decisions` events via outbox. Canonical Eligibility consumes.

**BRs implemented:** BR-101..105.

### Canonical Eligibility

**Purpose:** The headline data product. Holds the canonical member entity, partner enrollment many-to-one, lifecycle state, SCD2 history. Source of truth for verification reads.

**Boundary:** "what is true about this person at time T?"

**Owner:** Data engineering, with Wayfinding squad as primary consumer through Verification. Sequelae PH eligible.

**Components:**

- **Operational store.** AlloyDB for PostgreSQL (production target) holding current state plus the bounded history window per AD-005 (90 days). Schema in Data Schemas section.
- **State machine engine.** Application code enforcing the BR-202 transition table. Hand-coded per R2 F-144 (transitions = 9; library not justified). Transition logic centralized; no service mutates state without going through this layer. SCD2 closing semantics per R2 F-105 (timestamps from database `now()`, atomic transaction closing prior row + opening new row with `effective_from = previous.effective_to`).
- **Concurrency control.** Per-member-id advisory lock (`pg_advisory_xact_lock(hashtext(member_id))`) for every state mutation per R2 F-104. pgbouncer transaction-mode constraints per R2 F-121 are documented (no session-scoped state, no prepared statement caching, no LISTEN/NOTIFY).
- **SCD2 derivation.** On every update, prior state is closed (effective_to set) and new state opened (effective_from set). Atomic per R2 F-105. Operational store retains 90 days; older history flows to BigQuery via Datastream.
- **Analytical projection.** BigQuery dataset `canonical_eligibility` holding full SCD2 history. Datastream-replicated from the operational store.
- **Unmerge / canonical-identity-split path.** Per AD-033: irreversibility-classified; requires two-person authorization (AD-026); emits `IDENTITY_SPLIT` lifecycle event with full audit trail; downstream consumers receive the split event and reconcile.
- **Outbox table** for `lifecycle-events`.

**Inbound contract:** Subscribes to `match-decisions` (idempotent consumer). Receives lifecycle events from time-based jobs (grace period elapse).

**Outbound contract:** Publishes `lifecycle-events` for state transitions via outbox. Exposes a read-only query interface to Verification.

**BRs implemented:** BR-201..206, plus serving for BR-401 and BR-404.

### PII Vault

**Purpose:** The only place plaintext PII lives. Tokenization in, detokenization out, KMS-mediated keys, audited per access. Cryptographic lifecycle per ADR-0003.

**Boundary:** "the only plaintext-PII surface."

**Owner:** Security and platform engineering. **US-resident personnel only** per BR-506.

**Components:**

- **Vault store.** Cloud SQL for PostgreSQL instance inside an inner VPC-SC perimeter. Distinct from the Canonical Eligibility AlloyDB instance. Schema is intentionally narrow: token, encrypted plaintext PII fields (envelope encryption per ADR-0003), KMS DEK identifier per record, KEK identifier, creation timestamp, last-detok timestamp, deletion tombstone flag.
- **TokenizationService.** Cloud Run service exposing the `TokenizationService` interface (defined in API Contracts). All callers go through this service; no service has direct DB access to the vault. Mediates Cloud KMS HSM tier (per R3 S-077) for envelope encryption. Cryptographic primitives per ADR-0003: keyed deterministic tokens via HKDF-derived per-class HMAC keys; per-day DEK + per-class KEK envelope encryption.
- **KMS keyring.** Cloud KMS HSM-tier keyring scoped to the vault project. Separate keys per environment, per token class, per data class (DEK, KEK, deletion ledger key). Auto-rotation per ADR-0003 schedules.
- **Inner VPC-SC perimeter.** Service perimeter containing only the vault project resources. Egress and ingress restricted to a published allow-list of caller identities (TokenizationService, Break-Glass paths).
- **Two-person authorization gate** (per AD-026): vault key rotation, mass detokenization (>`MASS_DETOK_THRESHOLD` records), deletion override.

**Inbound contract:** TokenizationService API.

**Outbound contract:** Audit events on every tokenize, detokenize, and tombstone via outbox. Published to `audit-events` topic. Tombstones audited as `PII_HANDLER_DETOK` for human-actor detok or `PII_ACCESS` for service-actor.

**BRs implemented:** BR-502, BR-506, BR-702 (vault purge).

**Future swap:** AD-008 commits to Option 1 with a clean abstraction. Migration to Skyflow or self-hosted Vault means replacing TokenizationService implementation; callers do not change.

### Verification

**Purpose:** Public-facing identity verification API serving the Lore application's account creation flow. Privacy-preserving collapse, brute force protection, latency equalization per BR-401, BR-402, BR-403, BR-404, ADR-0009.

**Boundary:** "is this identity claim valid?"

**Owner:** **Wayfinding squad** (Mike Griffin's squad, AD-002). Sequelae PH eligible.

**Components:**

- **Verification API.** Cloud Run service. Stateless. Reads from Canonical Eligibility's operational store via internal query interface. Writes only to the rate-limit cache and the audit topic via outbox. Cold-start mitigation per ADR-0007 (`min=2` instances). JWT validation per ADR-0004.
- **Latency equalization layer.** Per ADR-0009: response held until `VERIFICATION_LATENCY_FLOOR_MS` elapses; response body padded to `VERIFICATION_RESPONSE_BODY_BYTES`; all error paths (rate-limit, friction, lockout) equalized in shape and timing.
- **Rate-limit cache.** Cloud Memorystore (Redis) HA tier (per R3 S-126). Identity-scoped failure counters per BR-402 and XR-004. Keys rotate on `BRUTE_FORCE_WINDOW_HOURS`. Replay defense for JWT `jti` (ADR-0004).
- **Friction challenge layer.** Per BR-402 second-failure progression. Implementation: invisible reCAPTCHA Enterprise scoring as primary; step-up via one-time-code as secondary. Per ADR `[friction-mechanism]` (forthcoming).
- **Lockout enforcement.** Application logic asserting that the third failure within the window flips the identity into a `LOCKED` flag in the rate-limit cache, separate from the canonical state. Recovery per BR-1308 service blueprint.
- **Public response collapse.** Application logic ensures the response set is exactly `{VERIFIED, NOT_VERIFIED}` regardless of internal state. Internal state is logged to audit via outbox; never crosses the public surface (BR-401, XR-003).
- **Fail-closed semantics** (per R2 F-108): when TokenizationService is unavailable, Verification returns `NOT_VERIFIED`; internal log + audit distinguishes "no match" from "TokenizationService down"; alerting fires immediately.

**Inbound contract:** External HTTPS API at the Lore application's domain. mTLS at the load balancer + RS256 JWT per ADR-0004. See API Contracts.

**Outbound contract:** Reads canonical state. Writes verification audit events via outbox.

**BRs implemented:** BR-401..405.

### Member Rights (synthesis addition per AD-029)

**Purpose:** Member-facing rights workflows: Right of Access (BR-903), Right to Amendment (BR-904), Right to Accounting (BR-905), Right to Restriction (BR-906), Right to Confidential Communications (BR-907), Member complaint procedure (BR-908), NPP delivery (BR-901), Authorization framework (BR-902), Personal representative flows (BR-1303), Member harm recovery (BR-1308).

**Boundary:** "Lore's interface with members exercising their HIPAA / state-law rights."

**Owner:** Compliance program (functional ownership) + Engineering (platform implementation). **US-resident personnel only** for plaintext PII access (BR-506).

**Components:**

- **DSAR (Data Subject Access Request) workflow service.** Cloud Run service hosting a unified case-management workflow for all member-rights requests. Intake → identity verification → routing per request type → fulfillment → audit emission.
- **NPP service.** Cloud Run service serving the layered NPP (per R6 U-005); tracking acknowledgment receipts; distributing updates on material change (BR-901).
- **Member portal back-end** (per BR-1306). Front-end may be hosted within Lore application or as a Lore-platform-served interface; back-end APIs consumed by either. Identity verification at portal login per NIST IAL2 or equivalent.
- **Complaint workflow.** Per BR-908. Persistent complaint case management; non-retaliation tracking coordinated with HR.
- **Personal representative service.** Per BR-1303. Distinct identity verification of representative + authority verification (POA, guardianship, etc.); audit trail captures who acted on whose behalf.
- **Compliance dashboard** (per R6 U-040). For Privacy Officer / Compliance Staff to view DSAR queue, complaint queue, breach investigation status, training compliance, BAA status.
- **Outbox table** for member-rights events.

**Inbound contract:** Member-facing intake (member portal); REST APIs from Lore application.

**Outbound contract:** Audit events on every action via outbox. Lifecycle event into Canonical Eligibility for amendments (BR-904) or restrictions (BR-906) that affect the canonical model.

**BRs implemented:** BR-901..908, BR-1301..1308.

### Deletion

**Purpose:** Right-to-deletion lifecycle. Verified request to vault purge to ledger insertion to suppression on subsequent ingestion. Completeness across all data copies per BR-702.

**Boundary:** "this person no longer exists in our system."

**Owner:** Security and compliance. **US-resident personnel only** per BR-506.

**Components:**

- **Deletion request intake.** Internal interface where verified deletion requests are recorded. Identity verification of the requester is a precondition handled by Member Rights context (BR-1303 if representative).
- **Deletion executor.** Cloud Run job that orchestrates the BR-702 sequence: vault purge, canonical record tombstone, BigQuery propagation verification, cache eviction, crypto-shred backup keys (per ADR-0003), deletion ledger insert (HMAC-keyed per ADR-0003), audit emission via outbox. Two-person authorization gate (AD-026).
- **Deletion ledger.** Postgres table inside Canonical Eligibility holding HMAC-keyed hashes of match-relevant attributes per BR-703. Per-partner salt for partner-scoped portion. Schema in Data Schemas section. The ledger is queried during ingestion for suppression; the suppression check lives in Identity Resolution but reads from this table.
- **Override path.** Operator override per BR-703, gated by two-person authorization (AD-026); emits `DELETION_OVERRIDE` audit event.
- **SLA tracking.** Composer DAG monitors pending deletion requests; emits `DELETION_SLA_BREACH` page event when a request exceeds `DELETION_SLA_DAYS` (BR-701).

**Inbound contract:** Internal-only. Deletion request intake from Member Rights context.

**Outbound contract:** Audit events via outbox. Lifecycle event into Canonical Eligibility for the state transition to `DELETED` (BR-202).

**BRs implemented:** BR-701..704.

### Audit

**Purpose:** Capture, store, and serve audit events with retention, immutability, and access control per BR-501 through BR-505 and ADR-0008.

**Boundary:** "what happened, who did it, when, and can we prove it."

**Owner:** Security and compliance. Sequelae PH eligible for read access on operational tier; high-criticality reads US-only.

**Components:**

- **Audit emission topic.** Pub/Sub topic `audit-events`. Every service publishes here via outbox (ADR-0005). Schema enforced via Pub/Sub schema validation. Ordering keys per topic (per R2 F-106).
- **Audit consumer (Dataflow).** Streaming Dataflow job that reads from `audit-events` (idempotent per ADR-0005), fans out to two sinks based on event class (per AD-027):
  - **Operational tier sink:** Direct write to BigQuery dataset `audit_operational`. Time-partitioned by event date, clustered by event_class, actor_role, target_token (R3 S-029 forensic query support). Table-level ACL grants write to the Dataflow service account only, read to the `Auditor` role only.
  - **High-criticality tier sink:** Append to a GCS Bucket Lock'd object stream (`audit_high_criticality` bucket, retention policy `AUDIT_RETENTION_PII_YEARS`, `LOCKED`). Hash chain anchored in the GCS stream. Cross-organization replication + RFC 3161 trusted timestamp per ADR-0008.
- **External table view.** BigQuery external table over the GCS bucket, exposing the high-criticality stream through the same SQL surface as operational events (AD-015).
- **Hash chain validator.** Real-time per-event + hourly bulk validation per ADR-0008. Pages on any break. Forensic preservation procedure on detection.
- **External anchor publisher.** Hourly publication of chain head hash + RFC 3161 timestamp + Compliance-organization replication.
- **Redaction scanner.** Scheduled Cloud Run job scanning a sampled slice of audit events against PII regex patterns per XR-005. Pages on any match.
- **Forensic export interface.** For Auditor role: signed export packages with chain-of-custody metadata (per R3 S-051).
- **Auditor query monitoring.** Anomaly detection on auditor query patterns; alerts to Privacy Officer (per R3 S-032).

**Inbound contract:** `audit-events` Pub/Sub topic. Schema-validated. Idempotent consumer.

**Outbound contract:** BigQuery dataset (read-only via IAM) and BigQuery external table.

**BRs implemented:** BR-501..505, plus enforcement of XR-005, XR-006, BR-1010 (forensic preservation).

## Cross-Cutting Architectural Patterns

### Configuration Management (BR-XR-001, BR-XR-002, BR-XR-010)

**Pattern:** Layered configuration with deterministic resolution order: per-load > per-contract > per-partner > global default. Resolution implemented in a single library (`shared/config/`) used by every service. Parameters typed via Pydantic with documented range, scope, owner, and strategic tier per BR-XR-010. Hot-reload semantics: validate-then-swap atomically; on validation failure, log and retain old config (per R5 D-149).

**Implementation:** Configuration source of truth is a Git repository of YAML files (separate repo from the main monorepo, but referenced); deployed configuration materialized into Cloud Storage and watched by a config-reload library in each service. Configuration changes follow the same PR + review pipeline as code (BR-XR-011).

**Audit:** Every configuration change emits a `CONFIGURATION_CHANGE` audit event (BR-501).

### TokenizationService Interface

**Pattern:** All PII flows through a single service interface. No service holds plaintext outside the vault. Interface stable across implementation swaps.

**Interface (illustrative):**

```python
class TokenizationService:
    def tokenize(
        self,
        value: PlaintextValue,
        token_class: TokenClass,
        caller_role: Role,
        purpose: AuditPurpose,
    ) -> Token:
        """Tokenize a plaintext value. Joinability determined by token_class.
        Audit event emitted via outbox. Caller role and purpose recorded."""

    def detokenize(
        self,
        token: Token,
        caller_role: Role,
        purpose: AuditPurpose,
    ) -> PlaintextValue:
        """Detokenize a single token. Synchronous only (AD-010).
        Caller role MUST be PII_HANDLER or BREAK_GLASS_ADMIN.
        Caller residency enforced at IAM + request-origin layer per BR-506.
        Audit event emitted via outbox."""

    def tombstone(
        self,
        token: Token,
        deletion_request_id: DeletionRequestId,
    ) -> None:
        """Irreversibly purge plaintext for this token. Token remains
        addressable for audit log resolution (resolves to TOMBSTONED).
        Two-person authorization for mass tombstone per AD-026."""
```

Token classes are declared in config (per ADR-0003): joinable identifiers like `partner_member_id` get keyed deterministic tokens with per-partner salt; non-joinable PII gets keyed deterministic tokens scoped per class (frequency-analysis-resistant).

### Transactional Outbox Pattern (per ADR-0005)

**Pattern:** Every state-changing operation that emits a Pub/Sub event uses the transactional outbox pattern. Outbox table per context co-resident with primary database. Producer atomically writes state change + outbox row. Publisher service polls outbox and publishes to Pub/Sub. Consumers maintain `processed_events` table for idempotency.

**Detail:** See ADR-0005.

### Idempotency Contract per Pipeline Stage (per ADR-0005)

**Pattern:** Each pipeline stage has a documented idempotency key. Replay produces the same effect at most once given the same key.

| Stage | Idempotency key |
|---|---|
| Landing | `(partner_id, source_file_hash)` |
| Format adapter parse | `(partner_id, source_file_hash, row_index)` |
| Mapping | Same as adapter |
| DQ | Same as adapter |
| Identity Resolution decision | `decision_id` (UUID) |
| Canonical state transition | `(member_id, transition_event_id)` |
| Audit emit | `event_id` (UUID) |

Consumer-side idempotency via `processed_events` table per consumer.

### Concurrency Control on Canonical State (per R2 F-104)

**Pattern:** Per-member-id advisory lock for every canonical state mutation. Prevents lost updates when multiple Match Orchestrator instances process records for the same member concurrently.

**Implementation:** `pg_advisory_xact_lock(hashtext(member_id))` at the start of every transaction modifying canonical state. Lock is transaction-scoped (`_xact_`), required by pgbouncer transaction-mode (per R2 F-121).

### Authentication and Authorization (PEP/PDP) — AD-025

**Pattern:** Policy Enforcement Point (PEP) at every API boundary; Policy Decision Point (PDP) as a shared library (`shared/authz/`). Every route declares the required permission via FastAPI dependency; the PDP returns ALLOW/DENY; the PEP enforces. No inline role checking.

**Per-resource authorization (IDOR prevention; per R3 S-010):** Every resource access checks (a) caller has the role, (b) resource is scoped to the caller (assigned-to, owned-by, organization-scoped). Implementation: `@requires_resource_access(resource_type, resource_id_arg)` decorator.

### Two-Person Rule for High-Risk Operations (AD-026)

**Pattern:** High-risk operations require N-of-M approval (typically 2-of-3 from a designated approver group). Approval workflow integrates with Privileged Access Manager (PAM) and emits dedicated audit events.

**Operations requiring two-person:**
- Vault key rotation
- Mass detokenization (> `MASS_DETOK_THRESHOLD` records)
- Deletion override (BR-703 re-introduction)
- Splink threshold change in production (BR-101)
- Audit log forensic export (R3 S-051)
- Cross-region DR failover (R5 D-040)
- Canonical-identity unmerge / split (AD-033)

### Audit Emission Pattern (per ADR-0005, AD-027)

**Pattern:** Every service publishes audit events to a single Pub/Sub topic via per-service outbox. Audit emission tied to the originating operation's transaction, eliminating audit-vs-state divergence. The Audit context's Dataflow consumer fans out by event class per AD-027.

**Schema:** Every event carries minimum fields per BR-502 + correlation_id per ADR-0006: `event_id`, `event_class`, `actor_role`, `actor_principal`, `target_token` (when applicable), `timestamp`, `outcome`, `trigger`, `context` (JSON), `correlation_id`.

### Logging Schema and Correlation ID Model (per ADR-0006)

**Pattern:** structlog with PII redaction (already LIVE in Phase 00 harness). Required log fields per ADR-0006. Correlation IDs propagated via OpenTelemetry W3C Trace Context for distributed tracing + dedicated `correlation_id` for per-business-record tracking.

**Detail:** See ADR-0006.

### Error Taxonomy and Retry Policy (per ADR-0006)

**Pattern:** Shared exception hierarchy in `shared/errors.py`. Five categories: TransientError, BackpressureSignal, PermanentDataError, PermanentSystemError, BusinessOutcome. Shared retry decorator (`shared/resilience.py`) applies per-category policy.

**Detail:** See ADR-0006.

### Schema Mapping Mechanism (AD-016)

**Pattern:** Two layers. Format adapters live as code, one per format family. Per-partner mappings live as YAML.

**Format adapter (code).** A Python class per format family implementing a uniform interface: `parse(file) -> Iterator[IntermediateRow]`. Adapter MUST NOT crash on row-level errors (R2 F-113); emits sentinel parse-error rows. Adapter count grows with format diversity, not partner count. Six families anticipated for v1: CSV, fixed-width, X12 834, JSON, XML, Parquet.

**Per-partner YAML (config).** Each partner has a YAML file in the schema registry declaring:

- partner_id and human-readable name
- format_family (selects adapter)
- column-to-canonical-field mappings, with explicit field-tier assignment per BR-301
- normalization rules per field
- partner-specific configuration overrides
- DQ baseline metadata (populated after onboarding sample profiling per BR-305)

**Onboarding (BR-801, BR-802).** Adding a partner is a YAML pull request plus a sample feed dropped into the staging onboarding bucket. Configuration-driven, no code change unless a structurally novel format requires a new adapter (rare).

### Audit Chain External Anchoring (per ADR-0008)

**Pattern:** In-stream hash chain (BR-504) plus cross-organization replication to a Compliance-organization GCS bucket plus RFC 3161 trusted timestamp service. Hourly anchor publication. Forensic preservation procedure on chain break.

**Detail:** See ADR-0008.

### Verification API Latency Equalization (per ADR-0009)

**Pattern:** Response held until `VERIFICATION_LATENCY_FLOOR_MS` floor elapses; response body padded to `VERIFICATION_RESPONSE_BODY_BYTES`; all error paths equalized in shape and timing.

**Detail:** See ADR-0009.

## Operational vs. Analytical Separation Pattern (Pattern C)

The verification API has a sub-floor latency requirement (BR-404 + ADR-0009 floor at `VERIFICATION_LATENCY_FLOOR_MS`). BigQuery is not a sub-second point-lookup database. Pattern C resolves this by making the operational Postgres-flavored store (AlloyDB) the canonical source of truth for verification, with BigQuery as a derived analytical surface.

### Read Paths

- **Verification reads:** Verification API queries Canonical Eligibility's AlloyDB. Indexed lookups on tokenized identifier and on the deterministic anchor composition (BR-102). Sub-floor achievable with proper index coverage. Read replica option held in reserve (R2 F-124) for scale.
- **Analytical reads:** Internal users, ML feature engineering (subject to AD-003 residency for plaintext access), audit reconstruction, point-in-time queries older than the operational window query BigQuery.

### Write Path

- All writes target AlloyDB first. Datastream replicates to BigQuery with target lag `DATASTREAM_LAG_TARGET_SECONDS`.
- BigQuery is read-only at the application layer; the only writer is Datastream (and the ETL jobs that derive feature tables).

### Operational History Window

The operational store retains current state plus a 90-day rolling SCD2 history window per AD-005, governed by `OPERATIONAL_HISTORY_WINDOW_DAYS`. Beyond the window, history is BigQuery-only.

### Failure Modes and Reconciliation

- **Datastream lag exceeds threshold.** Page on lag (per R5 D-061 monitoring). BigQuery becomes stale; analytics is degraded but verification is unaffected because verification reads AlloyDB, not BigQuery.
- **AlloyDB outage.** Verification fails. The system falls back to a `NOT_VERIFIED` response per privacy-preserving collapse (XR-003) and ADR-0009 fail-closed semantics. Internal alerting fires immediately.
- **Drift between AlloyDB and BigQuery.** Periodic reconciliation job (separate from BR-605 partner reconciliation) compares row counts and checksums between the two surfaces and pages on mismatch beyond a threshold.

### Reprocess and Read Consistency (per R2 F-119, BR-604)

When a reprocess rebuilds SCD2 history, Verification reads see either the prior or the new chain, never a mixed state. Atomic swap is implemented as: build new SCD2 chain in a parallel namespace; verify integrity; swap canonical pointer atomically; retain prior chain for audit retention window (BR-606).

### CDC Mechanism

Production v1 uses Datastream (GCP-managed Postgres-to-BigQuery CDC) per AD-006. The choice is encapsulated by Pattern C: nothing else in the architecture cares how rows get from AlloyDB to BigQuery. Reversibility preserved.

## Deployment Topology (AD-017)

### Region and Zones

- **Primary region:** us-central1. Justification: GCP's most feature-complete region, lowest service rollout lag, established BAA support across the relevant services.
- **DR region:** us-east1 (US-only per AD-028). Cross-region replication for AlloyDB (read replica with promotion capability) and Vault (Cloud SQL replica). Datastream replicates to BigQuery US multi-region.
- **Multi-zone:** All stateful services deployed multi-zone. Zonal failures absorbed without manual intervention.
- **No multi-region active-active for v1** per A27. Disaster recovery target RTO 1 hour, RPO 15 minutes for Vault and operational store; RTO 8 hours, RPO 4 hours for analytical store.

### Environments

Three environments: `dev`, `staging`, `prod`. Hard separation: separate GCP projects, separate VPC-SC perimeters, separate KMS keyrings, separate Artifact Registries. Service accounts and IAM bindings do not cross environments. Synthetic-only data in dev and staging; only `prod` carries real PII.

### Infrastructure as Code

All infrastructure managed via Terraform. State in Cloud Storage with bucket-level KMS encryption, IAM scoped to terraform-runners only, state locking via GCS object generations, daily backup to a separate region. CI/CD: per-PR `terraform plan` with security scan (Checkov / tfsec); merge requires approval; apply via OIDC (GitHub Actions → GCP Workload Identity Federation), no long-lived service account keys. Drift detection via daily `terraform plan` against each environment. ADR `[iac-framework]` (forthcoming) codifies.

### VPC Service Controls Perimeters

Two perimeters in `prod`:

- **Outer perimeter:** Encloses the prod project. All system services live here. Internet egress allowed only to partner-side endpoints (SFTP), CAPTCHA-equivalent provider, RFC 3161 TSA endpoint (per ADR-0008). Internet ingress allowed only to the public Verification API behind a load balancer.
- **Inner perimeter:** Encloses the Vault project resources only. Ingress allowed only from the TokenizationService service account. Egress denied. The TokenizationService is the only service that crosses the inner perimeter; every other service is fenced out architecturally.

### Identity and Access (AD-003)

- **SSO:** Google Workspace, mapped to IAM groups by role.
- **Role mappings:** Each role from the BRD's Role Taxonomy maps to an IAM group. Role membership is auditable through Workspace logs and IAM audit logs.
- **Sequelae PH boundary:** A Workspace-attribute condition gates membership in `pii_handler@`, `break_glass@`, `privacy_officer@`, `security_officer@`, `compliance_staff@` to US-resident accounts only. Sequelae PH accounts are organizationally segregated and cannot be added to these groups by IAM policy. Request-origin enforcement per BR-506: VPN-based geofencing + IAP conditional access deny non-US IPs from PII-handling services.
- **Break-glass:** Time-boxed grants via Privileged Access Manager. Default ceiling 4 hours. Two-person grant per AD-026. Every grant emits a `BREAK_GLASS_GRANTED` audit event; every revocation a `BREAK_GLASS_REVOKED` event.

### Service Hosting (per ADR-0007)

- **Stateless services**: Cloud Run (per ADR-0007).
- **Streaming consumers** (Audit Consumer): Dataflow.
- **Orchestration:** Cloud Composer (managed Airflow per the confirmed signal in TECH_STACK.md).
- **Stateful stores:** AlloyDB for Postgres (Canonical Eligibility), Cloud SQL for Postgres (Vault), Cloud Memorystore Redis HA tier (rate-limit cache), Cloud Storage (raw landing, quarantine, audit high-criticality), BigQuery (analytical surface, audit operational tier).
- **Per-service deployment strategy** per ADR-0007: canary for Verification API; blue/green for TokenizationService and Audit Consumer; rolling for others.
- **Per-service min/max instances + concurrency** per ADR-0007.
- **Container hardening** per AD-031: non-root user, read-only root filesystem, signed images via Cosign, Binary Authorization on Cloud Run.

### Networking

- VPC connectors per environment for Cloud Run services that need VPC resources.
- Private Service Connect for managed services (AlloyDB, Cloud SQL Vault, Memorystore) per R5 D-050.
- Cloud Armor on the public-facing Verification API load balancer per R3 S-054.
- Cloud DNS with DNSSEC enabled; CAA records pinning issuance to Google.
- Egress controls in IaC per R3 S-055 / R5 D-047.

### Streaming and Eventing

- **Pub/Sub topics:** `staging-records`, `match-decisions`, `lifecycle-events`, `audit-events`, `deletion-requests`, `member-rights-events`. Each has a defined Protobuf schema (per ADR-0006 message schema decision). Ordering keys per topic per R2 F-106.
- **Dataflow jobs:** Audit Consumer (one job, two sinks per AD-027). Reconciliation Sink (writes reconciliation events into BigQuery for trend analysis).

### Observability (per ADR-0006)

- **Logs:** structlog with PII redaction (LIVE per Phase 00). Cloud Logging across all services. Routed to BigQuery via log sink for analytical access. Subject to XR-005 in full; redaction scanner enforces. Operational logs 30-day retention; audit logs separate (per BR-503).
- **Metrics:** Cloud Monitoring. Standard SLI metrics per service per ADR-0006: request rate, error rate (split by error category), latency histogram, plus service-specific (DQ rates, match-tier distributions, vault detok by role, etc.). SLO targets per ADR-0006 / R5 D-023.
- **Traces:** OpenTelemetry instrumentation per ADR-0006. Span boundaries at every Pub/Sub publish/consume, every DB call (>10ms), every external call. Sampling: 100% for ingestion pipeline; 1% for Verification API; 10% for everything else.
- **Health probes:** `/livez` (process up); `/readyz` (dependencies reachable); `/health` (alias). Cloud Run uses `/readyz` for traffic.
- **Alerting:** PagerDuty integration with severity tiers per ADR-0006 (P0 / P1 / P2 / P3). Alert quality reviewed weekly per R5 D-036.

### Cost Engineering / FinOps

Per R5 D-030..033 and R7 E-007:
- Per-month cost estimate at v1, v1-launch (5-10 partners), 10x scale.
- Per-project budget alerts at 50% / 80% / 100% / 120% of forecast.
- Per-feature cost attribution via Cloud Billing labels.
- Cloud Billing anomaly detection.
- KMS HSM tier cost (Vault keys) accepted per R3 S-077; software tier acceptable for less-sensitive keys.

### Backup and DR

Per AD-028 and BRD NFR backup spec:

| Data class | Mechanism | RPO | RTO | Encryption | Cross-region |
|---|---|---|---|---|---|
| Vault | Cloud SQL continuous backups + cross-region replica | 15 min | 1 hour | KMS HSM, separate key from primary | Yes (us-east1) |
| Canonical operational | AlloyDB continuous backups + cross-region replica | 15 min | 1 hour | KMS | Yes (us-east1) |
| Canonical analytical (BQ) | BQ snapshot | 4 hours | 8 hours | KMS | Multi-region native |
| Audit (operational tier) | BQ snapshot + WORM source | 4 hours | 8 hours | KMS | Multi-region |
| Audit (high-criticality) | GCS Bucket Lock + Turbo Replication + Compliance org replication | 0 (immutable) | N/A | KMS | Yes |
| Configuration | Git + Cloud Storage backup | Continuous | 5 min | Standard | Yes |
| KMS keys | HSM-backed for critical; separate keyring for backups (per R5 D-044) | Special | Manual | Itself | Special procedure |

DR drill program per R5 D-039: tabletop quarterly; synthetic DR bi-annually; production DR drill annually. Reports document RTO/RPO measurement, runbook gaps, action items.

### Secrets Management

Per R3 S-058, R5 D-051..054:
- Production secrets in Secret Manager. Service accounts via Workload Identity (per R3 S-014); no service account key files.
- Per-secret rotation cadence in IaC. Automated rotation where possible (DB passwords, KMS keys via auto-rotation).
- Emergency rotation procedure documented; tested quarterly.
- Secret leak detection: GitHub native scanning + push protection; container image scanning includes secrets layer; Cloud Storage object scanning for sensitive buckets.

## Data Schemas

The brief asks for SQL DDL for key tables. The following are the operational-store (AlloyDB / Postgres) schemas. The BigQuery analytical projections are derived via Datastream.

### canonical_member

```sql
CREATE TABLE canonical_member (
    member_id            UUID         PRIMARY KEY,
    state                TEXT         NOT NULL CHECK (state IN (
                                          'PENDING_RESOLUTION',
                                          'ELIGIBLE_ACTIVE',
                                          'ELIGIBLE_GRACE',
                                          'INELIGIBLE',
                                          'DELETED'
                                      )),
    state_effective_from TIMESTAMPTZ  NOT NULL,
    state_effective_to   TIMESTAMPTZ,
    -- tokenized identifiers (per ADR-0003 keyed deterministic, per-class scope)
    name_token           TEXT         NOT NULL,
    dob_token            TEXT         NOT NULL,
    -- tokenized identifiers (vault-resolvable; not joinable cross-class)
    address_token        TEXT,
    phone_token          TEXT,
    email_token          TEXT,
    ssn_token            TEXT,
    -- metadata
    first_seen_at        TIMESTAMPTZ  NOT NULL,
    last_updated_at      TIMESTAMPTZ  NOT NULL,
    tombstoned_at        TIMESTAMPTZ,
    originating_correlation_id UUID            -- per ADR-0006
);

CREATE INDEX idx_canonical_member_state ON canonical_member(state);
CREATE INDEX idx_canonical_member_anchor ON canonical_member(name_token, dob_token);
```

State transitions are enforced by application code (BR-202), not by trigger, to keep the transition table testable in isolation.

### partner_enrollment

```sql
CREATE TABLE partner_enrollment (
    enrollment_id        UUID         PRIMARY KEY,
    member_id            UUID         NOT NULL REFERENCES canonical_member(member_id),
    partner_id           TEXT         NOT NULL,
    partner_member_id_token TEXT      NOT NULL,                  -- per-partner-scoped token (ADR-0003)
    effective_from       DATE         NOT NULL,
    effective_to         DATE,
    last_seen_in_feed_at TIMESTAMPTZ  NOT NULL,
    -- partner-supplied attributes (tokenized where PII)
    partner_attributes   JSONB        NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (partner_id, partner_member_id_token, effective_from)
);

CREATE INDEX idx_partner_enrollment_member ON partner_enrollment(member_id);
CREATE INDEX idx_partner_enrollment_active ON partner_enrollment(member_id) WHERE effective_to IS NULL;
```

The one-to-many relationship implements BR-205 attribution neutrality. Multiple simultaneous enrollments are first-class; no "primary partner" column exists.

### member_history (SCD2)

```sql
CREATE TABLE member_history (
    history_id           BIGSERIAL    PRIMARY KEY,
    member_id            UUID         NOT NULL REFERENCES canonical_member(member_id),
    state                TEXT         NOT NULL,
    state_effective_from TIMESTAMPTZ  NOT NULL,
    state_effective_to   TIMESTAMPTZ,
    name_token           TEXT,
    dob_token            TEXT,
    address_token        TEXT,
    phone_token          TEXT,
    email_token          TEXT,
    ssn_token            TEXT,
    change_trigger       TEXT         NOT NULL,
    change_event_id      UUID         NOT NULL,
    correlation_id       UUID                                      -- per ADR-0006
);

CREATE INDEX idx_member_history_member_time ON member_history(member_id, state_effective_from);
CREATE INDEX idx_member_history_change_event ON member_history(change_event_id);
```

`member_history` retains the operational window (90 days, AD-005). Datastream replicates to BigQuery `canonical_eligibility.member_history` which has unbounded retention.

### match_decision

```sql
CREATE TABLE match_decision (
    decision_id          UUID         PRIMARY KEY,
    candidate_record_ref TEXT         NOT NULL,
    resolved_member_id   UUID         REFERENCES canonical_member(member_id),
    tier_outcome         TEXT         NOT NULL CHECK (tier_outcome IN (
                                          'TIER_1_DETERMINISTIC',
                                          'TIER_2_PROB_HIGH',
                                          'TIER_3_PROB_REVIEW',
                                          'TIER_4_DISTINCT'
                                      )),
    score                NUMERIC(8, 6),
    algorithm_version    TEXT         NOT NULL,
    config_version       TEXT         NOT NULL,
    decided_at           TIMESTAMPTZ  NOT NULL DEFAULT now(),     -- DB-generated per R2 F-105
    score_breakdown      JSONB,
    correlation_id       UUID                                      -- per ADR-0006
);

CREATE INDEX idx_match_decision_member ON match_decision(resolved_member_id);
CREATE INDEX idx_match_decision_tier ON match_decision(tier_outcome);
```

Algorithm and configuration version stamps satisfy BR-104. `score_breakdown` retains Splink's per-comparison weights for explainability and reviewer decision support.

### deletion_ledger

```sql
CREATE TABLE deletion_ledger (
    ledger_id            BIGSERIAL    PRIMARY KEY,
    -- HMAC-keyed hash per ADR-0003 (replaces bare salted SHA-256)
    suppression_hash     TEXT         NOT NULL UNIQUE,
    algorithm_version    TEXT         NOT NULL,                   -- e.g. "v1:hmac-sha256"
    deleted_at           TIMESTAMPTZ  NOT NULL DEFAULT now(),
    deletion_request_id  UUID         NOT NULL,
    override_count       INT          NOT NULL DEFAULT 0,
    correlation_id       UUID                                      -- per ADR-0006
);

CREATE INDEX idx_deletion_ledger_hash ON deletion_ledger(suppression_hash);
```

The ledger holds no recoverable PII per BR-703. `suppression_hash` is computed via HMAC-SHA-256 with a KMS-resident key (per ADR-0003); offline brute force requires KMS access. Identity Resolution queries this table on every staging record before publication.

### review_queue

```sql
CREATE TABLE review_queue (
    queue_id             UUID         PRIMARY KEY,
    decision_id          UUID         NOT NULL REFERENCES match_decision(decision_id),
    candidate_record_ref TEXT         NOT NULL,
    candidate_member_ids UUID[]       NOT NULL,
    score                NUMERIC(8, 6) NOT NULL,
    queued_at            TIMESTAMPTZ  NOT NULL DEFAULT now(),
    claimed_by           TEXT,
    claimed_at           TIMESTAMPTZ,
    resolved_at          TIMESTAMPTZ,
    resolution           TEXT         CHECK (resolution IN ('MERGE', 'DISTINCT', 'ESCALATE', 'RETRACTED')),
    correlation_id       UUID
);

CREATE INDEX idx_review_queue_unresolved ON review_queue(queued_at) WHERE resolved_at IS NULL;
```

Tier 3 outcomes per BR-101 produce queue entries. Reviewers see tokenized references plus per-comparison feature contributions per ADR `[reviewer-decision-support]` forthcoming. `RETRACTED` outcome (per R8 P-024) abandons a queued decision before action.

### outbox (per context, per ADR-0005)

```sql
CREATE TABLE outbox (
    event_id             UUID         PRIMARY KEY,
    topic                TEXT         NOT NULL,
    ordering_key         TEXT,
    payload              JSONB        NOT NULL,
    correlation_id       UUID,                                     -- per ADR-0006
    created_at           TIMESTAMPTZ  NOT NULL DEFAULT now(),
    published_at         TIMESTAMPTZ,
    retry_count          INTEGER      NOT NULL DEFAULT 0,
    last_attempt_at      TIMESTAMPTZ,
    last_error           TEXT
);

CREATE INDEX idx_outbox_unpublished ON outbox(created_at) WHERE published_at IS NULL;
```

### processed_events (per consumer, per ADR-0005)

```sql
CREATE TABLE processed_events (
    event_id             UUID         PRIMARY KEY,
    topic                TEXT         NOT NULL,
    processed_at         TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX idx_processed_events_topic_time ON processed_events(topic, processed_at);
```

Pruned on schedule (events older than 30 days removed; assumption Pub/Sub retention plus processing latency is bounded well below the prune horizon).

### audit_event (operational tier, BigQuery)

```sql
CREATE TABLE audit_operational.audit_event (
    event_id             STRING       NOT NULL,
    event_class          STRING       NOT NULL,
    actor_role           STRING       NOT NULL,
    actor_principal      STRING       NOT NULL,
    target_token         STRING,
    timestamp            TIMESTAMP    NOT NULL,
    outcome              STRING       NOT NULL,
    trigger              STRING       NOT NULL,
    context              JSON,
    correlation_id       STRING                                    -- per ADR-0006
)
PARTITION BY DATE(timestamp)
CLUSTER BY event_class, actor_role, target_token
OPTIONS (
    partition_expiration_days = 730  -- AUDIT_RETENTION_OPS_YEARS = 2
);
```

Clustering on `target_token` (per R3 S-029) supports forensic queries by subject. The high-criticality external table mirrors this shape but reads from the GCS Bucket Lock'd object stream and includes additional columns for prior-event hash, self hash, and anchor_id (per ADR-0008 chain validation).

## API Contracts

### Verification API (Public)

The only public surface of the system. Wayfinding-owned (AD-002). Latency-equalized per ADR-0009.

**POST /v1/verify**

Request:

```json
{
  "claim": {
    "first_name": "string",
    "last_name": "string",
    "date_of_birth": "YYYY-MM-DD",
    "ssn_last_4": "string|null",
    "partner_member_id": "string|null",
    "address": { "...": "..." }
  },
  "context": {
    "client_id": "string",
    "request_id": "string"
  }
}
```

Response (constant time per ADR-0009; constant body length per `VERIFICATION_RESPONSE_BODY_BYTES`):

```json
{
  "outcome": "VERIFIED|NOT_VERIFIED",
  "request_id": "string",
  "_padding": "<base64 random>"
}
```

The response set is exactly two values per BR-401 and XR-003. No internal state. No error codes that distinguish reasons. No headers beyond standard. Response time and body length equalized per ADR-0009.

Authentication: mTLS at the load balancer plus a short-lived JWT issued by the Lore application's auth service. JWT validation per ADR-0004 (RS256 only; required claims; jti replay defense; max TTL 5 minutes).

Idempotency: `request_id` serves as idempotency key per R2 F-130. Repeated submissions with the same `request_id` within the cache TTL return the same outcome and do not double-count against rate limits.

**Verification != authentication** per ADR-0009: VERIFIED indicates the submitted claim matches an eligible identity; it does NOT authenticate the requester. Account creation in the Lore application MUST include independent factors (per BR assumption A29).

### TokenizationService API (Internal)

See the interface specification in the TokenizationService Interface section above. Surfaced as a Cloud Run service with HTTP/gRPC endpoints. Caller authentication via service-account-bound IAM (Workload Identity per R3 S-014). Caller authorization additionally checked by role per BR-506 and AD-003 residency. Two-person authorization gate for mass operations (AD-026).

### Manual Review API (Internal)

Backs the reviewer interface.

- `GET /v1/review/queue?status=unresolved&cursor=<>` — list unresolved queue items (cursor pagination per R6 U-156)
- `POST /v1/review/queue/{queue_id}/claim` — claim an item for review (IDOR-protected per AD-025)
- `POST /v1/review/queue/{queue_id}/resolve` — resolve with MERGE / DISTINCT / ESCALATE / RETRACTED

Reviewers see tokenized identifiers and per-comparison feature contributions. They do NOT see plaintext PII. Resolution actions emit audit events via outbox.

### Member Rights API (Internal)

Backs the member portal back-end.

- `POST /v1/rights/access` — submit Right of Access request (BR-903)
- `POST /v1/rights/amendment` — submit Right to Amendment request (BR-904)
- `POST /v1/rights/accounting` — submit Accounting of Disclosures request (BR-905)
- `POST /v1/rights/restriction` — submit Right to Restriction request (BR-906)
- `POST /v1/rights/communications` — submit Right to Confidential Communications request (BR-907)
- `POST /v1/rights/complaint` — submit complaint (BR-908)
- `GET /v1/rights/{request_id}` — track request status
- `POST /v1/rights/representative` — submit on behalf of another member (BR-1303)

Identity verification per BR-1306; representative authority verification per BR-1303.

### Deletion Request API (Internal)

- `POST /v1/deletion/request` — record a verified deletion request (verification of requester identity is a precondition handled by Member Rights context)
- `GET /v1/deletion/{request_id}` — status query

Both internal-only, behind the Security and Compliance role.

### Internal API Error Contract (per R3 S-129)

All internal APIs return errors in a consistent shape:

```json
{
  "error": {
    "code": "string",
    "message": "string",
    "request_id": "string",
    "retryable": false,
    "retry_after_seconds": null
  }
}
```

HTTP status code mapping: 4xx for client error; 5xx for server; 503 for backpressure with Retry-After header. Error category per ADR-0006 error taxonomy.

## Threat Model per Bounded Context (per R3 S-069)

Per-context STRIDE table identifying threats and mitigations. Asset classification per R3 S-070 below. This section delivers what R1 F-018 noted as a gap.

### Ingestion & Profiling

| Threat | Specific scenario | Mitigations |
|---|---|---|
| Spoofing | Adversary submits malicious file via partner SFTP credentials | SFTP credential lifecycle per R3 S-016; file integrity check per R3 S-045 |
| Tampering | Adversary modifies in-flight file in landing zone | Cloud Storage immutability + versioning |
| Repudiation | Partner denies sending file later | File hash logged at landing; outbox audit |
| Info disclosure | Quarantined file accessible to unauthorized | IAM on quarantine bucket; per-partner IAM scoping |
| DoS | Massive partner feed overloads pipeline | Backpressure + per-partner rate limit per R2 F-150; per-partner concurrency per R2 F-109 |
| Elevation | Format adapter compromised → access to all partners' files | Adapter is stateless; no inter-file context; reaffirm in code review |

### Identity Resolution

| Threat | Specific scenario | Mitigations |
|---|---|---|
| Spoofing | Adversary forges staging records to manipulate matching | Pub/Sub schema validation; signed messages (Pub/Sub native verification) |
| Tampering | Match decision modified in flight | Outbox pattern (ADR-0005); audit emission |
| Repudiation | Reviewer claims they didn't make a decision | Audit on resolve action; per-actor signing deferred to Phase 2 (per ADR-0008) |
| Info disclosure | Match scores leaked → re-identification via score patterns | Tokenized data only; reviewer auth; CODEOWNERS for review code (R3 S-040) |
| DoS | Massive dirty feed exhausts Splink runner | Per-partner concurrency limits; Splink batch slot allocation |
| Elevation | Reviewer abuses queue access for unauthorized reviews | Resource-level authorization per AD-025; auditor monitoring per R3 S-032 |
| Adversarial ML | Crafted records to force false positives or false negatives | Anomaly detection on match decisions; adversarial-robustness in training data per R3 S-075 |

### Canonical Eligibility

| Threat | Specific scenario | Mitigations |
|---|---|---|
| Spoofing | Lifecycle event injected from outside | Pub/Sub schema; Workload Identity per R3 S-014 |
| Tampering | Direct DB modification | IAM + DB user least privilege; per-service DB user (synthesis addition) |
| Repudiation | State change without attribution | Lifecycle event audit; correlation_id propagation per ADR-0006 |
| Info disclosure | Cross-partner data leakage via deterministic tokens | Keyed deterministic tokenization with per-partner salt (ADR-0003) |
| DoS | Verification overload on AlloyDB | Read replica; rate limit; Memorystore HA tier per R3 S-126 |
| Elevation | App role privilege escalation in DB | DB role scoping; per-service DB user; least privilege |

### PII Vault

| Threat | Specific scenario | Mitigations |
|---|---|---|
| Spoofing | Unauthorized service impersonating TokenizationService | Inner VPC-SC perimeter + IAM; TokenizationService is the only ingress |
| Tampering | Vault data modification by privileged user | Audit + two-person authorization for mass operations (AD-026) |
| Repudiation | Detok event without attribution | Audit on every detok; service-actor non-repudiation deferred to Phase 2 (ADR-0008); human-actor non-repudiation (WebAuthn) deferred to v2 |
| Info disclosure | PII leakage via memory dump | KMS HSM tier (R3 S-077); DEK caching with bounded TTL |
| Info disclosure | Frequency analysis via deterministic tokens | Keyed deterministic per ADR-0003 |
| DoS | Vault unavailability fails verification | Fail-closed per R2 F-108; graceful degradation |
| Elevation | KMS key extraction | HSM-backed; no plaintext key egress; Vault-only access |

### Verification

| Threat | Specific scenario | Mitigations |
|---|---|---|
| Spoofing | Forged JWT | RS256 + JWKS + jti replay cache per ADR-0004 |
| Tampering | Request body modification post-claim | TLS 1.2+ per ADR-0004; LB validates |
| Repudiation | Verification result claimed wrong | Per-request audit via outbox |
| Info disclosure | Existence inference via timing | Latency floor + equalization per ADR-0009 |
| Info disclosure | Existence inference via response shaping | Body padding to fixed length per ADR-0009 |
| DoS | DDoS on Verification | Cloud Armor (R3 S-054); rate limits |
| DoS | Brute-force enumeration | BR-402 lockout; identity-scoped rate limits |
| Elevation | Account takeover via verified claim | Verification ≠ authentication contracted (ADR-0009); Lore application requires independent factors |

### Member Rights

| Threat | Specific scenario | Mitigations |
|---|---|---|
| Spoofing | Adversary submits rights request as member | Identity verification at portal login per BR-1306; representative authority verification per BR-1303 |
| Tampering | Rights request modified in transit | TLS; outbox audit |
| Repudiation | Member denies submitting request | Audit on every action; member portal session log |
| Info disclosure | Cross-member rights data leakage | Per-resource authorization (AD-025; IDOR prevention) |
| DoS | Rights request flooding | Per-member rate limit |
| Elevation | Rights request submitter escalates to other member's data | IDOR prevention per AD-025; representative authority gates |

### Audit

| Threat | Specific scenario | Mitigations |
|---|---|---|
| Spoofing | Forged audit events | Workload Identity + schema validation; outbox-bound to originating operation |
| Tampering | Audit log modification | Bucket Lock + hash chain (BR-504) + cross-org replication + RFC 3161 timestamp (ADR-0008) |
| Tampering | Insider with admin access modifies audit IAM | Cross-organization replication (ADR-0008); IAM change alerts |
| Repudiation | Actor denies action | Audit captures principal; ADR-0008 service-actor non-repudiation Phase 2 |
| Info disclosure | Audit data leak | Auditor-only access; auditor query monitoring per R3 S-032 |
| DoS | Audit topic backlog | Pub/Sub backpressure; Dataflow scaling; outbox bounded growth |
| Elevation | Audit consumer compromise → tamper chain | Cross-org replication detects post-hoc; forensic preservation per ADR-0008 |

### Deletion

| Threat | Specific scenario | Mitigations |
|---|---|---|
| Spoofing | Forged deletion request | Out-of-band requester verification; identity verification per BR-1303; counsel-engaged verification flows |
| Tampering | Deletion executor manipulated | Two-person authorization (AD-026); audit emission |
| Repudiation | Deletion executed but not auditable | Audit on each step; high-criticality retention indefinite |
| Info disclosure | Deletion ledger reversibility | HMAC-keyed hash per ADR-0003; KMS-resident key |
| DoS | Mass deletion request | Rate limit + approval gate; two-person authorization |
| Elevation | Override path abuse | Two-person authorization (AD-026); `DELETION_OVERRIDE` audit event |

## Asset Classification (per R3 S-070)

| Asset | Confidentiality | Integrity | Availability |
|---|---|---|---|
| PII Vault (plaintext) | CRITICAL | CRITICAL | HIGH |
| Canonical Eligibility (operational) | HIGH (tokens) | CRITICAL | CRITICAL (verification path) |
| Audit log (high-criticality) | HIGH | CRITICAL | HIGH |
| Audit log (operational) | MEDIUM | HIGH | MEDIUM |
| Deletion ledger | HIGH | CRITICAL | MEDIUM |
| Match decisions | MEDIUM | HIGH | MEDIUM |
| Member rights records | HIGH | CRITICAL | HIGH |
| Configuration (Strategic tier) | MEDIUM | CRITICAL | HIGH |
| Configuration (other tiers) | LOW | HIGH | MEDIUM |
| Application code | MEDIUM | CRITICAL | HIGH |
| KMS keys (Vault) | CRITICAL | CRITICAL | HIGH |
| KMS keys (other) | HIGH | CRITICAL | HIGH |
| Splink models | LOW | HIGH (correctness affects matches) | MEDIUM |
| Operational logs (PII redacted) | LOW | MEDIUM | MEDIUM |
| Backup encryption keys | CRITICAL | CRITICAL | HIGH |

## Phased Delivery (AD-018)

Each phase has objective exit criteria. Following the Constitution's tier-exit pattern, no phase advances until criteria are met. Reviewers are scope-constrained per the current phase. Compliance and UX BLOCKERs are distributed across phases (per R8 P-071 and R8 P-072) to prevent end-loading.

### Phase 0: Foundation

**Goal:** Land the empty production substrate that everything else builds on; establish governance.

**Scope:** GCP projects (dev, staging, prod), VPC-SC perimeters (outer + inner), KMS keyrings (HSM tier for Vault), IAM groups mapped to BRD roles, Sequelae PH residency conditions, request-origin geofencing, IaC framework (Terraform), CI/CD pipelines, Artifact Registry, baseline observability per ADR-0006, Cloud Composer cluster, Pub/Sub topics with schemas, AlloyDB and Cloud SQL Vault instances at minimum size, outbox tables per context, processed_events tables per consumer.

Compliance Phase 0 work products: Privacy Officer + Security Officer designations; counsel engagement plan; foundational P&P documents; PHI inventory (BR-1202); risk assessment methodology (BR-1203); workforce sanctions policy (BR-1104); HIPAA documentation retention infrastructure (BR-1201).

UX Phase 0 work products: design system commitment; user research program plan; WCAG 2.1 AA audit commitment; inclusive design framework; trauma-informed design principles documented.

**Exit criteria:**

- IAM audit confirms residency conditions enforce as designed (BR-506)
- Request-origin geofencing verified (per BR-506 synthesis tightening)
- VPC-SC perimeter test confirms exfiltration paths are closed
- A no-op service deployable to Cloud Run hits all observability, logging, and audit-emission surfaces correctly (per ADR-0006)
- Tokenization smoke test (tokenize, detokenize, audit emission) passes end-to-end through the inner perimeter, demonstrating ADR-0003 keyed-deterministic primitive
- IaC drift detection runs daily without alerts
- CI/CD pipeline deploys via OIDC (no service account keys)
- Container Binary Authorization configured (signed images required)
- Privacy Officer + Security Officer designated and US-resident
- PHI inventory documented and counsel-reviewed
- 42 CFR Part 2 decision documented (BR-1402; per RR-006)
- Attestation roadmap decided (HITRUST or SOC 2; per RR-004)
- ARD `[part-2-implementation]`, `[member-portal-scope]`, `[reviewer-decision-support]`, `[friction-mechanism]`, `[iac-framework]`, `[dr-strategy]`, `[partner-sftp]`, `[sequelae-ph-ml-access]` ADRs all authored or scoped

### Phase 1: Single-Partner End-to-End

**Goal:** A single partner, real format, ingested through verification, with the architectural shape complete but feature surface minimal.

**Scope:** One format adapter (CSV likely; X12 834 if first partner delivers it), one partner YAML mapping, DQ engine with the Required tier only, Identity Resolution with deterministic anchor only (no Splink yet), Canonical Eligibility with state machine and SCD2, Verification API at the externally-correct shape (latency-equalized per ADR-0009; JWT per ADR-0004) reading only from canonical state, audit emission for every action class via outbox.

Compliance Phase 1 work products: NPP authoring (BR-901); first BAA executed; first partner data sharing agreement executed; subprocessor BAA chain documented.

UX Phase 1 work products: Verification failure UX coordination (BR-1301) — joint team work; lockout recovery service blueprint (BR-1308); member rights submission UX initial design.

**Exit criteria:**

- BR-202 transition table fully covered by tests
- Sample feed processed end-to-end with zero plaintext PII in any log (XR-005 LIVE-verified)
- Verification API returns correct outcome on canonical members and `NOT_VERIFIED` on synthetic non-members
- Latency-distribution test per ADR-0009 passes (statistical indistinguishability above floor)
- Audit redaction scan passes against representative log fixtures
- Datastream replication to BigQuery is working with lag under `DATASTREAM_LAG_TARGET_SECONDS`
- Audit chain validator running with zero breaks; external anchor publication operational
- Outbox publisher operational; consumer idempotency verified
- IaC drift detection clean; quarterly DR drill completed
- Privacy Officer signs off on Phase 1 production traffic readiness

### Phase 2: Production Cutover

**Goal:** All v1 BRs satisfied. System is production-defensible.

**Scope:** Splink integration with Tier 1 through Tier 4 evaluation, manual review queue and reviewer interface (with decision support per ADR `[reviewer-decision-support]`), brute force protection per BR-402, deletion workflow including ledger (HMAC-keyed per ADR-0003) and suppression, reconciliation jobs (BR-605), schema drift detection (BR-304), profile drift detection (BR-305), high-criticality audit tier with GCS Bucket Lock and hash chain + external anchoring (ADR-0008), member rights workflows (BR-901..908, BR-1301..1308), unmerge / canonical-identity-split path (AD-033).

Compliance Phase 2: Right of Access workflow (BR-903); complaint procedure (BR-908); breach notification infrastructure (BR-1001..1010); state law matrix (BR-1009); workforce training program LIVE.

UX Phase 2: Reviewer UX with tokenized data + decision support (R6 U-017); audit log forensic search UX (R6 U-037); member portal Phase-1-functionality.

**Exit criteria:**

- Every BR in the BRD is satisfied with passing tests
- Hash chain validator runs continuously, no breaks; external anchors verified
- Deletion ledger suppression demonstrated end-to-end on synthetic re-introduction scenarios
- Splink match weights are reproducible across runs given fixed configuration (per R2 F-135)
- All `[ADVISORY]` BRs have a documented process owner and review cadence
- Member rights workflow tested end-to-end (synthetic member submitting Right of Access; fulfillment within SLA)
- Member rights `[ADVISORY]` enforcement plan documented (counsel + compliance program ownership)
- HIPAA Privacy Rule infrastructure operational (NPP delivery, complaints, authorization tracking)
- Breach notification templates approved by counsel; tabletop exercise completed
- 50-state breach notification matrix authored
- Annual third-party security review completed (or scheduled)
- Two-person authorization for high-risk operations LIVE (AD-026)

### Phase 3: Scale to N Partners

**Goal:** Demonstrate the configuration-driven onboarding path with multiple partners and varied formats.

**Scope:** Onboard 5-10 partners with mixed formats (CSV, X12 834, fixed-width, JSON). Tune Splink thresholds against real cross-partner data. Establish DQ baselines per partner. Validate reconciliation flows. Subprocessor reviews. Partner-side deletion contracts.

UX Phase 3: Multi-partner reviewer workload tuning; partner self-service UX (if scoped).

**Exit criteria:**

- Onboarding a new partner is achievable in under one engineering-day from YAML PR to production-live
- No partner-specific code paths exist in production code (BR-802 enforcement)
- Cross-partner identity resolution (same person, two partners) is detected and handled correctly per BR-205
- Cross-partner correlation prevention verified (per ADR-0003 per-partner salts)
- Partner-side deletion notification path operational

### Phase 4: Hardening and Attestation Prep

**Goal:** SOC 2 Type II or HITRUST CSF readiness, depending on Lore's compliance roadmap (RR-004).

**Scope:** Penetration testing (per R3 S-052), third-party security review, runbook formalization, disaster recovery validation, audit log access review, BAA chain documentation finalized. Comprehensive accessibility audit (per XR-009).

UX Phase 4: Comprehensive accessibility audit; user research summary (R6 U-059).

**Exit criteria:** External attestation auditor's report with no high-severity findings.

## Prototype Scope

The interview deliverable runs a scoped subset of Phase 1 on the local substrate (AD-007). This section identifies what's in, what's stubbed, and how the production architecture remains visible behind the local implementation.

### In Scope for Prototype

- Format adapter for CSV (one format family)
- Mapping engine reading a YAML registry containing one or two synthetic partners
- DQ engine implementing field-tier validation, record-level quarantine, feed-level threshold gating
- Within-feed deduplication (BR-601)
- Snapshot-diff CDC against a prior snapshot (BR-602)
- Identity Resolution: Tier 1 deterministic plus Splink-on-DuckDB for Tier 2/3/4
- Canonical Eligibility schema in local Postgres with state machine and SCD2; outbox table; advisory locking
- Verification API as a thin FastAPI service returning `{VERIFIED, NOT_VERIFIED}` only, with latency floor (ADR-0009) demonstrated
- Deletion ledger with HMAC-keyed suppression check (ADR-0003 demonstrated with software KMS stub)
- Audit event emission to a local JSON Lines file via outbox; hash chain demonstrated
- Synthetic data harness producing partner feeds with seeded match scenarios

### Stubbed for Prototype

- **Cloud KMS replaced by local app-level encryption** with a static dev key. The TokenizationService interface is fully implemented; only the KMS backing is replaced. The interface is what the panel sees.
- **GCS Bucket Lock replaced by an append-only file** with hash chain in the same shape as production. Cross-organization replication and RFC 3161 anchoring are explained but not exercised.
- **Datastream replaced by a periodic sync script** that reads from Postgres and writes to a DuckDB analytical file. Pattern C separation preserved.
- **VPC-SC perimeters not applicable in local context.** Documented as the production intent.
- **Brute force protection demonstrated as logic, not against real attack traffic.**
- **Manual review queue exists as a Postgres table; no reviewer UI in the prototype.**
- **Cloud Composer replaced by a Python script orchestrating the pipeline run.**
- **Member Rights context not in prototype scope.** Documented as production intent.

### Demonstrative Goals

The prototype is built to make the following visible to the panel within a 60-minute walkthrough:

1. **Identity resolution with explainable scores.** Splink runs against synthetic data, produces match weights, and routes outcomes through the four tiers. The reviewer sees a Tier 3 case with the score breakdown.
2. **Cleansing in action.** A deliberately dirty feed (mixed-case names, varying date formats, near-duplicates, missing required fields) is processed; quarantined records are visible; profile baselines are captured.
3. **SCD2 history derivation.** A second-day snapshot triggers diff-CDC; SCD2 history is visible in queryable form.
4. **Deletion ledger suppression.** A deletion is executed; a subsequent feed re-introduces the deleted identity; the system suppresses it; the override path is demonstrated. HMAC-keyed mechanism (ADR-0003) is shown.
5. **Privacy-preserving collapse.** The verification API returns identical-shape responses across internal-state combinations; no log line in any service contains plaintext PII; the redaction scanner runs and reports clean. Latency floor demonstrated.

## Risk Register / Open Architectural Questions

(Re-formatted from prior "Open Architectural Questions" per R1 F-020 and R7 E-008. Risks tracked centrally; full executive risk register is in the corporate strategy repo, not duplicated here. This section captures architecture-bearing risks.)

| ID | Risk / Open Question | Likelihood | Impact | Owner | Decision deadline | Architectural branch if unfavorable |
| --- | --- | --- | --- | --- | --- | --- |
| RR-001 | Confirm BigQuery + Cloud Composer + AlloyDB + Cloud SQL Vault as production stack | Moderate | Material if any element non-confirmed | CTO + Data Engineering Lead | Phase 0 exit | Pattern C and Deployment Topology change |
| RR-002 | Partner contract terms beyond statutory requirements | Moderate | Material | Partnership Operations + counsel | Per-partner onboarding | Additional VPC-SC conditions; BAA terms |
| RR-003 | Existing identity model in Lore application | Low | Material if richer | CTO + Lore application Lead | Phase 0 | Verification API contract changes |
| RR-004 | HITRUST or SOC 2 attestation status and roadmap | High (decision pending) | Material (Phase 4 scope shift) | CISO + CEO | Phase 0 | Phase 4 scope changes |
| RR-005 | Splink threshold defaults | Moderate | Operational | ML lead | Phase 2 | Threshold deltas managed via BR-104 |
| RR-006 | 42 CFR Part 2 applicability per partner | Moderate | Material if applies | Privacy Officer + counsel | Phase 0 + per-partner | Per-partner Part 2 implementation |
| RR-007 | COPPA applicability | Low | Material if applies | Privacy Officer + counsel | Phase 0 | COPPA-compliant data flow |
| RR-008 | Vendor concentration (GCP) board acknowledgment | Low (catastrophic) | Existential | CTO + CEO + Board | Phase 0 | Multi-cloud abstraction expansion |
| RR-009 | Member portal scope | Decision pending | Material | CTO + Lore application Lead | Phase 0 | Scope reallocation |
| RR-010 | Reviewer interface build vs buy | Decision pending | Operational | Engineering Lead | Phase 1 | Build vs buy ADR |

## Bidirectional Cross-Reference Index (component → BR)

Per BRD XR-012, every component lists the BRs it implements. The reverse mapping (BR → component) is in the BRD §"Owning component" of each rule. Both sides validated by CI gate.

| Component | BRs implemented |
|---|---|
| Ingestion & Profiling: Landing zone | BR-302, BR-606 |
| Ingestion & Profiling: Format adapter | BR-301 (parsing), BR-302 (parse-error rows) |
| Ingestion & Profiling: Mapping engine | BR-301, BR-601, BR-602, BR-603, BR-604 |
| Ingestion & Profiling: Schema registry | BR-802, BR-801 |
| Ingestion & Profiling: DQ engine | BR-301, BR-302, BR-303, BR-304, BR-305, BR-306 |
| Ingestion & Profiling: Quarantine bucket | BR-302, BR-303, BR-306 |
| Ingestion & Profiling: Reconciliation engine | BR-605 |
| Ingestion & Profiling: Replay orchestrator | BR-606, BR-607 |
| Identity Resolution: Match orchestrator | BR-101, BR-102 |
| Identity Resolution: Splink runner | BR-101 (Tier 2/3/4), BR-104 |
| Identity Resolution: Match decision store | BR-104 |
| Identity Resolution: Manual review queue | BR-105 |
| Identity Resolution: Deletion-ledger suppression check | BR-703 (consumer side) |
| Canonical Eligibility: Operational store | BR-201, BR-205 |
| Canonical Eligibility: State machine engine | BR-201, BR-202, BR-203, BR-204 |
| Canonical Eligibility: SCD2 derivation | BR-202, BR-204, BR-606 |
| Canonical Eligibility: Analytical projection (BigQuery) | BR-205 (analytical), BR-503 (audit replication target) |
| Canonical Eligibility: Unmerge / split path | BR-103 (downstream effect) |
| PII Vault: Vault store | BR-502, BR-506 |
| PII Vault: TokenizationService | BR-502, BR-506 |
| PII Vault: Two-person authorization gate | BR-702, AD-026 |
| Verification: Verification API | BR-401, BR-402, BR-403, BR-404, BR-405 |
| Verification: Latency equalization layer | BR-401 (XR-003), BR-404 |
| Verification: Rate-limit cache | BR-402, XR-004 |
| Verification: Friction challenge layer | BR-402 |
| Verification: Lockout enforcement | BR-402, BR-403 |
| Verification: Public response collapse | BR-401, XR-003 |
| Member Rights: DSAR workflow service | BR-903, BR-904, BR-905, BR-906, BR-907 |
| Member Rights: NPP service | BR-901 |
| Member Rights: Member portal back-end | BR-1306 |
| Member Rights: Complaint workflow | BR-908 |
| Member Rights: Personal representative service | BR-1303 |
| Member Rights: Compliance dashboard | BR-1201 (review surface), BR-1202 (review surface) |
| Member Rights: Authorization tracking | BR-902 |
| Deletion: Deletion request intake | BR-701 |
| Deletion: Deletion executor | BR-702, BR-704 |
| Deletion: Deletion ledger | BR-703 |
| Deletion: Override path | BR-703 (override) |
| Deletion: SLA tracking | BR-701 |
| Audit: Audit emission topic | BR-501 |
| Audit: Audit consumer (Dataflow) | BR-501, BR-503 (routing per AD-027) |
| Audit: Operational tier sink | BR-501 (operational classes), BR-503 |
| Audit: High-criticality tier sink | BR-501 (high-criticality classes), BR-503, BR-504 |
| Audit: External table view | BR-501 (analyst access) |
| Audit: Hash chain validator | BR-504, BR-1010 |
| Audit: External anchor publisher | BR-504 |
| Audit: Redaction scanner | XR-005, BR-502 |
| Audit: Forensic export interface | BR-1010 |
| Audit: Auditor query monitoring | BR-505 |
| Cross-cutting: Configuration management library | XR-001, XR-002, XR-010 |
| Cross-cutting: Outbox + processed_events | (per ADR-0005, supports many BRs that emit/consume events) |
| Cross-cutting: PEP/PDP authorization library | BR-505, BR-506, AD-025 |
| Cross-cutting: Two-person authorization gate | AD-026 (BR-702, BR-703 override, BR-101 threshold change, etc.) |
| Cross-cutting: structlog logging + correlation_id | XR-005, ADR-0006 |
| Cross-cutting: Shared error catalog + retry decorator | ADR-0006 |
| Cross-cutting: Workforce training records system | BR-1103, BR-1104, BR-1105 |
| Cross-cutting: Documentation retention infrastructure | BR-1201 |
| Cross-cutting: PHI inventory | BR-1202, BR-1401 |
| Cross-cutting: Risk assessment framework | BR-1203 |
| Cross-cutting: P&P document store | BR-1204 |

## Closing Note

This ARD is a contract between the BRD and the implementation. Architectural decisions enumerated here may be revisited only by amendment with the same rigor that produced them: a cascading decision exchange, a stated rationale, named approver per BR-XR-011, and updated mappings. Any drift between the implementation and this document is a defect in the implementation, not a tacit amendment to the architecture.

Strategic context for these decisions lives in upstream business documents in the corporate strategy repository; the ARD is the technical expression of those strategic intents and references them rather than duplicating.
