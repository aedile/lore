# HIPAA Posture — Control Inventory

This document is the single source of truth for *which HIPAA-relevant
controls are enforced today*, *which are scaffolded but not yet
active*, and *which are deferred to specific upcoming phases*.

The harness has configured-but-not-enforced controls. Reading
`.env.example` plus `CONSTITUTION.md` can give the false impression that
redaction, audit, tokenization, and key-rotation primitives are all
live. This inventory keeps that perception aligned with reality.

The synthesis pass (rounds 1-8 review consolidation) materially changed many
control statuses by:

- Adding 40+ new business rules covering Privacy Rule, Breach Notification
  Rule, workforce, documentation, and member-facing UX (see BRD)
- Authoring 8 ADRs that codify decisions for many previously STUBBED items
  (see `docs/adr/ADR-0002` through `ADR-0009`)
- Adding architectural patterns (outbox, idempotency, PEP/PDP, two-person)
  with explicit BR ownership

Many controls remain STUBBED or DEFERRED but now have explicit BR + ADR +
ARD-component references that define the path forward.

**Status legend:**

- **LIVE** — actively enforced today; failing the control fails CI or
  startup.
- **STUBBED** — primitive exists but is empty / vacuously passing;
  the gate is wired and will activate when the primitive contains code.
- **PLANNED-PHASE-N** — not yet started; named in the roadmap with the
  phase that owns it; BR + ADR specify what it will be.
- **CONFIGURED-ONLY** — environment variable or constant exists but
  no code consumes it yet; presence on disk is not enforcement.
- **`[ADVISORY]`** — cannot be programmatically enforced; relies on process,
  audit, or human judgment.
- **NOT-APPLICABLE** — out of scope for v1 (e.g. physical safeguards
  for a software project).

Each row cites the BRD rule, ARD component, or ADR that owns it.

---

## HIPAA Security Rule — Technical Safeguards

### §164.312(a)(1) Access Control

| Control | Status | Where | Activation |
|---|---|---|---|
| Authentication required on all non-exempt routes (PEP/PDP per AD-025) | **STUBBED** | `tests/unit/test_auth_coverage.py` introspects `app.routes`. Today only `/health` exists and is exempt. PEP/PDP library specified per AD-025; `get_current_operator` dependency to be implemented per ADR-0004. | Activates as soon as the first non-exempt route is added. JWT contract per ADR-0004 ratified. |
| `AUTH_MODE='none'` forbidden in non-dev | **LIVE** | `bootstrapper/config_validation.py::validate_settings` raises `ConfigurationError` at app startup. | Now. |
| Role taxonomy (BRD §"Role Taxonomy" — 13 roles per synthesis) | **PLANNED-PHASE-1** | BRD §"Role Taxonomy" specifies 13 roles; ARD specifies IAM groups per role. Sequelae PH residency boundary per BR-506 + AD-003. | Phase 0 IAM setup → Phase 1 first non-exempt routes. |
| Session management / token rotation per ADR-0004 | **PLANNED-PHASE-1** | ADR-0004 specifies max 5-minute TTL; `jti` replay defense in Memorystore. | Phase 1 Verification API implementation. |
| IDOR / per-resource authorization (AD-025) | **PLANNED-PHASE-1** | AD-025 specifies `@requires_resource_access` decorator. | Phase 1 first authenticated route. |
| Two-person rule for high-risk operations (AD-026) | **PLANNED-PHASE-2** | AD-026 enumerates ops requiring two-person; PAM integration. | Phase 2 vault key rotation, deletion override, etc. |

### §164.312(a)(2)(iv) Encryption and Decryption

| Control | Status | Where | Activation |
|---|---|---|---|
| PII tokenization architecture | **STUBBED** | `shared/security/` directory exists but empty. ADR-0003 specifies keyed deterministic tokenization, per-class HMAC keys, envelope encryption with per-day DEK + per-class HSM-backed KEK. | Phase 0 tokenization smoke test exit criterion. |
| KMS HSM tier for Vault keys (R3 S-077) | **PLANNED-PHASE-0** | ARD §"PII Vault" + AD-008 specify HSM tier. IaC config required. | Phase 0 KMS keyring provisioning. |
| Algorithm versioning (`v1:` prefix per ADR-0003) | **PLANNED-PHASE-0** | ADR-0003 §"Algorithm versioning" specifies prefix on all crypto outputs. | Phase 0 with first tokenization implementation. |

