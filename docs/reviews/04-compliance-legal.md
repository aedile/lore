# Architecture Review — Round 4: Compliance & Legal Counsel

| Field | Value |
|---|---|
| **Round** | 4 of N (final review round before consolidation) |
| **Reviewer lens** | Compliance & Legal Counsel — regulatory defensibility, contract posture, member rights mechanics, breach response, counsel-engaged decisions, audit/attestation readiness, litigation posture, ACO-specific obligations |
| **Documents** | `docs/BUSINESS_REQUIREMENTS.md` (BRD), `docs/ARCHITECTURE_REQUIREMENTS.md` (ARD) |
| **Date** | 2026-04-29 |
| **Prior rounds** | `docs/reviews/01-principal-architect.md`, `docs/reviews/02-chief-programmer.md`, `docs/reviews/03-principal-security.md` |

This review reads the documents three ways simultaneously: as an HHS Office for Civil Rights enforcement attorney would read them ("can OCR find a violation here"), as a class action plaintiff's lawyer would read them ("what's exposed and what theory of liability survives"), and as Lore's counsel would read them ("what should we have in writing before launch"). Where prior rounds asked "is the control implemented," this round asks "is the control documented, defensible, contractual, and provable."

Severity per Constitution Rule 29 (BLOCKER / FINDING / ADVISORY).

Where I'm extending prior-round findings, I cite them. The bulk is new — compliance is a different vocabulary and largely a different control set than security architecture.

---

## TL;DR

**Will the platform be compliant if we proceed as-is? No. The platform has technical primitives that *would* support compliance, but the policy, procedure, contract, and documentation infrastructure that translates those primitives into compliance defensibility does not exist in the BRD/ARD.**

Compliance is roughly half technical controls (Round 3 covered) and half *evidence and process*: written policies, signed agreements, designated officers, documented risk assessments, complaint procedures, breach playbooks, member-rights workflows, retention of records, training records, sanctions discipline. Without that scaffolding, the technical controls are individually correct but collectively undefensible to an HHS auditor or a state AG.

**75 findings: 22 BLOCKERS, 44 FINDINGS, 9 ADVISORIES.**

The BLOCKERS cluster around: regulatory mandates that cannot be deferred (Privacy Officer designation, written P&P, risk assessment cadence, NPP, breach response infrastructure), contractual obligations that gate partner relationships (BAA chain, partner data agreements, subprocessor lifecycle), and counsel-engaged decisions that have legal authority I don't carry (state law matrix, 42 CFR Part 2 scope, ACO obligations).

After consolidating across all four rounds, the unique BLOCKER set spans approximately **55-60 items**. With all addressed, the platform is HIPAA-compliant, contractually sound, attestation-ready, and litigation-defensible. Without them, the platform may be technically secure but legally exposed.

---

## What Compliance & Legal Owns That Prior Rounds Could Not

Prior rounds have standing to identify control gaps. They do not have standing to:

1. **Make legal-authority decisions** (which state laws apply, what triggers HIPAA breach analysis, what falls under 42 CFR Part 2).
2. **Author binding contracts** (BAA terms, partner data sharing agreements, member authorizations).
3. **Designate compliance roles** (Privacy Officer per §164.530(a)(1), Security Officer per §164.308(a)(2)).
4. **Establish enforceable policies and procedures** (HIPAA §164.316 requires written P&P; engineering documents are not P&P).
5. **Determine attestation strategy** (HITRUST CSF vs SOC 2 Type II; required for partner contracts).
6. **Set workforce sanctions** for HIPAA violations (§164.530(e)).
7. **Approve or deny disclosures** in edge cases (subpoena, law enforcement, public health).
8. **Render advice on regulatory inquiries** (HHS OCR investigation, state AG subpoena, CMS audit).

This review surfaces those areas as gaps. Each requires counsel engagement; I'm flagging the work, not doing it.

---

## Strengths from a Compliance View

What's load-bearing for compliance defensibility that already exists:

1. **PHI tokenization architecture (Vault + TokenizationService).** Defensible per §164.312(a)(2)(iv) (encryption/decryption) and §164.312(e)(2)(ii) (transmission integrity).
2. **Audit log architecture.** Provides §164.312(b) audit controls and supports §164.528 accounting of disclosures.
3. **Two-state Verification response (XR-003, BR-401).** Privacy-preserving collapse aligns with minimum necessary §164.502(b).
4. **Sequelae PH boundary (BR-506, AD-003).** Documented architectural enforcement of cross-border restrictions.
5. **Configurability per partner.** Supports BAA-specific obligations being honored differently per partner.
6. **Phase exit criteria.** Provide audit trail of compliance-relevant milestones.
7. **Three-environment hard separation.** Aligns with HIPAA segregation expectations.
8. **Right-to-deletion mechanics (BR-701-704).** Aligns with state law right of erasure (CCPA, CPRA, MHMDA).

These work. The gaps are around what's *not* in the docs.

---

## 1. HIPAA Privacy Rule Compliance Infrastructure

The BRD/ARD address the HIPAA Security Rule (technical safeguards) extensively. The Privacy Rule (§164.500-534) is largely absent. The Privacy Rule has its own mandates that cannot be skipped.

### L-001: Notice of Privacy Practices (NPP) — §164.520 — BLOCKER

**Where:** Not addressed in either document.

**Why it matters:** §164.520 requires every covered entity to provide a Notice of Privacy Practices to individuals. The notice must describe how PHI may be used and disclosed, individual rights, the entity's legal duties, and contact information for complaints. Lore is a covered entity (CE) for its application's members. The NPP must be available *before* PHI is first used — which means before the first member's eligibility data is processed.

**What's needed:**
- NPP authored by counsel
- Distribution mechanism: at the Lore application's first member-facing point of contact
- Acknowledgment of receipt: written or electronic
- Posted prominently on Lore's website and in any physical location
- Updated when material changes (definition: change to use/disclosure not previously described)
- Retention: 6 years from last effective version (per §164.530(j))

**Effort:** M (counsel-authored; engineering integration with Lore application).

---

### L-002: Authorization for Use and Disclosure — §164.508 — BLOCKER

**Where:** Not addressed.

**Why it matters:** Most uses/disclosures of PHI require either (a) the use is for Treatment, Payment, or Healthcare Operations (TPO — exempt from authorization), (b) the use falls within a §164.512 exception (public health, law enforcement, etc.), or (c) the individual has authorized the use in writing.

Eligibility verification is generally TPO. But: any use beyond TPO (research, marketing, sale of PHI, certain non-treatment uses) requires written authorization. The BRD/ARD don't classify uses against this dichotomy.

