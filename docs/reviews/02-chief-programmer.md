# Architecture Review — Round 2: Chief Programmer / Expert Software Engineer

| Field | Value |
|---|---|
| **Round** | 2 of N |
| **Reviewer lens** | Chief Programmer — what does this look like as code; is it implementable, observable, debuggable, testable, maintainable; what races, retries, transactions, error paths, and operational realities are silent in the docs |
| **Documents** | `docs/BUSINESS_REQUIREMENTS.md` (BRD), `docs/ARCHITECTURE_REQUIREMENTS.md` (ARD) |
| **Date** | 2026-04-29 |
| **Prior round** | `docs/reviews/01-principal-architect.md` (25 findings; this round overlaps in places — overlap is intentional, agreement from different angles) |

This round looks at the docs the way a senior engineer about to ship the platform looks at them: I want to know how the code is laid out, what shared patterns I have to follow, what the error taxonomy is, what idempotency contracts exist, where the race conditions live, what the observability story is, and what I have to carry in my head that the docs leave silent.

Severity per Constitution Rule 29 (BLOCKER / FINDING / ADVISORY).

---

## TL;DR

**Will the platform be well-engineered, observable, and effective if we proceed as-is? No.**

The architectural shape is right (the principal architect agreed). What's missing is the *programmer's contract*: the cross-cutting patterns every service has to follow consistently or the platform fragments at the seams.

The single biggest gap is **discipline by absence**. Idempotency, error taxonomy, correlation IDs, transactional outbox, logging schema, message-schema evolution — without these stated, every developer invents their own version. After Phase 2 you have seven different error patterns, three correlation-ID conventions, and a Pub/Sub flow with non-idempotent consumers double-writing audit events. Past that point, retrofitting the discipline costs more than authoring it now.

This review surfaces 60 findings. **13 BLOCKERS** are correctness or operability issues that will cause defects or outages if backlog work starts without them resolved. **37 FINDINGS** should be addressed as Phase 0 ADRs with named owners. **10 ADVISORIES** can be addressed opportunistically.

---

## Strengths from a programmer's view

What's actually *implementable* about this design:

1. **Bounded contexts are deployable units.** Each maps to a Cloud Run service or job. Code organization can mirror context boundaries.
2. **TokenizationService interface is a clean abstraction.** Testable in isolation; mockable for service tests; backend swappable.
3. **Concrete SQL DDL.** Not pseudocode. The schema is reviewable now, not deferred.
4. **Pub/Sub as the shared event bus.** Standard GCP-native pattern; library support is mature.
5. **Per-partner YAML registry.** Keeps partner-specific behavior out of code; testable in isolation.
6. **Phase exit criteria are testable.** Not subjective.

These work. Don't relitigate them in this round.

---

## Findings

