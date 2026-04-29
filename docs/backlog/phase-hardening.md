# Phase 4 — Hardening and Attestation Prep Backlog

| Field | Value |
|-------|-------|
| **ARD reference** | §"Phased Delivery" / Phase 4 |
| **Goal** | SOC 2 Type II or HITRUST CSF readiness, depending on the attestation choice (RR-004). |
| **Status** | LIVE BACKLOG |

---

## Phase 4 Goal

Penetration testing (per R3 S-052), third-party security review, runbook formalization, disaster recovery validation, audit log access review, BAA chain documentation finalized. Comprehensive accessibility audit (per XR-009).

## Phase 4 Entry Gate

- All Phase 3 exit criteria met.
- Attestation framework decision (RR-004) is months ahead of the audit window per P0-COM-008.
- All `[ADVISORY]` BRs have process-owner closures (P2-ADV-001) operational for ≥ 1 review cycle.
- Production data continuity: ≥ 12 months of audit chain integrity demonstrated (the Phase 4 audit window typically requires this).
- Counsel + Privacy Officer + Security Officer aligned on attestation scope.

## Phase 4 Exit Criteria (per ARD)

- External attestation auditor's report with no high-severity findings.

(In practice, exit means: SOC 2 Type II report on file with controls effective for the audit period, or HITRUST CSF certification at the chosen level.)

---

## Epics

| Key | Epic | Description |
|-----|------|-------------|
| PEN | Penetration Testing | External pentest scoped + executed + remediated |
| TPR | Third-Party Security Review | Independent security review with findings tracked |
| DR  | DR Validation | Full DR drill against region failover |
| RUN | Runbook Formalization | Every operational scenario has a runbook |
| ALR | Audit Log Access Review | Annual review of who accessed what + retention demonstration |
| BAA | BAA Chain Finalization | Comprehensive BAA + subprocessor inventory |
| WCAG | Comprehensive Accessibility Audit | Full WCAG 2.1 AA audit by a third party |
| EVI | Attestation Evidence Pack | Evidence collection + auditor liaison |
| TRN | Workforce Training Continuous | Annual cadence + tracking maturity |
| RES | Resilience Validation | Chaos testing on production-like environment |

---

## Stories

### Epic PEN — Penetration Testing

#### P4-PEN-001 — External penetration test scoped + contracted
- **As** the Security Officer
  **I want** an external penetration test scoped and contracted with a qualified firm
  **So that** R3 S-052 + ARD Phase 4 entry are met.
- **AC**
  - Given the engagement, when scoped, then it covers Verification API, TokenizationService, member portal, reviewer interface, partner inbound paths, IaC-deployed infrastructure.
  - Given the contract, when reviewed, then it covers rules of engagement, NDA, scope-of-test, deliverable timelines, and remediation re-testing.
- **Originating** R3 S-052, ARD §"Phase 4"
- **Depends on** P0-COM-008
- **Tier** CRITICAL · **Size** M · **Owner** Security Officer

#### P4-PEN-002 — Penetration test execution + observability
- **As** the Security squad
  **I want** the pentest executed against the staging environment with prod-equivalent topology + monitored
  **So that** findings are actionable + the SOC's detection capability is also tested.
- **AC**
  - Given the test execution, when monitored, then SOC alerts and detection rates against the pentest activity are recorded.
  - Given findings, when received, then each is triaged with severity, owner, remediation plan within `PENTEST_TRIAGE_DAYS`.
- **Originating** R3 S-052, ARD §"Phase 4"
- **Depends on** P4-PEN-001
- **Tier** CRITICAL · **Size** L · **Owner** Security

#### P4-PEN-003 — Pentest findings remediation
- **As** the Security squad
  **I want** all CRITICAL + HIGH findings remediated and re-tested
  **So that** ARD Phase 4 exit ("no high-severity findings") is achievable.
- **AC**
  - Given a CRITICAL/HIGH finding, when remediated, then a re-test confirms closure.
  - Given a finding accepted-as-residual-risk, when documented, then it has Security Officer + counsel + Risk-Committee sign-off.
- **Originating** ARD §"Phase 4 exit"
- **Depends on** P4-PEN-002
- **Tier** CRITICAL · **Size** XL · **Owner** Security

---

### Epic TPR — Third-Party Security Review

#### P4-TPR-001 — Independent third-party review (architecture + controls)
- **As** the Security Officer
  **I want** an independent third-party security review covering architecture, controls, and posture
  **So that** ARD Phase 4 exit is met with external attestation.
