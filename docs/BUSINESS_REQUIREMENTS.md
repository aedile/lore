# Business Requirements Document: Strategic Data System for Trusted Partner Eligibility and Identity Verification

## Document Purpose

This document specifies the business rules, cross-cutting policies, role taxonomy, configuration parameters, non-functional requirements, and operating assumptions for the Lore Health partner eligibility and identity verification system. It is the input to the Architecture Requirements Document (ARD), which translates these rules into technology, schema, and infrastructure decisions.

This BRD takes no position on architectural choice. It states what must be true. The ARD states how.

Every business rule pairs with an enforcement mechanism. Rules without an automated mechanism are marked `[ADVISORY]` per the Programmatic Enforcement Principle (Section 4 of CONSTITUTION). The honest application of `[ADVISORY]` matters — claiming programmatic enforcement that does not exist is itself a defect.

This BRD has been synthesized from eight review rounds (principal architect, chief programmer, principal security, compliance/legal, principal DevOps, principal UI/UX, executive, project manager) covering 522 raw findings. Findings are referenced by ID throughout (R1 F-NNN, R3 S-NNN, R4 L-NNN, R5 D-NNN, R6 U-NNN, R7 E-NNN, R8 P-NNN). The `docs/reviews/` directory retains the diagnostic audit trail.

## Strategic Context

This eligibility platform serves Lore Health's Medicare Accountable Care Organization (ACO) operations. It is the data foundation for member identity verification at account creation and for the savings-attribution analytics downstream of that verification. Strategic intent and corporate-level positioning live in upstream strategy documents in another repository; the BRD is the technical expression of those intents.

Strategic outcomes this platform serves (high-level; not exhaustive):

- **Member trust at first interaction.** Verification UX shapes member acquisition; trust failures during onboarding propagate to lifetime value.
- **Partner contract retention.** Eligibility data quality, SLA compliance, and audit defensibility affect partner renewal and acquisition.
- **HIPAA / state-law defensibility.** Regulatory enforcement, attestation, and litigation posture are bounded by the controls expressed here.
- **Operational efficiency at scale.** Configuration-driven partner onboarding reduces marginal cost per partner, supporting growth-with-margin.
- **Foundation for downstream products.** Clinical product, savings-attribution analytics, and ML feature engineering build on this data foundation.

References to upstream strategic documents (in the strategy repository, not duplicated here):
- Corporate strategy and 3-year roadmap
- OKR catalog and quarterly objectives
- Board-approved business plan
- Risk acceptance log (executive level)
- Partnership economics and pricing

## Relationship to Other Documents