Organized into 10 thematic categories. Each finding lists severity, where, why-it-matters (programmer's view), what's-needed, effort.

---

## 1. Concurrency, Consistency, and Idempotency

The single largest gap-cluster. Async pipelines without an idempotency contract produce silent double-processing; without an outbox pattern, cross-context events drift from canonical state; without idempotent consumers, Pub/Sub at-least-once delivery causes duplicates that show up later as audit-chain breaks or doubled match decisions.

### F-101: Idempotency contract per pipeline stage — BLOCKER

**Where:** ARD §"Ingestion & Profiling" describes 5 stages (landing → format adapter → mapping engine → DQ engine → publish). BR-606: "Idempotent reprocessing for any pipeline stage." Nowhere is the idempotency key per stage specified.

**Why it matters:** Replay (BR-606) re-runs everything. Without keys, replay produces duplicate `match_decision` rows, duplicate `lifecycle-events`, duplicate `audit-events`. Each downstream consumer then has to dedupe — or doesn't, and the canonical model drifts.

**What's needed:** ARD section "Idempotency Keys per Stage." For each stage (landing, format-adapter parse, mapping, DQ, identity-resolution decision, canonical state transition, audit emit), name the key (typically: `(partner_id, source_file_hash, row_index)` for ingestion stages; `(decision_id)` for identity resolution; `(event_id)` for audit). The downstream contract is "given the same key, produce the same effect at most once."

**Effort:** S (one ARD section).

---

### F-102: Transactional outbox for cross-context events — BLOCKER

**Where:** ARD §"Canonical Eligibility": state transitions emit `lifecycle-events` to Pub/Sub. The transition itself is a SQL write. Two writes, two systems.

**Why it matters:** If state-transition SQL succeeds and Pub/Sub publish fails, downstream consumers never see the change → canonical model and consumer model drift permanently. If publish succeeds and SQL rolls back, downstream sees an event for a state that was never persisted.

The standard answer is the **transactional outbox pattern**: write the event to an `outbox` table in the same SQL transaction as the state change; a separate publisher reads from outbox and publishes to Pub/Sub with idempotency, marking outbox rows as published. Same approach for `audit-events`, `match-decisions`, `staging-records`.

**What's needed:** ARD ADR specifying the outbox pattern. Schema: `outbox(event_id, topic, payload, created_at, published_at, retry_count)`. Publisher service (a small Cloud Run scheduled job, or a Cloud Run instance behind Cloud Scheduler). Idempotency key on the topic side is `event_id`.

**Effort:** S (one ADR + outbox table + simple publisher).

---

### F-103: Pub/Sub at-least-once → idempotent consumers required — BLOCKER

**Where:** ARD §"Streaming and Eventing" lists topics. Pub/Sub guarantees at-least-once. Consumers will see duplicates.

**Why it matters:** Audit Consumer fanning out to BigQuery + GCS hash chain — a duplicate event written to the chain breaks chain validation. Match Orchestrator consuming `staging-records` — a duplicate produces a duplicate match decision, a duplicate canonical update, a duplicate lifecycle event, a duplicate audit event. The amplification is real.

**What's needed:** ARD section "Consumer Idempotency Pattern." Every consumer maintains a **processed-event-ids** record (in its own state store) keyed by the upstream event_id. Pre-process check: "have I seen this event_id?" If yes, ack and skip. The Audit Consumer's hash chain specifically must use append-with-idempotency-key (Cloud Storage object naming with event_id, or a deduplication step before chain append).

**Effort:** S to specify; M to implement consistently across all consumers.

---

### F-104: Race conditions on canonical model from concurrent processing — BLOCKER

**Where:** Match Orchestrator processes `staging-records` from Pub/Sub. Cloud Run instances autoscale to handle the topic. Two messages for the same partner_id, processed concurrently on two instances, both decide to update the same canonical_member.

**Why it matters:** The state machine is enforced in application code, not by triggers. Without locking discipline, concurrent transitions produce lost updates: instance A reads state ELIGIBLE_GRACE, computes next state ELIGIBLE_ACTIVE, writes; instance B reads state ELIGIBLE_GRACE (before A's write commits), also writes ELIGIBLE_ACTIVE, but the underlying transition table A used assumed B's read-state — both writes "succeed" but the SCD2 history is broken.

**What's needed:** ARD section "Concurrency Control on Canonical State." Per-member-id advisory lock (PostgreSQL `pg_advisory_xact_lock(hashtext(member_id))`) for every state mutation, OR optimistic concurrency with `state_effective_from` as a version column and retry on conflict. Pick one and document the discipline.

Note: pg_advisory_lock interacts with pgbouncer transaction mode — see F-201.

**Effort:** S to specify; the implementation is straightforward but discipline is everything.

---

### F-105: SCD2 closing semantics — FINDING

**Where:** ARD: "On every update, prior state is closed (effective_to set) and new state opened (effective_from set)." No specification of timestamp source, atomicity, or ordering when multiple changes occur in the same second.

**Why it matters:** If `effective_to` is set from `clock_timestamp()` (transaction-scoped wall clock) and `effective_from` of the new row is set the same way, two changes within the same TX have monotonic timestamps. But across transactions on different instances with clock skew, you can get `effective_to(prior) > effective_from(new)` — overlapping rows. SCD2 history then has "valid in two states at once" which breaks every downstream consumer.

**What's needed:** Convention: timestamps come from `now()` at the database, not from app code. Atomic update: same TX closes prior row and opens new row with `effective_from = previous.effective_to` (not a new `now()` call). Document the pattern in the state-machine implementation section.

**Effort:** S.

---

### F-106: Audit event ordering keys — FINDING

**Where:** ARD §"Audit emission pattern" describes Pub/Sub topic. Pub/Sub doesn't guarantee FIFO without ordering keys.

**Why it matters:** Audit chain validity depends on event order. Without an ordering key, two events for the same target token can land out of order in the chain — the chain validator either sees duplicates or sees an out-of-order chain it can't validate.

**What's needed:** ARD: ordering key per audit event. Either `target_token` (orders-by-subject) or `partition_key=hash(target_token)` (allows parallelism but preserves order per subject). If the chain itself is across-subjects, the ordering key is the chain partition.

**Effort:** S.

---

### F-107: Audit emission failure handling — BLOCKER

**Where:** Every service emits audit events. What happens if the publish fails? Specifically for PII access events: does the operation that triggered the audit return success?

**Why it matters:** Two failure modes:

1. **Audit-on-failure:** PII access succeeds, audit publish fails. Per HIPAA, PII access without audit is a defect. Should the operation succeed?
2. **Audit-as-blocker:** PII access depends on audit publish succeeding. If audit is unavailable, all PII access pauses. Operationally fragile (one Pub/Sub blip pauses the system).

The standard answer is **audit publish must be in the same transaction as the operation** (outbox per F-102) — outbox guarantees the audit event is recorded persistently in the same write that authorized the operation, and the publisher catches up asynchronously. The operation succeeds and the audit is durable.

**What's needed:** ARD section "Audit Durability." Audit events are written via outbox. PII access operations don't depend on Pub/Sub availability; they depend on the local DB. Async publisher delivers to Pub/Sub.

**Effort:** Covered by F-102 if the outbox is generalized correctly.

---

### F-108: Verification fail-closed semantics when TokenizationService unavailable — BLOCKER

**Where:** Verification API tokenizes the inbound claim, then queries Canonical Eligibility. If TokenizationService is unavailable mid-request, what does Verification return?

**Why it matters:** Three options:

1. **Fail closed → return NOT_VERIFIED.** Privacy-preserving (no information leakage). User-facing impact: account creation breaks during TokenizationService outage.
2. **Fail open → return VERIFIED on a cached or partial match.** Operational availability preserved. Privacy and integrity violated — wrong verifications happen.
3. **Fail with error → 503 to caller.** Information-leak via timing (XR-003 violation) and via error code presence. Forbidden.

The right answer is fail-closed → NOT_VERIFIED, but it must be deliberate, documented, and tested. The internal log and audit must distinguish "NOT_VERIFIED because no match" from "NOT_VERIFIED because TokenizationService down" — both look identical externally per BR-401.

**What's needed:** ARD ADR: fail-closed contract for Verification, internal-state distinction in logs/audit, alerting on the specific failure mode, runbook for the outage.

**Effort:** S.

---

### F-109: Concurrent partner-feed processing race conditions — FINDING

**Where:** DQ engine and Match Orchestrator can process multiple partner feeds concurrently. Two feeds from the same partner (e.g. corrected rerun) processed concurrently.

**Why it matters:** Two concurrent runs against the same partner_id may produce conflicting state changes on the same canonical_member. The advisory-lock pattern from F-104 handles per-record contention but not per-feed contention.

**What's needed:** Convention: per-partner ingestion is serialized by source_file_id ordering (file-effective-date order per BR-604). Same-partner concurrent processing is forbidden by the orchestrator (Composer DAG dependency) until the prior file completes.

**Effort:** S.

---

## 2. Error Handling and Resilience

Without an explicit error taxonomy, every service handles errors differently. Behavior varies, retries vary, alerting varies.

### F-110: Error category taxonomy — BLOCKER

**Where:** Nowhere. ARD has DQ failure categories (record-level, feed-level), match decision tiers, verification outcomes — these are *business* errors. *System* errors (network timeout, connection pool exhausted, KMS quota, Pub/Sub publish failed, BigQuery streaming insert failed) have no taxonomy.

**Why it matters:** Programmer needs to know: is this error retryable? Should I alert? Should I queue for later? Without taxonomy, every developer invents their own answers, often inconsistently.

**What's needed:** ARD section "Error Taxonomy." Categories: `Transient` (retry with backoff; alert if persistent), `BackpressureSignal` (slow down upstream), `PermanentDataError` (quarantine; don't retry), `PermanentSystemError` (page; don't retry), `BusinessOutcome` (not an error). Map common cases (timeout = Transient; KMS quota = BackpressureSignal; bad row = PermanentDataError; missing config = PermanentSystemError). Implementation: a shared exception hierarchy + a retry decorator that uses the category.

**Effort:** S (one ARD section + the shared library lives in `shared/errors.py`).

---

### F-111: Retry / backoff policy per integration point — FINDING

**Where:** No retry policies stated. Cloud Run internal calls, KMS calls, Pub/Sub publishes, BigQuery streaming inserts, AlloyDB queries — each has different retry tradeoffs.

**Why it matters:** Aggressive retries can amplify outages (thundering herd). Insufficient retries cause unnecessary failures. Without a policy, every integration retries differently.

**What's needed:** ARD §"Retry Policies" table per integration: max attempts, base delay, multiplier, jitter, total time budget, terminal action (page, quarantine, drop). Default to GCP client-library defaults where reasonable; customize where the operation has tight latency budgets (Verification API: no retries against AlloyDB; let it fail to NOT_VERIFIED).

**Effort:** S.

---

### F-112: Dead letter / poison message handling — FINDING

**Where:** Pub/Sub topics are listed. Dead letter topics are not.

**Why it matters:** A poison message (parse failure, schema violation) blocks the consumer if it's retried indefinitely. Pub/Sub dead-letter topics absorb these after N delivery attempts. Without configured DLTs, poison messages either retry forever or get dropped silently after the topic's max retention.

**What's needed:** ARD: every primary topic has a paired dead-letter topic. Max delivery attempts per topic. Operational runbook entry: who looks at the DLT, when, what's the resolution path.

**Effort:** S (config; runbook is part of F-115).

---

### F-113: Format adapter partial-parsing recovery — FINDING

**Where:** ARD: "Format adapter: per format family." DQ engine handles record-level errors. Format-adapter-level errors (malformed CSV at byte 5000 of a 10MB file) — what happens?

**Why it matters:** A single malformed row in a partner CSV shouldn't quarantine the entire feed (BR-302 says record-level quarantine). But the format adapter sits *before* the DQ engine — if the adapter throws on a parse error, the file is dead. The discipline is: format adapter must be fault-tolerant; it emits a synthetic "parse-error" row that the DQ engine then quarantines per BR-302.

**What's needed:** ARD §"Format Adapter Recovery": adapter never crashes on row-level errors; emits a sentinel Intermediate Row with parse-error metadata; DQ engine treats parse-error rows the same as required-tier failures.

**Effort:** S.

---

### F-114: Migration partial-failure recovery — FINDING

**Where:** alembic migrations execute as a sequence of SQL statements. A migration with 5 statements that fails on statement 3 leaves the DB in an inconsistent state. Alembic doesn't auto-rollback on partial failure.

**Why it matters:** Phase 1+ deploys will fail at some point. Without a rollback procedure, the operator manually unwinds — risky in production.

**What's needed:** Convention: every migration is single-statement-or-transactional. Multi-statement migrations are explicitly wrapped in `BEGIN/COMMIT`. Where DDL prevents transactions (Postgres handles most DDL inside TX, but some operations like CREATE INDEX CONCURRENTLY don't), document the recovery pattern. ADR: migration safety policy.

**Effort:** S.

---

## 3. Observability and Debuggability

The ARD names tools (Cloud Logging, Cloud Monitoring, Cloud Trace) but doesn't specify how they're used. Tools without conventions don't make a system observable.

### F-115: Logging schema convention — BLOCKER

**Where:** ARD says structured logging via Cloud Logging. Phase 00 of the harness configures structlog with PII redaction. No log schema is defined.

**Why it matters:** Every developer logs differently. Field names drift (`partner_id` vs `partnerId` vs `partner`). Required fields missing (no trace_id, no service_name). Querying across services is impossible.

**What's needed:** ARD §"Logging Schema": required fields per log entry (`timestamp`, `service_name`, `trace_id`, `span_id`, `severity`, `event` (the message), plus context like `partner_id` and `correlation_id` where applicable); structured-only (no f-strings); convention enforced by a shared `lore_eligibility.shared.telemetry.get_logger(__name__)` factory that pre-binds required fields.

**Effort:** S (one ARD section + shared factory + lint rule preventing direct stdlib logging).

---

### F-116: Correlation ID propagation across async boundaries — BLOCKER

**Where:** No correlation-ID model is specified. The pipeline is async (Pub/Sub between every stage). Without correlation IDs threading through, "why didn't this record verify" requires manual log archaeology across 6 services.

**Why it matters:** This is the single most important debuggability primitive. A partner record arrives, gets ingested, mapped, DQ'd, matched, applied to canonical state, served by Verification weeks later. Six asynchronous handoffs. Without a stable identifier traveling with the record, debugging is impossible.

**What's needed:** ARD §"Correlation ID Model": a `correlation_id` (UUID) is generated at ingestion (per source-file or per-record per the granularity decision) and propagated through:
- every Pub/Sub message attribute
- every database row that originates from that record (`originating_correlation_id` column or per-table audit FK)
- every log entry produced during processing
- every audit event

OpenTelemetry's W3C Trace Context provides the standard mechanism (`traceparent` header). Use it.

**Effort:** S to specify; M to implement consistently.

---

### F-117: Per-service metrics specification — FINDING

**Where:** ARD §"Observability" mentions Cloud Monitoring with Verification API dashboard. Other services unspecified.

**Why it matters:** Every service needs SLI metrics: request rate, error rate (split by error category per F-110), latency histogram. Plus service-specific: DQ rates, match-tier distributions, vault detok-by-role rates, etc.

**What's needed:** ARD §"Per-Service Metrics" table: for each service, the SLI metrics emitted, the SLO targets, the dashboard. Convention: every service uses prometheus-client-style metric names with shared label conventions (`service`, `environment`).

**Effort:** S to specify; ongoing as services are built.

---

### F-118: Tracing model — FINDING

**Where:** ARD: "Cloud Trace at the Verification API and TokenizationService, with sampling configured to keep trace storage bounded."

**Why it matters:** Two-service tracing is below the threshold of useful. The pipeline that matters is the multi-service path through ingestion to verification. Without traces across the pipeline, the latency-budget question (F-300 below) is unanswerable.

**What's needed:** ARD §"Tracing Model": OpenTelemetry instrumentation in every service, span boundaries at every Pub/Sub publish/consume, every DB call wrapped in a span, every external call (KMS, BigQuery) wrapped. Sampling: 1% for Verification (high volume), 100% for the ingestion pipeline (low volume, high debugging value).

**Effort:** S to specify.

---

### F-119: Health probe specification — FINDING

**Where:** Dockerfile has a HEALTHCHECK hitting `/health`. ARD doesn't distinguish liveness, readiness, dependency-health.

**Why it matters:** `/health` as written returns 200 if the process is alive. But Verification can't actually serve requests if AlloyDB is unreachable — yet it'd still pass `/health`. Cloud Run uses readiness for traffic routing decisions; getting this wrong means traffic to broken instances.

**What's needed:** ARD §"Health Endpoints" convention: `/livez` (process up; always 200 unless terminating), `/readyz` (dependencies reachable: DB ping, Pub/Sub publish-permission check, TokenizationService reachable; 503 if not). Cloud Run config uses `/readyz` for traffic.

**Effort:** S.

---

### F-120: Alert classification model — FINDING

**Where:** "PagerDuty integration on Priority 0 conditions (verification latency breach, vault-side errors, audit hash chain break, redaction scanner match)."

**Why it matters:** P0 is named but P1/P2/P3 aren't. Alerting noise is real — overpaging means missed important alerts. Underpaging means missed real outages.

**What's needed:** ARD §"Alert Severity Taxonomy": P0 (page on-call within minutes — service-down, security boundary breach), P1 (page on-call within an hour — degraded but serving), P2 (notification, business-hours response — DQ threshold trends), P3 (logged, weekly review — informational). Each alert is classified explicitly; the alert config emits the classification.

**Effort:** S.

---

## 4. Database, State, and Persistence

### F-121: pgbouncer transaction-mode constraints — BLOCKER

**Where:** ARD: pgbouncer in transaction pool mode. Application code: undocumented.

**Why it matters:** Transaction mode is the most efficient pgbouncer mode but disables several Postgres features:
- **Prepared statements** are not safe; the prepared-statement cache is per-server-connection, but transactions can land on different server connections. Solution: disable prepared-statement caching (in SQLAlchemy/asyncpg, set `statement_cache_size=0`).
- **Session-scoped state** (`SET LOCAL` is fine; `SET` without LOCAL is not) breaks across transaction boundaries.
- **Advisory locks** (`pg_advisory_lock` without `_xact`) hold across transactions and don't release; only `pg_advisory_xact_lock` is safe.
- **LISTEN/NOTIFY** doesn't work.

Without explicit guidance, developers will hit these one by one in production.

**What's needed:** ARD §"pgbouncer Operating Constraints" listing each forbidden pattern and the workaround. Plus: a CI lint rule for the obvious cases (`pg_advisory_lock` without `_xact_` is detectable statically).

**Effort:** S (one ARD section + a lint check).

---

### F-122: Connection pool sizing per service — FINDING

**Where:** Not specified.

**Why it matters:** Cloud Run scales to N instances. Each instance has a connection pool of size M. Total connections to AlloyDB = N × M. pgbouncer fronts AlloyDB and pools further. At scale (10x partners, 10x verification QPS), pool exhaustion becomes a real failure mode. Sizing must be explicit.

**What's needed:** ARD §"Connection Pool Sizing": per service, expected concurrency, pool size, pgbouncer reserved-pool size, AlloyDB max_connections. With monitoring + alerts on pool saturation.

**Effort:** S.

---

### F-123: Schema migration deploy order — FINDING

**Where:** Same as F-010 in principal review but at code-deploy level.

**Why it matters:** Cloud Run does rolling deploys. During the window between "old instances draining" and "new instances ready," migrations may have been applied but old code is still running. If migration is not backward-compatible (e.g. dropped column), old code breaks.

**What's needed:** Convention: every migration is backward-compatible-on-deploy. Two-deploy pattern for breaking changes:
1. Deploy migration that adds new column/table while old still exists.
2. Deploy app code that uses new column.
3. Deploy migration that removes old column.

Plus: which deploy runs the migration? Cloud Run service startup is the wrong place (race condition between instances). Composer DAG or one-shot Cloud Run job is the right place; service startup waits for migration completion via a check.

**Effort:** M (ADR + tooling).

---

### F-124: Read consistency model — FINDING

**Where:** Pattern C uses Datastream BigQuery replication. AlloyDB read replicas are not mentioned.

**Why it matters:** Verification reads AlloyDB primary. If load grows, replicas needed. Replicas have lag. After ingestion completes, "when does Verification see the new state" is a real consistency question.

**What's needed:** ARD §"Read Consistency": v1 reads from AlloyDB primary (sub-200ms achievable); when scale dictates, AlloyDB read replicas with documented bounded staleness; Verification reads tolerate replica staleness for reads but write paths (rate-limit-cache writes) hit primary.

**Effort:** S.

---

### F-125: Caching strategy — FINDING

**Where:** No caching strategy stated. The Verification path is hot.

**Why it matters:** Verification at p95 ≤ 200ms with cold AlloyDB lookups requires either solid index design (likely sufficient) or caching. Caching tokenized values is forbidden by Vault constraint (TokenizationService is the only plaintext surface). But other things can be cached: configuration, Splink match-weights at inference, frequently-accessed canonical_member rows.

**What's needed:** ARD §"Caching Strategy": cacheable surfaces (config, match-weights, anonymous prefetch warmup); non-cacheable (anything tokenized or post-detokenization); cache invalidation patterns; cache-stampede prevention.

**Effort:** S.

---

### F-126: Rate-limit cache durability — FINDING

**Where:** ARD §"Verification": "Cloud Memorystore (Redis) holding identity-scoped failure counters." Memorystore single-AZ default has a restart penalty; counters reset.

**Why it matters:** Post-restart, an attacker mid-attack gets a clean slate. The brute-force lockout (BR-402) silently degrades.

**What's needed:** ARD: HA Memorystore tier (multi-AZ) for the rate-limit cache. Or accept the tradeoff explicitly with an ADR (cost vs. residual brute-force window). Or persist counters into the operational store as a backstop.

**Effort:** S.

---

### F-127: Audit event sink routing logic — FINDING

**Where:** ARD §"Audit Consumer": "fans out to two sinks based on event class." The class-to-sink mapping isn't specified anywhere I can find.

**Why it matters:** PII access events are 7-year retention (BR-503) but `audit_operational.audit_event` has `partition_expiration_days = 730` (= 2 years, the OPS retention). So PII access can't go into the operational sink. The operational tier is for operational events; the high-criticality tier (GCS Bucket Lock, 7-year) is for PII access, identity merge, deletion. The mapping is implicit but not enumerated.

**What's needed:** ARD §"Audit Class Routing" table: every event class from BR-501 → sink (`audit_operational` BigQuery vs `audit_high_criticality` GCS).

**Effort:** S.

---

## 5. Type Safety and Inter-Service Contracts

### F-128: Message schema format choice — BLOCKER

**Where:** ARD: "schema is enforced via Pub/Sub schema validation." Schema format unspecified.

**Why it matters:** Pub/Sub supports Protobuf and Avro for schema validation (not JSON Schema natively). Each has different evolution semantics. Protobuf is standard for GCP-internal services with strong evolution support (additive changes are wire-compatible). Avro has different rules. Without a choice, services can't share message types.

**What's needed:** ADR: Protobuf for Pub/Sub message schemas. Schema lives in a `proto/` directory, code-generated for each service. Versioning convention (file path includes major version).

**Effort:** S (ADR + scaffolding).

---

### F-129: API error response contract — FINDING

**Where:** Verification public API has 2-state response. Internal APIs (TokenizationService, Manual Review API, Deletion Request API) — error response shape not specified.

**Why it matters:** Internal services need a consistent error contract so callers know how to interpret responses. HTTP status codes, an error body shape, retryability hints, rate-limit headers — all need standardization.

**What's needed:** ARD §"Internal API Error Contract": JSON body with `code`, `message`, `request_id`, `retryable: bool`, `retry_after_seconds: int|null`. Standard HTTP status code mapping (4xx for client error, 5xx for server, 503 for backpressure with Retry-After).

**Effort:** S.

---

### F-130: Idempotency keys at HTTP API — FINDING

**Where:** Public Verification API has `request_id` in the request body. Idempotency semantics not specified.

**Why it matters:** Client retries are inevitable. If the same `request_id` arrives twice, the API should return the same outcome and not double-count against rate limits. Standard pattern: idempotency key with TTL'd cache of (request_id, outcome).

**What's needed:** ARD: idempotency contract on Verification API and any internal API with side effects. TTL, cache backing (Memorystore is reasonable), behavior on key-collision-different-payload.

**Effort:** S.

---

### F-131: Cross-service type sharing — FINDING

**Where:** Not specified. Each service is a separate deploy.

**Why it matters:** Concepts shared across services (member_id, token shapes, audit event schemas, error categories) need consistent representation. Two options:

1. **Monorepo with shared library**: `lore_eligibility_shared` Python package imported by every service. Pro: type-safe, single source. Con: monorepo coordination.
2. **Polyrepo with code-generated types**: Protobuf as canonical (per F-128), each service's repo generates types. Pro: independent deploys. Con: codegen tooling.

The harness today is monorepo-shaped. Most likely answer: stay monorepo with a shared library.

**What's needed:** ADR. Pick monorepo + shared library, define what's shared (errors, types for cross-service messages, common middleware), define what's NOT shared (service-specific business logic).

**Effort:** S.

---

### F-132: Configuration parameter typing — FINDING

**Where:** BRD config table lists parameters with values. Types implicit. ARD says "type-safety / range-validation runs at config-load time" (in F-013 of principal review) but no concrete spec.

**Why it matters:** `GRACE_PERIOD_DAYS=30` — int? string? Pydantic-validated? What are the bounds (1..3650)? What happens if config has `GRACE_PERIOD_DAYS=foo`?

**What's needed:** Convention: a Pydantic BaseSettings model for each service's config slice. Type and range validation at load time. Failed validation at config-reload preserves the previous valid config. Add Pydantic to BRD's config-parameter table as the canonical type.

**Effort:** S.

---

## 6. Testing Strategy

### F-133: Local-substrate test environment — FINDING

**Where:** Phase 00 harness has docker-compose with Postgres + pgbouncer. The full pipeline has Pub/Sub, BigQuery, KMS, Cloud Run, Cloud Storage. Local development needs to exercise cross-service flows.

**Why it matters:** Without a local-substrate, every test is either unit-with-mocks (limited fidelity) or runs against actual GCP (slow, expensive, isolation issues). Pipeline-level bugs surface only in CI integration runs.

**What's needed:** ARD §"Local Development Substrate": Pub/Sub emulator (`gcloud beta emulators pubsub`), Cloud Storage emulator (fake-gcs-server), BigQuery local (limited; or use DuckDB as the prototype does per AD-007), KMS mocked at the TokenizationService level. Compose file orchestrates them. Documented in README.

**Effort:** M (substrate setup + documentation).

---

### F-134: Test data lifecycle — FINDING

**Where:** Prototype scope mentions "Synthetic data harness producing partner feeds with seeded match scenarios." Phase 1+ doesn't specify how synthetic data scales.

**Why it matters:** Phase 1 needs realistic synthetic feeds (mixed types, edge cases, deliberate dirty data, known-match scenarios for Splink validation). Phase 3 needs scale (millions of synthetic members across multiple partners). Phase 1's test data and Phase 3's are different beasts; without a tooling strategy, each phase rolls its own.

**What's needed:** ADR: synthetic-data tooling. For Phase 1, Faker plus a relationship-aware generator (same person on two partners with controlled drift). For Phase 3, scale generator producing N million members. Tooling lives in `scripts/synthesize_partner_feed.py` (or similar) and is tested itself.

**Effort:** M.

---

### F-135: Splink reproducibility under tests — FINDING

**Where:** Phase 2 exit criterion: "Splink match weights are reproducible across runs given fixed configuration."

**Why it matters:** Splink uses an iterative EM algorithm. Convergence depends on starting point. Floating-point determinism varies across CPUs and BLAS libraries. "Reproducible" is harder than it sounds.

**What's needed:** ADR: reproducibility approach. Pin `numpy.random.default_rng` seed in code; declare a deterministic backend (CPU, single-threaded for evaluation runs); document tolerance bounds for cross-platform comparisons; gate deploys on weights-within-tolerance vs. baseline.

**Effort:** S (ADR; the implementation is in identity-resolution work).

---

### F-136: Performance test harness — FINDING

**Where:** Phase 2 exit references "load test gate in pre-release pipeline." Specifics not stated.

**Why it matters:** The 200ms p95 contract needs continuous validation, not just a one-time check. Without a harness in CI/CD, perf regresses silently.

**What's needed:** ADR: load test harness (k6 or Locust), running against a staging environment with realistic synthetic data, gating phase exits and major releases. Targets per service: Verification API at sustained QPS, identity-resolution batch throughput, etc.

**Effort:** M.

---

### F-137: Chaos / failure injection — FINDING

**Where:** Implicit. Phase 4 hardening might include this.

**Why it matters:** The architecture has many failure modes (Memorystore restart, Datastream lag, KMS quota, Pub/Sub backlog, AlloyDB failover). Verifying correct behavior under each requires deliberate injection. Without it, you discover behavior on the day of the real outage.

**What's needed:** ADR: chaos / game-day plan. Targeted failures per quarter, runbook validation through the failure, postmortem-on-success.

**Effort:** M (initial scoping; ongoing).

---

### F-138: Test isolation for integration tests — FINDING

**Where:** Harness uses pytest-postgresql. Integration tests with Pub/Sub, BigQuery — substrate not specified.

**Why it matters:** Integration tests must be hermetic. Each test creates its own database/topic/dataset; cleanup at teardown; parallel runs don't conflict. pytest-postgresql handles Postgres; Pub/Sub emulator with per-test topic naming handles topics.

**What's needed:** ARD §"Integration Test Isolation" (or harness convention doc): per-test temp resources, naming convention, parallel-safe.

**Effort:** S.

---

## 7. Cloud Run Operational Patterns

### F-139: Cold start mitigation for Verification API — BLOCKER

**Where:** ARD: Cloud Run for stateless services. Verification API at p95 ≤ 200ms (BR-404).

**Why it matters:** Cloud Run cold starts for Python apps with FastAPI + cryptography + asyncpg + redis-client are easily 1-2 seconds — orders of magnitude over the contract. Verification cannot afford cold starts.

**What's needed:** ARD: minimum-instances configuration for Verification API (at minimum 2 for HA, scaled by load). Pre-warming via scheduled health checks if needed. Cost implication: minimum-instances doubles or quadruples at-rest cost vs. scale-to-zero. Document the tradeoff (latency vs cost).

**Effort:** S.

---

### F-140: Per-instance concurrency settings — FINDING

**Where:** Cloud Run default is 80 concurrent requests per instance. Not all services should default this.

**Why it matters:** Verification API at 80-concurrent-per-instance with sub-200ms p95 has no headroom for latency variance. Match Orchestrator processing Pub/Sub messages — concurrency affects DB connection pressure.

**What's needed:** ARD §"Concurrency Configuration" per service: target concurrency setting, rationale, expected impact on tail latency.

**Effort:** S.

---

### F-141: Service identity / Workload Identity binding — FINDING

**Where:** ARD: "service-account-bound IAM." Application-level credential pickup pattern unspecified.

**Why it matters:** Each Cloud Run service runs as a specific service account. The application uses that account's identity for KMS, Pub/Sub, BigQuery access. The pattern is `google.auth.default()` returning the metadata-server credentials. Without this convention stated, developers may try other patterns (key files, env vars).

**What's needed:** ARD §"Service Identity Pattern": every service uses the workload identity provided by Cloud Run. Code uses `google.auth.default()`. No service account key files anywhere. Local dev uses `gcloud auth application-default login` (impersonation via `--impersonate-service-account`).

**Effort:** S.

---

### F-142: Privilege escalation paths beyond break-glass — FINDING

**Where:** Break-glass via PAM is well-defined. Other escalation paths (operator override of suppression per BR-703, force-reprocess override, partner re-enable) are mentioned but not architected.

**Why it matters:** Each non-routine path needs the same audit rigor as break-glass: time-boxed grant, mandatory justification, audit emission, post-action review.

**What's needed:** ADR: pattern for "elevated operations." Generalizes break-glass. Every elevated operation runs through the same gate (PAM or equivalent), produces the same audit-event class, requires same review cadence.

**Effort:** S.

---

## 8. Code Organization

### F-143: Monorepo vs polyrepo decision — BLOCKER

**Where:** Not addressed.

**Why it matters:** Decides the entire codebase shape. The harness is monorepo-shaped (`src/lore_eligibility/{bootstrapper, modules, shared}`). Seven Cloud Run services — are they 7 directories under `modules/`, or 7 separate Cloud Run services from one codebase, or 7 separate repos? Each implies different CI/CD, deployment, and dependency management.

**Why a programmer needs to know now:** The first PR after this review will be writing actual service code. The structure of that PR depends on the answer.

**What's needed:** ADR: monorepo with one Python package, multiple Cloud Run targets. Each service has an entrypoint module (`lore_eligibility.services.verification.main`); CI/CD builds container image per service; shared code in `lore_eligibility.shared`. (My recommendation; the user can choose otherwise but the decision must land before backlog.)

**Effort:** S (ADR).

---

### F-144: State machine implementation pattern — FINDING

**Where:** ARD: "State transitions are enforced by application code per BR-202, not by trigger." No implementation pattern.

**Why it matters:** Hand-coded state machine over 9 transitions is manageable; over 20 it's not. Library options exist (transitions, statesman). Choose now.

**What's needed:** ADR: state machine library or pattern. Recommendation: hand-coded with explicit transition table for v1 (9 transitions; clear, testable, debuggable). Migrate to a library if transitions exceed ~15.

**Effort:** S.

---

### F-145: Shared error catalog — FINDING

**Where:** Phase 00 harness has `shared/errors.py` with skeleton exception hierarchy. ARD doesn't elaborate.

**Why it matters:** Every service raises errors. Consistent classification (per F-110) requires a shared catalog. Without it, each service has its own taxonomy and cross-service error mapping breaks.

**What's needed:** Ties to F-110. The error catalog lives in `shared/errors.py`, every service raises only catalog members.

**Effort:** S.

---

## 9. Operations and Day-1 Readiness

### F-146: Local dev workflow / mock GCP services — FINDING

**Where:** Harness has docker-compose. ARD doesn't address local dev workflow.

**Why it matters:** A new engineer joining mid-project needs to be productive on day 1. "Run `make dev`" should bring up enough substrate to write and test code. Today, `make dev` brings up Postgres + pgbouncer + a Cloud Run-style app. Pub/Sub + KMS + BigQuery are not represented.

**What's needed:** ADR + tooling: local-dev substrate with emulators. `make dev` brings up the full stack. Documented onboarding flow.

**Effort:** M.

---

### F-147: CI/CD pipeline shape — FINDING

**Where:** Phase 0 mentions CI/CD pipelines. Specifics not stated.

**Why it matters:** "How do I get my code to prod" is a developer-experience question that the docs leave silent. Per-service builds (only the changed service deploys)? Monorepo build with selective deploys?

**What's needed:** ADR: CI/CD pipeline shape. Build, test, deploy per service. Promotion model: dev → staging → prod with explicit gates. Rollback procedure.

**Effort:** M.

---

### F-148: Long-running operations contract — FINDING

**Where:** BR-606 partial replay can run for hours. ARD describes the operation conceptually; the API contract for it (start, status query, cancellation) isn't specified.

**Why it matters:** Replay is operator-initiated. Operator needs to start it, monitor progress, possibly cancel. Without a contract, operators run scripts and watch logs.

**What's needed:** ARD §"Long-Running Operations": Google's pattern (POST returns operation handle; GET returns status with progress; DELETE cancels). Backed by a simple operations table.

**Effort:** S.

---

### F-149: Configuration hot-reload safety — FINDING

**Where:** ARD: "Hot-reload supported for parameters that don't require service restart."

**Why it matters:** Hot-reload is dangerous: invalid config replaces valid config, services break. Race conditions between reload and request processing.

**What's needed:** Convention: validate-then-swap atomically; on validation failure, log and retain old config. Per F-132, all config goes through Pydantic at load.

**Effort:** S.

---

### F-150: Backpressure handling — FINDING

**Where:** Pub/Sub topics back up. BigQuery streaming has rate limits. KMS has quotas.

**Why it matters:** Backpressure has to flow somewhere. Without a strategy, it manifests as cascading failures.

**What's needed:** ARD §"Backpressure Strategy": per integration, the backpressure response (slow down upstream, buffer, alert). Pub/Sub backlog → ingestion pauses; KMS quota → tokenization rate-limits inbound rather than failing detok requests.

**Effort:** S.

---

## 10. Specific Programmer-Level Concerns

### F-151: Reviewer interface UX with tokens-only — ADVISORY

**Where:** ARD: reviewers see tokenized references and Splink score breakdowns.

**Why it matters:** A reviewer needs a discriminating signal to make a decision. "Token #abc123 with weight 0.85 against #abc456" — without context, that's an undecidable case. Some signal is needed beyond pure tokens (perhaps: similarity feature contributions per Splink, plus opaque "human-recognizable hint" — first character of name, year of birth — that doesn't fully reveal PII but supports decision-making).