### §164.312(b) Audit Controls

| Control | Status | Where | Activation |
|---|---|---|---|
| Audit log primitive | **STUBBED** | `shared/security/audit/` to be created per ADR-0005 outbox pattern. BR-501 enumerates 30+ event classes. | Phase 0 audit smoke test (every action class emits to `audit-events`); Phase 1+ per-class implementation. |
| Hash-chained audit integrity (BR-504) | **PLANNED-PHASE-2** | ADR-0008 specifies hash chain + cross-org replication + RFC 3161 anchoring. | Phase 2 high-criticality audit tier. |
| Append-only audit access (BR-504) | **PLANNED-PHASE-1** | GCS Bucket Lock for high-criticality tier per AD-013. BigQuery operational tier with table-level ACL grants write to Dataflow only. | Phase 1 audit consumer Dataflow job. |
| Retention by event class (BR-503) | **PLANNED-PHASE-1** | BR-503 specifies retention per class. AD-027 specifies routing to operational vs high-criticality tier. Storage lifecycle policies per ARD §"Backup and DR". | Phase 1 audit consumer + sink lifecycle policies. |
| Auditor query monitoring (BR-505) | **PLANNED-PHASE-2** | BR-505 specifies monitoring; ARD Audit context §"Auditor query monitoring". | Phase 2 audit log read access for compliance staff. |
| Audit chain external anchoring (ADR-0008) | **PLANNED-PHASE-2** | Cross-organization replication to Compliance org bucket + RFC 3161 trusted timestamp. | Phase 2 high-criticality tier. |

### §164.312(c)(1) Integrity

| Control | Status | Where | Activation |
|---|---|---|---|
| Artifact signing (BR-504; ADR-0008 chain) | **STUBBED** | `ARTIFACT_SIGNING_KEY` env required; validator checks distinct from `SECRET_KEY`. No signing primitive yet. ADR-0008 specifies hash chain integrity. | Phase 2 high-criticality audit emission. |
| Mutation testing on security-critical code | **STUBBED (vacuously passing)** | `mutmut` configured to target `shared/security/` and `bootstrapper/auth.py` with 60%/50% kill-rate gates. Both targets empty. | First security primitive committed in Phase 1+. |
| Schema drift detection (BR-304) | **PLANNED-PHASE-1** | BR-304 specifies; ARD Ingestion & Profiling §"DQ engine" implements. | Phase 1 DQ engine with single partner. |
| Container image signing (AD-031) | **PLANNED-PHASE-0** | AD-031 specifies Cosign signing + Binary Authorization. | Phase 0 CI/CD pipeline + Cloud Run deploy. |

### §164.312(d) Person or Entity Authentication

| Control | Status | Where | Activation |
|---|---|---|---|
| JWT authentication (RS256, ADR-0004) | **PLANNED-PHASE-1** | ADR-0004 specifies full contract; `JWT_PUBLIC_KEY` / `JWT_PRIVATE_KEY` env vars exist. | Phase 1 Verification API. |
| Brute force lockout (BR-402: 3-tier progressive) | **PLANNED-PHASE-2** | BR-402 specifies; Verification context §"Lockout enforcement"; ADR-0009 timing-equalized. | Phase 2 Verification API hardening. |
| Identity-scoped rate limits (XR-004) | **PLANNED-PHASE-2** | XR-004 specifies; rate-limit cache via Memorystore HA. | Phase 2 Verification API. |
| MFA for sensitive roles (R3 S-012) | **PLANNED-PHASE-1** | ADR-0004 references; specific roles (PII Handler, Break-Glass, Auditor, Privacy/Security Officer). | Phase 1 IAM setup. |

### §164.312(e)(1) Transmission Security

| Control | Status | Where | Activation |
|---|---|---|---|
| TLS in transit on database (`DATABASE_TLS_ENABLED`) | **LIVE** | `bootstrapper/config_validation.py` raises `ConfigurationError` at startup if `DATABASE_TLS_ENABLED=false` in staging/production. | Now. |
| TLS configuration (ADR-0004 §8) | **PLANNED-PHASE-0** | ADR-0004 specifies TLS 1.2+ AEAD-only; mTLS at LB. | Phase 0 IaC for LB + Cloud Run. |
| HTTPS redirect (T8.1 in `.env.example`) | **CONFIGURED-ONLY** | `HTTPS_REDIRECT_ENABLED` env var exists. No middleware. | Phase 1 reverse proxy in front of app. |
| mTLS between services (deferred per AD-018 service mesh decision) | **NOT-APPLICABLE for v1** | ADR-0007 explicitly skipped service mesh; mTLS via GFE. | Reintroduce if AD-007 sunset triggers fire. |

