# Architecture Requirements Document: Strategic Data System for Trusted Partner Eligibility and Identity Verification

## Document Purpose

This document specifies the architecture that satisfies the business rules in BRD.md. It commits to specific technologies, deployment topology, service decomposition, data schemas, and integration patterns. Where the BRD says what must be true, this ARD says how the system is built to make it true.

Every architectural decision is numbered (AD-NNN), traceable, and reversible only by amendment to this document. The Architectural Decision Ledger near the top of the document is the authoritative summary; the body sections elaborate.

The ARD is written to the production target. A separate Prototype Scope section near the end identifies the subset of the architecture that runs on the local substrate for the interview deliverable, and how the deviation from production is bounded.

## Relationship to Other Documents

- **PROBLEM_BRIEF.md** captured the problem space. Upstream of everything.
- **BRD.md** captured the business rules, cross-cutting policies, configuration parameters, NFRs, and assumptions. Direct upstream of this ARD. The ARD takes no position on business rules; conflicts with the BRD are resolved in favor of the BRD.
- **TECH_STACK.md** captured public signal on Lore's likely stack (GCP confirmed, Airflow confirmed, Python confirmed). Informs but does not constrain.
- **RESEARCH_NOTES.md** captured public signal on Lore's engineering organization. Informs ownership and staffing decisions.
- **CONTEXT.md** identifies the panel interviewers and squad mappings.

## Architectural Decision Ledger

| ID | Decision | Section |
| --- | --- | --- |
| AD-001 | Seven bounded contexts: Ingestion & Profiling, Identity Resolution, Canonical Eligibility, PII Vault, Verification, Deletion, Audit | Bounded Context Architecture |
| AD-002 | Wayfinding squad owns Verification end-to-end | Bounded Context Architecture / Verification |
| AD-003 | Sequelae PH staff may own Ingestion, Identity Resolution, Canonical Eligibility, Verification, Audit; Vault, Deletion, and Break-Glass are US-only | Deployment Topology / IAM |
| AD-004 | Pattern C: operational store canonical for verification, analytical store derived via CDC | Operational vs. Analytical Separation |
| AD-005 | Operational history window 90 days; older history is BigQuery-only | Operational vs. Analytical Separation |
| AD-006 | Datastream for production CDC; simple sync script in prototype | Operational vs. Analytical Separation |
| AD-007 | Prototype substrate: local Postgres in Docker plus DuckDB | Prototype Scope |
| AD-008 | PII Vault Option 1: Cloud KMS plus application-level tokenization plus hardened Cloud SQL inside VPC-SC, behind a `TokenizationService` interface | PII Vault Context |
| AD-009 | Random tokens for non-deterministic PII fields; deterministic non-FPE tokens for joinable identifiers; joinability declared in config | PII Vault Context |
| AD-010 | Synchronous per-record detokenization only for v1; batch detokenization roadmap | PII Vault Context |
| AD-011 | Splink for identity resolution; Fellegi-Sunter probabilistic record linkage with explainable per-pair match weights | Identity Resolution Context |
| AD-012 | Splink on DuckDB in prototype; Splink on BigQuery in production v1; Spark backend held in reserve | Identity Resolution Context |
| AD-013 | Tiered audit storage: BigQuery native for operational events; GCS Bucket Lock plus BigQuery external table for high-criticality events | Audit Context |
| AD-014 | GCS Bucket Lock retention 7 years, matching `AUDIT_RETENTION_PII_YEARS`; one-way commit accepted | Audit Context |
| AD-015 | Single SQL query surface in BigQuery, with high-criticality events surfaced through external tables over GCS | Audit Context |
| AD-016 | Two-layer schema mapping: code-resident format adapters per format family; declarative YAML per-partner mapping in a versioned registry | Cross-Cutting Patterns / Schema Mapping |
| AD-017 | Single primary US region (us-central1), multi-AZ, three environments (dev/staging/prod), VPC-SC perimeter with stricter inner perimeter around the Vault, Cloud Run for stateless services, Cloud Composer for orchestration, Pub/Sub plus Dataflow for streaming | Deployment Topology |
| AD-018 | Five-phase delivery: foundation, single-partner end-to-end, production cutover, scale, hardening | Phased Delivery |

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
                               v
                     +-------------------+
                     | Identity Resolver |  Splink, comparing staging records
                     | (Cloud Run job,   |  against canonical history
                     |  Splink-on-BQ)    |
                     +---------+---------+
                               |
                               v
                     +-------------------+         +---------------------+
                     | Canonical         |  --->   | Manual Review Queue |
                     | Eligibility       |         | (Postgres-backed)   |
                     | (AlloyDB/CloudSQL |         +---------------------+
                     |  Postgres)        |
                     +---+--------+------+
                         |        |
              CDC        |        | direct read
              (Datastream)        v
                         |  +-------------------+
                         |  | Verification API  |  Wayfinding-owned (AD-002)
                         |  | (Cloud Run)       |  external states {VERIFIED, NOT_VERIFIED}
                         v  +-------------------+
              +----------------+
              | BigQuery       |  full SCD2 history, analytics, ML feature store,
              | (analytical)   |  audit external tables over GCS
              +----------------+

  PII Vault (Cloud SQL + KMS, inner VPC-SC perimeter, US-only IAM)
       ^                                                             ^
       | TokenizationService API (Cloud Run)                         | break-glass detok
       +-------------------------------------------------------------+
       all services token-only; vault is the only plaintext PII surface

  Audit emission: every service publishes to Pub/Sub `audit-events` topic;
  Dataflow consumer fans out to BigQuery (operational tier) and GCS Bucket
  Lock (high-criticality tier with hash chain)
