# Lore Eligibility: Case Study Walkthrough

A working prototype and architectural narrative for the Lore Health Staff
Data Engineer panel interview, Case Study 3.

This document is the panel-facing read. Depth lives in
`docs/BUSINESS_REQUIREMENTS.md` (BRD) and `docs/ARCHITECTURE_REQUIREMENTS.md`
(ARD); this walkthrough surfaces the load-bearing decisions and points
into those documents where appropriate.

The prototype itself is in `prototype/`, runnable with
`make dev-db-only && make prototype-demo`. The end-to-end test
(`prototype/tests/test_e2e_demo.py`) asserts every numbered acceptance
criterion in the PRD. As of this writing the suite is 153 tests green.

## 1. Problem framing

Lore is a Medicare ACO. Revenue comes from shared savings against reduced
total cost of care for a defined population. That population is defined by
partner-supplied eligibility data. Eligibility data is therefore not a
peripheral concern: it is the operational mechanism by which Lore
identifies whose health outcomes count against which partner's savings
calculation. An incorrect canonical identity means clinical context bleeds
across people, attribution misroutes savings credit, and a member who
asked to leave is silently re-onboarded the next day. Bad eligibility data
is a clinical-trust problem before it is a financial one.

Three structural challenges shape the work. Inbound feeds are
heterogeneous in format, schema, and freshness. Inbound feeds carry
quality issues that range from typos to missing fields to schema drift
between days. The data is regulated under HIPAA, HITECH, state laws like
CCPA/CPRA, the Washington My Health My Data Act, and partner contractual
requirements that may exceed any of those.

The system has two operational uses. First, identity verification when a
member tries to access Lore: the verification API answers "is this
person an eligible Lore member, yes or no." Second, source-of-truth for
account creation: the curated eligibility store is what the Wayfinding
squad reads from when they create a new application account.

The system supports two operational modes that share infrastructure.
Initial bulk load is the first time a partner sends a full roster.
Continuous incremental updates reflect attrition, new enrollments, and
attribute changes within each partner's pool. The prototype treats both
as snapshot-diff against the prior snapshot per BR-602; partners rarely
deliver true change feeds, so a snapshot-diff approach is the realistic
default.

## 2. Strategic vision

The eligibility system is built as a set of bounded contexts treated as
data products, not as a monolithic warehouse. Each context owns its
schema, its freshness, and its quality SLOs. The contexts are:

- Ingestion and Profiling. Reads partner files, applies per-partner
  mapping configuration, runs DQ rules, profiles distributions.
- Identity Resolution. Tier 1 deterministic plus Splink-on-DuckDB for
  Tiers 2-4. Output: a canonical member with one or more partner
  enrollments.
- Canonical Eligibility. The operational source of truth. Six tables:
  `canonical_member`, `partner_enrollment`, `member_history` (SCD2),
  `match_decision`, `deletion_ledger`, `review_queue`. Schema is in
  ARD §"Data Schemas".
- Verification. The only public surface. Returns
  `{VERIFIED, NOT_VERIFIED}` and nothing else.
- Deletion. Right-to-deletion executor plus suppression check on
  re-introduction.
- Member Rights. HIPAA Privacy Rule infrastructure: NPP presentation,
  authorization tracking, and member rights fulfillment (access,
  amendment, accounting, restriction, confidential communications,
  complaints). Out of prototype scope; the production system carries
  this as a distinct bounded context per AD-029.
- Audit. Append-only JSONL hash chain in the prototype; Pub/Sub plus
  GCS Bucket Lock in production.
- PII Vault. Random tokens for non-joinable PII; deterministic
  non-FPE tokens for joinable identifiers.

Pattern C separation runs through everything. The operational tier holds
a bounded history window (90 days per AD-005) and serves low-latency
verification reads. The analytical tier holds unbounded history and
serves data science access. Replication between them is one-way, async,
and tokenized: the analytical tier never holds plaintext PII.

Onboarding a new partner is a configuration change, not a code change.
Format adapters are code-resident per format family, one for CSV, one
for JSON, one for fixed-width, etc. (AD-016). Per-partner mapping rules
live in YAML files in a versioned registry. Adding partner number three
in the prototype is exercised by `test_third_partner_onboarded_via_yaml_only`:
a brand new YAML, no Python edits. That property is what makes the
system absorb partner growth without becoming an engineering bottleneck.

