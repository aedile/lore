# Phase 0 — Foundation Backlog

| Field | Value |
|-------|-------|
| **ARD reference** | §"Phased Delivery" / Phase 0 |
| **Goal** | Land the empty production substrate; designate governance roles; scope open ADRs. |
| **Status** | LIVE BACKLOG |

---

## Phase 0 Goal

Land the empty production substrate that everything else builds on; establish governance.

## Phase 0 Entry Gate

- Phase 00 (Harness) exit criteria met (`make ci-local` returns 0; ADR-0001 reflects shipped state; `docs/retros/phase-00.md` written; branch protection on `main` enabled).
- Synthesis PR (BRD + ARD + ADRs 0002–0009 + HIPAA_POSTURE) merged to `main`.
- Approved Capex/Opex envelope from Finance for GCP minimum-instance baseline (Verification + Tokenization at `min=2`).

## Phase 0 Exit Criteria (per ARD)

- IAM audit confirms residency conditions enforce as designed (BR-506).
- Request-origin geofencing verified (BR-506 synthesis tightening).
- VPC-SC perimeter test confirms exfiltration paths are closed.
- A no-op service deployable to Cloud Run hits all observability, logging, and audit-emission surfaces correctly (ADR-0006).
- Tokenization smoke test (tokenize, detokenize, audit emission) passes end-to-end through the inner perimeter, demonstrating ADR-0003 keyed-deterministic primitive.
- IaC drift detection runs daily without alerts.
- CI/CD pipeline deploys via OIDC (no service account keys).
- Container Binary Authorization configured (signed images required).
- Privacy Officer + Security Officer designated and US-resident (BR-1101, BR-1102; AD-030).
- PHI inventory documented and counsel-reviewed (BR-1202).
- 42 CFR Part 2 decision documented (BR-1402; RR-006).
- Attestation roadmap decided — HITRUST or SOC 2 (RR-004).
- ARD `[part-2-implementation]`, `[member-portal-scope]`, `[reviewer-decision-support]`, `[friction-mechanism]`, `[iac-framework]`, `[dr-strategy]`, `[partner-sftp]`, `[sequelae-ph-ml-access]` ADRs all authored or scoped.

---

## Epics

| Key | Epic | Description |
|-----|------|-------------|
| GCP | GCP Foundation | Projects, residency, geofencing, billing accounts |
| IAM | Identity & Access | IAM groups, residency conditions, OIDC for CI, service identities |
| VPC | VPC Service Controls | Outer + inner perimeters, exfiltration tests |
| KMS | Cryptographic Foundation | HSM keyrings, per-class KEKs, per-day DEK rotation |
| IAC | Infrastructure as Code | Terraform framework, drift detection, change control |
| CICD | Build & Deploy Pipeline | OIDC auth, Cosign signing, Binary Authorization, SLSA provenance |
| OBS | Observability Backbone | Logging, tracing, metrics, audit infrastructure |
| DAT | Data Substrate | AlloyDB, Cloud SQL Vault, Pub/Sub topics + schemas, BigQuery, Cloud Storage |
| TBL | Operational Tables | Outbox tables per context, processed_events per consumer, schema migrations |
| TOK | Tokenization Smoke Path | TokenizationService skeleton + ADR-0003 primitive proof |
| CFG | Configuration Ledger | 47-parameter ledger LIVE; runtime validation; per-environment promotion |
| ADR | Open ADRs Authored | Author/scope the 8 deferred ADRs listed in ARD Phase 0 exit |
| COM | Compliance Foundation | Officers, P&P, PHI inventory, sanctions, retention infrastructure, training plan, attestation roadmap |
| UX  | UX Foundation | Design system, research program, WCAG audit commitment, trauma-informed framework |
| SEC | Security Baseline | Cloud Armor, secrets management, scanner gates, threat-model maintenance |

---

## Stories

### Epic GCP — GCP Foundation

#### P0-GCP-001 — Provision GCP organization + folder hierarchy
- **As** the Platform/SRE squad
  **I want** a GCP organization with folders for `engineering/{dev,staging,prod}` and `compliance/{anchor-registry}`
  **So that** the cross-org separation in ADR-0008 (audit anchor) is structurally enforced and Engineering-org admin compromise cannot rewrite the chain head registry.
- **AC**
  - Given the GCP organization, when the folder layout is inspected, then it matches `engineering/{dev,staging,prod}` + `compliance/{anchor-registry}` exactly.
  - Given an Engineering-org admin principal, when they attempt to modify IAM in the Compliance folder, then the operation is denied (separate org admin).
  - Given a Terraform plan, when run with the Compliance-org credentials, then it can read but not write the Engineering folders (and vice versa).
- **Originating** ADR-0008 §3a, AD-017, AD-030
- **Depends on** —
- **Tier** CRITICAL · **Size** M · **Owner** Platform/SRE

#### P0-GCP-002 — Land three engineering projects (dev, staging, prod)
- **As** the Platform/SRE squad
  **I want** three GCP projects with consistent naming, billing, and bootstrap APIs enabled
  **So that** environments are isolated and IAM bindings are project-scoped per AD-017.
- **AC**
  - Given the three projects, when their API enablement is listed, then the bootstrap set (Cloud Run, AlloyDB, Cloud SQL, KMS, Pub/Sub, BigQuery, Cloud Storage, IAM, Logging, Monitoring, Trace, Artifact Registry, Cloud Build, VPC Access, Cloud DNS, Datastream) is enabled in each.
  - Given the three projects, when their billing is inspected, then each is linked to the same billing account with project-level budget alerts at 50/80/100%.
  - Given the three projects, when their default region is queried, then it is `us-central1` (or the AD-017 chosen region) consistently.
- **Originating** AD-017
- **Depends on** P0-GCP-001
- **Tier** CRITICAL · **Size** S · **Owner** Platform/SRE

#### P0-GCP-003 — Region + zone selection ADR (formalize)
- **As** the Architecture team
  **I want** the region/zone selection captured in an ADR
  **So that** future multi-region and DR work has the rationale chain.
- **AC**
  - Given the new ADR, when reviewed, then it documents primary region, two zones, latency model from PH workforce vantage, BAA region constraints, and DR target region.
  - Given the ADR, when cross-referenced with ARD §"Region and Zones", then no contradictions exist.
- **Originating** AD-017, RR-008
- **Depends on** —
- **Tier** IMPORTANT · **Size** S · **Owner** Architecture

#### P0-GCP-004 — Sequelae PH residency conditions on IAM bindings
- **As** the Security squad
  **I want** every IAM binding for PH-resident principals to carry residency conditions enforcing data-class access scope
  **So that** PH-resident workforce can never access plaintext PII tier despite being legitimately on the workforce.
- **AC**
  - Given a PH-resident principal, when they attempt to read the Vault (Cloud SQL Vault project + KMS HSM keyring), then access is denied by IAM Conditions before reaching the resource.
  - Given a PH-resident principal, when they attempt to read tokenized data (canonical_member, BigQuery analytical replica), then access is granted (assuming role grants it).
  - Given an IAM audit script run, when results are reviewed, then 100% of PH-resident bindings carry an explicit residency Condition.
- **Originating** BR-506, AD-002, AD-017
- **Depends on** P0-GCP-002
- **Tier** CRITICAL · **Size** M · **Owner** Security

#### P0-GCP-005 — Request-origin geofencing for Verification API
- **As** the Security squad
  **I want** the Verification API public load balancer to enforce geofencing at the request-origin, not just the account record
  **So that** BR-506 (synthesis tightening) holds: a Sequelae PH workforce member cannot access a US member's verification path even via VPN tunneling unless their request originates from the US.
- **AC**
  - Given a request from a non-allowlisted geography, when it reaches the Verification API, then Cloud Armor returns 403 before the request enters the application.
  - Given a request from an allowlisted geography but with a member-record residency condition mismatch, when it reaches the application, then it is denied by the PEP layer (AD-025) and audited.
  - Given a synthetic test from PH IP space, when issued against a US-only verification path, then it is denied (Cloud Armor or PEP, whichever fires first; both must be configured).
