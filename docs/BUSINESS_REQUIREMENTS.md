# Business Requirements Document: Strategic Data System for Trusted Partner Eligibility and Identity Verification

## Document Purpose

This document specifies the business rules, cross-cutting policies, role taxonomy, configuration parameters, non-functional requirements, and operating assumptions for the Lore Health partner eligibility and identity verification system. It is the input to the Architecture Requirements Document (ARD), which will translate these rules into technology, schema, and infrastructure decisions.

This BRD takes no position on architectural choice. It states what must be true. The ARD states how.

Every business rule in this document is paired with an enforcement mechanism. Rules without an automated mechanism are marked `[ADVISORY]` per the Section 4 Programmatic Enforcement Principle, on the conviction that a requirement enforced only by honor system is incomplete.

## Relationship to Other Documents

- **PROBLEM_BRIEF.md** captured the problem space, stakeholders, and explicit case prompt deliverables. It is the upstream document.
- **TECH_STACK.md** and **RESEARCH_NOTES.md** captured public signal on Lore's likely technology stack. They inform but do not constrain this BRD.
- **CONTEXT.md** identifies the panel interviewers as proxy stakeholders for the deliverable.
- The forthcoming ARD will consume this BRD plus the stack documents and produce a buildable architecture.

## Scope

### In Scope

- Multi-partner eligibility ingestion across heterogeneous file formats
- Identity resolution within and across partner feeds
- Canonical member entity with full SCD2 history
- Identity verification API serving the Lore application's account creation flow
- PII isolation, tokenization, and audit posture sufficient to satisfy HIPAA technical safeguards
- Right-to-deletion workflow consistent with state privacy law obligations
- Operational observability across the pipeline
- Partner onboarding workflow (configuration-driven, not code-driven)

### Out of Scope

- Real-time API ingestion from partners (v1 is file-based)
- Account creation logic itself (eligibility system is a source of truth, not an account owner)
- Member-facing consent management UI
- Finance-side savings attribution logic (the data product is attribution-neutral; finance reads from it)
- Production-hardened infrastructure-as-code, secrets management, and disaster recovery runbooks (referenced in NFRs, not produced)
- Manual review queue staffing and SLA (existence and clear-mechanism only)

## Cross-Cutting Rules

These rules apply across every domain in this BRD. Domain-specific business rules MUST be consistent with them; conflicts are resolved in favor of the cross-cutting rule.

### XR-001: Layered Configurability

**Statement:** Every threshold, timeout, cadence, and policy value referenced in this BRD MUST be a named, documented configuration parameter with a global default. Per-partner override MUST be supported. Per-contract override (where a partner has heterogeneous eligibility populations) and per-load override (for backfills and reruns) MUST be supported where the parameter is meaningfully scoped to those layers. Hardcoded values in production code are a defect.

**Rationale:** Partner contracts vary. Operational realities vary. Anything baked into code becomes a code change for what should be a config change.

**Enforcement:** CI lint rule scanning implementation code for inline numeric or duration literals that match the names of config parameters in the configuration parameter table. Test asserting the override resolution order produces expected values for representative parameter and partner combinations.

### XR-002: No Magic Numbers

**Statement:** Every numeric requirement in this BRD references a named configuration parameter from the configuration parameter table. Implementation code MUST NOT contain inline numeric constants that govern policy behavior.

**Rationale:** Magic numbers are unauditable. Configuration parameters are auditable.

**Enforcement:** CI lint rule. Reviewer checklist item.

### XR-003: Privacy-Preserving Collapse on Public Surfaces

**Statement:** Public-facing API responses, error messages, and external observability surfaces MUST NOT distinguish "the subject exists in the system but X" from "the subject does not exist in the system." Internal richer state is preserved for authenticated admin and audit paths only.

**Rationale:** Distinguishing existence from non-existence on a public surface leaks PHI association to anyone who can call the endpoint, regardless of the response payload's other contents.

**Enforcement:** Integration test asserting that across all combinations of internal state, the public response set is exactly `{VERIFIED, NOT_VERIFIED}` with consistent generic messaging. Static analysis check that internal state enums are not imported by public-facing controllers.

### XR-004: Identity-Scoped Lockouts and Rate Limits

**Statement:** Rate limits and lockouts that protect against brute-force or enumeration MUST be scoped to resolved Lore identity wherever that scope is meaningful. Claim-payload and source-IP scopes are auxiliary controls layered on top.

**Rationale:** Source-IP-only limits are defeated by IP rotation. Claim-payload-only limits are defeated by spelling variation. Identity scope means an attacker burns through one identity at a time and stops, regardless of network topology or input variation.

**Enforcement:** Integration test exercising lockout under IP rotation and spelling-variation attack patterns.

### XR-005: Zero PII or PHI in Logs

**Statement:** Plaintext PII or PHI MUST NOT appear in any log, metric, trace, or alert payload. Resolved identities MUST be logged as their tokenized identifier. Inbound claim payloads MUST be logged as salted hashes only. Forensic reconstruction goes through the vault under break-glass access, which is itself logged.

**Rationale:** Industry standard for healthcare audit logging. Logs holding only tokens and hashes fall outside the PHI scope of HIPAA, materially reducing breach blast radius and the regulatory weight on the logging system.

**Enforcement:** Two gates. (a) CI test asserting that log emissions for representative fixture inputs contain no plaintext patterns matching known PII (SSN regex, email regex, plausible name plus DOB combinations). (b) Scheduled production-safe sampling job scanning live logs for the same patterns and paging on any match.

### XR-006: Irreversibility Separation

