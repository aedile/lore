# ADR-0007: Container Orchestration — Cloud Run for v1

| Field | Value |
|-------|-------|
| **Status** | ACCEPTED |
| **Date** | 2026-04-29 |
| **Phase** | Phase 00 (synthesis pre-Phase 1) |
| **Originating findings** | R5 D-017 (container orchestration choice), R5 D-018 (service mesh decision), R5 D-019 (cold start mitigation), R5 D-020 (concurrency tuning), R5 D-021 (scaling policies), R2 F-139 (Verification API cold start) |

---

## Context

The ARD names Cloud Run as the runtime for stateless services. The decision
between Cloud Run and GKE (Google Kubernetes Engine) is consequential — it
shapes deployment, scaling, networking, debugging, cost, and operational
overhead. Without an explicit decision, future amendments are unclear; team
members may assume different runtimes; investments in Cloud Run-specific
tooling are unmotivated.

Trade-offs:

| Dimension | Cloud Run | GKE |
|---|---|---|
| Operational overhead | Low (Google manages cluster, scaling, patching) | High (cluster ops, node pools, upgrades) |
| Cold start | Real concern (1-2s for Python+FastAPI+deps) | Not present (instances run continuously) |
| Scaling | Per-request concurrency-based, autoscale-to-zero capable | Pod-based, HPA |
| Networking | Per-service ingress; service-to-service via internal HTTPS | Cluster-internal networking; service mesh option |
| Service mesh | Not natively integrated | Istio / Anthos Service Mesh available |
| Debugging | No SSH; logs and observability only | `kubectl exec`, port-forward, etc. |
| Cost | Pay-per-request (cheaper for low-traffic services) | Always-on cluster (cheaper at high concurrency) |
| GPU / specialized hardware | Limited | Full support |
| Multi-region | Per-service deployment to multiple regions | Cluster federation, more complex |

A separate question: service mesh (Istio / Anthos Service Mesh) on GKE
provides automated mTLS, retries, circuit breakers, traffic shaping. On
Cloud Run, mTLS is at the GFE (Google Front End) layer; retries and circuit
breakers are in application code (per ADR-0006).

## Decision

### 1. Cloud Run for v1, with explicit sunset clause

All stateless services run on Cloud Run for v1:

- Verification API (Cloud Run service, public-facing via load balancer)
- TokenizationService (Cloud Run service, internal)
- Format Adapter (Cloud Run job, scheduled)
- Mapping Engine (Cloud Run job, triggered)
- DQ Engine (Cloud Run job, triggered)
- Match Orchestrator (Cloud Run service, Pub/Sub push or pull)
- Splink Runner (Cloud Run job, batch)
- Deletion Executor (Cloud Run job, scheduled)
- Outbox Publisher (Cloud Run service, polling)
- Reviewer interface backend (Cloud Run service, internal)

Audit Consumer is Dataflow (streaming) — outside the Cloud Run scope by virtue
of being a streaming workload.

### 2. Sunset trigger

Re-evaluate to GKE if any of the following occurs:

- **More than 15 distinct services** with significant inter-service traffic
  (mesh value emerges)
- **Cross-cluster traffic patterns** require service mesh primitives
  (canary across regions; service-to-service mTLS with cert rotation
  policy)
- **Specialized hardware needs** (GPU for ML inference; TPU; dedicated
  RAM-bound workloads)
- **Cold start latency** exceeds tolerance for Verification (already a
  bound at 200ms p95 + latency floor; cold start mitigation per below
  must hold)

### 3. No service mesh for v1

Rationale: 7-10 services with modest inter-service complexity; mTLS
provided by GFE; retries and circuit breakers in application code via the
shared `shared/resilience.py` library (per ADR-0006). Service mesh adds:

- Operational complexity (mesh control plane, sidecars)
- Latency overhead (sidecar processing per call)
- New attack surface (mesh control plane)

Trade-off accepted: mesh-managed mTLS rotation is replaced by GFE-managed;
mesh-managed retry policy is replaced by application-level decorator.

### 4. Cold start mitigation per service

Per the framework in R5 D-019:

| Service | Min instances | Max instances | Concurrency | Rationale |
|---|---|---|---|---|
| Verification API | 2 | 100 | 20 | Latency-critical; HA + scale; tail-latency budget |
| TokenizationService | 2 | 20 | 30 | Verification depends on it; HA + KMS-bound |
| Match Orchestrator | 0 | 20 | 10 | Event-driven; CPU-bound Splink invocations |
| Format Adapter | 0 | 10 | 80 (default) | DAG-triggered; tolerates cold start |
| Mapping Engine | 0 | 10 | 80 | DAG-triggered |
| DQ Engine | 0 | 10 | 80 | DAG-triggered |
| Splink Runner | 0 | 5 | 1 | Batch CPU-bound |
| Outbox Publisher | 1 | 3 | 10 | Always running; modest concurrency |
| Deletion Executor | 0 | 2 | 1 | Scheduled, low volume |
| Reviewer Backend | 1 | 5 | 30 | Internal-facing; modest traffic |