- **Originating** BR-506, AD-017, R3 S-054
- **Depends on** P0-GCP-002, P0-SEC-001
- **Tier** CRITICAL · **Size** M · **Owner** Security

---

### Epic IAM — Identity & Access

#### P0-IAM-001 — IAM group taxonomy mapped to BRD 13-role list
- **As** the Security squad
  **I want** each BRD role mapped to exactly one IAM group, named consistently
  **So that** role-to-group is unambiguous and audit/access-review queries are mechanical.
- **AC**
  - Given the IAM group listing, when compared with BRD §"Role taxonomy", then every role has a corresponding group; no orphaned groups exist.
  - Given a workforce member, when their group memberships are listed, then they belong to exactly the groups for their assigned roles (no shadow grants).
- **Originating** BRD §"Role taxonomy", AD-003
- **Depends on** P0-GCP-001
- **Tier** CRITICAL · **Size** S · **Owner** Security

#### P0-IAM-002 — Service identity per Cloud Run service (no shared SAs)
- **As** the Security squad
  **I want** one dedicated service account per Cloud Run deployable
  **So that** least-privilege is enforced and audit logs attribute actions to the correct service principal.
- **AC**
  - Given the IAM listing, when grouped by service-account-to-Cloud-Run-service, then the relationship is 1:1 (no SA backs more than one service).
  - Given each SA, when its IAM bindings are reviewed, then the granted roles are scoped to exactly the resources that service touches; no `*Admin` or `*Editor` outside its own resources.
- **Originating** AD-003, AD-021, R3 S-058
- **Depends on** P0-GCP-002
- **Tier** CRITICAL · **Size** M · **Owner** Security

#### P0-IAM-003 — OIDC trust for GitHub Actions → GCP (no SA keys)
- **As** the Platform/SRE squad
  **I want** GitHub Actions to authenticate to GCP via OIDC Workload Identity Federation
  **So that** no long-lived service account keys exist anywhere in the build pipeline.
- **AC**
  - Given a CI run, when it deploys to dev, then no SA key was used (audit log shows OIDC token exchange).
  - Given the GCP project, when SA-key listing is queried, then zero keys exist for any deployment SA.
  - Given a forked PR from outside the org, when CI runs, then OIDC is denied (workload identity pool restricts source repository).
- **Originating** ADR Phase 0 exit, R3 S-055
- **Depends on** P0-GCP-002
- **Tier** CRITICAL · **Size** S · **Owner** Platform/SRE

#### P0-IAM-004 — Quarterly access review job + dashboard
- **As** the Security squad
  **I want** a scheduled job that snapshots IAM bindings + group memberships and posts a review queue
  **So that** quarterly access reviews (BR-1104, R3 S-058) have a mechanical evidence trail.
- **AC**
  - Given a quarter boundary, when the job runs, then it produces a CSV/dashboard of all role-to-principal bindings with `last_used_at` (from Cloud Audit Logs) and `granted_at`.
  - Given a binding unused for > 90 days, when the dashboard renders, then it is flagged for revocation review.
  - Given a review-completion record, when the next quarter starts, then the prior quarter's record is archived in a compliance-folder bucket with retention.
- **Originating** BR-1104, R3 S-058, R4 C-079
- **Depends on** P0-IAM-001, P0-IAM-002, P0-OBS-002
- **Tier** IMPORTANT · **Size** M · **Owner** Security

---

### Epic VPC — VPC Service Controls

#### P0-VPC-001 — Outer perimeter (engineering prod project)
- **As** the Security squad
  **I want** a VPC-SC outer perimeter around the prod engineering project
  **So that** managed-service traffic cannot exfiltrate to projects outside the perimeter (BigQuery, GCS, Pub/Sub).
- **AC**
  - Given a request from inside the perimeter to a Google managed service, when it lands, then it succeeds.
  - Given a request from outside the perimeter (or from a principal not on the access level), when it attempts to read perimeter-protected resources, then VPC-SC denies and emits an audit event.
  - Given the perimeter config in IaC, when reviewed, then BigQuery, Cloud Storage, Pub/Sub, AlloyDB, Cloud SQL, KMS, Cloud Logging, and Artifact Registry are all listed as protected services.
- **Originating** AD-017, R3 S-053
- **Depends on** P0-GCP-002
- **Tier** CRITICAL · **Size** M · **Owner** Security

#### P0-VPC-002 — Inner perimeter (Vault project subset)
- **As** the Security squad
  **I want** an inner VPC-SC perimeter around the Vault Cloud SQL instance + Vault KMS keyring
  **So that** even compromised perimeter-internal services can only reach the Vault via the explicitly-allowed TokenizationService SA.
- **AC**
  - Given any service principal except TokenizationService SA, when attempting to reach the Vault DB or KMS keyring, then the request is denied at the inner perimeter.
  - Given TokenizationService SA, when calling Vault DB or KMS keyring, then the call succeeds.
  - Given a synthetic test where TokenizationService is impersonated by an unauthorized service, when it attempts the Vault path, then denial is logged with full context.
- **Originating** AD-017, R3 S-053
- **Depends on** P0-VPC-001, P0-IAM-002
- **Tier** CRITICAL · **Size** M · **Owner** Security

#### P0-VPC-003 — Exfiltration test harness
- **As** the Security squad
  **I want** a scripted exfiltration test exercising 8+ paths (cross-project copy, public IP egress, public bucket grant, Pub/Sub cross-org subscription, etc.)
  **So that** VPC-SC posture is verified continuously rather than assumed.
- **AC**
  - Given the test harness, when run against dev/staging/prod, then every attempted exfiltration is denied + logged.
  - Given a deliberate misconfig (test removes one VPC-SC service from protection), when the harness runs, then the corresponding test fails (negative-test verifies the harness actually catches breakage).
  - Given the harness in CI, when it runs nightly, then results are posted to a compliance dashboard.
- **Originating** AD-017, R3 S-053, R4 C-072
- **Depends on** P0-VPC-001, P0-VPC-002
- **Tier** CRITICAL · **Size** M · **Owner** Security

---

### Epic KMS — Cryptographic Foundation

#### P0-KMS-001 — HSM-tier keyring in the Vault project
- **As** the Security squad
  **I want** a KMS HSM-tier keyring in the Vault project with separate KEKs per data class (Tier 1 → Tier 4)
  **So that** ADR-0003 envelope encryption uses HSM-bound keys per the AD-009 commitment.
- **AC**
  - Given the keyring, when its protection level is queried, then it is HSM (not software).
  - Given the keyring, when keys are listed, then there is one KEK per data class with naming `kek-class-{tier}-v1`.
  - Given a key, when its IAM is reviewed, then only TokenizationService SA has `cloudkms.cryptoKeyEncrypterDecrypter` and only Security-Officer SA has `cloudkms.admin`.
- **Originating** ADR-0003, AD-009, R3 S-018
- **Depends on** P0-IAM-002, P0-VPC-002
- **Tier** CRITICAL · **Size** M · **Owner** Security

#### P0-KMS-002 — HKDF-derived per-class HMAC keys
- **As** the Security squad
  **I want** a key-derivation routine that derives a per-class HMAC key from an HSM-bound master via HKDF
  **So that** ADR-0003 keyed-deterministic tokenization is reproducible without exposing the master key in process memory.
- **AC**
  - Given the derivation routine, when run twice with the same context label, then the derived key is identical (deterministic).
  - Given two different context labels, when run, then the derived keys differ and have no algebraic relation (cryptographic separation).
  - Given a process under load, when key derivation is profiled, then it is performed once per process startup (cached in memory; not re-derived per request).
- **Originating** ADR-0003 §"Keyed deterministic tokens", R3 S-018
- **Depends on** P0-KMS-001
- **Tier** CRITICAL · **Size** S · **Owner** Security

#### P0-KMS-003 — Per-day DEK with rotation policy
- **As** the Security squad
  **I want** a per-day Data Encryption Key wrapped by the per-class KEK, rotating at 00:00 UTC
  **So that** envelope encryption follows ADR-0003 + AD-009 with bounded blast radius on DEK compromise.
