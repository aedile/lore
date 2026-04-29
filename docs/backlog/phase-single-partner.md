# Phase 1 — Single-Partner End-to-End Backlog

| Field | Value |
|-------|-------|
| **ARD reference** | §"Phased Delivery" / Phase 1 |
| **Goal** | One partner, real format, ingested through verification, with the architectural shape complete but feature surface minimal. |
| **Status** | LIVE BACKLOG |

---

## Phase 1 Goal

A single partner, real format, ingested through verification, with the architectural shape complete but feature surface minimal.

## Phase 1 Entry Gate

- All Phase 0 exit criteria met (per `phase-foundation.md`).
- First partner identified; data sharing agreement in negotiation; BAA signed or scheduled.
- Privacy Officer + Security Officer sign-off on Phase 1 scope.
- 8 Phase-0 ADRs authored or scoped (RR-006, RR-009, RR-010 all answered).

## Phase 1 Exit Criteria (per ARD)

- BR-202 transition table fully covered by tests.
- Sample feed processed end-to-end with zero plaintext PII in any log (XR-005 LIVE-verified).
- Verification API returns correct outcome on canonical members and `NOT_VERIFIED` on synthetic non-members.
- Latency-distribution test per ADR-0009 passes (statistical indistinguishability above floor).
- Audit redaction scan passes against representative log fixtures.
- Datastream replication to BigQuery is working with lag under `DATASTREAM_LAG_TARGET_SECONDS`.
- Audit chain validator running with zero breaks; external anchor publication operational.
- Outbox publisher operational; consumer idempotency verified.
- IaC drift detection clean; quarterly DR drill completed.
- Privacy Officer signs off on Phase 1 production traffic readiness.

---

## Epics

| Key | Epic | Description |
|-----|------|-------------|
| ING | Format Adapter + Mapping | One format adapter, one partner YAML mapping, mapping engine |
| DQ  | DQ Required Tier | Field-tier validation, per-record quarantine, feed threshold |
| IDR | Identity Resolution (Deterministic) | Tier 1 deterministic anchor; pre-Splink |
| CAN | Canonical Eligibility | State machine (BR-202), SCD2 derivation, advisory locks |
| VER | Verification API | Skeleton with JWT + latency floor + collapsed responses |
| TOK | Tokenization Production-Ready | TokenizationService prod-grade; per-partner salt LIVE |
| AUD | Audit Emission | Outbox publisher, audit_event store, redaction-scanner LIVE |
| DAT | Datastream → BigQuery | CDC replication, lag monitoring |
| ANC | Audit Chain + External Anchor | Hash-chain validator, RFC 3161 TSA integration, cross-org publish |
| ONB | Partner Onboarding | First partner: schema registry, mapping YAML, monitoring dashboards |
| COM | Compliance — Phase 1 | NPP authoring, BAA, partner data sharing agreement, subprocessor BAA chain |
| UX  | UX — Phase 1 | Verification failure UX, lockout recovery service blueprint, member rights submission UX |
| DR  | DR Drill (First) | Quarterly DR drill scoped + executed |
| TST | End-to-End Test Harness | Canonical scenarios; synthetic data; CI-runnable |

---

## Stories

### Epic ING — Format Adapter + Mapping Engine

#### P1-ING-001 — CSV format adapter (per AD-016)
- **As** the Ingestion squad
  **I want** a CSV format adapter that reads partner files and emits row dicts with parse-error rows separated
  **So that** AD-016 (format adapters are code; mappings are YAML) is implemented with one canonical adapter.
- **AC**
  - Given a well-formed CSV, when adapted, then each row becomes a dict + per-row metadata (line number, raw bytes hash for forensic).
  - Given a row with a parse error (unterminated quote, bad encoding), when adapted, then it is emitted as a `parse_error` record (not silently dropped) with the raw line preserved per BR-302.
  - Given a CSV with BOM / encoding ambiguity, when adapted, then encoding is auto-detected and recorded in metadata.
- **Originating** AD-016, BR-301, BR-302
- **Depends on** P0-OBS-001
- **Tier** CRITICAL · **Size** M · **Owner** Ingestion

#### P1-ING-002 — Per-partner YAML mapping registry
- **As** the Ingestion squad
  **I want** a YAML registry mapping partner-source columns to canonical fields with per-field tier assignments
  **So that** AD-016 holds (mappings are configuration, not code) and adding a future partner is YAML-only.
- **AC**
  - Given a partner mapping YAML, when loaded, then it validates against a JSON schema (column→canonical-field, normalization rules, tier).
  - Given a mapping with a missing required field, when validated, then validation fails with a specific error pointing to the missing canonical field.
  - Given two partners with different column orders, when each is processed, then both produce canonical staging records (no partner-specific code path).
- **Originating** AD-016, BR-801, BR-802, R3 S-006
- **Depends on** P1-ING-001
- **Tier** CRITICAL · **Size** M · **Owner** Ingestion

#### P1-ING-003 — Mapping engine
- **As** the Ingestion squad
  **I want** a mapping engine that consumes adapter output + YAML mapping and emits canonical staging dicts
  **So that** the canonical schema is the contract that downstream pipeline stages (DQ, ID resolution) consume.
- **AC**
  - Given adapter output + a partner mapping, when the engine runs, then it produces canonical staging records or quarantine records (per BR-302 tiers).
  - Given a normalization rule (e.g., uppercase, trim, date format), when applied, then the canonical value reflects the rule and original raw value is preserved in metadata.
  - Given a mapping requesting a field with no source column, when the engine runs, then it raises a `MAPPING_INCOMPLETE` error before processing rows.
- **Originating** AD-016, BR-301
- **Depends on** P1-ING-001, P1-ING-002
- **Tier** CRITICAL · **Size** M · **Owner** Ingestion