**Statement:** Every state-mutating operation MUST be classified as reversible or irreversible. Reversible operations MUST be idempotent. Irreversible operations MUST require explicit operator confirmation, MUST emit the strongest audit trail in the system, and MUST be bounded to the smallest possible set of code paths.

**Rationale:** Vault purges, deletion ledger inserts, and similar operations cannot be undone. They deserve different code paths, different review, and different audit treatment than re-runnable operations.

**Enforcement:** Code-path inventory check. Operations classified `irreversible` MUST live in a designated module with elevated review requirements. Test asserting that irreversible operations require an explicit confirmation token in their invocation signature.

## Role Taxonomy

The system recognizes seven roles. Role assignments are auditable and managed under the same change-control rigor as production code.

| Role | Access | PII Access | Residency Constraint |
| --- | --- | --- | --- |
| Data Engineer | Pipeline operations, configuration | None (tokenized surfaces only) | None |
| Data Ops / SRE | Pipeline operations, on-call escalations | None (tokenized surfaces only) | None |
| Reviewer | Manual review queue | None (tokenized surfaces only) | None |
| PII Handler | Vault detokenization for legitimate purposes | Yes, audited per access | US-resident only |
| Data Owner | Per-partner config, onboarding sign-off | None (tokenized surfaces only) | None |
| Auditor | Read-only access to audit logs | None | None |
| Break-Glass Admin | Time-boxed elevated access for incident response | Yes, time-boxed and audited | US-resident only |

The data engineering function (including offshore staff at Sequelae PH) operates without direct access to plaintext PII or PHI. This is enforced as an architectural decision (BR-505), not as an organizational practice.

## Business Rules

Rules are numbered for citation from the ARD, from tests, and from operational runbooks. Each rule states what must be true. Rationale and enforcement follow.

### Domain: Identity Resolution

#### BR-101: Tiered Match Decision

**Statement:** Identity resolution MUST proceed through four tiers, evaluated in order. A record's match decision is the result of the first tier that produces a definitive outcome.

1. **Tier 1, Deterministic Anchor.** Match on `partner_member_id + DOB + normalized_last_name` within the same partner. Outcome: auto-merge.
2. **Tier 2, Probabilistic High Confidence.** Match score at or above `MATCH_THRESHOLD_HIGH`. Outcome: auto-merge with audit event.
3. **Tier 3, Probabilistic Mid Confidence.** Match score in `[MATCH_THRESHOLD_REVIEW, MATCH_THRESHOLD_HIGH)`. Outcome: queue for human review, no merge until cleared.
4. **Tier 4, Below Threshold.** Match score below `MATCH_THRESHOLD_REVIEW`. Outcome: treat as distinct identity.

**Rationale:** Healthcare PII context is asymmetric on match errors. False positives merging two distinct people are a HIPAA breach; false negatives duplicating one person are revenue leakage and onboarding friction. Tiered policy preserves automation where confidence supports it and routes ambiguity to humans.

**Enforcement:** Unit tests asserting deterministic outcomes on synthetic match payloads at each tier boundary. Integration test asserting that tier evaluation order is preserved under partial input.

#### BR-102: Match Anchor Composition

**Statement:** The deterministic anchor for Tier 1 MUST be `partner_member_id + DOB + normalized_last_name`. SSN MAY be used as a secondary anchor when present and full (not last-4 only) and MUST NOT be used as a sole anchor. Last-4 SSN MAY contribute to probabilistic scoring but never to deterministic merge decisions.

**Rationale:** SSN availability is variable across partners under standard medical records keeping practice (Assumption A1). A deterministic tier dependent on SSN would silently degrade to no-anchor when partners redact. The chosen composition is robust to redaction.

**Enforcement:** Test asserting that records lacking SSN entirely still resolve through Tier 1 when other anchor fields are complete. Test asserting that last-4 SSN does not produce a Tier 1 outcome under any input combination.

#### BR-103: Survivorship on Conflicting Attributes

**Statement:** When matched records carry conflicting attribute values, survivorship rules apply per attribute class:

- **Mutable attributes** (address, phone, email, current name): most-recent-update wins.
- **Identity-defining attributes** (DOB, full SSN): locked after first verified value. Conflicting subsequent values do not overwrite. Conflict triggers a review queue entry of class `IDENTITY_CONFLICT` and suspends the auto-merge that produced the conflict pending resolution.

**Rationale:** Identity-defining attributes are stable across a person's life. A conflicting DOB is a stronger signal of identity mismatch than of typo correction. Mutable attributes routinely change.

**Enforcement:** Test asserting most-recent-update behavior for each mutable attribute. Test asserting that DOB conflict produces a `PENDING_RESOLUTION` state and a review queue entry without overwriting the prior value.

#### BR-104: Match Replay Continuity

**Statement:** When the matching algorithm or its scoring configuration changes, every affected match record MUST carry both the algorithm version and the configuration version active at the time of the decision. Operators MAY initiate full-history match replay at any time. Operators MAY initiate partial match replay only with explicit acknowledgment that a discontinuity will be introduced; the discontinuity MUST be queryable via the version stamps.

**Rationale:** Probabilistic match decisions incorporate evidence from the full historical record. A partial replay with a changed algorithm produces silent discontinuity unless explicitly versioned and acknowledged. Versioning makes the discontinuity visible rather than invisible.

**Enforcement:** Test asserting every match record carries both version stamps. Integration test asserting partial match replay refuses to execute without a confirmation token referencing the version delta.

#### BR-105: Manual Review Queue Existence

**Statement:** A persistent, queryable manual review queue MUST exist. Items entering the queue MUST carry the tier evaluation result, the candidate match score, the records under consideration (referenced by tokenized identifier), and the queue entry timestamp. A clear mechanism for resolving queue items MUST exist. Reviewer staffing, queue SLA, and routing rules are deferred from v1.