- **AC**
  - Given a tokenize call at 23:59 UTC, when followed by another at 00:01 UTC the next day, then the DEK used differs.
  - Given a wrapped DEK in storage, when inspected, then it carries `dek_version`, `kek_class`, and `created_date` metadata.
  - Given a DEK older than the retention window (configurable, default 90 days), when it has zero referencing ciphertexts, then it is deleted from storage on a scheduled job.
- **Originating** ADR-0003, AD-009, BR-501
- **Depends on** P0-KMS-002
- **Tier** CRITICAL · **Size** M · **Owner** Security

#### P0-KMS-004 — Algorithm version prefix in stored ciphertexts/tokens
- **As** the Security squad
  **I want** every stored token and ciphertext to carry a `v1:` (or version-marker) prefix
  **So that** algorithm rotation in the future is non-breaking for stored data per ADR-0003.
- **AC**
  - Given a tokenize call, when its output is inspected, then the token carries the version prefix.
  - Given a detokenize call with a future-version token, when no migration handler exists, then the call returns a clear `UNSUPPORTED_TOKEN_VERSION` error.
  - Given the codebase, when the version constant is referenced, then it is sourced from a single named constant (no string-literal scattering).
- **Originating** ADR-0003 §"Algorithm versioning"
- **Depends on** P0-KMS-002
- **Tier** IMPORTANT · **Size** S · **Owner** Security

---

### Epic IAC — Infrastructure as Code

#### P0-IAC-001 — Terraform framework decision (`[iac-framework]` ADR)
- **As** the Architecture team
  **I want** the open `[iac-framework]` ADR authored
  **So that** Phase 0 IaC commits land into a documented framework choice (Terraform structure, modules, state backend, backend locking).
- **AC**
  - Given the new ADR, when reviewed, then it specifies module layout, state backend (GCS), state locking, secret-handling policy, and review-before-apply gating.
  - Given a sample module written under the framework, when `terraform plan` is run, then it produces a clean diff and locks state.
- **Originating** ARD §"Phase 0 exit" `[iac-framework]`, AD-017
- **Depends on** —
- **Tier** CRITICAL · **Size** S · **Owner** Architecture

#### P0-IAC-002 — Daily drift detection job
- **As** the Platform/SRE squad
  **I want** a scheduled `terraform plan` against prod + staging that alerts on non-zero drift
  **So that** out-of-band changes are detected within 24 hours.
- **AC**
  - Given the scheduled job, when run against a clean repo, then drift is zero and no alert fires.
  - Given a deliberately drifted resource (test creates a resource manually), when the job runs, then a P2 alert fires within one cycle.
  - Given the alert path, when reviewed, then it routes to Platform/SRE on-call with full plan diff attached.
- **Originating** ARD §"Phase 0 exit", R5 D-016
- **Depends on** P0-IAC-001
- **Tier** CRITICAL · **Size** S · **Owner** Platform/SRE

#### P0-IAC-003 — Two-person review on prod IaC apply
- **As** the Security squad
  **I want** prod-environment Terraform apply gated by two-person review (CODEOWNERS + branch protection + manual approval)
  **So that** AD-026 (two-person rule) extends to infrastructure, not just data operations.
- **AC**
  - Given a PR touching prod IaC, when CI runs, then merge requires approval from at least one Platform/SRE and one Security CODEOWNER.
  - Given a `terraform apply` invocation against prod, when triggered from CI, then a manual approval step blocks until an approver clicks through.
  - Given an attempted bypass (force-push, admin merge), when audited, then it is captured in the protected-branch audit log and triggers a P1 alert.
- **Originating** AD-026, R3 S-040
- **Depends on** P0-IAC-001, P0-IAM-001
- **Tier** CRITICAL · **Size** S · **Owner** Security

---

### Epic CICD — Build & Deploy Pipeline

#### P0-CICD-001 — Selective monorepo build per service
- **As** the Platform/SRE squad
  **I want** a CI workflow that detects changed paths and rebuilds only affected Cloud Run services
  **So that** monorepo build time stays bounded as the codebase grows (ADR-0002).
- **AC**
  - Given a PR touching only `modules/verification/`, when CI runs, then only the Verification service image rebuilds.
  - Given a PR touching `shared/`, when CI runs, then all dependent services rebuild (transitive dependency respected).
  - Given a PR touching only docs, when CI runs, then no service rebuilds (zero image work).
- **Originating** ADR-0002, R5 D-007
- **Depends on** P0-IAM-003
- **Tier** CRITICAL · **Size** M · **Owner** Platform/SRE

#### P0-CICD-002 — Cosign signing of images at build time
- **As** the Security squad
  **I want** every container image signed with Cosign using a keyless OIDC identity
  **So that** Binary Authorization can enforce only signed images at deploy.
- **AC**
  - Given a CI build, when an image is pushed, then it is signed with Cosign using the GitHub Actions OIDC identity.
  - Given an unsigned image manually pushed to Artifact Registry, when deploy is attempted, then Binary Authorization denies.
  - Given a signed image, when its signature is verified out-of-band, then verification succeeds and surfaces the signing identity.
- **Originating** ADR-0007 §"Container hardening", R3 S-056
- **Depends on** P0-CICD-001, P0-IAM-003
- **Tier** CRITICAL · **Size** M · **Owner** Security

#### P0-CICD-003 — Binary Authorization policy on Cloud Run
- **As** the Security squad
  **I want** Binary Authorization configured to require Cosign-signed images on all prod Cloud Run services
  **So that** unsigned/untrusted images cannot run in prod.
- **AC**
  - Given the BA policy, when reviewed, then it requires the Cosign attestor on `prod` Cloud Run services and warns on `staging`.
  - Given a deploy of an unsigned image to prod, when initiated, then BA blocks the deploy with a clear error.
  - Given a break-glass workflow (security-incident emergency deploy), when invoked, then it requires a signed override + emits a P0 audit event.
- **Originating** ADR-0007, R3 S-056
- **Depends on** P0-CICD-002
- **Tier** CRITICAL · **Size** S · **Owner** Security

#### P0-CICD-004 — SLSA Level 3 provenance for service images
- **As** the Security squad
  **I want** SLSA L3 provenance attached to every service image
  **So that** supply-chain integrity is verifiable end-to-end and the attestation evidence pack (Phase 4) has the artifact.
- **AC**
  - Given an image, when its provenance attestation is fetched, then it includes builder identity (GitHub Actions runner), source commit SHA, build steps, and material hashes.
  - Given a CI run, when provenance is generated, then it is signed by the Cosign keyless identity (same as image signature).
  - Given a tamper attempt (modify image post-build), when verified, then provenance verification fails.
- **Originating** R3 S-064, R5 D-008
- **Depends on** P0-CICD-002
- **Tier** IMPORTANT · **Size** M · **Owner** Security

#### P0-CICD-005 — Trivy + gitleaks gate in CI (LIVE)
- **As** the Security squad
  **I want** Trivy (image vulnerability scan) and gitleaks (secret scan) running on every PR
  **So that** known-vuln packages and committed secrets are caught at PR time, not in production.
- **AC**
  - Given a PR introducing a CRITICAL CVE in a dep, when CI runs, then the image scan job fails with the CVE details.
  - Given a PR committing a secret matching the gitleaks rules, when CI runs, then the secret-scan job fails and surfaces the file/line.
  - Given the `.secrets.baseline`, when CI starts, then it has been regenerated within the last 30 days (staleness gate).
- **Originating** R3 S-039, R3 S-085, harness Phase 00
- **Depends on** P0-CICD-001
- **Tier** CRITICAL · **Size** S · **Owner** Security

#### P0-CICD-006 — Per-service deployment strategy mapped (canary/blue-green/rolling)
- **As** the Platform/SRE squad
  **I want** the Cloud Run revision strategy per service codified in IaC
  **So that** deployment risk is matched to service criticality (ADR-0007 §5).