- **AC**
  - Given the engagement, when complete, then a report identifies findings with severity + recommendations.
  - Given the report, when reviewed, then findings are triaged similarly to P4-PEN-003.
- **Originating** ARD §"Phase 4 exit", R3 S-068
- **Depends on** P0-COM-008, P2-COM-005
- **Tier** CRITICAL · **Size** L · **Owner** Security Officer

---

### Epic DR — DR Validation

#### P4-DR-001 — Full DR drill (region failover)
- **As** the Platform/SRE squad
  **I want** a full DR drill executing region failover end-to-end with measured RTO/RPO
  **So that** the `[dr-strategy]` ADR's targets are validated, not assumed.
- **AC**
  - Given the drill, when executed, then RTO + RPO targets are met with documented evidence.
  - Given the drill, when reviewed, then a postmortem identifies any operational frictions.
- **Originating** ARD §"Phase 4", P0-ADR-005, R5 D-039
- **Depends on** P0-ADR-005, P1-DR-001
- **Tier** CRITICAL · **Size** XL · **Owner** Platform/SRE

#### P4-DR-002 — DR runbook validation
- **As** the Platform/SRE squad
  **I want** the DR runbook validated against the drill outcome
  **So that** the runbook reflects what actually works under failover conditions.
- **AC**
  - Given the runbook, when reviewed post-drill, then it accurately reflects the drill steps and any deviations are folded back into the runbook.
- **Originating** R5 D-039
- **Depends on** P4-DR-001
- **Tier** CRITICAL · **Size** M · **Owner** Platform/SRE

---

### Epic RUN — Runbook Formalization

#### P4-RUN-001 — Operational runbook coverage audit
- **As** the Platform/SRE squad
  **I want** an audit confirming every paged-alert path has a corresponding runbook
  **So that** on-call has a documented response to every alertable scenario.
- **AC**
  - Given every alert in the alerting catalog, when audited, then each has a linked runbook with: triage steps, remediation steps, escalation criteria, postmortem template.
  - Given an alert without a runbook, when found, then it is filed as a follow-up before the audit period closes.
- **Originating** AD-021, R5 D-035
- **Depends on** P0-OBS-007 + all phase observability stories
- **Tier** CRITICAL · **Size** L · **Owner** Platform/SRE

#### P4-RUN-002 — Runbook drill cadence
- **As** the Platform/SRE squad
  **I want** a quarterly drill cadence exercising at least one runbook per quarter
  **So that** runbook accuracy and operator familiarity stay current.
- **AC**
  - Given a quarter, when reviewed, then at least one runbook drill was executed with attendance + postmortem on file.
  - Given drill outcomes, when reviewed annually, then runbook updates are tracked to the drill that surfaced them.
- **Originating** R5 D-039
- **Depends on** P4-RUN-001
- **Tier** IMPORTANT · **Size** M · **Owner** Platform/SRE

---

### Epic ALR — Audit Log Access Review

#### P4-ALR-001 — Annual audit log access review
- **As** the Privacy Officer
  **I want** an annual review of who accessed audit logs + audit-log access patterns
  **So that** BR-503 review surface is operational and any anomalous access is caught.
- **AC**
  - Given the review, when conducted, then it produces a list of audit-log accesses by principal + purpose with anomalous-access flagged for follow-up.
  - Given an anomaly, when reviewed, then a documented investigation outcome is recorded.
- **Originating** BR-503, BR-505, R3 S-058, R4 C-079
- **Depends on** P1-AUD-002, P2-UX-002
- **Tier** CRITICAL · **Size** M · **Owner** Privacy Officer

#### P4-ALR-002 — Audit retention demonstrated (≥ 6 years)
- **As** the Compliance squad
  **I want** evidence that audit logs older than the BR-503 retention floor are retrievable + still bucket-locked
  **So that** retention claims are demonstrable to an auditor.
- **AC**
  - Given audit logs at the retention floor, when sampled + retrieved, then they are intact and bucket-locked.
  - Given retention attestation, when produced for the auditor, then it covers chain-of-custody + bucket-lock evidence.
- **Originating** BR-503, ADR-0008
- **Depends on** P2-ANC-001
- **Tier** CRITICAL · **Size** S · **Owner** Compliance

---

### Epic BAA — BAA Chain Finalization

#### P4-BAA-001 — Comprehensive BAA + subprocessor inventory
- **As** the Privacy Officer
  **I want** a comprehensive BAA + subprocessor inventory covering: every partner, every subprocessor, every BAA signing date + expiration
  **So that** BAA chain is auditor-presentable.
