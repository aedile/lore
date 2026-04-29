# Architecture Review — Round 1: Principal Architect

| Field | Value |
|---|---|
| **Round** | 1 of N (multiple specialty rounds planned) |
| **Reviewer lens** | Principal Architect — breadth across domains, correctness of decomposition, completeness, fitness-for-purpose, hidden tradeoffs |
| **Documents** | `docs/BUSINESS_REQUIREMENTS.md` (BRD), `docs/ARCHITECTURE_REQUIREMENTS.md` (ARD) |
| **Date** | 2026-04-29 |

This review uses the Constitution's triage taxonomy (Rule 29):

- **BLOCKER** — must fix before any backlog work; correctness, security, data integrity, or HIPAA defensibility issue
- **FINDING** — should fix before backlog or document as a deferred ADR with explicit owner and target phase
- **ADVISORY** — log for awareness; address opportunistically

This is the *principal architect's* review. Subsequent rounds (data-engineering principal, security/red-team architect, infra/DevOps architect, clinical-trust reviewer) will go deeper in their specialty. Where I notice something a specialty review should dig into, I flag it as such rather than fully resolving it here.

---

## TL;DR

**Will the platform be well-engineered if we proceed as-is? No, not quite.**

The BRD and ARD are well-structured and substantively correct in their cores. The bounded-context decomposition, Pattern C operational/analytical split, TokenizationService abstraction, and Sequelae PH residency story are solid principal-architect-grade choices. The reverse-mapping table proves BR coverage. Phase exit criteria are objective.

But there are six **BLOCKERS** and a non-trivial set of **FINDINGS** that, left unaddressed, would produce a system that:

1. Has correct architectural shape but unknown capacity, cost, and scaling behavior
2. Is HIPAA-defensible against organized adversaries on paper but has at least two real-world re-identification side channels
3. Has no convincing answer for the operational-reality cases (canonical-identity unmerge, vault disaster recovery, partner SFTP credential lifecycle)
4. Treats the identity-resolution model as a static config rather than a system component with its own lifecycle

The gaps are addressable. None require redesigning the core. Most can be resolved with focused additions to the ARD, a small set of new ADRs, and one or two structural decisions before backlog work begins.

---

## Strengths to preserve

These are the load-bearing decisions. Round 2+ reviews should not relitigate them without a strong reason.

1. **Seven-context decomposition (AD-001).** Clean separation of concerns. Each context is a deployable, an ownership boundary, and a data product. Nothing is split awkwardly.
2. **Pattern C — operational/analytical split with directional CDC (AD-004).** The right answer for the latency contract on Verification (BR-404). Datastream is the right v1 mechanism; the pattern is preserved if it's replaced later.
3. **TokenizationService abstraction (AD-008, AD-009).** The Vault is a swappable backend behind a stable interface. Skyflow / self-hosted Vault is a forward path. Token-class declaration in config, not implicit, is correct.
4. **Sequelae PH boundary as architecture, not policy (AD-003, BR-506).** IAM Workspace conditions plus inner VPC-SC perimeter is the right level. Architectural enforcement, not honor-system.
5. **Privacy-preserving collapse (XR-003, BR-401).** Two-state response set is correct. Latency-equalization called out (though see F-005).
6. **Reverse-mapping table at the end of the ARD.** Every BR maps to a component. That's a real audit artifact.
7. **Phase exit criteria with objective measures.** Each phase ends on something testable, not on opinion.
8. **Configuration as code under Git review (XR-001).** Per-partner YAML in a versioned registry is the correct mechanism for BR-802's no-new-code-per-partner requirement.

---

## BLOCKERS (must address before backlog)

### F-001: NFR engineering — capacity, sizing, throughput model are absent — BLOCKER

**Where:** ARD §"Deployment Topology" mentions "minimum size" for AlloyDB; ARD §"Phased Delivery" Phase 0 says "minimum size"; nowhere does the ARD compute or target concrete capacity numbers.

**Why it matters:** The BRD has hard NFRs — verification p95 ≤ 200ms, 99.9% availability, partner volumes from thousands to millions of members, 10x partner-count headroom. None of these have an architectural budget. Without a capacity model, every backlog ticket assumes a different ceiling. The first real load test will be the first time anyone discovers a wrong assumption.