**Rationale:** The queue is a structural component of the match policy. Its operational shape is deferred but its existence is not.

**Enforcement:** Test asserting that Tier 3 outcomes produce queue entries with the required fields. Test asserting that queue items are addressable by stable identifier.

### Domain: Eligibility Lifecycle

#### BR-201: Canonical Member State Machine

**Statement:** Every canonical member record MUST occupy exactly one state at any point in time, drawn from the following set:

- `PENDING_RESOLUTION`: created from a partner record but blocked on manual identity review
- `ELIGIBLE_ACTIVE`: present on at least one current partner roster
- `ELIGIBLE_GRACE`: dropped from all partner rosters within the last `GRACE_PERIOD_DAYS`, still account-eligible
- `INELIGIBLE`: past grace period, account locked or read-only
- `DELETED`: right-to-deletion executed, PII vault purged, SCD2 history retained with PII fields nulled

**Rationale:** Account creation, verification, and downstream consumers all need an unambiguous current state. A state machine makes transitions auditable and verifiable.

**Enforcement:** Database constraint asserting `state` is one of the enumerated values. Test asserting every transition between states is covered by a defined transition rule (BR-202).

#### BR-202: State Transition Rules

**Statement:** Allowed state transitions MUST be exactly:

- `(none)` → `PENDING_RESOLUTION`: ingested record requires review
- `(none)` → `ELIGIBLE_ACTIVE`: ingested record clears Tier 1 or Tier 2 match and resolves to a new identity
- `PENDING_RESOLUTION` → `ELIGIBLE_ACTIVE`: review cleared, identity confirmed
- `PENDING_RESOLUTION` → `DELETED`: review cleared as distinct identity that requested deletion (rare path)
- `ELIGIBLE_ACTIVE` → `ELIGIBLE_GRACE`: dropped from all current partner rosters
- `ELIGIBLE_GRACE` → `ELIGIBLE_ACTIVE`: re-appears on any partner roster within grace period
- `ELIGIBLE_GRACE` → `INELIGIBLE`: grace period elapsed without re-enrollment
- `INELIGIBLE` → `ELIGIBLE_ACTIVE`: re-appears on any partner roster (re-enrollment after gap, identity preserved)
- Any state → `DELETED`: right-to-deletion executed

All other transitions are forbidden.

**Rationale:** Explicit transition table prevents implicit state drift from ad-hoc updates.

**Enforcement:** Unit test enumerating every state pair and asserting allowed/forbidden status matches this rule.

#### BR-203: Grace Period

**Statement:** The grace period from "last seen on any roster" to `INELIGIBLE` MUST default to `GRACE_PERIOD_DAYS` (default 30). This parameter MUST support per-partner override and per-contract override.

**Rationale:** Care continuity argues for a non-zero grace; partner contracts may dictate specific values; some partner populations within a single partner may have different terms.

**Enforcement:** Test asserting transition timing matches the resolved (global, partner, contract) parameter value for representative configurations.

#### BR-204: Re-Enrollment After Gap

**Statement:** When a previously-known member returns to any partner roster, the canonical identity MUST be preserved. The member transitions from `ELIGIBLE_GRACE` or `INELIGIBLE` back to `ELIGIBLE_ACTIVE`. A `REENROLLMENT` audit event MUST be emitted, recording the gap duration and the partner that reintroduced the member.

**Rationale:** Identity continuity across enrollment gaps is essential for clinical context and for accurate longitudinal savings calculation. Creating a new identity on re-enrollment would fragment the longitudinal record.

**Enforcement:** Test asserting that an ingestion of a previously-deleted-then-returned roster member resolves to the original canonical identity (subject to BR-703 deletion suppression). Test asserting `REENROLLMENT` audit event emission.

#### BR-205: Attribution Neutrality

**Statement:** The canonical member record MUST hold a one-to-many relationship to `partner_enrollment` rows. Each enrollment row carries its own effective period, partner identifier, and partner-supplied attributes. Simultaneous enrollments across multiple partners MUST be recorded faithfully without the data product choosing among them. Attribution rules (savings credit, primary partner) are out of scope for the data product and are read by downstream consumers from this neutral shape.

**Rationale:** Attribution rules vary by partner contract and may change over time. Embedding an attribution rule in the data product would couple the data product to finance logic and require rebuilds when finance rules change. Neutral storage decouples them.

**Enforcement:** Schema constraint enforcing the one-to-many shape. Test asserting that two simultaneous enrollments produce two retained enrollment rows with no canonical-record-level "primary partner" field.

#### BR-206: Lifecycle Audit

**Statement:** Every state transition MUST emit a `STATE_TRANSITION` audit event recording the prior state, the new state, the trigger (ingestion, time-based, deletion request, review resolution), the resolved canonical identity in tokenized form, and the timestamp.

**Enforcement:** Test asserting audit event emission on each transition class. Audit event schema validation.

### Domain: Data Quality

#### BR-301: Field Criticality Tiers

**Statement:** Every canonical eligibility field MUST be assigned to exactly one of three tiers:

- **Required:** Record is rejected if missing or invalid.
- **Verification:** Record is accepted but flagged as not-verifiable until the field is populated and valid.
- **Enrichment:** Absence is logged but never blocks acceptance.

The Required tier MUST be seeded from the X12 834 Required (R) field set as a baseline. Lore-specific additions to the Required tier MUST be documented per partner.

**Rationale:** Industry-standard 834 R-set is a defensible baseline. Three tiers separate "this record is unusable" from "this record needs more before it counts" from "this is nice to have."