- **AC**
  - Given the inventory, when reviewed, then it is complete + counsel-signed-off.
  - Given an upcoming BAA expiration, when detected, then a renewal workflow auto-triggers ≥ 90 days in advance.
- **Originating** BR-1101, P1-COM-004, P3-SUB-001
- **Depends on** P3-SUB-001
- **Tier** CRITICAL · **Size** M · **Owner** Privacy Officer

#### P4-BAA-002 — Partner BAA renewal automation
- **As** the Privacy Officer
  **I want** a workflow auto-tracking BAA expirations + renewal status
  **So that** no partner data flows under an expired BAA.
- **AC**
  - Given an expired BAA, when detected, then partner-data flows pause + Privacy Officer is paged.
  - Given a renewal in flight, when status is tracked, then milestones (sent / signed / countersigned / stored) are visible.
- **Originating** BR-1101, R7 E-022
- **Depends on** P4-BAA-001
- **Tier** IMPORTANT · **Size** M · **Owner** Privacy Officer

---

### Epic WCAG — Comprehensive Accessibility Audit

#### P4-WCAG-001 — Third-party WCAG 2.1 AA audit
- **As** the UX squad
  **I want** a comprehensive accessibility audit by a qualified third party covering all member-facing + reviewer-facing surfaces
  **So that** XR-009 + ARD Phase 4 ("Comprehensive accessibility audit") is met with external attestation.
- **AC**
  - Given the engagement, when complete, then a report identifies WCAG 2.1 AA conformance + findings + recommendations.
  - Given AA findings, when remediated, then re-testing confirms closure.
  - Given the report, when published internally, then it informs Phase 5+ AAA targets.
- **Originating** XR-009, R6 U-039, ARD §"Phase 4"
- **Depends on** P0-UX-003, P2-UX-003
- **Tier** CRITICAL · **Size** L · **Owner** UX

#### P4-WCAG-002 — User research summary (R6 U-059)
- **As** the UX squad
  **I want** a multi-phase user research summary covering all populations served (member, reviewer, partner ops)
  **So that** R6 U-059 is closed with documented evidence the program produced learning.
- **AC**
  - Given the summary, when reviewed, then it covers research conducted across all phases + key findings + product impact.
- **Originating** R6 U-059, BR-XR-009
- **Depends on** P0-UX-002
- **Tier** IMPORTANT · **Size** M · **Owner** UX

---

### Epic EVI — Attestation Evidence Pack

#### P4-EVI-001 — Evidence pack assembly (per attestation framework)
- **As** the Security Officer + Compliance squad
  **I want** an attestation-evidence pack covering all required controls, sample evidence per control, and chain-of-custody
  **So that** the auditor can perform Type II / certification work efficiently.
- **AC**
  - Given the pack, when reviewed against the framework's control list, then every required control has evidence.
  - Given the pack, when reviewed by external counsel + auditor pre-engagement, then no material gaps remain.
- **Originating** RR-004, P0-COM-008
- **Depends on** P0-COM-008, P4-PEN-003, P4-TPR-001, P4-DR-001, P4-ALR-001..002, P4-BAA-001
- **Tier** CRITICAL · **Size** XL · **Owner** Security Officer

#### P4-EVI-002 — Continuous-control monitoring (post-attestation)
- **As** the Security Officer
  **I want** dashboards demonstrating each attestation control is continuously effective post-attestation
  **So that** Type II requires-continuous-effectiveness is demonstrably met period-over-period.
- **AC**
  - Given each control, when monitored, then a dashboard renders effectiveness + a documented remediation path on any gap.
  - Given a control gap, when detected, then remediation is tracked + auditor-disclosure is documented if material.
- **Originating** RR-004
- **Depends on** P4-EVI-001
- **Tier** CRITICAL · **Size** L · **Owner** Security Officer

#### P4-EVI-003 — Auditor liaison + engagement management
- **As** the Security Officer
  **I want** an internal auditor-liaison process: who fields auditor requests, what's in scope, response SLA
  **So that** the audit engagement runs efficiently and avoids scope creep.
- **AC**
  - Given an auditor request, when received, then it is tracked + responded to within the documented SLA.
  - Given the engagement, when reviewed post-attestation, then a retro identifies process improvements for next cycle.
- **Originating** RR-004
- **Depends on** P4-EVI-001
- **Tier** IMPORTANT · **Size** M · **Owner** Security Officer

---

### Epic TRN — Workforce Training Continuous

#### P4-TRN-001 — Annual training cadence demonstrated
- **As** the Privacy Officer
  **I want** evidence of completed annual HIPAA workforce training across all current workforce
  **So that** BR-1103 has demonstrable continuity for the attestation period.