```

## Bounded Context Architecture

Each context is a deployable boundary, an ownership boundary, and a data product. Cross-context communication is through published contracts (API or event topic), never through shared databases.

### Ingestion & Profiling

**Purpose:** Convert raw partner files into validated canonical staging records, with per-feed quality assessment and quarantine of records or feeds that fail the rules in BR-301 through BR-306.

**Boundary:** "raw partner file" to "validated staging record awaiting identity resolution."

**Owner:** Data engineering. Sequelae PH eligible (operates on tokenized surfaces and pre-canonical staging only).

**Components:**

- **Landing zone.** Cloud Storage bucket per partner, versioned, lifecycle-policy-retained for the audit retention window. Source files are immutable once landed; reprocessing reads from here (BR-606).
- **Format adapter (per format family).** Cloud Run jobs implementing the adapter pattern from AD-016. One adapter per format family, not per partner. Adapters parse to a common intermediate row representation.
- **Mapping engine.** Cloud Run job that reads the per-partner YAML mapping from the schema registry, applies normalization rules, and emits canonical staging records. New partners equal new YAML; new format families equal new adapter.
- **Schema registry.** Git repository of per-partner YAML files, versioned alongside code. Changes go through the same review pipeline as application code. The registry is the source of truth for partner mappings, not a database.
- **DQ engine.** Cloud Run job that applies field-tier validation (BR-301), record-level quarantine (BR-302), feed-level threshold gating (BR-303), schema drift detection (BR-304), and profile drift detection (BR-305). Emits DQ events to the audit topic.
- **Quarantine bucket.** Cloud Storage bucket for rejected records and quarantined feeds, retained for forensic replay (BR-302).

**Inbound contract:** Partner files arrive via SFTP (production) into the landing zone, or directly into the landing bucket via partner-side service account if the partner can write to GCS.

**Outbound contract:** Validated staging records published to the `staging-records` Pub/Sub topic, partitioned by partner. Identity Resolution subscribes.

**BRs implemented:** BR-301 through BR-306, BR-601, BR-602, BR-603, BR-604.

### Identity Resolution

**Purpose:** Decide whether a staging record represents a known canonical identity (and which) or a new identity, per the tiered match policy in BR-101 through BR-105.

**Boundary:** "two records, same person?"

**Owner:** Data engineering / ML. Sequelae PH eligible.

**Components:**

- **Match orchestrator.** Cloud Run job that consumes from `staging-records`, applies Tier 1 deterministic anchor evaluation in SQL against Canonical Eligibility, and routes ties or non-matches to Splink for Tier 2 / 3 / 4 evaluation.
- **Splink runner.** Cloud Run job invoking Splink against the BigQuery backend (AD-012). Splink generates blocking and comparison SQL; BigQuery executes; scored pairs return. Match weights and per-comparison contributions are persisted alongside each decision.
- **Match decision store.** Postgres table inside Canonical Eligibility holding `match_decision` rows: candidate record, resolved canonical identity, tier outcome, score, algorithm version, configuration version (BR-104).
- **Manual review queue.** Postgres-backed work queue. Tier 3 outcomes produce queue entries (BR-105). Reviewer interface is a thin internal application reading and writing this table; reviewers see tokenized identifiers only.

**Inbound contract:** Subscribes to `staging-records`.

**Outbound contract:** Publishes `match-decisions` events. Canonical Eligibility consumes and applies updates.

**BRs implemented:** BR-101 through BR-105.

### Canonical Eligibility

**Purpose:** The headline data product. Holds the canonical member entity, partner enrollment many-to-one, lifecycle state, SCD2 history. Source of truth for verification reads.

**Boundary:** "what is true about this person at time T?"

**Owner:** Data engineering, with Wayfinding squad as primary consumer through Verification. Sequelae PH eligible.

**Components:**

- **Operational store.** AlloyDB for PostgreSQL (production target) holding current state plus the bounded history window per AD-005 (90 days). Schema in the Data Schemas section below.
- **State machine engine.** Application code enforcing the BR-202 transition table. Transition logic is centralized; no service mutates state without going through this layer.
- **SCD2 derivation.** On every update, prior state is closed (effective_to set) and new state opened (effective_from set). The operational store retains 90 days; older history flows to BigQuery via Datastream.
- **Analytical projection.** BigQuery dataset `canonical_eligibility` holding full SCD2 history. Datastream-replicated from the operational store.

**Inbound contract:** Subscribes to `match-decisions`. Receives lifecycle events from time-based jobs (grace period elapse).

**Outbound contract:** Publishes `lifecycle-events` for state transitions. Exposes a read-only query interface to Verification.

**BRs implemented:** BR-201 through BR-206, plus serving for BR-401 and BR-404.

### PII Vault

**Purpose:** The only place plaintext PII lives. Tokenization in, detokenization out, KMS-mediated keys, audited per access.

**Boundary:** "the only plaintext-PII surface."

**Owner:** Security and platform engineering. **US-resident personnel only** per BR-506.

**Components:**

- **Vault store.** Cloud SQL for PostgreSQL instance inside an inner VPC-SC perimeter. Distinct from the Canonical Eligibility AlloyDB instance. Schema is intentionally narrow: token, plaintext PII fields encrypted at rest with field-level encryption, KMS DEK per record, creation timestamp, last-detok timestamp, deletion tombstone flag.
- **TokenizationService.** Cloud Run service exposing the `TokenizationService` interface (defined in API Contracts). All callers go through this service; no service has direct DB access to the vault. Mediates Cloud KMS for envelope encryption.
- **KMS keyring.** Cloud KMS keyring scoped to the vault project, with separate keys per environment and per token class. Auto-rotation on the standard schedule.
- **Inner VPC-SC perimeter.** Service perimeter containing only the vault project resources. Egress and ingress restricted to a published allow-list of caller identities (TokenizationService, Break-Glass paths).

**Inbound contract:** TokenizationService API.

**Outbound contract:** Audit events on every tokenize, detokenize, and tombstone. Published to `audit-events` topic.

**BRs implemented:** BR-502, BR-506, BR-702 (vault purge).

**Future swap:** AD-008 commits to Option 1 with a clean abstraction. Migration to Skyflow or self-hosted Vault means replacing TokenizationService implementation; callers do not change.

### Verification

**Purpose:** Public-facing identity verification API serving the Lore application's account creation flow. Privacy-preserving collapse and brute force protection per BR-401, BR-402, BR-403.

**Boundary:** "is this identity claim valid?"

**Owner:** **Wayfinding squad** (Mike Griffin's squad, AD-002). Sequelae PH eligible.

**Components:**

- **Verification API.** Cloud Run service. Stateless. Reads from Canonical Eligibility's operational store via internal query interface. Writes only to the rate-limit cache and the audit topic.
- **Rate-limit cache.** Cloud Memorystore (Redis) holding identity-scoped failure counters per BR-402 and XR-004. Keys rotate on `BRUTE_FORCE_WINDOW_HOURS`.
- **Friction challenge layer.** External CAPTCHA-equivalent integration (reCAPTCHA Enterprise as the default). Triggered on second failure per BR-402.
- **Lockout enforcement.** Application logic asserting that the third failure within the window flips the identity into a `LOCKED` flag in the rate-limit cache, separate from the canonical state. Lockout is recovery-out-of-band only (BR-402, BR-403).
- **Public response collapse.** Application logic ensures the response set is exactly `{VERIFIED, NOT_VERIFIED}` regardless of internal state. Internal state is logged to audit; never crosses the public surface (BR-401, XR-003).

**Inbound contract:** External HTTPS API at the Lore application's domain. See API Contracts.

**Outbound contract:** Reads canonical state. Writes verification audit events.

**BRs implemented:** BR-401 through BR-405.

### Deletion

**Purpose:** Right-to-deletion lifecycle. Verified request to vault purge to ledger insertion to suppression on subsequent ingestion.

**Boundary:** "this person no longer exists in our system."

**Owner:** Security and compliance. **US-resident personnel only** per BR-506.

**Components:**

- **Deletion request intake.** Internal interface where verified deletion requests are recorded. Identity verification of the requester is a precondition handled out of band (BR-701).
- **Deletion executor.** Cloud Run job that orchestrates the BR-702 sequence: vault purge, canonical record tombstone, deletion ledger insert, audit emission.
- **Deletion ledger.** Postgres table inside Canonical Eligibility holding one-way hashes of match-relevant attributes per BR-703. Schema in the Data Schemas section. The ledger is queried during ingestion for suppression; the suppression check lives in Identity Resolution but reads from this table.

**Inbound contract:** Internal-only. Deletion request intake.

**Outbound contract:** Audit events. Lifecycle event into Canonical Eligibility for the state transition to `DELETED`.

**BRs implemented:** BR-701 through BR-704.

### Audit

**Purpose:** Capture, store, and serve audit events with retention, immutability, and access control per BR-501 through BR-505.

**Boundary:** "what happened, who did it, when, and can we prove it."

**Owner:** Security and compliance. Sequelae PH eligible for read access on operational tier; high-criticality reads US-only.

**Components:**

- **Audit emission topic.** Pub/Sub topic `audit-events`. Every service publishes here. Schema is enforced via Pub/Sub schema validation.
- **Audit consumer (Dataflow).** Streaming Dataflow job that reads from `audit-events`, fans out to two sinks based on event class:
  - **Operational tier sink:** Direct write to BigQuery dataset `audit_operational`. Time-partitioned by event date, table-level ACL grants write to the Dataflow service account only, read to the `Auditor` role only.
  - **High-criticality tier sink:** Append to a GCS Bucket Lock'd object stream (`audit_high_criticality` bucket, retention policy 7 years per AD-014, `LOCKED`). Hash chain anchored in the GCS stream: each event includes a hash of itself plus the prior event's hash; chain breaks are detectable.
- **External table view.** BigQuery external table over the GCS bucket, exposing the high-criticality stream through the same SQL surface as operational events (AD-015).
- **Hash chain validator.** Scheduled Cloud Run job reading the GCS stream and verifying chain continuity. Pages on any break.
- **Redaction scanner.** Scheduled Cloud Run job scanning a sampled slice of audit events against PII regex patterns per XR-005. Pages on any match.

**Inbound contract:** `audit-events` Pub/Sub topic. Schema-validated.

**Outbound contract:** BigQuery dataset (read-only via IAM) and BigQuery external table.

**BRs implemented:** BR-501 through BR-505, plus enforcement of XR-005 and XR-006.

## Operational vs. Analytical Separation Pattern (Pattern C)

The verification API has a sub-200ms p95 latency requirement (BR-404). BigQuery is not a sub-200ms point-lookup database. Pattern C resolves this by making the operational Postgres-flavored store (AlloyDB) the canonical source of truth for verification, with BigQuery as a derived analytical surface.

### Read Paths

- **Verification reads:** Verification API queries Canonical Eligibility's AlloyDB. Indexed lookups on tokenized identifier and on the deterministic anchor composition (BR-102). Sub-200ms achievable with proper index coverage.
- **Analytical reads:** Internal users, ML feature engineering, audit reconstruction, point-in-time queries older than the operational window query BigQuery.

### Write Path

- All writes target AlloyDB first. Datastream replicates to BigQuery with target lag under 60 seconds.
- BigQuery is read-only at the application layer; the only writer is Datastream (and the ETL jobs that derive feature tables).

### Operational History Window

The operational store retains current state plus a 90-day rolling SCD2 history window per AD-005, governed by `OPERATIONAL_HISTORY_WINDOW_DAYS`. Beyond the window, history is BigQuery-only. Justification:

- Verification needs current state, not history. The window serves debug, recent-change reconstruction, and short-window point-in-time queries.
- 90 days exceeds the default grace period (30 days, BR-203) by a 3x factor, ensuring that grace-period transitions remain visible to the operational layer.
- Configurable per the BRD's layering pattern. Partners with longer grace periods can have the window extended.

### Failure Modes and Reconciliation

- **Datastream lag exceeds threshold.** Page on lag. BigQuery becomes stale; analytics is degraded but verification is unaffected because verification reads AlloyDB, not BigQuery.
- **AlloyDB outage.** Verification fails. The system falls back to a `NOT_VERIFIED` response per privacy-preserving collapse (XR-003), since revealing "system unavailable" externally is itself a leak. Internal alerting fires immediately.
- **Drift between AlloyDB and BigQuery.** Periodic reconciliation job (separate from BR-605 partner reconciliation) compares row counts and checksums between the two surfaces and pages on mismatch beyond a threshold.

### CDC Mechanism

Production v1 uses Datastream (GCP-managed Postgres-to-BigQuery CDC). The choice is encapsulated by Pattern C: nothing else in the architecture cares how rows get from AlloyDB to BigQuery. Reversibility is preserved.

## Cross-Cutting Architectural Patterns

### Configuration Management

**Pattern:** Layered configuration with deterministic resolution order: per-load > per-contract > per-partner > global default. Resolution is implemented in a single library used by every service. Every parameter named in BRD's configuration parameter table is resolved through this library. Inline numeric and duration literals in implementation code matching parameter names trigger CI failure (XR-001, XR-002).

**Implementation:** Configuration source of truth is a Git repository of YAML files; deployed configuration is materialized into Cloud Storage and watched by a config-reload library in each service. Hot-reload supported for parameters that don't require service restart; restart-required parameters are documented as such in the parameter registry.

**Audit:** Every configuration change emits a `CONFIGURATION_CHANGE` audit event (BR-501).

### TokenizationService Interface

**Pattern:** All PII flows through a single service interface. No service holds plaintext outside the vault. Interface is stable across implementation swaps (AD-008 commits to Option 1, with Option 2 / 3 as roadmap).

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
        Audit event emitted. Caller role and purpose recorded."""

    def detokenize(
        self,
        token: Token,
        caller_role: Role,
        purpose: AuditPurpose,
    ) -> PlaintextValue:
        """Detokenize a single token. Synchronous only (AD-010).
        Caller role must be PII_HANDLER or BREAK_GLASS_ADMIN.
        Audit event emitted. Caller residency enforced at IAM layer."""

    def tombstone(
        self,
        token: Token,
        deletion_request_id: DeletionRequestId,
    ) -> None:
        """Irreversibly purge plaintext for this token. Token remains
        addressable for audit log resolution (resolves to TOMBSTONED)."""
```