**What's needed:** ADR: reviewer-interface-information-architecture. What does the reviewer see, and how does that support BR-105 outcomes without violating BR-506?

**Effort:** M (a real UX design problem).

---

### F-152: Frontend choice for reviewer interface — ADVISORY

**Where:** Manual Review API exists; frontend not specified.

**Why it matters:** v1 has a reviewer interface; what tech stack? Same SSO as IAM groups.

**What's needed:** ADR: frontend choice. Recommendation: simple FastAPI + server-rendered Jinja for v1 (low complexity, fast to build, no separate SPA). Migrate to React if interaction complexity grows.

**Effort:** S (ADR).

---

### F-153: BigQuery query cost runaway — ADVISORY

**Where:** BigQuery is the analytical projection. Internal users query it.

**Why it matters:** A single bad query (no partition pruning, full table scan) can cost serious money on BigQuery's on-demand pricing. Without controls, surprise bills.

**What's needed:** ADR: BigQuery cost controls. Slot reservations or capacity-based pricing for predictable cost; per-user query quotas; cost dashboards; "expensive query" alerting.

**Effort:** S.

---

### F-154: Multi-tenancy / partner isolation — ADVISORY

**Where:** Partners share infrastructure. ARD partitions ingestion per partner via Pub/Sub; verification is shared.

