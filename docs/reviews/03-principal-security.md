# Architecture Review — Round 3: Principal Security Engineer

| Field | Value |
|---|---|
| **Round** | 3 of N |
| **Reviewer lens** | Principal Security Engineer — adversarial perspective, cryptographic correctness, authn/authz rigor, insider threat, supply chain, detection/response readiness, HIPAA/HITECH/state law completeness, threat-model depth |
| **Documents** | `docs/BUSINESS_REQUIREMENTS.md` (BRD), `docs/ARCHITECTURE_REQUIREMENTS.md` (ARD) |
| **Date** | 2026-04-29 |
| **Prior rounds** | `docs/reviews/01-principal-architect.md`, `docs/reviews/02-chief-programmer.md` |

This review reads the documents the way an attacker, an auditor, and a CISO read them — three lenses simultaneously. The attacker asks: *where's the soft spot, and how do I exploit it.* The auditor asks: *can I prove this control works, and what's the evidence.* The CISO asks: *if there's a breach tomorrow, what's the blast radius and the response.*

Severity per Constitution Rule 29 (BLOCKER / FINDING / ADVISORY).

Where I'm extending or sharpening prior-round findings, I cite them (e.g. "extends R1 F-003"). Where I'm raising something new, no citation. New work is the majority.

---

## TL;DR

**Will the platform be secure if we proceed as-is? No, with a non-trivial gap to close.**

The architecture has the *primitives* right — Vault with KMS, VPC-SC perimeters, Sequelae PH residency at the IAM layer, audit chain in WORM storage, two-state Verification response. These are not wrong choices; they're correct foundational choices that an experienced HIPAA architect would make. But primitives alone don't make a system secure. Security comes from:

1. **Cryptographic correctness** — keys derived correctly, algorithms versioned, rotation procedures, randomness sources, length and mode discipline.
2. **Authn/authz model rigor** — JWT specifics, claim validation, IDOR prevention at every API, two-person rules for high-risk operations, session lifecycle.
3. **Defense in depth** — every layer (network, edge, container, application, data) has its own controls; compromising one layer doesn't compromise the system.
4. **Detection and response** — controls fail silently if no one's watching; SIEM, anomaly detection, incident-response runbooks, breach notification procedures.
5. **Threat-model integration** — STRIDE per context with explicit mitigations; asset classification driving where defense effort goes.
6. **Compliance specifics** — HIPAA Security Rule, HITECH, state law (CCPA, CPRA, MHMDA), 42 CFR Part 2 decisions.

**60+ findings below: 18 BLOCKERS, 47 FINDINGS, 9 ADVISORIES (74 total).** This is more than prior rounds because security touches every layer — and every layer has gaps to enumerate.

If all the BLOCKERS from rounds 1, 2, and 3 are addressed (~37 unique), the platform will be HIPAA-defensible against a sophisticated adversary, auditable against external attestation, and operationally responsive when incidents happen. If only the architectural shape is delivered, the platform will pass a friendly walkthrough but fail an external red-team or attestation audit.

---

## Strengths from a security view

What's load-bearing and correct (do not relitigate):

1. **Vault as the only plaintext PII surface, behind TokenizationService interface.** Strong abstraction with a swappable backend.
2. **Inner VPC-SC perimeter around the Vault.** Architectural enforcement of the most sensitive boundary.
3. **Sequelae PH IAM gating with Workspace residency conditions (AD-003).** Cross-border data residency as architecture, not policy.
4. **Audit chain in WORM-locked GCS, fanned out from a Pub/Sub topic.** Tamper-evident and standard.
5. **Two-state Verification response (BR-401).** Privacy-preserving collapse is the right design pattern.
6. **PII redaction in logs (XR-005) implemented with two-layer defense in the harness.** Principle and primitive both present.
7. **Three-environment hard separation (dev/staging/prod).** Synthetic-only outside prod is the right discipline.
8. **Air-gapped engineering of the Sequelae PH boundary.** Workspace conditions, distinct service-account groups, US-only PII Handler role.
9. **AUDIT_KEY, ARTIFACT_SIGNING_KEY, PII_ENCRYPTION_KEY explicitly named in env vars.** The keys exist as concepts; the question is correctness.

These all contribute. The findings below extend, sharpen, or fill gaps around them.

---

## 1. Cryptographic Primitives and Correctness

The ARD names cryptographic concepts but doesn't specify the primitives, modes, key derivation, lengths, or rotation discipline. Cryptographic correctness is rarely about choosing the wrong primitive (most projects pick AES, SHA-256, HMAC); it's about getting the *details* wrong (using ECB mode, reusing IVs, unsalted hashes, weak KDFs, insufficient entropy).

### S-001: Keyed deterministic tokenization with proper KDF — BLOCKER

**Where:** AD-009, plus extends Round 1 F-003.

**Why it matters:** R1 F-003 raised frequency analysis; this finding sharpens the cryptographic spec. Naive deterministic tokenization (`token = HMAC(key, plaintext)`) leaks under chosen-plaintext if an attacker can submit values and observe tokens. For the eligibility system, a Sequelae PH ML engineer with read access to BigQuery sees `name_token` distributions; if the deterministic key has weak entropy or short rotation cadence, frequency-analysis attacks succeed.

**What's needed:**
- Derivation: `class_master_key = HKDF(KMS_master, salt="lore_eligibility:v1:<class>", length=32)`
- Per-class subkey (one for `name_token`, one for `dob_token`, etc.) — compromise of one class doesn't compromise others
- Rotation: data-key (per-class) wraps an underlying tokenization-key; data-key rotates every 90 days; tokenization-key rotates yearly with re-keying procedure
- Algorithm: HMAC-SHA-256 (256-bit key, 256-bit output truncated to ~128-bit token)
- Token format includes algorithm version (`v1:<base64>`); enables migration

**Effort:** M (one ADR + key-rotation procedure + re-keying playbook).

---

### S-002: Deletion ledger hash uses HMAC, not bare SHA-256 — BLOCKER

**Where:** BR-703 schema: `suppression_hash = SHA256(salt || normalized_name || dob_token || partner_member_id_hash)`.