Token classes are declared in config (AD-009): joinable identifiers like `partner_member_id` get deterministic non-FPE tokens; non-joinable PII gets random tokens. Joinability is a property of the class, never implicit.

### Audit Emission Pattern

**Pattern:** Every service publishes audit events to a single Pub/Sub topic. Event schema is enforced at the topic level. The Audit context's Dataflow consumer fans out by event class (operational tier vs. high-criticality tier per AD-013).

**Why a topic, not direct writes:** Decouples emitters from storage. Storage tiering (BR-503), retention policies (BR-503), and immutability mechanism (BR-504) are concerns of the consumer and the sink. Emitters publish a record; what happens to it after is the Audit context's problem.

**Schema:** Every event carries minimum fields per BR-502: actor (role plus principal), action class, target (tokenized identifier), timestamp, outcome, trigger. Service-specific events extend the schema with additional fields scoped to their concern, validated against per-class schemas in the Audit consumer.

### Schema Mapping Mechanism (AD-016)

**Pattern:** Two layers. Format adapters live as code, one per format family. Per-partner mappings live as YAML.

**Format adapter (code).** A Python class per format family implementing a uniform interface: `parse(file) -> Iterator[IntermediateRow]`. The intermediate row is a partner-agnostic dict-like structure with raw values plus source-line metadata for forensic replay. Adapter count grows with format diversity, not partner count. Six families are anticipated for v1: CSV, fixed-width, X12 834, JSON, XML, and Parquet.