#### P1-ING-004 — Within-feed deduplication (BR-601)
- **As** the Ingestion squad
  **I want** within-feed deduplication on `(partner_id, partner_member_id)` with last-record-wins semantics
  **So that** BR-601 is implemented and audit emission documents resolved duplicates.
- **AC**
  - Given a feed with two rows sharing `(partner_id, partner_member_id)`, when deduped, then the last-line wins and the prior line is recorded in the dedup audit event.
  - Given a feed with no duplicates, when deduped, then output equals input and zero dedup events emit.
  - Given the dedup audit event, when inspected, then it carries `duplicate_count`, `kept_line`, and `feed_id` (no plaintext PII; tokens only).
- **Originating** BR-601, XR-005
- **Depends on** P1-ING-003, P1-AUD-001
- **Tier** CRITICAL · **Size** S · **Owner** Ingestion

#### P1-ING-005 — Snapshot-diff CDC against prior feed (BR-602)
- **As** the Ingestion squad
  **I want** the ingestion pipeline to compute the diff against the prior feed for the same partner
  **So that** BR-602 is implemented (incremental CDC even when partner sends full snapshots) and downstream stages see only changes.
- **AC**
  - Given two consecutive feeds for the same partner, when diffed, then the diff classifies rows as ADDED / CHANGED / REMOVED / UNCHANGED.
  - Given a CHANGED classification, when inspected, then the changed-fields delta is preserved for SCD2 history derivation.
  - Given a REMOVED row, when processed, then it routes through the deletion-suppression check (P2-DEL-001 stub for Phase 1; LIVE in Phase 2).
- **Originating** BR-602, BR-606
- **Depends on** P1-ING-003
- **Tier** CRITICAL · **Size** M · **Owner** Ingestion

#### P1-ING-006 — Partner SFTP / inbound transport (per `[partner-sftp]` ADR)
- **As** the Platform/SRE squad
  **I want** the partner inbound transport implemented per the P0-ADR-006 outcome (SFTP / API / SaaS connector / file-on-bucket)
  **So that** the first partner can land files into the prod project.
- **AC**
  - Given a partner-authenticated upload, when received, then the file lands in the landing-zone bucket with metadata (partner_id, received_at, sha256, size).
  - Given the upload, when authentication is logged, then the audit event records principal, source IP, transport, and outcome (no plaintext PII).
  - Given a malformed / oversized upload, when attempted, then it is rejected with a clear error and a P2 alert fires.
- **Originating** AD-001, BR-801, P0-ADR-006
- **Depends on** P0-ADR-006, P0-DAT-005
- **Tier** CRITICAL · **Size** L · **Owner** Platform/SRE

---

### Epic DQ — Data Quality Required Tier

#### P1-DQ-001 — Field-tier registry and per-record validation (BR-301, BR-302)
- **As** the Ingestion squad
  **I want** field-tier validation enforcing Required-tier rules per partner mapping
  **So that** BR-301 + BR-302 hold for the first partner.
- **AC**
  - Given a record missing a Required-tier field, when validated, then it routes to per-record quarantine with a structured reason.
  - Given a record with all Required-tier fields present, when validated, then it proceeds to the canonical-staging stage.
  - Given the quarantine bucket, when inspected, then quarantined records carry token-only references (no plaintext PII per XR-005).
- **Originating** BR-301, BR-302, XR-005
- **Depends on** P1-ING-003, P0-DAT-005
- **Tier** CRITICAL · **Size** M · **Owner** Ingestion

#### P1-DQ-002 — Feed-level quarantine threshold (BR-303)
- **As** the Ingestion squad
  **I want** a configurable feed-level threshold (`FEED_QUARANTINE_THRESHOLD_PCT`, default 5%) that, when exceeded by per-record quarantines, escalates to feed-level quarantine
  **So that** BR-303 holds and a broken feed doesn't poison downstream stages.
- **AC**
  - Given a feed with 4% per-record quarantine, when processed, then the feed proceeds normally.
  - Given a feed with 6% per-record quarantine (threshold = 5%), when processed, then the entire feed is quarantined and a P1 alert fires for the partner-onboarding owner.
  - Given the threshold, when adjusted via config, then the change flows through XR-010 promotion path and emits a `CONFIG_CHANGE_PROD` audit event.
- **Originating** BR-303
- **Depends on** P1-DQ-001, P0-CFG-001
- **Tier** CRITICAL · **Size** S · **Owner** Ingestion

#### P1-DQ-003 — Schema drift detection (BR-304)
- **As** the Ingestion squad
  **I want** schema-drift detection that classifies new feeds as ADDITIVE / REMOVED / TYPE_CHANGE compared to the partner schema registry
  **So that** BR-304 holds: ADDITIVE drift is auto-accepted with notification; REMOVED / TYPE_CHANGE quarantines the feed.
- **AC**
  - Given a feed with a new column not in the registry, when detected, then it is recorded as `SCHEMA_DRIFT_ADDITIVE` and the feed proceeds.
  - Given a feed missing a column present in the registry, when detected, then the feed is quarantined and a P1 alert fires.
  - Given a feed where a column's type appears to have changed, when detected, then the feed is quarantined.
- **Originating** BR-304
- **Depends on** P1-ING-002, P1-DQ-001
- **Tier** CRITICAL · **Size** M · **Owner** Ingestion

#### P1-DQ-004 — Profile baseline + drift detection (BR-305)
- **As** the Ingestion squad
  **I want** per-partner profile baselines (null rates, value distributions for low-cardinality columns, length stats) with drift detection
  **So that** BR-305 holds: a partner sending a degraded feed is detected before it pollutes canonical state.
- **AC**
  - Given the first feed for a partner, when processed, then a baseline profile is captured and persisted.
  - Given subsequent feeds, when their profile drifts beyond `PROFILE_DRIFT_THRESHOLD_PCT`, then a P2 alert fires and the feed continues (drift is signal, not block, unless threshold-quarantined).
  - Given the baseline, when reviewed, then it is queryable and human-readable.