**Enforcement:** Configuration validation asserting every canonical field carries a tier assignment. Test asserting tier-correct rejection and acceptance behavior.

#### BR-302: Record-Level Quarantine

**Statement:** Records failing Required-tier validation MUST be quarantined individually. The remainder of the feed MUST proceed to processing. Quarantined records MUST be retained for forensic replay and partner-side correction.

**Enforcement:** Test asserting a single bad record does not block its feed. Test asserting quarantined records are addressable for replay.

#### BR-303: Feed-Level Quarantine Threshold

**Statement:** When the per-feed record rejection rate exceeds `FEED_QUARANTINE_THRESHOLD_PCT` (default 5%), the entire feed MUST be quarantined and a human MUST be paged. This parameter MUST support per-partner and per-load override.

**Rationale:** A bad single record is a partner data hygiene issue. A high rejection rate is a structural problem (schema drift, encoding error, wrong file) that cannot be safely processed record-by-record.

**Enforcement:** Test asserting the feed-quarantine trigger fires at the threshold boundary for representative configurations. Integration test asserting human-paging path is exercised.

#### BR-304: Schema Drift Handling

**Statement:** Additive schema changes (new columns) MUST be auto-accepted with a `SCHEMA_DRIFT_ADDITIVE` notification logged. Subtractive (column removed) and type-narrowing (type changed in a way that loses information) schema changes MUST quarantine the feed and page a human.

**Rationale:** Additive changes are routine and rarely indicate failure; alerting on every additive change creates fatigue and degrades signal on changes that matter. Subtractive and narrowing changes silently break downstream contracts.

**Enforcement:** Test asserting additive change produces accepted-with-notification outcome. Test asserting subtractive and narrowing changes produce quarantine and page.

#### BR-305: Data Profiling Baseline

**Statement:** During partner onboarding (BR-801), an initial data profile MUST be computed from the sample feed: per-field null rate, per-field cardinality, per-field value distribution, and feed-level row count. Subsequent feeds MUST be compared against this baseline. Distribution drift exceeding `PROFILE_DRIFT_THRESHOLD` MUST emit a `PROFILE_DRIFT` event and route the feed for review without auto-quarantine.

**Rationale:** Profile drift catches the silent failure modes that schema-conformant feeds can still exhibit (a field that was 5% null is now 80% null; a state code field that had 50 distinct values now has 3).

**Enforcement:** Test asserting profile capture during onboarding. Test asserting drift detection fires at the threshold.

#### BR-306: Quality SLA Gating Downstream Publication

**Statement:** Feeds that fail Required-tier or feed-threshold validation MUST NOT publish to the curated layer. Quarantined feeds remain accessible only to data engineering roles for diagnosis.

**Rationale:** The curated layer is the source of truth for verification and account creation. Bad data must not reach it.

**Enforcement:** Integration test asserting that quarantined feeds do not produce curated-layer effects.

### Domain: Identity Verification API

#### BR-401: External State Set

**Statement:** The verification API's external response set MUST be exactly `{VERIFIED, NOT_VERIFIED}` with consistent generic messaging. Internal richer states (`NOT_FOUND`, `INELIGIBLE`, `PENDING_RESOLUTION`, `AMBIGUOUS`) MUST be preserved for logging and authenticated admin paths only.

**Rationale:** Privacy-preserving collapse per XR-003. Distinguishing "you exist but ineligible" from "you don't exist" leaks PHI association to anyone who can call the endpoint.

**Enforcement:** Per XR-003 enforcement. Integration test enumerating all internal state combinations and asserting external response collapse.

#### BR-402: Progressive Friction on Failed Verification

**Statement:** Verification failure handling MUST follow a three-tier progression scoped to resolved Lore identity within `BRUTE_FORCE_WINDOW_HOURS` (default 24):

1. **First failure:** Normal retry, no friction.
2. **Second failure:** Friction challenge applied (CAPTCHA-equivalent or step-up). Increased response latency. Additional logging.
3. **Third failure:** Identity locked. Self-service recovery is not available; recovery is out-of-band only.

Per-claim-payload rate limits MUST also be enforced as auxiliary controls per XR-004. All probes MUST be logged regardless of outcome. All thresholds MUST be configurable.

**Rationale:** Typo recovery is the dominant first-failure case; adding friction there harms legitimate users. Subsequent failures within a short window are a stronger attack signal.

**Enforcement:** Integration test exercising the three-tier progression under same-identity attack patterns and under spelling-variation attack patterns.

#### BR-403: Failed Verification Fallback

**Statement:** When a user fails verification through the self-service path, the response MUST display a generic message and a contact-support path. v1 MUST NOT provide a deferred-account state or in-system manual-review escalation from the user-facing surface.

**Rationale:** Self-service-only is a defensible v1 scope. Deferred-account and in-app manual review are roadmap items requiring additional UX, fraud, and clinical-trust analysis.

**Enforcement:** Test asserting public response on failure does not reveal internal path options or queue identifiers.

#### BR-404: Verification Latency

**Statement:** Verification API responses MUST achieve p95 latency at or below `VERIFICATION_P95_LATENCY_MS` (default 200 ms) under nominal load.

**Rationale:** The API is in the critical path of account creation. User experience expectations and timeout budgets in the calling surface set the ceiling.

**Enforcement:** Continuous performance monitoring with alerting on threshold breach. Load test gate in pre-release pipeline.

#### BR-405: Verification Availability

**Statement:** The verification API MUST achieve `VERIFICATION_AVAILABILITY_PCT` (default 99.9%) measured rolling-30-day. If account creation is hard-blocked on the API, the parameter SHOULD be raised to 99.95%.

