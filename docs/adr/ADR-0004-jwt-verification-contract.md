# ADR-0004: JWT Verification Contract for Public Verification API

| Field | Value |
|-------|-------|
| **Status** | ACCEPTED |
| **Date** | 2026-04-29 |
| **Phase** | Phase 00 (synthesis pre-Phase 1) |
| **Originating findings** | R3 S-005 (JWT specifics), R3 S-012 (session management), R3 S-006 (TLS configuration) |

---

## Context

The Verification API is the only public-facing surface of the platform. The
ARD specifies "mTLS at the load balancer plus a short-lived JWT issued by the
Lore application's auth service. The Verification API validates the JWT and
authorizes by client_id." This is correct in shape but underspecified in
detail.

JWT is the most-misused web auth mechanism. Common attacks against
underspecified JWT implementations:

- `alg: none` accepted (no signature validation)
- Algorithm confusion (RS256 token treated as HS256 with public key as secret)
- Missing audience validation (token from another service accepted)
- Missing issuer validation
- Missing expiry (token valid forever)
- Missing replay defense (`jti` claim tracking)
- Insufficient TTL (long compromise window)
- Public key rotation gaps (revoked key still trusted)

Each is a real defect pattern observed in production systems. A binding
specification prevents them.

## Decision

The Verification API enforces the following JWT validation contract.

### 1. Algorithm

- **Required**: `RS256` (asymmetric, public-key-verified).
- **Forbidden**: `none`, `HS256`, `HS384`, `HS512` (symmetric algorithms).
- **Verification logic**: explicitly check the `alg` header against the
  required value; reject the token if it does not match. Do **not** rely on
  the JWT library's default to handle this.

### 2. Required claims

| Claim | Required | Validation |
|---|---|---|
| `iss` | Yes | Must equal the configured Lore application auth service issuer URL (`JWT_ISSUER` env var) |
| `aud` | Yes | Must equal `lore-eligibility-verification` (the audience configured for this API) |
| `exp` | Yes | Must be present; must be in the future at the time of validation |
| `iat` | Yes | Must be present; must be ≤ `exp` |
| `jti` | Yes | Must be unique within a 24-hour replay window |
| `sub` | Yes | The Lore application client identifier; must be in the configured allow-list |
| `nbf` | Optional | If present, must be ≤ now |

Additional claims (specific to Lore application's auth model) are accepted
but not validated by the Verification API.

### 3. Public key retrieval — JWKS

- **Source**: JWKS endpoint at the issuer URL (e.g.,
  `https://auth.lore.app/.well-known/jwks.json`).
- **Cache TTL**: 1 hour (configurable via `JWT_JWKS_CACHE_TTL_SECONDS`).
- **Refresh**: cache miss + token's `kid` not in cache triggers JWKS refresh.
- **`kid` enforcement**: the JWT's `kid` header is required; the public key
  must match the `kid`. Tokens without a `kid` are rejected.

### 4. TTL bounds

- **Maximum acceptable TTL**: 5 minutes (the configured `JWT_TTL_MAX_SECONDS`).
- The Verification API rejects tokens whose `exp - iat > JWT_TTL_MAX_SECONDS`.
- The Lore application's auth service is configured to issue tokens with
  TTL ≤ 5 minutes.

### 5. Replay defense

- **`jti` cache**: 24-hour TTL keyed by `jti`. Cache backed by Cloud
  Memorystore (Redis) per BR-402's rate-limit cache infrastructure.
- **First sighting**: token is added to the cache; request proceeds.
- **Repeated sighting**: token is rejected as a replay attempt; an audit
  event of class `JWT_REPLAY_REJECTED` is emitted.

### 6. Authorization (post-authentication)

- The `sub` claim identifies the Lore application client.
- The Verification API maintains an allow-list of expected client identifiers.
- Tokens whose `sub` is not in the allow-list are rejected with HTTP 401 (not
  HTTP 403, to avoid leaking client-list state to attackers via differential
  responses).

### 7. Failure mode disclosure

Per BR-401 and XR-003, the public response set is `{VERIFIED, NOT_VERIFIED}`.
JWT validation failures must not produce response variations:

- JWT validation failure → HTTP 401 with empty body.
- The HTTP 401 is differentiable from "valid JWT but NOT_VERIFIED" externally
  by status code, which is acceptable per the public-surface privacy model
  (caller knows they failed authentication; the member's verification state
  is not disclosed).

### 8. TLS at the load balancer (related but distinct)

- **TLS minimum**: TLS 1.2.
- **Preferred**: TLS 1.3.
- **Cipher suites**: AEAD-only allow-list (AES-GCM, ChaCha20-Poly1305).
- **Forward secrecy**: required (ECDHE).
- **mTLS**: client certificate validation at the load balancer; certificates
  managed by Google Certificate Manager; revocation via OCSP stapling.

This applies to all callers, including the Lore application.

## Consequences

### Positive

- **Defends against the most common JWT attack patterns.**
- **Replay window is bounded** by both `jti` tracking and short TTL.
- **Public key rotation works** through JWKS with `kid` discipline.
- **Audience and issuer validation** prevents tokens from other services
  from working here.

### Negative

- **Memorystore dependency** for `jti` cache. If Memorystore is unavailable,
  the API must decide: (a) fail-closed and reject all tokens (high
  availability impact), or (b) fail-open and accept tokens without replay
  defense (security-deficient temporarily).
  - **Decision**: fail-closed. Memorystore HA tier (R3 S-126) is required.
  - **Effect**: Memorystore outage propagates to Verification API outage.
    Acceptable given Verification's role and the alternative.

- **JWKS dependency** on Lore application's auth service. JWKS endpoint
  outage during a key rotation could cause valid tokens to be rejected.
  - **Mitigation**: extended cache TTL (1 hour) tolerates short JWKS
    outages; on extended outage, alert + fail-closed.

### Mitigations

- All JWT validation logic is centralized in `bootstrapper/auth.py`; no
  per-route reimplementation.
- Mutation testing on `bootstrapper/auth.py` per ADR-0001 / Constitution
  Priority 4.
- Attack tests cover every rejection path (algorithm confusion, missing
  claims, replay, expired, future-dated, etc.).
- Integration tests against a synthetic JWKS endpoint validate refresh
  behavior.

## Alternatives considered

1. **HS256 (symmetric)**: rejected. Shared secret with the Lore application
   creates a single point of compromise; secret distribution is fragile.
2. **OAuth 2.0 / OIDC introspection**: alternative model where each request
   triggers an introspection call to the auth service. Rejected for the
   Verification API's hot path: introduces synchronous dependency on
   introspection endpoint per request, harming latency (BR-404).
   May be acceptable for less-hot internal APIs in future.
3. **Mutual TLS only (no JWT)**: rejected. mTLS authenticates the calling
   service but not the calling user/session within that service. JWT carries
   the per-request Lore application identity claim.
4. **Longer TTL (e.g., 1 hour)**: rejected. Short TTL bounds compromise
   window; refresh frequency is acceptable for Lore application's
   verification flow.

## References

- Originating findings: R3 S-005, R3 S-012, R3 S-006
- BR-401 (External State Set), XR-003 (Privacy-Preserving Collapse)
- BR-402 (Rate-limit cache infrastructure), BR-405 (availability target)
- ARD §"Verification" context, §"API Contracts"
- R3 S-126 (Memorystore HA tier requirement)
- R5 D-051 (secret rotation automation)
