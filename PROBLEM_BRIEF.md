# Problem Brief: Strategic Data System for Trusted Partner Eligibility and Identity Verification

## Document Purpose

This document captures the problem space, known facts, derived requirements, and assumptions for the Lore Health Staff Data Engineer panel interview, Case Study 3. It is the foundational input for a Business Requirements Document (BRD), which will in turn inform an Architecture Requirements Document (ARD). The goal is to translate a deliberately under-specified case prompt into a structured problem statement that captures both the explicit asks and the inferred constraints that a Staff-level response should address.

This brief distinguishes between confirmed facts (drawn directly from the case prompt or from public information about Lore Health) and inference (derived from context). Inference is marked where it occurs.

## Scenario Summary

Lore is onboarding multiple partners who supply eligibility data containing PII. This data has two operational uses:

1. Identity verification of users attempting to access Lore
2. Definitive source of truth for new user account creation in the Lore application

The inbound data presents three structural challenges:

1. Heterogeneous formats across partners
2. Quality issues and inconsistencies within and across partner feeds
3. Strict privacy regulation compliance requirements

The integration must support two operational modes:

1. Initial bulk load of historical eligibility data per partner
2. Continuous incremental updates reflecting attrition and changes within each partner's eligibility pool

## Context: Lore Health

The following context is drawn from public sources about Lore Health and shapes the problem space, even though it is not stated in the case prompt. This is inference applied to confirmed facts about the company.

### Business Model

Lore operates as a Medicare Accountable Care Organization (ACO) and partners with healthcare-cost-bearing entities including employers, health plans, and Medicare. Revenue comes from shared savings against reduced total cost of care. Eligibility data is therefore not a peripheral concern: it is the operational mechanism by which Lore identifies whose health outcomes count against which partner's savings calculation. Eligibility accuracy has a direct line to revenue, and eligibility errors have a direct line to revenue leakage or partner trust loss.

### Geographic Scope

Lore's customer and partner base is US-only by structural necessity. The Medicare ACO designation is a CMS construct that does not exist outside the United States. However, Lore Health maintains an engineering and operations presence in the Philippines, which introduces cross-border data handling considerations even though all end users are US-based.

### Compliance Posture

Operating in US healthcare with PII and PHI implies the following regulatory regimes apply:

- HIPAA Privacy Rule and Security Rule (primary regime)
- HITECH (breach notification, audit logging requirements)
- State privacy laws including CCPA and CPRA (California), Washington's My Health My Data Act, and the broader patchwork of state-level health and consumer privacy laws
- 42 CFR Part 2 if substance use disorder data is in scope (likely not for general eligibility, but worth scoping out explicitly)
- Industry attestation expectations such as HITRUST CSF or SOC 2 Type II as a partner contracting prerequisite

### Stack Signal

Public statements from Lore-affiliated sources reference Domain-Driven Design and Test-Driven Development as engineering practices, and emphasize robust data products and AI/ML alongside speed to insights. This suggests a stack and culture that will respond well to:

- Explicit domain boundaries and contracts
- Tested data pipelines (not just tested application code)
- Data product framing rather than monolithic warehouse framing

Specific tooling is not publicly disclosed at the time of this brief and should be researched separately or proposed on first principles with justification.

## Stakeholders: Interview Panel as Proxy

Three interviewers represent three concerns that any proposed solution must address. They are not the only stakeholders the production system would have, but for the purposes of this deliverable they are the audience.

**Mike Griffin (Software Engineer, Wayfinding squad).** Owns the user journey from recruitment to first day in the app. His squad is the primary downstream consumer of eligibility data. He will evaluate whether the proposed system actually serves user account creation cleanly and whether failure modes have been thought through from his side of the integration contract.

**Jonathon Gaff (Data Engineer, internal systems).** Focused on trustworthy and private data infrastructure for LoreBot conversations. He will evaluate data architecture, PII isolation, governance controls, and the technical defensibility of identity resolution choices.

**Adam Ameele (PsyD, clinical context).** Focused on resilience-enhancing dialogue and clinical authenticity. He will evaluate whether the candidate understands that data infrastructure is a clinical-trust prerequisite, not just a technical concern. The framing for him is that bad data or sloppy PII handling at onboarding poisons every conversation downstream.

## Explicit Deliverables from the Prompt