- **AC**
  - Given the IaC for each service, when reviewed, then Verification API uses canary (5%→50%→100%), TokenizationService uses blue/green, batch jobs use rolling.
  - Given a Verification API deploy, when initiated, then traffic split moves through 5%→50%→100% with auto-rollback on SLO breach.
  - Given a TokenizationService deploy, when initiated, then a manual cutover gate is required and old revision drains explicitly.
- **Originating** ADR-0007 §5, R5 D-006
- **Depends on** P0-CICD-001, P0-IAC-001
- **Tier** IMPORTANT · **Size** M · **Owner** Platform/SRE

---

### Epic OBS — Observability Backbone

#### P0-OBS-001 — structlog PII-redacting logger LIVE in `shared/`
- **As** the Platform/SRE squad
  **I want** the PII-redacting structlog config from the harness validated end-to-end on Cloud Run
  **So that** XR-005 (zero plaintext PII in logs) holds from day 1 (AC tighter than the Phase 00 unit-test pass).
- **AC**
  - Given a no-op service deploy, when it logs a record containing a synthetic SSN/email/phone/DOB, then Cloud Logging records show the field redacted (`[REDACTED]`) and the source line is not in the structured fields.
  - Given the redaction scanner, when run against 24h of staging logs, then it reports zero matches.
  - Given a misconfigured service that doesn't import the shared logger, when it deploys, then a startup-validation gate (per `bootstrapper/config_validation.py` extension) blocks startup.
- **Originating** ADR-0006, BR-XR-005, harness Phase 00 carryover
- **Depends on** P0-GCP-002
- **Tier** CRITICAL · **Size** S · **Owner** Platform/SRE

#### P0-OBS-002 — Cloud Logging sink to BigQuery audit dataset
- **As** the Compliance squad
  **I want** all `prod` audit logs sinked to BigQuery in a dedicated `audit` dataset with bucket-level retention
  **So that** queryable audit history is available for access reviews and breach investigation.
- **AC**
  - Given the sink, when audit log entries land in Cloud Logging, then a corresponding BigQuery row appears within 30s.
  - Given the BigQuery dataset, when its retention is queried, then it is set to ≥ 6 years (per BR-503 / HIPAA-aligned).
  - Given a query on the dataset, when filtered by `principal`, then per-principal action history is queryable in under 5s on 30 days of data.
- **Originating** BR-503, ADR-0006
- **Depends on** P0-GCP-002, P0-OBS-001
- **Tier** CRITICAL · **Size** S · **Owner** Compliance

#### P0-OBS-003 — OpenTelemetry W3C Trace Context propagation
- **As** the Platform/SRE squad
  **I want** OpenTelemetry instrumentation with W3C Trace Context propagation across all Cloud Run services
  **So that** distributed traces stitch end-to-end (ADR-0006).
- **AC**
  - Given a request entering Verification API, when traced, then the trace shows spans across Verification → TokenizationService → AlloyDB read (or vault read) with consistent trace_id.
  - Given a Pub/Sub publish/subscribe, when consumed, then the consuming span is parented under the publishing span via Trace Context attributes.
  - Given Cloud Trace, when queried, then span attribute `correlation_id` (per-business-record) is present and distinct from `trace_id` per ADR-0006.
- **Originating** ADR-0006 §"Logging Schema and Correlation ID Model", R5 D-088
- **Depends on** P0-OBS-001
- **Tier** CRITICAL · **Size** M · **Owner** Platform/SRE

#### P0-OBS-004 — Correlation ID enforcement at API ingress
- **As** the Platform/SRE squad
  **I want** the Verification API ingress to inject `correlation_id` if absent and propagate it through every downstream span and log
  **So that** per-record forensic traceability holds independently of the OTel trace_id (which can be ambiguous across re-tries).
- **AC**
  - Given a request without `correlation_id` header, when received, then the API generates a UUID v4 and tags every emitted log/span with it.
  - Given a request with `correlation_id` set by an upstream caller, when received, then it is passed through unmodified.
  - Given a downstream Pub/Sub message, when published from a request handler, then the message attribute carries the same `correlation_id` (idempotency-safe per ADR-0005).
- **Originating** ADR-0006, ADR-0005
- **Depends on** P0-OBS-003
- **Tier** CRITICAL · **Size** S · **Owner** Platform/SRE

#### P0-OBS-005 — Error catalog (`shared/errors.py`) wired to ADR-0006 taxonomy
- **As** the Platform/SRE squad
  **I want** a finite typed error catalog that every service raises against
  **So that** operators see a bounded set of error categories on dashboards and runbooks (ADR-0006).
- **AC**
  - Given the catalog, when reviewed, then it covers: VALIDATION_ERROR, AUTH_ERROR, NOT_FOUND, CONFLICT, RATE_LIMITED, DEPENDENCY_UNAVAILABLE, INTERNAL_ERROR, AUDIT_FAIL, TOKEN_VERSION_UNSUPPORTED.
  - Given a service handler, when it raises an unmapped exception, then the framework wraps it as `INTERNAL_ERROR` with the original traceback in non-PII fields.
  - Given a CI lint pass (custom check), when run, then any `raise Exception(...)` in module code fails the build (must use catalog).
- **Originating** ADR-0006 §"Error taxonomy", R5 D-035
- **Depends on** P0-OBS-001
- **Tier** IMPORTANT · **Size** S · **Owner** Platform/SRE

#### P0-OBS-006 — Cloud Monitoring dashboards for golden signals (per service)
- **As** the Platform/SRE squad
  **I want** a per-service dashboard with latency p50/p95/p99, error rate, request rate, and saturation
  **So that** the SLO baseline is observable from day 1 of Phase 1 (AD-021).
- **AC**
  - Given a deployed service, when the dashboard URL is followed, then the four golden signals render with live data within 60s of deploy.
  - Given a synthetic load test, when issued, then dashboards show the load reflected within one scrape interval.
  - Given the dashboard config, when queried in IaC, then all services have identical dashboard structure (no snowflakes).
- **Originating** AD-021, R5 D-088
- **Depends on** P0-OBS-001, P0-OBS-003
- **Tier** IMPORTANT · **Size** M · **Owner** Platform/SRE

#### P0-OBS-007 — Alerting policy: PII redaction failure → P0
- **As** the Security squad
  **I want** any PII redaction failure (regex hit on production logs) to page on-call P0
  **So that** breaches of XR-005 are caught and contained within the 60-day breach-notification window (HIPAA §164.404).
- **AC**
  - Given a synthetic test that injects a non-redacted SSN, when the redaction scanner runs, then a P0 alert pages within 5 minutes.
  - Given the alert, when received, then the runbook link in the alert points to a documented PII-leak response procedure.
  - Given a real prod log, when scanned, then zero alerts fire (baseline-clean state).
- **Originating** XR-005, BR-1001..1010, ADR-0006
- **Depends on** P0-OBS-001
- **Tier** CRITICAL · **Size** S · **Owner** Security

#### P0-OBS-008 — No-op service deployable end-to-end
- **As** the Platform/SRE squad
  **I want** a "hello world" Cloud Run service that exercises every observability surface (logs, traces, metrics, audit emission via outbox)
  **So that** Phase 0 exit criterion ("no-op service hits all surfaces correctly") is testable.
- **AC**
  - Given the no-op service deploy, when one request flows through, then an entry appears in: Cloud Logging (structured + redacted), Cloud Trace (span tree), Cloud Monitoring (request count metric), audit_event BigQuery (via outbox publisher).
  - Given the service, when audited, then logs/spans/metrics/audit all share the same `correlation_id`.
- **Originating** ARD §"Phase 0 exit"
- **Depends on** P0-OBS-001..006, P0-TBL-001, P0-TOK-001
- **Tier** CRITICAL · **Size** M · **Owner** Platform/SRE

#### P0-OBS-009 — Traceability-matrix generator script
- **As** the Architecture team
  **I want** `scripts/build_traceability_matrix.py` parsing `docs/backlog/*.md` and emitting BR↔story + ADR↔story tables
  **So that** the BRD XR-012 bidirectional cross-reference is mechanically verified rather than maintained by hand.