## 3. Identity resolution as the technical heart

Identity resolution is the part of this system that determines whether
the work is defensible at Staff level or not. SQL JOINs do not solve it.
Two records are the same person when their first name matches, their
last name has a one-character typo, their date of birth matches, their
SSN last four matches, and their address has a format difference but
the same underlying location. A literal JOIN finds none of those.

The match policy is BR-101. Four tiers:

- Tier 1, deterministic. A new record matches an existing canonical
  member exactly on (partner_id, partner_member_id) plus last name plus
  date of birth. Auto-merge, no scoring needed. This is the day-2
  ingest path when a partner re-sends a roster: most records resolve
  here in milliseconds via index lookups.
- Tier 2, probabilistic high. Splink computes a match weight; weights
  at or above the auto-merge threshold (default 5.0, tuned during
  prototype work) auto-merge with the per-comparison breakdown stored
  on `match_decision.score_breakdown`.
- Tier 3, probabilistic mid. Weights between the review threshold and
  the auto-merge threshold land on the manual review queue. Reviewers
  see tokenized references and the score breakdown so they can audit
  the model's reasoning before clicking MERGE or DISTINCT.
- Tier 4, distinct. Below the review threshold, treated as a new
  identity.

Splink (AD-011) is the implementation choice for Tiers 2 through 4. It
is a Python library implementing the Fellegi-Sunter probabilistic record
linkage model. It is open source, actively maintained, and supports
multiple SQL backends through SQLGlot. Crucially, Splink reports per-
comparison Bayes factors on every prediction. Each pair carries
`bf_first_name`, `bf_last_name`, `bf_dob`, `bf_ssn_last4`, etc.,
showing exactly how each field contributed to the score. That is the
property that lets the system explain a merge to a compliance auditor
or a clinical reviewer rather than pointing at a black box.

The backend choice is split. In the prototype Splink runs on DuckDB
for in-process, file-backed execution that needs no infrastructure.
In production v1 Splink runs on BigQuery so partner-scale data lives
where the rest of the analytical stack does (AD-012). The Spark backend
stays in reserve for partner growth beyond BigQuery's slot economics.

Worked example. The synthetic harness seeds two cross-partner near-match
truths. Truth T00005: same person on PARTNER_A and PARTNER_B with a
last-name typo. Truth T00010: same person with an address format
difference. Running `make prototype-h2` produces:

```
Truth T00005: PARTNER_A:A00005 <-> PARTNER_B:B90000
  tier   = TIER_2_PROB_HIGH
  weight = 39.926
  per-comparison breakdown:
    bf_dob          = 30167.567
    bf_first_name   = 178.735
    bf_last_name    = 1082.568
    bf_ssn_last4    = 7938.833
    bf_street       = 538.947
```

A weight of 39.926 is well above the 5.0 auto-merge threshold. The
breakdown shows that DOB and SSN-last-4 dominate the decision: the
identity holds even with the name typo because the strong identifiers
align. That is exactly the auditable-decision property a clinical-
trust audience needs to see.

## 4. PII governance and audit

Two architectural decisions do most of the compliance work.

First, the two-token-class pattern (AD-009). PII fields split into
joinable identifiers and non-joinable PII. Joinable identifiers (last
name, DOB, SSN-last-4, partner-assigned member ID) get deterministic
non-FPE tokens via HMAC-SHA-256 with a per-environment salt. Production
wraps the salt with Cloud KMS; the prototype uses a fixed dev salt.
Cross-partner identity resolution can compare tokens directly and the
plaintext never leaves the vault. Non-joinable PII (street, phone,
email, full SSN) get random tokens whose plaintext lives only in the
vault, accessible only to authenticated paths with explicit audit
emission. Tombstoning a token nulls the plaintext while leaving the
token row referenceable, so historical audit events resolve cleanly to
"deleted" rather than dangling.