**Why it matters:** The salt is "environment-scoped." If an adversary obtains the salt (it's stored alongside the application code or in config), they can offline-compute hashes for an arbitrary candidate population — name + DOB combinations are bounded (~10^9 for US population) and brute-forceable. The deletion ledger then becomes a re-identification oracle.

**What's needed:**
- Replace bare SHA-256 with HMAC-SHA-256 keyed by a KMS-resident secret never exposed to the application directly. Application calls KMS to compute the HMAC; offline brute force requires KMS access.
- Or: use Argon2id with high memory cost (64MB, t=3, p=4) to make brute force computationally expensive even with the salt.

**Effort:** S (cryptographic primitive change + ADR).

---

### S-003: Tokenization vs. encryption distinction is muddled — BLOCKER

**Where:** AD-008 says "Cloud KMS plus application-level tokenization plus hardened Cloud SQL." `.env.example` has `PII_ENCRYPTION_KEY` as Fernet. The Vault schema has "encrypted at rest with field-level encryption, KMS DEK per record." Three different concepts: tokenization (random token + lookup table), application-level encryption (encrypted blob, decrypts to plaintext), Fernet (symmetric authenticated encryption — different from envelope encryption).

**Why it matters:** Without clear spec, implementation will mix patterns. Tokens that are actually encrypted blobs leak length information; encrypted fields that pretend to be tokens fail when decryption keys rotate. The two have different security properties (tokens can be replayed; encrypted blobs reveal nothing without the key).

**What's needed:**
- ARD: explicit choice. Recommendation: random tokens with separate vault lookup table (not encrypted blobs as tokens). The vault stores `(token, encrypted_plaintext)` where `encrypted_plaintext` uses envelope encryption with a per-record DEK (or per-class-per-day DEK to amortize KMS cost) wrapped by a KMS KEK.
- Distinguish tokenization (vault-lookup-required) from field-level encryption (key-required) — these are different mechanisms; the system uses both.
- Replace `PII_ENCRYPTION_KEY` Fernet wording in `.env.example` with the actual envelope-encryption KEK identifier.

**Effort:** S (ADR + .env.example update).

---

### S-004: KMS DEK lifecycle and caching — FINDING

**Where:** ARD: "KMS DEK per record."

**Why it matters:** KMS has rate limits (per-project, per-second). Per-record DEK with no caching means every detok hits KMS — quotas exhausted at scale, latency added. But aggressive DEK caching exposes plaintext DEKs in service memory longer.

**What's needed:** ADR specifying DEK caching policy. Standard pattern: per-class DEK rotated daily, cached in-memory in TokenizationService for the duration of the day, dropped on rotation. KMS hit per rotation, not per detok.

**Effort:** S.

---

### S-005: JWT specifics for Verification API — BLOCKER

**Where:** ARD: "mTLS at the load balancer plus a short-lived JWT issued by the Lore application's auth service. The Verification API validates the JWT and authorizes by client_id."

**Why it matters:** JWT is the most-misused web auth mechanism. Without specifics, the implementation will be fragile. Attacks on weakly-specified JWT include: alg=none, key confusion (RS256 → HS256), missing audience validation (token from another service accepted), missing expiry, replay (no jti tracking), insufficient TTL, missing key rotation.

**What's needed:** ADR specifying the JWT contract:
- Algorithm: RS256 (asymmetric), pinned. Reject `alg: none` and HS256 explicitly.
- Required claims: `iss` (must match Lore application's auth service URL), `aud` (must equal `lore-eligibility-verification`), `exp` (mandatory, ≤ 5 minutes), `iat`, `jti` (unique per token, cached in Memorystore for replay prevention up to TTL), `sub` (Lore application client identifier).
- Public key retrieval: JWKS endpoint at `https://auth.lore.app/.well-known/jwks.json`, refreshed every hour with cache.
- Signature validation: explicit key ID (`kid` header) → JWKS lookup; reject if `kid` not present.
- Authorization: `aud` validated; client `sub` checked against an allow-list.

**Effort:** M (ADR + implementation discipline).

---

### S-006: TLS configuration discipline — BLOCKER

**Where:** ARD: TLS in transit; `DATABASE_TLS_ENABLED` enforced. Specifics not stated.

**Why it matters:** TLS misconfiguration is a class of HIPAA findings in audits. Without explicit policy: TLS 1.0/1.1 may be allowed; weak cipher suites; no certificate pinning for outbound calls; no revocation checking on inbound mTLS.

**What's needed:** ADR specifying TLS configuration:
- Minimum version: TLS 1.2; preferred TLS 1.3.
- Cipher suites: AEAD only (AES-GCM, ChaCha20-Poly1305); explicit allow-list, deny everything else.
- Forward secrecy: required (ECDHE key exchange).
- Database connections: TLS verified with CA pinning to GCP-managed CA bundle.
- Inbound mTLS at LB: client certificate validation via Google-managed CA or organization CA; revocation via OCSP stapling.
- Internal service-to-service: TLS at the GFE layer (Cloud Run handles); explicit verification that ALTS or mTLS is the transport.
- Certificate management: managed by Google Certificate Manager; rotation cadence documented.

**Effort:** M (ADR + per-service config).

---

### S-007: Random number generation source — FINDING

**Where:** Random tokens, JWT jti, salts, deletion ledger entropy.

**Why it matters:** Python's `random` is not cryptographically secure. UUID v4 is, but the code path matters. A developer using `random.randbytes()` instead of `secrets.token_bytes()` produces predictable randomness — token guessing becomes feasible.

**What's needed:** Convention: every cryptographic random byte comes from `secrets` module or `os.urandom`. CI lint rule banning `random.` usage in `shared/security/` and `bootstrapper/auth.py`. Document the sources.

**Effort:** S.

---

### S-008: Algorithm versioning across crypto operations — FINDING

**Where:** No algorithm version tracking. Tokens, audit hashes, signing — each is single-version.

**Why it matters:** Cryptographic agility — when SHA-256 weakens (decade horizon for full break, but practical attacks emerge sooner), migration is non-trivial without versioning. Audit chain cryptographically signed today; verifying historical chain in 10 years requires algorithm support.

**What's needed:** Convention: every cryptographic output prefixed with algorithm version (`v1:hmac-sha256:<base64>`). Rotation procedure documented. Sunset of old algorithms scheduled. The `match_decision.algorithm_version` is one such version field; extend the pattern.

**Effort:** S (convention) + ongoing.

---

## 2. Authentication and Authorization

Auth is rarely a single decision; it's a *system* of decisions with consistency requirements. Without explicit specification, every API ends up with subtly-different auth, IDOR vulnerabilities multiply, and privilege escalation paths emerge from inconsistencies.

### S-009: PEP/PDP authorization model — BLOCKER

**Where:** Implicit. Each service does its own auth.

**Why it matters:** Without an explicit authorization model, every service implements role checking inline, with subtly different semantics. Confused-deputy bugs result. Specifically: PEP (Policy Enforcement Point — at the API boundary, enforces decisions) vs PDP (Policy Decision Point — computes decisions from policy + context). Sharing the PDP across services produces consistent enforcement.

**What's needed:** ADR: PEP at every API endpoint (FastAPI dependency); PDP as a shared library (`shared/authz/`) implementing role + attribute checks. Every route declares the required permission via decorator/dependency; the PDP returns ALLOW/DENY; the PEP enforces. No inline role checking.

**Effort:** M (ADR + shared library).

---

### S-010: IDOR prevention — per-resource authorization — BLOCKER

**Where:** Manual Review API: `GET /v1/review/queue/{queue_id}/claim`. Authorization checks reviewer is in Reviewer role. But: any reviewer can `POST` to any `queue_id`. IDOR.

**Why it matters:** Role-based check is necessary but not sufficient. Reviewer A claims queue item Q; Reviewer B subsequently can claim Q (no per-resource check) and override A's resolution. Same pattern for deletion request status endpoint, audit log queries, etc.

**What's needed:** Convention: every resource access checks (a) caller has the role, (b) resource is scoped to the caller (assigned-to, owned-by, or organization-scoped). Implementation: shared decorator `@requires_resource_access(resource_type, resource_id_arg)` that enforces both.

**Effort:** S to specify; ongoing as routes are added.

---

### S-011: Two-person rule for high-risk operations — BLOCKER

**Where:** BR-702 deletion executor runs autonomously. BR-703 deletion override emits audit but doesn't require multi-party. Vault key rotation, mass detok, Splink config changes — all single-actor today.

**Why it matters:** Insider threat is a real attack vector. A single privileged user can cause irrecoverable damage (deletion, key rotation gone wrong, mass detok for exfil). HIPAA "minimum necessary" plus standard HITRUST/SOC 2 controls mandate multi-party authorization for high-risk operations.

**What's needed:** ADR: classify operations by risk. High-risk operations require N-of-M approval (typically 2-of-3 from a designated approver group):
- Vault key rotation
- Mass detokenization (>100 records)
- Deletion override (BR-703 re-introduction)
- Splink threshold change in production
- Audit log access for forensic investigation
- Cross-region DR failover

Implementation: dedicated approval workflow (Google Identity-Aware Proxy + Privileged Access Manager + custom workflow service). Time-boxed (1 hour to approve), audited, post-action review.

**Effort:** M (workflow service + approver-group design).

---

### S-012: Session management — BLOCKER

**Where:** JWT TTL implied 5-60 minutes. Refresh, revocation, logout not specified.

**Why it matters:** Stale JWTs with no revocation = compromise window equal to TTL. For HIPAA: long sessions in PII-handling roles is a finding in attestation audits.

**What's needed:** ADR:
- Access token TTL: 15 minutes for PII-bearing roles (PII Handler, Break-Glass Admin), 1 hour for non-PII roles.
- Refresh token: rotated on every use, sliding TTL up to 24 hours, stored hashed in DB.
- Revocation: explicit logout endpoint invalidates the refresh token; access token expires naturally.
- Session limits: max 3 concurrent sessions per user; session list visible to user.
- Idle timeout: 30 minutes of inactivity invalidates session for PII-bearing roles.
- MFA: required for PII Handler, Break-Glass Admin, Auditor roles. WebAuthn preferred; TOTP acceptable.

**Effort:** M (ADR + auth service integration).

---

### S-013: Operator credential standards — FINDING

**Where:** Phase 00 `.env.example` has `CRUCIBLE_ADMIN_PASSWORD_HASH` (bcrypt) holdover. Operator passwords for the verification UI / reviewer interface unspecified.

**Why it matters:** Weak operator credentials are a primary attack vector. Bcrypt is fine; the question is policy (length, complexity, rotation, breach checking).

**What's needed:** ADR:
- Password hashing: argon2id (Python `argon2-cffi`) — stronger than bcrypt for new systems.
- Minimum length: 12 characters, no complexity rules (NIST SP 800-63B).
- Breach check: integration with Have-I-Been-Pwned k-anonymity API at change time.
- MFA: mandatory for any operator role (per S-012).
- No password rotation by time (per NIST SP 800-63B); rotate only on compromise.
- Account lockout: 10 failed attempts → exponential backoff up to 1-hour lockout; per-IP lockout at gateway.

**Effort:** S.

---

### S-014: Workload Identity discipline — FINDING

**Where:** Round 2 F-141 noted Workload Identity as the binding mechanism. Extend.

**Why it matters:** Each service has its own service account with its own IAM bindings. Least privilege requires per-service permissions, not blanket.

**What's needed:** ADR: explicit IAM matrix per service. Each Cloud Run service has a dedicated service account; service-account permissions enumerated (BigQuery dataset read, Pub/Sub topic publish, KMS key use, AlloyDB connection); no blanket "editor" or "owner" roles. Annual review of IAM bindings.

**Effort:** S.

---

### S-015: Privileged access lifecycle — FINDING

**Where:** Break-glass via PAM, time-boxed, audited (AD-003). Other privileged paths (Auditor read access, BAA-mediated subprocessor access) not addressed.

**Why it matters:** "Break-glass" is one privileged access type; others exist (regular Auditor work, scheduled compliance reviews, partner support escalations). All need lifecycle.

**What's needed:** ADR: privileged-access framework. Categories: Standing privileged (PII Handler — controlled by IAM group + MFA + per-action audit), Time-boxed (Break-Glass — PAM grant), Approval-gated (high-risk operations per S-011). Each category: grant procedure, audit, revocation, post-review cadence.

**Effort:** S.

---

## 3. Data Classification and Privacy-by-Design

HIPAA distinguishes PHI from PII. State laws have additional categories. The system needs explicit classification to apply correct controls.

### S-016: PII vs PHI classification per field — BLOCKER

**Where:** BRD uses "PII" and "PII or PHI" interchangeably. Eligibility data linked to healthcare context = PHI under HIPAA.

**Why it matters:** Different classes have different controls. PHI requires HIPAA Security Rule technical safeguards; non-PHI PII varies by state law. Audit retention, breach notification, residency, BAA scope — all depend on class. Misclassification = either over-controlling (cost) or under-controlling (compliance breach).

**What's needed:** Classification table per data field:

| Field | Class | HIPAA scope | Notes |
|---|---|---|---|
| name | PII (PHI when linked to eligibility) | Yes | Always treat as PHI in this system |
| DOB | PII (PHI) | Yes | |
| SSN (full) | Sensitive PII (PHI) | Yes | Extra controls; 42 CFR Part 2 if SUD-related |
| SSN (last-4) | PII (PHI) | Yes | Lower sensitivity but still in scope |
| address | PII (PHI) | Yes | Geographic re-id risk |
| phone | PII (PHI) | Yes | |
| email | PII (PHI) | Yes | |
| partner_member_id | Indirect identifier | Yes | Re-id when joined |
| eligibility status | PHI | Yes | Direct healthcare association |
| match score | Derived metadata | No (in isolation) | But links PHI in queries |
| audit_event metadata | Operational | No | Tokens reference PHI; metadata itself is not |

Add to ARD as authoritative classification table.

**Effort:** S (one table; significant downstream impact).

---

### S-017: Data minimization policy per partner — BLOCKER

**Where:** BRD: PII fields include "additional fields per partner are likely." Open-ended.

**Why it matters:** HIPAA "minimum necessary" rule (§164.502(b)) requires limiting PHI use/disclosure to minimum necessary. Partners may push extra fields ("here's their pet's name"); without a policy, those land in the canonical model and become liability.

**What's needed:** Policy: per-partner YAML mapping enumerates *only* the fields used. Unused fields from partner feed are dropped at the format-adapter stage, not stored. Each enumerated field has a documented purpose. Purpose without use = drop.

**Effort:** S (BRD addition + tooling enforcement).

---

### S-018: Pseudonymization vs anonymization terminology — FINDING

**Where:** BRD/ARD use "tokenization" throughout.

**Why it matters:** Tokenized data is still PHI under HIPAA — re-identifiable via the vault. Some downstream uses (research, analytical) want truly anonymized (no re-identification path). Terminology rigor matters for audit and for downstream user expectations.

**What's needed:** Glossary in BRD or ARD:
- **Tokenization (pseudonymization):** Reversible. Vault holds the mapping. Token-bearing data is still PHI.
- **De-identification (HIPAA Safe Harbor):** Removal of 18 specified identifiers; resulting data is not PHI.
- **Anonymization (Expert Determination):** Statistical evaluation that re-identification risk is "very small."

System scope: Verification, Identity Resolution, Canonical Eligibility — all PHI (tokenized). Analytical surfaces accessible to Sequelae PH — tokenized PHI; *not* anonymized (re-id via vault is possible by US-eligible roles).

**Effort:** S.

---

### S-019: SSN-specific handling — FINDING

**Where:** BR-102: full SSN secondary anchor; last-4 contributes to scoring only. ARD schema: `ssn_token` for full SSN.

**Why it matters:** Full SSN is special-category PII under most state laws. Storage, access, and audit have additional requirements.

**What's needed:**
- Don't store last-4 separately (it's a function of full SSN — derivable as needed).
- Full SSN access at the service level requires elevated role (PII Handler), even within Vault.
- Last-4 use in matching: hash of last-4 used as scoring feature; never stored as separate column.
- Specific access audit: every SSN detok logs caller + purpose with elevated retention.

**Effort:** S.

---

### S-020: Purpose specification per data field — FINDING

**Where:** BRD lists fields. No documented purpose per field.

**Why it matters:** HIPAA "minimum necessary" + privacy-by-design requires purpose for each PHI use. Audit defensibility: "Why is `email_token` collected?" needs a documented answer.

**What's needed:** Purpose table per field, in BRD:

| Field | Stored | Purpose |
|---|---|---|
| name | Vault | Identity match anchor; reviewer disambiguation |
| DOB | Vault + canonical token | Identity match anchor; clinical age-derived features |
| SSN (full) | Vault | Identity match secondary anchor; deletion ledger input |
| email | Vault | Member contact; verification claim element |
| ... | ... | ... |

**Effort:** S (one table).

---

### S-021: Retention policy per data class — FINDING

**Where:** BR-503 has retention defaults: 7 years PII access events, 2 years operational events. Other data classes not specified.

**Why it matters:** HIPAA requires 6 years PHI retention; state law varies (some 10 years). Operational data, derived analytics, partner-supplied raw files, reviewer comments, ML training data — each has its own retention.

**What's needed:** Retention table:

| Data class | Retention | Disposal mechanism |
|---|---|---|
| Vault PII (active) | While member is active + 7 years | Crypto-shred on tombstone |
| Vault PII (tombstoned) | Records purged; tombstone retained 7 years | N/A |
| Audit (PII access) | 7 years (BR-503) | GCS Bucket Lock retention |
| Audit (operational) | 2 years (BR-503) | BigQuery partition expiration |
| Canonical SCD2 (operational store) | 90 days (AD-005) | Datastream replicated; operational pruning |
| Canonical SCD2 (BigQuery) | 7 years | Partition policy |
| Raw landing zone | 7 years for replay | GCS lifecycle |
| Quarantine | 7 years | GCS lifecycle |
| Reviewer comments | 7 years (PHI-adjacent) | DB retention |
| ML training data | 2 years; refreshed annually | Cloud Storage lifecycle |
| Application logs | 90 days | Cloud Logging retention |
| Splink session artifacts | 1 year | Cloud Storage lifecycle |
| Pub/Sub messages (in transit) | 7 days max | Default retention |

**Effort:** S.

---

### S-022: Right-to-deletion completeness — BLOCKER

**Where:** BR-702: vault purge, canonical tombstone (PII fields nulled), audit log preserved by token. ARD reverse-mapping confirms.

**Why it matters:** Deletion must reach every copy. The doc covers vault and operational store. It misses: BigQuery analytical projection (replicated SCD2 history with PII tokens), ML training data derivatives, Cloud Storage raw landing zone (immutable for 7 years per BR-503 — conflict with deletion?), Memorystore rate-limit cache, BigQuery cached query results. And critically: backups.

For HIPAA-grade deletion: crypto-shredding is the standard. Delete the encryption key for the data class; backup copies of the data become unrecoverable even if backups themselves persist.

**What's needed:** ADR: deletion completeness. Per data class, the deletion mechanism. Crypto-shredding for backups. Conflict resolution between BR-503 raw landing retention (7 years for replay) and right-to-deletion (immediate purge): probably the raw landing zone is exempt under HIPAA's "designated record set" exclusion, but explicit decision required.

**Effort:** M.

---

### S-023: Membership inference resistance — FINDING

**Where:** Implicit. Even with privacy-preserving collapse, repeated probing reveals membership.

**Why it matters:** Adversary submits N claims to Verification, each with slight variations. Even rate-limited and timing-equalized, statistical accumulation reveals which claims are members. Differential privacy techniques can resist this by adding controlled noise.

**What's needed:** ADR: membership inference resistance. Options: (a) tighter rate limits at lower bounds (1 attempt per 24 hours per identity-shape), (b) noise injection in NOT_VERIFIED responses (occasionally return NOT_VERIFIED for actual members and VERIFIED for actual non-members at low rate to confuse statistical analysis — controversial, has correctness implications), (c) accept membership inference as residual risk and document it.

Probably (a) is the right answer. Document explicitly.

**Effort:** S.

---

## 4. Cross-Border Data Flows and Residency

Sequelae PH boundary is enforced via IAM Workspace conditions. That handles *account* residency. Real residency requires additional controls.

### S-024: Residency = location, not just account — BLOCKER

**Where:** AD-003: "Workspace-attribute condition gates membership in pii_handler@ and break_glass@ groups to US-resident accounts only."

**Why it matters:** A US-resident PII Handler logs in from Manila. IAM allows access (account is US). Data crosses the border in the network packets. HIPAA / state-law residency obligations require the *data flow* to be US-only, not just the account.

**What's needed:** Defense in depth:
- Conditional access via IP geolocation: deny access to PII-handling services from non-US IPs.
- BeyondCorp / Identity-Aware Proxy with geo-restriction.
- VPN with US-only egress for personnel work.
- Detection: alerts on access from non-US IPs by US-resident accounts (unusual travel).

**Effort:** M.

---

### S-025: Cross-border data flow audit log — FINDING

**Where:** Implicit; not stated.

**Why it matters:** Auditors and regulators want evidence that PHI never crossed the border. An audit log specifically of cross-border data flows (or absence thereof) is a defensibility artifact.

**What's needed:** Logging convention: every Vault detok logs requester IP; geo-resolved IP recorded in audit event; aggregate dashboards show cross-border flow rates (target zero); alerts on any cross-border PII access.

**Effort:** S.

---

### S-026: Backup residency — FINDING

**Where:** ARD: "Disaster recovery via cross-region backup replication." Region of secondary not specified.

**Why it matters:** Multi-region backup replication: target must be US. GCP us-central1 → us-east1 is fine; us-central1 → asia-northeast1 violates residency.

**What's needed:** ADR: backup target region(s) explicit and US-only. Cloud SQL replicas, AlloyDB read replicas, GCS bucket replication, BigQuery dataset replication — all US-region-locked.

**Effort:** S.

---

### S-027: Subprocessor / downstream data flow — FINDING

**Where:** BRD mentions BAA chain for every subprocessor. ARD doesn't enumerate.

**Why it matters:** Every GCP service with PHI access is a subprocessor (per HIPAA §164.314). Each must be covered by BAA. Each subprocessor's residency must be auditable.

**What's needed:** Subprocessor inventory:

| Service | PHI access | BAA scope | Residency |
|---|---|---|---|
| Cloud SQL | Yes (Vault + canonical) | GCP BAA | us-central1 |
| BigQuery | Yes (analytical) | GCP BAA | US multi-region |
| Cloud KMS | Yes (key access) | GCP BAA | us-central1 |
| Cloud Storage | Yes (raw landing, audit, quarantine) | GCP BAA | us-central1 |
| Cloud Run | Yes (in-transit) | GCP BAA | us-central1 |
| Pub/Sub | Yes (in-transit, tokenized) | GCP BAA | us-central1 |
| Cloud Composer | Yes (orchestration metadata) | GCP BAA | us-central1 |
| Cloud Logging | No (PII redacted) | GCP BAA | us-central1 |
| Memorystore | No (rate-limit counters only) | GCP BAA | us-central1 |
| reCAPTCHA Enterprise | No (claim metadata; not PHI) | GCP BAA | Global (review) |
| PagerDuty | No (alert metadata) | Vendor BAA | Multi-region |
| GitHub Actions | No (no PHI flows through CI) | None needed | Vendor terms |

For each: BAA on file; residency assertion; review cadence.

**Effort:** S (table).

---

## 5. Audit Forensic Depth and Integrity

Audit is the single most important compliance artifact. The architecture has the primitives; the depth and forensic readiness need work.

### S-028: Audit completeness — every API call — BLOCKER

**Where:** BR-501 lists 12 event classes. The list is not exhaustive.

**Why it matters:** Auditors and forensic investigators want every API call logged, not just "PII access." Authentication events (login, logout, token refresh, MFA challenge), authorization decisions (deny events especially), config reads, dashboard queries — each is an audit signal. Absence of comprehensive logging creates blind spots in investigation.

**What's needed:** Augmented event classes in BR-501:
- Authentication: login_success, login_failure, mfa_challenge, mfa_success, mfa_failure, logout, session_revoked, token_issued, token_refreshed, token_revoked
- Authorization: access_allowed (sample at 1% to control volume), access_denied (always)
- Configuration: config_read, config_change_attempted, config_change_succeeded, config_change_failed
- Investigation: audit_log_queried (logs the queries themselves), forensic_export, forensic_legal_hold
- System: deploy_started, deploy_succeeded, deploy_failed, schema_migration_started, schema_migration_completed
- Network: VPC-SC perimeter violation attempted (always), egress_to_external_service (sample)

Plus the existing 12. Total ~30 classes. Each class has retention per S-021.

**Effort:** S (BRD addition; implementation grows with services).

---

### S-029: Forensic query indexes — FINDING

**Where:** ARD schema: `audit_event` partitioned by date, clustered by event_class, actor_role.

**Why it matters:** Forensic investigation queries: "all access to records related to John Doe between Date X and Date Y by user Y." Requires lookups by (target_token), (actor_principal), (timestamp range), (event_class). The current clustering supports event_class + actor_role but not target_token.

**What's needed:** Add clustering on target_token. BigQuery supports up to 4 clustering columns; choose target_token + event_class + actor_role + date partition. Query patterns documented.

**Effort:** S.

---

### S-030: Audit chain validator cadence and forensic preservation — BLOCKER

**Where:** Round 1 F-008 covered external anchoring. This finding extends to validation cadence and forensic response.

**Why it matters:** ARD: "Hash chain validator runs continuously, no breaks." On break: paged. Recovery procedure not specified. If chain breaks, the forensic question is: was this tampering, replication lag, or a bug? Each has a different response.

**What's needed:** ADR: chain validator operational model.
- Cadence: real-time validator on event arrival + hourly bulk validator over the prior 24 hours.
- Break categories: (a) chain break in append-only path → likely consumer bug → forensic preserve, halt audit consumer, investigate; (b) chain break with prior chain valid → tampering attempted → trigger immediate IR.
- Forensic preservation: snapshot affected GCS objects, snapshot consumer logs, legal hold; do not modify the chain to "repair" it.
- Recovery: if tampering ruled out and bug fixed, append a "chain reset" event with cryptographic proof of intent; resume.

**Effort:** M (ADR + runbook).

---

### S-031: Audit log immutability — defense in depth — FINDING

**Where:** ARD: GCS Bucket Lock with retention. Round 1 F-008 covered external anchoring.

**Why it matters:** Bucket Lock is strong. Stronger is multi-account replication: audit log replicated to a second GCP organization owned by Compliance (not Engineering); Engineering can't modify, even with breach of Engineering admin credentials.

**What's needed:** ADR: cross-organization audit replication. Compliance org owns the secondary copy; replication via Cloud Storage Transfer Service or custom Dataflow; replicated copy is the legal record. Engineering org's copy is the operational record.

**Effort:** M.

---

### S-032: Audit log access by Auditor role — FINDING

**Where:** BR-505: Auditor role has read-only access to audit logs. META_AUDIT_READ event emitted on read.

**Why it matters:** Insider Auditor role abuse. Auditor reads logs related to a person of interest for non-compliance reasons. Detection: anomaly on auditor query patterns; mandatory justification per query; periodic review of auditor queries by a peer.

**What's needed:**
- Mandatory justification field on audit log query (free text, audited).
- Auditor query rate baselines; alert on anomalous spikes.
- Quarterly peer review: random 10% of auditor queries reviewed for legitimate justification.
- Co-auditor: high-sensitivity queries (target = senior executive, etc.) require co-auditor approval.

**Effort:** S.

---

### S-033: WORM compliance evidence — FINDING

**Where:** GCS Bucket Lock provides WORM. Compliance evidence chain not explicit.

**Why it matters:** HITRUST CSF and SOC 2 Type II require evidence of WORM compliance. Auditors want artifacts: bucket configuration as code, retention policy attestation, periodic verification reports.

**What's needed:** Compliance artifacts:
- IaC (Terraform) for GCS bucket configuration including Bucket Lock retention; checked in to Git.
- Periodic verification report (monthly): script queries bucket retention policy; produces report; archived.
- Retention policy documented in compliance binder.

**Effort:** S.

---

### S-034: Audit log forensic readiness — BLOCKER

**Where:** Implicit.

**Why it matters:** When a breach is suspected, time-to-investigation matters. The audit log is the primary forensic artifact. Forensic readiness includes: log query tooling, chain-of-custody procedures, expert testimony preparation.

**What's needed:** ADR: forensic readiness. Documented investigation procedures (who can initiate, what authorities, what tools); chain-of-custody for log exports (signed, hash-chained, transferred via secure channel); legal hold mechanism (extends BR-503 retention indefinitely on flagged events).

**Effort:** S (ADR; implementation in Phase 4 or earlier IR readiness).

---

### S-035: Audit chain non-repudiation — FINDING

**Where:** Hash chain provides tamper-evidence. Non-repudiation (proof a specific actor did a specific action) requires cryptographic signing per event.

**Why it matters:** A user who detoks a record and is later found to have abused access can claim "that wasn't me." Stronger than IP-address audit: each audit event signed with the actor's session-bound key. Non-repudiation in the strong sense.

**What's needed:** ADR: per-actor signing for high-criticality events. Each PII access event signed by the requesting service account's KMS-bound key; signature verifiable by anyone with the public key. For human actors: hardware-backed signature (FIDO2 / WebAuthn assertion bound to the action).

**Effort:** L (high engineering cost; deferral with documented residual risk is acceptable for v1).

---

## 6. Insider Threat and Privileged Access

The hardest threats to detect, often the most damaging.

### S-036: Privileged user activity baselining — BLOCKER

**Where:** Implicit; not stated.

**Why it matters:** PII Handler can detok any record. Without baseline + anomaly detection, a malicious or compromised PII Handler exfiltrates undetected.

**What's needed:** ADR: privileged user behavior monitoring. Baseline per user (avg detok rate, hours of access, geographic patterns, target distribution); alerts on 3-sigma deviations; UEBA (User and Entity Behavior Analytics) integration.

**Effort:** M.

---

### S-037: Concurrent session limits on privileged roles — FINDING

**Where:** Implicit.

**Why it matters:** Stolen credentials → adversary uses parallel sessions to amplify damage. Concurrent session limit + invalidate-on-new-session mitigates.

**What's needed:** Session policy: PII Handler max 2 concurrent sessions; new session at the limit invalidates oldest; warning message displayed.

**Effort:** S.

---

### S-038: Insider threat detection signals — FINDING

**Where:** Implicit.

**Why it matters:** Specific signals of insider abuse:
- Off-hours PII access (after-hours, weekends without on-call status)
- High-volume detok in short window
- Detok of records outside the user's typical territory (geographic, partner)
- Browse patterns: sequential reviews of unrelated records
- Departure-imminent patterns: high access in the weeks before announced departure

**What's needed:** Detection rules per signal; integration with SIEM (per S-046); response procedure documented.

**Effort:** M.

---

### S-039: Departure procedures — FINDING

**Where:** Implicit.

**Why it matters:** When privileged personnel depart: revoke access, audit recent activity, secure handoff of any in-flight investigations.

**What's needed:** Documented procedure:
- Day of departure: IAM access revoked; sessions terminated; MFA tokens deactivated.
- Within 7 days: audit review of last 30 days of access for the departing user; sign-off by Security and Compliance.
- For roles with persistent assets (Auditor, Break-Glass Admin): role transition with documented handover.

**Effort:** S.

---

### S-040: Code review for security-sensitive paths — FINDING

**Where:** CLAUDE.md has red-team-reviewer on every phase. Production should have CODEOWNERS for security paths.

**Why it matters:** Security-sensitive code (vault, audit, auth, key management) requires review by someone qualified. Without CODEOWNERS, generic reviewer suffices on PR; subtle security bugs slip.

**What's needed:** GitHub CODEOWNERS file:
```
src/lore_eligibility/shared/security/   @lore-security-team
src/lore_eligibility/bootstrapper/auth.py   @lore-security-team
src/lore_eligibility/services/vault/    @lore-security-team
src/lore_eligibility/services/audit/    @lore-security-team
docs/adr/                                @lore-architecture-team
```

Plus: branch protection requiring 2 reviewer approvals on these paths.

**Effort:** S.

---

## 7. Supply Chain Security

End-to-end provenance: from dependency to production.

### S-041: Vulnerability management SLAs — FINDING

**Where:** pip-audit configured. SLAs not stated.

**Why it matters:** Discovery without SLA is theater. Standard SLAs:
- Critical CVE (CVSS ≥ 9.0): patched within 7 days
- High (CVSS 7.0-8.9): patched within 30 days
- Medium: patched within 90 days
- Low: patched at next regular update

**What's needed:** ADR: vulnerability management policy with SLAs, exception process (when patch is unavailable), tracking dashboard, automated escalation for SLA breaches.

**Effort:** S.

---

### S-042: Container image signing and provenance — FINDING

**Where:** ARD doesn't address.

**Why it matters:** Verifying that production runs only known-good images. SLSA (Supply chain Levels for Software Artifacts) provides framework levels.

**What's needed:** ADR:
- Build provenance via GitHub Actions OIDC + Sigstore Cosign signatures.
- Cloud Run policy: only execute signed images from a specified registry.
- Provenance attestations attached to images (build commit, build time, builder identity).
- Target SLSA Level 2 by Phase 1; Level 3 by Phase 4.

**Effort:** M.

---

### S-043: Third-party library risk assessment — FINDING

**Where:** Implicit.

**Why it matters:** Splink, FastAPI, SQLModel, asyncpg, etc. — each has its own security posture. Some have known historical issues (`pyyaml.load`); some have dependency trees with weakly-maintained libraries.

**What's needed:** Periodic third-party library audit:
- Quarterly review of all production dependencies via `pip-licenses` + Snyk / Dependabot.
- Evaluation criteria: maintenance activity, security history, dependency tree depth, deprecation status.
- Red-listed libraries explicitly forbidden (e.g. `pyyaml.load`, `pickle` for untrusted inputs).
- Approval gate for new dependencies (ADR for non-trivial additions).

**Effort:** S (process); ongoing.

---

### S-044: CI/CD pipeline security — FINDING

**Where:** Round 2 F-147 covered CI/CD shape. Security depth here.

**Why it matters:** GitHub Actions are a privileged attack surface. Compromised workflow = code injection in production.

**What's needed:** ADR:
- Branch protection on `.github/workflows/` requires 2 approvers.
- CI secrets scoped to specific workflows; no broad `secrets.*` access.
- Workflow approvals required for runs against main from forks.
- Egress controls in CI: deny-list known data exfil destinations; allow-list package registries.
- Runner hygiene: Google-hosted runners only; self-hosted runners forbidden in this org.

**Effort:** S.

---

### S-045: Partner data integrity verification — FINDING

**Where:** BR-304 covers schema drift; S-016 covers data minimization. Integrity verification at the file level not addressed.

**Why it matters:** Compromised partner SFTP → adversary injects manipulated eligibility data. Detection beyond schema drift:
- File integrity: SHA-256 hash of file at landing; compare against partner-side hash sent out-of-band (email, separate channel) when feasible.
- Volume anomaly: feed size deviation > 3-sigma triggers manual review.
- Structural anomaly: per-field distribution vs baseline (BR-305 profile drift handles some).
- Cryptographic signing of files where partners support it (PGP, S/MIME).

**What's needed:** ADR: partner file integrity verification framework. Per-partner config: hash-out-of-band, signing, anomaly thresholds.

**Effort:** M.

---

## 8. Detection and Response

### S-046: SIEM and centralized security event monitoring — BLOCKER

**Where:** Implicit.

**Why it matters:** Logs are collected (Cloud Logging). Audit events are tiered. Without SIEM correlation, signals are siloed; insider threat, multi-stage attacks, lateral movement all evade single-source detection.

**What's needed:** ADR: SIEM strategy. GCP options: Chronicle (Google's SIEM), Splunk (third-party), Elastic Security. Correlation rules covering:
- Auth burst (failed-login spike across many users → credential stuffing)
- Privilege escalation chains (role grant → privileged action → role revoke within short window)
- Cross-service anomalies (Verification API + Audit Consumer simultaneous degradation)
- Data exfiltration patterns (high detok rate + outbound network volume)