**Why it matters:** A noisy partner (huge feed, many quarantine events) shouldn't degrade verification for other partners' members. Per-partner resource quotas, per-partner rate limits on DQ engine, per-partner isolation in Splink runs.

**What's needed:** ADR: tenant isolation patterns. Where it matters (DQ engine concurrent feeds, Splink batch sizes, audit-emission rates per partner) and where it doesn't (verification is shared).

**Effort:** S.

---

### F-155: UUID v4 vs v7 for member_id — ADVISORY

**Where:** `canonical_member.member_id UUID PRIMARY KEY`.

**Why it matters:** UUID v4 (random) inserts cause B-tree page splits across the index, hurting insert performance at scale. UUID v7 (time-ordered, RFC 9562) is monotonic and inserts cleanly. v7 became standard in 2024.

**What's needed:** ADR: use UUID v7 generated app-side (Postgres has no native v7 generator yet; Python's `uuid_extensions` or a small wrapper).

**Effort:** S.

---

### F-156: Pagination patterns — ADVISORY

**Where:** No pagination contract for any internal API.

**Why it matters:** Manual review queue may have thousands of items. Audit log queries may return many rows. Without a pagination contract, callers do unbounded queries.

**What's needed:** Convention: cursor-based pagination on every list endpoint. Standard query params (`limit`, `cursor`); standard response shape (`items`, `next_cursor`).