The case prompt explicitly requests:

1. A strategic vision for integrating and managing eligibility data
2. Clear data quality standards
3. PII governance requirements, including privacy controls such as anonymization or pseudonymization, and compliance measures
4. A comprehensive data integration strategy supporting both bulk ingestion and ongoing change data capture
5. Defined performance and freshness requirements
6. An automated data cleansing and curation process ensuring consistency, accuracy, and continuous compliance
7. A high-level design for the identity verification system using the curated data as source of truth
8. Articulated availability and reliability requirements for the verification system
9. Hands-on artifacts:
   - SQL DDL for key table(s) in the cleansed and curated eligibility data store
   - A code snippet or SQL query identifying or cleansing a specific type of data inconsistency such as duplicate PII or format errors
10. Technical and architectural justifications throughout, considering data profiling, transformation techniques, and overall data security

The panel instructions add a further deliverable on top of the case prompt itself: a working prototype that illustrates the proposed approach.

## Functional Capabilities Required

Derived from the explicit deliverables and the operational scenario:

- Multi-partner ingestion across heterogeneous formats (CSV, JSON, fixed-width, and XML are all plausible)
- Per-partner schema mapping to a canonical internal eligibility model
- Data profiling against incoming feeds covering volume, distribution, and anomaly detection
- Validation rules at the field level (format, type, range), record level (cross-field consistency), and feed level (row count deltas, distribution shifts)
- Deduplication within a single partner feed
- Identity resolution across partner feeds, including detection of the same person enrolled with multiple partners
- Survivorship rules where partners disagree about the same person's attributes
- Snapshot-diff change data capture for partners who do not produce true change feeds (the realistic majority case)
- Slowly Changing Dimension Type 2 history on the canonical member entity for audit and point-in-time queries
- Tokenization of PII with separation between analytical surface and PII-bearing vault
- Identity verification API that resolves an inbound identity claim against the curated source of truth
- Audit logging for all PII access, satisfying HIPAA audit requirements
- Operational observability across the pipeline including run status, data quality metrics, and lineage

## Non-Functional Requirements

The prompt explicitly asks the candidate to define these. Proposed targets follow.

### Latency and Freshness

- Bulk load per partner: hours to single-digit days for onboarding, scaled by volume
- Incremental updates: same-day processing of partner feeds, with daily cadence as the baseline
- Identity verification API response: sub-200ms p95 latency
- Account creation eligibility check: real-time read against the curated store

### Reliability and Availability

- Identity verification API: 99.9 percent availability target as a baseline; 99.95 percent if account creation is hard-blocked on it
- Pipeline: per-partner SLA with explicit late-arrival handling and reprocessing capability
- No data loss tolerance for source files; full replay capability must exist from a raw landing layer

### Scalability

- Partner count: design must absorb 10x current partner count without architectural change
- Volume per partner: must absorb partners ranging from thousands to millions of members
- Verification call volume: scales with user growth and authentication activity

### Data Quality

- Quantified metrics for completeness, validity, uniqueness, consistency, and timeliness, computed per partner feed
- Quality SLAs that gate downstream publication; feeds failing thresholds are quarantined rather than published

### Security and Privacy

- Encryption in transit and at rest as a baseline
- Field-level encryption or tokenization for PII columns
- Role-based access control with explicit separation between analytics roles and PII-handling roles
- Audit trail on every PII access
- Data residency controls preventing PII from being processed outside designated jurisdictions, given the offshore engineering footprint
- Right-to-deletion handling consistent with state law obligations
- Documented Business Associate Agreement chain for every data subprocessor

### Operational Efficiency

- Adding a new partner should be a matter of configuration and mapping, not new code
- Schema drift detection on partner feeds with alerting before bad data lands in curated layers
- Idempotent reprocessing for any pipeline stage

## Constraints

- **Time box.** 24 hours from receipt to submission. Net working budget is closer to 12 to 15 hours after sleep and meals.
- **Prototype expectation.** A working prototype is required, not just documentation. The prototype should demonstrate the technical heart of the solution (identity resolution and cleansing on synthetic data) rather than attempt every subsystem.
- **No clarifying questions.** All ambiguities must be resolved through documented assumptions.
- **Communication preferences.** Direct, concise prose. No marketing language. Clean typographic formatting without decorative elements. No em dashes.