---

## HIPAA Privacy Rule — Synthesis Additions

### Notice of Privacy Practices (§164.520)

| Control | Status | Where | Activation |
|---|---|---|---|
| NPP exists (BR-901) | **PLANNED-PHASE-1** | BR-901; Member Rights context §"NPP service". `[ADVISORY]` for content authoring (counsel-engaged). | Phase 1 NPP authoring + delivery. |
| NPP layered notice approach (R6 U-005) | **PLANNED-PHASE-1** | R6 U-005 specifies layered design (1-paragraph plain-language summary + section navigation + full legal NPP). | Phase 1 with NPP authoring. |
| Acknowledgment of receipt (BR-901) | **PLANNED-PHASE-1** | BR-901; Member Rights context. | Phase 1 with NPP delivery. |

### Member Rights (§164.524, §164.526, §164.528, §164.522)

| Control | Status | Where | Activation |
|---|---|---|---|
| Right of Access fulfillment (BR-903) | **PLANNED-PHASE-2** | BR-903 specifies 30-day SLA; Member Rights context §"DSAR workflow service". | Phase 2 Member Rights workflows. |
| Right to Amendment (BR-904) | **PLANNED-PHASE-2** | BR-904 specifies; Member Rights + Canonical Eligibility for propagation. | Phase 2. |
| Right to Accounting of Disclosures (BR-905) | **PLANNED-PHASE-2** | BR-905; Audit context for `DISCLOSURE_TO_EXTERNAL_PARTY` events. | Phase 2 with audit context full. |
| Right to Restriction (BR-906) | **PLANNED-PHASE-2** | BR-906; Member Rights context for restriction tracking. | Phase 2. |
| Right to Confidential Communications (BR-907) | **PLANNED-PHASE-2** | BR-907; Member Rights context for preference tracking. | Phase 2. |
| Personal representative flows (BR-1303) | **PLANNED-PHASE-2** | BR-1303; Member Rights context §"Personal representative service". | Phase 2 with representative authority verification. |
| Member Complaint Procedure (BR-908) | **PLANNED-PHASE-2** | BR-908; Member Rights context §"Complaint workflow". | Phase 2. |
| Authorization tracking (BR-902) | **PLANNED-PHASE-2** | BR-902; Member Rights context §"Authorization tracking". | Phase 2. |

### Privacy Rule Operational

| Control | Status | Where | Activation |
|---|---|---|---|
| Minimum-necessary (§164.502(b)) | **PLANNED-PHASE-1** | BR-502 + per-role accessible-field allow-list per R3 S-059. | Phase 1 PEP/PDP with role-based field scopes. |
| Data minimization at acquisition (BR-XR data minimization, S-017) | **PLANNED-PHASE-1** | Per-partner YAML mapping enumerates only used fields; unused fields dropped at format-adapter stage. | Phase 1 Mapping Engine. |
| Sale of PHI prohibition (BR-902) | **`[ADVISORY]`** | No current monetization path; review at any future change. | N/A unless triggered. |
| Marketing communications restrictions (§164.508(a)(3)) | **`[ADVISORY]`** | Eligibility data not used for marketing without authorization. | N/A unless triggered. |

---

## HIPAA Breach Notification Rule — Synthesis Additions