**Per-partner YAML (config).** Each partner has a YAML file in the schema registry declaring:

- partner_id and human-readable name
- format_family (selects adapter)
- column-to-canonical-field mappings, with explicit field-tier assignment per BR-301
- normalization rules per field (uppercase, trim, date format, phone format, etc.)
- partner-specific configuration overrides (cadence, grace period, thresholds)
- DQ baseline metadata (populated after onboarding sample profiling per BR-305)

**Onboarding (BR-801, BR-802).** Adding a partner is a YAML pull request plus a sample feed dropped into the staging onboarding bucket. Configuration-driven, no code change unless a structurally novel format requires a new adapter (rare).

## Deployment Topology (AD-017)

### Region and Zones

- **Primary region:** us-central1. Justification: GCP's most feature-complete region, lowest service rollout lag, established BAA support across the relevant services.
- **Multi-zone:** All stateful services (AlloyDB, Cloud SQL Vault, Cloud Composer, GCS) deployed multi-zone. Zonal failures absorbed without manual intervention.
- **No multi-region active-active for v1.** Per Assumption A27. Disaster recovery via cross-region backup replication for AlloyDB and the Vault, target RTO 4 hours and RPO 15 minutes for v1.

### Environments

Three environments: `dev`, `staging`, `prod`. Hard separation: separate GCP projects, separate VPC-SC perimeters, separate KMS keyrings, separate Artifact Registries. Service accounts and IAM bindings do not cross environments. Synthetic-only data in dev and staging; only `prod` carries real PII.