Second, the audit chain. Every state change emits an audit event:
`FEED_INGESTED`, `MATCH_RESOLVED`, `DELETION_REQUESTED`,
`DELETION_EXECUTED`, `SUPPRESSED_DELETED`, `STATE_TRANSITION`. In
production these go to a Pub/Sub topic that fans out to a GCS
Bucket-Lock'd object store with a hash chain. In the prototype they
go to an append-only JSONL file with the same hash chain shape: each
entry's `prior_event_hash` is the previous entry's `self_hash`,
computed as SHA-256 over the canonical JSON of all other fields.
Tampering with any entry breaks the chain at that line. The
end-to-end test demonstrates this:
`test_demo_chain_tampering_is_detected` mutates one event's outcome
field on disk and confirms validation fails at the right line.

XR-005 is the operational contract: zero plaintext PII in any log
line. The prototype enforces this two ways. First, every code path
that writes to the application logger uses tokenized references and
request_ids only; `test_logs_contain_no_plaintext_pii` runs a full
verify request with caplog turned on and asserts the plaintext never
appears in any record. Second, after the demo runs, the redaction
scanner regex-passes the audit chain looking for SSN, US-format date,
phone-with-area-code, and email patterns. The end-to-end test
asserts zero matches: `test_redaction_scan_zero_matches`.

Cross-border data residency deserves a separate sentence. Lore's
engineering organization in the Philippines is real; their PII access
posture is enforced architecturally rather than organizationally. The
analytical tier is what they reach: tokens only, no plaintext PII. The
PII vault sits inside an inner VPC-SC perimeter (BR-506) restricted to
US-resident principals. This is documented in the deliverable as an
architectural decision because telling the panel "we'll write a policy"
is not a defensible answer to data residency.

## 5. Cleansing in action

The data pipeline runs in this order:

1. Format adapter reads CSV (one of N format families per AD-016).
2. Mapping engine projects source columns onto canonical fields per
   the partner YAML, parses dates to ISO, derives ssn_last4 from
   full SSN when present, and records parse errors per record.
3. DQ engine applies BR-301 through BR-305 in one pass.
4. BR-601 within-feed dedup keeps the last-seen record per
   (partner_id, partner_member_id).
5. Identity resolution checks Tier 1 against existing canonical, then
   sends the rest to Splink.
6. Pre-publication suppression check queries deletion_ledger; hits
   route to SUPPRESSED_DELETED rather than ELIGIBLE_ACTIVE.
7. Persistence inserts canonical_member, partner_enrollment, and
   match_decision rows. Day 2 also opens member_history rows for
   SCD2 closure.

The DQ engine encodes the BRD's data-quality contract as code. BR-301
field tiers are declared per-partner in YAML; required-tier failures
quarantine the record per BR-302. BR-303 fires when more than 5
percent of records would be quarantined: the feed itself is rejected,
nothing publishes, a human is paged. BR-304 schema drift is split:
additive columns auto-accept with a notification (the day-2
PARTNER_A feed in the prototype adds an `EligibilityStartDate`
column and runs cleanly); subtractive or type-narrowing changes
quarantine the feed wholesale. BR-305 profile baselines per partner
are persisted as JSON; subsequent feeds compare null-rate per field
and emit a `PROFILE_DRIFT` event when the change exceeds threshold.

The supporting H2 snippet (`prototype/snippets/h2_dedup_query.sql`)
shows BR-601 dedup as window-function SQL with an audit emission
that uses `name_token` only, never plaintext name. Two parts: one
SELECT identifies winners and losers per (partner_id,
partner_member_id) with `ROW_NUMBER() OVER (...)`, one INSERT
emits one `WITHIN_FEED_DEDUP` audit event per winner with the
duplicate count and kept line number in `context`. This is the
literal "duplicate PII" example the case prompt asks for. The Splink
snippet handles the harder near-duplicate case the SQL cannot.

## 6. Identity verification design

The verification API is the only public surface. Its public response
set is exactly `{VERIFIED, NOT_VERIFIED}` (BR-401). Five different
internal states map to NOT_VERIFIED: not-found, PENDING_RESOLUTION,
ELIGIBLE_GRACE, INELIGIBLE, DELETED. The end-to-end test enumerates
all five and confirms identical response shape across every one.
This is XR-003 privacy-preserving collapse: distinguishing "you exist
but are ineligible" from "you do not exist" leaks PHI association to
anyone who can call the endpoint.