| Control | Status | Where | Activation |
|---|---|---|---|
| Discovery clock + reasonable-diligence detection (BR-1001) | **PLANNED-PHASE-2** | BR-1001 specifies; Round 3 SIEM (R3 S-046) + Round 5 monitoring provide detection baseline. | Phase 2 SIEM operational. |
| Risk Assessment Methodology (BR-1002) | **`[ADVISORY]`** | BR-1002 specifies four-factor framework. Counsel-authored methodology. | Pre-Phase 1 counsel-engaged work. |
| Breach Notification Content templates (BR-1003) | **`[ADVISORY]`** | BR-1003 specifies content elements per §164.404(c). | Pre-Phase 1 counsel-authored. |
| Individual notification 60-day timeline (BR-1004) | **`[ADVISORY]`** | Per-incident SLA tracking. | Pre-Phase 1 IR plan. |
| Substitute Notice (BR-1005) | **`[ADVISORY]`** | Procedure + toll-free vendor procurement. | Pre-Phase 1 vendor selection. |
| Media Notice (BR-1006) | **`[ADVISORY]`** | Procedure; media list per state; PR coordination. | Pre-Phase 1 procedure. |
| HHS Notification (BR-1007) | **`[ADVISORY]`** | HHS Breach Portal access; rollup tracking. | Pre-Phase 1 portal access. |
| HITECH BA Notification (BR-1008) | **`[ADVISORY]`** | BAA terms; per-incident clock tracking. | Pre-Phase 1 BAA template. |
| State Law Breach Matrix (BR-1009) | **`[ADVISORY]`** | Counsel-authored 50-state matrix. | Phase 2 (Round 4 L-014 BLOCKER). |
| Forensic Preservation on Suspected Breach (BR-1010) | **PLANNED-PHASE-2** | Per ADR-0008 forensic preservation procedure + R3 S-051 chain-of-custody. | Phase 2 audit chain validator + forensic export. |

---

## Workforce and Officer Designations

| Control | Status | Where | Activation |
|---|---|---|---|
| Privacy Officer designation (BR-1101) | **`[ADVISORY]`** | HR-coordinated; CEO designation; per AD-030 required pre-Phase 1. | Phase 0 (organizational decision). |
| Security Officer designation (BR-1102) | **`[ADVISORY]`** | Same as above. | Phase 0. |
| Workforce Training (BR-1103) | **PLANNED-PHASE-2** | Compliance-records DB + training compliance report; `[ADVISORY]` for delivery. | Phase 2 training program LIVE. |
| Workforce Sanctions Policy (BR-1104) | **`[ADVISORY]`** | HR + counsel coordination. | Phase 0 policy authoring; ongoing application. |
| Background checks for sensitive roles (BR-1105) | **`[ADVISORY]`** | HR + counsel; state law variation. | Phase 0 hiring policy. |
| Departure procedures + IAM revocation (BR-1106) | **PLANNED-PHASE-1** | IAM revocation programmatic on HR offboarding signal; `[ADVISORY]` for audit review portion. | Phase 1 with IAM setup. |

---

## Documentation and Records

| Control | Status | Where | Activation |
|---|---|---|---|
| HIPAA Documentation Retention (BR-1201, §164.530(j) and §164.316(b)) | **PLANNED-PHASE-1** | Documentation retention infrastructure; quarterly compliance review `[ADVISORY]`. | Phase 0 setup; Phase 1+ ongoing. |
| PHI Inventory (BR-1202) | **PLANNED-PHASE-0** | BR-1202 specifies; counsel-reviewed; required Phase 0 exit criterion. | Phase 0 inventory documented. |
| Risk Assessment Cadence (BR-1203, §164.308(a)(1)(ii)(A)) | **`[ADVISORY]`** | Annual delivery; methodology document; tracked to remediation. | Phase 0 first assessment. |
| Policies and Procedures (BR-1204, §164.316) | **`[ADVISORY]`** | Counsel-engaged authoring; version control per BR-XR-011. | Phase 0 P&P document set. |

---

## Member-Facing UX (BRD §"Member-Facing UX" + XR-007, XR-008, XR-009)

| Control | Status | Where | Activation |
|---|---|---|---|
| Plain language commitment (XR-007) | **PLANNED-PHASE-1** | CI gate on Flesch-Kincaid; content design CODEOWNERS. | Phase 1 first member-facing content. |
| Multilingual support (XR-008, Title VI) | **PLANNED-PHASE-1** | English + Spanish minimum; `MEMBER_LANGUAGE_PRIORITY_LIST`; CI gate on translation coverage. | Phase 1 with NPP authoring. |
| Accessibility WCAG 2.1 AA (XR-009) | **PLANNED-PHASE-1** | CI gate (axe / Lighthouse); per-release manual audit; annual third-party `[ADVISORY]`. | Phase 1 first UI surface. |
| Verification failure UX coordination (BR-1301) | **PLANNED-PHASE-1** | Joint design with Lore application UX team; OLA per R7 E-015. | Phase 1 Verification implementation. |
| Lockout recovery service blueprint (BR-1308) | **PLANNED-PHASE-1** | Service blueprint + identity verification standard. | Phase 1 Verification implementation. |
| Member portal scope (BR-1306) | **DECISION PENDING** | Per RR-009; ADR `[member-portal-scope]` forthcoming. | Phase 0 decision. |
| Trauma-informed design (BR-1305) | **PLANNED-PHASE-1** | Style guide enforcement via design-system patterns. | Phase 1 first member-facing UI. |

