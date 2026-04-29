# ADR-0003: Tokenization and Deletion Ledger Cryptographic Lifecycle

| Field | Value |
|-------|-------|
| **Status** | ACCEPTED |
| **Date** | 2026-04-29 |
| **Phase** | Phase 00 (synthesis pre-Phase 1) |
| **Originating findings** | R1 F-003 (deterministic token frequency analysis), R3 S-001 (keyed tokenization with KDF), R3 S-002 (HMAC ledger), R3 S-004 (DEK lifecycle), R3 S-008 (algorithm versioning) |

---

## Context

The system has two related cryptographic constructs:

1. **Tokenization** — replaces plaintext PII with reversible tokens. Some tokens
   must be deterministic (so the canonical model can support BR-102's anchor
   match on `name_token` + `dob_token` via equality). Others may be random
   (no joinability required).

2. **Deletion ledger** — one-way hashes of match-relevant attributes per BR-703,
   used to suppress re-introduction of deleted identities on subsequent
   ingestion.

Both constructs face cryptographic-correctness challenges:

- **Naive deterministic tokenization** (`token = stable_function(plaintext)`)
  preserves frequency. An attacker with read access to the analytical surface
  (e.g., a Sequelae PH ML engineer with BigQuery access — permitted by
  AD-003 to see tokenized data) sees `name_token = X` appearing 10,000 times
  and infers, against a US census prior, that X tokenizes "Smith." Chained
  with deterministic `dob_token`, this produces re-identification without
  ever touching the Vault.

- **Bare salted SHA-256** for the deletion ledger (BR-703 as drafted) is
  reversible by an attacker with the salt. The salt is environment-scoped and
  stored alongside application code or config — a moderately-skilled attacker
  with code access can offline-compute hashes for arbitrary candidate
  populations (the US population is bounded; ~10⁹ name+DOB combinations are
  brute-forceable).

- **Per-record DEK** as drafted in AD-008 is operationally infeasible at scale
  without DEK caching: KMS rate limits and cost.

- **No algorithm versioning** in the original design means future cryptographic
  agility (rotating from SHA-256 to SHA-3 or argon2 if SHA-256 weakens)
  requires a flag day.

## Decision

The cryptographic lifecycle is specified as follows.

### 1. Tokenization key model — keyed deterministic tokenization

For each token class (e.g., `name_token`, `dob_token`, `address_token`,
`email_token`, `phone_token`, `ssn_token`, `partner_member_id_token`), the
TokenizationService maintains a per-class secret key:

```
class_key = HKDF(
    master = KMS_master_key,
    salt = "lore_eligibility:v1:<class_name>",
    info = "tokenization-class-key",
    length = 32,
)
```

Tokens are computed:

```
token = "v1:" + base64(HMAC-SHA-256(class_key, normalize(plaintext)))
```

The `v1:` prefix is the **algorithm version**; future rotation produces `v2:`
tokens with a new key. Both versions coexist during rotation.

For tokens that should not correlate cross-partner (e.g.,
`partner_member_id_token`), the `class_name` is partner-scoped:
`class_name = "partner_member_id:<partner_id>"`. Tokens then have per-partner
domains and cannot be joined cross-partner without Vault access.

### 2. Tokenization storage and DEK lifecycle

The Vault stores `(token, encrypted_plaintext)` rows. The plaintext is
encrypted with envelope encryption:

- **DEK (Data Encryption Key)**: per-class, per-day; cached in
  TokenizationService memory for the day; rotated at midnight UTC.
- **KEK (Key Encryption Key)**: per-class, KMS-resident, HSM-backed (Cloud
  KMS HSM tier per R3 S-077); rotated annually with grace period.
