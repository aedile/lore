# ADR-0009: Verification API Latency Equalization

| Field | Value |
|-------|-------|
| **Status** | ACCEPTED |
| **Date** | 2026-04-29 |
| **Phase** | Phase 00 (synthesis pre-Phase 1) |
| **Originating findings** | R1 F-004 (Verification API timing side-channel), R3 S-074 (timing channel depth), R3 S-073 (verification ≠ authentication contract), R6 U-001 (verification failure UX) |

---

## Context

XR-003 and BR-401 collapse the Verification API external response set to
`{VERIFIED, NOT_VERIFIED}` to prevent existence-disclosure attacks via
response variation. The collapse defends against payload-content-based
inference; it does **not** defend against side-channel inference.

Three side channels remain:

1. **Timing side channel**: if `VERIFIED` (indexed lookup that succeeds)
   takes 50ms and `NOT_VERIFIED` (multi-tier lookup that exhausts to
   no-match) takes 200ms, an attacker can submit N claims, sort by latency,
   and recover existence information statistically.

2. **Response shape side channel**: HTTP/2 stream priorities, TCP packet
   sizes, response body length variations (even with identical fields,
   different tokenized internal IDs may produce different content lengths
   when serialized).

3. **Error path side channel**: rate-limit responses, friction-challenge
   triggers, lockout responses — each takes different time and produces
   different (HTTP-level) artifacts. An attacker correlating these to
   submitted claims learns which claim shape triggered which response,
   which leaks information about the underlying state machine.

ARD §"Verification API" mentions latency equalization as a one-line
commitment but does not engineer it. Without explicit engineering, the
side channels remain live.

A further question: BR-404 sets verification p95 at ≤ 200ms. Latency
equalization implies a **floor** below which responses are held; that
floor is necessarily ≥ the slowest legitimate path's p99. If the floor
exceeds 200ms, BR-404 must be reconciled.

## Decision

### 1. Latency floor — bounded, equalized response time

The Verification API enforces a **response latency floor**. Every response,
regardless of internal outcome (VERIFIED, NOT_VERIFIED, rate-limited,
friction-required, lockout), is held until the floor elapses from request
arrival.

- **Floor value**: `VERIFICATION_LATENCY_FLOOR_MS` (configuration parameter,
  initial value 250ms).
- **Floor source**: parameter set above the slowest legitimate path's p99
  latency. Initial sizing 250ms; tuned during Phase 1 load testing.
- **Implementation**: a coroutine-level `asyncio.sleep_until` or
  equivalent; the response is fully prepared internally then held until
  the floor elapses.

### 2. Reconciliation with BR-404

BR-404 currently sets p95 ≤ 200ms. With a floor of 250ms, the p95
becomes the floor. **BR-404 is amended** in synthesis: Verification
API p95 latency = `VERIFICATION_LATENCY_FLOOR_MS` (named parameter, set to
250ms initially).

This is a deliberate trade-off:
- Pre-decision: p95 ≤ 200ms, side channel exposed
- Post-decision: p95 = 250ms (precise; floor-anchored), side channel closed

The 50ms cost is the price of timing-equalization. Acceptable for
verification (member-facing experience tolerates 250ms easily; the
difference between 200ms and 250ms is imperceptible to users).

### 3. Response shape equalization — content-length padding

Every response body is padded to a fixed length:

```json
{
  "outcome": "VERIFIED" | "NOT_VERIFIED",
  "request_id": "<UUID>",
  "_padding": "<random-bytes-or-zeros-to-fixed-length>"
}
```

- **Fixed length**: `VERIFICATION_RESPONSE_BODY_BYTES` (configuration
  parameter, initial value 256 bytes).
- **Padding**: `_padding` field with random or fixed bytes to reach the
  fixed length. Random preferred (defense in depth against future
  body-content analysis).

Attackers see identical-length responses; TCP packet sizes for the
response body are equivalent.

### 4. Error path response equalization

All response paths produce the same shape and same latency:

| Internal state | External response | Floor enforced | Body shape |
|---|---|---|---|
| VERIFIED | `{outcome: VERIFIED}` | Yes (≥ floor) | Padded to fixed length |
| NOT_VERIFIED (no match) | `{outcome: NOT_VERIFIED}` | Yes | Padded |
| NOT_VERIFIED (TokenizationService unavailable — fail-closed per F-108) | `{outcome: NOT_VERIFIED}` | Yes | Padded |
| Rate-limited (BR-402 first/second/third failure threshold) | `{outcome: NOT_VERIFIED}` | Yes | Padded |
| Lockout (third failure within window) | `{outcome: NOT_VERIFIED}` | Yes | Padded |
| Friction-challenge required (BR-402 second failure) | HTTP 401 with friction-challenge token; padded | Yes | Padded |

Externally the rate-limited response is HTTP 401 (per ADR-0004 JWT
contract); a member who hit the rate limit sees the same HTTP/body shape
and same timing as a member who failed authentication.

Internally (in audit logs and metrics, never in responses), the path
distinction is preserved for monitoring and incident response.

### 5. Internal state distinguishability

The audit log records the precise internal state per request (per BR-401
and ADR-0006). Operations dashboards distinguish among the internal
outcomes. Externally, none of this is observable.

### 6. Verification ≠ authentication — explicit contract

Per R3 S-073: VERIFIED is a verification outcome (the submitted claim
matches an eligible identity); it is **not authentication of the
requester**. The Lore application must not treat VERIFIED as sufficient
for account creation; account creation requires additional independent
factors (email verification, identity proofing, etc.).

This contract is documented in the API specification and in the BAA
between Lore eligibility platform and Lore application teams (the
internal OLA per R7 E-015).

### 7. Test gates

Phase 1 exit criterion includes a timing-distribution test:

- Submit 10,000 representative claims across all internal-state
  combinations.
- Measure response latency distribution per internal-state.
- Assert: distributions are statistically indistinguishable above the
  floor (Kolmogorov-Smirnov test or equivalent at p ≥ 0.05).

This is a CI-gateable test (slow; runs nightly or per release); a
material regression prevents merge.

## Consequences

### Positive

- **Side channels closed**: timing, body length, response path —
  none leak existence information.
- **Predictable latency**: the floor anchors p95; ops know the
  budget exactly.
- **Test-gated**: regressions caught automatically.

### Negative

- **Latency cost**: ~50ms added vs. fast-path response. Member-imperceptible.
- **Bandwidth cost**: ~250 bytes per response (vs. shorter unpadded).
  Negligible at expected volume.
- **Engineering complexity**: latency floor implementation requires
  careful async handling (no blocking I/O in the held window).

### Mitigations

- The floor is a config parameter; tuned during load testing rather than
  guessed.
- The held time is usable for low-priority background work (e.g., async
  audit log emission completion) — not wasted.
- Test gates ensure the property is verified continuously, not assumed.

## Alternatives considered

1. **No latency equalization (XR-003 collapse alone)**: rejected. The
   timing channel is a real attack pattern in healthcare-PII enumeration.
   The architecture's privacy commitment is meaningful only if side
   channels are closed.
2. **Constant-time per-request, no floor**: rejected. Forcing every
   computation to take exactly N ms is more invasive in the codebase
   (every code path must be constant-time-aware) than holding the
   response. The floor pattern is well-understood and minimally invasive.
3. **Differential privacy noise**: occasionally return NOT_VERIFIED for
   actual members and VERIFIED for non-members at low rate to confuse
   statistical analysis. Rejected: violates BR-401 correctness; introduces
   business-outcome errors as a security mechanism, which is the wrong
   trade.
4. **Lower floor (e.g., 150ms)**: rejected. p99 of slowest legitimate
   path needs measurement; 150ms may be too aggressive given AlloyDB +
   TokenizationService + audit emission. 250ms is conservative; tunable.

## References

- Originating findings: R1 F-004, R3 S-073, R3 S-074, R6 U-001
- ADR-0001 (Harness Foundation)
- ADR-0004 (JWT Verification Contract)
- ADR-0006 (Logging, Correlation, Error Taxonomy)
- BR-401, BR-402, BR-403, BR-404, BR-405 (Verification API)
- XR-003 (Privacy-Preserving Collapse)
- R7 E-015 (Internal SLA / OLA between teams)