**What's needed:**
- A capacity model section in the ARD. At minimum: peak verification QPS estimate, AlloyDB CPU/RAM/IOPS sizing rationale at v1 and at 10x scale, BigQuery slot budget at v1 and projected, KMS operations budget per partner-day, Cloud Run concurrency-per-instance for each stateless service, Pub/Sub backlog ceiling.
- Each NFR (BR-404, BR-405, plus the implicit ones — partner-count headroom, member-count headroom, verification QPS headroom) maps to a sizing assertion and a load-test gate that proves it.
- Headroom budget: how much margin between v1 sizing and the 10x-partner ceiling? At what point does sizing-based scaling fail and architectural change become required?

**Effort:** M (1-2 days of capacity sketching + a sizing ADR).

**Hand-off:** Round 2 (Infra/DevOps Architect) goes deeper on actual GCP service sizing.

---

### F-002: Bulk vs. incremental ingestion code-path unification is not stated — BLOCKER

**Where:** BRD success criterion #4: "A unified bulk and incremental design that does not treat them as separate systems with separate code." ARD §"Ingestion & Profiling" describes the daily incremental flow. ARD §"Phased Delivery" Phase 1 calls it "single-partner end-to-end." Bulk historical onboarding is implicit in BR-606 (replay) and Phase 3 (multi-partner onboarding) but never explicitly the same code path.

**Why it matters:** This is a stated success criterion of the deliverable. Bulk loads have different shapes than daily incrementals — different volumes, different DQ tolerances, different Splink batch sizes, different latency tolerances. A "unified" design has a single code path with knobs. A "let's just write a bulk-loader script" design has two systems with eventual divergence.

**What's needed:**
- An explicit ARD section: "Bulk and Incremental — One Pipeline, Two Profiles." Enumerate the knobs (batch sizes, DQ thresholds, Splink invocation strategy, target lag) that differ between modes and how they're surfaced (which config layer per XR-001).
- Phase 1 exit criterion: backfill of N months of synthetic historical data through the same code path used for daily incrementals, producing equivalent results.

**Effort:** S (one ARD section, possibly an ADR-0002 codifying the unified-pipeline contract).

---

### F-003: Deterministic tokens vulnerable to frequency-analysis re-identification — BLOCKER

**Where:** AD-009: "Random tokens for non-deterministic PII fields; deterministic non-FPE tokens for joinable identifiers." Schema: `name_token`, `dob_token` are deterministic to support the BR-102 anchor.

**Why it matters:** Deterministic tokenization preserves equality and therefore preserves frequency. An analytical reader (Sequelae PH ML engineer with BigQuery access) sees `name_token = X` appearing 10,000 times — and given a US census distribution prior, can infer with high confidence that X tokenizes "Smith". Chain that with a deterministic `dob_token` and you have re-identification without ever touching the Vault. Audit logs themselves carry the same `target_token` value, so an auditor with read access to operational audit can do the same correlation.

This is a real attack against deterministic tokenization in healthcare. It's not theoretical; it's the standard reason production systems use *keyed* deterministic tokenization with periodic rotation.