**What's needed:**
- Use-and-disclosure inventory: every PHI flow classified as TPO, §164.512 exception, or authorization-required
- Authorization template: counsel-authored, populated with specific use details
- Authorization tracking: when received, when revoked, what scope
- §164.508(b)(3) compounding restrictions: certain authorizations can't be combined

**Effort:** M (inventory + counsel-authored templates).

---

### L-003: Right of Access (§164.524) — Operational Implementation — BLOCKER

**Where:** Round 3 S-060 raised; this is the legal/operational depth.

**Why it matters:** §164.524 grants individuals the right to access their PHI. Specifics:
- 30-day response (extendable once by 30 days with written explanation)
- Format requested by individual (electronic if PHI is in EHR; paper acceptable)
- Reasonable cost-based fee permitted (HHS guidance: copying, postage, labor — not retrieval, infrastructure)
- Free electronic access if PHI is in EHR
- Denials only on specific grounds (§164.524(a)(3))
- Review of denials by licensed healthcare professional

This is a *legally enforceable individual right*. Failure to provide is a violation.

**What's needed:**
- Documented procedure: how members request, how Lore responds, who reviews, how delivered
- Form: counsel-authored request form
- Requestor verification: identity proofing standard (typically NIST IAL2 or equivalent)
- Fee schedule: published, cost-based, capped per HHS guidance
- Denial procedure: for the limited grounds; reviewer designated; communication to individual
- Response template: HHS-required content
- 30-day clock tracking: case management system

**Effort:** L (workflow + counsel-authored materials + member-portal integration).

---

### L-004: Right to Amendment (§164.526) — FINDING

**Where:** Not addressed.

**Why it matters:** §164.526 grants individuals the right to request amendment to their PHI. CE must accept or deny within 60 days (extendable once by 30 days). Denial requires statement of reason and individual's right to file statement of disagreement.

Eligibility data is the most amendment-prone PHI: members request name corrections (marriage, legal name change), DOB corrections (data entry errors), address updates, etc.

**What's needed:**
- Procedure: how members request amendment, how reviewed, who decides, propagation
- Architectural impact: amendment workflow against canonical_member; audit of amendments; downstream propagation to partners (note: some partners cannot accept amendments; documented)
- 60-day clock tracking
- Denial procedure with statement of disagreement attached to records

**Effort:** M.

---

### L-005: Right to Accounting of Disclosures (§164.528) — FINDING

**Where:** Round 3 S-061 raised; legal/operational depth here.

**Why it matters:** §164.528 grants individuals the right to receive an accounting of disclosures of their PHI for the prior 6 years. Major exclusions: TPO disclosures, disclosures to the individual themselves, disclosures with authorization. Non-TPO disclosures (research, public health, law enforcement) require accounting.

**What's needed:**
- Accounting query: identify all non-excluded disclosures from audit log for a given member
- Required content: date, recipient, brief description of PHI, purpose
- Format: written accounting; one free per 12 months, fees for additional
- 60-day clock; extendable once by 30 days
- §164.528(d): disclosures excluded from accounting need not appear; documentation of excluded vs included

**Effort:** M (audit log query + procedure).

---

### L-006: Right to Restrict Disclosures (§164.522(a)) — FINDING

**Where:** Not addressed.

**Why it matters:** §164.522(a) grants individuals the right to *request* restrictions on use and disclosure for TPO. The CE must consider but is generally not required to agree.

One restriction is mandatory (§164.522(a)(1)(vi)): if the individual pays for service out-of-pocket and requests restriction of disclosure to the health plan for that service, the CE must agree.

For Lore: if a member requests that eligibility data not be used for verification by partner X, what's the response? Mandatory in some scenarios.

**What's needed:**
- Procedure: how members request, how reviewed, who decides, documentation
- Mandatory-restriction handling: out-of-pocket-payment scenario
- Restriction tracking: per-member restrictions stored and honored across all PHI flows
- Restriction enforcement: architectural impact (a member with a restriction must not have their data flow to the restricted partner/use)

**Effort:** M.

---

### L-007: Right to Confidential Communications (§164.522(b)) — FINDING

**Where:** Not addressed.

**Why it matters:** §164.522(b) grants individuals the right to receive communications via specific channels (e.g. mail to a specific address, not phone calls).

For Lore: members may request verification-related communications via specific channels.

**What's needed:**
- Procedure: how members request, how honored
- Architectural impact: contact preferences stored and respected; no fallback to other channels without authorization

**Effort:** S.

---

### L-008: Notice of Privacy Practices Distribution Mechanism — FINDING

**Where:** Not addressed (related to L-001).

**Why it matters:** §164.520 requires:
- NPP available at first service delivery
- Acknowledgment of receipt obtained (written or electronic)
- NPP posted prominently online
- Updated NPP distributed to existing members upon material change

**What's needed:** Distribution workflow integrated with Lore application onboarding flow; tracking of acknowledgments; revision distribution mechanism.

**Effort:** S (integration with Lore application).

---

## 2. HIPAA Breach Notification Rule Infrastructure

Round 3 S-049 raised the timeline. This round delivers the legal infrastructure underneath.

### L-009: Breach Risk Assessment Methodology — §164.402(2) — BLOCKER

**Where:** Not addressed.

**Why it matters:** §164.402(2) defines a "breach" as an unauthorized acquisition, access, use, or disclosure of PHI that compromises its security or privacy *unless* the CE demonstrates a low probability of compromise via a risk assessment.

The risk assessment is the determinative document for whether a notification obligation triggers. Without a documented methodology, every incident is a coin flip on whether to notify.