**Effort:** S.

---

### F-157: Locale / clock skew — ADVISORY

**Where:** Multiple Cloud Run instances; cross-instance wall clocks.

**Why it matters:** Audit ordering by wall-clock timestamp is unreliable across instances. BR-104 records `decided_at` — clock skew between match-decision-emitter and audit-event-emitter can produce inverted ordering.

**What's needed:** Convention: every timestamp comes from the database (`now()` at insert time) where possible. App-generated timestamps are advisory. Audit ordering uses Pub/Sub publish-time, not event-payload timestamp, where ordering matters.

**Effort:** S.

---

### F-158: Internationalization — ADVISORY

**Where:** Names with non-ASCII characters; address formats; phone formats. ARD's `normalized_last_name` for matching is unspecified.

**Why it matters:** Eligibility data has international names (especially in healthcare with diverse populations). A "normalize" function that drops non-ASCII characters silently lowers match recall.

**What's needed:** ADR: normalization rules. Unicode-aware (NFKC normalization, accent folding optional, casefolding). Test cases with realistic international names. Phone normalization via libphonenumber.

**Effort:** S.

---

### F-159: Schema validation for partner feeds — ADVISORY

**Where:** DQ engine validates partner feeds. Tooling not specified.

**Why it matters:** Pydantic is great for FastAPI but heavy for streaming row processing. Pandera (DataFrame-aware) or jsonschema (lightweight) may be better fits for the DQ engine.