**Effort:** L (selection + integration + rule authoring).

---

### S-047: Anomaly detection on access patterns — FINDING

**Where:** Round 3 S-036, S-038 cover specific signals. This is the unified detection plane.

**Why it matters:** Per-user, per-role, per-resource baselines + ML or rule-based detection.

**What's needed:** Layered:
- Statistical: 3-sigma alerts on per-user metrics.
- ML: trained on historical access patterns; flag novel access combinations.
- Pattern matching: known attack patterns (rapid sequential access, batch detok with no business context).

**Effort:** L.

---

### S-048: Incident response plan — BLOCKER

**Where:** Phase 4 mentions runbook formalization. Earlier phases don't have IR plan.

**Why it matters:** Phase 1 hits production traffic. Phase 1 incidents need an IR plan. HIPAA breach notification timeline (60 days from discovery to affected-individual notification) starts the clock when the breach is discovered.

**What's needed:** IR plan documented before Phase 1:
- Roles: Incident Commander, Security Lead, Engineering Lead, Communications Lead, Legal/Compliance Liaison.
- Severity levels: SEV1 (active breach), SEV2 (suspected breach), SEV3 (vulnerability disclosure), SEV4 (operational issue).
- Procedures per SEV: detection → triage → containment → eradication → recovery → post-incident.
- Communication tree: internal (Slack channel, on-call), external (regulators, partners, members) with timeline.
- Forensic preservation: legal hold procedure, log snapshot, chain of custody.
- Tabletop exercises: quarterly SEV1 simulation in pre-production.