**Enforcement:** Continuous availability monitoring with alerting and quarterly review.

### Domain: Audit and Compliance

#### BR-501: Audit Event Classes

**Statement:** The system MUST emit audit events for all of the following event classes, at minimum:

- PII access (read)
- PII modification
- Verification attempt (success and failure)
- Identity merge (auto and manual)
- Eligibility state transition (per BR-206)
- Manual review action (queue entry, resolution, override)
- Configuration change
- DQ threshold breach
- Schema drift event
- Deletion request
- Deletion execution
- Break-glass access grant and revocation

**Enforcement:** Test asserting event emission for each class under triggering conditions.

#### BR-502: Audit Log Content Constraints

**Statement:** Audit logs MUST NOT contain plaintext PII or PHI per XR-005. Resolved identities MUST be referenced by tokenized identifier. Inbound claim payloads MUST be referenced by salted hash. Audit events MUST contain sufficient metadata to reconstruct the relevant action: actor, action class, target (tokenized), timestamp, outcome, and trigger.

**Enforcement:** Per XR-005 enforcement. Audit event schema validation. Forensic-replay test asserting that incident reconstruction is achievable from logged metadata plus authenticated vault access.

#### BR-503: Audit Retention

**Statement:** Retention MUST be at minimum:

- PII access and modification events: `AUDIT_RETENTION_PII_YEARS` (default 7)
- Identity merge events and deletion events: indefinite
- Operational and DQ events: `AUDIT_RETENTION_OPS_YEARS` (default 2)

The PII retention default exceeds the HIPAA documentation floor of 6 years by one year of buffer.

**Enforcement:** Storage lifecycle policy verification. Test asserting that retention rules apply to representative event types.

#### BR-504: Audit Log Integrity

**Statement:** Audit logs MUST be append-only by access control. High-criticality event classes (PII access, identity merge, deletion) MUST be additionally protected by hash-chained integrity such that tampering is detectable. Stronger guarantees (WORM storage, separate cloud account) MAY be added as a hardening step but are not required for v1.

**Enforcement:** Access control test asserting that no role permits update or delete on the audit log table or stream. Hash-chain validation job runs continuously and pages on chain break.

#### BR-505: Audit Log Read Access

**Statement:** The `Auditor` role MUST have read-only access to audit logs. PII Handler, Data Engineer, Data Ops, Reviewer, and Data Owner roles MUST NOT have audit log read access by default. Reads of the audit log MUST themselves be logged. Temporary grants for incident response MUST be time-boxed and logged.

**Rationale:** The auditor role enables compliance to answer audit questions without pulling in engineering and without granting engineering visibility into who was investigated for what.

**Enforcement:** Access control test asserting role-correct access boundaries. Test asserting that audit log reads emit a `META_AUDIT_READ` event.

#### BR-506: Sequelae PH PII Boundary