- **Originating** BR-305
- **Depends on** P1-DQ-001, P0-DAT-005
- **Tier** IMPORTANT · **Size** M · **Owner** Ingestion

#### P1-DQ-005 — Reconciliation (row counts in vs. out) (BR-605)
- **As** the Ingestion squad
  **I want** a reconciliation step that asserts: rows-in = rows-out + quarantined + suppressed-deleted
  **So that** BR-605 holds and silent data loss is impossible.
- **AC**
  - Given a feed end-of-run, when reconciliation runs, then the equality holds; otherwise a P1 alert fires.
  - Given a reconciliation failure, when triaged, then the per-stage row counts are queryable for forensic.
- **Originating** BR-605
- **Depends on** P1-DQ-001..P1-DQ-004, P1-IDR-001..002
- **Tier** CRITICAL · **Size** S · **Owner** Ingestion

---

### Epic IDR — Identity Resolution (Deterministic Tier 1)

#### P1-IDR-001 — Tier 1 deterministic match (BR-101 Tier 1)
- **As** the Identity Resolution squad
  **I want** a deterministic match that joins staging records to canonical members on `(partner_member_id, normalized DOB, normalized last_name)` (or the AD-008 anchor)
  **So that** BR-101 Tier 1 is implemented and same-partner re-arrivals deterministically auto-merge.
- **AC**
  - Given a staging record matching exactly one canonical member on the deterministic anchor, when resolved, then the record auto-merges (no review queue) and a `MATCH_TIER_1` audit event fires.
  - Given a staging record matching zero canonical members, when resolved, then it routes to "new canonical member" path.
  - Given a staging record matching > 1 canonical member on the deterministic anchor, when resolved, then it routes to manual review (anomaly; should not happen and indicates upstream issue).
- **Originating** BR-101, AD-008, AD-011
- **Depends on** P1-CAN-001
- **Tier** CRITICAL · **Size** M · **Owner** Identity Resolution

#### P1-IDR-002 — Match decision audit trail (BR-104)
- **As** the Identity Resolution squad
  **I want** every match decision recorded in `match_decision` table with the inputs, outputs, tier, and rationale
  **So that** BR-104 (explainability) holds and any merge is reproducible from the audit trail.
- **AC**
  - Given a match decision, when persisted, then the row carries `tier`, `inputs_hash` (token-only), `algorithm_version`, `decision`, `correlation_id`.
  - Given a query for "why was member X merged with Y?", when run, then the answer is one row in `match_decision` with full rationale.
  - Given a Splink-tuning change in Phase 2, when applied, then existing match_decision rows still validate with their `algorithm_version` (no retroactive interpretation drift).
- **Originating** BR-104, AD-011
- **Depends on** P1-IDR-001, P1-CAN-001
- **Tier** CRITICAL · **Size** M · **Owner** Identity Resolution

#### P1-IDR-003 — Pre-publication deletion-ledger consultation
- **As** the Identity Resolution squad
  **I want** identity resolution to consult the deletion ledger before publishing a canonical merge/insert
  **So that** even in Phase 1 (deletion ledger stubbed), the integration point is real and Phase 2's full ledger drops in without further surgery.
- **AC**
  - Given a staging record whose tokenized identity-hash matches a deletion-ledger entry, when resolved, then the record routes to `SUPPRESSED_DELETED` instead of merging.
  - Given the deletion ledger query, when issued, then it uses the HMAC-keyed hash (ADR-0003) — even with the Phase 1 stub returning empty.
  - Given Phase 2 ledger live, when re-runs against Phase 1 data, then no Phase 1 record was wrongly suppressed and no Phase 1 record now should-have-been-suppressed-and-wasn't.
- **Originating** BR-703, ADR-0003, ADR-0005
- **Depends on** P1-IDR-001, P1-TOK-001
- **Tier** CRITICAL · **Size** S · **Owner** Identity Resolution

---

### Epic CAN — Canonical Eligibility

#### P1-CAN-001 — Canonical schema migrations (per ARD §"Data Schemas")
- **As** the Data Engineering squad
  **I want** Alembic migrations creating `canonical_member`, `partner_enrollment`, `member_history`, `match_decision`, `deletion_ledger`, `review_queue` per ARD specs
  **So that** Phase 1 has the full operational schema even where some tables are sparsely populated until Phase 2.
- **AC**
  - Given a fresh AlloyDB instance, when migrations run, then all six tables exist with declared constraints and indexes.
  - Given the schema, when reviewed, then `partner_member_id` is tokenized (not plaintext), per-class ciphertext fields point at vault refs, and FK constraints are present.
  - Given the migration, when run twice, then it is idempotent (second run is a no-op).
- **Originating** AD-007, AD-022, ARD §"Data Schemas"
- **Depends on** P0-DAT-001, P0-TBL-004
- **Tier** CRITICAL · **Size** M · **Owner** Data Engineering

#### P1-CAN-002 — State machine engine (BR-202 transitions)
- **As** the Canonical Eligibility squad
  **I want** a state machine engine enforcing BR-202 transitions on `canonical_member.status`
  **So that** illegal state transitions raise rather than silently corrupt state.
- **AC**
  - Given an attempt to transition from `TERMINATED` directly to `ELIGIBLE_ACTIVE`, when called, then the engine raises `ILLEGAL_TRANSITION` and audits.
  - Given a valid transition (e.g., `PENDING_RESOLUTION` → `ELIGIBLE_ACTIVE`), when called, then it succeeds, persists, and emits a state-change event via outbox.
  - Given the BR-202 transition matrix, when exhaustively tested, then 100% of cells (legal + illegal) are covered by tests.
- **Originating** BR-202
- **Depends on** P1-CAN-001
- **Tier** CRITICAL · **Size** M · **Owner** Canonical Eligibility

#### P1-CAN-003 — SCD2 history derivation (BR-202, BR-204)
- **As** the Canonical Eligibility squad
  **I want** every state-bearing change to canonical_member to close the prior `member_history` row (set `valid_to`) and open a new row
  **So that** historical reconstruction is always possible from `member_history` alone.