### VPC Service Controls Perimeters

Two perimeters in `prod`:

- **Outer perimeter:** Encloses the prod project. All system services live here. Internet egress allowed only to partner-side endpoints (SFTP) and CAPTCHA-equivalent provider. Internet ingress allowed only to the public Verification API behind a load balancer.
- **Inner perimeter:** Encloses the Vault project resources only. Ingress allowed only from the TokenizationService service account. Egress denied. The TokenizationService is the only service that crosses the inner perimeter; every other service is fenced out architecturally.

### Identity and Access (AD-003)

- **SSO:** Google Workspace, mapped to IAM groups by role.
- **Role mappings:** Each role from the BRD's Role Taxonomy maps to an IAM group. Role membership is auditable through Workspace logs and IAM audit logs.
- **Sequelae PH boundary:** A Workspace-attribute condition gates membership in the `pii_handler@` and `break_glass@` groups to US-resident accounts only. Sequelae PH accounts are organizationally segregated and cannot be added to these groups by IAM policy. Tested by the IAM audit referenced in BR-506 enforcement.
- **Break-glass:** Time-boxed grants via Privileged Access Manager. Default ceiling 4 hours. Every grant emits a `BREAK_GLASS_GRANTED` audit event; every revocation a `BREAK_GLASS_REVOKED` event.

### Service Hosting

- **Stateless services** (Verification API, TokenizationService, Format Adapters, Mapping Engine, DQ Engine, Match Orchestrator, Splink Runner, Deletion Executor): Cloud Run.
- **Streaming consumers** (Audit Consumer): Dataflow.
- **Orchestration:** Cloud Composer (managed Airflow per the confirmed signal in TECH_STACK.md). Composer DAGs orchestrate the daily pipeline runs, reconciliation jobs, time-based lifecycle transitions (grace period elapse), and the redaction scanner.
- **Stateful stores:** AlloyDB for Postgres (Canonical Eligibility), Cloud SQL for Postgres (Vault), Cloud Memorystore Redis (rate-limit cache), Cloud Storage (raw landing, quarantine, audit high-criticality), BigQuery (analytical surface, audit operational tier).

### Streaming and Eventing

- **Pub/Sub topics:** `staging-records`, `match-decisions`, `lifecycle-events`, `audit-events`, `deletion-requests`. Each has a defined schema.
- **Dataflow jobs:** Audit Consumer (one per event class fan-out target). Reconciliation Sink (writes reconciliation events into BigQuery for trend analysis).

### Observability

- **Logs:** Cloud Logging across all services. Routed to BigQuery via log sink for analytical access. **Subject to XR-005 in full**: no PII in any log payload, ever; redaction scanner enforces.
- **Metrics:** Cloud Monitoring. Standard SLO dashboards per service. Verification API dashboard surfaces p50/p95/p99 latency (BR-404), success rate (BR-405), and brute-force trigger rate.
- **Traces:** Cloud Trace at the Verification API and TokenizationService, with sampling configured to keep trace storage bounded.
- **Alerting:** PagerDuty integration on Priority 0 conditions (verification latency breach, vault-side errors, audit hash chain break, redaction scanner match).