**Effort:** L.

---

### S-049: HIPAA breach notification timeline — BLOCKER

**Where:** Implicit.

**Why it matters:** HIPAA §164.404-410: 60 days from discovery to notify affected individuals; >500 individuals = notify HHS within 60 days; some states have shorter timelines (CCPA: 72 hours for some categories).

**What's needed:** ADR + procedure:
- Discovery definition: when does the clock start? (Per HIPAA: when the covered entity reasonably should have known.)
- Risk assessment template (per §164.402(2)): factors to evaluate whether PHI was compromised.
- Notification templates: pre-approved by counsel; populated with incident specifics.
- State-by-state timeline matrix (50 states; Lore operates US-wide).
- Notification channel: written notice; electronic only with affirmative consent.

**Effort:** M (template authoring; counsel-reviewed).

---

### S-050: Vulnerability disclosure program — FINDING

**Where:** Implicit.

**Why it matters:** External researchers find vulnerabilities. Without a published program, they either don't report or report to less responsible channels.

**What's needed:**
- security@lore.health email + PGP key.
- Published responsible disclosure policy (90-day timeline standard).
- Hall of fame / acknowledgment for responsible reporters.
- Optional: bug bounty program (HackerOne, Bugcrowd).

**Effort:** S.

---

### S-051: Forensic preservation procedure — FINDING