- **PROBLEM_BRIEF.md** captured the problem space, stakeholders, and explicit case-prompt deliverables. Upstream of everything technical.
- **TECH_STACK.md** and **RESEARCH_NOTES.md** captured public signal on Lore's likely technology stack. Inform but do not constrain.
- **CONTEXT.md** identifies the panel interviewers and squad mappings.
- **ARCHITECTURE_REQUIREMENTS.md** consumes this BRD plus the stack documents and produces the buildable architecture.
- **HIPAA_POSTURE.md** tracks the live-vs-stubbed-vs-deferred status of every control; updated when status changes.
- **docs/adr/** contains Architecture Decision Records (ADR-0001 through ADR-0009 in the synthesis baseline) that codify specific decisions referenced from this BRD and from the ARD.
- **docs/reviews/** contains the eight review rounds that informed the synthesis; retained for traceability.

## Scope

### In Scope

- Multi-partner eligibility ingestion across heterogeneous file formats
- Identity resolution within and across partner feeds
- Canonical member entity with full SCD2 history
- Identity verification API serving the Lore application's account creation flow
- PII isolation, tokenization, and audit posture sufficient to satisfy HIPAA technical safeguards
- Right-to-deletion workflow consistent with state privacy law obligations
- Member rights fulfillment (Right of Access, Amendment, Accounting, Restriction, Confidential Communications)
- HIPAA Privacy Rule infrastructure (NPP, authorization, complaint handling)
- Breach notification infrastructure (assessment, content, channels, timelines)
- Workforce compliance program (Privacy Officer, Security Officer, training, sanctions)
- Operational observability across the pipeline
- Partner onboarding workflow (configuration-driven, not code-driven)

### Out of Scope

- Real-time API ingestion from partners (v1 is file-based; A22)
- Account creation logic itself (eligibility system is a source of truth, not an account owner)
- Member-facing consent management UI beyond rights fulfillment workflows
- Finance-side savings attribution logic (the data product is attribution-neutral; finance reads from it)
- Production-hardened infrastructure-as-code, secrets management, and disaster recovery runbooks (referenced in NFRs and ADRs; not produced here)
- Manual review queue staffing and SLA (existence and clear-mechanism only; staffing is operational concern)

## Per-Rule Metadata Schema

Every rule below carries the following metadata:

- **Statement** — testable assertion in `MUST`/`MUST NOT`/`SHOULD` form. SHOULD is reserved for genuinely advisory items.
- **Rationale** — why the rule exists.
- **Business value** — what business outcome the rule serves (member trust, partner contract retention, HIPAA defensibility, operational efficiency, brand defense, revenue protection, regulatory compliance, etc.).
- **Strategic tier** — one of:
  - **Differentiator** — competitive advantage; valuable
  - **Compliance baseline** — required for HIPAA / state law / contract; non-negotiable
  - **Operational excellence** — improves cost, reliability, or scale
  - **Optionality** — preserves future moves (configurability, format flexibility)
  - **Foundation** — required for other rules to be implementable
- **Enforcement** — concrete mechanism: live test, planned test, CI gate, programmatic check, process audit, or `[ADVISORY]` (no programmatic enforcement available).

Numbers in rules MUST appear as named parameters from the Configuration Parameters table; rules MUST NOT contain inline numeric literals (XR-002).

## Cross-Cutting Rules

These rules apply across every domain. Domain-specific rules MUST be consistent with them; conflicts are resolved in favor of the cross-cutting rule.

### XR-001: Layered Configurability

**Statement:** Every threshold, timeout, cadence, and policy value referenced in this BRD MUST be a named configuration parameter with a global default. Per-partner override MUST be supported. Per-contract override and per-load override MUST be supported where the parameter is meaningfully scoped to those layers. Hardcoded values in production code are a defect.

**Rationale:** Partner contracts vary; operational realities vary; baked-in values become code changes for what should be config changes.

**Business value:** Operational efficiency; partner contract flexibility.

**Strategic tier:** Foundation.

**Enforcement:** CI lint rule (`scripts/check_inline_literals.py`, planned) scanning implementation code for inline numeric or duration literals matching parameter names. Test (`tests/integration/test_config_resolution.py`, planned) asserting the override resolution order produces expected values for representative parameter and partner combinations.

### XR-002: No Magic Numbers

**Statement:** Every numeric requirement in this BRD MUST reference a named configuration parameter from the Configuration Parameters table. Implementation code MUST NOT contain inline numeric constants that govern policy behavior.

**Rationale:** Magic numbers are unauditable; configuration parameters are auditable.

**Business value:** Audit defensibility; operational efficiency.

**Strategic tier:** Foundation.

**Enforcement:** Same as XR-001. Reviewer checklist item enforced via `phase-boundary-auditor` agent.

### XR-003: Privacy-Preserving Collapse on Public Surfaces

**Statement:** Public-facing API responses, error messages, and external observability surfaces MUST NOT distinguish "the subject exists in the system but X" from "the subject does not exist in the system." Internal richer state MUST be preserved for authenticated admin and audit paths only. Side channels (timing, response shape, error path artifacts) MUST be closed per ADR-0009.

**Rationale:** Distinguishing existence from non-existence on a public surface leaks PHI association to anyone who can call the endpoint, regardless of the response payload's other contents.

**Business value:** Member trust; HIPAA defensibility; brand defense.

**Strategic tier:** Differentiator (privacy-preserving design as competitive posture).

**Enforcement:** Integration test (`tests/integration/test_verification_collapse.py`, planned) asserting the public response set is exactly `{VERIFIED, NOT_VERIFIED}` with consistent generic messaging across all internal-state combinations. Static analysis check (`scripts/check_internal_enum_export.py`, planned) preventing internal state enums from being importable by public-facing controllers. Latency-distribution test per ADR-0009 (statistical indistinguishability above the floor; planned in Phase 1 exit criteria).

### XR-004: Identity-Scoped Lockouts and Rate Limits

**Statement:** Rate limits and lockouts that protect against brute-force or enumeration MUST be scoped to resolved Lore identity wherever that scope is meaningful. Claim-payload and source-IP scopes ARE auxiliary controls layered on top, not primary.

**Rationale:** Source-IP-only limits are defeated by IP rotation. Claim-payload-only limits are defeated by spelling variation. Identity scope means an attacker burns through one identity at a time and stops, regardless of network topology or input variation.

**Business value:** Member trust; HIPAA defensibility.

**Strategic tier:** Compliance baseline.

**Enforcement:** Integration test (`tests/integration/test_brute_force_scope.py`, planned) exercising lockout under IP rotation and spelling-variation attack patterns.

### XR-005: Zero PII or PHI in Logs

**Statement:** Plaintext PII or PHI MUST NOT appear in any log, metric, trace, or alert payload. Resolved identities MUST be logged as their tokenized identifier. Inbound claim payloads MUST be logged as salted hashes only. Forensic reconstruction MUST go through the vault under break-glass access (which is itself logged).

**Rationale:** Industry standard for healthcare audit logging. Logs holding only tokens and hashes fall outside the PHI scope of HIPAA, materially reducing breach blast radius and the regulatory weight on the logging system.

**Business value:** HIPAA defensibility; brand defense; member trust.

**Strategic tier:** Compliance baseline.

**Enforcement:** Two gates. (a) `bootstrapper/logging_config.py` (LIVE per Phase 00 harness) implements PII-redacting structlog processors with two-layer defense (key-based + pattern-based). (b) CI gate `scripts/check_pii_in_fixtures.py` (LIVE) scans test fixtures for PII shapes. (c) Scheduled production-safe sampling job (PLANNED Phase 2) scans live logs for the same patterns and pages on any match.

### XR-006: Irreversibility Separation

**Statement:** Every state-mutating operation MUST be classified as reversible or irreversible. Reversible operations MUST be idempotent. Irreversible operations MUST require explicit operator confirmation, MUST emit the strongest audit trail in the system, and MUST be bounded to the smallest possible set of code paths.

**Rationale:** Vault purges, deletion ledger inserts, and similar operations cannot be undone. They deserve different code paths, different review, and different audit treatment than re-runnable operations.

**Business value:** HIPAA defensibility; operational excellence.

**Strategic tier:** Foundation.

**Enforcement:** Code-path inventory check (`scripts/check_irreversible_ops.py`, planned). Operations classified `irreversible` MUST live in a designated module (`shared/security/irreversible/`) with elevated review requirements (CODEOWNERS). Test (`tests/unit/test_irreversible_confirmation.py`, planned) asserting that irreversible operations require an explicit confirmation token in their invocation signature.

### XR-007: Plain Language for Member-Facing Content

**Statement:** All member-facing content (NPP, error messages, breach notifications, support communications, rights-request responses, member portal text) MUST be authored at or below 8th-grade reading level. Active voice MUST be preferred. Sentence length SHOULD typically be ≤ 20 words. Translation MUST follow the same plain-language standard.

**Rationale:** HIPAA notices in legal language are a compliance success but a trust failure. Plain language serves members with limited literacy, English-as-a-second-language, cognitive disabilities, and stress contexts (acute care, crisis).

**Business value:** Member trust; HIPAA defensibility; brand defense.

**Strategic tier:** Differentiator.

**Enforcement:** CI gate (`scripts/check_reading_level.py`, planned) running Flesch-Kincaid against member-facing content; deploy blocked above the threshold. Content design review on every member-facing content change (CODEOWNERS).

### XR-008: Multilingual Support

**Statement:** All member-facing surfaces (NPP, breach notifications, member portal, support communications, error messages) MUST support English and Spanish at v1. Additional languages MUST be added per `MEMBER_LANGUAGE_PRIORITY_LIST` parameter as the partner population justifies. Translations MUST be reviewed by counsel for legal-document accuracy.

**Rationale:** Title VI of the Civil Rights Act requires meaningful language access for federally funded healthcare. Lore's population includes significant Spanish-speaking members; English-only fails members and exposes Lore to enforcement.

**Business value:** Regulatory compliance; member trust; brand defense.

**Strategic tier:** Compliance baseline.

**Enforcement:** Test (`tests/integration/test_member_content_languages.py`, planned) asserting required content exists in all supported languages per `MEMBER_LANGUAGE_PRIORITY_LIST`. CI gate (`scripts/check_translation_coverage.py`, planned) failing on untranslated content. `[ADVISORY]` for the counsel-review portion (legal review is process, not programmatic).

### XR-009: Accessibility (WCAG 2.1 AA)

**Statement:** All UI surfaces (member portal, reviewer interface, operator dashboards, compliance UI, partner-facing portal) MUST meet WCAG 2.1 AA. Accessibility audit MUST be run automated per PR (axe / Lighthouse) and manually per release (keyboard navigation, screen reader). External third-party audit MUST occur annually.

**Rationale:** ADA Title III applicability for healthcare-facing content; equity for disabled members; compliance baseline for federal contracts.

**Business value:** Regulatory compliance; member trust.

**Strategic tier:** Compliance baseline.

**Enforcement:** CI gate (`scripts/check_accessibility.sh`, planned) running automated audit per UI PR. Per-release manual audit checklist (process; tracked in PM tool). Annual third-party audit `[ADVISORY]` (procurement is process).

### XR-010: Configuration Parameter Discipline

**Statement:** Every configuration parameter MUST have: a typed schema (Pydantic), a documented range, a documented scope (global / per-partner / per-contract / per-load), a documented owner role, and a documented strategic tier. Configuration changes MUST go through the same review pipeline as code (PR + review + audit).

**Rationale:** Configuration changes have the same blast radius as code changes. A bad threshold quarantines feeds; a bad match parameter merges wrong identities.

**Business value:** Operational excellence; HIPAA defensibility.

**Strategic tier:** Foundation.

**Enforcement:** CI gate (`scripts/validate_config_schema.py`, planned) verifying every parameter has the required metadata. Test (`tests/integration/test_config_load_failure.py`, planned) asserting invalid configuration is rejected at load time and the previous valid configuration is retained.

### XR-011: Decision Authority and Amendment Process

**Statement:** Every BR amendment, every Architectural Decision (ADR), and every Configuration Parameter classified as **Strategic** in the parameter ledger MUST cite an approver. The approver MUST be at the appropriate authority tier (engineering lead for Operational; CTO for Strategic differentiator; CEO for Existential-risk-bearing). Amendments MUST follow the documented change request process.

**Rationale:** Without explicit decision authority, amendments are untraceable; future contributors cannot tell which decisions are settled and which are open.

**Business value:** Operational excellence; audit defensibility.

**Strategic tier:** Foundation.

**Enforcement:** CI gate on PRs touching BRD/ARD/ADR (`scripts/check_decision_authority.py`, planned) verifying the amendment cites an approver. Process audit `[ADVISORY]` for verifying the named approver actually approved (signature workflow is downstream tooling).

### XR-012: Bidirectional Traceability

**Statement:** Every BR MUST map to at least one architectural component that owns its implementation (BR → component, recorded in this BRD). Every architectural component MUST list the BRs it implements (component → BRs, recorded in the ARD). The mapping MUST be complete in both directions.

**Rationale:** Orphan rules (rules with no owning component) cannot be implemented; orphan components (components serving no BR) are gold-plating. Bidirectional traceability surfaces both.

**Business value:** Operational excellence; audit defensibility.

**Strategic tier:** Foundation.

**Enforcement:** CI gate (`scripts/check_traceability.py`, planned) reading the BR-to-component table from this BRD and the component-to-BR table from the ARD; failing on any orphan in either direction. Run on every BRD or ARD change.

## Role Taxonomy

The system recognizes the following roles. Role assignments are auditable and managed under the same change-control rigor as production code. Role membership changes MUST emit audit events.

| Role | Access | PII Access | Residency Constraint | Designated By |
| --- | --- | --- | --- | --- |
| Member | Self-service rights via member portal | Own PHI only | None | N/A (member-facing) |
| Personal Representative | Acts on behalf of member with verified authority | Subject member's PHI only | None | Member's verified authority document |
| Reviewer | Manual review queue | None (tokenized surfaces only) | None | Engineering lead |
| Data Engineer | Pipeline operations, configuration | None (tokenized surfaces only) | None | Engineering lead |
| Data Ops / SRE | Pipeline operations, on-call escalations | None (tokenized surfaces only) | None | Engineering lead |
| PII Handler | Vault detokenization for legitimate purposes | Yes, audited per access | US-resident only | Privacy Officer + CISO |
| Data Owner | Per-partner config, onboarding sign-off | None (tokenized surfaces only) | None | Partner ops lead |
| Auditor | Read-only access to audit logs | None | None | Privacy Officer |
| Privacy Officer | HIPAA Privacy Rule program ownership | Limited (audit log read; documented review purposes) | US-resident only | CEO designation |
| Security Officer | HIPAA Security Rule program ownership | Limited (incident response only; audited) | US-resident only | CEO designation |
| Break-Glass Admin | Time-boxed elevated access for incident response | Yes, time-boxed and audited | US-resident only | CISO + Privacy Officer (two-person grant per ADR-0008) |
| Compliance Staff | DSAR fulfillment, complaint handling, breach assessment | None directly; coordinates Auditor reads | US-resident only | Privacy Officer |
| Partner | Partner-facing portal (when implemented) | Limited per BAA | Partner residency per BAA | Partnership operations |

The data engineering function (including offshore staff at Sequelae PH) operates without direct access to plaintext PII or PHI. This is enforced as an architectural decision (BR-506), not as an organizational practice. Sequelae PH residents MUST NOT be members of `pii_handler@`, `break_glass@`, `privacy_officer@`, `security_officer@`, or `compliance_staff@` IAM groups.

## Business Rules

Rules are numbered for citation from the ARD, from tests, and from operational runbooks. Each rule states what must be true, with the per-rule metadata schema applied.

### Domain: Identity Resolution

#### BR-101: Tiered Match Decision

**Statement:** Identity resolution MUST proceed through four tiers, evaluated in order. A record's match decision MUST be the result of the first tier that produces a definitive outcome.

1. **Tier 1, Deterministic Anchor.** Match on `partner_member_id + dob_token + name_token` within the same partner. Outcome: auto-merge.
2. **Tier 2, Probabilistic High Confidence.** Match score at or above `MATCH_THRESHOLD_HIGH`. Outcome: auto-merge with audit event.
3. **Tier 3, Probabilistic Mid Confidence.** Match score in `[MATCH_THRESHOLD_REVIEW, MATCH_THRESHOLD_HIGH)`. Outcome: queue for human review; no merge until cleared.
4. **Tier 4, Below Threshold.** Match score below `MATCH_THRESHOLD_REVIEW`. Outcome: treat as distinct identity.

**Rationale:** Healthcare PII context is asymmetric on match errors. False positives merging two distinct people are a HIPAA breach; false negatives duplicating one person are revenue leakage and onboarding friction. Tiered policy preserves automation where confidence supports it and routes ambiguity to humans.

**Business value:** Member trust (Tier 3 prevents unsafe merges); operational efficiency (Tiers 1-2 enable scale); revenue protection (Tier 4 prevents identity fragmentation).

**Strategic tier:** Differentiator (Tier 3 review quality is competitive); Operational excellence (Tiers 1-2-4).

**Enforcement:** Unit tests (`tests/unit/test_match_tier_decisions.py`, planned) asserting deterministic outcomes on synthetic match payloads at each tier boundary. Integration test (`tests/integration/test_match_tier_order.py`, planned) asserting tier evaluation order is preserved under partial input.

**Owning component:** Identity Resolution context (Match Orchestrator + Splink Runner).

#### BR-102: Match Anchor Composition

**Statement:** The deterministic anchor for Tier 1 MUST be `partner_member_id + dob_token + name_token`. SSN MAY be used as a secondary anchor when present and full (not last-4 only) and MUST NOT be used as a sole anchor. Last-4 SSN MAY contribute to probabilistic scoring but MUST NOT produce a Tier 1 outcome under any input combination.

**Rationale:** SSN availability is variable across partners under standard medical records keeping practice (Assumption A1). A deterministic tier dependent on SSN would silently degrade to no-anchor when partners redact. The chosen composition is robust to redaction.

**Business value:** Operational excellence; member trust (avoids fragility-based mismatches).

**Strategic tier:** Operational excellence.

**Enforcement:** Test (`tests/unit/test_anchor_no_ssn.py`, planned) asserting records lacking SSN entirely still resolve through Tier 1 when other anchor fields are complete. Test (`tests/unit/test_anchor_last4_ssn.py`, planned) asserting last-4 SSN does not produce a Tier 1 outcome under any input combination.

**Owning component:** Identity Resolution context (Match Orchestrator).

#### BR-103: Survivorship on Conflicting Attributes

**Statement:** When matched records carry conflicting attribute values, survivorship rules MUST apply per attribute class:

- **Mutable attributes** (address, phone, email, current name): most-recent-update wins.
- **Identity-defining attributes** (dob_token, full SSN): locked after first verified value. Conflicting subsequent values MUST NOT overwrite. Conflict MUST trigger a review queue entry of class `IDENTITY_CONFLICT` and MUST suspend the auto-merge that produced the conflict pending resolution.

**Rationale:** Identity-defining attributes are stable across a person's life. A conflicting DOB is a stronger signal of identity mismatch than typo correction. Mutable attributes routinely change.

**Business value:** Member trust; HIPAA defensibility (prevents wrong-person merges).

**Strategic tier:** Compliance baseline.

**Enforcement:** Test (`tests/unit/test_survivorship_mutable.py`, planned) asserting most-recent-update behavior for each mutable attribute. Test (`tests/unit/test_survivorship_dob_conflict.py`, planned) asserting DOB conflict produces a `PENDING_RESOLUTION` state and a review queue entry without overwriting the prior value.

**Owning component:** Canonical Eligibility context (State Machine Engine) + Identity Resolution context (Match Orchestrator).

#### BR-104: Match Replay Continuity

**Statement:** When the matching algorithm or its scoring configuration changes, every affected match record MUST carry both the algorithm version and the configuration version active at the time of the decision. Operators MAY initiate full-history match replay at any time. Operators MAY initiate partial match replay only with explicit acknowledgment that a discontinuity will be introduced; the discontinuity MUST be queryable via the version stamps.

**Rationale:** Probabilistic match decisions incorporate evidence from the full historical record. A partial replay with a changed algorithm produces silent discontinuity unless explicitly versioned and acknowledged. Versioning makes the discontinuity visible rather than invisible.

**Business value:** Operational excellence; HIPAA defensibility.

**Strategic tier:** Operational excellence.

**Enforcement:** Test (`tests/unit/test_match_decision_versioning.py`, planned) asserting every match record carries both version stamps. Integration test (`tests/integration/test_partial_replay_confirmation.py`, planned) asserting partial match replay refuses to execute without a confirmation token referencing the version delta.

**Owning component:** Identity Resolution context (Match Decision Store).

#### BR-105: Manual Review Queue Existence

**Statement:** A persistent, queryable manual review queue MUST exist. Items entering the queue MUST carry the tier evaluation result, the candidate match score, the records under consideration (referenced by tokenized identifier), the queue entry timestamp, and the score breakdown for reviewer decision support per ADR `[reviewer-UX]` (forthcoming). A clear mechanism for resolving queue items MUST exist. Reviewer staffing, queue SLA, and routing rules are deferred from v1 (`[ADVISORY]` portion).

**Rationale:** The queue is a structural component of the match policy. Its operational shape is deferred but its existence is not.

**Business value:** Member trust; HIPAA defensibility.

**Strategic tier:** Differentiator.

**Enforcement:** Test (`tests/unit/test_tier3_queue_entry.py`, planned) asserting Tier 3 outcomes produce queue entries with the required fields. Test (`tests/integration/test_review_queue_addressable.py`, planned) asserting queue items are addressable by stable identifier. Reviewer staffing model `[ADVISORY]` (operational concern; PM-tracked).

**Owning component:** Identity Resolution context (Manual Review Queue) + Reviewer interface (frontend, deferred).

### Domain: Eligibility Lifecycle

#### BR-201: Canonical Member State Machine

**Statement:** Every canonical member record MUST occupy exactly one state at any point in time, drawn from the following set:

- `PENDING_RESOLUTION`: created from a partner record but blocked on manual identity review
- `ELIGIBLE_ACTIVE`: present on at least one current partner roster
- `ELIGIBLE_GRACE`: dropped from all partner rosters within the last `GRACE_PERIOD_DAYS`, still account-eligible
- `INELIGIBLE`: past grace period; account locked or read-only
- `DELETED`: right-to-deletion executed; PII vault purged; SCD2 history retained with PII fields nulled

**Rationale:** Account creation, verification, and downstream consumers all need an unambiguous current state. A state machine makes transitions auditable and verifiable.

**Business value:** Operational excellence; HIPAA defensibility.

**Strategic tier:** Foundation.

**Enforcement:** Database constraint asserting `state` is one of the enumerated values (`canonical_member` schema, ARD §"Data Schemas"). Test (`tests/unit/test_state_machine_coverage.py`, planned) asserting every transition between states is covered by a defined transition rule (BR-202).

**Owning component:** Canonical Eligibility context (State Machine Engine).

#### BR-202: State Transition Rules

**Statement:** Allowed state transitions MUST be exactly the set enumerated below. All other transitions MUST be forbidden by application code (not by trigger; per ARD AD discussion).

- `(none)` → `PENDING_RESOLUTION`: ingested record requires review
- `(none)` → `ELIGIBLE_ACTIVE`: ingested record clears Tier 1 or Tier 2 match and resolves to a new identity
- `PENDING_RESOLUTION` → `ELIGIBLE_ACTIVE`: review cleared; identity confirmed
- `PENDING_RESOLUTION` → `DELETED`: review cleared as distinct identity that requested deletion (rare path)
- `ELIGIBLE_ACTIVE` → `ELIGIBLE_GRACE`: dropped from all current partner rosters
- `ELIGIBLE_GRACE` → `ELIGIBLE_ACTIVE`: re-appears on any partner roster within grace period
- `ELIGIBLE_GRACE` → `INELIGIBLE`: grace period elapsed without re-enrollment
- `INELIGIBLE` → `ELIGIBLE_ACTIVE`: re-appears on any partner roster (re-enrollment after gap; identity preserved)
- Any state → `DELETED`: right-to-deletion executed

**Rationale:** Explicit transition table prevents implicit state drift from ad-hoc updates.

**Business value:** Operational excellence; HIPAA defensibility.

**Strategic tier:** Foundation.

**Enforcement:** Unit test (`tests/unit/test_state_transitions.py`, planned) enumerating every state pair and asserting allowed/forbidden status matches this rule.

**Owning component:** Canonical Eligibility context (State Machine Engine).

#### BR-203: Grace Period

**Statement:** The grace period from "last seen on any roster" to `INELIGIBLE` MUST default to `GRACE_PERIOD_DAYS`. This parameter MUST support per-partner override and per-contract override.

**Rationale:** Care continuity argues for a non-zero grace; partner contracts may dictate specific values; some partner populations within a single partner may have different terms.

**Business value:** Member trust (continuity of care signal); partner contract flexibility.

**Strategic tier:** Operational excellence.

**Enforcement:** Test (`tests/integration/test_grace_period_resolution.py`, planned) asserting transition timing matches the resolved (global, partner, contract) parameter value for representative configurations.

**Owning component:** Canonical Eligibility context (State Machine Engine + Configuration library).

#### BR-204: Re-Enrollment After Gap

**Statement:** When a previously-known member returns to any partner roster, the canonical identity MUST be preserved. The member MUST transition from `ELIGIBLE_GRACE` or `INELIGIBLE` back to `ELIGIBLE_ACTIVE`. A `REENROLLMENT` audit event MUST be emitted, recording the gap duration and the partner that reintroduced the member.

**Rationale:** Identity continuity across enrollment gaps is essential for clinical context and accurate longitudinal savings calculation. Creating a new identity on re-enrollment would fragment the longitudinal record.

**Business value:** Member trust (continuity of care); revenue protection (savings attribution accuracy).

**Strategic tier:** Operational excellence.

**Enforcement:** Test (`tests/integration/test_reenrollment_continuity.py`, planned) asserting that ingestion of a previously-deleted-then-returned roster member resolves to the original canonical identity (subject to BR-703 deletion suppression). Test (`tests/unit/test_reenrollment_audit_event.py`, planned) asserting `REENROLLMENT` audit event emission with required fields.

**Owning component:** Canonical Eligibility context (State Machine Engine) + Audit context.

#### BR-205: Attribution Neutrality

**Statement:** The canonical member record MUST hold a one-to-many relationship to `partner_enrollment` rows. Each enrollment row MUST carry its own effective period, partner identifier, and partner-supplied attributes. Simultaneous enrollments across multiple partners MUST be recorded faithfully without the data product choosing among them. Attribution rules (savings credit, primary partner) ARE out of scope for the data product and MUST be read by downstream consumers from this neutral shape.

**Rationale:** Attribution rules vary by partner contract and may change over time. Embedding an attribution rule in the data product would couple the data product to finance logic and require rebuilds when finance rules change. Neutral storage decouples them.

**Business value:** Optionality (preserves finance flexibility); operational excellence.

**Strategic tier:** Optionality.

**Enforcement:** Schema constraint enforcing the one-to-many shape (ARD `partner_enrollment` schema). Test (`tests/integration/test_multi_partner_enrollment.py`, planned) asserting that two simultaneous enrollments produce two retained enrollment rows with no canonical-record-level "primary partner" field.

**Owning component:** Canonical Eligibility context (operational store schema).

#### BR-206: Lifecycle Audit

**Statement:** Every state transition MUST emit a `STATE_TRANSITION` audit event recording the prior state, the new state, the trigger (ingestion, time-based, deletion request, review resolution), the resolved canonical identity in tokenized form, the timestamp, and the correlation_id (per ADR-0006).

**Rationale:** State transitions are auditable history; without per-transition audit, point-in-time state reconstruction fails.

**Business value:** HIPAA defensibility; operational excellence.

**Strategic tier:** Compliance baseline.

**Enforcement:** Test (`tests/unit/test_lifecycle_audit_emission.py`, planned) asserting audit event emission on each transition class. Audit event schema validation at Pub/Sub topic level.

**Owning component:** Canonical Eligibility context + Audit context.

### Domain: Data Quality

#### BR-301: Field Criticality Tiers

**Statement:** Every canonical eligibility field MUST be assigned to exactly one of three tiers:

- **Required:** Record is rejected if missing or invalid.
- **Verification:** Record is accepted but flagged as not-verifiable until the field is populated and valid.
- **Enrichment:** Absence is logged but never blocks acceptance.

The Required tier MUST be seeded from the X12 834 Required (R) field set as a baseline. Lore-specific additions to the Required tier MUST be documented per partner.

**Rationale:** Industry-standard 834 R-set is a defensible baseline. Three tiers separate "this record is unusable" from "this record needs more before it counts" from "this is nice to have."

**Business value:** HIPAA defensibility; partner contract flexibility.

**Strategic tier:** Operational excellence.

**Enforcement:** Configuration validation (`scripts/validate_partner_yaml.py`, planned) asserting every canonical field carries a tier assignment. Test (`tests/integration/test_dq_tier_behavior.py`, planned) asserting tier-correct rejection and acceptance behavior.

**Owning component:** Ingestion & Profiling context (DQ Engine + Schema Registry).

#### BR-302: Record-Level Quarantine

**Statement:** Records failing Required-tier validation MUST be quarantined individually. The remainder of the feed MUST proceed to processing. Quarantined records MUST be retained for forensic replay and partner-side correction for `RAW_FEED_RETENTION_DAYS` from quarantine.

**Rationale:** A bad single record is a partner data hygiene issue, not a feed-level structural problem.

**Business value:** Operational excellence; partner relationship.

**Strategic tier:** Operational excellence.

**Enforcement:** Test (`tests/integration/test_record_quarantine.py`, planned) asserting a single bad record does not block its feed. Test (`tests/integration/test_quarantine_addressable.py`, planned) asserting quarantined records are addressable for replay.

**Owning component:** Ingestion & Profiling context (DQ Engine + Quarantine Bucket).

#### BR-303: Feed-Level Quarantine Threshold

**Statement:** When the per-feed record rejection rate exceeds `FEED_QUARANTINE_THRESHOLD_PCT`, the entire feed MUST be quarantined and a human MUST be paged. This parameter MUST support per-partner and per-load override.

**Rationale:** A bad single record is a partner data hygiene issue. A high rejection rate is a structural problem (schema drift, encoding error, wrong file) that cannot be safely processed record-by-record.

**Business value:** HIPAA defensibility (prevents bad data reaching curated layer); partner relationship.

**Strategic tier:** Compliance baseline.

**Enforcement:** Test (`tests/integration/test_feed_quarantine_boundary.py`, planned) asserting the feed-quarantine trigger fires at the threshold boundary for representative configurations. Integration test (`tests/integration/test_feed_quarantine_paging.py`, planned) asserting human-paging path is exercised.

**Owning component:** Ingestion & Profiling context (DQ Engine).

#### BR-304: Schema Drift Handling

**Statement:** Additive schema changes (new columns) MUST be auto-accepted with a `SCHEMA_DRIFT_ADDITIVE` notification logged. Subtractive (column removed) and type-narrowing (type changed in a way that loses information) schema changes MUST quarantine the feed and page a human.

**Rationale:** Additive changes are routine and rarely indicate failure; alerting on every additive change creates fatigue and degrades signal on changes that matter. Subtractive and narrowing changes silently break downstream contracts.

**Business value:** Operational excellence; partner relationship.

**Strategic tier:** Operational excellence.

**Enforcement:** Test (`tests/integration/test_schema_drift_additive.py`, planned) asserting additive change produces accepted-with-notification outcome. Test (`tests/integration/test_schema_drift_breaking.py`, planned) asserting subtractive and narrowing changes produce quarantine and page.

**Owning component:** Ingestion & Profiling context (DQ Engine + Schema Registry).

#### BR-305: Data Profiling Baseline

**Statement:** During partner onboarding (BR-801), an initial data profile MUST be computed from the sample feed: per-field null rate, per-field cardinality, per-field value distribution, and feed-level row count. Subsequent feeds MUST be compared against this baseline. Distribution drift exceeding `PROFILE_DRIFT_THRESHOLD` MUST emit a `PROFILE_DRIFT` event and route the feed for review without auto-quarantine.

**Rationale:** Profile drift catches the silent failure modes that schema-conformant feeds can still exhibit (a field that was 5% null is now 80% null; a state code field that had 50 distinct values now has 3).

**Business value:** Operational excellence; partner relationship; HIPAA defensibility.

**Strategic tier:** Operational excellence.

**Enforcement:** Test (`tests/integration/test_profile_capture.py`, planned) asserting profile capture during onboarding. Test (`tests/integration/test_profile_drift.py`, planned) asserting drift detection fires at the threshold.

**Owning component:** Ingestion & Profiling context (DQ Engine).

#### BR-306: Quality SLA Gating Downstream Publication

**Statement:** Feeds that fail Required-tier or feed-threshold validation MUST NOT publish to the curated layer. Quarantined feeds MUST remain accessible only to data engineering roles for diagnosis.

**Rationale:** The curated layer is the source of truth for verification and account creation. Bad data must not reach it.

**Business value:** HIPAA defensibility; member trust.

**Strategic tier:** Compliance baseline.

**Enforcement:** Integration test (`tests/integration/test_quarantine_no_curated_publish.py`, planned) asserting that quarantined feeds do not produce curated-layer effects.

**Owning component:** Ingestion & Profiling context (DQ Engine + Curated layer publisher).

### Domain: Identity Verification API

#### BR-401: External State Set

**Statement:** The verification API's external response set MUST be exactly `{VERIFIED, NOT_VERIFIED}` with consistent generic messaging. Internal richer states (`NOT_FOUND`, `INELIGIBLE`, `PENDING_RESOLUTION`, `AMBIGUOUS`) MUST be preserved for logging and authenticated admin paths only. Side channels MUST be closed per ADR-0009.

**Rationale:** Privacy-preserving collapse per XR-003. Distinguishing "you exist but ineligible" from "you don't exist" leaks PHI association to anyone who can call the endpoint.

**Business value:** Member trust; HIPAA defensibility; brand defense.

**Strategic tier:** Differentiator.

**Enforcement:** Per XR-003 enforcement. Integration test enumerating all internal state combinations and asserting external response collapse and timing equalization (per ADR-0009).

**Owning component:** Verification context.

#### BR-402: Progressive Friction on Failed Verification

**Statement:** Verification failure handling MUST follow a three-tier progression scoped to resolved Lore identity within `BRUTE_FORCE_WINDOW_HOURS`:

1. **First failure:** Normal retry; no friction.
2. **Second failure:** Friction challenge applied (preferred: step-up via one-time-code to registered channel; secondary: invisible reCAPTCHA scoring per ADR `[friction-mechanism]` forthcoming). Increased response latency (still floor-equalized per ADR-0009). Additional logging.
3. **Third failure:** Identity locked. Self-service recovery is not available; recovery is out-of-band only per BR-1308.

Per-claim-payload rate limits MUST also be enforced as auxiliary controls per XR-004. All probes MUST be logged regardless of outcome. All thresholds MUST be configurable.

**Rationale:** Typo recovery is the dominant first-failure case; adding friction there harms legitimate users. Subsequent failures within a short window are a stronger attack signal.

**Business value:** Member trust; HIPAA defensibility.

**Strategic tier:** Compliance baseline.

**Enforcement:** Integration test (`tests/integration/test_brute_force_progression.py`, planned) exercising the three-tier progression under same-identity attack patterns and under spelling-variation attack patterns.

**Owning component:** Verification context (rate-limit cache + friction layer + lockout enforcement).

#### BR-403: Failed Verification Fallback

**Statement:** When a user fails verification through the self-service path, the response MUST display a generic message and a contact-support path. v1 MUST NOT provide a deferred-account state or in-system manual-review escalation from the user-facing surface. The contact-support path UX MUST be designed per BR-1308.

**Rationale:** Self-service-only is a defensible v1 scope. Deferred-account and in-app manual review are roadmap items requiring additional UX, fraud, and clinical-trust analysis.

**Business value:** Member trust (when fallback is well-designed; harms member trust when poorly designed); operational excellence.

**Strategic tier:** Compliance baseline.

**Enforcement:** Test (`tests/integration/test_failure_response_no_internal_state.py`, planned) asserting public response on failure does not reveal internal path options or queue identifiers.

**Owning component:** Verification context + Lore application UX (cross-team).

#### BR-404: Verification Latency

**Statement:** Verification API responses MUST achieve p95 latency at exactly `VERIFICATION_LATENCY_FLOOR_MS` (the floor; not "at or below"). The floor MUST be set above the slowest legitimate path's p99 to enable timing equalization (ADR-0009). p99 MUST be at or below `VERIFICATION_LATENCY_P99_CEILING_MS`.

**Rationale:** Latency equalization (ADR-0009) requires a floor; the floor anchors p95. Pre-synthesis BRD set p95 ≤ 200ms; post-synthesis, the floor is 250ms (timing-side-channel mitigation).

**Business value:** Member trust; HIPAA defensibility (closes timing channel).

**Strategic tier:** Differentiator (timing equalization as competitive privacy posture).

**Enforcement:** Continuous performance monitoring with alerting on threshold breach. Load test gate (`scripts/run_load_test.sh`, planned) in pre-release pipeline. Phase 1 exit criterion includes timing-distribution test per ADR-0009.

**Owning component:** Verification context.

#### BR-405: Verification Availability

**Statement:** The verification API MUST achieve `VERIFICATION_AVAILABILITY_PCT` measured rolling-30-day. If account creation is hard-blocked on the API, the parameter SHOULD be raised to `VERIFICATION_AVAILABILITY_HARDBLOCK_PCT`.

**Rationale:** API is in the critical path of account creation. User experience expectations and timeout budgets in the calling surface set the ceiling.

**Business value:** Member trust; partner contract retention; revenue protection.

**Strategic tier:** Compliance baseline (commercial commitment to Lore application via internal OLA per R7 E-015).

**Enforcement:** Continuous availability monitoring with alerting and quarterly review. SLO compliance reviewed at Quarterly Business Review per `[ADVISORY]` operational cadence (process).

**Owning component:** Verification context.

### Domain: Audit and Compliance

#### BR-501: Audit Event Classes

**Statement:** The system MUST emit audit events for all of the following event classes, at minimum. Each class MUST have a documented routing decision (operational tier vs. high-criticality tier) per BR-503 retention rules.

**Authentication and authorization:**
- `LOGIN_SUCCESS`, `LOGIN_FAILURE`, `MFA_CHALLENGE`, `MFA_SUCCESS`, `MFA_FAILURE`
- `LOGOUT`, `SESSION_REVOKED`
- `TOKEN_ISSUED`, `TOKEN_REFRESHED`, `TOKEN_REVOKED`
- `ACCESS_DENIED`
- `JWT_REPLAY_REJECTED`

**PHI access and modification:**
- `PII_ACCESS` (read; high-criticality)
- `PII_MODIFICATION` (high-criticality)
- `VERIFICATION_ATTEMPT` (success and failure)
- `IDENTITY_MERGE` (auto and manual; high-criticality)
- `STATE_TRANSITION` (per BR-206)
- `MANUAL_REVIEW_ACTION` (queue entry, resolution, override)

**Configuration and operations:**
- `CONFIGURATION_READ`, `CONFIGURATION_CHANGE_ATTEMPTED`, `CONFIGURATION_CHANGE_SUCCEEDED`, `CONFIGURATION_CHANGE_FAILED`
- `DEPLOY_STARTED`, `DEPLOY_SUCCEEDED`, `DEPLOY_FAILED`
- `SCHEMA_MIGRATION_STARTED`, `SCHEMA_MIGRATION_COMPLETED`

**Data quality:**
- `DQ_THRESHOLD_BREACH`
- `SCHEMA_DRIFT_ADDITIVE`, `SCHEMA_DRIFT_BREAKING`
- `PROFILE_DRIFT`

**Deletion lifecycle:**
- `DELETION_REQUEST`, `DELETION_VERIFICATION`, `DELETION_EXECUTED`, `DELETION_OVERRIDE` (high-criticality)
- `REENROLLMENT` (per BR-204)

**Privileged access:**
- `BREAK_GLASS_GRANTED`, `BREAK_GLASS_REVOKED`
- `PII_HANDLER_DETOK` (high-criticality)
- `META_AUDIT_READ` (Auditor querying audit log)

**Network and security:**
- `VPC_SC_PERIMETER_VIOLATION`
- `EGRESS_TO_EXTERNAL_SERVICE` (sampled at `EGRESS_AUDIT_SAMPLE_RATE`)
- `AUDIT_CHAIN_BREAK_DETECTED` (per ADR-0008)

**Disclosures:**
- `DISCLOSURE_TO_EXTERNAL_PARTY` (per BR-905, accounting of disclosures)
- `FORENSIC_EXPORT`, `FORENSIC_LEGAL_HOLD`

**Rationale:** Comprehensive event class coverage prevents blind spots in investigation and auditor inquiries. Some classes are sampled (e.g., `ACCESS_ALLOWED` would be too noisy unless sampled); sampling is parameterized.

**Business value:** HIPAA defensibility; brand defense; insider threat detection.

**Strategic tier:** Compliance baseline.

**Enforcement:** Test per event class (e.g., `tests/unit/test_audit_emission_login_success.py`, planned for each class) asserting event emission under triggering conditions.

**Owning component:** Audit context (Pub/Sub topic + Dataflow consumer + sinks) + every emitting context.

#### BR-502: Audit Log Content Constraints

**Statement:** Audit logs MUST NOT contain plaintext PII or PHI per XR-005. Resolved identities MUST be referenced by tokenized identifier. Inbound claim payloads MUST be referenced by salted hash. Audit events MUST contain sufficient metadata to reconstruct the relevant action: actor, action class, target (tokenized), timestamp, outcome, trigger, correlation_id (per ADR-0006).

**Rationale:** Logs holding only tokens and hashes fall outside the PHI scope of HIPAA, materially reducing breach blast radius.

**Business value:** HIPAA defensibility; brand defense.

**Strategic tier:** Compliance baseline.

**Enforcement:** Per XR-005 enforcement. Audit event schema validation at Pub/Sub. Forensic-replay test (`tests/integration/test_forensic_replay_no_pii.py`, planned) asserting incident reconstruction is achievable from logged metadata plus authenticated vault access without plaintext PII in logs.

**Owning component:** Audit context (schema enforcement) + every emitting context.

#### BR-503: Audit Retention by Class

**Statement:** Retention by event class MUST be at minimum:

- High-criticality events (PII access/modification, identity merge, deletion lifecycle, vault detokenization, audit chain breaks, forensic exports): `AUDIT_RETENTION_PII_YEARS`. Routed to high-criticality tier (GCS Bucket Lock per ADR-0008).
- Operational events (configuration, deploy, DQ, schema drift, profile drift): `AUDIT_RETENTION_OPS_YEARS`. Routed to operational tier (BigQuery `audit_operational`).
- Authentication and authorization events: `AUDIT_RETENTION_AUTHN_YEARS`. Routed to operational tier.
- Network and security events: `AUDIT_RETENTION_OPS_YEARS`. Routed to operational tier.

The PII retention default exceeds the HIPAA documentation floor of 6 years.

**Rationale:** HIPAA requires 6 years; some state laws require longer; longer retention also benefits forensic investigation.

**Business value:** HIPAA defensibility; regulatory compliance.

**Strategic tier:** Compliance baseline.

**Enforcement:** Storage lifecycle policy verification (`scripts/verify_audit_retention.sh`, planned). Test (`tests/integration/test_audit_retention_routing.py`, planned) asserting retention rules apply to representative event types.

**Owning component:** Audit context (Dataflow consumer routing logic + sinks).

#### BR-504: Audit Log Integrity

**Statement:** Audit logs MUST be append-only by access control. High-criticality event classes MUST be additionally protected by hash-chained integrity per ADR-0008 such that tampering is detectable. External anchoring of the chain head (RFC 3161 + cross-organization GCS replication) MUST occur on `AUDIT_CHAIN_ANCHOR_INTERVAL_HOURS`.

**Rationale:** Hash chain provides tamper-evidence; external anchoring extends evidence to attacker who has organization-level admin access.

**Business value:** HIPAA defensibility; insider threat resistance; brand defense.

**Strategic tier:** Differentiator (audit-chain integrity at this level is differentiated for the ACO scale).

**Enforcement:** Access control test (`tests/integration/test_audit_log_immutable.py`, planned) asserting that no role permits update or delete on the audit log table or stream. Hash-chain validation job (`scripts/validate_audit_chain.py`, planned) runs continuously and pages on chain break per ADR-0008. External anchor verification (`scripts/verify_audit_anchors.py`, planned) hourly.

**Owning component:** Audit context.

#### BR-505: Audit Log Read Access

**Statement:** The `Auditor` role MUST have read-only access to audit logs. Other roles (PII Handler, Data Engineer, Data Ops, Reviewer, Data Owner, Compliance Staff except via documented review purposes) MUST NOT have audit log read access by default. Reads of the audit log MUST themselves be logged with the actor, target query, justification, and timestamp. Temporary grants for incident response MUST be time-boxed and logged. Auditor query rate baselines MUST be monitored; anomalous spikes MUST page Privacy Officer.

**Rationale:** Auditor role enables compliance to answer audit questions without pulling in engineering and without granting engineering visibility into who was investigated for what.

**Business value:** HIPAA defensibility; insider threat resistance.

**Strategic tier:** Compliance baseline.

**Enforcement:** Access control test (`tests/integration/test_auditor_role_access.py`, planned) asserting role-correct access boundaries. Test (`tests/unit/test_meta_audit_emission.py`, planned) asserting audit log reads emit a `META_AUDIT_READ` event. Justification required at query time (planned UI gate). Anomaly detection on auditor query patterns.

**Owning component:** Audit context.

#### BR-506: Sequelae PH PII Boundary

**Statement:** Personnel based at Sequelae PH (Lore's Philippines engineering arm) MUST NOT have access to plaintext PII or PHI. Their access MUST be limited to tokenized analytical surfaces and operational tooling that does not surface plaintext PII. The PII Handler, Break-Glass Admin, Privacy Officer, Security Officer, and Compliance Staff roles MUST be restricted to US-resident personnel by IAM Workspace conditions. Residency MUST be enforced at request origin (geolocation), not just account residency, per R3 S-024.

**Rationale:** Cross-border data residency is a structural concern given the offshore engineering footprint. The boundary is enforced architecturally rather than as policy.

**Business value:** HIPAA defensibility; regulatory compliance; partner contract retention.

**Strategic tier:** Foundation.

**Enforcement:** IAM configuration audit (`scripts/audit_iam_residency.sh`, planned). Test (`tests/integration/test_residency_enforcement.py`, planned) asserting that representative offshore-mapped principals cannot detokenize. Cross-border data flow audit log (per BR-501 `EGRESS_TO_EXTERNAL_SERVICE` event class) reviewed quarterly. BAA chain documentation includes Sequelae PH as a subprocessor with this scope explicitly stated `[ADVISORY]` (BAA documentation is process).

**Owning component:** All contexts (residency boundary is cross-cutting at IAM layer); IAM configuration owned by Security Officer.

### Domain: Ingestion Lifecycle

#### BR-601: Within-Feed Deduplication

**Statement:** When a single partner feed contains the same `partner_member_id` more than once, the last occurrence in file order MUST win. All occurrences MUST be retained in the raw landing zone for forensic replay. A `WITHIN_FEED_DEDUP` event MUST be logged with the count of duplicate occurrences resolved.

**Rationale:** Last-record-wins is the partner-implied convention (records are corrections-in-flight); raw retention preserves audit trail.

**Business value:** Operational excellence; audit defensibility.

**Strategic tier:** Operational excellence.

**Enforcement:** Test (`tests/integration/test_within_feed_dedup.py`, planned) asserting last-record-wins behavior. Test (`tests/integration/test_raw_landing_retention.py`, planned) asserting raw landing zone retains all original records.

**Owning component:** Ingestion & Profiling context (Mapping Engine + Landing Zone).

#### BR-602: Snapshot-Diff Comparison

**Statement:** Each accepted partner feed MUST be diffed against the most recent prior accepted feed from the same partner to derive adds, changes, and removes. The diff MUST be authoritative for downstream effects regardless of the prior snapshot's age.

**Rationale:** Snapshot-diff is the implementation pattern for partners delivering full rosters per A23.

**Business value:** Operational excellence.

**Strategic tier:** Foundation.

**Enforcement:** Test (`tests/integration/test_snapshot_diff_correctness.py`, planned) asserting diff correctness across representative scenarios (clean day, partner skipped delivery, schema-drifted feed).

**Owning component:** Ingestion & Profiling context (Mapping Engine + Diff Engine).

#### BR-603: Stale Baseline Warning

**Statement:** When the gap between the prior accepted snapshot and the current snapshot exceeds the partner's expected cadence (`PARTNER_CADENCE_DAYS` per-partner config), a `STALE_BASELINE` warning MUST be emitted. The diff MUST still be processed; the warning flags that significant change may have occurred in the gap.

**Rationale:** Late deliveries happen; processing must continue; the warning preserves operational visibility.

**Business value:** Operational excellence; partner relationship.

**Strategic tier:** Operational excellence.

**Enforcement:** Test (`tests/integration/test_stale_baseline_warning.py`, planned) asserting warning emission when gap exceeds cadence.

**Owning component:** Ingestion & Profiling context.

#### BR-604: Late-Arriving File Ordering

**Statement:** Files MUST be processed in file-effective-date order, not arrival order. When a file arrives whose effective date precedes the most recent processed file, the SCD2 history MUST be rebuilt to reflect the correct sequence. Reprocessing of subsequent files MAY be required and MUST be a first-class operation, not an emergency. SCD2 rebuild during reprocess MUST be transactional with respect to Verification reads (Verification sees either the prior or the new chain, never a mixed state) per ARD §"Reprocess and Read Consistency".

**Rationale:** Partners are operationally messy. Treating late arrivals as exceptions creates emergency reruns and silent inconsistency. Treating them as routine creates a system that absorbs reality.

**Business value:** Operational excellence; member trust (Verification consistency).

**Strategic tier:** Operational excellence.

**Enforcement:** Test (`tests/integration/test_out_of_order_rebuild.py`, planned) asserting that an out-of-order arrival rebuilds SCD2 history correctly. Idempotency test (`tests/integration/test_reprocess_idempotent.py`, planned) asserting that reprocessing produces stable results. Test (`tests/integration/test_verification_during_reprocess.py`, planned) asserting Verification consistency during rebuild.

**Owning component:** Ingestion & Profiling context (Mapping Engine) + Canonical Eligibility context (SCD2 history).

#### BR-605: Reconciliation

**Statement:** The system MUST automatically reconcile its derived current member count per partner against the partner's reported count on `RECONCILIATION_CADENCE_DAYS`. Variance exceeding `RECONCILIATION_VARIANCE_THRESHOLD_PCT` MUST open an investigation ticket and emit a `RECONCILIATION_VARIANCE` event. Absence of a reconciliation reading MUST NOT be treated as success; missing readings MUST page operations.

**Rationale:** Silent drift between Lore's view and the partner's view is a high-cost defect. Periodic reconciliation catches it.

**Business value:** Operational excellence; partner relationship; revenue protection (savings attribution accuracy).

**Strategic tier:** Operational excellence.

**Enforcement:** Scheduled job presence verification (`scripts/verify_reconciliation_job.sh`, planned). Test (`tests/integration/test_reconciliation_variance.py`, planned) asserting variance trigger fires at threshold. Test (`tests/integration/test_missing_reading_alert.py`, planned) asserting missing-reading detection.

**Owning component:** Ingestion & Profiling context (Reconciliation Engine).

#### BR-606: Replay Capability

**Statement:** Full replay from the raw landing zone MUST be available at all times. Replay MUST be operator-initiated and never automatic. Replay MUST produce a parallel SCD2 chain that is swapped in atomically once verified; the prior chain MUST be retained for the audit retention window. Operators MUST be able to specify a start point for data replay (schema mapping, validation, SCD2 history derivation). Match replay defaults to full-history; partial match replay requires explicit confirmation per BR-104. Idempotency MUST be enforced per ADR-0005 (outbox pattern + processed_events) at every stage.

**Rationale:** Replay is the recovery primitive for the entire pipeline. Without idempotency, replay multiplies events; without atomicity, swaps mid-replay confuse Verification.

**Business value:** Operational excellence; HIPAA defensibility (recovery from corruption).

**Strategic tier:** Operational excellence.

**Enforcement:** Integration test (`tests/integration/test_full_replay.py`, planned) exercising full and partial replay paths. Test (`tests/integration/test_replay_atomic_swap.py`, planned) asserting atomic swap behavior. Test (`tests/integration/test_replay_prior_chain_retention.py`, planned) asserting prior chain retention.

**Owning component:** Ingestion & Profiling context (Replay Orchestrator) + Canonical Eligibility context (SCD2 swap).

#### BR-607: Replay Scope Preview

**Statement:** Before any replay executes, the system MUST present the operator with a scope preview: the number of partners, members, and SCD2 rows to be affected; expected duration estimate; storage delta estimate. Execution MUST require explicit confirmation after preview. The confirmation pattern MUST require operator to type the partner name (or "ALL" for full replay), not just click — UI design pattern per R6 U-031.

**Rationale:** Per XR-006, irreversibility separation argues against accidental large-scope reprocessing. The preview catches operator error before it becomes operator regret.

**Business value:** Operational excellence; HIPAA defensibility.

**Strategic tier:** Compliance baseline.

**Enforcement:** Integration test (`tests/integration/test_replay_confirmation_required.py`, planned) asserting that replay invocation without confirmation token fails. Test (`tests/integration/test_replay_preview_contents.py`, planned) asserting preview contents match the executed scope.

**Owning component:** Ingestion & Profiling context (Replay Orchestrator) + Operator UI.

### Domain: Right-to-Deletion

#### BR-701: Deletion Request SLA

**Statement:** Verified deletion requests MUST be executed within `DELETION_SLA_DAYS` of verification. Verification of requester identity is a precondition and MUST NOT be counted against the SLA clock.

**Rationale:** GDPR requires 30 days. CCPA requires 45 days. Default satisfies both with margin. Configurable should specific state law shift.

**Business value:** Regulatory compliance; member trust.

**Strategic tier:** Compliance baseline.

**Enforcement:** Test (`tests/integration/test_deletion_sla_breach.py`, planned) asserting that pending deletion requests past the SLA emit a `DELETION_SLA_BREACH` page event. Compliance dashboard asserting current pending-deletion ages.

**Owning component:** Deletion context (Deletion Executor + SLA tracker).

#### BR-702: Deletion Scope and Mechanics

**Statement:** Deletion execution MUST: (a) irreversibly purge the canonical member's plaintext PII from the vault, (b) tombstone the canonical member record with PII fields nulled while retaining the SCD2 history skeleton for audit, (c) preserve all audit log entries referencing the deleted identity by tokenized identifier (the token remains; the resolution from token to PII does not; vault `tombstone()` per ADR-0003), (d) remove from BigQuery analytical projection (replicated via Datastream; verify removal post-replication), (e) remove from any caches (Memorystore rate-limit, BigQuery query cache), (f) crypto-shred backups via the deletion of the encryption key for that data class (per ADR-0003 envelope encryption), (g) emit a `DELETION_EXECUTED` event. Partner-side data is outside Lore's reach; the partner MUST be notified through the BAA-defined channel but cannot be compelled by Lore's system. The raw landing zone retention (BR-302) is preserved per HIPAA "designated record set" exclusion; documented as a deliberate decision per ADR `[deletion-completeness]` (forthcoming).

**Rationale:** Deletion completeness across all data copies is required for HIPAA-grade right-to-deletion. Crypto-shredding handles backup unrecoverability without deleting backup objects.

**Business value:** Regulatory compliance; member trust.

**Strategic tier:** Compliance baseline.

**Enforcement:** Test (`tests/integration/test_detokenization_after_delete.py`, planned) asserting detokenization attempts against a deleted identity fail with a `TOMBSTONED` outcome. Test (`tests/integration/test_audit_log_token_resolves_post_delete.py`, planned) asserting audit log queries by token still resolve. Test (`tests/integration/test_deletion_bigquery_propagation.py`, planned) asserting BigQuery removal via Datastream completes within expected lag. Test (`tests/integration/test_deletion_cache_eviction.py`, planned) asserting cache eviction. Crypto-shred verification (`scripts/verify_crypto_shred.py`, planned). Partner notification path test.

**Owning component:** Deletion context (Deletion Executor) + PII Vault context + Canonical Eligibility context (BigQuery propagation) + Audit context.

#### BR-703: Re-Introduction Suppression

**Statement:** A `deletion_ledger` table MUST record a one-way HMAC-keyed hash (per ADR-0003 — not bare SHA-256) of every deleted identity's match-relevant attributes (normalized last name, dob_token, partner_member_id_token, with per-partner salt for the partner-scoped portion). The ledger MUST hold no recoverable PII. On every subsequent ingestion, candidate records MUST be hashed against the ledger using the same HMAC key. Hash matches MUST be auto-quarantined to a `SUPPRESSED_DELETED` state and MUST NOT be published to the curated layer. Re-introduction is permitted only through an explicit operator override that emits a `DELETION_OVERRIDE` audit event.

**Rationale:** Without suppression, partner re-snapshots silently re-introduce deleted identities, rendering deletion meaningless. The HMAC keying (vs. bare salted SHA-256) defeats offline brute force using the salt.

**Business value:** Regulatory compliance; member trust.

**Strategic tier:** Compliance baseline.

**Enforcement:** Test (`tests/integration/test_deletion_suppression.py`, planned) asserting that ingestion of a previously-deleted identity routes to `SUPPRESSED_DELETED`. Test (`tests/unit/test_ledger_no_recoverable_pii.py`, planned) asserting that the ledger contains no recoverable PII through any vault-side query. Test (`tests/unit/test_ledger_hmac_key_required.py`, planned) asserting bare SHA-256 cannot reproduce ledger hashes.

**Owning component:** Deletion context (Deletion Ledger) + Identity Resolution context (Suppression check).

#### BR-704: Deletion Auditability

**Statement:** Deletion request, verification, execution, and any override MUST each emit distinct audit events (`DELETION_REQUEST`, `DELETION_VERIFICATION`, `DELETION_EXECUTED`, `DELETION_OVERRIDE`). These events MUST be retained indefinitely (high-criticality tier per BR-503).

**Rationale:** Member rights enforcement requires audit trail of fulfillment.

**Business value:** Regulatory compliance; HIPAA defensibility.

**Strategic tier:** Compliance baseline.

**Enforcement:** Test (`tests/integration/test_deletion_lifecycle_events.py`, planned) asserting that the deletion lifecycle produces the expected audit event sequence with required fields.

**Owning component:** Deletion context + Audit context.

### Domain: Partner Onboarding

#### BR-801: Onboarding Gate Sequence

**Statement:** A partner MUST NOT go live in production until all of the following gates are cleared:

1. Partner-to-canonical schema mapping is documented and reviewed (`[ADVISORY]` for human review portion).
2. A representative sample feed is processed end-to-end through the quarantine path.
3. DQ baselines (BR-305) are established from the sample feed.
4. The Business Associate Agreement is executed and recorded.
5. Partner-specific configuration overrides (cadence, grace period, thresholds) are reviewed and signed off by a Data Owner (`[ADVISORY]` for sign-off; programmatic gate verifies artifact existence).
6. Partner data sharing agreement is executed (per BR-1102 forthcoming).
7. SFTP credentials are provisioned with documented rotation schedule per ADR `[partner-sftp]` (forthcoming).

**Rationale:** Onboarding errors compound. Each gate addresses a known historical failure mode in eligibility ingestion programs.

**Business value:** HIPAA defensibility; partner relationship; operational excellence.

**Strategic tier:** Compliance baseline.

**Enforcement:** Programmatic gates 2, 3, 4, 6, 7: partner-live state in the partner registry MUST require artifacts referencing all gate completions; the registry rejects activation without them. `[ADVISORY]` for gates 1 and 5 (human review portions).

**Owning component:** Partner registry (Operations) + Ingestion & Profiling context.

#### BR-802: Configuration-Driven Onboarding

**Statement:** Onboarding a new partner MUST be achievable through configuration and schema mapping alone; it MUST NOT require new deployable code. New code MAY be required for partners introducing structurally novel formats; these MUST be developed as reusable format adapters, not partner-specific code paths.

**Rationale:** Code-per-partner produces a maintenance liability that grows linearly with partner count. The system is designed to absorb 10x partner growth (NFR) without architectural change; this rule is the operational expression of that NFR.

**Business value:** Operational excellence; revenue scalability (per-partner unit economics).

**Strategic tier:** Differentiator (low marginal cost per partner is competitive).

**Enforcement:** Code review checklist item flagging partner-specific code paths (`[ADVISORY]` review portion). Static-analysis check (`scripts/check_partner_specific_branches.py`, planned) scanning for partner identifiers as conditional branch keys.

**Owning component:** Ingestion & Profiling context (Schema Registry + Format Adapters).

### Domain: HIPAA Privacy Rule Infrastructure

(New domain in synthesis baseline. Originating findings: R4 L-001 through L-008.)

#### BR-901: Notice of Privacy Practices (NPP) — §164.520

**Statement:** A Notice of Privacy Practices (NPP) MUST exist and MUST be presented to members before first PHI use. The NPP MUST be available via Lore application's first member-facing point of contact, posted prominently on Lore's website, and provided on request. Acknowledgment of receipt MUST be obtained (written or electronic). Updates to the NPP MUST be distributed when material changes are made. The NPP MUST be retained per BR-1201.

**Rationale:** §164.520 mandate.

**Business value:** Regulatory compliance; member trust.

**Strategic tier:** Compliance baseline.

**Enforcement:** Test (`tests/integration/test_npp_presentation.py`, planned) asserting NPP presentation at first PHI use. Test (`tests/integration/test_npp_acknowledgment_recorded.py`, planned) asserting acknowledgment capture. NPP authoring `[ADVISORY]` (counsel-engaged content production).

**Owning component:** Member Rights context (forthcoming) + Lore application UX (cross-team).

#### BR-902: Authorization for Use and Disclosure — §164.508

**Statement:** PHI uses outside Treatment, Payment, and Healthcare Operations (TPO) and outside §164.512 exceptions MUST require written authorization. The system MUST maintain an inventory of every PHI flow classified as TPO, §164.512 exception, or authorization-required. Authorizations MUST be tracked (when received, when revoked, scope) and honored. Sale of PHI is explicitly prohibited without authorization per §164.508(a)(4).

**Rationale:** §164.508 mandate.

**Business value:** Regulatory compliance.

**Strategic tier:** Compliance baseline.

**Enforcement:** Test (`tests/integration/test_authorization_tracking.py`, planned) asserting authorization persistence and retrieval. PHI flow classification document `[ADVISORY]` (compliance program responsibility). Sale-prohibition gate `[ADVISORY]` (no current monetization path; review at any future change).

**Owning component:** Member Rights context (forthcoming) + Compliance program.

#### BR-903: Right of Access — §164.524

**Statement:** Members MUST be able to request access to their PHI. Lore MUST respond within `MEMBER_ACCESS_RESPONSE_DAYS` (extendable once by `MEMBER_ACCESS_EXTENSION_DAYS` with written explanation). Format MUST follow member request (electronic if PHI is in EHR; paper acceptable). Reasonable cost-based fee per `MEMBER_ACCESS_FEE_SCHEDULE` MAY apply (HHS-guidance-compliant; capped to copying labor + supplies + postage). Free electronic access MUST be available if PHI is in EHR. Denials MUST be limited to specific grounds per §164.524(a)(3) and reviewed by a designated licensed healthcare professional.

**Rationale:** §164.524 mandate (legally enforceable individual right).

**Business value:** Regulatory compliance; member trust.

**Strategic tier:** Compliance baseline.

**Enforcement:** Test (`tests/integration/test_right_of_access_workflow.py`, planned) asserting workflow completion within SLA. Test (`tests/integration/test_right_of_access_response_format.py`, planned). Fee schedule document `[ADVISORY]` (counsel-authored). Denial review process `[ADVISORY]` (clinical oversight is process).

**Owning component:** Member Rights context.

#### BR-904: Right to Amendment — §164.526

**Statement:** Members MUST be able to request amendment to their PHI. Lore MUST accept or deny within `MEMBER_AMENDMENT_RESPONSE_DAYS` (extendable once by `MEMBER_AMENDMENT_EXTENSION_DAYS`). Denials MUST be limited to grounds in §164.526(a)(2) and MUST allow the member to file a statement of disagreement; the disagreement MUST be attached to subsequent disclosures of the contested record.

**Rationale:** §164.526 mandate.

**Business value:** Regulatory compliance; member trust.

**Strategic tier:** Compliance baseline.

**Enforcement:** Test (`tests/integration/test_right_to_amendment.py`, planned) asserting workflow completion. Test (`tests/integration/test_amendment_propagation.py`, planned) asserting amendment propagates to canonical model.

**Owning component:** Member Rights context + Canonical Eligibility context.

#### BR-905: Right to Accounting of Disclosures — §164.528

**Statement:** Members MUST be able to request an accounting of disclosures of their PHI for the prior `ACCOUNTING_DISCLOSURE_HISTORY_YEARS`. Lore MUST respond within `ACCOUNTING_DISCLOSURE_RESPONSE_DAYS`. The accounting MUST exclude disclosures that fall under §164.528(a)(1) exclusions (TPO, to the individual, with authorization). Non-excluded disclosures MUST emit `DISCLOSURE_TO_EXTERNAL_PARTY` audit events with required fields per §164.528(b)(2).

**Rationale:** §164.528 mandate.

**Business value:** Regulatory compliance.

**Strategic tier:** Compliance baseline.

**Enforcement:** Test (`tests/integration/test_accounting_query.py`, planned) asserting accounting query produces expected results. Audit event class enforced per BR-501.

**Owning component:** Member Rights context + Audit context.

#### BR-906: Right to Restriction — §164.522(a)

**Statement:** Members MUST be able to request restrictions on use and disclosure of their PHI. Lore MUST consider but is not generally required to agree, except when the request is for restriction of disclosure to a health plan for a service paid out-of-pocket per §164.522(a)(1)(vi). Agreed restrictions MUST be tracked and honored across all PHI flows. Whether Lore qualifies as a "health plan" for purposes of the mandatory restriction MUST be determined by counsel `[ADVISORY]`.

**Rationale:** §164.522(a) mandate.

**Business value:** Regulatory compliance; member trust.

**Strategic tier:** Compliance baseline.

**Enforcement:** Test (`tests/integration/test_restriction_tracking.py`, planned) asserting restriction persistence and enforcement. Counsel determination on health-plan classification `[ADVISORY]`.

**Owning component:** Member Rights context + every disclosure path.

#### BR-907: Right to Confidential Communications — §164.522(b)

**Statement:** Members MUST be able to request communications via specific channels (e.g., specific address, specific phone, no voicemail). Lore MUST honor reasonable requests. Communication preferences MUST be stored and respected; fallback to other channels without member authorization MUST NOT occur.

**Rationale:** §164.522(b) mandate.

**Business value:** Regulatory compliance; member trust.

**Strategic tier:** Compliance baseline.

**Enforcement:** Test (`tests/integration/test_communication_preferences.py`, planned) asserting preference enforcement. Test (`tests/integration/test_no_unauthorized_fallback.py`, planned) asserting no fallback without authorization.

**Owning component:** Member Rights context + every member communication path.

#### BR-908: Member Complaint Procedure — §164.530(d)

**Statement:** A documented complaint procedure MUST exist. Members MUST be able to file complaints concerning Lore's policies, procedures, or compliance. Complaints MUST be tracked, acknowledged within `COMPLAINT_ACKNOWLEDGMENT_DAYS`, and resolved within `COMPLAINT_RESOLUTION_DAYS` (target; not legally bound). Complaint records MUST be retained per BR-1201. Lore MUST NOT retaliate against complainants per §164.530(g).

**Rationale:** §164.530(d) mandate.

**Business value:** Regulatory compliance; member trust.

**Strategic tier:** Compliance baseline.

**Enforcement:** Test (`tests/integration/test_complaint_workflow.py`, planned) asserting acknowledgment and tracking. Non-retaliation policy `[ADVISORY]` (HR-coordinated; complaint-records-vs-employment-records audit `[ADVISORY]`).

**Owning component:** Member Rights context + Compliance program.

### Domain: Breach Notification Rule

(New domain in synthesis baseline. Originating findings: R4 L-009 through L-016.)

#### BR-1001: Discovery Definition and Clock Start

**Statement:** A "discovered breach" MUST be defined as the first day on which the breach is known to Lore or, by exercising reasonable diligence, would have been known. The HIPAA `BREACH_NOTIFICATION_INDIVIDUAL_DAYS` notification clock MUST start at discovery. Discovery decision (which event becomes a "discovered breach") MUST be documented per incident with the deciding party and basis.

**Rationale:** §164.404(a)(2) mandate. Failure to discover via reasonable diligence is itself an enforcement risk.

**Business value:** Regulatory compliance; reputation defense.

**Strategic tier:** Compliance baseline.

**Enforcement:** Detection processes (Round 3 SIEM, Round 5 monitoring) provide the "reasonable diligence" baseline. Discovery documentation per incident `[ADVISORY]` (process).

**Owning component:** Compliance program; security incident response (cross-cutting).

#### BR-1002: Breach Risk Assessment Methodology

**Statement:** Every potential breach MUST be assessed against the four-factor methodology of §164.402(2):

1. Nature and extent of PHI involved (data elements, sensitivity, identifiability)
2. Unauthorized person who used or to whom disclosure was made
3. Whether PHI was actually acquired or viewed
4. Mitigation extent (containment, recovery, recipient assurances)

The assessment MUST produce a documented determination of whether a breach occurred. Assessments MUST be retained per BR-1201.

**Rationale:** §164.402(2) framework.

**Business value:** Regulatory compliance; reputation defense.

**Strategic tier:** Compliance baseline.

**Enforcement:** Methodology document `[ADVISORY]` (counsel-authored). Per-incident assessment `[ADVISORY]` (case-by-case process).

**Owning component:** Compliance program.

#### BR-1003: Breach Notification Content

**Statement:** Breach notification content MUST include all elements per §164.404(c):

- Brief description of what happened (date of breach and date of discovery if known)
- Description of types of unsecured PHI involved
- Steps individuals should take to protect themselves
- Brief description of what Lore is doing to investigate, mitigate, and prevent recurrence
- Contact information

Pre-approved notification templates MUST exist before first production-bearing phase.

**Rationale:** §164.404(c) mandate.

**Business value:** Regulatory compliance; reputation defense; member trust.

**Strategic tier:** Compliance baseline.

**Enforcement:** Template existence `[ADVISORY]` (counsel-authored content). Per-incident populated notification reviewed by counsel `[ADVISORY]`.

**Owning component:** Compliance program.

#### BR-1004: Individual Notification Timeline

**Statement:** Affected individuals MUST be notified within `BREACH_NOTIFICATION_INDIVIDUAL_DAYS` of breach discovery (per §164.404(b)).

**Rationale:** §164.404(b) mandate.

**Business value:** Regulatory compliance.

**Strategic tier:** Compliance baseline.

**Enforcement:** Per-incident SLA tracking `[ADVISORY]` (case-by-case process). Failure-to-notify is regulatory enforcement risk.

**Owning component:** Compliance program.

#### BR-1005: Substitute Notice

**Statement:** When Lore has insufficient or out-of-date contact information for `SUBSTITUTE_NOTICE_THRESHOLD_INDIVIDUALS` or more individuals, substitute notice MUST be provided per §164.404(d)(2):

- Conspicuous posting on Lore's website for `SUBSTITUTE_NOTICE_POSTING_DAYS`, OR
- Conspicuous notice in major print or broadcast media in the geographic area where affected individuals likely reside

Plus: a toll-free number active for `SUBSTITUTE_NOTICE_TOLL_FREE_DAYS` for individuals to learn if their PHI was involved.

**Rationale:** §164.404(d)(2) mandate.

**Business value:** Regulatory compliance.

**Strategic tier:** Compliance baseline.

**Enforcement:** Procedure `[ADVISORY]` (counsel-coordinated process). Toll-free vendor capability MUST be procured before first production phase `[ADVISORY]`.

**Owning component:** Compliance program.

#### BR-1006: Media Notice

**Statement:** When a breach affects more than `MEDIA_NOTICE_THRESHOLD_INDIVIDUALS` residents in a single state, Lore MUST notify prominent media outlets serving that state per §164.406, in addition to individual notice.

**Rationale:** §164.406 mandate.

**Business value:** Regulatory compliance; reputation defense (better to lead the disclosure than be reactive).

**Strategic tier:** Compliance baseline.

**Enforcement:** Procedure `[ADVISORY]` (PR + legal coordination).

**Owning component:** Compliance program; communications.

#### BR-1007: HHS Notification

**Statement:** Breaches affecting `HHS_NOTIFICATION_THRESHOLD_INDIVIDUALS` or more individuals MUST be notified to HHS within `BREACH_NOTIFICATION_HHS_DAYS` of discovery via the HHS Breach Portal. Breaches affecting fewer individuals MUST be reported in an annual rollup by `HHS_ANNUAL_ROLLUP_DEADLINE` (typically end of calendar year following the year of discovery).

**Rationale:** §164.408 mandate.

**Business value:** Regulatory compliance.

**Strategic tier:** Compliance baseline.

**Enforcement:** Per-incident HHS portal submission `[ADVISORY]` (process). Annual rollup tracking `[ADVISORY]`.

**Owning component:** Compliance program.

#### BR-1008: HITECH Business Associate Notification

**Statement:** When a Business Associate (e.g., a partner of Lore that becomes aware of a breach affecting Lore-handled PHI) is involved, the BA MUST notify Lore within `BA_BREACH_NOTIFICATION_DAYS` (per HITECH §13402). BAA terms MUST require this notification (per BR-1102 forthcoming).

**Rationale:** HITECH §13402 mandate; BAA contractual obligation.

**Business value:** Regulatory compliance; reputation defense.

**Strategic tier:** Compliance baseline.

**Enforcement:** BAA terms `[ADVISORY]` (counsel-authored). Per-incident clock tracking `[ADVISORY]`.

**Owning component:** Compliance program; BAA contract management.

#### BR-1009: State Law Breach Notification Matrix

**Statement:** A state-by-state matrix of breach notification requirements (50 states + territories) MUST be maintained, covering: definition of breach, notification trigger, timeline, recipient requirements, format, substitute notice rules, AG notification thresholds, and credit-reporting-agency notification thresholds. The matrix MUST be authored by counsel and reviewed annually.

**Rationale:** Each state has unique statute. Lore operates US-wide; all 50 states are in scope.

**Business value:** Regulatory compliance; reputation defense.

**Strategic tier:** Compliance baseline.

**Enforcement:** Matrix existence `[ADVISORY]` (counsel-authored). Annual review `[ADVISORY]`.

**Owning component:** Compliance program (counsel-engaged).

#### BR-1010: Forensic Preservation on Suspected Breach

**Statement:** When a breach is suspected, all relevant audit logs, application logs, system snapshots, and communications MUST be preserved on legal hold per BR-1203 and the forensic preservation procedure of ADR-0008. Preserved evidence MUST be hash-attested with chain-of-custody for legal admissibility.

**Rationale:** Forensic readiness affects breach assessment quality and legal defensibility.

**Business value:** Regulatory compliance; reputation defense; litigation defense.

**Strategic tier:** Compliance baseline.

**Enforcement:** Per ADR-0008 forensic preservation procedure. Test (`tests/integration/test_forensic_preservation.py`, planned) asserting snapshot capability and chain-of-custody.

**Owning component:** Audit context + Compliance program.

### Domain: Workforce and Officer Designations

(New domain in synthesis baseline. Originating findings: R4 L-036 through L-041.)

#### BR-1101: Privacy Officer Designation — §164.530(a)(1)

**Statement:** Lore MUST designate a Privacy Officer responsible for development and implementation of HIPAA Privacy Rule policies and procedures. The Privacy Officer's identity and contact information MUST be documented in the Notice of Privacy Practices and on the Lore website. The Privacy Officer MUST be a US-resident individual.

**Rationale:** §164.530(a)(1) mandate.

**Business value:** Regulatory compliance; HIPAA defensibility.

**Strategic tier:** Compliance baseline.

**Enforcement:** Designation document `[ADVISORY]` (HR-coordinated). NPP content reference per BR-901.

**Owning component:** Compliance program.

#### BR-1102: Security Officer Designation — §164.308(a)(2)

**Statement:** Lore MUST designate a Security Officer responsible for development and implementation of HIPAA Security Rule policies and procedures. The Security Officer MUST be a US-resident individual. The same person MAY hold both Privacy Officer and Security Officer roles in smaller organizations.

**Rationale:** §164.308(a)(2) mandate.

**Business value:** Regulatory compliance; HIPAA defensibility.

**Strategic tier:** Compliance baseline.

**Enforcement:** Designation document `[ADVISORY]` (HR-coordinated).

**Owning component:** Security program.

#### BR-1103: Workforce Training — §164.530(b)

**Statement:** All workforce members MUST be trained on HIPAA policies and procedures as necessary for their function:

- Within `WORKFORCE_TRAINING_INITIAL_DAYS` after hire
- When material change in policies occurs
- At minimum annually

Training records MUST be retained per BR-1201.

**Rationale:** §164.530(b) mandate.

**Business value:** Regulatory compliance.

**Strategic tier:** Compliance baseline.

**Enforcement:** Training delivery `[ADVISORY]` (HR / Compliance). Compliance-records database tracks training completion per workforce member; report (`scripts/training_compliance_report.py`, planned) flags overdue.

**Owning component:** Compliance program; HR.

#### BR-1104: Workforce Sanctions Policy — §164.530(e)

**Statement:** A documented sanctions policy MUST exist and MUST be applied uniformly when workforce members fail to comply with HIPAA policies. Sanctions records MUST be retained per BR-1201.

**Rationale:** §164.530(e) mandate.

**Business value:** Regulatory compliance.

**Strategic tier:** Compliance baseline.

**Enforcement:** Policy document `[ADVISORY]` (HR + counsel). Application audit `[ADVISORY]` (HR records).

**Owning component:** HR + Compliance program.

#### BR-1105: Background Checks for Sensitive Roles

**Statement:** Pre-employment screening MUST occur for PII Handler, Break-Glass Admin, Privacy Officer, Security Officer, and Auditor roles. Screening criteria MUST be documented and applied uniformly per state law constraints.

**Rationale:** Insider threat mitigation; sensitive-role due diligence.

**Business value:** Regulatory compliance; insider threat resistance.

**Strategic tier:** Compliance baseline.

**Enforcement:** Policy document `[ADVISORY]` (HR + counsel; state law variation). Per-hire screening record `[ADVISORY]` (HR records).

**Owning component:** HR.

#### BR-1106: Workforce Departure Procedures

**Statement:** When privileged workforce members depart (PII Handler, Break-Glass Admin, Privacy Officer, Security Officer, Auditor, Compliance Staff), the following MUST occur:

- Day of departure: IAM access revoked; sessions terminated; MFA tokens deactivated
- Within `DEPARTURE_AUDIT_REVIEW_DAYS`: audit review of last `DEPARTURE_AUDIT_REVIEW_LOOKBACK_DAYS` of access for the departing user; sign-off by Privacy Officer + Security Officer
- For roles with persistent assets: documented role transition and handover

**Rationale:** Insider threat mitigation; departure-period risk window closure.

**Business value:** Insider threat resistance; HIPAA defensibility.

**Strategic tier:** Compliance baseline.

**Enforcement:** Procedure `[ADVISORY]` (HR + Security). IAM revocation MUST be programmatic on HR offboarding signal (test `tests/integration/test_offboarding_iam_revocation.py`, planned).

**Owning component:** HR + Security program.

### Domain: Documentation and Records

(New domain in synthesis baseline. Originating findings: R4 L-044 through L-049.)

#### BR-1201: HIPAA Documentation Retention — §164.530(j) and §164.316(b)

**Statement:** All HIPAA-required documentation MUST be retained for at least `HIPAA_DOCUMENTATION_RETENTION_YEARS` from creation or last effective date, whichever is later. Documentation in scope:

- Policies and procedures (current and prior versions)
- Communications (NPPs, authorizations, breach notifications)
- Complaints and resolutions
- Sanctions records
- Workforce training records
- Risk assessments
- BAA executions and amendments
- Incident response documentation
- Authorization records
- Accounting of disclosures records
- Restriction agreements
- Member rights request fulfillments

This retention is **separate** from operational data retention; it is the compliance evidence chain.

**Rationale:** §164.530(j) and §164.316(b) mandate.

**Business value:** Regulatory compliance; audit defensibility.

**Strategic tier:** Compliance baseline.

**Enforcement:** Documentation retention infrastructure (separate from operational data). Quarterly compliance review `[ADVISORY]`. Pre-disposal audit `[ADVISORY]`.

**Owning component:** Compliance program.

#### BR-1202: PHI Inventory and Data Mapping

**Statement:** A documented PHI inventory MUST exist and MUST be reviewed at least annually and on every architectural change affecting PHI flow. The inventory MUST cover, per data field:

- Source (which partner, which file format)
- Storage location(s) (system, instance, region)
- Processing services
- Transmission paths
- Recipients (internal roles; external parties; subprocessors)
- Retention period
- Destruction mechanism

**Rationale:** Required for risk assessment, breach response, audit defensibility, member rights fulfillment.

**Business value:** Regulatory compliance; HIPAA defensibility; operational excellence.

**Strategic tier:** Foundation.

**Enforcement:** Inventory document `[ADVISORY]` (counsel-reviewed). Annual review `[ADVISORY]`. Test (`tests/integration/test_phi_inventory_completeness.py`, planned) asserting that data fields named in the BRD's PII vs PHI classification (BR-1401) appear in the inventory.

**Owning component:** Compliance program; Architecture.

#### BR-1203: Risk Assessment Cadence — §164.308(a)(1)(ii)(A)

**Statement:** A documented risk assessment MUST be completed at least annually covering all PHI flows, controls, threats, vulnerabilities, and residual risk. Methodology MUST be documented. Findings MUST be tracked to remediation. Assessment retained per BR-1201.

**Rationale:** §164.308(a)(1)(ii)(A) mandate.

**Business value:** Regulatory compliance; HIPAA defensibility.

**Strategic tier:** Compliance baseline.

**Enforcement:** Annual risk assessment delivery `[ADVISORY]` (Compliance + Security). Documentation retained per BR-1201.

**Owning component:** Security program; Compliance program.

#### BR-1204: Policies and Procedures — §164.316

**Statement:** Written HIPAA Privacy and Security Policies and Procedures (P&P) documents MUST exist and MUST be updated when material changes occur. P&P documents are distinct from this BRD; this BRD is the technical expression of business rules, while P&P documents are the organizational operating procedures.

**Rationale:** §164.316 mandate.

**Business value:** Regulatory compliance; audit defensibility.

**Strategic tier:** Compliance baseline.

**Enforcement:** P&P document existence `[ADVISORY]` (counsel-engaged authoring). Version control and approval workflow per XR-011.

**Owning component:** Compliance program.

### Domain: Member-Facing UX

(New domain in synthesis baseline. Originating findings: R6 U-001, U-002, U-004, U-005, U-009, U-010, U-011, U-014, U-050. Round 6 raised many UX BLOCKERs; rules below capture the platform-side commitments. UX implementation details live in cross-functional UX deliverables.)

#### BR-1301: Verification Failure UX Coordination

**Statement:** Verification API failure paths (NOT_VERIFIED, lockout, friction-required) MUST be designed jointly by the Verification platform team and the Lore application UX team. Failure UX MUST satisfy XR-007 (plain language), XR-008 (multilingual), XR-009 (accessibility), and the privacy-preserving constraints of BR-401. The coordination MUST be documented in an Operational Level Agreement (OLA) per R7 E-015.

**Rationale:** Verification failure UX shapes member acquisition and trust at the most consequential moment. Privacy-preserving collapse forces UX into the Lore application; coordination is the answer.

**Business value:** Member trust; revenue protection (CAC).

**Strategic tier:** Differentiator.

**Enforcement:** OLA existence `[ADVISORY]` (cross-team document). Joint design review per release `[ADVISORY]`.

**Owning component:** Verification context (platform side); Lore application UX (cross-team).

#### BR-1302: Lockout Recovery Service Blueprint

**Statement:** When a member is locked out per BR-402, the contact-support recovery path MUST be designed as an end-to-end service (not just a phone number). The blueprint MUST cover: identity verification standard for support staff, multi-channel options, response SLA, status updates to member, multilingual support, escalation path. The blueprint MUST be documented and tested.

**Rationale:** Locked-out members are in a worst-case UX state; UX failure compounds harm.

**Business value:** Member trust; revenue protection.

**Strategic tier:** Differentiator.

**Enforcement:** Service blueprint document `[ADVISORY]` (UX + Operations + Compliance). Periodic mystery-shopper testing `[ADVISORY]`.

**Owning component:** Verification context + Member Support operations.

#### BR-1303: Personal Representative Flows

**Statement:** The system MUST support member rights workflows for personal representatives (parents of minors, guardians, POA holders, executors of deceased members). Identity verification of representative MUST be distinct from identity verification of member. Authority verification MUST require documentation appropriate to the relationship (POA document, guardianship attestation, parent attestation, death certificate + executor appointment). Audit trail MUST capture who acted on whose behalf.

**Rationale:** Personal representative flows are common in healthcare and have specific HIPAA framework (§164.502(g)).

**Business value:** Regulatory compliance; member trust.

**Strategic tier:** Compliance baseline.

**Enforcement:** Procedure `[ADVISORY]` (counsel-coordinated; state law variation). Test (`tests/integration/test_representative_flow.py`, planned) asserting representative-distinct workflow.

**Owning component:** Member Rights context.

#### BR-1304: Accessibility WCAG 2.1 AA

**Statement:** All UI surfaces (member portal, reviewer interface, operator dashboards, compliance UI, partner-facing portal) MUST meet WCAG 2.1 AA per XR-009.

**Rationale:** Per XR-009.

**Business value:** Per XR-009.

**Strategic tier:** Per XR-009.

**Enforcement:** Per XR-009.

**Owning component:** Every UI surface; Design system (forthcoming).

#### BR-1305: Trauma-Informed Design

**Statement:** Member-facing UI patterns MUST follow trauma-informed design principles (SAMHSA framework). Anti-patterns MUST be avoided: countdown timers (urgency stress), aggressive opt-in dialogs (false choice), error messages that imply user fault, "limited time offer" framing. Healthcare-context patterns MUST be documented in the UX style guide.

**Rationale:** Healthcare members frequently access services in vulnerable states; UI defaults must accommodate.

**Business value:** Member trust.

**Strategic tier:** Differentiator.

**Enforcement:** Style guide enforcement via design-system patterns. Trauma-informed review of member-facing UX `[ADVISORY]` (UX research).

**Owning component:** Design system; every member-facing UI surface.

#### BR-1306: Member Portal Scope

**Statement:** A member portal MUST exist (in Lore application or as a Lore-platform-served interface; decision per ADR `[member-portal-scope]` forthcoming) supporting: identity verification, view own eligibility data summary, submit member rights requests (Right of Access, Amendment, Accounting, Restriction, Confidential Communications), view NPP, file complaints, track request status. Identity verification at portal login MUST follow NIST SP 800-63 IAL2 or equivalent.

**Rationale:** Member rights fulfillment requires accessible channel; paper-only fulfillment is operationally infeasible.

**Business value:** Regulatory compliance; member trust.

**Strategic tier:** Compliance baseline.

**Enforcement:** Portal existence `[ADVISORY]` (delivery commitment). Identity verification standard tested per BR-1303.

**Owning component:** Member Rights context + Member portal (cross-team or platform-internal).

#### BR-1307: Plain Language and Multilingual Compliance

**Statement:** All member-facing content MUST satisfy XR-007 (plain language) and XR-008 (multilingual support).

**Rationale:** Per XR-007 and XR-008.

**Business value:** Per XR-007 and XR-008.

**Strategic tier:** Per XR-007 and XR-008.

**Enforcement:** Per XR-007 and XR-008.

**Owning component:** Every member-facing surface.

#### BR-1308: Member Harm Recovery (Impersonation)

**Statement:** When a member discovers their account was created via stolen PII (impersonation through verification), the recovery workflow MUST: enable the actual-member to prove identity through alternative factors (contemporaneous photo ID, voiceprint, in-person verification at a participating provider); lock the disputed account; investigate; restore with documented assurance. Coordination with Lore application's account state MUST be defined.

**Rationale:** Verification ≠ authentication per ADR-0009; impersonation recovery is a real case.

**Business value:** Member trust; reputation defense.

**Strategic tier:** Compliance baseline.

**Enforcement:** Procedure `[ADVISORY]` (counsel + fraud + compliance). Test `tests/integration/test_impersonation_recovery.py` (planned) asserting recovery workflow steps.

**Owning component:** Member Rights context + Verification context + Lore application (cross-team).

### Domain: Specialized Data Categories

(New domain in synthesis baseline. Originating findings: R3 S-016, R4 L-017, L-018, L-019, L-020.)

#### BR-1401: PII vs PHI Classification

**Statement:** Every data field handled by the system MUST be classified per the table below. Classification MUST be reviewed when new fields are added or when partner data scope changes.

| Field | Class | HIPAA scope | Notes |
|---|---|---|---|
| name | PII (PHI when linked to eligibility) | Yes | Always treat as PHI in this system |
| dob | PII (PHI) | Yes | |
| ssn (full) | Sensitive PII (PHI) | Yes | Extra controls per BR-1402 considerations |
| ssn (last-4) | PII (PHI) | Yes | Lower sensitivity but still in scope |
| address | PII (PHI) | Yes | Geographic re-id risk |
| phone | PII (PHI) | Yes | |
| email | PII (PHI) | Yes | |
| partner_member_id | Indirect identifier | Yes | Re-id when joined |
| eligibility status | PHI | Yes | Direct healthcare association |
| match score | Derived metadata | No (in isolation) | Links PHI in queries |
| audit metadata | Operational | No | Tokens reference PHI; metadata itself is not |

**Rationale:** Different classes have different controls (audit retention, breach notification, BAA scope). Classification must be explicit.

**Business value:** Regulatory compliance; HIPAA defensibility.

**Strategic tier:** Foundation.

**Enforcement:** Classification table maintained as source of truth. Test (`tests/integration/test_phi_classification_consistency.py`, planned) asserting classification matches PHI inventory (BR-1202).

**Owning component:** Compliance program (classification authority); every context (consuming the classification).

#### BR-1402: 42 CFR Part 2 Decision

**Statement:** Lore MUST decide whether 42 CFR Part 2 (Substance Use Disorder treatment records) applies to any partner's eligibility data. The decision MUST be documented with counsel sign-off. If Part 2 applies, additional controls (explicit consent, prohibition on re-disclosure, segregated audit) MUST be implemented per ADR `[part-2-implementation]` forthcoming. If Part 2 does not apply, the criteria for that determination MUST be documented and re-evaluated when new partners are onboarded.

**Rationale:** Part 2 is significantly stricter than HIPAA; presence of SUD-program identifiers in partner data triggers it.

**Business value:** Regulatory compliance.

**Strategic tier:** Compliance baseline.

**Enforcement:** Decision document `[ADVISORY]` (counsel-engaged). Per-partner SUD-identifier audit `[ADVISORY]` at onboarding.

**Owning component:** Compliance program (decision); Ingestion & Profiling context (filtering if Part 2 applies).

#### BR-1403: GINA / Mental Health / State-Specific Sensitive Categories

**Statement:** A per-state matrix of sensitive-data categories MUST be maintained covering at minimum: HIV/AIDS, mental health, genetic information (GINA Title I), substance use (per BR-1402), reproductive health. The matrix MUST be authored and reviewed by counsel. Categories triggering additional state-law controls beyond HIPAA MUST be enumerated. Where partner data may include such categories, additional controls MUST apply per the matrix.

**Rationale:** Multiple states have category-specific protections (CMIA in California, etc.); GINA Title I prohibits genetic-info-based health insurance underwriting.

**Business value:** Regulatory compliance.

**Strategic tier:** Compliance baseline.

**Enforcement:** Matrix existence `[ADVISORY]` (counsel-engaged). Per-partner audit at onboarding `[ADVISORY]`.

**Owning component:** Compliance program; Ingestion & Profiling context (filtering).

#### BR-1404: COPPA Scope Decision

**Statement:** Lore MUST decide whether the Lore application's scope includes members under 13 (COPPA-protected). The decision MUST be documented. If COPPA applies, the data flow MUST be COPPA-compliant (parental consent before data collection, additional notice, etc.). If COPPA does not apply, age-verification at signup MUST exclude under-13.

**Rationale:** COPPA applies to information collected from children under 13.

**Business value:** Regulatory compliance.

**Strategic tier:** Compliance baseline.

**Enforcement:** Decision document `[ADVISORY]` (counsel-engaged).

**Owning component:** Compliance program; Lore application (signup flow).

## Configuration Parameters

Every parameter named in this BRD is listed here. New parameters introduced through future amendments MUST be added to this table with full metadata. Numbers MUST appear as named parameters here; rules MUST NOT contain inline numeric literals (XR-002).

Schema: parameter | default | type | range | scope | owner role | strategic tier | referenced by

| Parameter | Default | Type | Range | Scope (override layers) | Owner role | Strategic tier | Referenced By |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `MATCH_THRESHOLD_HIGH` | TBD by tuning on synthetic data | float | 0.0-1.0 | global, per-partner | Privacy Officer + ML lead | Operational excellence | BR-101 |
| `MATCH_THRESHOLD_REVIEW` | TBD by tuning on synthetic data | float | 0.0-1.0 | global, per-partner | Privacy Officer + ML lead | Operational excellence | BR-101 |
| `GRACE_PERIOD_DAYS` | 30 | int | 0-365 | global, per-partner, per-contract | Data Owner | Operational excellence | BR-203 |
| `FEED_QUARANTINE_THRESHOLD_PCT` | 5 | float | 0.0-100.0 | global, per-partner, per-load | Data Engineering Lead | Operational excellence | BR-303 |
| `PROFILE_DRIFT_THRESHOLD` | TBD by per-field tuning | float | per-field | global, per-partner, per-field | Data Engineering Lead | Operational excellence | BR-305 |
| `BRUTE_FORCE_WINDOW_HOURS` | 24 | int | 1-168 | global | Security Officer | Compliance baseline | BR-402 |
| `VERIFICATION_LATENCY_FLOOR_MS` | 250 | int | 100-1000 | global | CTO | Differentiator | BR-404, ADR-0009 |
| `VERIFICATION_LATENCY_P99_CEILING_MS` | 500 | int | 250-2000 | global | CTO | Operational excellence | BR-404 |
| `VERIFICATION_RESPONSE_BODY_BYTES` | 256 | int | 128-4096 | global | Security Officer | Differentiator | ADR-0009 |
| `VERIFICATION_AVAILABILITY_PCT` | 99.9 | float | 95.0-100.0 | global | CTO | Compliance baseline | BR-405 |
| `VERIFICATION_AVAILABILITY_HARDBLOCK_PCT` | 99.95 | float | 99.0-100.0 | global | CTO | Differentiator | BR-405 |
| `RAW_FEED_RETENTION_DAYS` | 2555 (7 years) | int | 365-3650 | global | Privacy Officer | Compliance baseline | BR-302, BR-503 |
| `AUDIT_RETENTION_PII_YEARS` | 7 | int | 6-50 | global | Privacy Officer | Compliance baseline | BR-503 |
| `AUDIT_RETENTION_OPS_YEARS` | 2 | int | 1-7 | global | Security Officer | Compliance baseline | BR-503 |
| `AUDIT_RETENTION_AUTHN_YEARS` | 2 | int | 1-7 | global | Security Officer | Compliance baseline | BR-503 |
| `AUDIT_CHAIN_ANCHOR_INTERVAL_HOURS` | 1 | int | 1-24 | global | Security Officer | Compliance baseline | BR-504, ADR-0008 |
| `EGRESS_AUDIT_SAMPLE_RATE` | 0.01 | float | 0.0-1.0 | global | Security Officer | Operational excellence | BR-501 |
| `PARTNER_CADENCE_DAYS` | (no global default; per-partner required) | int | 1-365 | per-partner | Data Owner | Operational excellence | BR-603 |
| `RECONCILIATION_CADENCE_DAYS` | 30 | int | 7-90 | global, per-partner | Data Owner | Operational excellence | BR-605 |
| `RECONCILIATION_VARIANCE_THRESHOLD_PCT` | 0.5 | float | 0.0-10.0 | global, per-partner | Data Owner | Operational excellence | BR-605 |
| `DELETION_SLA_DAYS` | 30 | int | 1-90 | global | Privacy Officer | Compliance baseline | BR-701 |
| `MEMBER_ACCESS_RESPONSE_DAYS` | 30 | int | 15-30 | global | Privacy Officer | Compliance baseline | BR-903 |
| `MEMBER_ACCESS_EXTENSION_DAYS` | 30 | int | 1-30 | global | Privacy Officer | Compliance baseline | BR-903 |
| `MEMBER_ACCESS_FEE_SCHEDULE` | (counsel-authored; cost-based; capped) | document reference | N/A | global | Privacy Officer + counsel | Compliance baseline | BR-903 |
| `MEMBER_AMENDMENT_RESPONSE_DAYS` | 60 | int | 1-60 | global | Privacy Officer | Compliance baseline | BR-904 |
| `MEMBER_AMENDMENT_EXTENSION_DAYS` | 30 | int | 1-30 | global | Privacy Officer | Compliance baseline | BR-904 |
| `ACCOUNTING_DISCLOSURE_HISTORY_YEARS` | 6 | int | 6-7 | global | Privacy Officer | Compliance baseline | BR-905 |
| `ACCOUNTING_DISCLOSURE_RESPONSE_DAYS` | 60 | int | 30-60 | global | Privacy Officer | Compliance baseline | BR-905 |
| `COMPLAINT_ACKNOWLEDGMENT_DAYS` | 5 | int | 1-30 | global | Privacy Officer | Operational excellence | BR-908 |
| `COMPLAINT_RESOLUTION_DAYS` | 30 | int | 14-90 | global | Privacy Officer | Operational excellence | BR-908 |
| `BREACH_NOTIFICATION_INDIVIDUAL_DAYS` | 60 | int | 1-60 | global | Privacy Officer | Compliance baseline | BR-1004 |
| `BREACH_NOTIFICATION_HHS_DAYS` | 60 | int | 1-60 | global | Privacy Officer | Compliance baseline | BR-1007 |
| `HHS_NOTIFICATION_THRESHOLD_INDIVIDUALS` | 500 | int | 500-500 | global | Privacy Officer | Compliance baseline | BR-1007 |
| `HHS_ANNUAL_ROLLUP_DEADLINE` | "Feb 28 of following year" | date format | per HIPAA | global | Privacy Officer | Compliance baseline | BR-1007 |
| `SUBSTITUTE_NOTICE_THRESHOLD_INDIVIDUALS` | 10 | int | 10-10 | global | Privacy Officer | Compliance baseline | BR-1005 |
| `SUBSTITUTE_NOTICE_POSTING_DAYS` | 90 | int | 90-90 | global | Privacy Officer | Compliance baseline | BR-1005 |
| `SUBSTITUTE_NOTICE_TOLL_FREE_DAYS` | 90 | int | 90-90 | global | Privacy Officer | Compliance baseline | BR-1005 |
| `MEDIA_NOTICE_THRESHOLD_INDIVIDUALS` | 500 | int | 500-500 | global | Privacy Officer | Compliance baseline | BR-1006 |
| `BA_BREACH_NOTIFICATION_DAYS` | 60 | int | 1-60 | global | Privacy Officer | Compliance baseline | BR-1008 |
| `WORKFORCE_TRAINING_INITIAL_DAYS` | 30 | int | 1-90 | global | Privacy Officer | Compliance baseline | BR-1103 |
| `DEPARTURE_AUDIT_REVIEW_DAYS` | 7 | int | 1-30 | global | Security Officer | Compliance baseline | BR-1106 |
| `DEPARTURE_AUDIT_REVIEW_LOOKBACK_DAYS` | 30 | int | 7-180 | global | Security Officer | Compliance baseline | BR-1106 |
| `HIPAA_DOCUMENTATION_RETENTION_YEARS` | 6 | int | 6-50 | global | Privacy Officer | Compliance baseline | BR-1201 |
| `KEY_ROTATION_GRACE_PERIOD_DAYS` | 30 | int | 0-90 | global | Security Officer | Compliance baseline | ADR-0003 |
| `JWT_TTL_MAX_SECONDS` | 300 (5 min) | int | 60-1800 | global | Security Officer | Compliance baseline | ADR-0004 |
| `JWT_JWKS_CACHE_TTL_SECONDS` | 3600 | int | 300-7200 | global | Security Officer | Operational excellence | ADR-0004 |
| `JWT_REPLAY_CACHE_TTL_SECONDS` | 86400 | int | 3600-86400 | global | Security Officer | Compliance baseline | ADR-0004 |
| `MEMBER_LANGUAGE_PRIORITY_LIST` | ["en", "es"] | list[ISO 639-1] | global | Privacy Officer | Compliance baseline | XR-008 |

Parameters marked TBD MUST be tuned during the prototype phase against synthetic and partner-supplied sample data, with the tuned defaults captured in this table before production cutover.

## Non-Functional Requirements

NFRs are designated as **Commercial NFR** (contractually committed to external party — partner SLA or Lore application OLA — with remediation obligations on breach) or **Internal NFR** (operational target without external commitment).

### Latency

- Verification API p95: exactly `VERIFICATION_LATENCY_FLOOR_MS` (timing-equalized per ADR-0009). **Commercial NFR** — committed via OLA to Lore application team and via partner contracts.
- Verification API p99: at or below `VERIFICATION_LATENCY_P99_CEILING_MS`. **Internal NFR**.
- Bulk load per partner: hours to single-digit days for onboarding, scaled by volume; no hard SLA at the bulk-load level. **Internal NFR**.

### Availability

- Verification API: `VERIFICATION_AVAILABILITY_PCT` baseline. **Commercial NFR**.
- Verification API hard-block scenario: `VERIFICATION_AVAILABILITY_HARDBLOCK_PCT`. **Commercial NFR** (when applicable).

### Freshness

- Incremental feeds: same-day processing once received; daily delivery cadence as the baseline, configurable per partner. **Internal NFR**.
- Datastream lag (operational store → BigQuery): p95 ≤ 60 seconds (Phase 1 exit criterion). **Internal NFR**.
- Audit consumer lag: p95 ≤ 30 seconds. **Internal NFR**.

### Durability

- Zero data loss tolerance for partner-supplied source files. **Commercial NFR** (contractual partner data integrity).
- Full replay capability from raw landing zone at all times (BR-606). **Internal NFR**.
- Backup RPO: 15 minutes for Vault and operational store; 4 hours for analytical store. **Internal NFR**.
- Restore RTO: 1 hour for Vault and operational store; 8 hours for analytical store. **Internal NFR**.

### Scalability

- Partner count: design absorbs 10x current partner count without architectural change (BR-802 supports operationally). **Internal NFR**.
- Volume per partner: thousands to millions of members per partner. **Internal NFR**.
- Verification call volume: scales with user growth and authentication activity. **Commercial NFR** (must support partner-projected volume per BAA terms).

### Security and Privacy

- Encryption in transit and at rest as a baseline (TLS 1.2+ AEAD-only per ADR-0004; envelope encryption at rest per ADR-0003). **Commercial NFR**.
- Field-level encryption or tokenization for PII (XR-005 governs log-side; ADR-0003 governs vault-side). **Commercial NFR**.
- Role-based access control with explicit residency constraints (Role Taxonomy, BR-506). **Commercial NFR**.
- Audit trail on every PII access (BR-501). **Commercial NFR**.
- US-only PII data residency, with offshore engineering access mediated through tokenized surfaces (BR-506). **Commercial NFR**.
- Right-to-deletion handling consistent with state law obligations (BR-701 through BR-704, BR-1004). **Commercial NFR**.
- Documented BAA chain including Sequelae PH as a subprocessor. **Commercial NFR**.
- Audit chain integrity with external anchoring (BR-504, ADR-0008). **Internal NFR** (operational defense in depth).

### Operational Efficiency

- Partner onboarding via configuration, not code (BR-802). **Internal NFR**.
- Schema drift detection with alerting before bad data lands in curated layers (BR-304). **Internal NFR**.
- Idempotent reprocessing for any pipeline stage (BR-606, ADR-0005). **Internal NFR**.

### User Experience

- WCAG 2.1 AA conformance on all UI surfaces (XR-009). **Commercial NFR** (regulatory compliance; ADA Title III applicability).
- Plain language commitment per XR-007. **Internal NFR** (operational discipline).
- Multilingual support per XR-008. **Commercial NFR** (Title VI applicability).

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
| A19 | Re-introduction suppression via HMAC-keyed deletion ledger (synthesis tightening of original SHA-256 design per ADR-0003). | Conversation, R3 S-002 |
| A20 | Partner onboarding requires schema mapping, sample feed processing, DQ baseline, executed BAA, executed partner data sharing agreement, Data Owner sign-off, SFTP credential provisioning before going live. | Conversation, R3 S-016 |
| A21 | Twelve-role taxonomy: Member, Personal Representative, Reviewer, Data Engineer, Data Ops/SRE, PII Handler, Data Owner, Auditor, Privacy Officer, Security Officer, Break-Glass Admin, Compliance Staff, Partner. (Synthesis expansion from original seven-role.) | Conversation, R4 |
| A22 | Partner data delivery is file-based (SFTP or equivalent). Real-time partner-side APIs are out of scope for v1. | Brief |
| A23 | Partner feeds are full-roster snapshots, not change feeds. Diff-based CDC is the implementation pattern. | Brief |
| A24 | Daily delivery cadence is the baseline; weekly and monthly partners must be absorbable. | Brief |
| A25 | The Lore application owns user account state. The eligibility system is a source of truth that account creation reads from; it does not create application accounts directly. | Brief |
| A26 | System is greenfield for v1. Migration from a prior system is not in scope. | Brief |
| A27 | Single primary US cloud region (us-central1), multi-AZ, no multi-region active-active for v1. Cross-region DR replica in another US region per ADR `[dr-strategy]` (forthcoming). | Brief, R3 S-005 |
| A28 | AI/ML capabilities are in scope where they provide explainability. Black-box ML for identity match decisions is not appropriate. | Brief |
| A29 | Verification != authentication: VERIFIED indicates the submitted claim matches an eligible identity, not that the requester is the person whose data they're submitting. The Lore application requires additional authentication factors for account creation. (ADR-0009.) | Synthesis, R3 S-073 |
| A30 | Sequelae PH residency is enforced at request origin (geolocation), not just account residency. | Synthesis, R3 S-024 |

## Risk Register

The "Open Architectural Questions" section in prior BRD revisions is replaced by a risk register treatment. Each open question is an unresolved decision; each carries impact, owner, and decision deadline.

| ID | Risk / Open Question | Likelihood | Impact | Owner | Decision deadline | Architectural branch if unfavorable |
| --- | --- | --- | --- | --- | --- | --- |
| RR-001 | Lore's data platform stack — confirm BigQuery + Cloud Composer + AlloyDB + Cloud SQL Vault | Moderate (some uncertainty on confirmation) | Material if any element is non-confirmed (architectural rework) | CTO + Data Engineering Lead | Phase 0 exit | Substitute warehouse / orchestrator changes Pattern C and §"Deployment Topology" |
| RR-002 | Partner contract terms beyond statutory requirements (data residency, retention, BAA-specific obligations) | Moderate | Material | Partnership Operations + counsel | Per-partner onboarding | Stricter constraints surface as additional VPC-SC conditions and BAA-chain documentation |
| RR-003 | Existing identity model in Lore application | Low (likely simple user-account model) | Material if richer | CTO + Lore application Lead | Phase 0 | Verification API contract may need additional fields |
| RR-004 | HITRUST or SOC 2 attestation status and roadmap | High (decision pending) | Material (Phase 4 scope shift; partner-contract gating) | CISO + CEO | Phase 0 | Phase 4 scope changes; may pull attestation work earlier |
| RR-005 | Splink threshold defaults (production tuning vs synthetic tuning) | Moderate | Operational | ML lead | Phase 2 | Threshold deltas managed via BR-104 versioning |
| RR-006 | 42 CFR Part 2 applicability per partner | Moderate (depends on partner mix) | Material if applies (Part 2 overlays significant) | Privacy Officer + counsel | Phase 0 + per-partner onboarding | Per-partner Part 2 implementation per ADR `[part-2-implementation]` |
| RR-007 | COPPA applicability (under-13 in scope) | Low | Material if applies | Privacy Officer + counsel | Phase 0 | COPPA-compliant data flow + consent infrastructure |
| RR-008 | Vendor concentration risk (GCP) acknowledged by board | Low (catastrophic), Moderate (adverse change) | Existential (catastrophic) / Material (adverse) | CTO + CEO + Board | Phase 0 | Multi-cloud abstraction expansion in TokenizationService and other primitives |
| RR-009 | Member portal scope: built by Lore application or by Lore eligibility platform | Decision pending | Material (delivery scope) | CTO + Lore application Lead | Phase 0 | Scope re-allocation between teams |
| RR-010 | Reviewer interface: built in-house or third-party | Decision pending | Operational | Engineering Lead | Phase 1 | Build vs. buy ADR forthcoming |

## Enforcement Mechanism Inventory

This table maps each Constitutional priority and rule to its enforcement mechanism with honest status:

- **LIVE** — gate exists and fires today (in current Phase 00 harness or earlier-completed work)
- **PLANNED** — gate is specified in this BRD/ARD; will be built before the BR's owning component goes live
- **`[ADVISORY]`** — cannot be programmatically enforced; relies on process, audit, or human judgment

| Rule | Mechanism | Status |
|------|-----------|--------|
| Constitution Priority 0 (Security) | gitleaks, detect-secrets, bandit in pre-commit + CI | LIVE |
| Constitution Priority 0 (HIPAA / PII handling) | PII vault isolation enforced via import-linter contracts; structlog redaction; PII-in-fixtures gate | LIVE |
| XR-001 (Layered Configurability) | CI lint for inline literals; resolution-order test | PLANNED |
| XR-002 (No Magic Numbers) | CI lint; reviewer checklist | PLANNED |
| XR-003 (Privacy-Preserving Collapse) | Integration test for state collapse; static analysis preventing internal enum import; latency-distribution test (ADR-0009) | PLANNED |
| XR-004 (Identity-Scoped Lockouts) | Integration test exercising IP rotation and spelling variation | PLANNED |
| XR-005 (Zero PII in Logs) | structlog redaction processors; CI fixture redaction gate; production sampling job | LIVE (logging + fixture); PLANNED (production sampling) |
| XR-006 (Irreversibility Separation) | Code-path inventory; confirmation-token signature; module isolation | PLANNED |
| XR-007 (Plain Language) | CI gate on Flesch-Kincaid; content design CODEOWNERS | PLANNED |
| XR-008 (Multilingual) | Test for required content in supported languages; CI gate on translation coverage | PLANNED |
| XR-009 (WCAG 2.1 AA) | CI accessibility gate (axe / Lighthouse); per-release manual audit; annual third-party audit | PLANNED (CI gate); `[ADVISORY]` (manual + annual) |
| XR-010 (Configuration Discipline) | CI parameter-schema validator; load-time validation test | PLANNED |
| XR-011 (Decision Authority) | CI gate on PR amendments to BRD/ARD/ADR | PLANNED |
| XR-012 (Bidirectional Traceability) | CI gate validating BR-to-component and component-to-BR mappings | PLANNED |
| BR-101..105 (Identity Resolution) | Per-tier unit tests; integration tests for tier ordering, queue entry, version stamping | PLANNED |
| BR-201..206 (Lifecycle) | DB constraint; transition-coverage test; per-attribute survivorship tests; per-transition-class audit emission | PLANNED |
| BR-301..306 (Data Quality) | Tier-assignment validation; per-tier behavior tests; threshold boundary tests | PLANNED |
| BR-401..405 (Verification API) | (Per XR-003 + XR-004); three-tier progression test; performance monitoring; latency-distribution test (ADR-0009) | PLANNED |
| BR-501..505 (Audit) | Per-event-class emission tests; access control tests; hash-chain validator (ADR-0008) | PLANNED |
| BR-506 (Sequelae PH) | IAM audit script; offshore-principal detokenization test; cross-border data flow audit | PLANNED |
| BR-601..607 (Ingestion) | Per-step idempotency tests; replay path tests; reconciliation tests | PLANNED |
| BR-701..704 (Deletion) | End-to-end deletion test; ledger no-recoverable-PII test; suppression test | PLANNED |
| BR-801..802 (Onboarding) | Partner registry activation gate; partner-conditional branch static analysis | PLANNED + `[ADVISORY]` portion |
| BR-901..908 (Privacy Rule) | Workflow tests for each member right; complaint workflow test | PLANNED + `[ADVISORY]` for counsel-engaged work |
| BR-1001..1010 (Breach Notification) | Detection processes per Round 3/5; per-incident `[ADVISORY]` (case-by-case) | LIVE (detection); `[ADVISORY]` (per-incident) |
| BR-1101..1106 (Workforce) | Per-role designation `[ADVISORY]`; offboarding IAM revocation test | LIVE (designations done in Phase 0); PLANNED (IAM revocation test) |
| BR-1201..1204 (Documentation / Records) | Documentation retention infrastructure; PHI inventory completeness test; risk assessment cadence | PLANNED + `[ADVISORY]` |
| BR-1301..1308 (Member-Facing UX) | Various per-rule (see each rule); largely cross-functional | PLANNED + `[ADVISORY]` |
| BR-1401..1404 (Specialized Data Categories) | Classification consistency test; per-category decision documents `[ADVISORY]` | PLANNED + `[ADVISORY]` |

## Bidirectional Cross-Reference Index

Every BR maps to one or more architectural components in the ARD. The complete BR → component mapping is maintained in this BRD §"Owning component" of each rule. The complete component → BR mapping is maintained in the ARD §"Bidirectional Cross-Reference Index". CI gate (XR-012) verifies completeness in both directions.

## Closing Note

This BRD is the contract between the problem space and the architecture. Any change to a business rule, cross-cutting rule, or configuration parameter is a contract change and MUST be reflected in updated tests before implementation proceeds. Amendments MUST follow the change request process per XR-011.

The strategic context in which this BRD operates lives in upstream business documents in the corporate strategy repository; this BRD is the technical expression of those strategic intents and references them rather than duplicating.