## Data Schemas

The brief asks for SQL DDL for key tables. The following are the operational-store (AlloyDB / Postgres) schemas for the canonical model. The BigQuery analytical projections are derived via Datastream and use logically equivalent shapes with BigQuery type mappings.

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
    -- tokenized identifiers (joinable)
    name_token           TEXT         NOT NULL,
    dob_token            TEXT         NOT NULL,
    -- tokenized identifiers (non-joinable, vault-resolvable only)
    address_token        TEXT,
    phone_token          TEXT,
    email_token          TEXT,
    ssn_token            TEXT,
    -- metadata
    first_seen_at        TIMESTAMPTZ  NOT NULL,
    last_updated_at      TIMESTAMPTZ  NOT NULL,
    tombstoned_at        TIMESTAMPTZ
);

CREATE INDEX idx_canonical_member_state ON canonical_member(state);
CREATE INDEX idx_canonical_member_anchor ON canonical_member(name_token, dob_token);
```

State transitions are enforced by application code per BR-202, not by trigger, to keep the transition table testable in isolation.

### partner_enrollment

```sql
CREATE TABLE partner_enrollment (
    enrollment_id        UUID         PRIMARY KEY,
    member_id            UUID         NOT NULL REFERENCES canonical_member(member_id),
    partner_id           TEXT         NOT NULL,
    partner_member_id    TEXT         NOT NULL,
    effective_from       DATE         NOT NULL,
    effective_to         DATE,
    last_seen_in_feed_at TIMESTAMPTZ  NOT NULL,
    -- partner-supplied attributes (tokenized)
    partner_attributes   JSONB        NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (partner_id, partner_member_id, effective_from)
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
    change_event_id      UUID         NOT NULL
);

CREATE INDEX idx_member_history_member_time ON member_history(member_id, state_effective_from);
CREATE INDEX idx_member_history_change_event ON member_history(change_event_id);
```

`member_history` retains the operational window (90 days, AD-005). Datastream replicates to BigQuery `canonical_eligibility.member_history` which is unbounded retention.

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
    decided_at           TIMESTAMPTZ  NOT NULL,
    score_breakdown      JSONB
);

CREATE INDEX idx_match_decision_member ON match_decision(resolved_member_id);
CREATE INDEX idx_match_decision_tier ON match_decision(tier_outcome);
```

Algorithm and configuration version stamps satisfy BR-104. `score_breakdown` retains Splink's per-comparison weights for explainability.

### deletion_ledger

```sql
CREATE TABLE deletion_ledger (
    ledger_id            BIGSERIAL    PRIMARY KEY,
    -- one-way hash inputs are normalized match-relevant attributes only
    suppression_hash     TEXT         NOT NULL UNIQUE,
    deleted_at           TIMESTAMPTZ  NOT NULL,
    deletion_request_id  UUID         NOT NULL,
    override_count       INT          NOT NULL DEFAULT 0
);

CREATE INDEX idx_deletion_ledger_hash ON deletion_ledger(suppression_hash);
```

The ledger holds no recoverable PII per BR-703. `suppression_hash` is computed as `SHA256(salt || normalized_name || dob_token || partner_member_id_hash)` where the salt is environment-scoped and the inputs are deterministic. Identity Resolution queries this table on every staging record before publication.

### review_queue

```sql
CREATE TABLE review_queue (
    queue_id             UUID         PRIMARY KEY,
    decision_id          UUID         NOT NULL REFERENCES match_decision(decision_id),
    candidate_record_ref TEXT         NOT NULL,
    candidate_member_ids UUID[]       NOT NULL,
    score                NUMERIC(8, 6) NOT NULL,
    queued_at            TIMESTAMPTZ  NOT NULL,
    claimed_by           TEXT,
    claimed_at           TIMESTAMPTZ,
    resolved_at          TIMESTAMPTZ,
    resolution           TEXT         CHECK (resolution IN ('MERGE', 'DISTINCT', 'ESCALATE'))
);

CREATE INDEX idx_review_queue_unresolved ON review_queue(queued_at) WHERE resolved_at IS NULL;
```