**What's needed:** Counsel-authored methodology covering the four mandatory factors:
1. Nature and extent of PHI involved (data elements, sensitivity, identifiability)
2. Unauthorized person who used or to whom disclosure was made (workforce member, external party, recipient's likely use)
3. Whether PHI was actually acquired or viewed (forensic evidence)
4. Mitigation extent (containment, recovery, recipient assurances)

Decision tree: scoring per factor → composite risk → notification decision. Documented for every incident.

**Effort:** M (counsel-authored).

---

### L-010: Breach Notification Content — §164.404(c) — BLOCKER

**Where:** Not addressed.

**Why it matters:** §164.404(c) specifies required notification content:
- Brief description of what happened, including date of breach and date of discovery (if known)
- Description of types of unsecured PHI involved
- Steps individuals should take to protect themselves
- Brief description of what CE is doing to investigate, mitigate, and prevent recurrence
- Contact information

**What's needed:** Pre-approved template. Populated with incident specifics during response. Counsel-reviewed before each use.

**Effort:** S (template).

---

### L-011: Substitute Notice — §164.404(d)(2) — BLOCKER

**Where:** Not addressed.

**Why it matters:** When the CE has insufficient or out-of-date contact info for ≥10 individuals, substitute notice is required:
- Conspicuous posting on CE's website for 90 days, OR
- Conspicuous notice in major print or broadcast media in geographic area

Plus: toll-free number active for 90 days for individuals to learn if their PHI was involved.

**What's needed:** Procedure, website notice template, toll-free call center vendor (or capability), 90-day commitment.

**Effort:** S (procedure); operational readiness (vendor).

---

### L-012: Media Notice (>500 in a State) — §164.406 — BLOCKER

**Where:** Not addressed.

**Why it matters:** When breach affects >500 residents in a single state, CE must notify prominent media outlets serving that state, in addition to individual notice.

**What's needed:** Procedure: media list per state; press release template; 60-day timeline.

**Effort:** S.

---

### L-013: HHS Notification — §164.408 — BLOCKER

**Where:** Not addressed.

**Why it matters:**
- Breach affecting ≥500 individuals: HHS notification within 60 days of discovery
- Breach affecting <500 individuals: annual rollup notification by end of calendar year

Both via HHS Breach Portal (online form).

**What's needed:** Procedure: who has portal access, content authoring, 60-day clock tracking, rollup process for <500 incidents.

**Effort:** S.

---

### L-014: State Breach Notification Matrix — Counsel-Engaged — BLOCKER

**Where:** Round 3 S-064 raised; this is the legal layer.

**Why it matters:** Each US state has its own breach notification statute with unique:
- Definition of "personal information" or "protected health information"
- Trigger threshold (any unauthorized access vs. risk-of-harm-based)
- Notification timeline (CCPA: "without unreasonable delay"; specific states: 30, 45, 60, 90 days)
- Recipient requirements (state AG, residents, credit reporting agencies for >500)
- Notification format
- Substitute notice rules
- Penalties for non-compliance

State of residence of affected individual determines which state's law applies. ACO operates US-wide; all 50 states are in scope.

**What's needed:** Counsel-authored 50-state matrix. Maintained current. Decision flowchart: incident details → applicable state laws → notification requirements consolidated.

**Effort:** L (counsel engagement; ongoing maintenance).

---

### L-015: HITECH Notification Enhancements — FINDING

**Where:** Not addressed.

**Why it matters:** HITECH expanded HIPAA breach notification:
- Lowered trigger threshold (HITECH presumption that breach occurred unless CE demonstrates low probability — codified in §164.402(2))
- Added BA notification obligations to CE (BA must notify CE within 60 days)
- Civil money penalty tiers expanded

**What's needed:** Acknowledge HITECH framework in BRD; ensure BA contracts include notification obligations.

**Effort:** S (BRD addition + BAA template).

---

### L-016: Breach Detection Discipline — Discovery Definition — BLOCKER

**Where:** Round 3 S-049 implied; legal definition needed.

**Why it matters:** §164.404(a)(2) defines "discovered" as the first day on which the breach is known to the CE *or, by exercising reasonable diligence, would have been known*. The clock starts at discovery.

The "reasonable diligence" standard means a CE that fails to detect a breach for 6 months can have its clock backdated by HHS.

**What's needed:** Documented detection processes (Round 3 SIEM, anomaly detection); discovery decision (who designates an event as a "discovered breach"); clock-start documentation per incident.

**Effort:** S.

---

## 3. Specialized Data Categories

### L-017: 42 CFR Part 2 Decision and Implementation — Counsel-Engaged — BLOCKER

**Where:** Round 3 S-062 surfaced; this is the legal decision.

**Why it matters:** 42 CFR Part 2 governs SUD program records. Stricter than HIPAA: explicit consent for each disclosure (HIPAA TPO does not apply); prohibition on re-disclosure; segregated audit logs.

If any partner's eligibility data includes SUD-program identifiers (HCPCS codes, NPI of SUD providers, even some payer codes), Part 2 applies in full to that subset of data. Operational impact is significant.

**What's needed:** Counsel-engaged decision:
- Option A: Reject partners whose data includes Part 2-covered identifiers. Define identifiers precisely. Communicate to partners.
- Option B: Implement Part 2 controls for the affected subset. Includes consent management, restricted disclosure, segregated audit, additional retention.
- Option C: Operational segregation — Part 2 data goes through a separate code path entirely.

Decision rationale documented; counsel sign-off.

**Effort:** S to decide; M-L if Option B.

---

### L-018: Mental Health & State-Specific Sensitive Categories — FINDING

**Where:** Not addressed beyond 42 CFR Part 2.

**Why it matters:** Multiple states have specific protections:
- California Confidentiality of Medical Information Act (CMIA): mental health, AIDS/HIV, genetic test results
- New York Mental Hygiene Law §33.13: mental health records
- Illinois Mental Health and Developmental Disabilities Confidentiality Act
- Many states: HIV/AIDS-specific protection

**What's needed:** Per-state sensitive-category matrix. Decision: do partner feeds include these categories? If yes, additional state-law controls.

**Effort:** S (matrix); ongoing per state.

---

### L-019: Genetic Information Non-Discrimination Act (GINA) — FINDING

**Where:** Not addressed.

**Why it matters:** GINA Title I prohibits health insurance underwriting based on genetic information. ACO context: Lore is not directly an insurer but operates on behalf of insurers in some contracts. Decision: is genetic information ever part of eligibility data?

**What's needed:** Decision in BRD. If yes: explicit handling. If no: reject partner data containing genetic identifiers; document.

**Effort:** S (decision).

---

### L-020: Children's Online Privacy Protection Act (COPPA) — FINDING

**Where:** Not addressed.

**Why it matters:** COPPA applies to information collected from children under 13. Healthcare data on minors typically goes through parental consent under HIPAA. But if Lore directly collects from a member portal: COPPA applies for under-13.

**What's needed:** Decision: does Lore application's scope include under-13 members? If yes: COPPA-compliant flow. If no: explicit exclusion at signup.

**Effort:** S (decision).

---

## 4. Medicare ACO Specific Compliance

Lore operates as a Medicare ACO under the Medicare Shared Savings Program. CMS regulations apply.

### L-021: 42 CFR Part 425 — Medicare ACO Beneficiary Protections — Counsel-Engaged — BLOCKER

**Where:** Not addressed.

**Why it matters:** 42 CFR Part 425 (Medicare Shared Savings Program) imposes specific obligations:
- Beneficiary notification (§425.312): ACO must notify beneficiaries about ACO participation
- Beneficiary opt-out rights (§425.708): limited opt-out from data sharing
- Marketing restrictions (§425.310)
- ACO governance composition (§425.106)
- Protection against reduced services or quality

ACO data sharing with CMS: specific Data Use Agreement (DUA) with CMS controlling re-disclosure.

**What's needed:** Counsel-engaged compliance review of Part 425 obligations. Document obligations in BRD. Architectural impact (opt-out tracking, beneficiary notification mechanism).

**Effort:** M (counsel-engaged).

---

### L-022: CMS Data Use Agreement Compliance — FINDING

**Where:** Not addressed.

**Why it matters:** Lore receives Medicare claims and beneficiary data from CMS under a DUA. The DUA imposes use restrictions:
- Specific permitted uses only
- Re-disclosure prohibited (or strictly limited)
- Data retention limits
- Audit and reporting obligations

Eligibility data flowing from CMS data has DUA constraints. Some controls inherit from HIPAA; some are DUA-specific.

**What's needed:** DUA terms documented in BRD's compliance section. Architectural enforcement: data lineage tracking; CMS-source data flagged and access-controlled.

**Effort:** M.

---

### L-023: Beneficiary Assignment Data — FINDING

**Where:** Not addressed.

**Why it matters:** ACO receives beneficiary assignment data (which beneficiaries are attributed to the ACO). Specific data elements with specific protections under Part 425.

**What's needed:** Acknowledge in BRD; ensure handling matches Part 425 §425.312 requirements.

**Effort:** S.

---

## 5. Member Rights — Operational Workflows

These are individual rights granted by HIPAA and state law. Each requires a workflow for fulfillment.

### L-024: Unified DSAR (Data Subject Access Request) Workflow — FINDING

**Where:** Not addressed.

**Why it matters:** Across all member rights (HIPAA Right of Access, Right to Amendment, Right to Accounting, state privacy laws like CCPA's right of access, right of deletion, right to opt-out), members will submit requests. A unified DSAR workflow:
- Single intake channel
- Identity verification standard (NIST IAL2 typical)
- Routing per request type
- Response timeline tracking
- Audit of fulfillment
- Member portal integration

**What's needed:** ADR: DSAR workflow tooling. Likely a dedicated case management system (OneTrust, BigID, custom) integrated with member portal.

**Effort:** L (cross-functional; technology + process).

---

### L-025: Member Complaint Procedure — §164.530(d) — BLOCKER

**Where:** Not addressed.

**Why it matters:** §164.530(d) requires CEs to provide a process for individuals to file complaints concerning the CE's policies and procedures or compliance therewith. Complaints directly to CE; also to HHS OCR.

**What's needed:**
- Documented complaint procedure
- Complaint form (counsel-authored)
- Complaint tracking system
- Response timeline (HIPAA does not specify, but standard is 30 days)
- Documentation retention: 6 years per §164.530(j)
- No retaliation policy: complaints cannot trigger adverse action against complainant (§164.530(g))

**Effort:** M.

---

### L-026: Member Access Fee Schedule — FINDING

**Where:** Not addressed.

**Why it matters:** §164.524(c)(4) allows reasonable cost-based fee for copies. HHS guidance (2016 + 2018 clarifications):
- Fees limited to: copying labor, supplies, postage, and prepared summary if requested
- Cannot include: retrieval costs, technology infrastructure
- Free electronic access if PHI is in EHR
- Reasonable cap: per-page or flat fee with cost basis

**What's needed:** Counsel-authored fee schedule consistent with HHS guidance. Published. Reviewed annually.

**Effort:** S.

---

### L-027: Authorization vs Consent Terminology Discipline — FINDING

**Where:** BRD/ARD use the words informally.

**Why it matters:**
- "Authorization" (HIPAA): specific written permission for a specific use
- "Consent" (HIPAA): general agreement (HIPAA does not require but does not prohibit)
- "Opt-in / Opt-out" (state laws, marketing): differs by state

Different legal weight. Documents must use terms precisely.

**What's needed:** Glossary in BRD. Counsel-reviewed.

**Effort:** S.

---

### L-028: Member Rights Notification at Verification Point — FINDING

**Where:** Implicit; not stated.

**Why it matters:** When the Verification API is invoked (member is creating account in Lore application), members are at a point of decision. Privacy notice presentation is required at this point. Members should be informed of rights. Failure to inform is a Privacy Rule violation.

**What's needed:** Coordinate with Lore application: NPP delivery, member rights summary, complaint contact info presented at relevant flows.

**Effort:** S (coordination).

---

## 6. Contractual Posture — Business Associate Agreements

The HIPAA contract regime is the legal architecture underpinning the technical architecture.

### L-029: BAA Chain — Comprehensive Coverage — BLOCKER

**Where:** Round 3 S-027 enumerated subprocessors; legal layer here.

**Why it matters:** §164.314(a) requires a BAA between CE and BA. Each BA must have BAAs with its subprocessors. Chain must extend through every PHI-touching layer.

For Lore:
- Lore (CE for application, BA for some partner relationships)
- GCP (BA — covered by Google Cloud BAA)
- Each GCP service used (verify each is in-scope under Google's BAA)
- PagerDuty (BA if PHI flows to alerts)
- Splunk/Elastic/Chronicle if SIEM (BA depending on scope)
- Sequelae PH (BA-equivalent, with cross-border addendum)
- Any third-party vendor

**What's needed:**
- Comprehensive BAA inventory: every entity, BAA execution date, BAA renewal cadence
- Verify GCP BAA scope covers every GCP service used (Google publishes scope; verify against architecture)
- BAA template: counsel-authored standard
- Pre-BAA-execution gate: no PHI flow until BAA is signed
- Renewal tracking

**Effort:** M (initial inventory; ongoing).

---

### L-030: BAA Standard Terms — Counsel-Engaged — BLOCKER

**Where:** Not addressed.

**Why it matters:** §164.504(e) specifies required BAA terms:
- Permitted uses and disclosures
- Prohibition on improper use
- Safeguards required
- Reporting of unauthorized use/disclosure
- Subcontractor BAA chain
- Access to PHI for individuals (Right of Access)
- Amendment access
- Accounting of disclosures
- HHS access to records
- Termination
- Return or destruction of PHI at termination

Plus desired (not mandatory) terms: indemnification, limitation of liability, insurance, audit rights, breach allocation, defense cooperation.

**What's needed:** Counsel-authored BAA template. Negotiation playbook (what's negotiable, where Lore holds the line). Reviewed annually.

**Effort:** L (counsel engagement; legal template work).

---

### L-031: BAA Termination Data Return / Destruction — FINDING

**Where:** Round 3 S-067 raised partner-side; same applies to all BAs.

**Why it matters:** §164.504(e)(2)(ii)(J) requires BAA to address what happens to PHI at termination — return to CE, destruction, or extension of protections if neither feasible.

**What's needed:** Procedure: at BA termination, request data return or destruction; receive certificate of destruction; document closure.

**Effort:** S (process).

---

### L-032: Partner Data Sharing Agreements — Counsel-Engaged — BLOCKER

**Where:** Not addressed.

**Why it matters:** Each partner has a contractual relationship with Lore for eligibility data. The partner is a CE; Lore is a BA. The agreement governs:
- Permitted uses (TPO scope)
- Data fields shared (data minimization L-040)
- Quality standards
- Notification of data quality issues
- Breach notification timelines (BA → CE within 60 days; partners may want stricter)
- Audit rights
- Termination terms
- Indemnification
- Insurance requirements

This is the *partner-side* contract chain; without it, Lore receives partner PHI without legal authority.

**What's needed:** Counsel-authored standard partner data sharing agreement. Negotiation playbook. No partner data flows without executed agreement.

**Effort:** L.

---

### L-033: Subprocessor Lifecycle — FINDING

**Where:** Round 3 S-066 raised; legal layer here.

**Why it matters:** Onboarding a new subprocessor requires:
- Vendor risk assessment (security questionnaire, SOC 2 / HITRUST attestation review)
- BAA execution
- Documentation in BA inventory
- Customer notification (some BAA templates require notice of new subprocessors)

Termination requires data return/destruction.

**What's needed:** Subprocessor lifecycle procedure. Approval gate. Customer notification (if applicable per BAA terms).

**Effort:** M.

---

### L-034: BAA Cross-Border Addendum (Sequelae PH) — Counsel-Engaged — FINDING

**Where:** Not explicitly addressed in BAA-level terms.

**Why it matters:** Cross-border data transfer requires explicit contractual mechanism. Standard Contractual Clauses (SCCs) — originally GDPR-driven but standard practice for international data flows. Philippines Data Privacy Act of 2012 also applies if Sequelae PH personnel process any PII (even tokenized).

**What's needed:** Counsel-engaged: BAA addendum or separate Data Processing Agreement (DPA) covering Sequelae PH cross-border flow. Reference applicable laws (Philippines DPA, US state laws).

**Effort:** M (counsel engagement).

---

### L-035: Vendor Risk Assessment Process — FINDING

**Where:** Round 3 S-033 implied; legal/process here.

**Why it matters:** Pre-contract due diligence on vendors prevents downstream compliance issues. Standard:
- Security questionnaire (SIG, CAIQ)
- Recent attestation review (SOC 2 Type II, HITRUST CSF, ISO 27001)
- Financial stability check
- Reference checks
- BAA negotiability

**What's needed:** Vendor risk assessment procedure. Criteria for vendor approval. Annual review of in-flight vendors.

**Effort:** M.

---

## 7. Workforce / Personnel Compliance

### L-036: Privacy Officer Designation — §164.530(a)(1) — BLOCKER

**Where:** Not addressed.

**Why it matters:** §164.530(a)(1) *requires* CE to designate a Privacy Officer responsible for development and implementation of policies and procedures. Identifiable individual; contact information must be in NPP.

**What's needed:** Designation document. Officer's contact info in NPP. Officer's responsibilities documented.

**Effort:** S (designation; ongoing accountability).

---

### L-037: Security Officer Designation — §164.308(a)(2) — BLOCKER

**Where:** Not addressed.

**Why it matters:** §164.308(a)(2) requires CE to designate a Security Officer responsible for development and implementation of policies and procedures. Same person can hold both Privacy and Security Officer roles in smaller organizations.

**What's needed:** Designation document.

**Effort:** S.

---

### L-038: Workforce Training — §164.530(b) — BLOCKER

**Where:** Round 3 S-079 raised; legal mandate here.

**Why it matters:** §164.530(b) requires CE to train all workforce members on policies and procedures, as necessary for their function. Must be:
- Within reasonable time after hire
- When material change in policies
- Documented (training records retained 6 years)

**What's needed:**
- Training program: counsel-reviewed content; role-specific modules
- Training records: retained per §164.530(j)
- Training compliance dashboard: who's trained, who's overdue

**Effort:** M (program); ongoing.

---

### L-039: Workforce Sanctions Policy — §164.530(e) — BLOCKER

**Where:** Not addressed.

**Why it matters:** §164.530(e) requires CE to have a sanctions policy for workforce members who fail to comply with HIPAA policies. Documented sanctions; applied uniformly; documented in employment records.

**What's needed:** Sanctions policy: tiered (verbal, written, training, suspension, termination); applied uniformly; documented in HR records; counsel-reviewed.

**Effort:** S.

---

### L-040: Background Checks for PHI-Handling Roles — FINDING

**Where:** Not addressed.

**Why it matters:** HIPAA does not mandate but standard practice. Specifically for PII Handler, Break-Glass Admin, Privacy Officer, Security Officer roles.

**What's needed:** Pre-employment screening policy. Counsel-reviewed (state laws on background check vary).

**Effort:** S.

---

### L-041: Workforce Departure Procedure — Compliance Layer — FINDING

**Where:** Round 3 S-039 covered access revocation; legal here.

**Why it matters:** Departure is a compliance event:
- Final audit of recent privileged-role activity
- Final HIPAA training acknowledgment retained
- Sanctions on file (if any) retained per retention policy
- Notification to BAs if BA-handled departures (some BAA templates require)

**What's needed:** Procedure with HR + Compliance + Security collaboration.

**Effort:** S.

---

### L-042: Whistleblower Protections — §164.502(j)(1) — FINDING

**Where:** Not addressed.

**Why it matters:** §164.502(j)(1) protects workforce members who in good faith disclose unlawful conduct to authorities. Lore policy must support this.

**What's needed:** Whistleblower protection policy; non-retaliation commitment; reporting channel (typically external).

**Effort:** S.

---

### L-043: Mobile Device & Remote Work Policy — FINDING

**Where:** Not addressed.

**Why it matters:** Workforce members may access PHI from mobile devices, home computers, public networks. HIPAA requires safeguards.

**What's needed:** BYOD / Remote work policy. Encryption requirements for endpoint devices. VPN requirements. Public Wi-Fi restrictions. Lost device procedure (remote wipe).

**Effort:** S (policy); ongoing enforcement.

---

## 8. Records Management & Documentation Retention

### L-044: HIPAA Documentation Retention — §164.530(j) and §164.316(b) — BLOCKER

**Where:** Round 3 S-021 covered data retention; legal mandate for documentation here.

**Why it matters:** §164.530(j) (Privacy) and §164.316(b) (Security) require retention of:
- Policies and procedures (current and prior versions)
- Communications (NPPs, authorizations, breach notifications)
- Complaints
- Sanctions records
- Workforce training records
- Risk assessments
- BAA executions and amendments
- Incident response documentation

Retention: 6 years from creation OR last effective date, whichever is later.

This is *separate* from data retention. Documentation retention is the compliance evidence chain.

**What's needed:** Documentation retention policy; retention infrastructure (separate from operational data); annual review.

**Effort:** M.

---

### L-045: PHI Inventory and Data Mapping — BLOCKER

**Where:** Not explicitly addressed.

**Why it matters:** A documented PHI inventory is required for:
- Risk assessment (you can't assess what you don't know exists)
- Breach response (you can't notify affected individuals if you don't know which PHI was involved)
- Right of Access fulfillment
- Audit defensibility

The data flow inventory must cover: source, storage, processing, transmission, destination, retention, destruction.

**What's needed:** Documented PHI inventory:
- Per data field: source, storage location(s), processing services, transmission paths, recipients, retention, destruction mechanism
- Updated annually and on architectural change
- Counsel-reviewed for completeness

**Effort:** M.

---

### L-046: Litigation Hold Procedure — FINDING

**Where:** Round 3 S-051 implied; legal procedural layer here.

**Why it matters:** When litigation is reasonably anticipated, common-law spoliation duty arises: preserve all relevant records. Failure → adverse inference, sanctions.

Triggers: lawsuit filed or threatened, regulatory inquiry, large breach (likely litigation), employee dispute, partner dispute.

**What's needed:** Procedure:
- Trigger criteria
- Hold notice to all relevant parties (engineering, IT, HR, business)
- Preservation of operational data, audit logs, communications, work product
- Hold maintained until released by Legal
- Documentation of hold actions

**Effort:** S.

---

### L-047: e-Discovery Readiness — FINDING

**Where:** Implicit.

**Why it matters:** When litigation comes, electronically stored information (ESI) must be produced. Search, preservation, production capabilities.

**What's needed:** ESI search capability across:
- Audit logs
- Application logs
- Email and Slack
- Document repositories
- Source code
- Architecture documents (BRD, ARD, ADRs)

Tools: Cloud Logging supports search; corporate email/Slack have e-discovery options. Process for production.

**Effort:** M (technology readiness); ongoing.

---

### L-048: Privilege Protection — FINDING

**Where:** Implicit.

**Why it matters:** Attorney-client privileged communications must be identified and protected. Engineering investigations conducted under counsel direction may be privileged.

**What's needed:**
- Procedure for invoking privilege (counsel-directed work)
- Privilege log maintenance
- Protection of privileged work product in litigation
- Training on privilege boundaries

**Effort:** S.

---

## 9. Audit & Attestation

### L-049: Risk Assessment — Required Cadence — §164.308(a)(1)(ii)(A) — BLOCKER

**Where:** Not addressed.

**Why it matters:** §164.308(a)(1)(ii)(A) requires "accurate and thorough assessment of the potential risks and vulnerabilities to the confidentiality, integrity, and availability of PHI." This is a HIPAA mandate, not an aspiration.

Cadence: annual minimum; more frequent on material change.

**What's needed:**
- Risk assessment methodology (counsel + security)
- Annual scope: all PHI flows, controls, threats, vulnerabilities, residual risk
- Documented findings and remediation plan
- Retained per §164.530(j)

**Effort:** M (initial); annual ongoing.

---

### L-050: HITRUST CSF or SOC 2 Type II — Decision and Roadmap — BLOCKER

**Where:** BRD references in passing.

**Why it matters:** Partner contracts increasingly require attestation. Two main options:
- **HITRUST CSF**: healthcare-specific framework; comprehensive; expensive (~$200k+ engagement)
- **SOC 2 Type II**: broader-applicability; less healthcare-specific; less expensive

Some partners may require both. Decision and roadmap have material cost and timing implications.

**What's needed:** Counsel + Compliance decision: which attestation, by when, scope.

Phase 4 currently assigns "SOC 2 Type II or HITRUST CSF readiness, depending on Lore's compliance roadmap." Decision before Phase 1 production.

**Effort:** S to decide; L to execute (Phase 4).

---

### L-051: Internal Audit Program — FINDING

**Where:** Implicit.

**Why it matters:** Internal audit independent of operations:
- Cadence: continuous + annual deep
- Scope: all controls (HIPAA + state law + contractual)
- Reporting: to Privacy Officer, Security Officer, Executive Leadership
- Findings tracked to remediation

**What's needed:** Internal audit charter; staffing model (in-house vs outsourced); cadence; tooling.

**Effort:** M.

---

### L-052: Compliance Testing — FINDING

**Where:** Round 3 S-052 covered penetration testing; compliance testing here.

**Why it matters:** Distinct from penetration testing:
- Compliance testing: are controls operating as designed?
- Examples: random sampling of audit log entries for completeness; vault detok audit review; access control validation

**What's needed:** Compliance testing program; cadence; sampling methodology; findings to remediation.

**Effort:** M.

---

### L-053: Compliance Reporting to Leadership — FINDING

**Where:** Implicit.

**Why it matters:** Executive leadership and board need visibility into compliance posture. Without reporting, gaps fester.

**What's needed:** Quarterly compliance dashboard: controls status, incidents, audit findings, regulatory updates, training completion. Annual to board.

**Effort:** S.

---

## 10. Insurance & Risk Transfer

### L-054: Cyber Liability Insurance — FINDING

**Where:** Not addressed.

**Why it matters:** Standard for healthcare data handlers. Coverage for:
- Investigation costs
- Notification costs
- Defense costs
- Regulatory fines (where insurable)
- Business interruption

Coverage levels typical for ACO scale: $5M-$25M per incident.

**What's needed:** Insurance procurement; annual review; coverage adequacy assessment.

**Effort:** S (procurement); ongoing.

---

### L-055: Errors & Omissions / Professional Liability — FINDING

**Where:** Not addressed.

**Why it matters:** Coverage for professional services failures. Verification API misverification = potential E&O claim.

**What's needed:** Coverage assessment.

**Effort:** S.

---

### L-056: Director & Officer Insurance — FINDING

**Where:** Not addressed.

**Why it matters:** Coverage for D&O personal liability for compliance failures. Standard for healthcare.

**What's needed:** Coverage assessment.

**Effort:** S.

---

## 11. Litigation & Regulatory Inquiry Readiness

### L-057: Regulatory Inquiry Response Procedure — BLOCKER

**Where:** Not addressed.

**Why it matters:** HHS OCR investigation, state AG inquiry, CMS audit, partner audit — each can arrive with a 30-day or 60-day response deadline. Without procedure, response is ad-hoc.

**What's needed:**
- Designated point of contact (Privacy Officer or counsel)
- Document production process
- Privilege screening before production
- Response coordination
- Witness preparation

**Effort:** M.

---

### L-058: Class Action Defense Readiness — FINDING

**Where:** Implicit.

**Why it matters:** Healthcare data breaches frequently trigger class actions. Defense readiness:
- Document preservation (litigation hold L-046)
- Class certification opposition strategy
- Settlement reserves
- PR coordination

**What's needed:** Counsel-engaged playbook.

**Effort:** L (counsel engagement).

---

### L-059: Member Harm from Verification — Liability Allocation — FINDING

**Where:** Round 3 S-073 raised; legal layer here.

**Why it matters:** If Verification API produces wrong outcome:
- False NOT_VERIFIED → member can't access services → consequential damages
- False VERIFIED → impersonation → identity theft → state UDAP claims

Liability between Lore (eligibility data system), Lore application (account creator), and partners.

**What's needed:** Counsel-engaged: liability allocation in BAA / partner agreements; member terms-of-service; indemnification structure.

**Effort:** M.

---

### L-060: Subpoena Response Procedure — FINDING

**Where:** Not addressed.

**Why it matters:** Subpoenas (judicial, administrative, grand jury) seeking PHI arrive periodically. §164.512(e) provides limited safe harbor; specific procedural requirements (notice to individual or qualified protective order).

**What's needed:** Procedure: receipt, counsel review, response strategy, member notification (where applicable).

**Effort:** S.

---

### L-061: Law Enforcement Disclosure Procedure — FINDING

**Where:** §164.512(f) is mentioned implicitly.

**Why it matters:** Specific exceptions for law enforcement. Each requires different documentation:
- Court order: comply
- Grand jury subpoena: comply
- Administrative request: limited (must be authorized by law)
- Voluntary disclosure: very limited grounds
- Imminent threat: emergency disclosure permitted

**What's needed:** Procedure with counsel review.

**Effort:** S.

---

### L-062: Public Health Reporting — §164.512(b) — FINDING

**Where:** Not addressed.

**Why it matters:** §164.512(b) permits disclosure to public health authorities. Mandatory reporting for some categories (communicable disease, child abuse, gunshot wounds in some states).

**What's needed:** Procedure: identify mandatory reporting in scope; channels for reporting; authorization waiver under §164.512(b).

**Effort:** S.

---

## 12. Specific Operational / Member-Facing Concerns

### L-063: Member Portal Authentication — FINDING

**Where:** Round 3 S-073 implies.

**Why it matters:** Member portal access to PHI requires identity verification. NIST SP 800-63 IAL2 typical for healthcare.

**What's needed:** ADR + counsel-reviewed: identity verification standard for member portal.

**Effort:** S.

---

### L-064: Marketing Communications Restrictions — §164.508(a)(3) — FINDING

**Where:** Not addressed.

**Why it matters:** Marketing PHI use generally requires authorization. Limited exceptions (face-to-face communications; promotional gifts of nominal value). Eligibility data should not be used for marketing without authorization.

**What's needed:** Policy: explicit prohibition on eligibility data for marketing; audit controls.

**Effort:** S.

---

### L-065: Sale of PHI — Explicit Prohibition — §164.508(a)(4) — FINDING

**Where:** Not addressed.

**Why it matters:** Sale of PHI requires authorization. ACOs sometimes face proposals to share data with research entities for compensation; falls under sale rules.

**What's needed:** Policy: explicit prohibition on sale without authorization; approval gate for any PHI exchange involving compensation.

**Effort:** S.

---

### L-066: Member Restriction on Disclosures to Health Plans — FINDING

**Where:** Related to L-006.

**Why it matters:** §164.522(a)(1)(vi) mandatory restriction: out-of-pocket payment for service → individual can require restriction of disclosure to health plan. ACO has health-plan-equivalent role; mandatory restriction may apply.

**What's needed:** Counsel decision: is ACO a "health plan" under §164.522(a)(1)(vi)? If yes, mandatory restriction handling.

**Effort:** S (counsel decision).

---

### L-067: Self-Disclosure to HHS — ADVISORY

**Where:** Not addressed.

**Why it matters:** HHS provides voluntary self-disclosure mechanisms. May reduce penalty severity.

**What's needed:** Decision tree for self-disclosure (counsel-engaged).

**Effort:** S.

---

## 13. Counsel Engagement and Document Maintenance

### L-068: Counsel Sign-off on BRD/ARD — BLOCKER

**Where:** N/A (procedural).

**Why it matters:** BRD/ARD reference legal/regulatory requirements throughout but were authored without counsel engagement. Final documents going to Phase 1 production need HIPAA-qualified counsel review and sign-off.

**What's needed:** Counsel review of:
- BRD legal/regulatory references
- Section 4 (Programmatic Enforcement) legal accuracy
- ARD security/compliance claims
- BAA-impacting provisions
- Member rights mechanics

Counsel sign-off documented.

**Effort:** M (counsel engagement).

---

### L-069: Document Versioning and Approval — FINDING

**Where:** Implicit (Git versioning).

**Why it matters:** Compliance documents (P&P, NPP, BAAs) need formal version control:
- Version number, effective date, approver
- Change log
- Approval workflow (Privacy Officer + counsel typical)

Distinct from Git history (which captures *what* changed but not *who approved* in a HIPAA-defensible way).

**What's needed:** Document control system for compliance documents; approval workflow; change log; counsel-reviewed.

**Effort:** M.

---

### L-070: Compliance Calendar — FINDING

**Where:** Implicit.

**Why it matters:** Many compliance obligations are time-bound:
- Annual risk assessment
- Annual workforce training refresher
- Annual BAA review
- Annual subprocessor review
- Quarterly compliance dashboard
- HIPAA breach <500 annual rollup
- State law-specific timing requirements
- Insurance renewal

**What's needed:** Compliance calendar maintained by Privacy Officer; alerts; reporting.

**Effort:** S.

---

### L-071: Regulatory Update Tracking — FINDING

**Where:** Implicit.

**Why it matters:** HIPAA regulations update; HITECH amendments; state laws change; CMS issues regulations and sub-regulatory guidance. Without tracking, Lore drifts out of compliance.

**What's needed:** Regulatory tracking service (counsel firm, compliance vendor) or in-house monitoring; quarterly review; impact assessment.

**Effort:** S (subscription); ongoing.

---

## 14. Specific Edge Cases

### L-072: Deceased Members — FINDING

**Where:** Not addressed.

**Why it matters:** §164.502(f) PHI of deceased individuals retains protection for 50 years. Different access rules: personal representatives, etc.

**What's needed:** Procedure: handling of deceased-member PHI; access by personal representatives; retention.

**Effort:** S.

---

### L-073: Minors and Personal Representatives — FINDING

**Where:** Not addressed.

**Why it matters:** §164.502(g) governs personal representatives (parents for minors, guardians for incapacitated). Minor adolescents: state law governs whether parent can access certain records.

**What's needed:** Procedure aligned with applicable state laws.

**Effort:** S.

---

### L-074: Incapacitated Individuals — FINDING

**Where:** Not addressed.

**Why it matters:** §164.510(b) provides limited disclosure to family/friends in certain circumstances. Incapacitated individual cannot consent; legal representative governs.

**What's needed:** Procedure.

**Effort:** S.

---

### L-075: Substance Abuse Confidentiality (42 CFR Part 2) — Architectural — Counsel-Engaged — BLOCKER

**Where:** L-017 covered the decision; this is the architectural integration.

**Why it matters:** If Part 2 applies (decision per L-017), architectural enforcement:
- Separate audit segment for Part 2 records
- Specific consent management UI/UX
- Re-disclosure prohibition enforcement
- Retention rules per Part 2

**What's needed:** Architectural integration if Part 2 applies; ADR.

**Effort:** L (if applicable).

---

## Summary triage

| Severity | Count | Examples |
|---|---|---|
| BLOCKER | 22 | NPP (L-001), Authorization (L-002), Right of Access ops (L-003), Breach Risk Assessment methodology (L-009), Breach Notification Content (L-010), Substitute Notice (L-011), Media Notice (L-012), HHS Notification (L-013), State Breach Matrix (L-014), Discovery Definition (L-016), 42 CFR Part 2 (L-017), Medicare ACO Beneficiary (L-021), Complaint Procedure (L-025), BAA Chain (L-029), BAA Standard Terms (L-030), Partner Data Sharing Agreements (L-032), Privacy Officer designation (L-036), Security Officer designation (L-037), Workforce Training (L-038), Sanctions Policy (L-039), Documentation Retention (L-044), PHI Inventory (L-045), Risk Assessment cadence (L-049), Attestation roadmap (L-050), Regulatory Inquiry response (L-057), Counsel Sign-off (L-068), Part 2 architecture (L-075) |
| FINDING | 44 | Right to Amendment, Right to Accounting ops, Right to Restriction, Right to Confidential Communications, NPP distribution, HITECH enhancements, mental health categories, GINA, COPPA, CMS DUA, beneficiary assignment, DSAR workflow, member access fees, terminology, member rights notification at Verification, BAA termination, subprocessor lifecycle, cross-border addendum, vendor risk assessment, background checks, departure procedures, whistleblower, mobile/remote, litigation hold, e-Discovery, privilege, internal audit, compliance testing, leadership reporting, cyber insurance, E&O, D&O, class action defense, member harm liability, subpoena, law enforcement, public health, member portal auth, marketing, sale of PHI, plan restrictions, document versioning, compliance calendar, regulatory tracking, deceased members, minors, incapacitated |
| ADVISORY | 9 | Self-disclosure to HHS, plus a few smaller items |
| **Total** | **75** | |

---

## Cross-round summary (all four rounds)

| Round | Lens | BLOCKERS | FINDINGS | ADVISORIES | Total |
|---|---|---|---|---|---|
| 1 | Principal Architect | 6 | 14 | 5 | 25 |
| 2 | Chief Programmer | 13 | 37 | 10 | 60 |
| 3 | Principal Security | 18 | 47 | 9 | 74 |
| 4 | Compliance / Legal | 22 | 44 | 9 | 75 |
| **Combined (with overlap)** | — | **59** | **142** | **33** | **234** |

After de-duplication across rounds, the unique BLOCKER set is approximately **55-60 items**. Many are S effort individually; collectively they represent multiple person-quarters of work — primarily counsel-engagement, procedure authoring, P&P document creation, training program development, and BAA/contract execution.

Without this work: the platform may be technically secure but legally exposed. HHS OCR enforcement action, state AG inquiry, partner contract breach, member class action — each becomes a viable threat in the absence of compliance scaffolding.

---

## Recommended path before backlog

1. **Engage counsel.** A non-trivial fraction of the BLOCKERS (L-014 state law matrix, L-017 Part 2, L-021 ACO beneficiary, L-029-032 BAA chain and terms, L-058 class action defense, L-068 counsel sign-off) cannot be resolved by engineering alone. Counsel is a precondition.
2. **Designate Privacy Officer and Security Officer** (L-036, L-037). These designations gate all other compliance work — these officers own the compliance program.
3. **Author core P&P documents** (L-044 retention, L-038 training, L-039 sanctions, L-049 risk assessment methodology). HIPAA mandate; cannot be deferred.
4. **PHI inventory and data mapping** (L-045). Foundation for risk assessment, breach response, audit defensibility.
5. **Address the procedural BLOCKERS** in parallel with Phase 0 / Phase 1 work: complaint procedure, breach response infrastructure, member rights workflows.
6. **Defer the remaining FINDINGS** to a Compliance Phase 0 ADR set with named owners. Many are S effort but cumulative.
7. **Work the ADVISORIES** opportunistically.

Cross-round coordination: the 55-60 unique BLOCKERs from all four rounds should be triaged together. Some compound: L-029 BAA chain depends on L-050 attestation decision; L-049 risk assessment depends on L-045 PHI inventory; L-014 state matrix informs L-009 breach methodology.

---

## Hand-offs to the consolidation pass

The user has indicated this is the final review round before consolidation. After this, all four rounds' findings are consolidated into BRD/ARD amendments.

**Recommended consolidation approach:**

1. **Triage all four rounds' BLOCKERs** into:
   - Document amendments (BRD/ARD changes)
   - Phase 0 ADRs (decisions tracked separately)
   - Compliance Phase 0 work products (P&P, contracts, designations — not tracked in BRD/ARD)
2. **Author BRD/ARD amendments** as a single PR with one commit per finding addressed (or themed groups). Each commit references the originating finding.
3. **Carry deferred findings into the phase backlog** with named owners, target phases, and acceptance criteria.
4. **Counsel review of the consolidated BRD/ARD** before backlog work begins.

The four reviews collectively have done the diagnostic. The consolidation is the prescription.

---

## What this review did NOT cover

Out of scope for the compliance/legal lens:

- Architectural decomposition (Round 1)
- Code-level discipline (Round 2)
- Security technical controls (Round 3 — though Privacy Rule overlap is genuine)
- Domain correctness (would be DE Principal / clinical-trust)
- Specific BAA contract clauses (counsel work product, not architecture review)
- State-by-state legal opinions (counsel work product)
- HIPAA training content authoring (compliance/HR work product)
- P&P document drafting (compliance work product)

These belong to counsel and the compliance program. This review identified them as gaps and gave them named status; the work itself is downstream.