---

## Specialized Data Categories

| Control | Status | Where | Activation |
|---|---|---|---|
| PII vs PHI Classification (BR-1401) | **LIVE (BRD)** | BRD §"PII vs PHI Classification" table. PHI inventory consumes the classification. | Now (table is the source of truth). |
| 42 CFR Part 2 decision (BR-1402) | **DECISION PENDING** | Per RR-006; counsel-engaged Phase 0 decision. | Phase 0. |
| GINA / Mental Health / State Sensitive Categories (BR-1403) | **`[ADVISORY]`** | Per-state matrix; counsel-engaged. | Phase 0 matrix; per-partner audit at onboarding. |
| COPPA Scope (BR-1404) | **DECISION PENDING** | Per RR-007; counsel-engaged decision. | Phase 0. |

---

## Cross-Cutting BRD Rules (XR-001..XR-012)

| Control | Status | Where | Activation |
|---|---|---|---|
| **XR-001** Layered Configurability | **PLANNED-PHASE-0** | CI lint for inline literals; resolution-order test. | Phase 0 with first parameter consumption. |
| **XR-002** No Magic Numbers | **PLANNED-PHASE-0** | Same as XR-001. | Phase 0. |
| **XR-003** Privacy-Preserving Collapse | **PLANNED-PHASE-1** | Integration test + static analysis + latency-distribution test (ADR-0009). | Phase 1 Verification. |
| **XR-004** Identity-Scoped Lockouts | **PLANNED-PHASE-2** | Integration test exercising attack patterns. | Phase 2 Verification hardening. |
| **XR-005** Zero PII in Logs | **LIVE (logging + fixture); PLANNED (production sampling)** | structlog redaction processors LIVE; CI fixture redaction gate LIVE; production sampling job planned Phase 2. | structlog and CI gate now; sampling job Phase 2. |
| **XR-006** Irreversibility Separation | **PLANNED-PHASE-2** | Code-path inventory; confirmation-token signature; module isolation. | Phase 2 deletion + replay paths. |
| **XR-007** Plain Language | **PLANNED-PHASE-1** | CI gate on Flesch-Kincaid. | Phase 1 first member-facing content. |
| **XR-008** Multilingual Support | **PLANNED-PHASE-1** | Test for required content in supported languages. | Phase 1. |
| **XR-009** Accessibility WCAG 2.1 AA | **PLANNED-PHASE-1** | CI accessibility gate; manual audit `[ADVISORY]`. | Phase 1. |
| **XR-010** Configuration Discipline | **PLANNED-PHASE-0** | CI parameter-schema validator; load-time validation test. | Phase 0 with first config consumer. |
| **XR-011** Decision Authority | **PLANNED-PHASE-0** | CI gate on PR amendments to BRD/ARD/ADR; named approver required. | Phase 0 (governance precondition). |
| **XR-012** Bidirectional Traceability | **PLANNED-PHASE-0** | CI gate validating BR ↔ component mappings. | Phase 0 (BRD + ARD synthesis precondition). |

---

## Operational / Supply Chain