**What's needed:**
- AD-009 must specify keyed deterministic tokenization: `token = HMAC(class_key, normalize(plaintext))`. Class keys are KMS-managed, environment-scoped, and rotatable on a schedule.
- Per-partner salt for partner-scoped tokens that should not correlate cross-partner. The ARD's "partner_member_id_hash" in `deletion_ledger` already implies per-partner — generalize.
- Token rotation lifecycle: how do you rotate a class key without invalidating the canonical model's anchor lookups? Answer is non-trivial (re-key the entire token column atomically, or maintain old + new keys during migration). Needs an ADR.
- Acknowledge frequency analysis as a residual risk for the operational anchor lookup (BR-102 needs deterministic equality — that's the core tradeoff). Document the tradeoff explicitly so reviewers and auditors see it.

**Effort:** M (one ADR for keyed deterministic tokenization + key rotation lifecycle).

**Hand-off:** Round 2 (Security/Red-Team Architect) should stress-test the residual frequency-analysis exposure on the analytical surface.

---

### F-004: Verification API timing side-channel is named but not engineered — BLOCKER

**Where:** ARD §"Verification API (Public)": "The response time is consistent across all internal outcomes (latency-equalized to prevent timing-based inference)." That's a one-sentence claim, not a design.

**Why it matters:** XR-003 and BR-401 collapse the response set to two values to prevent existence-disclosure, but timing is a covert channel. If `VERIFIED` (which involves an indexed lookup that succeeds) takes 50ms and `NOT_VERIFIED` (which may involve a multi-tier lookup or full anchor search) takes 200ms, an attacker submits N claims, sorts by latency, and recovers existence information. A non-trivial percentage of healthcare-PII enumeration in the wild uses exactly this pattern.

**What's needed:**
- ARD section "Latency Equalization" specifying: a fixed latency floor (e.g. 250ms) below which the response is held; the floor must be set above the slowest legitimate path's p99; rate-limit responses, friction-challenge flows, and lockout responses must be indistinguishable along the timing dimension as well.
- Test gate: Phase 1 exit criterion includes a timing-distribution test across all internal-state combinations, asserting that the latency distributions are statistically indistinguishable above some threshold.
- Document the floor as a tradeoff against BR-404 (200ms p95): if the floor is 250ms, the p95 contract becomes 250ms and the BRD parameter changes accordingly. Reconcile.

**Effort:** S (one ARD section + one ADR clarifying the BR-404 reconciliation if needed).

**Hand-off:** Round 2 (Security/Red-Team) should verify the floor accounts for all known side channels including error-response paths.

---

### F-005: Disaster recovery for the Vault is hand-waved — BLOCKER

**Where:** ARD §"Region and Zones": "Disaster recovery via cross-region backup replication for AlloyDB and the Vault, target RTO 4 hours and RPO 15 minutes for v1."

**Why it matters:** The Vault is the only place plaintext PII lives. Losing it means losing the ability to detokenize — which means losing audit-log resolution, deletion verification, break-glass forensics. "Cross-region backup" is doing a lot of work in that sentence. Specifically:

- Backup target region — same data-residency boundary? Cross-residency leak risk during DR.
- Backup encryption — separate KMS keyring? Same? Cross-region KMS replication has its own model.
- Restore validation — when's the last time someone tested it? Untested DR is no DR.
- Recovery procedure for *the keys themselves* — KMS key compromise/loss is the catastrophic tail of the DR distribution.
- Audit GCS Bucket Lock'd objects cannot be moved across regions once Locked. Cross-region DR for the high-criticality audit tier requires its own design.

**What's needed:**
- Vault DR ADR: backup mechanism, target region, encryption-at-rest model, restore validation cadence (recommended: monthly synthetic DR test in staging), key-rotation interaction.
- Audit chain DR: GCS Bucket Lock retention + cross-region replication strategy. Cloud Storage offers Turbo Replication; at minimum that needs to be the design.
- DR runbook: who declares the incident, what's the procedure, how is the restored Vault validated against the canonical eligibility model before resuming detokenization.
- Add a Phase 0 exit criterion: synthetic DR test in dev, end-to-end.

**Effort:** M (DR ADR + runbook; ~1 day to draft, more to validate).

**Hand-off:** Round 2 (Infra/DevOps + Security) should review DR design.

---

### F-006: Canonical identity unmerge / split is unaddressed — BLOCKER

**Where:** BR-103 mentions identity-conflict review-routing and `IDENTITY_CONFLICT` queue class. BR-202 has every transition into `DELETED` but no transition for "this canonical identity should never have existed; split it."

**Why it matters:** This is operational reality. A reviewer says MERGE on a Tier 3 case. Three weeks later, a third partner feed produces evidence (definitive Tier 1 anchor mismatch) that the merge was wrong. The two people whose records were merged are now sharing a canonical identity, sharing eligibility state, and downstream consumers (Lore application accounts) have already used that canonical identity to make decisions. Unmerging is non-trivial:

- Lifecycle events for the merged identity have already been published; consumers may have acted.
- SCD2 history is a single chain — splitting it requires deciding which historical states belong to which split member.
- Audit chain referencing the merged `target_token` — the split shouldn't break audit-log resolvability.
- Downstream Lore application accounts: which side of the split owns the existing account?

This is the #1 operational defect in eligibility systems that have it. It's the #1 reason eligibility teams build manual ad-hoc tooling that bypasses the architecture.

**What's needed:**
- BRD addition (or assumption update): explicit policy on unmerge — is it supported, deferred, or never? If supported, what's the trigger and what's the contract with downstream consumers?
- ARD: if supported, an Unmerge Executor component analogous to Deletion Executor — irreversibility-classified per XR-006, requires explicit operator confirmation, emits the strongest audit trail in the system, requires a published `IDENTITY_SPLIT` lifecycle event.
- Phase 2 exit criterion: synthetic unmerge scenario through the full path.
- If deferred to v2, the deferral must be a documented decision with the operational-handling alternative for v1 (probably: incident response with ad-hoc remediation under audit, until v2).

**Effort:** S to defer with documentation; M to scope into v1.

---

## FINDINGS (resolve before backlog or document as deferred ADRs)

### F-007: Cost envelope absent — FINDING

**Where:** Nowhere. ARD names services without a per-month or per-partner cost model.

**Why it matters:** AlloyDB is a non-trivial line item; BigQuery slots and storage compound at scale; KMS operations are billed per call and the verification path is high-call-count. At Lore's headcount (42, ~25 in engineering), cost is a first-order constraint. An architecture that's correct but unaffordable doesn't ship.

**What's needed:** A back-of-envelope cost section in the ARD. Per-month at v1 (1 partner, low volume), at v1-launch (5-10 partners), at 10x. Identify the top three cost drivers and their unit-economic levers.

**Effort:** S (a few hours with GCP pricing data).

---

### F-008: Audit hash chain has no external anchoring — FINDING

**Where:** ARD §"Audit" — hash chain in GCS Bucket Lock'd object stream. Bucket Lock prevents deletion or modification within retention. Chain validator pages on chain break.

**Why it matters:** The chain is tamper-evident against in-system mutation. It's not tamper-evident against an adversary who has both write access to the bucket *during the open append window* and the ability to suppress events. Without an external anchor (e.g. periodic chain-head hash published to a separate Cloud Storage account, signed by a separate KMS key, or to an external timestamping service), a sophisticated insider can rewrite recent history before the bucket finalizes the locked retention.

**What's needed:**
- ADR: external anchoring strategy. Minimum: hourly publication of the current chain-head hash to a separate Storage account, signed with a KMS key from a separate keyring whose IAM is restricted to a different role. Better: external trusted-timestamp service (RFC 3161).
- Chain validator extended to validate against external anchors.

**Effort:** S (one ADR + Phase 0 implementation).

---

### F-009: Identity resolution is treated as static config, not a model with a lifecycle — FINDING

**Where:** BR-104 requires algorithm and configuration version stamps; ARD's `match_decision` schema has the columns. ARD §"Identity Resolution" describes Splink invocation. Nowhere does either document define how Splink models are trained, deployed, rolled back, or evaluated against ground truth.

**Why it matters:** Splink is a probabilistic system. It depends on:
- Trained match-weights derived from labeled training data — where does that come from? Synthetic for prototype; production training data is itself sensitive and changes over time as the partner mix evolves.
- A configuration (m and u probabilities, blocking rules, comparison vectors) that can be tuned. "Tune thresholds" is more than `MATCH_THRESHOLD_HIGH=0.95` — it's an artifact.
- Per-version evaluation against held-out ground truth — is the new model better than the old one? On which metrics?

Without a model lifecycle, the BR-104 version stamp records *what version was deployed* but cannot answer *was that version any good*. A regulator asking "how did you validate your identity resolution accuracy" has no defensible answer.

**What's needed:**
- ARD section "Identity Resolution Model Lifecycle": training data provenance, model artifact storage (Cloud Storage with KMS encryption + versioning), deployment mechanism (atomic), shadow-mode evaluation (new model runs in parallel against the current pipeline; results are diffed; promotion is a deliberate decision), rollback path.
- Held-out evaluation set: where it lives, how it's maintained, the metrics that gate promotion (precision at each tier threshold, recall at the deterministic anchor, calibration of probability scores).
- Per-version explainability artifact: when a model version changes, which BRs' replay-continuity guarantees are stressed (BR-104), and what the operator's decision options are.

**Effort:** M (one ADR for lifecycle + one ADR for evaluation/promotion).

**Hand-off:** Round 2 (Data-Engineering Principal) should detail the training-data and evaluation harness.

---

### F-010: Schema migration strategy is unaddressed — FINDING

**Where:** ARD has 6+ tables with concrete DDL. The harness has alembic configured. The ARD does not reference alembic, migration policy, backward compatibility, rollback strategy, or test gates.

**Why it matters:** Schema is a contract. Adding a column is forward-compatible; renaming is not; dropping is not without a deprecation cycle. In a system this is the source of truth for downstream account creation, a botched migration is a HIPAA-relevant incident (data integrity).

**What's needed:**
- ARD reference to the migration harness (alembic) and the migration policy: forward-compatible by default; breaking changes require a deprecation cycle with cross-environment coordination.
- Migration test gate: every PR that introduces an alembic migration runs forward + downgrade, plus runs against representative data and asserts no row loss / no schema drift.
- Coordination model when an ARD-amendment changes schema: when does the migration deploy relative to the application code that uses the new schema?

**Effort:** S (one ARD subsection + one ADR for migration policy).

---

### F-011: Service deployment / release engineering not addressed — FINDING

**Where:** ARD §"Service Hosting" lists Cloud Run for stateless services. Nothing about release strategy.

**Why it matters:** Cloud Run supports blue/green, canary, and rolling. The Verification API is in the critical path of account creation. A bad deploy that crashes Verification is an outage that's user-visible to onboarding members. Release strategy is part of the architecture, not an operational detail.

**What's needed:**
- ARD §"Release Engineering" section: per-service release strategy (probably canary for Verification API, rolling for everything else), release coordination model (when Verification API contract changes, the Lore application client must update — how is this versioned?).
- Feature flag policy: are flags used? If so, what's the lifecycle (max age before either promote or remove)?
- Rollback procedure: time-to-rollback target, automated vs operator-triggered.

**Effort:** S.

**Hand-off:** Round 2 (Infra/DevOps).

---

### F-012: Service-to-service authentication not specified — FINDING

**Where:** ARD §"API Contracts" mentions mTLS at the load balancer for the public Verification API; service-account-bound IAM for TokenizationService. Internal calls (Match Orchestrator → Splink Runner, every service → audit topic, etc.) — unspecified.

**Why it matters:** Zero-trust is the default for healthcare. Every service-to-service call should carry a verifiable identity. Cloud Run supports this via IAM-bound service accounts, but the ARD should explicitly state it and the audit posture (every internal call's caller identity is logged where? With what retention?).

**What's needed:**
- ARD §"Service-to-Service Authentication" section: per-call identity model, retention of internal-call audit, the relationship between internal-call audit and the BR-501 audit event classes.

**Effort:** S.

---

### F-013: Configuration change-control is not specified — FINDING

**Where:** ARD §"Configuration Management" describes the mechanism (Git → Cloud Storage → config-reload library). It does not describe the change-control process.

**Why it matters:** A bad threshold change can quarantine entire feeds (BR-303 threshold raised too low) or auto-merge wrong identities (BR-101 thresholds lowered). Configuration changes have the same blast radius as code changes. Same review rigor.

**What's needed:**
- ARD: configuration changes follow the same PR + review pipeline as code; the schema-registry repo's review gates are explicit; reviewer scope per parameter class (DQ thresholds need DE review; matching thresholds need ML review; partner-cadence overrides need Data Owner sign-off per BR-801).
- Hot-reload safety: parameters that hot-reload must be classified explicitly; type-safety / range-validation runs at config-load time, not request time; failed reload retains the previous valid config.

**Effort:** S.

---

### F-014: Sequelae PH ML feature engineering path is unaddressed — FINDING

**Where:** AD-003 says Sequelae PH may own Ingestion, Identity Resolution, Canonical Eligibility, Verification, Audit. BR-506 says Sequelae PH personnel must not access plaintext PII or PHI. ARD §"Identity Resolution" says ML lives there.

**Why it matters:** ML feature engineering routinely needs richer signal than fully-tokenized data provides — e.g. address-derived geographic clusters, name-similarity features for the matching model itself. Even tokenized addresses can be re-identified via cross-correlation. Splink's training itself requires labeled match data, which by definition is matched PII.

There's a real design question here: how does an ML engineer in Manila iterate on features when the operational-truth data they need has plaintext that can't cross the residency boundary?

Standard answers exist (synthetic-data clean rooms, US-only feature compute with Sequelae PH consuming feature stores via tokens, differential-privacy-aware feature sets) but the ARD doesn't pick one.

**What's needed:**
- ADR: ML feature-engineering access model under the Sequelae PH residency boundary. Pick one of:
  1. US-only feature compute pipeline; Sequelae PH consumes pre-computed feature tables only
  2. Synthetic-data clean room for ML iteration; production training is US-only
  3. Differential-privacy noise on feature aggregates accessible to Sequelae PH
- Restate AD-003 with the actual access matrix once the model is chosen.

**Effort:** M (one ADR; non-trivial architectural decision).

**Hand-off:** Round 2 (Data-Engineering Principal).

---

### F-015: Day-1 runbooks not enumerated — FINDING

**Where:** Phase 4 includes "runbook formalization." Nothing earlier.

**Why it matters:** Phase 1 hits production traffic. Phase 1 incidents need runbooks. Deferring runbooks to Phase 4 means the first 3 phases run on tribal knowledge.

**What's needed:**
- Phase 1 entry criterion: the following runbooks exist:
  - Vault break-glass detokenization audit response
  - Audit hash chain break response
  - DQ feed quarantine response
  - Verification API latency-breach response
  - Datastream lag escalation
  - PII-in-logs-detected response (the redaction scanner paged)
- Each runbook: trigger, immediate action, escalation path, postmortem requirement.

**Effort:** M (one runbook each; ~half-day per).

**Hand-off:** Round 2 (Infra/DevOps).

---

### F-016: Partner SFTP credential lifecycle unaddressed — FINDING

**Where:** ARD §"Ingestion": "Partner files arrive via SFTP (production) into the landing zone, or directly into the landing bucket via partner-side service account." Nothing on credential provisioning or rotation.

**Why it matters:** SFTP credentials are PII-equivalent in this system — possession of partner SFTP creds means the ability to inject malicious eligibility data, which then flows through the canonical model and out through Verification. Credential lifecycle is part of the security posture.

**What's needed:**
- ARD: SFTP credential model. Where do creds live? Rotation cadence? Per-partner separation? Partner-side compromise detection?
- Onboarding gate (BR-801): credential provisioning is part of the gate sequence; revocation is part of the offboarding gate.

**Effort:** S.

---

### F-017: Region-residency configuration assertions missing — FINDING

**Where:** AD-017 and ARD §"Region and Zones" name us-central1. Nothing enumerates per-service residency configuration assertions.

**Why it matters:** "Single primary US region" is a policy statement. The actual residency boundary depends on per-service configuration: BigQuery dataset region, Cloud Logging routing region, Cloud Composer environment region, KMS keyring location, Cloud Storage bucket location, Pub/Sub message storage policy. Each of these is a separate setting; missing one is a leak.

**What's needed:**
- ARD §"Residency Configuration Inventory" listing every region-controlled service and the assertion (us-central1, with multi-zone). This is an audit artifact.
- IaC (Terraform or equivalent) that enforces the assertions.

**Effort:** S (table; the IaC follows in Phase 0).

---

### F-018: STRIDE-style threat model absent — FINDING

**Where:** ARD has good security primitives but no enumerated threat model.

**Why it matters:** A principal architect reads the ARD and infers the threat model from the controls. A regulator or external auditor wants the threat model stated explicitly. Mapping each control to the threat it addresses is also a gap-finding tool — controls that address no threat are over-engineering; threats with no controls are exposures.

**What's needed:**
- ADR or ARD section: STRIDE per bounded context. Spoofing, Tampering, Repudiation, Information Disclosure, Denial of Service, Elevation of Privilege. For each context, identify the realistic attackers and the controls that mitigate each.
- This is the input artifact for Round 2 (Security/Red-Team).

**Effort:** M (~1 day for a defensible first cut).

**Hand-off:** Round 2 (Security/Red-Team) does the deep version.

---

### F-019: SCD2 reprocess interaction with reads is unaddressed — FINDING

**Where:** BR-604 (late-arriving file rebuild SCD2), BR-606 (full replay produces parallel SCD2 chain swapped in atomically). ARD §"Operational vs Analytical" mentions Datastream replication. No discussion of how Verification reads behave during a reprocess.

**Why it matters:** Reprocessing rebuilds history. Verification reads the operational store. If Verification is mid-call when the swap happens, what does it see? If the swap is transactional in the operational store, BigQuery is briefly inconsistent. If not transactional, Verification sees mixed states. Either way, reprocesses can cause verification flakiness if not engineered.

**What's needed:**
- ARD §"Reprocess and Read Consistency": atomicity guarantees, Verification behavior during a reprocess, replication-lag policy on BigQuery during the swap.

**Effort:** S.

---

### F-020: Risk register / decision deadlines for open questions — FINDING

**Where:** ARD §"Open Architectural Questions" lists six. They're framed as questions. A principal architect reads them as risks.

**Why it matters:** Each open question has an impact + probability + mitigation. "Confirmed warehouse choice" — if BigQuery is wrong, the analytical projection layer changes substantially. That's a real risk. Treating it as "we'll find out" is not architecture.

**What's needed:**
- Convert §"Open Architectural Questions" into a risk register: question / impact / probability / mitigation / decision deadline (which phase needs the answer) / fallback architectural branch if the answer is the unfavorable one.

**Effort:** S.

---

## ADVISORIES (log; address opportunistically)

### F-021: AD-NNN vs ADR-NNNN distinction unclear — ADVISORY

**Where:** ARD has 18 inline architectural decisions (AD-001..AD-018). Repo has docs/adr/ADR-0001-harness-foundation.md. Numbering schemes are different.

**Why it matters:** Future contributors won't know which catalog to consult, nor whether an inline AD requires a separate ADR.

**What's needed:** Clarify in the ARD: AD-NNN are inline decisions captured at ARD authorship; ADR-NNNN are individual decision documents under docs/adr/ that supersede or extend the inline ADs over time. Or unify the numbering. Either is fine; pick one.

**Effort:** S.

---

### F-022: Architecture review cadence undefined — ADVISORY

**Where:** ARD closing note says "may be revisited only by amendment with the same rigor that produced them." No cadence.

**Why it matters:** Architectures decay. A scheduled re-review (quarterly or per phase boundary) catches drift.

**What's needed:** ARD addition: review cadence (recommended: per phase boundary, plus ad-hoc on BR amendment), reviewer composition, output artifact (a delta document like this one).

**Effort:** S.

---

### F-023: [ADVISORY] BR graduation path undefined — ADVISORY

**Where:** BRD has rules tagged `[ADVISORY]` — BR-506 BAA documentation, BR-801 human-review gates, BR-802 partner-conditional code paths.

**Why it matters:** [ADVISORY] is honorable acknowledgment that programmatic enforcement isn't available yet. But a project Constitution that prizes programmatic enforcement (Constitution §0.5) needs a graduation mechanism — when does an [ADVISORY] become an enforced rule?

**What's needed:** BRD addition: each [ADVISORY] item carries a target phase by which it must either graduate to programmatic enforcement or be relabeled as a permanent process-only requirement with documented owner.

**Effort:** S.

---

### F-024: Match retraction semantics — ADVISORY

**Where:** Related to F-006 (unmerge) but distinct. Match retraction = a previously-recorded match decision is later determined to be wrong, but the system has not yet acted on it (no merge has occurred).

**Why it matters:** Less catastrophic than full unmerge but still needs a path. Reviewer says MERGE; the system queues the lifecycle event but hasn't published; reviewer realizes mistake; what's the abort path?

**What's needed:** Either explicitly defer with the assumption that this is rare and handled out-of-band, or specify a `RETRACT` action on `match_decision` that supersedes prior decisions before they take effect.

**Effort:** S.

---

### F-025: Column-level audit granularity not specified — ADVISORY

**Where:** BR-501: "PII access (read)" event class. ARD's Audit context doesn't specify granularity.

**Why it matters:** A `SELECT *` over `canonical_member` returns 6 token columns. Is that 1 access event or 6? HIPAA "minimum necessary" implies column-level, but column-level audit at scale is non-trivial.

**What's needed:** Either specify granularity (likely row-level, with the columns-accessed enumerated in the event payload) or document the deferral with a v2 plan.

**Effort:** S.

---

## Summary triage

| Severity | Count | Examples |
|---|---|---|
| BLOCKER | 6 | Capacity, Bulk/incremental, Token frequency analysis, Timing side-channel, Vault DR, Unmerge |
| FINDING | 14 | Cost, Audit anchoring, Model lifecycle, Schema migration, Release engineering, Service-to-service auth, Config change-control, Sequelae PH ML, Day-1 runbooks, SFTP credentials, Region assertions, STRIDE, SCD2 reprocess, Risk register |
| ADVISORY | 5 | AD vs ADR, Review cadence, [ADVISORY] graduation, Match retraction, Column-level audit |
| **Total** | **25** | |

---

## Recommended path before backlog work

1. **Address all 6 BLOCKERS** in the ARD or as new ADRs in `docs/adr/`. None are large — most are S or M effort. The unmerge BLOCKER (F-006) can be deferred with explicit documentation if v2 is acceptable, but the deferral itself must be a documented decision.
2. **Address F-009 (model lifecycle), F-018 (STRIDE), F-014 (Sequelae PH ML path)** before backlog because they will shape the backlog's structure. The backlog can't sequence ML work without a lifecycle model; can't sequence security work without a threat model; can't sequence Sequelae PH ownership without an ML access model.
3. **Convert F-020 (open questions) into a risk register.** Decisions on the warehouse, orchestrator, identity model, and attestation status need deadlines. Some will block phase transitions.
4. **Defer F-007 (cost), F-008 (anchoring), F-010 (migration), F-011 (release), F-012 (s2s auth), F-013 (config control), F-015 (runbooks), F-016 (SFTP), F-017 (residency), F-019 (SCD2 reads)** to dedicated ADRs in `docs/adr/`, owned and tracked in the phase backlog. These don't need to land in the ARD itself, but they need to land somewhere with a phase.
5. **Address advisories opportunistically** — most are 30-minute fixes.

If the BLOCKERS are addressed and the FINDINGS are tracked as ADRs with named owners and target phases, the platform on the other end will be well-engineered. If we proceed without addressing them, the platform will have correct architectural shape but unknown capacity, real privacy side channels, and operational gaps that surface as incidents in Phase 1-2.

---

## Hand-offs to subsequent review rounds

| Round | Reviewer | Findings to dig into |
|---|---|---|
| 2 | Security / Red-Team Architect | F-003 (token frequency), F-004 (timing), F-005 (DR), F-008 (audit anchoring), F-018 (STRIDE), F-016 (SFTP) |
| 2 | Data-Engineering Principal | F-002 (bulk/incremental), F-009 (model lifecycle), F-010 (migration), F-014 (Sequelae PH ML), F-019 (SCD2 reads) |
| 2 | Infra / DevOps Architect | F-001 (capacity), F-005 (DR), F-007 (cost), F-011 (release), F-015 (runbooks), F-017 (residency) |
| 2 | Clinical-Trust Reviewer (Adam Ameele lens) | Whether the user-facing failure paths (BR-403 contact-support fallback, BR-402 lockout) preserve clinical trust |

---

## What this review did NOT cover

Out of scope for principal-architect lens:

- BRD content correctness against domain reality (DE Principal's lens; clinical-trust reviewer's lens)
- Specific GCP service configuration (Infra/DevOps Architect)
- Detailed cryptographic primitive choice (Security Architect)
- Code-level test design or harness alignment (QA reviewer; phase-boundary auditor)

These are next-round concerns. This round focused on completeness, decomposition, tradeoffs, and defensibility — the specifically-principal-architect questions.