**Where:** Implicit; touched in S-030 and S-034.

**Why it matters:** When a breach is investigated, evidence preservation chain-of-custody affects legal admissibility and regulatory defensibility.

**What's needed:** Procedure:
- Legal hold initiated by Legal team; broadcasts to all systems retaining relevant data.
- Log snapshots captured to a forensic-only Cloud Storage bucket with separate IAM (Compliance + Legal only).
- Hashes of snapshots recorded in chain of custody log.
- Retention extended indefinitely on held items.

**Effort:** S.

---

### S-052: Penetration testing cadence — FINDING

**Where:** Phase 4 mentions "Penetration testing, third-party security review."

**Why it matters:** Annual minimum, quarterly preferred for HIPAA. External and internal scope.

**What's needed:** Cadence:
- External (public-facing): quarterly, by qualified third party.
- Internal (assumed-breach): annually, by qualified third party.
- Application-level (white-box): per major release.
- Findings tracked with severity, owner, remediation timeline.

**Effort:** S (planning); ongoing (engagement).

---

## 9. Defense in Depth

### S-053: Network micro-segmentation — FINDING

**Where:** ARD: outer + inner VPC-SC perimeters. Within outer perimeter, services communicate freely.

**Why it matters:** Compromise of one service → lateral movement across all services in the outer perimeter. Standard mitigation: micro-segmentation with explicit allow-lists per service-to-service path.