| Control | Status | Where | Activation |
|---|---|---|---|
| **Branch protection on `main`** | **NOT ENABLED — FINDING** | `gh api repos/aedile/lore/branches/main/protection` returns HTTP 404. | **REMEDIATION REQUIRED**: enable in GitHub Settings before backlog work begins. |
| Secrets scanning (gitleaks) | **LIVE** | Pre-commit hook + CI job. | Now. |
| Secrets scanning (detect-secrets baseline) | **LIVE on hook; baseline must be regenerated on first install** | `.secrets.baseline` was authored by hand for the bootstrap commit; regenerate via `detect-secrets scan > .secrets.baseline` on first install. | First `poetry install` + `pre-commit install`. |
| Dependency vulnerability scanning (pip-audit) | **LIVE** | `scripts/pip-audit.sh` runs in ci-local and CI. | Now. |
| Container image scanning (Trivy / SBOM) | **PLANNED-PHASE-0** | Per ADR-0007 + AD-031 image signing; SBOM via cyclonedx in CI. | Phase 0 with first image build. |
| Dockerfile HEALTHCHECK | **LIVE** | Dockerfile uses Python urllib to hit /health every 30s. | Now. |
| `make merge-pr` audit-logged merge | **STUBBED** | `scripts/merge-pr.sh` exists but requires `make ci-local` to pass. | After T0.7 (harness end-to-end validation). |
| IaC framework (Terraform; ADR `[iac-framework]` forthcoming) | **PLANNED-PHASE-0** | Per Round 5 D-001. | Phase 0 (first deploy). |
| SLI/SLO/Error Budget engineering (Round 5 D-022..025; per service) | **PLANNED-PHASE-1** | Per ADR-0006 metrics + R5 D-023 SLO targets. | Phase 1 first SLO measurement. |
| On-call rotation structure (Round 5 D-034) | **`[ADVISORY]`** | Operational; PagerDuty integration. | Phase 1 production traffic precondition. |
| DR drill program (Round 5 D-039) | **PLANNED-PHASE-1** | Quarterly tabletop; bi-annual synthetic; annual prod drill. | Phase 1 first quarterly drill. |
| Backup integrity testing (Round 5 D-043) | **PLANNED-PHASE-1** | Quarterly restore drill. | Phase 1 first restore. |
| Secret rotation automation (Round 5 D-051) | **PLANNED-PHASE-0** | Per-secret rotation in IaC; Secret Manager auto-rotation. | Phase 0 setup. |
| Incident command structure (Round 5 D-075 + ADR-0008) | **`[ADVISORY]`** | IR plan; war room procedures; postmortem culture. | Pre-Phase 1 readiness. |

---

## Required Operator Action Before Production

The following items are NOT optional once domain code starts handling
real partner data. They are listed here so they cannot be forgotten:

1. **Enable branch protection on `main`.** See "Operational / Supply
   Chain" table above.
2. **Provision a real `.secrets.baseline`** via `detect-secrets scan`.
3. **Generate distinct production secrets** for `SECRET_KEY`,
   `AUDIT_KEY`, `ARTIFACT_SIGNING_KEY`, `PII_ENCRYPTION_KEY`. Each
   must be unique. The `validate_settings` startup gate enforces
   distinctness between `SECRET_KEY` and `ARTIFACT_SIGNING_KEY`;
   distinctness across the others is operator-managed.
4. **Provision a real pgbouncer SCRAM-SHA-256 hash** in
   `pgbouncer/userlist.txt` (gitignored). The committed
   `userlist.txt.example` is a placeholder.
5. **Set `DATABASE_TLS_ENABLED=true`** in production. The
   `validate_settings` gate refuses to start otherwise.
6. **Designate Privacy Officer + Security Officer** (AD-030; BR-1101, BR-1102).
   Both US-resident; both required pre-Phase 1 production traffic.
7. **Author counsel-engaged work products** before Phase 1+:
   NPP (BR-901); Workforce Training program (BR-1103); Workforce Sanctions
   Policy (BR-1104); P&P documents (BR-1204); Risk Assessment methodology
   (BR-1002); Breach Notification templates (BR-1003); 50-state Breach
   Notification Matrix (BR-1009); BAA standard terms (per R4 L-030);
   Partner Data Sharing Agreement template (per R4 L-032).
8. **Author a Business Associate Agreement (BAA) chain document**
   listing every subprocessor (per BRD §"Security and Privacy" NFR).
   Sequelae PH must be explicitly listed with the no-plaintext-PII
   scope per BR-506.
9. **Decide 42 CFR Part 2 applicability** (RR-006; counsel-engaged Phase 0).
10. **Decide attestation roadmap** (RR-004; HITRUST CSF or SOC 2 Type II).
11. **Decide member portal scope** (RR-009; ADR `[member-portal-scope]`).

---

## Document Maintenance

This file is the source of truth for HIPAA control state. Update it when:

- A control moves from STUBBED to LIVE (a primitive is implemented).
- A new control is added (BRD amendment, new ADR).
- A deferred control's target phase changes.

Stale rows in this file are themselves a HIPAA risk: if "audit log
hash chain" stays "DEFERRED" after it ships, a future contributor
will assume it's not live and may not enforce its invariants.

This file was synthesized to reflect the consolidated state after
review rounds 1-8 (`docs/reviews/01-principal-architect.md` through
`docs/reviews/08-project-manager.md`). Subsequent BRD/ARD amendments
should update this inventory.