Cost implication: minimum-instances cost is real. Verification API at
`min=2` plus TokenizationService at `min=2` is the largest cost contribution.
Acceptable given the latency contract (BR-404 / 200ms p95) — alternatives
(scale-to-zero) are not viable.

### 5. Per-service deployment strategy (per ADR-0008 / R5 D-006)

| Service | Strategy |
|---|---|
| Verification API | Canary (5% → 50% → 100% with auto-rollback on SLO breach) |
| TokenizationService | Blue/Green (single-point-criticality; explicit cutover) |
| Match Orchestrator, DQ, Mapping, Format Adapter | Rolling (Cloud Run default) |
| Splink Runner | Rolling |
| Audit Consumer (Dataflow) | Blue/Green (drain old; verify new; cutover) |
| Outbox Publisher | Rolling |

### 6. Container hardening

Per R3 S-056 and the harness Dockerfile pattern (Phase 00):

- Base image: `python:3.12-slim` for v1 (consider distroless after
  initial production hardening).
- Non-root user (UID 1000).
- Read-only root filesystem (with tmpfs for `/tmp` and any required
  scratch space).
- No shell in the runtime image (debugging via `gcloud run services logs`,
  not interactive).
- Capability drops: `--cap-drop=ALL`; only re-add specific capabilities
  if proven necessary (none expected for application services).
- Image signing via Cosign / Sigstore; Binary Authorization on Cloud Run
  enforces only signed images run.

### 7. Networking topology

- VPC connector for Cloud Run services that need VPC resources (AlloyDB,
  Cloud SQL Vault, Memorystore).
- Private Service Connect for managed services (R5 D-050) keeps traffic
  on Google's network.
- Cloud Armor on the public-facing Verification API load balancer (R3 S-054).
- VPC Service Controls perimeters as already specified in AD-017 (outer
  perimeter for prod project; inner perimeter around Vault).

## Consequences

### Positive

- **Low operational overhead**: Google manages the runtime; team focuses on
  application code.
- **Cost-efficient at low traffic**: scale-to-zero where appropriate (jobs,
  background services) eliminates idle cost.
- **Tight integration**: with other GCP services (Pub/Sub, KMS, IAM,
  BigQuery, Cloud Logging, Cloud Trace).
- **Per-service deploy independence**: each Cloud Run service deploys
  independently; no cluster-level coordination.

### Negative

- **Cold start cost**: Verification API + TokenizationService require
  `min=2` for HA; this is real cost ($N/month per service per instance).
- **No SSH-into-instance debugging**: forces strong observability discipline
  (per ADR-0006). Acceptable given the discipline.
- **Vendor lock-in**: Cloud Run-specific (vs. GKE which is
  Kubernetes-portable). Mitigated by container abstraction; significant
  refactor cost only on full vendor migration.

### Mitigations

- Cold start latency monitored per release (D-088 APM, D-066 deployment
  dashboards) — regression triggers rollback per ADR-0008.
- Container hardening enforces production-grade security defaults.
- Sunset clause is documented; evaluation criteria are concrete.

## Alternatives considered

1. **GKE Standard from v1**: rejected for current scope; operational overhead
   too high for the team size; the cluster ops + Kubernetes expertise burden
   is not justified by current service count.
2. **GKE Autopilot**: middle ground (Google manages nodes; team manages
   workloads). Rejected: cost vs. Cloud Run is similar at low concurrency;
   added Kubernetes complexity is not justified.
3. **App Engine Standard**: rejected. Older platform; less GCP-native
   integration than Cloud Run; less ecosystem momentum.
4. **Service mesh (Anthos Service Mesh on Cloud Run)**: rejected for v1.
   Reduces explicit application-level resilience patterns at cost of
   significant new operational surface.

## References

- Originating findings: R5 D-017, R5 D-018, R5 D-019, R5 D-020, R5 D-021,
  R2 F-139
- ADR-0001 (Harness Foundation)
- ADR-0006 (Logging, Correlation, Error Taxonomy — application-level
  resilience replaces mesh-level)
- ARD §"Deployment Topology"
- BR-404, BR-405 (Verification SLO)
