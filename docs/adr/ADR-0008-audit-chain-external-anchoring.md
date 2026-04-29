# ADR-0008: Audit Chain Hash Chain with External Anchoring

| Field | Value |
|-------|-------|
| **Status** | ACCEPTED |
| **Date** | 2026-04-29 |
| **Phase** | Phase 00 (synthesis pre-Phase 1) |
| **Originating findings** | R1 F-008 (audit chain external anchoring), R3 S-030 (chain validator cadence + forensic), R3 S-031 (cross-org replication), R3 S-035 (non-repudiation per actor), R3 S-034 (forensic readiness) |

---

## Context

The ARD specifies a hash chain in GCS Bucket Lock'd object stream for the
high-criticality audit tier (PII access, identity merge, deletion). The
chain provides tamper-evidence: each event includes a hash of itself plus
the prior event's hash; chain breaks are detectable; Bucket Lock prevents
modification within the retention period.

This is a strong starting point. Three weaknesses, however:

1. **Chain head is in-system.** The chain head hash is stored in the same
   GCS bucket as the chain body. A sufficiently-privileged adversary with
   write access to the bucket *during the open append window* and the
   ability to suppress events can rewrite recent history before the bucket
   finalizes the locked retention. Without an external anchor, tamper-
   evidence is bounded to "in-system mutation" — sophisticated insider
   abuse is not detected.

2. **Single-organization storage.** GCS Bucket Lock with retention is
   strong. It is not strong against an attacker who compromises GCP
   organization-level admin credentials and changes bucket-level IAM
   policies (which Bucket Lock retention does not prevent — retention
   prevents object deletion/modification, not policy changes). For a
   HIPAA-grade audit, cross-organization replication adds defense in depth.

3. **Forensic readiness is not engineered.** The chain validator runs and
   pages on break, but the recovery procedure on chain break is not
   specified. A chain break could be tampering, replication lag, consumer
   bug, or a benign retry. Each has a different response. Without a
   procedure, the response is improvised at the worst time.

## Decision

### 1. Hash chain construction

Each high-criticality audit event in the GCS object stream contains:

```
{
  "event_id": "<UUID>",
  "event_class": "<class>",
  "actor_role": "<role>",
  "actor_principal": "<principal>",
  "target_token": "<tokenized identifier>",
  "timestamp": "<ISO-8601 UTC>",
  "outcome": "<outcome>",
  "trigger": "<trigger>",
  "context": { ... },
  "correlation_id": "<UUID>",          // per ADR-0006
  "prior_event_hash": "<sha256-hex>",   // hash of the prior event in chain
  "self_hash": "<sha256-hex>",          // sha256 of all preceding fields
  "anchor_id": "<anchor-uuid-or-null>"  // points to external anchor when present
}
```

`self_hash` is computed over the canonical-JSON serialization of all
preceding fields. `prior_event_hash` chains the events.

### 2. Continuous chain validator

A scheduled Cloud Run job runs:

- **Real-time per-event** (validating each event upon arrival in the GCS
  stream against the prior event's hash)
- **Hourly bulk** (validating the chain over the prior 24 hours; catches
  any gaps not caught real-time)

On chain break detection, the validator:

1. Pages on-call (P0 alert per ADR-0006 / R5 D-035).
2. Snapshots the affected GCS objects to a forensic-only bucket.
3. Halts the audit consumer (Dataflow) to prevent further appends until
   triage completes.
4. Emits a `AUDIT_CHAIN_BREAK_DETECTED` system event.

### 3. External anchoring

Every hour, the chain validator publishes the **current chain head hash**
to two external sinks:

#### 3a. Cross-organization replication

- A separate GCP organization (the **Compliance organization**, distinct
  from the Engineering organization) hosts a chain-head registry bucket.
- The Compliance organization is administered by Privacy / Compliance
  leadership; Engineering does not have IAM modification rights.
- The chain head hash + timestamp + signature (signed with a KMS key in
  the Compliance organization) is appended to a Bucket Lock'd object in the
  Compliance organization.

This separation means an attacker who compromises Engineering org-level
admin cannot also rewrite the chain-head registry; both compromises are
required to forge the chain.

#### 3b. Trusted timestamp service (RFC 3161)

- The chain head hash is also submitted to an external RFC 3161 trusted
  timestamp service (commercial provider; e.g., DigiCert's TSA, FreeTSA,
  or government TSA).
- The signed timestamp is stored alongside the chain head in the
  Compliance organization bucket.

This adds a third independent attestation: an external party (the TSA
operator) cryptographically attests the chain head existed at the timestamp.

### 4. Validator + anchor verification

The chain validator additionally verifies:

- Every hourly anchor in the Compliance organization bucket matches what the
  chain produces at that hour's snapshot.
- Anchor mismatches trigger the same forensic preservation procedure as
  chain breaks.

### 5. Forensic preservation procedure

On chain break or anchor mismatch:

1. **Preserve**: snapshot all affected GCS objects to a forensic-only
   Cloud Storage bucket; the snapshot is in a separate KMS-encrypted bucket
   with bucket lock + cross-org replication.
2. **Halt**: pause the audit consumer (Dataflow); pause any write paths
   that emit to the affected stream.
3. **Investigate**: triage by Security + Compliance teams. Categorize:
   - Tampering (real adversarial action) — full IR per ADR R3 S-048
   - Consumer bug (idempotency error, exactly-once-failure) — fix and
     deploy; reconcile chain
   - Replication lag (timestamp ordering issue) — verify and resume
   - False positive (validator bug) — fix validator; resume
4. **Resume**: only after Security + Compliance sign-off. Resume requires:
   - A signed `CHAIN_RESET` event written to the chain documenting the
     break, investigation outcome, and resumption.
   - Updated anchor in the Compliance organization.
5. **Document**: incident postmortem; HIPAA breach assessment per L-009.

### 6. Per-actor non-repudiation (deferred)

R3 S-035 raised stronger non-repudiation: per-actor signing of audit
events using an actor-bound key (FIDO2 / WebAuthn for human actors;
KMS-bound service identity for service actors). This is engineering-
significant and is **deferred**:

- Service-actor signing: **planned for Phase 2**; service identity
  signing via KMS-bound keys.
- Human-actor signing (WebAuthn): **deferred to v2** with documented
  residual risk (audit attribution relies on session authentication +
  audit log binding; sufficient for HIPAA defense; insufficient for
  full non-repudiation).

## Consequences

### Positive

- **Tamper-evidence at three levels**: in-stream chain, cross-org
  registry, external TSA. All three would have to be subverted to forge.
- **Forensic readiness**: documented preservation procedure prevents
  evidence loss during investigation.
- **Audit defensibility**: external attestation (TSA) provides legally
  significant proof of chain integrity at given timestamps.
- **Ops-tested**: chain validator runs continuously; integration tests
  exercise the break-and-recover path.

### Negative

- **Operational complexity**: cross-org bucket; KMS keys in two orgs;
  TSA integration; periodic verification runs.
- **External dependency**: TSA service availability; mitigated by
  retries and acceptance that occasional anchor latency is acceptable
  (the chain itself doesn't depend on TSA being available, only the
  external attestation does).
- **Cost**: small additional storage, KMS, network egress for
  cross-org replication; TSA fees if commercial provider.

### Mitigations

- Compliance organization is set up as part of Phase 0 IaC.
- TSA integration uses retry + circuit breaker per ADR-0006; on extended
  TSA outage, anchor is queued and submitted on recovery.
- Forensic preservation procedure is documented; quarterly drill (R5
  D-039) exercises chain-break recovery.

## Alternatives considered

1. **In-stream chain only (no external anchor)**: rejected. Tamper-
   evidence is bounded; sophisticated insider compromise is not detected.
2. **Blockchain-style distributed ledger**: rejected. Operational cost
   and energy footprint vastly exceed value; HIPAA requirements are met
   by simpler mechanisms.
3. **Cross-cloud replication** (e.g., GCS → AWS S3): rejected for v1.
   Adds cross-cloud complexity; Compliance organization within GCP
   provides equivalent defense at lower cost. May revisit if regulatory
   posture or insurance terms require multi-cloud.

## References

- Originating findings: R1 F-008, R3 S-030, R3 S-031, R3 S-034, R3 S-035
- ADR-0001 (Harness Foundation)
- ADR-0006 (Logging, Correlation, Error Taxonomy)
- BR-501..505 (Audit), BR-504 (Audit Log Integrity)
- ARD §"Audit" context
- R5 D-039 (DR drill program)
- R5 D-075 (Incident command structure)