**Statement:** Personnel based at Sequelae PH (Lore's Philippines engineering arm) MUST NOT have access to plaintext PII or PHI. Their access is limited to tokenized analytical surfaces and operational tooling that does not surface plaintext PII. The PII Handler and Break-Glass Admin roles MUST be restricted to US-resident personnel.

**Rationale:** Cross-border data residency is a structural concern given the offshore engineering footprint. The boundary is enforced architecturally rather than as policy.

**Enforcement:** IAM configuration audit. Test asserting that representative offshore-mapped principals cannot detokenize. BAA chain documentation includes Sequelae PH as a subprocessor with this scope explicitly stated. `[ADVISORY]` for the BAA documentation portion.

### Domain: Ingestion Lifecycle

#### BR-601: Within-Feed Deduplication

**Statement:** When a single partner feed contains the same `partner_member_id` more than once, the last occurrence in file order MUST win. All occurrences MUST be retained in the raw landing zone for forensic replay. A `WITHIN_FEED_DEDUP` event MUST be logged with the count of duplicate occurrences resolved.

**Enforcement:** Test asserting last-record-wins behavior. Test asserting raw landing zone retains all original records.

#### BR-602: Snapshot-Diff Comparison

**Statement:** Each accepted partner feed MUST be diffed against the most recent prior accepted feed from the same partner to derive adds, changes, and removes. The diff is authoritative for downstream effects regardless of the prior snapshot's age.

**Enforcement:** Test asserting diff correctness across representative scenarios (clean day, partner skipped delivery, schema-drifted feed).

#### BR-603: Stale Baseline Warning

**Statement:** When the gap between the prior accepted snapshot and the current snapshot exceeds the partner's expected cadence (per `PARTNER_CADENCE_DAYS` per-partner config), a `STALE_BASELINE` warning MUST be emitted. The diff is still processed; the warning flags that significant change may have occurred in the gap.

**Enforcement:** Test asserting warning emission when gap exceeds cadence.

#### BR-604: Late-Arriving File Ordering

**Statement:** Files MUST be processed in file-effective-date order, not arrival order. When a file arrives whose effective date precedes the most recent processed file, the SCD2 history MUST be rebuilt to reflect the correct sequence. Reprocessing of subsequent files MAY be required and is a first-class operation, not an emergency.

**Rationale:** Partners are operationally messy. Treating late arrivals as exceptions creates emergency reruns and silent inconsistency. Treating them as routine creates a system that absorbs reality.

**Enforcement:** Test asserting that an out-of-order arrival rebuilds SCD2 history correctly. Idempotency test asserting that reprocessing produces stable results.

#### BR-605: Reconciliation

**Statement:** The system MUST automatically reconcile its derived current member count per partner against the partner's reported count on a configurable cadence (`RECONCILIATION_CADENCE_DAYS`, default 30). Variance exceeding `RECONCILIATION_VARIANCE_THRESHOLD_PCT` (default 0.5%) MUST open an investigation ticket and emit a `RECONCILIATION_VARIANCE` event. Absence of a reconciliation reading MUST NOT be treated as success; missing readings page operations.

**Rationale:** Silent drift between Lore's view and the partner's view is a high-cost defect. Periodic reconciliation catches it.

**Enforcement:** Scheduled job presence verification. Test asserting variance trigger fires at threshold. Test asserting missing-reading detection.

#### BR-606: Replay Capability

**Statement:** Full replay from the raw landing zone MUST be available at all times. Replay MUST be operator-initiated and never automatic. Replay MUST produce a parallel SCD2 chain that is swapped in atomically once verified; the prior chain MUST be retained for the audit retention window. Operators MUST be able to specify a start point for data replay (schema mapping, validation, SCD2 history derivation). Match replay defaults to full-history; partial match replay requires explicit confirmation per BR-104.

**Enforcement:** Integration test exercising full and partial replay paths. Test asserting atomic swap behavior. Test asserting prior chain retention.

#### BR-607: Replay Scope Preview

**Statement:** Before any replay executes, the system MUST present the operator with a scope preview: the number of partners, members, and SCD2 rows to be affected; expected duration estimate; storage delta estimate. Execution MUST require explicit confirmation after preview.

**Rationale:** Per XR-006, irreversibility separation argues against accidental large-scope reprocessing. The preview catches operator error before it becomes operator regret.

**Enforcement:** Integration test asserting that replay invocation without confirmation token fails. Test asserting preview contents match the executed scope.

### Domain: Right-to-Deletion

#### BR-701: Deletion Request SLA

**Statement:** Verified deletion requests MUST be executed within `DELETION_SLA_DAYS` (default 30) of verification. Verification of requester identity is a precondition and is not counted against the SLA clock.

**Rationale:** GDPR requires 30 days. CCPA requires 45 days. The default satisfies both with margin. Per the layering pattern, the parameter is configurable should specific state law shift.

**Enforcement:** Test asserting that pending deletion requests past the SLA emit a `DELETION_SLA_BREACH` page event. Compliance dashboard asserting current pending-deletion ages.

#### BR-702: Deletion Scope and Mechanics

**Statement:** Deletion execution MUST: (a) irreversibly purge the canonical member's plaintext PII from the vault, (b) tombstone the canonical member record with PII fields nulled while retaining the SCD2 history skeleton for audit, (c) preserve all audit log entries referencing the deleted identity by tokenized identifier (the token remains; the resolution from token to PII does not), (d) emit a `DELETION_EXECUTED` event. Partner-side data is outside Lore's reach; the partner MUST be notified through the BAA-defined channel but cannot be compelled by Lore's system.

**Enforcement:** Test asserting that detokenization attempts against a deleted identity fail with a `TOMBSTONED` outcome. Test asserting that audit log queries by token still resolve. Test asserting partner notification path is exercised.

#### BR-703: Re-Introduction Suppression

**Statement:** A `deletion_ledger` MUST record a one-way hash of every deleted identity's match-relevant attributes (normalized last name, DOB, partner_member_id, and any other Tier 1 anchor components). The ledger MUST hold no recoverable PII. On every subsequent ingestion, candidate records MUST be hashed against the ledger. Hash matches MUST be auto-quarantined to a `SUPPRESSED_DELETED` state and MUST NOT be published to the curated layer. Re-introduction is permitted only through an explicit operator override that emits a `DELETION_OVERRIDE` audit event.

**Rationale:** Without suppression, partner re-snapshots silently re-introduce deleted identities, rendering deletion meaningless. The ledger is the standard pattern; one-way hashing prevents the ledger itself from becoming a PII surface.

**Enforcement:** Test asserting that ingestion of a previously-deleted identity routes to `SUPPRESSED_DELETED`. Test asserting that the ledger contains no recoverable PII through any vault-side query.

#### BR-704: Deletion Auditability

**Statement:** Deletion request, verification, execution, and any override MUST each emit distinct audit events. These events MUST be retained indefinitely per BR-503.

**Enforcement:** Test asserting that the deletion lifecycle produces the expected audit event sequence.

### Domain: Partner Onboarding

#### BR-801: Onboarding Gate Sequence

**Statement:** A partner MUST NOT go live in production until all of the following gates are cleared:

1. Partner-to-canonical schema mapping is documented and reviewed.
2. A representative sample feed is processed end-to-end through the quarantine path.
3. DQ baselines (BR-305) are established from the sample feed.
4. The Business Associate Agreement is executed and recorded.
5. Partner-specific configuration overrides (cadence, grace period, thresholds) are reviewed and signed off by a Data Owner.

**Rationale:** Onboarding errors compound. Each gate addresses a known historical failure mode in eligibility ingestion programs.

**Enforcement:** `[ADVISORY]` for the human-review portions (gates 1 and 5). Programmatic gate (gates 2, 3, 4): partner-live state in the partner registry MUST require artifacts referencing all gate completions; the registry rejects activation without them.

#### BR-802: Configuration-Driven Onboarding

**Statement:** Onboarding a new partner MUST be achievable through configuration and schema mapping alone; it MUST NOT require new deployable code. New code may be required for partners introducing structurally novel formats; these MUST be developed as reusable format adapters, not partner-specific code paths.

**Rationale:** Code-per-partner produces a maintenance liability that grows linearly with partner count. The system is designed to absorb 10x partner growth (NFR) without architectural change; this rule is the operational expression of that NFR.

**Enforcement:** `[ADVISORY]` enforcement: code review checklist item flagging partner-specific code paths. Backed by a static-analysis check scanning for partner identifiers as conditional branch keys.

## Configuration Parameters

Every parameter named in this BRD is listed here with default value, scope of override layers, and the business rules that reference it. New parameters introduced through future amendments MUST be added to this table.

| Parameter | Default | Override Layers | Referenced By |
| --- | --- | --- | --- |
| `MATCH_THRESHOLD_HIGH` | TBD by tuning on synthetic data | global, per-partner | BR-101 |
| `MATCH_THRESHOLD_REVIEW` | TBD by tuning on synthetic data | global, per-partner | BR-101 |
| `GRACE_PERIOD_DAYS` | 30 | global, per-partner, per-contract | BR-203 |
| `FEED_QUARANTINE_THRESHOLD_PCT` | 5 | global, per-partner, per-load | BR-303 |
| `PROFILE_DRIFT_THRESHOLD` | TBD by per-field tuning | global, per-partner, per-field | BR-305 |
| `BRUTE_FORCE_WINDOW_HOURS` | 24 | global | BR-402 |
| `VERIFICATION_P95_LATENCY_MS` | 200 | global | BR-404 |
| `VERIFICATION_AVAILABILITY_PCT` | 99.9 | global | BR-405 |
| `AUDIT_RETENTION_PII_YEARS` | 7 | global | BR-503 |
| `AUDIT_RETENTION_OPS_YEARS` | 2 | global | BR-503 |
| `PARTNER_CADENCE_DAYS` | (no global default; per-partner required) | per-partner | BR-603 |
| `RECONCILIATION_CADENCE_DAYS` | 30 | global, per-partner | BR-605 |
| `RECONCILIATION_VARIANCE_THRESHOLD_PCT` | 0.5 | global, per-partner | BR-605 |
| `DELETION_SLA_DAYS` | 30 | global | BR-701 |

Parameters marked TBD MUST be tuned during the prototype phase against synthetic and partner-supplied sample data, with the tuned defaults captured in this table before production cutover.

## Non-Functional Requirements

### Latency

- Verification API: p95 at or below 200 ms (BR-404)
- Bulk load per partner: hours to single-digit days for onboarding, scaled by volume; no hard SLA at the bulk-load level

### Availability

- Verification API: 99.9% baseline; 99.95% if account creation is hard-blocked on it (BR-405)

### Freshness

- Incremental feeds: same-day processing once received; daily delivery cadence as the baseline, configurable per partner

### Durability

- Zero data loss tolerance for partner-supplied source files
- Full replay capability from raw landing zone at all times (BR-606)

### Scalability

- Partner count: design absorbs 10x current partner count without architectural change (BR-802 supports this operationally)
- Volume per partner: thousands to millions of members per partner
- Verification call volume: scales with user growth and authentication activity

### Security and Privacy

- Encryption in transit and at rest as a baseline
- Field-level encryption or tokenization for PII (XR-005 governs log-side; vault-side handled in ARD)
- Role-based access control with explicit residency constraints (Role Taxonomy, BR-506)
- Audit trail on every PII access (BR-501)
- US-only PII data residency, with offshore engineering access mediated through tokenized surfaces (BR-506)
- Right-to-deletion handling consistent with state law obligations (BR-701 through BR-704)
- Documented BAA chain including Sequelae PH as a subprocessor

### Operational Efficiency

- Partner onboarding via configuration, not code (BR-802)
- Schema drift detection with alerting before bad data lands in curated layers (BR-304)
- Idempotent reprocessing for any pipeline stage (BR-606)

## Assumption Ledger

Every assumption made in this BRD is recorded here. Each will be revisited as the prototype is built and as partner-side facts surface.

| ID | Assumption | Source |
| --- | --- | --- |
| A1 | SSN availability across partners is variable under standard medical records keeping. SSN is a secondary anchor, never sole. | Conversation |
| A2 | Manual review queue exists with a clear-mechanism for resolution; staffing and SLA are deferred from v1. | Conversation |
| A3 | Grace period defaults to 30 days, configurable across global, per-partner, and per-contract layers. | Conversation |
| A4 | Data product is attribution-neutral. Savings attribution is a downstream finance concern. | Conversation |
| A5 | DQ field tiers are seeded from the X12 834 R-set as baseline; partner-specific additions documented. | Conversation |
| A6 | Record-level quarantine with feed-level threshold trigger; default 5%, configurable. | Conversation |
| A7 | Schema drift handling: additive accepted with notification; subtractive or narrowing quarantines and pages. | Conversation |
| A8 | Verification API external state set is `{VERIFIED, NOT_VERIFIED}`. | Conversation |
| A9 | Brute force handling is three-tier progressive within 24h: normal, friction, lockout. | Conversation |
| A10 | Failed verification fallback is contact-support only for v1. | Conversation |
| A11 | Zero plaintext PII or PHI in logs; salted hashes and tokens only; redaction-verification scan in place. | Conversation, web research |
| A12 | Within-feed deduplication: last record in file order wins; both retained. | Conversation |
| A13 | Snapshot-diff baseline: most recent accepted snapshot regardless of age, with `STALE_BASELINE` warning beyond cadence. | Conversation |
| A14 | Late-arriving files processed in file-effective-date order; SCD2 rebuilt. | Conversation |
| A15 | Reconciliation cadence default 30 days; variance threshold 0.5%; both configurable. | Conversation |
| A16 | Reprocessing is operator-initiated; full replay available; data replay supports start-point selection; match replay defaults to full-history with explicit override. | Conversation |
| A17 | Deletion SLA is 30 days from verified request. | Conversation, regulatory analysis |
| A18 | Deletion scope is Lore's own copy; partners notified via BAA-defined channel but not system-compelled. | Conversation |
| A19 | Re-introduction suppression via one-way hashed deletion ledger. | Conversation |
| A20 | Partner onboarding requires schema mapping, sample feed processing, DQ baseline, executed BAA, and Data Owner sign-off before going live. | Conversation |
| A21 | Seven-role taxonomy: Data Engineer, Data Ops/SRE, Reviewer, PII Handler, Data Owner, Auditor, Break-Glass Admin. | Conversation |
| A22 | Partner data delivery is file-based (SFTP or equivalent). Real-time partner-side APIs are out of scope for v1. | Brief |
| A23 | Partner feeds are full-roster snapshots, not change feeds. Diff-based CDC is the implementation pattern. | Brief |
| A24 | Daily delivery cadence is the baseline; weekly and monthly partners must be absorbable. | Brief |
| A25 | The Lore application owns user account state. The eligibility system is a source of truth that account creation reads from; it does not create application accounts directly. | Brief |
| A26 | System is greenfield for v1. Migration from a prior system is not in scope. | Brief |
| A27 | Single primary US cloud region, multi-AZ, no multi-region active-active for v1. | Brief |
| A28 | AI/ML capabilities are in scope where they provide explainability. Black-box ML for identity match decisions is not appropriate. | Brief |

## Open Questions

These remain open and are recorded so that the assumption-driven defaults above can be revisited when answers surface.

1. Existing data platform stack at Lore (cloud, warehouse, orchestration). The TECH_STACK.md document captures public signal; first-party confirmation will tighten ARD decisions.
2. Current partner count and projected growth at 12 and 24 months.
3. Existing Lore application identity model and account record contract.
4. Existing partner contracts that may constrain data handling beyond statutory requirements.
5. Existing identity resolution approach within Lore, if any.
6. Existing HITRUST or SOC 2 attestation status.
7. Initial onboarding wave: which partners, what formats.
8. Match threshold defaults: requires tuning against synthetic data with known ground truth before parameter values can be set.

## Enforcement Mechanism Inventory

This table maps every cross-cutting and business rule to its enforcement mechanism. The table MUST be updated when rules are added or amended.

| Rule | Mechanism |
| --- | --- |
| XR-001 | CI lint for inline literals matching config names; resolution-order test |
| XR-002 | CI lint; reviewer checklist |
| XR-003 | Integration test enumerating internal-to-external state collapse; static analysis preventing internal enum import in public controllers |
| XR-004 | Integration test exercising attack patterns under IP rotation and spelling variation |
| XR-005 | CI fixture redaction test; scheduled production-safe sampling job |
| XR-006 | Code-path inventory; confirmation-token signature requirement; module isolation |
| BR-101 | Per-tier unit tests at boundaries; tier ordering integration test |
| BR-102 | Anchor-composition tests with and without SSN |
| BR-103 | Per-attribute survivorship tests; DOB-conflict review-routing test |
| BR-104 | Version-stamp presence test; partial-replay confirmation gate test |
| BR-105 | Tier 3 queue-entry test; queue addressability test |
| BR-201 | DB constraint; transition-coverage test |
| BR-202 | Exhaustive transition-pair test |
| BR-203 | Override-resolution test |
| BR-204 | Re-enrollment continuity test; `REENROLLMENT` event test |
| BR-205 | Schema constraint; multi-enrollment retention test |
| BR-206 | Per-transition-class event emission test |
| BR-301 | Tier-assignment validation; tier-correct rejection test |
| BR-302 | Single-bad-record isolation test; quarantine addressability test |
| BR-303 | Boundary test on threshold; integration test on pager path |
| BR-304 | Additive accept test; subtractive and narrowing quarantine test |
| BR-305 | Profile capture test; drift detection test |
| BR-306 | Quarantined-feed-no-curated-effect integration test |
| BR-401 | (See XR-003) |
| BR-402 | Three-tier progression integration test |
| BR-403 | Public-failure-response test |
| BR-404 | Continuous performance monitoring; pre-release load test |
| BR-405 | Continuous availability monitoring |
| BR-501 | Per-event-class emission test |
| BR-502 | (See XR-005); event schema validation; forensic-replay test |
| BR-503 | Storage lifecycle policy verification; per-event-type retention test |
| BR-504 | ACL test; hash-chain validation job |
| BR-505 | Role-correct access test; `META_AUDIT_READ` event test |
| BR-506 | IAM audit; offshore-principal detokenization test; `[ADVISORY]` BAA documentation |
| BR-601 | Last-record-wins test; raw-landing retention test |
| BR-602 | Diff correctness test |
| BR-603 | Stale-baseline warning test |
| BR-604 | Out-of-order rebuild test; idempotency test |
| BR-605 | Scheduled-job verification; variance-trigger test; missing-reading detection test |
| BR-606 | Replay path integration test; atomic-swap test; prior-chain retention test |
| BR-607 | Confirmation-token gate test; preview-content test |
| BR-701 | SLA breach pager test; compliance dashboard |
| BR-702 | Detokenization-after-delete test; audit-log token-resolution test; partner notification path test |
| BR-703 | Suppression routing test; ledger-no-recoverable-PII test |
| BR-704 | Deletion lifecycle event-sequence test |
| BR-801 | Partner registry activation gate (programmatic for gates 2/3/4); `[ADVISORY]` for gates 1 and 5 |
| BR-802 | Code review checklist; static-analysis check on partner-conditional branches; `[ADVISORY]` |

## Closing Note

This document is the contract between the problem space and the architecture. Any change to a business rule, cross-cutting rule, or configuration parameter is a contract change and MUST be reflected in updated tests before implementation proceeds.