Privacy-preserving collapse extends to timing. BR-404 sets a 200ms
p95 latency target; the prototype API enforces a 50ms response floor
that equalises VERIFIED and NOT_VERIFIED response time. Without that,
a careful attacker could time-discriminate between the lookup-hit
and lookup-miss paths and infer membership. The
`_equalise_latency` helper is one short function; the test suite
verifies both response shapes are identical.

BR-402 progressive friction handles brute-force probes. A failure log
keyed on the resolved-identity anchor `(name_token, dob_token)` counts
failures within a configurable window. Three failures inside the
window flip a lockout flag scoped to that anchor; subsequent verify
attempts on that anchor short-circuit to NOT_VERIFIED regardless of
whether the input is correct. A successful verify on the same anchor
clears the failure window. The lockout scope is per-anchor, not per-
client, so an attacker rotating client IDs cannot side-step it. The
prototype does this in-memory; production wires Redis with the same
contract.

The integration shape Wayfinding consumes:

```http
POST /v1/verify
Content-Type: application/json

{
  "claim": {
    "first_name": "...",
    "last_name": "...",
    "date_of_birth": "YYYY-MM-DD",
    "ssn_last_4": "..."  // optional
  },
  "context": {
    "client_id": "wayfinding-prod",
    "request_id": "..."
  }
}

200 OK
{ "status": "VERIFIED" | "NOT_VERIFIED" }
```

Three failure modes Wayfinding needs to handle: lockout on the same
identity, transient 5xx (retry with idempotent request_id), and the
plain NOT_VERIFIED path. The contract exposes all three via the
single status field plus standard HTTP semantics. No deferred-account
state, no in-system manual-review escalation from the user-facing
surface (BR-403); failure routes the user to contact-support only.

## 7. Phased delivery and what is prototyped

The ARD lays out five phases:

- Phase 0, Foundation. Empty production substrate, governance roles
  designated, open ADRs scoped. Eighty stories in the synthesis
  backlog spanning engineering, security, compliance, UX, and
  infrastructure tracks. Includes Privacy Officer and Security
  Officer designations, PHI inventory, P&P content, 42 CFR Part 2
  decision, attestation roadmap, and BAA chain — not plumbing alone.
- Phase 1, Single-Partner End-to-End. The full pipeline against one
  real partner. This is what the prototype scopes against.
- Phase 2, Production Cutover. Real eligibility data, real verification
  traffic. Cutover from any prior system.
- Phase 3, Scale to N partners. Onboarding playbook, capacity tuning,
  partner-specific contract handling.
- Phase 4, Hardening and Attestation. SOC 2 Type II or HITRUST CSF
  prep, runbooks, DR drills.

The prototype is a scoped subset of Phase 1 running on a local
substrate. Per the ARD's "Stubbed for Prototype" section: Cloud KMS
becomes a fixed dev salt, GCS Bucket Lock becomes an append-only
JSONL hash chain, Datastream becomes a periodic sync script,
VPC-SC perimeters are documented but not enforceable locally, the
manual review queue exists as a Postgres table without a UI,
Cloud Composer becomes a Python orchestrator (`prototype/demo.py`).

What does run end-to-end against synthetic data on local Postgres +
DuckDB:

- Day 1 ingest: PARTNER_A and PARTNER_B feeds with seeded
  problematic rows, deduped, validated, identity-resolved by Splink,
  persisted to canonical store.
- Deletion: the deletion fixture member is operator-deleted with a
  strict-tuple suppression hash and a broad (dob, ssn_last4)
  suppression hash. The canonical row is tombstoned. Audit events
  emitted.
- Day 2 ingest: the deletion-fixture identity is re-introduced via
  PARTNER_B with a name typo. Pre-publication suppression check
  catches it on the broad hash; the record routes to
  SUPPRESSED_DELETED automatically. SCD2 history rows are written
  for the deletion closure plus new day-2 canonical members.
- Audit chain: every step emits an event. Hash chain validates
  start-to-end. Tampering with any entry on disk is detected at the
  exact failed line.
- Redaction scanner: runs over the audit chain, reports zero matches
  against SSN, date, phone, and email patterns.
- Verification API: handles all four canonical states plus not-found
  with identical response shape.

`make prototype-demo` executes all of the above against the dev
Postgres in roughly five seconds. `prototype/tests/test_e2e_demo.py`
is the same flow with assertions; the suite runs in CI green.