- **Plaintext encryption**: AES-256-GCM with the DEK; ciphertext stored with
  the DEK identifier (the day's class-DEK).

Per-day DEK is rotated at midnight UTC; previous days' DEKs are retained for
detokenization of historical ciphertexts. KEK rotation re-wraps existing DEKs
without re-encrypting plaintext.

### 3. Deletion ledger — HMAC-keyed hash

The `deletion_ledger.suppression_hash` is computed:

```
suppression_hash = "v1:" + base64(HMAC-SHA-256(deletion_ledger_key, normalize(inputs)))
```

Where:
- `deletion_ledger_key` is a KMS-resident key, distinct from tokenization
  class keys, with separate IAM scoping (only Identity Resolution Match
  Orchestrator + Deletion Executor have access).
- `inputs` = `partner_id || normalized_last_name || dob || partner_member_id`
  (joined with a delimiter that cannot appear in normalized inputs).

Offline brute force requires KMS access (rate-limited, audited, IAM-restricted
beyond the application's runtime identity).

### 4. Algorithm versioning

Every cryptographic output is prefixed with an algorithm version (`v1:`).
Migration to `v2:` (e.g., HKDF-HMAC-SHA-3 if SHA-2 weakens) follows:

1. Add `v2:` derivation alongside `v1:`.
2. New tokens written as `v2:`.
3. Lookup logic checks both `v1:` and `v2:` (during transition).
4. Background job re-derives `v1:` tokens to `v2:` (atomic per-record).
5. Once all tokens are `v2:`, `v1:` lookup is removed.

### 5. Rotation cadence

| Key | Rotation period | Mechanism | Grace |
|---|---|---|---|
| Class HMAC key (tokenization) | Annual | KMS rotation; re-derivation via HKDF | 90 days (both keys valid) |
| Class DEK (envelope encryption) | Daily | KMS-issued; cached per day | Previous DEK retained indefinitely |
| Class KEK (envelope encryption) | Annual | KMS auto-rotation | Re-wraps DEKs |
| Deletion ledger key | 5 years | KMS rotation; ledger entries retain `v1:` indefinitely (deletion is final) | N/A |

## Consequences

### Positive

- **Frequency analysis defeated** by HMAC keying: an attacker with analytical
  access cannot brute-force tokens without the class key.
- **Cross-partner correlation prevented** for partner-scoped tokens.
- **Cryptographic agility** through versioning: future algorithm migration
  is forecastable.
- **Operational cost manageable**: per-day DEK caching keeps KMS calls bounded.
- **Defense in depth**: KMS HSM tier prevents key extraction via memory dump
  for the most sensitive operations.

### Negative

- **Increased complexity** vs. naive design. Multiple key types, rotation
  cadences, version migration logic.
- **KMS cost** is non-trivial at scale; envelope encryption with cached DEKs
  is the standard pattern but requires correct cache invalidation on rotation.
- **Operational overhead** for rotation: requires runbooks, monitoring,
  drill exercises.

### Mitigations

- Single TokenizationService implementation centralizes the cryptographic
  logic; all callers use the abstraction.
- KMS rotation cadences are configured in IaC (per ADR-0007 / Round 5
  D-001) and audited.
- Rotation drills run as part of DR drill program (R5 D-039).

## Alternatives considered

1. **Format-preserving encryption (FPE)** for deterministic tokens: FPE
   produces tokens of the same shape as plaintext (useful for legacy
   integration). Rejected: introduces FPE-specific cryptographic concerns;
   Lore has no legacy integration requiring same-shape tokens.
2. **Argon2id for deletion ledger hash** (instead of HMAC-SHA-256): rejected
   as primary mechanism but acceptable as alternative if HMAC keying is
   determined insufficient. Argon2id is computationally expensive (intentional
   for password hashing) but slow for the high-volume ledger lookups during
   ingestion. HMAC-keyed hash provides equivalent attacker-resistance with
   lower runtime cost.
3. **Random tokens for deterministic-equality use cases** with a separate
   "alias" lookup: rejected because the lookup itself becomes the
   re-identification surface.

## References

- Originating findings: R1 F-003, R3 S-001, R3 S-002, R3 S-004, R3 S-008
- ADR-0001 (Harness Foundation)
- BR-102 (Match Anchor Composition)
- BR-703 (Re-Introduction Suppression)
- ARD §"PII Vault Context"
- R3 S-077 (KMS HSM tier for Vault keys)