- **AC**
  - Given the script run, when complete, then it emits a generated matrix listing every BR with its implementing story IDs across all phases.
  - Given a BR with zero implementing stories, when the script runs, then it exits non-zero and CI flags it as orphan.
  - Given a story with an originating ID that doesn't exist in BRD/ARD, when the script runs, then it exits non-zero with the offending story ID.
- **Originating** XR-012, R8 P-015
- **Depends on** —
- **Tier** IMPORTANT · **Size** S · **Owner** Architecture

---

### Epic DAT — Data Substrate

#### P0-DAT-001 — AlloyDB primary + read replica (minimum size)
- **As** the Data Engineering squad
  **I want** an AlloyDB primary with one read replica provisioned at minimum config
  **So that** Phase 1 has the operational store ready and scaling is configuration-only.
- **AC**
  - Given AlloyDB provisioning, when complete, then the primary is in the prod project, replica in a different zone, both inside the outer VPC-SC perimeter.
  - Given a connection from a Cloud Run service via VPC connector, when issued, then it succeeds via Private Service Connect (no public IP).
  - Given pgbouncer between Cloud Run and AlloyDB, when configured, then it is in transaction-mode with `pool_size` and `max_client_conn` matching the AD-022 sizing.
- **Originating** AD-007, AD-022, RR-001
- **Depends on** P0-VPC-001
- **Tier** CRITICAL · **Size** M · **Owner** Data Engineering

#### P0-DAT-002 — Cloud SQL Vault instance (private, inner-perimeter)
- **As** the Security squad
  **I want** a Cloud SQL Postgres instance for the Vault inside the inner VPC-SC perimeter
  **So that** ADR-0003 envelope-encrypted ciphertexts and KMS-wrapped DEKs have a minimal-blast-radius store.
- **AC**
  - Given the Vault instance, when its IAM is reviewed, then only TokenizationService SA has connect rights.
  - Given the instance, when its network config is queried, then it has only a private IP (no public).
  - Given a connection attempt from any service except TokenizationService, when made, then it is denied at the inner perimeter before reaching the DB.
- **Originating** AD-009, AD-017, ADR-0003
- **Depends on** P0-VPC-002, P0-IAM-002
- **Tier** CRITICAL · **Size** M · **Owner** Security

#### P0-DAT-003 — Pub/Sub topic registry with schemas
- **As** the Architecture team
  **I want** every Pub/Sub topic declared in IaC with an associated Protobuf schema (in `shared/messages/`)
  **So that** producers and consumers share a single contract enforced at publish-time.
- **AC**
  - Given a topic, when its config is queried, then schema enforcement is enabled and points to the registered Protobuf schema.
  - Given a publish call with a malformed message, when made, then Pub/Sub rejects with a clear schema-mismatch error.
  - Given a consumer reading the topic, when its dependency on the schema is checked (import-linter contract), then it imports from `shared/messages/` only.
- **Originating** ADR-0002, ADR-0005, R5 D-046
- **Depends on** P0-GCP-002
- **Tier** IMPORTANT · **Size** M · **Owner** Architecture

#### P0-DAT-004 — BigQuery datasets for analytical replica + audit
- **As** the Data Engineering squad
  **I want** BigQuery datasets `analytical` (for Pattern C analytical mirror) and `audit` (for log-sink + audit_event) provisioned with retention and IAM
  **So that** Datastream replication and audit log sink land into prepared targets in Phase 1.
- **AC**
  - Given the datasets, when listed, then `analytical` has 7-day default table retention and `audit` has 6-year retention with no human delete role.
  - Given the datasets, when IAM is queried, then PH-resident principals have row-level access conditions enforcing PII-tier exclusion.
  - Given the datasets, when a synthetic write is issued, then it lands in the analytical dataset (audit dataset is sink-only, no human writes).
- **Originating** AD-007, RR-001, BR-503
- **Depends on** P0-VPC-001, P0-IAM-001
- **Tier** CRITICAL · **Size** S · **Owner** Data Engineering

#### P0-DAT-005 — Cloud Storage buckets (quarantine, anchor, forensic, attestation)
- **As** the Data Engineering squad
  **I want** four GCS buckets provisioned: `quarantine` (DQ), `anchor-registry` (Compliance org, ADR-0008), `forensic` (KMS-encrypted, retention-locked), `attestation-evidence`
  **So that** Phase 1+ work has the storage targets prepared with retention and access policies set.
- **AC**
  - Given each bucket, when its retention is queried, then quarantine = 90 days, anchor-registry = 6 years + Bucket Lock, forensic = 6 years + Bucket Lock, attestation-evidence = 7 years.
  - Given each bucket, when its IAM is queried, then no public access, KMS encryption with the appropriate keyring, and retention-policy locking is enabled where indicated.
  - Given the anchor-registry bucket, when accessed by an Engineering-org admin, then access is denied (Compliance org owns it).
- **Originating** ADR-0008, BR-503, R5 D-072
- **Depends on** P0-GCP-001, P0-KMS-001
- **Tier** CRITICAL · **Size** M · **Owner** Data Engineering

---

### Epic TBL — Operational Tables (Outbox, Idempotency, Migrations)

#### P0-TBL-001 — Outbox table per bounded context (DDL + Alembic migrations)
- **As** the Architecture team
  **I want** an `outbox` table per bounded context that participates in domain transactions and is drained by a publisher
  **So that** ADR-0005 transactional outbox holds for every context that emits Pub/Sub messages.
- **AC**
  - Given each context's database (canonical_eligibility, identity_resolution, deletion, member_rights, audit), when migrated, then an `outbox` table exists with the schema in ARD §"outbox".
  - Given a domain transaction, when it commits, then any outbox row inserted is visible to the publisher within the next poll cycle.
  - Given a publisher crash mid-publish, when the publisher restarts, then duplicate publishes for the same outbox row are observed but consumers idempotently dedupe (via processed_events).
- **Originating** ADR-0005, AD-027
- **Depends on** P0-DAT-001
- **Tier** CRITICAL · **Size** M · **Owner** Architecture

#### P0-TBL-002 — Processed_events table per consumer
- **As** the Architecture team
  **I want** a `processed_events` table per consumer (or shared schema) that holds `(consumer_id, event_id)` for idempotency dedup
  **So that** at-least-once Pub/Sub delivery becomes effectively-once at the application layer (ADR-0005).
- **AC**
  - Given a consumer, when it processes an event_id it has seen before, then the second processing is a no-op (no duplicate side effect).
  - Given the table, when its growth is monitored, then a cleanup job prunes entries older than the message retention window (default 7 days; configurable).
  - Given idempotency tests, when they exhaustively replay events, then no double-merge, double-delete, or double-emit is observed.
- **Originating** ADR-0005 §"Idempotency"
- **Depends on** P0-TBL-001
- **Tier** CRITICAL · **Size** S · **Owner** Architecture

#### P0-TBL-003 — Per-member advisory locks (pgbouncer-safe)
- **As** the Identity Resolution squad
  **I want** an advisory-lock helper that acquires `pg_advisory_xact_lock` on `hash(member_id)` inside a transaction
  **So that** concurrent merges on the same member serialize without blocking unrelated work (R2 F-104).
- **AC**
  - Given two concurrent merge attempts on the same member, when both run, then one waits and the other proceeds (no deadlock, no race).
  - Given the helper used through pgbouncer transaction-mode, when the transaction commits/rollbacks, then the lock is released (no orphaned advisory lock).
  - Given a load test of N concurrent unique-member operations, when run, then no contention is observed (locks scoped per member, not global).
- **Originating** R2 F-104, AD-022, ADR-0005
- **Depends on** P0-TBL-001
- **Tier** CRITICAL · **Size** S · **Owner** Identity Resolution

#### P0-TBL-004 — Alembic baseline + per-context schema migration scaffolds
- **As** the Data Engineering squad
  **I want** Alembic baselined per bounded context with a CI gate that fails on out-of-order migrations
  **So that** schema evolution is reviewable and reproducible (per ADR-0001 carry-forward).