## 8. What I would ask in week one

The case-study prompt forbids clarifying questions, so the BRD and
ARD list assumptions where a real engagement would ask. Here are
the highest-value questions for week one:

1. What is the existing data platform stack? Cloud provider,
   warehouse or lakehouse, orchestrator, transform tooling. The
   ARD assumes BigQuery + Cloud Composer; if Lore self-manages
   Airflow on GKE the orchestration section adapts.
2. What is the current partner count and the projected count at 12
   and 24 months? The Phase 3 capacity work is sized off this.
3. What does the existing identity model in the Lore application
   require beyond eligibility verification? If the application has
   richer identity primitives (preferred name, pronouns, contact
   preferences) the verification API contract may need additional
   fields beyond `{VERIFIED, NOT_VERIFIED}`.
4. Are there existing partner contracts with data-handling
   requirements stricter than statute? Phase 0's BAA work depends
   on this.
5. What is the Philippines engineering organization's permitted
   PII access posture? The architecture assumes "tokenized analytical
   surface only"; if that is wrong the inner VPC-SC perimeter
   shrinks or expands.
6. Where is Lore on HITRUST or SOC 2? Phase 4 scope shifts
   accordingly.
7. Is there an existing identity-resolution approach in production?
   If so, what does it use and what is its observed false-merge
   rate? Splink is the proposal but the migration path matters.
8. How does eligibility loss interact with account state? Soft
   deactivate, hard close, grace period? The state machine and
   GRACE_PERIOD_DAYS default need this answer to be defensible.
9. Which partners are in the initial onboarding wave, and what
   formats do they actually deliver? The two-format-family
   assumption (CSV + one other) holds for now.
10. How reliable is SSN as a deterministic match key in the
    real partner data? The prototype's tier policy assumes
    SSN-last-4 is usable; if SSN coverage is much lower than
    expected, Tier 1 logic shifts.

These are conversation starters, not gaps in the proposal. Every
one is recorded as an explicit assumption in the BRD and ARD with
a stated default; week one would tighten the defaults against
ground truth.

## Closing note

The prototype demonstrates the load-bearing pieces of the design on
synthetic data. It is intentionally bounded: cloud services stubbed,
no UI, no real partner integration, no attestation work. What it does
prove, in code and in passing tests, is that the architectural
decisions hold together: identity resolution produces explainable
matches, PII isolation survives the deletion path, the audit chain
detects tampering, the verification API does not leak internal state.
The path from this prototype to Phase 1 production is the work the
ARD's phased delivery plan describes. The path is what week one
conversations turn into commitments.

## Appendix: lens-specific framing for the panel

The same eight sections, with emphasis tuned to each interviewer's
concern.

**Mike Griffin (Wayfinding squad).** The integration contract is
section 6. The verification API is the only surface Wayfinding
sees. Three failure modes are explicit and uniform: lockout, 5xx
retry, and plain NOT_VERIFIED. The status field is the only public
state; no schema migrations on the response shape; no leaked internal
states. Section 5's pipeline-flow narrative explains why
NOT_VERIFIED can mean five different things internally without
Wayfinding having to know.

**Jonathon Gaff (data engineering).** Sections 2, 3, and 4. The
bounded-context architecture is the strategic frame. Splink-on-
DuckDB-on-prototype, Splink-on-BigQuery-on-production is the
technical core; AD-012 gives the migration path. The two-token-class
pattern with the joinable/non-joinable split is the PII isolation
move that materially reduces blast radius. The audit hash chain is
the irreversible-ledger primitive that makes the rest defensible.

**Adam Ameele (clinical context).** Section 1's framing is the lead.
Bad eligibility data is a clinical-trust failure: a wrong identity
merge means clinical context bleeds across people; a partial
deletion means a person who asked to leave is silently re-onboarded.
Section 3's worked example matters here: the Splink decision is
auditable down to the per-comparison weight, so a clinical reviewer
can ask "why did the system decide these two records are the same
person" and get an answer that is not "the model said so." Section 4
reframes XR-005 (zero PII in logs) as a clinical-trust requirement,
not an engineering one: the people inside the system seeing
plaintext PII unnecessarily is itself a breach of the trust the
member extends when they hand Lore their identity.