**What's needed:** ADR: per-service ingress allow-list. Verification API: ingress only from LB + Audit topic publish. Match Orchestrator: ingress only from staging-records subscription + AlloyDB connection. Etc.

**Effort:** M (initial config; ongoing maintenance).

---

### S-054: Edge protection — Cloud Armor / WAF — FINDING

**Where:** Verification API behind a load balancer. Cloud Armor not mentioned.

**Why it matters:** Public endpoints face the full internet. Without WAF: SQL injection (mitigated by parameterized queries but defense-in-depth), DDoS, OWASP Top 10 attack patterns.

**What's needed:** ADR: Cloud Armor policy on Verification API LB. Default deny; allow-list known clients (Lore application IPs); rate limits; OWASP Core Rule Set; bot management; geo-restriction (US-only sources for Verification calls).

**Effort:** S.

---

### S-055: Egress controls — FINDING

**Where:** Outer VPC-SC perimeter restricts egress. Specifics not enumerated.

**Why it matters:** Defense against data exfiltration via compromised service. Default-deny egress with per-service allow-list.

**What's needed:** ADR: egress allow-list per service.
- Format Adapter: SFTP to partner endpoints (specific IPs/hostnames).
- Verification API: reCAPTCHA Enterprise endpoint only.
- All services: GCP API endpoints (KMS, BigQuery, etc.).
- All services: deny everything else.

**Effort:** S.

---

### S-056: Container hardening — FINDING

**Where:** Dockerfile uses `python:3.12-slim` with non-root user.

**Why it matters:** Standard slim image has unnecessary packages. Distroless (`gcr.io/distroless/python3`) is smaller attack surface. Read-only root filesystem prevents tampering.

**What's needed:** ADR: container hardening standard. Distroless base; read-only root filesystem (with tmpfs for `/tmp`); no shell in image (debugging via `kubectl exec` impossible — tradeoff); minimum capabilities (`--cap-drop=ALL --cap-add=NET_BIND_SERVICE` if any privileged port needed); seccomp profile (`runtime/default`).

**Effort:** M (per-service Dockerfile updates).

---

### S-057: Runtime security monitoring — FINDING

**Where:** Implicit.

**Why it matters:** Container compromise detection: anomalous process execution, unexpected network connections, file integrity.

**What's needed:** ADR: runtime security via GCP Container Threat Detection (built into GKE Standard) or third-party (Falco, Sysdig). Specific alerts: shell spawned in container, network connection to non-allow-listed IP, file modification in read-only paths.

**Effort:** M.

---

### S-058: Secrets management runtime — FINDING

**Where:** Phase 00 `.env` file. Production should use Secret Manager.

**Why it matters:** `.env` in production is risk (file system access = secret access). Secret Manager: KMS-backed, IAM-scoped, audited per access.

**What's needed:** ADR: production secrets via Secret Manager + Workload Identity. Service mounts secrets at runtime via metadata server; `.env` deprecated in production. Rotation: per-secret cadence.

**Effort:** S.

---

## 10. HIPAA, HITECH, and State Law Specifics

The BRD acknowledges HIPAA generally. Specific compliance controls need explicit treatment.

### S-059: HIPAA Privacy Rule — minimum necessary — BLOCKER

**Where:** BRD references HIPAA but doesn't enumerate Privacy Rule specifics.

**Why it matters:** §164.502(b) "Minimum Necessary" requires that PHI use/disclosure be limited to minimum necessary. Implementation: role-based access (covered), purpose limitations per access (S-020 covers per-field).

**What's needed:** ADR: minimum-necessary enforcement.
- Per-role accessible-field allow-list (an Auditor sees event metadata, not target_token resolution unless investigation justification).
- Per-API-endpoint accessible-field allow-list (Verification API request body fields are minimum necessary; no extra fields accepted).
- Documentation: minimum-necessary justification per role and per endpoint.

**Effort:** S.

---

### S-060: HIPAA Right of Access (45 CFR §164.524) — FINDING

**Where:** BR-704 covers right-to-deletion. Right-of-access not addressed.

**Why it matters:** Members can request access to their PHI. Most member-facing right-of-access is the responsibility of the Lore application; the eligibility system supports the underlying queries.

**What's needed:** ADR: right-of-access support.
- Query path: by member identity → all canonical records, partner enrollments, lifecycle history.
- Format: HHS-recommended electronic format (PDF, JSON).
- Timeline: 30 days from request to fulfillment (HIPAA requirement).
- Authentication: requestor identity verified before fulfillment.

**Effort:** M.

---

### S-061: HIPAA Accounting of Disclosures (45 CFR §164.528) — FINDING

**Where:** BR-501 audit covers all PII access. Accounting of Disclosures specifically tracks disclosures to outside parties for treatment, payment, operations purposes — usually exempt from accounting per §164.528(a)(1)(i)-(iii).

**Why it matters:** Members can request accounting of disclosures (6 years history). Mostly excluded for TPO disclosures; non-TPO disclosures (research, public health, law enforcement) require accounting.

**What's needed:** Audit event class: DISCLOSURE_TO_EXTERNAL_PARTY with required fields (recipient, purpose, fields disclosed, justification). Query path: per-member disclosure accounting.

**Effort:** S (mostly inherits from existing audit infrastructure).

---

### S-062: 42 CFR Part 2 substance use disorder — BLOCKER

**Where:** BRD: "42 CFR Part 2 if substance use disorder data is in scope (likely not for general eligibility, but worth scoping out explicitly)."

**Why it matters:** Part 2 applies if any partner data includes SUD treatment information. Stricter than HIPAA: explicit consent for each disclosure, prohibition on certain re-disclosures. If partner data includes SUD program identifiers (even payer codes can imply SUD), Part 2 applies.

**What's needed:** Explicit decision in BRD:
- Option A: Reject partners whose data includes SUD-program identifiers. Define "SUD-program identifiers" precisely.
- Option B: Implement Part 2 controls (additional consent management, restricted disclosure, separate audit retention).
- Option C: Accept the risk and document.

A is simplest; B is the right choice if Lore's partner book includes SUD providers.

**Effort:** S to decide; M-L if Option B.

---

### S-063: HITECH meaningful use audit — FINDING

**Where:** Implicit.

**Why it matters:** HITECH adds requirements for breach notification, audit logging, and EHR access logging. ACOs are subject to subset of HITECH requirements.

**What's needed:** Compliance review against applicable HITECH requirements; gaps captured in compliance binder.

**Effort:** S.

---

### S-064: State law breach response matrix — BLOCKER

**Where:** BRD: "California, Washington, broader patchwork of state-level health and consumer privacy laws."

**Why it matters:** Each state has unique requirements: CCPA (45-day notification with affirmative consent for some categories), CPRA (extended), Washington MHMDA (health-data-specific), New York SHIELD Act, Texas HB 4 (60-day notification + state AG), Massachusetts §93H, etc. ACO operates US-wide.

**What's needed:** State-by-state matrix:

| State | Trigger | Timeline | Recipients | Notification format |
|---|---|---|---|---|
| California (CCPA/CPRA) | Unauthorized PHI/PII access affecting CA residents | Without unreasonable delay; AG if >500 | AG + affected residents | Substitute notice if cost > $250k |
| Washington (MHMDA) | Health data breach | 30 days | AG + affected residents | Specific MHMDA categories |
| ... (50 states) | ... | ... | ... | ... |

Counsel-authored. Updated annually.

**Effort:** L (counsel engagement).

---

### S-065: HIPAA Security Rule §164.310 Physical Safeguards — FINDING

**Where:** Cloud-hosted; GCP handles physical.

**Why it matters:** GCP BAA confirms scope. Lore's BAA chain documents must include this.

**What's needed:** Compliance artifact: signed BAA with Google. Annual review. Subprocessor list (S-027) cross-references this.

**Effort:** S.

---

### S-066: HIPAA Security Rule §164.314 Organizational Requirements — FINDING

**Where:** BAA chain mentioned in BRD as advisory.

**Why it matters:** Subprocessor lifecycle management: onboarding (BAA executed), monitoring (compliance posture), termination (BAA termination + data return/destruction).