- **AC**
  - Given a state change at time T, when persisted, then prior history row is closed at T and a new row opens at T (no gaps; no overlaps).
  - Given a query "state of member X at time T-Δ", when run, then the answer derives from `member_history` correctly even for long-ago timestamps.
  - Given concurrent state changes on different members, when they commit, then no cross-member history corruption is observed (per-member advisory lock from P0-TBL-003 mediates).
- **Originating** BR-202, BR-204, AD-022
- **Depends on** P1-CAN-002, P0-TBL-003
- **Tier** CRITICAL · **Size** M · **Owner** Canonical Eligibility

#### P1-CAN-004 — Partner enrollment (one canonical → many partner_enrollment) (BR-205)
- **As** the Canonical Eligibility squad
  **I want** the `partner_enrollment` table populated per partner for each canonical member
  **So that** BR-205 holds: one canonical identity may be enrolled with multiple partners, with per-partner state and dates.
- **AC**
  - Given a member enrolled with two partners, when queried, then `canonical_member` has one row and `partner_enrollment` has two rows.
  - Given an enrollment status change, when applied, then it is partner-scoped (does not affect canonical_member status unless all enrollments collapse).
- **Originating** BR-205, AD-022
- **Depends on** P1-CAN-001
- **Tier** CRITICAL · **Size** S · **Owner** Canonical Eligibility

#### P1-CAN-005 — Outbox emission for state changes
- **As** the Canonical Eligibility squad
  **I want** every state-bearing change to emit an outbox row (state-change event) inside the same DB transaction
  **So that** ADR-0005 holds: downstream consumers (Datastream→BigQuery, audit, etc.) see the change exactly once eventually.
- **AC**
  - Given a state change committed, when the outbox is polled, then a corresponding row exists with the canonical event payload.
  - Given a transaction rollback, when reviewed, then no outbox row was created (atomicity preserved).
  - Given the publisher draining the outbox, when it publishes to Pub/Sub, then it deletes the row only after acked publish.
- **Originating** ADR-0005, AD-027
- **Depends on** P1-CAN-002, P0-TBL-001
- **Tier** CRITICAL · **Size** S · **Owner** Canonical Eligibility

---

### Epic VER — Verification API Skeleton

#### P1-VER-001 — Verification API skeleton (FastAPI, JWT, canonical lookup)
- **As** the Verification squad
  **I want** a FastAPI service exposing `POST /v1/verify` with RS256 JWT verification + canonical lookup
  **So that** the public verification contract is shipped at the externally-correct shape.
- **AC**
  - Given a valid JWT and a verifying claim, when the request is issued, then the service returns `{outcome: VERIFIED}` if the claim matches a canonical eligible member.
  - Given a verifying claim that doesn't match any canonical member, when issued, then the service returns `{outcome: NOT_VERIFIED}`.
  - Given an expired or wrongly-signed JWT, when issued, then the service returns 401 with no internal-state leakage.
- **Originating** BR-401, ADR-0004, ADR-0009
- **Depends on** P1-CAN-001, P1-CAN-002
- **Tier** CRITICAL · **Size** L · **Owner** Verification

#### P1-VER-002 — JWT verifier with strict claim validation (ADR-0004)
- **As** the Verification squad
  **I want** the JWT verifier to enforce: RS256 only, `iss` allowlist, `aud` allowlist, `exp` ≤ 5min from `iat`, `jti` replay defense
  **So that** ADR-0004 holds end-to-end.
- **AC**
  - Given a JWT with `alg: HS256` or `alg: none`, when verified, then it is rejected.
  - Given a JWT with a `jti` already seen in the replay window, when verified, then it is rejected with audit emission.
  - Given a JWT with `exp - iat > 300s`, when verified, then it is rejected.
- **Originating** ADR-0004, R3 S-013
- **Depends on** P1-VER-001
- **Tier** CRITICAL · **Size** M · **Owner** Verification

#### P1-VER-003 — Latency floor enforcement (ADR-0009)
- **As** the Verification squad
  **I want** every Verification API response held until `VERIFICATION_LATENCY_FLOOR_MS` elapses from request arrival
  **So that** ADR-0009 timing-equalization holds.
- **AC**
  - Given a request that resolves in 30ms internally, when the response is emitted, then ≥ floor (250ms initial) elapsed since arrival.
  - Given a request that resolves in 220ms (rate-limited path), when the response is emitted, then ≥ floor elapsed.
  - Given the held window, when profiled, then it is filled with low-priority work (audit emission completion, etc.) — not idle sleep.
- **Originating** BR-401, BR-404, ADR-0009
- **Depends on** P1-VER-001, P0-CFG-001
- **Tier** CRITICAL · **Size** M · **Owner** Verification

#### P1-VER-004 — Response shape padding (ADR-0009 §3)
- **As** the Verification squad
  **I want** every Verification API response body padded to `VERIFICATION_RESPONSE_BODY_BYTES` with `_padding`
  **So that** TCP packet sizes are equivalent across outcomes (ADR-0009 §3).
- **AC**
  - Given any response (VERIFIED / NOT_VERIFIED / 401 friction-required), when measured, then body size is exactly `VERIFICATION_RESPONSE_BODY_BYTES` (default 256).
  - Given padding, when inspected, then it is random bytes (not zero-padded; defense-in-depth).
  - Given the parameter, when adjusted via config, then promotion path enforces (P0-CFG-002).
- **Originating** ADR-0009 §3
- **Depends on** P1-VER-001
- **Tier** CRITICAL · **Size** S · **Owner** Verification

#### P1-VER-005 — Latency-distribution test gate (ADR-0009 §7)
- **As** the Verification squad
  **I want** a test that submits 10,000 representative requests across all internal-state paths and asserts statistical indistinguishability above the floor
  **So that** ADR-0009 §7 holds and regressions are caught at CI.