- **AC**
  - Given a fresh DB, when `alembic upgrade head` runs, then all contexts converge to the baseline schema.
  - Given a PR introducing a migration with a non-monotonic revision, when CI runs, then the gate fails.
  - Given a destructive migration (DROP COLUMN, DROP TABLE), when in CI, then a CODEOWNERS check requires Security + DBA approval.
- **Originating** ADR-0001 carry-forward, R5 D-014
- **Depends on** P0-DAT-001
- **Tier** CRITICAL · **Size** S · **Owner** Data Engineering

---

### Epic TOK — Tokenization Smoke Path

#### P0-TOK-001 — TokenizationService skeleton with `tokenize`/`detokenize`/`tombstone` interface
- **As** the Vault squad
  **I want** a Cloud Run TokenizationService with the production interface (per ADR-0003 §"TokenizationService Interface")
  **So that** every other service codes against the production contract from day 1; only the implementation backing differs in dev (software KMS) vs prod (HSM KMS).
- **AC**
  - Given a `tokenize(plaintext, class)` call, when issued, then a `v1:`-prefixed token is returned and a vault row is created with the wrapped DEK + ciphertext.
  - Given a `detokenize(token)` call by an authorized principal, when issued, then the plaintext is returned and a `DETOK` audit event is emitted.
  - Given a `tombstone(token)` call, when issued, then subsequent `detokenize` returns `TOMBSTONED` and the audit trail is preserved.
- **Originating** ADR-0003, AD-009
- **Depends on** P0-DAT-002, P0-KMS-001..004
- **Tier** CRITICAL · **Size** L · **Owner** Vault

#### P0-TOK-002 — End-to-end tokenization smoke test
- **As** the Vault squad
  **I want** an integration test that calls TokenizationService through the inner perimeter from a no-op service
  **So that** ADR-0003 keyed-deterministic primitive is empirically demonstrated (Phase 0 exit criterion).
- **AC**
  - Given the same plaintext + class tokenized twice, when the resulting tokens are compared, then they are byte-identical (deterministic-by-design).
  - Given the same plaintext under two different classes, when tokenized, then the resulting tokens differ and have no exploitable algebraic relation.
  - Given a detokenize from outside the inner perimeter, when attempted, then VPC-SC denies before TokenizationService is invoked.
- **Originating** ARD §"Phase 0 exit", ADR-0003
- **Depends on** P0-TOK-001, P0-VPC-002
- **Tier** CRITICAL · **Size** S · **Owner** Vault

#### P0-TOK-003 — Per-partner salt isolation enforced
- **As** the Security squad
  **I want** the tokenization key derivation to take partner_id as a context input
  **So that** cross-partner correlation via shared tokens is structurally impossible (ADR-0003 cross-partner correlation prevention).
- **AC**
  - Given partner A and partner B both submitting the same plaintext (e.g., same SSN), when each is tokenized, then the resulting tokens differ.
  - Given an attacker with read access to both partners' tokenized data, when they attempt to correlate by token equality, then no matches are found (correlation requires plaintext or master-key compromise).
  - Given the derivation routine, when reviewed, then `partner_id` is in the HKDF info parameter for the per-partner derived key.
- **Originating** ADR-0003 §"Per-partner cryptographic isolation", BR-XR-005, RR-002
- **Depends on** P0-TOK-001, P0-KMS-002
- **Tier** CRITICAL · **Size** S · **Owner** Security

---

### Epic CFG — Configuration Parameter Ledger

#### P0-CFG-001 — Ledger published in BRD; runtime validation gate
- **As** the Platform/SRE squad
  **I want** the BRD's 47-parameter ledger surfaced as a runtime-validated config schema
  **So that** misconfigured services (out-of-range, missing, wrong type) fail fast at startup rather than misbehave in production (extends harness Phase 00 `config_validation.py`).
- **AC**
  - Given the schema, when a service starts with a parameter set out of its declared range, then startup fails with a clear error pointing to the parameter name.
  - Given the schema, when a service starts in `prod` env without a required parameter, then startup fails (no silent default).
  - Given a parameter change in IaC, when deployed, then the schema is the source-of-truth (no service-local override files).
- **Originating** XR-001, XR-010, BRD §"Configuration Parameter Ledger"
- **Depends on** —
- **Tier** CRITICAL · **Size** M · **Owner** Platform/SRE

#### P0-CFG-002 — Per-environment promotion path (dev → staging → prod)
- **As** the Platform/SRE squad
  **I want** parameters promoted dev→staging→prod via PR review
  **So that** prod-only parameter changes carry a documented audit trail.
- **AC**
  - Given a parameter change PR, when it changes only dev, then it merges with one approval.
  - Given a PR changing prod parameters, when merged, then it requires CODEOWNERS approval per AD-026 (two-person) and emits a `CONFIG_CHANGE_PROD` audit event.
  - Given a config drift between staging and prod, when detected by a daily diff job, then it surfaces as a P2 alert.
- **Originating** XR-010, AD-026
- **Depends on** P0-CFG-001
- **Tier** IMPORTANT · **Size** S · **Owner** Platform/SRE

---

### Epic ADR — Open ADRs Authored or Scoped

#### P0-ADR-001 — Author `[part-2-implementation]` ADR
- **As** the Compliance squad
  **I want** the 42 CFR Part 2 ADR authored
  **So that** RR-006 is closed before Phase 1 partner onboarding (Part 2 applicability changes the data flow).
- **AC**
  - Given the ADR, when reviewed, then it answers: applicability triggers, segregation pattern (separate Vault keyring vs same-keyring-with-tag), audit-emission delta, partner-side responsibilities.
  - Given the ADR, when cross-referenced with BR-1402, then no contradictions exist.
- **Originating** RR-006, BR-1402
- **Depends on** —
- **Tier** CRITICAL · **Size** M · **Owner** Compliance

#### P0-ADR-002 — Author `[member-portal-scope]` ADR
- **As** the Architecture team
  **I want** the member portal scope decision documented
  **So that** RR-009 is closed and Phase 2 UX work has a definitive scope contract.
- **AC**
  - Given the ADR, when reviewed, then it specifies: in-scope rights workflows, out-of-scope rights workflows (and the alternative path), authentication model, accessibility commitments.
- **Originating** RR-009, BR-1306
- **Depends on** —
- **Tier** CRITICAL · **Size** M · **Owner** Architecture

#### P0-ADR-003 — Author `[reviewer-decision-support]` ADR
- **As** the Architecture team
  **I want** the reviewer decision-support pattern documented (what data, what rendering, what controls)
  **So that** Phase 2 reviewer interface has the contract before build.
- **AC**
  - Given the ADR, when reviewed, then it specifies: tokenized vs detokenized rendering, side-by-side comparison layout, score breakdown surface, explainability requirements (BR-104), keyboard accessibility commitment.
- **Originating** R6 U-017, BR-105, BR-104, RR-010
- **Depends on** —
- **Tier** CRITICAL · **Size** M · **Owner** Architecture

#### P0-ADR-004 — Author `[friction-mechanism]` ADR
- **As** the Verification squad
  **I want** the brute-force friction mechanism documented (CAPTCHA vs WebAuthn vs proof-of-work, vendor choice)
  **So that** Phase 2 build of BR-402 has the implementation contract.
- **AC**
  - Given the ADR, when reviewed, then it specifies: chosen mechanism, vendor (if applicable), accessibility implications, latency contribution to ADR-0009 floor, alternatives considered.
- **Originating** BR-402, R6 U-001, R6 U-027
- **Depends on** —
- **Tier** CRITICAL · **Size** M · **Owner** Verification

#### P0-ADR-005 — Author `[dr-strategy]` ADR
- **As** the Platform/SRE squad
  **I want** the disaster-recovery strategy documented (RTO, RPO, region pairing, restore drill cadence)
  **So that** Phase 1+ has DR exit criteria with explicit targets.
- **AC**
  - Given the ADR, when reviewed, then it specifies: prod region + DR region, RTO target, RPO target, drill cadence, runbook ownership.