**What's needed:** ADR: subprocessor lifecycle. Process for adding new subprocessor, periodic review (annual), termination procedures, member notification of subprocessor changes (if required by partner contracts).

**Effort:** S.

---

### S-067: Partner-side deletion contract — FINDING

**Where:** BR-702: partner notified via BAA channel. Contract terms not specified.

**Why it matters:** Lore can delete its copy. Partner's copy is partner's responsibility. BAA must specify partner's deletion obligation upon Lore-side deletion.

**What's needed:** Standard BAA addendum: partner agrees to delete or de-identify per Lore notification within 30 days; partner provides certification of deletion.

**Effort:** S (legal template).

---

### S-068: Privacy notice — public-facing — ADVISORY

**Where:** Out of scope for the eligibility system; the Lore application's responsibility.

**Why it matters:** Verification API is consumer-facing (via Lore application). Privacy notice references the eligibility system's data handling.

**What's needed:** Coordinate with Lore application's privacy notice. Cross-reference eligibility system controls in the notice.

**Effort:** S (coordination).

---

## 11. Threat Modeling per Bounded Context

The principal architect (R1 F-018) noted STRIDE was absent. This round delivers a starter STRIDE per context.

### S-069: STRIDE per bounded context — BLOCKER

**Where:** Round 1 F-018 (gap noted).

**Why it matters:** Without per-context threat model, security investments are uneven; some contexts over-controlled; others under-controlled.

**What's needed:** STRIDE table per context. Below is a starter; needs deepening with the team:

#### Ingestion & Profiling

| Threat | Specific scenario | Existing mitigations | Gaps |
|---|---|---|---|
| Spoofing | Adversary submits malicious file via partner SFTP credentials | SFTP authentication | F-016 (credential lifecycle); S-045 (file integrity) |
| Tampering | Adversary modifies in-flight file in landing zone | Cloud Storage immutability + versioning | None — adequate |
| Repudiation | Partner denies sending file later | File hash logged at landing | None — adequate |
| Info disclosure | Quarantined file accessible to unauthorized | IAM on quarantine bucket | Per-partner IAM scoping in quarantine |
| DoS | Massive partner feed overloads pipeline | Backpressure + per-partner rate limit | F-150 (backpressure) |
| Elevation | Format adapter compromised → access to all partners' files | Adapter is stateless; no inter-file context | Reaffirm |

#### Identity Resolution

| Threat | Specific scenario | Existing mitigations | Gaps |
|---|---|---|---|
| Spoofing | Adversary forges staging records to manipulate matching | Pub/Sub schema validation + signed messages | F-128 (Protobuf schema); message signing |
| Tampering | Match decision modified in flight | Outbox pattern + audit | F-102 (outbox) |
| Repudiation | Reviewer claims they didn't make a decision | Audit on resolve action | S-035 (per-actor signing) |
| Info disclosure | Match scores leaked → re-identification via score patterns | Tokenized data only; reviewer auth | S-040 (CODEOWNERS for review code) |
| DoS | Massive dirty feed exhausts Splink runner | Per-partner concurrency limits | New finding |
| Elevation | Reviewer abuses queue access for unauthorized reviews | Resource-level authorization | S-010 (IDOR); S-032 (auditor monitoring) |

#### Canonical Eligibility

| Threat | Scenario | Mitigations | Gaps |
|---|---|---|---|
| Spoofing | Lifecycle event injected from outside | Pub/Sub schema; service-to-service auth | F-128, F-141 |
| Tampering | Direct DB modification | IAM + DB user least privilege | New: Vault + canonical separate DB users with no cross-DB access |
| Repudiation | State change without attribution | Lifecycle event log | Adequate |
| Info disclosure | Cross-partner data leakage | Schema = neutral; tokens cross-partner via deterministic with per-partner salt? | S-001 reinforce per-partner salts |
| DoS | Verification overload AlloyDB | Read replica; rate limit; F-126 | F-126 Memorystore HA tier |
| Elevation | App role privilege escalation | DB role scoping | New: per-service DB user; least privilege |

#### PII Vault

| Threat | Scenario | Mitigations | Gaps |
|---|---|---|---|
| Spoofing | Unauthorized service impersonating TokenizationService | Inner VPC-SC + IAM | Adequate |
| Tampering | Vault data modification by privileged user | Audit + multi-party approval | S-011 two-person rule |
| Repudiation | Detok event without attribution | Audit on every detok | S-035 strong signing |
| Info disclosure | PII leakage via memory dump | KMS HSM tier | S-058 secrets at rest; HSM tier |
| Info disclosure | Frequency analysis via deterministic tokens | (Round 1 F-003 surfaced) | S-001 keyed deterministic |
| DoS | Vault unavailability fails verification | Fail-closed + graceful degradation | S-108 fail-closed |
| Elevation | KMS key extraction | HSM-backed; mlocked memory | S-058 HSM tier |

#### Verification

| Threat | Scenario | Mitigations | Gaps |
|---|---|---|---|
| Spoofing | Forged JWT | RS256 + jwks + jti | S-005 JWT specifics |
| Tampering | Request body modification post-claim | TLS + LB validates | Adequate |
| Repudiation | Verification result claimed wrong | Per-request audit | Adequate |
| Info disclosure | Existence inference via timing | Latency-equalization | (R1 F-004 surfaced); S-074 timing depth |
| Info disclosure | Existence inference via response shaping | Body size differences | New: padding to constant size |
| DoS | DDoS on Verification | Cloud Armor; rate limits | S-054 Cloud Armor |
| DoS | Brute-force enumeration | BR-402 lockout | Adequate |
| Elevation | Account takeover via verified claim | Verification ≠ authentication | S-073 contract |

#### Audit

| Threat | Scenario | Mitigations | Gaps |
|---|---|---|---|
| Spoofing | Forged audit events | Service-to-service auth + schema validation | Adequate |
| Tampering | Audit log modification | WORM + hash chain | Adequate |
| Tampering | Insider with admin access modifies audit IAM | (gap) | S-031 cross-org replication |
| Repudiation | Actor denies action | Audit captures principal | S-035 strong signing |
| Info disclosure | Audit data leak | Auditor-only access | S-032 auditor monitoring |
| DoS | Audit topic backlog | Pub/Sub backpressure + Dataflow scaling | F-150 backpressure |
| Elevation | Audit consumer compromise → tamper chain | (gap) | S-030 forensic preservation |

#### Deletion

| Threat | Scenario | Mitigations | Gaps |
|---|---|---|---|
| Spoofing | Forged deletion request | Out-of-band requester verification | S-060 right-of-access; verification process |
| Tampering | Deletion executor manipulated | Single-actor today | S-011 two-person rule for deletion |
| Repudiation | Deletion executed but not auditable | Audit on each step | Adequate |
| Info disclosure | Deletion ledger reversibility | (Round 1 F-003 + S-002 surfaced) | S-002 argon2 / HMAC |
| DoS | Mass deletion request | Rate limit + approval gate | S-011 two-person rule |
| Elevation | Override path abuse | Operator override audit | S-011 two-person rule |

**Effort:** M (initial); ongoing as system evolves.

---

### S-070: Asset classification — FINDING

**Where:** Implicit.

**Why it matters:** Drives where security spend goes. Asset C/I/A ratings:

| Asset | Confidentiality | Integrity | Availability |
|---|---|---|---|
| PII Vault (plaintext) | CRITICAL | CRITICAL | HIGH |
| Canonical Eligibility | HIGH (tokens) | CRITICAL | CRITICAL (verification path) |
| Audit log | HIGH | CRITICAL | HIGH |
| Deletion ledger | HIGH | CRITICAL | MEDIUM |
| Match decisions | MEDIUM | HIGH | MEDIUM |
| Configuration | MEDIUM | CRITICAL (config-driven behavior) | HIGH |
| Application code | MEDIUM | CRITICAL | HIGH |
| KMS keys | CRITICAL | CRITICAL | HIGH |
| Splink models | LOW | HIGH (correctness affects matches) | MEDIUM |
| Operational logs | LOW (PII redacted) | MEDIUM | MEDIUM |

**Effort:** S.

---

## 12. Specific Attack Vectors

### S-071: Replay attacks — FINDING

**Where:** Round 2 F-130 noted idempotency keys at HTTP API; security depth here.

**Why it matters:** Adversary captures legitimate JWT or API request, replays. Mitigations: jti claim with replay cache, idempotency keys, time-bound nonces.

**What's needed:** Layered:
- JWT replay: jti in cache (Memorystore, TTL = JWT expiry).
- HTTP idempotency: request_id with TTL'd response cache.
- Audit replay (Pub/Sub): event_id deduplication in consumer.

**Effort:** S.

---

### S-072: Time-of-check-vs-time-of-use (TOCTOU) — FINDING

**Where:** Implicit.

**Why it matters:** Authorization checked at request entry; database operation happens later; authorization revoked between → operation succeeds without authority.

**What's needed:** Convention: re-check authorization at write time within the same database transaction. Or: maintain authorization in transaction (row-level security).

**Effort:** S (convention).

---

### S-073: Verification ≠ authentication — distinct contract — BLOCKER

**Where:** ARD: "Verification API serving the Lore application's account creation flow."