- **AC**
  - Given the test, when run, then it issues 10,000+ requests and the per-state latency distributions pass KS at p ≥ 0.05.
  - Given a deliberate regression (test removes the floor), when CI runs, then the test fails (negative-test verifies harness).
  - Given the test in CI, when scheduled, then it runs nightly (slow; not on every PR) but blocks release.
- **Originating** ADR-0009 §7, BR-404
- **Depends on** P1-VER-003, P1-VER-004
- **Tier** CRITICAL · **Size** M · **Owner** Verification

#### P1-VER-006 — Verification API audit emission via outbox
- **As** the Verification squad
  **I want** every verification request to emit an `IDV_REQUEST` audit event via the outbox
  **So that** all external-facing verification activity is auditable per BR-501.
- **AC**
  - Given a verification request, when handled, then exactly one `IDV_REQUEST` event is in the outbox at transaction-commit time.
  - Given the audit event, when inspected, then it includes outcome, internal_state (audit-only), tokenized claim, request_id, JWT iss/aud, timestamp — and zero plaintext PII.
- **Originating** BR-501, ADR-0006, XR-005
- **Depends on** P1-VER-001, P1-AUD-001
- **Tier** CRITICAL · **Size** S · **Owner** Verification

---

### Epic TOK — Tokenization Production-Ready

#### P1-TOK-001 — TokenizationService prod-ready (HSM-bound; per-partner salt LIVE)
- **As** the Vault squad
  **I want** TokenizationService running with HSM-bound KEKs, per-partner salts in HKDF info, full audit emission
  **So that** Phase 1 production traffic uses the production cryptographic posture from day 1.
- **AC**
  - Given a tokenize call with `partner_id=A`, when issued, then the resulting token differs from the same plaintext under `partner_id=B` (P0-TOK-003 holds).
  - Given a detokenize call by an authorized service, when issued, then plaintext returns and `DETOK` audit emits.
  - Given a load test of 200 RPS against TokenizationService, when run, then p95 < 30ms (verified against ADR-0009 budget).
- **Originating** ADR-0003, AD-009
- **Depends on** P0-TOK-001..003
- **Tier** CRITICAL · **Size** M · **Owner** Vault

#### P1-TOK-002 — Tombstone on member identity removal
- **As** the Vault squad
  **I want** the `tombstone(token)` flow tested and audited
  **So that** when Phase 2 deletion lands, the tombstone primitive is proven from Phase 1.
- **AC**
  - Given a tombstone call, when issued, then subsequent detokenize returns `TOMBSTONED` and a `TOMBSTONE` audit event is preserved.
  - Given a tombstoned token, when re-tokenized later (re-arriving member), then a fresh distinct token is generated (per ADR-0003 — re-tokenization does not collide).
- **Originating** ADR-0003 §"Tombstone semantics", BR-702
- **Depends on** P1-TOK-001
- **Tier** IMPORTANT · **Size** S · **Owner** Vault

---

### Epic AUD — Audit Emission

#### P1-AUD-001 — Outbox publisher (Cloud Run service)
- **As** the Audit squad
  **I want** a Cloud Run service polling outbox tables across contexts and publishing to Pub/Sub
  **So that** ADR-0005 transactional outbox flows end-to-end.
- **AC**
  - Given an outbox row inserted, when the publisher polls (default interval 1s), then it publishes to the topic and deletes the row on ack.
  - Given a publish failure, when retried, then the row is not deleted until success; backoff is exponential.
  - Given the publisher under load (1000 events/sec), when measured, then end-to-end latency p95 < 5s from outbox-insert to BigQuery audit row.
- **Originating** ADR-0005, AD-027
- **Depends on** P0-TBL-001, P0-DAT-003
- **Tier** CRITICAL · **Size** L · **Owner** Audit

#### P1-AUD-002 — Audit consumer (Dataflow streaming)
- **As** the Audit squad
  **I want** a Dataflow streaming pipeline consuming the audit topic and writing to BigQuery `audit_event`
  **So that** the operational audit tier is queryable per BR-503.
- **AC**
  - Given an audit event published, when the pipeline runs, then a BigQuery row appears within 30s.
  - Given duplicate events (at-least-once delivery), when consumed, then the consumer dedupes via `event_id` (idempotent per ADR-0005).
  - Given the pipeline failing, when restarted, then it resumes from last checkpoint with no double-counting.
- **Originating** BR-503, ADR-0005, ADR-0006
- **Depends on** P1-AUD-001, P0-DAT-004
- **Tier** CRITICAL · **Size** L · **Owner** Audit

#### P1-AUD-003 — High-criticality audit tier writer (GCS + hash chain)
- **As** the Audit squad
  **I want** a separate writer for high-criticality events (PII access, identity merge, deletion) writing append-only to GCS with hash-chain
  **So that** BR-501..504 tamper-evidence holds for the high tier.
- **AC**
  - Given a high-criticality event, when emitted, then the chain head hash advances and the prior-event-hash is correct.
  - Given a chain-validity walk, when run, then validation succeeds (no breaks).
  - Given Bucket Lock retention, when verified, then the bucket has retention enabled (Phase 2 will lock the policy).
- **Originating** BR-501, BR-503, BR-504, ADR-0008
- **Depends on** P1-AUD-001, P0-DAT-005
- **Tier** CRITICAL · **Size** L · **Owner** Audit

#### P1-AUD-004 — Redaction scanner LIVE in CI + on streaming logs
- **As** the Security squad
  **I want** the redaction scanner running on every PR's log-fixture diff and on a 1% sample of streaming prod logs
  **So that** XR-005 holds continuously, not just at design time.
- **AC**
  - Given a PR introducing a log line that would emit plaintext SSN, when CI runs, then the scanner fails the PR.
  - Given a streaming sample with a leak, when scanned, then a P0 alert fires (P0-OBS-007).
  - Given the scanner's regex set, when reviewed, then it covers SSN, full email, phone w/ area code, DOB-as-date, MRN, full credit card.