Tier 3 outcomes per BR-101 produce queue entries. Reviewers see tokenized references only; resolving a queue item to MERGE triggers a state transition on the canonical record.

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
    context              JSON
)
PARTITION BY DATE(timestamp)
CLUSTER BY event_class, actor_role
OPTIONS (
    partition_expiration_days = 730  -- AUDIT_RETENTION_OPS_YEARS = 2
);
```

The high-criticality external table mirrors this shape but reads from the GCS Bucket Lock'd object stream and includes additional columns for prior-event hash and self hash to support BR-504 chain validation.

## API Contracts

### Verification API (Public)

The only public surface of the system. Wayfinding-owned (AD-002).

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

Response:

```json
{
  "outcome": "VERIFIED|NOT_VERIFIED",
  "request_id": "string"
}
```

The response set is exactly two values per BR-401 and XR-003. No internal state, no error codes that distinguish reasons, no headers that carry information beyond what the body conveys. The response time is consistent across all internal outcomes (latency-equalized to prevent timing-based inference).

Authentication: mTLS at the load balancer plus a short-lived JWT issued by the Lore application's auth service. The Verification API validates the JWT and authorizes by client_id.

### TokenizationService API (Internal)

See the interface specification in the TokenizationService Interface section above. Surfaced as a Cloud Run service with HTTP/gRPC endpoints. Caller authentication via service-account-bound IAM. Caller authorization additionally checked by role per BR-506 and AD-003 residency.

### Manual Review API (Internal)

Backs the reviewer interface.

- `GET /v1/review/queue?status=unresolved` — list unresolved queue items
- `POST /v1/review/queue/{queue_id}/claim` — claim an item for review
- `POST /v1/review/queue/{queue_id}/resolve` — resolve with MERGE / DISTINCT / ESCALATE

Reviewers see tokenized identifiers and Splink score breakdowns. They do not see plaintext PII. Resolution actions emit audit events.

### Deletion Request API (Internal)

- `POST /v1/deletion/request` — record a verified deletion request (verification of requester identity is a precondition handled out of band)
- `GET /v1/deletion/{request_id}` — status query

Both internal-only, behind the Security and Compliance role.

## Phased Delivery (AD-018)

Each phase has objective exit criteria. Following the Constitution's tier-exit pattern, no phase advances until criteria are met. Reviewers are scope-constrained per the current phase.

### Phase 0: Foundation

**Goal:** Land the empty production substrate that everything else builds on.

**Scope:** GCP projects (dev, staging, prod), VPC-SC perimeters (outer plus inner), KMS keyrings, IAM groups mapped to BRD roles, Sequelae PH residency conditions, CI/CD pipelines, Artifact Registry, baseline observability, Cloud Composer cluster, Pub/Sub topics with schemas, AlloyDB and Cloud SQL Vault instances at minimum size.

**Exit criteria:**

- IAM audit confirms residency conditions enforce as designed (BR-506)
- VPC-SC perimeter test confirms exfiltration paths are closed
- A no-op service deployable to Cloud Run hits all observability, logging, and audit-emission surfaces correctly
- Tokenization smoke test (tokenize, detokenize, audit emission) passes end-to-end through the inner perimeter

### Phase 1: Single-Partner End-to-End

**Goal:** A single partner, real format, ingested through verification, with the architectural shape complete but feature surface minimal.

**Scope:** One format adapter (CSV is the simplest; X12 834 if the first partner delivers it), one partner YAML mapping, DQ engine with the Required tier only, Identity Resolution with deterministic anchor only (no Splink yet), Canonical Eligibility with state machine and SCD2, Verification API at the externally-correct shape but reading only from canonical state, audit emission for every action class.

**Exit criteria:**

- BR-202 transition table fully covered by tests
- Sample feed processed end-to-end with zero plaintext PII in any log
- Verification API returns correct outcome on canonical members and `NOT_VERIFIED` on synthetic non-members
- Audit redaction scan passes against representative log fixtures
- Datastream replication to BigQuery is working with lag under 60 seconds

### Phase 2: Production Cutover

**Goal:** All v1 BRs satisfied. System is production-defensible.

**Scope:** Splink integration with Tier 1 through Tier 4 evaluation, manual review queue and reviewer interface, brute force protection per BR-402, deletion workflow including ledger and suppression, reconciliation jobs (BR-605), schema drift detection (BR-304), profile drift detection (BR-305), high-criticality audit tier with GCS Bucket Lock and hash chain.

**Exit criteria:**

- Every BR in the BRD is satisfied with passing tests
- Hash chain validator runs continuously, no breaks
- Deletion ledger suppression demonstrated end-to-end on synthetic re-introduction scenarios
- Splink match weights are reproducible across runs given fixed configuration
- All `[ADVISORY]` BRs have a documented process owner and review cadence

### Phase 3: Scale to N Partners

**Goal:** Demonstrate the configuration-driven onboarding path with multiple partners and varied formats.

**Scope:** Onboard 5 to 10 partners with mixed formats (CSV, X12 834, fixed-width, JSON). Tune Splink thresholds against real cross-partner data. Establish DQ baselines per partner. Validate reconciliation flows.

**Exit criteria:**

- Onboarding a new partner is achievable in under one engineering-day from YAML PR to production-live
- No partner-specific code paths exist in production code (BR-802 enforcement)
- Cross-partner identity resolution (same person, two partners) is detected and handled correctly per BR-205

### Phase 4: Hardening and Attestation Prep

**Goal:** SOC 2 Type II or HITRUST CSF readiness, depending on Lore's compliance roadmap.

**Scope:** Penetration testing, third-party security review, runbook formalization, disaster recovery validation, audit log access review, BAA chain documentation finalized.

**Exit criteria:** External attestation auditor's report with no high-severity findings.

## Prototype Scope

The interview deliverable runs a scoped subset of Phase 1 on the local substrate (AD-007). This section identifies what's in, what's stubbed, and how the production architecture remains visible behind the local implementation.

### In Scope for Prototype

- Format adapter for CSV (one format family)
- Mapping engine reading a YAML registry containing one or two synthetic partners
- DQ engine implementing field-tier validation, record-level quarantine, feed-level threshold gating
- Within-feed deduplication (BR-601)
- Snapshot-diff CDC against a prior snapshot (BR-602)
- Identity Resolution: Tier 1 deterministic plus Splink-on-DuckDB for Tier 2 / 3 / 4
- Canonical Eligibility schema in local Postgres with state machine and SCD2
- Verification API as a thin Flask or FastAPI service returning `{VERIFIED, NOT_VERIFIED}` only
- Deletion ledger with suppression check
- Audit event emission to a local JSON Lines file
- Synthetic data harness producing partner feeds with seeded match scenarios (true matches, near-matches, deliberate duplicates, identity conflicts)

### Stubbed for Prototype

- **Cloud KMS replaced by local app-level encryption** with a static dev key. The TokenizationService interface is fully implemented; only the KMS backing is replaced. The interface is what the panel sees.
- **GCS Bucket Lock replaced by an append-only file** with hash chain in the same shape as production would emit. The chain is verifiable.
- **Datastream replaced by a periodic sync script** that reads from Postgres and writes to a DuckDB analytical file. The Pattern C separation is preserved; only the replication mechanism differs.
- **VPC-SC perimeters not applicable in local context.** Documented as the production intent.
- **Brute force protection demonstrated as logic, not against real attack traffic.** Test cases exercise the three-tier progression.
- **Manual review queue exists as a Postgres table; no reviewer UI in the prototype.** The queue mechanism per BR-105 is demonstrated; the human-in-the-loop interface is roadmap.
- **Cloud Composer replaced by a Python script orchestrating the pipeline run.** The DAG shape is preserved as code structure.

### Demonstrative Goals

The prototype is built to make the following visible to the panel within a 60-minute walkthrough:

1. **Identity resolution with explainable scores.** Splink runs against synthetic data, produces match weights, and routes outcomes through the four tiers. The reviewer sees a Tier 3 case with the score breakdown.
2. **Cleansing in action.** A deliberately dirty feed (mixed-case names, varying date formats, near-duplicates, missing required fields) is processed; quarantined records are visible; profile baselines are captured.
3. **SCD2 history derivation.** A second-day snapshot triggers diff-CDC; SCD2 history is visible in queryable form.
4. **Deletion ledger suppression.** A deletion is executed; a subsequent feed re-introduces the deleted identity; the system suppresses it; the override path is demonstrated.
5. **Privacy-preserving collapse.** The verification API returns identical-shape responses across internal-state combinations; no log line in any service contains plaintext PII; the redaction scanner runs and reports clean.

## Open Architectural Questions

Carried forward from the BRD's open questions, with architectural framing.

1. **Confirmed warehouse choice.** ARD assumes BigQuery. Confirm with Jonathon Gaff or surface alternatives.
2. **Confirmed orchestrator deployment shape.** ARD assumes Cloud Composer. If Lore self-manages Airflow on GKE, the orchestration section adapts.
3. **Existing identity model in the Lore application.** ARD assumes the Lore application owns user accounts and reads from the Verification API. If the application has a richer identity primitive, the contract may need additional fields.
4. **Existing partner contracts on data residency.** Sequelae PH boundary is enforced architecturally; partner-specific contracts may impose stricter requirements that surface as additional VPC-SC conditions or additional BAA-chain documentation.
5. **HITRUST or SOC 2 attestation status.** Phase 4 scope shifts based on the active workstream.
6. **Splink threshold defaults.** Will be tuned against synthetic data with seeded ground truth in the prototype; production defaults require partner-data tuning.

## Mapping to Business Rules

Every BR in BRD.md maps to one or more architectural components. Reverse mapping below confirms coverage.

| BR | Architectural Component(s) |
| --- | --- |
| XR-001, XR-002 | Configuration Management library; CI lint |
| XR-003 | Verification API public response collapse; logging redaction |
| XR-004 | Verification rate-limit cache scope by resolved identity |
| XR-005 | Audit emission schema; redaction scanner; CI fixture test |
| XR-006 | TokenizationService tombstone path; Deletion Executor; code-path inventory |
| BR-101 through BR-105 | Identity Resolution context; Splink Runner; match_decision schema; review_queue |
| BR-201 through BR-206 | Canonical Eligibility state machine engine; canonical_member, member_history schemas |
| BR-301 through BR-306 | Ingestion & Profiling DQ engine; quarantine bucket; per-partner YAML field-tier assignments |
| BR-401 through BR-405 | Verification context; Verification API; rate-limit cache; friction challenge |
| BR-501 through BR-505 | Audit context; Pub/Sub `audit-events`; Dataflow consumer; tiered storage |
| BR-506 | IAM residency conditions; inner VPC-SC perimeter; PII Vault US-only ownership |
| BR-601 through BR-607 | Ingestion & Profiling format adapters and DQ engine; Identity Resolution match orchestrator; replay job |
| BR-701 through BR-704 | Deletion context; Deletion Executor; deletion_ledger; vault tombstone path |
| BR-801, BR-802 | Schema mapping mechanism (AD-016); partner registry activation gate |

## Closing Note

This ARD is a contract between the BRD and the implementation. Architectural decisions enumerated here may be revisited only by amendment with the same rigor that produced them: a cascading decision exchange, a stated rationale, and updated mappings. Any drift between the implementation and this document is a defect in the implementation, not a tacit amendment to the architecture.

The next deliverable is the prototype itself, scoped per the Prototype Scope section. The case study walkthrough document follows from the prototype.