**Why it matters:** Verification confirms a claim (this PII matches an eligibility record). It does NOT confirm the claimant is the person whose data they're submitting. An adversary with stolen PII passes verification. The Lore application must not treat VERIFIED as sufficient for account creation.

**What's needed:** Explicit contract:
- Verification API doc states: "VERIFIED indicates the submitted claim matches an eligible identity. It does not authenticate the requester. Account creation must include independent factors (email verification, identity proofing, etc.)."
- Verification API rate limits per claim shape (per BR-402).
- Lore application's account creation flow includes additional factors documented in contract.

**Effort:** S.

---

### S-074: Verification timing channel depth — FINDING

**Where:** Round 1 F-004 covered floor-padding; security depth here.

**Why it matters:** Floor padding helps but other side channels remain:
- Response body size (different outcomes have different content lengths despite identical fields)
- TCP packet timing (multi-packet responses leak byte counts)
- HTTP/2 stream priorities
- TLS alert timing
- Error response paths (rate-limit response timing distinct from normal NOT_VERIFIED)

**What's needed:** Constant-time response: pad body to fixed size; flush response in single TCP segment where possible; ensure error paths take the same time as success paths; equalize all internal-state-conditional code paths via dummy work.

**Effort:** M.

---

### S-075: Splink adversarial inputs — FINDING

**Where:** Implicit.

**Why it matters:** Splink trained on data; adversary crafts records to:
- Force false positives (multiple identities merge to one — re-identification + account takeover)
- Force false negatives (same identity stays distinct — fraud across partners)
- Extract training data via probing match scores

**What's needed:**
- Adversarial robustness in training data: avoid systematic biases.
- Anomaly detection on match decisions: high-velocity merges trigger review.
- Score-extraction defense: limit reviewer access to score breakdowns to claim-by-claim, no aggregate exposure.

**Effort:** M.

---

### S-076: Cross-partner temporal correlation — ADVISORY

**Where:** Round 1 F-003 covered frequency analysis. Temporal pattern is a related but distinct attack.

**Why it matters:** Token X appears in Feed A on Day 1, Feed B on Day 3 → correlates Partner A and B membership for same person. Tokenization doesn't prevent this; only joining-on-token prevention via per-partner salts (S-001).

**What's needed:** Per-partner salts for tokens that should not correlate cross-partner. The deletion ledger's `partner_member_id_hash` is per-partner — generalize to all tokens that don't need cross-partner equality.

**Effort:** S.

---

### S-077: Memory-resident key extraction — ADVISORY

**Where:** KMS keys in service memory during operations.

**Why it matters:** Compromise of a service instance → memory dump → key extraction. Mitigation: HSM-backed KMS (Cloud KMS HSM tier) means keys never leave the HSM in plaintext.

**What's needed:** HSM tier for KMS keys protecting PII Vault encryption. Software tier acceptable for less-sensitive keys (audit signing, etc.). Per-key tier classification.

**Effort:** S (config + cost trade-off).

---

## 13. Quantum and Long-Horizon Concerns

### S-078: Quantum resistance — ADVISORY

**Where:** Implicit.

**Why it matters:** SHA-256, RSA, ECDSA may be broken by quantum (decade horizon). Long-retention data (audit log 7 years; deletion ledger indefinite) is exposure to "harvest now, decrypt later."

**What's needed:** ADR: quantum-readiness tracking. NIST post-quantum standards (CRYSTALS-Kyber, CRYSTALS-Dilithium) finalized 2024; migration is multi-year. Track via algorithm versioning (S-008). Plan migration before NIST-recommended sunset of current algorithms.

**Effort:** S (tracking ADR; migration deferred years).

---

## 14. Security Operations and Training

### S-079: Security training requirements — FINDING

**Where:** Implicit.

**Why it matters:** HIPAA §164.530(b)(1) requires workforce training. Annual baseline; role-specific deeper training.

**What's needed:** Training program:
- All staff: annual HIPAA + security awareness (phishing, social engineering, password hygiene).
- Engineers: secure coding (OWASP Top 10, language-specific).
- PII Handlers: HIPAA Privacy Rule deep dive; minimum necessary; right-of-access; right-to-deletion.
- Auditors: forensic procedures; chain of custody.
- Break-Glass Admins: incident response; tabletop exercises.

Compliance: training records retained per HIPAA retention.

**Effort:** S (program design); ongoing (delivery).

---

### S-080: Security architect review on amendments — FINDING

**Where:** ARD review cadence is the principal architect's role (R1 F-022). Security amendments need security review.

**Why it matters:** Some amendments (new data type, new partner-data category, new role) have security implications that the architecture review may miss.

**What's needed:** Convention: any BRD/ARD amendment touching security primitives, role definitions, data classes, or audit categories requires security-architect approval (CODEOWNERS extension).

**Effort:** S.

---

## Summary triage

| Severity | Count | Examples |
|---|---|---|
| BLOCKER | 18 | Keyed deterministic tokenization (S-001), Argon2 deletion ledger (S-002), Tokenization clarity (S-003), JWT specifics (S-005), TLS config (S-006), PEP/PDP model (S-009), IDOR per-resource (S-010), Two-person rule (S-011), Sessions (S-012), PII/PHI classification (S-016), Data minimization (S-017), Right-to-deletion completeness (S-022), Residency = location (S-024), Audit completeness (S-028), Audit chain forensic preservation (S-030), Audit forensic readiness (S-034), Privileged user baselining (S-036), SIEM (S-046), IR plan (S-048), Breach notification (S-049), Minimum necessary (S-059), Part 2 decision (S-062), State law matrix (S-064), STRIDE per context (S-069), Verification ≠ auth (S-073) |
| FINDING | 47 | DEK lifecycle, RNG, algorithm versioning, Workload Identity depth, privileged lifecycle, pseudonymization terms, SSN handling, purpose specs, retention table, membership inference, cross-border audit, backup residency, subprocessors, forensic indexes, immutability cross-org, auditor monitoring, WORM evidence, non-repudiation, session limits, insider signals, departure procedures, CODEOWNERS, vuln SLAs, image signing, library audit, CI security, partner integrity, anomaly detection, vuln disclosure, forensic preservation, pen test cadence, micro-segmentation, Cloud Armor, egress, container hardening, runtime security, secrets management, right of access, accounting of disclosures, HITECH, BAA chain, subprocessor lifecycle, partner deletion, asset classification, replay attacks, TOCTOU, timing depth, Splink adversarial, training, security architect on amendments |
| ADVISORY | 9 | Cross-partner temporal correlation, memory-resident keys, quantum resistance, privacy notice coordination, plus a few smaller items |
| **Total** | **74** | (18 + 47 + 9) |

Note: I exceeded both prior rounds. Security touches every layer — by definition, more controls to enumerate. Many findings overlap with prior rounds (cited where applicable); the BLOCKER counts across all three rounds, deduplicated, are approximately 37 unique items.

---

## Recommended path before backlog

1. **Address all 18 BLOCKERS.** None are large individually; collectively they're meaningful. Most are S or M effort. Two are L (S-046 SIEM, S-048 IR plan, S-064 state law matrix) — those are likely Phase 0 work that overlaps with normal Phase 0 readiness.
2. **Address compliance-critical FINDINGS** before Phase 1 production traffic: S-027 (subprocessors), S-049 (breach notification — overlaps BLOCKER), S-052 (pen test), S-079 (training).
3. **Defer remaining FINDINGS** to dedicated ADRs in `docs/adr/` with named owners and target phases. Most are S effort.
4. **Address ADVISORIES** opportunistically.

If all three rounds' BLOCKERS are resolved, the platform will be HIPAA-defensible and audit-ready. If only the architectural shape is delivered, the platform passes a friendly walkthrough but fails an external red-team or attestation audit.

---

## Hand-offs to subsequent review rounds

| Round | Reviewer | Findings to dig into |
|---|---|---|
| 4 | Data-Engineering Principal | S-018 pseudonymization terms in analytical context, S-021 retention per data class, S-039 partner integrity verification, S-075 Splink adversarial inputs |
| 4 | Infra / DevOps Architect | S-046 SIEM selection, S-053 micro-segmentation, S-054 Cloud Armor, S-055 egress, S-056 container hardening, S-057 runtime security, S-058 secrets management |
| 4 | Compliance / Legal | S-049 breach notification, S-064 state law matrix, S-062 Part 2 decision, S-066 subprocessor lifecycle, S-067 partner deletion contract, S-068 privacy notice |
| 4 | Clinical-Trust Reviewer | S-073 Verification ≠ auth implications for member experience |

---

## What this review did NOT cover

Out of scope for the principal-security-engineer lens:

- BRD content correctness against domain reality (DE Principal; clinical-trust)
- Specific GCP service feature gaps (Infra/DevOps)
- Legal language in BAA / privacy notices (Compliance/Legal)
- Architectural decomposition tradeoffs (Round 1)
- Code-level discipline (Round 2 — though many findings here have code-level expression)
- Performance / capacity (Round 1)

These belong to other reviewers. This round focused on the security-specific gaps that, if unaddressed, fail HIPAA defensibility against a sophisticated adversary, against an external attestation auditor, or against a determined insider.