- **Originating** XR-005, R3 S-039, ADR-0006
- **Depends on** P0-OBS-001, P0-OBS-007
- **Tier** CRITICAL · **Size** S · **Owner** Security

---

### Epic DAT — Datastream → BigQuery

#### P1-DAT-001 — Datastream replication AlloyDB → BigQuery
- **As** the Data Engineering squad
  **I want** Datastream replicating canonical_member, partner_enrollment, member_history, match_decision into BigQuery `analytical` dataset
  **So that** Pattern C (operational vs analytical separation) is implemented.
- **AC**
  - Given a write to AlloyDB, when monitored, then the corresponding BigQuery row appears within `DATASTREAM_LAG_TARGET_SECONDS` (default 30s).
  - Given Datastream lag exceeding the target, when sustained for > 5 min, then a P2 alert fires.
  - Given the BigQuery `analytical` dataset, when queried, then PII-tier columns are masked or excluded per AD-007 + AD-002.
- **Originating** AD-007, AD-022, RR-001, BR-205
- **Depends on** P0-DAT-004, P1-CAN-001
- **Tier** CRITICAL · **Size** M · **Owner** Data Engineering

#### P1-DAT-002 — BigQuery analytical schema + masking policies
- **As** the Data Engineering squad
  **I want** BigQuery schemas + column-level masking policies for the analytical dataset
  **So that** PH-resident analysts can query without ever seeing PII (BR-506).
- **AC**
  - Given a PH-resident principal querying the analytical dataset, when running a SELECT *, then PII columns return masked (token-only) values.
  - Given a US-resident analyst principal with the right role, when querying, then PII columns return raw (token-only; never plaintext).
  - Given an attempt to bypass masking via UDF, when inspected, then BigQuery deny rules catch it (or the UDF cannot read raw column anyway).
- **Originating** AD-002, BR-506, RR-001
- **Depends on** P1-DAT-001
- **Tier** CRITICAL · **Size** M · **Owner** Data Engineering

---

### Epic ANC — Audit Chain + External Anchor

#### P1-ANC-001 — Continuous chain validator (Cloud Run scheduled)
- **As** the Audit squad
  **I want** a Cloud Run job that validates the high-criticality chain in real-time per-event and bulk hourly
  **So that** ADR-0008 §2 is implemented.
- **AC**
  - Given a chain-break (test injection), when the validator runs, then it pages on-call P0 within one cycle and freezes the audit consumer.
  - Given a clean chain over 24h, when validated, then no alerts fire and a `CHAIN_HEALTH_OK` metric updates.
  - Given the validator running, when monitored, then per-event validation completes within 100ms p99.
- **Originating** ADR-0008 §2, R3 S-030
- **Depends on** P1-AUD-003
- **Tier** CRITICAL · **Size** M · **Owner** Audit

#### P1-ANC-002 — Cross-org anchor publication (Compliance org)
- **As** the Audit squad
  **I want** every hourly chain head hash published to the Compliance-org anchor-registry bucket with a Compliance-org KMS signature
  **So that** ADR-0008 §3a defense-in-depth is operational.
- **AC**
  - Given the hourly schedule, when triggered, then the chain head + timestamp + signature is appended to the Compliance-org bucket within 60s.
  - Given the published anchor, when verified out-of-band, then signature validates against the Compliance-org KMS public key.
  - Given an Engineering-org admin attempting to write the anchor bucket, when attempted, then it is denied (cross-org IAM separation).
- **Originating** ADR-0008 §3a
- **Depends on** P1-ANC-001, P0-GCP-001
- **Tier** CRITICAL · **Size** M · **Owner** Audit

#### P1-ANC-003 — RFC 3161 TSA integration (external timestamp)
- **As** the Audit squad
  **I want** every hourly chain head submitted to an external RFC 3161 TSA (e.g., DigiCert, FreeTSA)
  **So that** ADR-0008 §3b external attestation is operational.
- **AC**
  - Given the hourly schedule, when triggered, then the chain head is submitted to the TSA and the signed timestamp returned + stored alongside the anchor.
  - Given a TSA outage, when retries exhaust, then the anchor is queued and a P3 alert fires; chain itself is unaffected.
  - Given a stored TSA timestamp, when verified out-of-band, then it validates against the TSA's public certificate.
- **Originating** ADR-0008 §3b
- **Depends on** P1-ANC-002, P0-SEC-002
- **Tier** CRITICAL · **Size** M · **Owner** Audit

#### P1-ANC-004 — Forensic preservation procedure documented + drilled
- **As** the Security Officer
  **I want** the chain-break / anchor-mismatch forensic preservation procedure documented in a runbook + a drill conducted
  **So that** ADR-0008 §5 holds operationally, not just on paper.
- **AC**
  - Given the runbook, when reviewed, then it covers preserve, halt, investigate, resume, document phases with specific commands.
  - Given a drill (deliberate chain-break injection), when run, then the team executes the runbook end-to-end within an exercise window and produces a postmortem.
- **Originating** ADR-0008 §5, R5 D-039
- **Depends on** P1-ANC-001
- **Tier** CRITICAL · **Size** M · **Owner** Security Officer

---

### Epic ONB — Partner Onboarding (First Partner)

#### P1-ONB-001 — Schema registry per partner
- **As** the Ingestion squad
  **I want** a per-partner schema registry persisting the agreed-upon column list, types, and tier assignments
  **So that** schema drift detection (BR-304) has a baseline and partner contracts are machine-readable.
- **AC**
  - Given a partner schema, when registered, then it is queryable, versioned, and immutable on finalize (changes require ADR + new version).
  - Given a feed for a partner, when validated against the registry, then drift detection (P1-DQ-003) uses this as the source of truth.