## Assumptions

The following assumptions are made in place of asking clarifying questions. Each will be stated explicitly in the BRD and the final deliverable.

1. Partners deliver eligibility data via SFTP drop or equivalent file-based mechanism. Real-time API feeds from partners are out of scope for v1.
2. Partner feeds are full-roster snapshots, not change feeds. Diff-based CDC is the implementation pattern.
3. Daily cadence is the baseline; some partners may deliver weekly or monthly. The design must absorb the range.
4. PII fields include at minimum: full name, date of birth, SSN (or partial), address, phone, email, and partner-assigned member ID. Additional fields per partner are likely.
5. The Lore application owns user account state. The eligibility system is a source of truth that account creation reads from; it does not create application accounts directly.
6. Identity verification at account creation is customer-facing but not life-critical. Outage is recoverable but degrades the onboarding experience and should be avoided.
7. The system is greenfield for the purposes of this brief. Migration from a prior system is not in scope unless surfaced explicitly.
8. The implementation deploys in a single primary cloud region within the United States, with multi-AZ resilience but not multi-region active-active for v1.
9. AI/ML capabilities such as probabilistic identity matching and anomaly detection are within scope where they provide explainability. Black-box ML for identity match decisions is not appropriate here, primarily for compliance and auditability reasons.
10. The Philippines engineering organization does not have direct access to production PII. Their access is mediated through tokenized analytical surfaces. This will be stated as an architectural decision, not an organizational one.

## Out of Scope for the Deliverable

The following are real concerns in production but should be acknowledged and bracketed in the deliverable rather than implemented:

- Full implementation of the identity verification service beyond a thin API contract and reference implementation
- Production-hardened secrets management, networking design, and infrastructure-as-code
- Full HIPAA compliance audit; the deliverable will articulate controls and posture, not implement attestation
- Disaster recovery runbook; will be referenced in non-functional requirements but not produced
- Member-facing consent management UI
- Integration with downstream Lore application services beyond the eligibility-to-account contract

## Open Questions Documented but Not Asked

These are questions a candidate would normally ask in a real engagement. They are recorded here as open and will be addressed via stated assumption in the final deliverable.

1. What is the existing data platform stack: cloud provider, data warehouse or lakehouse, orchestration, transformation tooling?
2. What is the current partner count, and what is the projected count at 12 and 24 months?
3. What is the existing identity model in the Lore application, and what does an account record require beyond eligibility verification?
4. Are there existing partner contracts that constrain data handling beyond statutory requirements?
5. Is the Philippines engineering organization permitted to handle production PII, or is access to PII restricted to US-resident personnel?
6. Does Lore currently hold a HITRUST or SOC 2 attestation, or is that an active workstream?
7. Is there an existing approach to identity resolution within Lore, and if so what does it use?
8. How does eligibility loss (a member removed from a partner roster) interact with account state? Soft deactivate, hard close, grace period?
9. What partners are in scope for the initial onboarding wave, and what formats do they actually deliver?
10. What is the expected balance between deterministic match keys (SSN, partner-assigned member ID) and probabilistic matching (name plus DOB plus address)? Specifically, can SSN be relied on or is it frequently absent or partial?

## Success Criteria for the Deliverable

The deliverable succeeds if it demonstrates:

1. Staff-level architectural judgment, including explicit decisions about what to leave out
2. A defensible position on identity resolution, which is the technical core of the problem
3. A clean PII isolation pattern that materially reduces compliance burden and breach blast radius
4. A unified bulk and incremental design that does not treat them as separate systems with separate code
5. A working demonstration of the cleansing and matching logic on synthetic data
6. Clean SQL DDL for the curated eligibility model with explicit SCD2 history
7. An identity verification API contract that the Wayfinding squad could integrate against without a follow-up meeting
8. Explicit non-functional requirements expressed as numbers, not adjectives
9. A phased delivery approach that respects the realities of partner onboarding
10. Acknowledgment of cross-border data residency given Lore's offshore engineering footprint

The deliverable fails if:

- It treats identity resolution as a SQL JOIN
- It buries PII handling as an afterthought rather than a structural decision
- It conflates the bulk load and incremental update as separate codebases
- It produces no runnable demonstration
- It overreaches into a fully production-ready system that cannot be defended cleanly across three 60-minute interviews