- **AC**
  - Given the audit period, when reviewed, then 100% of workforce members active during the period have a documented training completion within the cadence.
  - Given non-completion, when surfaced, then sanctions per BR-1104 were applied (or documented reason).
- **Originating** BR-1103, BR-1104, ARD §"Phase 4"
- **Depends on** P2-COM-004
- **Tier** CRITICAL · **Size** M · **Owner** Privacy Officer

#### P4-TRN-002 — Role-specific training tracks
- **As** the Privacy Officer
  **I want** role-specific training tracks (reviewer-track, operator-track, engineer-track) with material reflecting role-specific risks
  **So that** workforce training is risk-targeted, not generic.
- **AC**
  - Given each role, when their training material is reviewed, then it covers role-specific PII handling, audit obligations, escalation paths.
- **Originating** BR-1103
- **Depends on** P4-TRN-001
- **Tier** IMPORTANT · **Size** L · **Owner** Privacy Officer

---

### Epic RES — Resilience Validation

#### P4-RES-001 — Chaos testing on staging-prod-like environment
- **As** the Platform/SRE squad
  **I want** chaos-engineering experiments on a staging environment that matches prod topology
  **So that** resilience claims (circuit breakers, retries, fallbacks per ADR-0006) are tested under fault.
- **AC**
  - Given a chaos experiment (kill a Pub/Sub subscriber, drop AlloyDB read replica, block KMS calls), when run, then the system degrades gracefully per the documented circuit-breaker + fallback behavior.
  - Given the experiments, when reviewed, then any gaps identified result in code changes + retests.
- **Originating** ADR-0006 §"Error taxonomy + retry", R5 D-103
- **Depends on** P1-DAT-001, P1-VER-001
- **Tier** IMPORTANT · **Size** XL · **Owner** Platform/SRE

#### P4-RES-002 — Load test at 2x peak projected demand
- **As** the Platform/SRE squad
  **I want** a load test sustaining 2x projected peak Verification API + ingestion demand
  **So that** scaling headroom is validated before attestation.
- **AC**
  - Given the test, when run, then SLO targets hold + ADR-0009 latency floor is preserved.
  - Given the test, when reviewed, then any saturation point is documented + scaling levers identified.
- **Originating** AD-021, BR-404
- **Depends on** P1-VER-005
- **Tier** IMPORTANT · **Size** L · **Owner** Platform/SRE

---

## Phase 4 cross-track summary

| Track | Critical stories | Important / Supportive |
|-------|------------------|------------------------|
| Engineering | P4-RES-001..002 (IMPORTANT) | — |
| Security | P4-PEN-001..003, P4-TPR-001, P4-EVI-001..002 | P4-EVI-003 |
| Compliance | P4-ALR-001..002, P4-BAA-001, P4-TRN-001 | P4-BAA-002, P4-TRN-002 |
| UX | P4-WCAG-001 | P4-WCAG-002 |
| Infrastructure | P4-DR-001..002, P4-RUN-001 | P4-RUN-002 |

## Phase 4 risk-register linkage

| Risk | Story closing it (or downgrading) |
|------|-----------------------------------|
| RR-004 (HITRUST or SOC 2 status) | P4-EVI-001..003 |
| RR-008 (vendor concentration) | P4-DR-001 (region failover validated) |

---

## Out of scope for Phase 4

- AAA accessibility (post-Phase 4 if required by member-impact study).
- Multi-cloud abstraction (only triggered if RR-008 escalates).
- Member portal full-surface (per scope decided in P0-ADR-002 — extensions into v2).
- Per-actor non-repudiation via WebAuthn (deferred to v2 per ADR-0008).

---

## Continuous (post-Phase-4) Operating Loops

These are not "stories" with completion criteria but recurring obligations seeded by Phase 4 work — captured here for visibility:

- Quarterly DR drill (P4-DR-001 cadence)
- Quarterly runbook drill (P4-RUN-002 cadence)
- Annual access review (P0-IAM-004 cadence)
- Annual audit-log access review (P4-ALR-001 cadence)
- Annual third-party security review (P2-COM-005 / P4-TPR-001 cadence)
- Annual workforce training (P4-TRN-001 cadence)
- Annual subprocessor security review (P3-SUB-002 cadence)
- Annual penetration test (P4-PEN-001 cadence; new-feature-driven if material)
- Continuous-control monitoring (P4-EVI-002)
- Per-quarter STRIDE threat model review (P0-SEC-003)

These cadences should be tracked in the operations calendar, not in this backlog, but each cadence's first execution is a Phase-4-or-earlier story above.