- **Originating** BR-801, BR-802, BR-304
- **Depends on** P1-ING-002
- **Tier** CRITICAL · **Size** S · **Owner** Ingestion

#### P1-ONB-002 — First-partner onboarding runbook
- **As** the Partnership Operations squad
  **I want** a runbook covering: BAA + DSA execution → IAM + perimeter add → mapping YAML PR → schema registration → first feed → reconciliation
  **So that** Phase 3 scale (5–10 partners) inherits a proven path.
- **AC**
  - Given the runbook, when followed for the first partner, then they go from "agreement signed" to "first feed processed" without ad-hoc engineering.
  - Given the runbook, when reviewed post-execution, then any deviations are documented as runbook updates.
- **Originating** BR-801, R7 E-008
- **Depends on** P1-ONB-001
- **Tier** CRITICAL · **Size** M · **Owner** Partnership Operations

#### P1-ONB-003 — Per-partner monitoring dashboard
- **As** the Platform/SRE squad
  **I want** a per-partner dashboard showing feed-arrival cadence, row counts in/out/quarantined, drift alerts, latency
  **So that** partner health is observable at a glance.
- **AC**
  - Given a partner, when the dashboard renders, then it shows the last 30 days of feeds with status.
  - Given a partner missing a scheduled feed, when the SLA window elapses, then a P2 alert fires (driven by dashboard rules).
- **Originating** AD-021, BR-801
- **Depends on** P1-DQ-005, P0-OBS-006
- **Tier** IMPORTANT · **Size** S · **Owner** Platform/SRE

---

### Epic COM — Compliance Phase 1

#### P1-COM-001 — Notice of Privacy Practices (NPP) authored
- **As** the Privacy Officer
  **I want** the NPP authored, counsel-reviewed, and ready to publish/distribute
  **So that** BR-901 is satisfied before Phase 1 production traffic touches any covered population.
- **AC**
  - Given the NPP, when reviewed, then it covers all HIPAA-required elements (uses, disclosures, member rights, complaint path, effective date).
  - Given counsel sign-off, when stored, then it is in the documentation retention store with version history.
- **Originating** BR-901
- **Depends on** P0-COM-001, P0-COM-006
- **Tier** CRITICAL · **Size** M · **Owner** Privacy Officer

#### P1-COM-002 — First BAA executed
- **As** the Privacy Officer
  **I want** the first partner BAA executed before any production data flows
  **So that** HIPAA covered-entity-to-business-associate compliance holds end-to-end.
- **AC**
  - Given the executed BAA, when stored, then it is in the documentation retention store with both signatures.
  - Given a partner's data flow start, when traced, then the executed BAA precedes the first production transmission.
- **Originating** BR-1101, BRD §"Partner Onboarding"
- **Depends on** P1-COM-001
- **Tier** CRITICAL · **Size** M · **Owner** Privacy Officer

#### P1-COM-003 — Partner Data Sharing Agreement (DSA) executed
- **As** the Privacy Officer + Partnership Operations
  **I want** a DSA executed with the first partner covering data minimization, schedules, transport, contact path, breach notification timing
  **So that** the operational contract is enforceable beyond statutory minima.
- **AC**
  - Given the DSA, when reviewed, then it covers data scope, ETL transport, breach notification timing, partner-side deletion contract (forward-looking to Phase 2/3), partner contact roster.
- **Originating** BR-801, BR-1006
- **Depends on** P1-COM-002
- **Tier** CRITICAL · **Size** M · **Owner** Privacy Officer

#### P1-COM-004 — Subprocessor BAA chain documented
- **As** the Privacy Officer
  **I want** the GCP BAA on file + any sub-subprocessor (e.g., Cloud-side managed services) documented as part of the chain
  **So that** BR-1101 has a complete chain-of-trust artifact.
- **AC**
  - Given the chain document, when reviewed, then it traces from Lore (covered entity boundary) → first partner (BA) → Lore as BA receiving from partner → GCP (sub-BA via BAA).
  - Given counsel sign-off, when stored, then it is in the documentation retention store.
- **Originating** BR-1101
- **Depends on** P1-COM-002
- **Tier** CRITICAL · **Size** M · **Owner** Privacy Officer

#### P1-COM-005 — Privacy Officer Phase 1 production sign-off
- **As** the Privacy Officer
  **I want** a documented Phase 1 production-traffic readiness review with sign-off
  **So that** the ARD Phase 1 exit criterion is closed with named accountability.
- **AC**
  - Given the review, when conducted, then a documented checklist verifies: NPP published, BAA + DSA executed, IAM residency conditions, redaction scanner LIVE, audit chain validator LIVE, latency-distribution test passing.
  - Given the sign-off, when stored, then the Privacy Officer's signature is in the documentation retention store.
- **Originating** ARD §"Phase 1 exit"
- **Depends on** P1-COM-001..004, P1-VER-005, P1-AUD-004, P1-ANC-001
- **Tier** CRITICAL · **Size** S · **Owner** Privacy Officer

---

### Epic UX — UX Phase 1

#### P1-UX-001 — Verification failure UX (joint with engineering)
- **As** the UX squad
  **I want** the Verification API failure path designed: messaging, recovery, escalation-to-human
  **So that** BR-1301 is satisfied with trauma-informed framing for members who were just told NOT_VERIFIED.
- **AC**
  - Given a NOT_VERIFIED outcome surfaced to a member, when reviewed against P0-UX-004 framework, then it passes the trauma-informed checklist.
  - Given the failure UX, when usability-tested with synthetic personas (eligible-but-typo, ineligible-but-recently-eligible, never-eligible), then 80%+ identify the next step they should take.
  - Given the messaging, when scanned, then it carries no internal-state distinction across outcomes (BR-401 / XR-003 collapse holds in UX too).
- **Originating** BR-1301, R6 U-001, ARD §"Phase 1 UX"
- **Depends on** P0-UX-004, P1-VER-001
- **Tier** CRITICAL · **Size** M · **Owner** UX