**What's needed:** ADR: DQ engine validation library.

**Effort:** S.

---

### F-160: Documentation as code — ADVISORY

**Where:** OpenAPI generated from FastAPI is mentioned implicitly. Schema docs, architecture diagrams — manual?

**Why it matters:** Docs that aren't generated from code drift.

**What's needed:** Convention: OpenAPI auto-generated from FastAPI; ER diagrams generated from SQLModel/SQLAlchemy metadata; architecture diagrams as Mermaid in markdown so PRs can update them.

**Effort:** S.

---

## Summary triage

| Severity | Count | Examples |
|---|---|---|
| BLOCKER | 13 | Idempotency contract (F-101), Transactional outbox (F-102), Idempotent consumers (F-103), Race conditions on canonical (F-104), Audit durability (F-107), Verification fail-closed (F-108), Error taxonomy (F-110), Logging schema (F-115), Correlation IDs (F-116), pgbouncer constraints (F-121), Message schema format (F-128), Cold start (F-139), Monorepo decision (F-143) |
| FINDING | 37 | Retry policies, dead-letter, partial-parse recovery, migration recovery, metrics, tracing, health probes, alert classes, connection pooling, migration ordering, read consistency, caching, rate-limit durability, audit routing, internal API errors, idempotency keys, type sharing, config typing, local substrate, test data, Splink reproducibility, perf harness, chaos, test isolation, concurrency settings, service identity, privilege escalation, state machine pattern, error catalog, local dev, CI/CD, long-running ops, hot-reload, backpressure |
| ADVISORY | 10 | Reviewer UX, frontend choice, BigQuery cost, multi-tenancy, UUID v7, pagination, clock skew, i18n, schema validation library, docs-as-code |
| **Total** | **60** | |