- **Originating** AD-021, R5 D-039, BRD §"DR" amendments
- **Depends on** P0-GCP-003
- **Tier** CRITICAL · **Size** M · **Owner** Platform/SRE

#### P0-ADR-006 — Author `[partner-sftp]` ADR (or alternative)
- **As** the Ingestion squad
  **I want** the partner inbound transport documented (SFTP vs API vs SaaS connector vs file-on-bucket)
  **So that** Phase 1 partner onboarding has a definitive ingress contract.
- **AC**
  - Given the ADR, when reviewed, then it specifies: chosen transport, identity model (mTLS, IP allowlist, key auth), file-arrival notification, authentication audit.
- **Originating** AD-001, BR-801, R5 D-047
- **Depends on** —
- **Tier** CRITICAL · **Size** M · **Owner** Ingestion

#### P0-ADR-007 — Author `[sequelae-ph-ml-access]` ADR
- **As** the Compliance squad
  **I want** the Sequelae PH workforce access model to ML / analytical surfaces documented
  **So that** PH-resident workforce productivity is preserved without violating BR-506 residency.
- **AC**
  - Given the ADR, when reviewed, then it specifies: which analytical surfaces are accessible to PH-resident principals (tokenized only), which are explicitly excluded, what tooling enforces (BigQuery row-level access, dataset masking, etc.).
- **Originating** BR-506, AD-002
- **Depends on** P0-DAT-004
- **Tier** IMPORTANT · **Size** M · **Owner** Compliance

#### P0-ADR-008 — Scope `[iac-framework]` ADR (covered by P0-IAC-001)
- (Covered — see P0-IAC-001.)

---

### Epic COM — Compliance Foundation

#### P0-COM-001 — Designate Privacy Officer (US-resident)
- **As** the CEO + Compliance squad
  **I want** a Privacy Officer designated, US-resident, with documented role and authority
  **So that** AD-030 / BR-1101 are satisfied before any Phase 1 production traffic.
- **AC**
  - Given the org chart, when reviewed, then a Privacy Officer is named with US residency confirmed.
  - Given the role document, when reviewed, then it covers HIPAA Privacy Rule responsibilities, NPP authoring authority, complaint handling, breach assessment authority.
- **Originating** BR-1101, AD-030
- **Depends on** —
- **Tier** CRITICAL · **Size** S · **Owner** CEO

#### P0-COM-002 — Designate Security Officer (US-resident)
- **As** the CEO + Compliance squad
  **I want** a Security Officer designated, US-resident, with documented role and authority
  **So that** AD-030 / BR-1102 are satisfied before any Phase 1 production traffic.
- **AC**
  - Given the org chart, when reviewed, then a Security Officer is named with US residency confirmed.
  - Given the role document, when reviewed, then it covers HIPAA Security Rule responsibilities, incident command, sanctions authority, attestation owner.
- **Originating** BR-1102, AD-030
- **Depends on** —
- **Tier** CRITICAL · **Size** S · **Owner** CEO

#### P0-COM-003 — PHI inventory authored and counsel-reviewed
- **As** the Privacy Officer
  **I want** a comprehensive PHI inventory mapping every data class, location, retention, and access path
  **So that** BR-1202 is satisfied and Phase 1+ controls have an authoritative scope.
- **AC**
  - Given the inventory, when reviewed, then every data class in the BRD §"Data Classification" appears with its store, encryption-at-rest model, retention, and access groups.
  - Given counsel review, when complete, then a signed counsel sign-off attests the inventory is complete.
- **Originating** BR-1202
- **Depends on** P0-COM-001
- **Tier** CRITICAL · **Size** M · **Owner** Privacy Officer

#### P0-COM-004 — Risk assessment methodology documented (BR-1203)
- **As** the Privacy Officer
  **I want** a documented risk-assessment methodology aligned with NIST SP 800-30 or HITRUST
  **So that** annual risk assessments (BR-1203) have a repeatable framework.
- **AC**
  - Given the methodology document, when reviewed, then it specifies: risk identification, likelihood scoring, impact scoring, control mapping, residual-risk acceptance authority.
- **Originating** BR-1203
- **Depends on** P0-COM-002
- **Tier** CRITICAL · **Size** M · **Owner** Privacy Officer

#### P0-COM-005 — Workforce sanctions policy (BR-1104)
- **As** the Security Officer
  **I want** a documented sanctions policy for HIPAA / Privacy / Security violations
  **So that** BR-1104 is satisfied and workforce understands consequences in advance.
- **AC**
  - Given the policy, when reviewed, then it specifies categories of violation, escalation tiers, due-process model, and signing authority.
  - Given onboarding, when a workforce member is added, then they sign acknowledgment as part of access provisioning.
- **Originating** BR-1104
- **Depends on** P0-COM-002
- **Tier** CRITICAL · **Size** S · **Owner** Security Officer

#### P0-COM-006 — Documentation retention infrastructure (BR-1201)
- **As** the Privacy Officer
  **I want** a 6-year-retention document store with version history and locked-on-finalize semantics
  **So that** BR-1201 (HIPAA documentation retention) holds for P&Ps, training records, NPP versions.
- **AC**
  - Given the store, when a document is finalized, then it cannot be deleted or modified for 6 years (retention lock).
  - Given a version-history query, when run on a P&P, then every prior version is retrievable.
- **Originating** BR-1201
- **Depends on** P0-DAT-005
- **Tier** CRITICAL · **Size** M · **Owner** Privacy Officer

#### P0-COM-007 — 42 CFR Part 2 applicability decision (RR-006)
- **As** the Privacy Officer
  **I want** a documented decision on Part 2 applicability per partner type
  **So that** RR-006 is closed before Phase 1 partner onboarding.
- **AC**
  - Given the decision document, when reviewed, then it lists partner archetypes (commercial health plan, ACO, SUD treatment partner, etc.) and Part 2 applicability per archetype with counsel rationale.
  - Given a future partner, when their Part 2 status is unclear, then the document directs to the counsel review path.
- **Originating** RR-006, BR-1402
- **Depends on** P0-COM-001, P0-ADR-001
- **Tier** CRITICAL · **Size** M · **Owner** Privacy Officer

#### P0-COM-008 — Attestation roadmap decision (RR-004)
- **As** the Security Officer
  **I want** the SOC 2 vs HITRUST decision documented with target attestation date
  **So that** RR-004 is closed and Phase 4 has a definitive scope.
- **AC**
  - Given the decision, when reviewed, then it states: chosen framework, scope (Type II for SOC 2 or HITRUST CSF certification level), auditor selection plan, evidence-pack ownership.
- **Originating** RR-004
- **Depends on** P0-COM-002
- **Tier** CRITICAL · **Size** M · **Owner** Security Officer

#### P0-COM-009 — Counsel engagement plan (in-house + outside)
- **As** the Privacy Officer
  **I want** a documented counsel engagement plan (in-house counsel of record; outside counsel for breach + state-law matters)
  **So that** Phase 2 breach-notification work has the legal authority chain pre-built.
- **AC**
  - Given the plan, when reviewed, then it names in-house counsel, outside counsel firm, retainer status, escalation triggers.
- **Originating** BR-1101, BR-1006
- **Depends on** P0-COM-001
- **Tier** IMPORTANT · **Size** S · **Owner** Privacy Officer

---

### Epic UX — UX Foundation

#### P0-UX-001 — Design system commitment (UI library + tokens)
- **As** the UX squad
  **I want** a design system chosen and committed (component library, design tokens, theming)
  **So that** Phase 1+ UX work shares a consistent visual + interaction substrate.
- **AC**
  - Given the design system decision, when documented, then it names the library (e.g., Radix + Tailwind, Material, custom), token model, and accessibility baseline.
  - Given a component built under the system, when reviewed, then it inherits the tokens and passes the accessibility baseline.
- **Originating** XR-009, R6 U-002
- **Depends on** —
- **Tier** IMPORTANT · **Size** M · **Owner** UX