#### P1-UX-002 — Lockout recovery service blueprint
- **As** the UX squad
  **I want** the lockout recovery flow (post BR-402 third-failure) blueprinted: who the member contacts, identity-proofing required, restoration SLA
  **So that** BR-1308 has a documented service blueprint before Phase 2 lockout build.
- **AC**
  - Given the blueprint, when reviewed, then it covers contact channel, identity-proofing standard, restoration authority, SLA, audit-emission requirements.
  - Given the blueprint, when shared with Operations, then it is buildable into a runbook for Phase 2.
- **Originating** BR-1308, R6 U-001
- **Depends on** P0-UX-004
- **Tier** CRITICAL · **Size** M · **Owner** UX

#### P1-UX-003 — Member rights submission UX (initial)
- **As** the UX squad
  **I want** the initial design for member rights request submission (Right of Access, complaint, authorization revocation)
  **So that** Phase 2 build has a usable contract.
- **AC**
  - Given the design, when reviewed against XR-007 (plain language) + XR-009 (WCAG 2.1 AA), then it passes both gates.
  - Given the design, when usability-tested, then 80%+ of synthetic personas can complete a Right of Access request without help.
- **Originating** BR-901..908, BR-1306, R6 U-068
- **Depends on** P0-UX-004, P0-UX-005
- **Tier** CRITICAL · **Size** M · **Owner** UX

---

### Epic DR — Disaster Recovery (First Drill)

#### P1-DR-001 — DR drill (per `[dr-strategy]` ADR)
- **As** the Platform/SRE squad
  **I want** the first quarterly DR drill executed against the staged environment
  **So that** ARD Phase 1 exit ("quarterly DR drill completed") is closed with evidence.
- **AC**
  - Given the drill plan from P0-ADR-005, when executed, then RTO + RPO targets are met within the drill window.
  - Given the drill, when reviewed, then a postmortem is filed in `docs/retros/` with action items.
- **Originating** ARD §"Phase 1 exit", R5 D-039, P0-ADR-005
- **Depends on** P0-ADR-005, P1-DAT-001
- **Tier** CRITICAL · **Size** L · **Owner** Platform/SRE

---

### Epic TST — End-to-End Test Harness

#### P1-TST-001 — Synthetic data harness (BR-coverage scenarios)
- **As** the QA team
  **I want** a synthetic data generator producing partner feeds that exercise BR-101 deterministic, BR-301..305 DQ paths, BR-202 transitions, BR-401 verification outcomes
  **So that** end-to-end coverage is reproducible across CI runs.
- **AC**
  - Given a fixed seed, when run, then output is byte-identical (reproducible).
  - Given the generator, when run, then it emits a documented scenario manifest (which rows are duplicates, which are quarantine candidates, etc.).
- **Originating** AD-007 (prototype carryover), BR-coverage gates
- **Depends on** —
- **Tier** CRITICAL · **Size** M · **Owner** QA

#### P1-TST-002 — End-to-end CI scenario
- **As** the QA team
  **I want** a nightly CI scenario that runs feed→pipeline→verification end-to-end
  **So that** regressions across context boundaries are caught at CI rather than in staging.
- **AC**
  - Given the scenario, when run nightly, then it asserts: zero plaintext PII in logs, BR-202 transition coverage, BR-401 outcome coverage on representative members.
  - Given a regression introduced (deliberate test), when CI runs, then the scenario fails with a clear diagnosis.
- **Originating** ARD §"Phase 1 exit"
- **Depends on** P1-TST-001, P1-VER-005, P1-AUD-004
- **Tier** CRITICAL · **Size** M · **Owner** QA

#### P1-TST-003 — BR-202 transition matrix exhaustive test
- **As** the Canonical Eligibility squad
  **I want** an exhaustive parameterized test covering all cells in the BR-202 transition matrix
  **So that** ARD Phase 1 exit ("BR-202 transition table fully covered by tests") is unambiguously closed.
- **AC**
  - Given the matrix in BRD §"BR-202", when tests are generated, then 100% of cells (legal + illegal) have at least one test.
  - Given a missing-coverage gap, when CI runs, then a coverage gate flags it.
- **Originating** BR-202, ARD §"Phase 1 exit"
- **Depends on** P1-CAN-002
- **Tier** CRITICAL · **Size** S · **Owner** Canonical Eligibility

---

## Phase 1 cross-track summary

| Track | Critical stories | Important / Supportive |
|-------|------------------|------------------------|
| Engineering | P1-ING-001..006, P1-DQ-001..003, P1-DQ-005, P1-IDR-001..003, P1-CAN-001..005, P1-VER-001..006, P1-TOK-001, P1-AUD-001..003, P1-DAT-001..002, P1-ANC-001..004, P1-ONB-001..002, P1-TST-001..003 | P1-DQ-004, P1-TOK-002, P1-ONB-003 |
| Security | P1-AUD-004, P1-VER-002, P1-VER-005 | (Phase 0 baseline carries) |
| Compliance | P1-COM-001..005 | — |
| UX | P1-UX-001..003 | — |
| Infrastructure | P1-DR-001 | — |

## Phase 1 risk-register linkage

| Risk | Story closing it (or downgrading) |
|------|-----------------------------------|
| RR-001 (BigQuery + Composer + AlloyDB confirmed in production) | P1-DAT-001, P1-CAN-001 (production-validated) |
| RR-002 (partner contract terms) | P1-COM-002, P1-COM-003 |
| RR-003 (existing identity model) | P1-IDR-001 (deterministic match against existing canonical store) |

---

## Out of scope for Phase 1

- Splink probabilistic matching (Phase 2)
- Manual review queue + reviewer interface (Phase 2)
- Brute force progression (Phase 2)
- Deletion workflow + ledger LIVE (Phase 2)
- Member rights workflows (Phase 2)
- Cross-partner identity correlation (Phase 3)
- Penetration testing (Phase 4)