---

## Recommended path before backlog

1. **Address all 13 BLOCKERS.** Most are S effort (one ARD section or one ADR). Two are M (correlation IDs implementation discipline, monorepo decision with corresponding repo restructure if needed).
2. **Address F-117 (metrics), F-118 (tracing), F-131 (cross-service types), F-132 (config typing)** as Phase 0 foundation work. These shape every service's structure.
3. **Defer the remaining 24 FINDINGS to Phase 0 ADRs** with named owners and target phases. Each ADR is small (S effort).
4. **Address ADVISORIES** opportunistically. Several (F-155 UUID v7, F-157 clock skew, F-158 i18n, F-156 pagination) want decisions before the corresponding code is written, but they don't block backlog kickoff.

If the BLOCKERS are resolved, the platform will be implementable, observable, and effective. Without them, expect the symptoms enumerated in the TL;DR — duplicate processing, doubled audit events, untraceable ingestion failures, race-condition state corruption, brittle error handling.

---

## Hand-offs to subsequent review rounds

| Round | Reviewer | Findings to dig into |
|---|---|---|
| 3 | Security / Red-Team Architect | F-104 (concurrency races affect security state), F-108 (fail-closed contract), F-141 (service identity), F-142 (privilege escalation), F-103 (idempotent consumers — duplicate audit events have integrity implications) |
| 3 | Data-Engineering Principal | F-101 (ingestion idempotency), F-102 (outbox), F-105 (SCD2 closing), F-127 (audit routing), F-133 (test substrate), F-134 (synthetic data), F-150 (backpressure) |
| 3 | Infra / DevOps Architect | F-119 (health probes), F-122 (pool sizing), F-123 (migration deploy ordering), F-126 (Memorystore tier), F-139 (cold start), F-140 (concurrency settings), F-146 (local dev), F-147 (CI/CD), F-153 (BigQuery cost) |
| 3 | Application Engineer (UX-aware) | F-151 (reviewer UX), F-152 (frontend), F-130 (idempotency keys at HTTP) |

---

## What this review did NOT cover

Out of scope for the chief programmer lens:

- BRD content correctness against domain reality (DE Principal's lens; clinical-trust reviewer)
- Specific GCP service configuration (Infra/DevOps Architect)
- Detailed cryptographic primitive choice (Security Architect)
- Architectural decomposition tradeoffs (covered by Round 1 Principal Architect)
- The shape of the code review process or PR conventions (covered by harness CLAUDE.md)
- Performance modeling specifics (covered by Round 1 F-001 capacity model)

These belong to other reviewers. This round focused on the code-level discipline gaps that, if left unaddressed, fragment the system at the seams.