#### P0-UX-002 — User research program plan
- **As** the UX squad
  **I want** a documented user research program (recruitment, cadence, ethics, consent)
  **So that** Phase 1+ research has a repeatable framework.
- **AC**
  - Given the program plan, when reviewed, then it specifies: recruitment vendors, IRB/ethics path (if any), consent template, data-handling for research artifacts.
  - Given a research session, when run, then artifacts are stored under the documentation retention store (BR-1201) per consent terms.
- **Originating** R6 U-059, BR-XR-009
- **Depends on** P0-COM-006
- **Tier** IMPORTANT · **Size** M · **Owner** UX

#### P0-UX-003 — WCAG 2.1 AA audit commitment + tooling
- **As** the UX squad
  **I want** an axe-core / Lighthouse CI gate on every UX-bearing PR
  **So that** WCAG 2.1 AA regressions are caught at PR time (XR-009).
- **AC**
  - Given a PR introducing a WCAG violation, when CI runs, then the gate fails with the violation listed.
  - Given the gate config, when reviewed, then the WCAG 2.1 AA ruleset is the baseline (not a subset).
- **Originating** XR-009, R6 U-039
- **Depends on** P0-UX-001
- **Tier** IMPORTANT · **Size** S · **Owner** UX

#### P0-UX-004 — Trauma-informed design framework documented
- **As** the UX squad
  **I want** trauma-informed design principles documented for healthcare-PII flows
  **So that** Verification failure UX (Phase 1) and Member Rights UX (Phase 2) inherit the framework.
- **AC**
  - Given the framework, when reviewed, then it specifies: language tone (no blame), failure-state recovery paths, plain-language commitment, safe-navigation patterns, escalation-to-human path.
  - Given a UX review, when applied, then a checklist derived from the framework is part of every PR.
- **Originating** R6 U-001, R6 U-070, XR-007
- **Depends on** —
- **Tier** IMPORTANT · **Size** M · **Owner** UX

#### P0-UX-005 — Inclusive design framework + plain-language standard
- **As** the UX squad
  **I want** plain-language and inclusive-design standards documented
  **So that** XR-007 (plain language) and XR-008 (multilingual) hold across all member-facing surfaces.
- **AC**
  - Given the standard, when reviewed, then it specifies reading-level target (e.g., 6th–8th grade), preferred-language rendering chain, RTL support commitment, screen-reader contract.
  - Given a member-facing string, when reviewed, then it passes a readability check (Hemingway / Flesch-Kincaid) at the target level.
- **Originating** XR-007, XR-008
- **Depends on** P0-UX-001
- **Tier** IMPORTANT · **Size** S · **Owner** UX

---

### Epic SEC — Security Baseline

#### P0-SEC-001 — Cloud Armor on Verification API LB
- **As** the Security squad
  **I want** Cloud Armor configured on the public Verification API load balancer with WAF rules + geo-allowlist
  **So that** common attack vectors (OWASP top 10 patterns, geo-blocked sources) are filtered before reaching the application.
- **AC**
  - Given a request matching a WAF rule (e.g., SQLi pattern), when issued, then Cloud Armor returns 403 and emits an audit event.
  - Given a request from a non-allowlisted geography, when issued, then Cloud Armor returns 403.
  - Given the Cloud Armor policy, when reviewed, then rate-limiting at the edge is configured per BR-402 first-tier (independent from app-level rate limits).
- **Originating** R3 S-054, BR-402, BR-506
- **Depends on** P0-GCP-002
- **Tier** CRITICAL · **Size** M · **Owner** Security

#### P0-SEC-002 — Secrets Manager + secret-rotation policy
- **As** the Security squad
  **I want** all secrets in Google Secret Manager with rotation policies
  **So that** no static secrets live in env vars, files, or repo (R3 S-085).
- **AC**
  - Given a service config, when inspected, then secrets are referenced by SM resource name (no inline values).
  - Given a rotation policy, when reviewed, then KMS keys, JWT signing keys, partner SFTP keys, and TSA API keys all have documented rotation cadences.
  - Given gitleaks scan history, when reviewed, then no secret has been committed to the repo.
- **Originating** R3 S-085, ADR-0006
- **Depends on** P0-GCP-002
- **Tier** CRITICAL · **Size** M · **Owner** Security

#### P0-SEC-003 — STRIDE threat model maintenance cadence
- **As** the Security squad
  **I want** a quarterly review of the per-context STRIDE threat model in ARD §"Threat Model per Bounded Context"
  **So that** new findings, new attack patterns, and architectural changes update the model rather than drift from it.
- **AC**
  - Given a quarter end, when the review is held, then a dated entry in `docs/retros/threat-model-{Q}.md` records changes (or "no change") with reviewer attribution.
  - Given an architectural change PR, when it touches a bounded context, then a CODEOWNERS check requires Security review of any threat-model implications.
- **Originating** R3 S-069, ARD §"Threat Model"
- **Depends on** —
- **Tier** IMPORTANT · **Size** S · **Owner** Security

#### P0-SEC-004 — Branch protection on `main` + PR review gates
- **As** the Security squad
  **I want** branch protection on `main` with required status checks (Detect Changes, Security Scan, Documentation Gate, Lint, Unit Tests) + 1 review minimum
  **So that** the harness Phase 00 carryover (T0.10) is closed and CONSTITUTION assumes hold.
- **AC**
  - Given `gh api repos/{owner}/{repo}/branches/main/protection`, when called, then it returns 200 with the required status checks enabled.
  - Given a force-push attempt to `main`, when made, then it is rejected by the protection rule.
  - Given a PR without the required reviews, when merge is attempted, then GitHub blocks merge.
- **Originating** Phase 00 T0.10, HIPAA_POSTURE.md "branch protection still not enabled"
- **Depends on** —
- **Tier** CRITICAL · **Size** XS · **Owner** Security

---

## Phase 0 cross-track summary

| Track | Critical stories | Important / Supportive |
|-------|------------------|------------------------|
| Engineering | P0-TBL-001..004, P0-TOK-001..003, P0-OBS-008 | P0-OBS-005, P0-OBS-006, P0-OBS-009 |
| Security | P0-GCP-004..005, P0-IAM-001..003, P0-VPC-001..003, P0-KMS-001..004, P0-IAC-003, P0-CICD-002..005, P0-SEC-001, P0-SEC-002, P0-SEC-004 | P0-IAM-004, P0-CICD-006, P0-OBS-007, P0-SEC-003 |
| Compliance | P0-COM-001..008 | P0-COM-009, P0-ADR-001 |
| UX | P0-UX-001, P0-UX-003, P0-UX-004 | P0-UX-002, P0-UX-005 |
| Infrastructure | P0-GCP-001..002, P0-DAT-001..005, P0-IAC-001..002, P0-CICD-001, P0-OBS-001..004 | P0-GCP-003 |

## Phase 0 risk-register linkage

| Risk | Story closing it (or downgrading) |
|------|-----------------------------------|
| RR-001 (BigQuery + Composer + AlloyDB confirmed) | P0-DAT-001, P0-DAT-004, P0-IAC-001 |
| RR-004 (HITRUST or SOC 2 decision) | P0-COM-008 |
| RR-006 (42 CFR Part 2 applicability) | P0-ADR-001, P0-COM-007 |
| RR-008 (vendor concentration board ack) | P0-GCP-003 (region/zone ADR), P0-ADR-005 (DR strategy) |
| RR-009 (member portal scope) | P0-ADR-002 |
| RR-010 (reviewer build vs buy) | P0-ADR-003 |

---

## Out of scope for Phase 0

- Format adapter / mapping engine implementation (Phase 1)
- DQ engine implementation (Phase 1)
- Identity Resolution implementation (Phase 1 deterministic, Phase 2 Splink)
- Verification API implementation (Phase 1 skeleton, Phase 2 BR-402 brute force)
- Member Rights workflows (Phase 2)
- Real partner onboarding (Phase 1 first partner; Phase 3 N partners)
- Penetration testing (Phase 4)
- Comprehensive accessibility audit (Phase 4)
