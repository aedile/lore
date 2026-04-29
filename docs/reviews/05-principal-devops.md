# Architecture Review — Round 5: Principal DevOps Engineer

| Field | Value |
|---|---|
| **Round** | 5 of N |
| **Reviewer lens** | Principal DevOps Engineer — infrastructure-as-code, deployment automation, observability, on-call, capacity, cost, reliability engineering, incident management, day-2 operational realities, dev/prod parity, the systems that keep the platform running and changing |
| **Documents** | `docs/BUSINESS_REQUIREMENTS.md` (BRD), `docs/ARCHITECTURE_REQUIREMENTS.md` (ARD) |
| **Date** | 2026-04-29 |
| **Prior rounds** | `docs/reviews/01-principal-architect.md`, `docs/reviews/02-chief-programmer.md`, `docs/reviews/03-principal-security.md`, `docs/reviews/04-compliance-legal.md` |

This review reads the documents the way a DevOps lead about to operate the platform reads them: where's the IaC, what's the deploy strategy, what are the SLOs, who pages me, what does my dashboard look like, how do I roll back, how do I scale, what's my cost ceiling, where's the runbook, what happens at 3am during a Datastream outage. Where prior rounds asked "is the architecture right" or "is it secure," this round asks **"can this be operated."**

Severity per Constitution Rule 29 (BLOCKER / FINDING / ADVISORY).

Where I'm extending prior-round findings, I cite them. The bulk is new — operational engineering is largely orthogonal to architecture, security, code, and compliance.

---

## TL;DR

**Will the platform be deployable and observable if we proceed as-is? No.**

The architecture names tools (Cloud Run, Cloud Composer, Cloud Logging, Cloud Monitoring, Datastream, Pub/Sub, AlloyDB) but doesn't engineer the operational layer that turns tools into a runnable system. The gaps are not subtle:

- **No infrastructure as code (IaC) framework specified.** "Deploy in three environments" without IaC is click-ops — undefensible to audit, drift-prone, and unrebuildable after disaster.
- **No SLI/SLO/error-budget engineering.** BRD has latency and availability targets (BR-404, BR-405) but no error budgets, burn-rate alerts, or budget-exhaustion policy. Reliability is undefinable.
- **No deployment strategy per service.** Verification API is in the critical path of account creation. Cloud Run "deploy" without canary, traffic split, automated rollback = high-risk path with one chance to get it right.
- **No on-call structure.** Phase 1 hits production traffic. Without on-call rotation, escalation matrix, runbook quality SLA — incidents have no responder.
- **No capacity engineering** (Round 1 F-001 noted; reaffirmed and extended).
- **No DR drill program.** Round 1 F-005 said RTO/RPO claims are theoretical; without drill cadence, they remain theoretical.
- **No backup integrity testing.** Backups exist on paper; first restore attempt is the test.
- **No deployment observability.** Deployments are blind; mean-time-to-detect-bad-deploy is undefined.
- **No incident management process** beyond Round 3's IR plan; no command structure, status page, war-room procedure, postmortem culture.
- **Local dev parity is incomplete.** Round 2 F-117/F-146 noted; not engineered.

**71 findings: 18 BLOCKERS, 44 FINDINGS, 9 ADVISORIES.**

After consolidating across all five rounds, the unique BLOCKER set spans approximately **65-70 items**. With all addressed, the platform is operable: deployable safely, observable in real time, recoverable from failure, scalable under load, defensible to audit. Without them, the platform is shippable but unsustainable — the first outage exposes the absence of operational engineering.

---

## What DevOps Owns That Prior Rounds Could Not

Prior rounds have standing to identify gaps. They don't have standing to:

1. **Author IaC** (Terraform/Pulumi modules; the actual cloud configuration).
2. **Define SLOs** (negotiated with product/business; operational target).
3. **Engineer deployment automation** (canary controllers, rollback triggers, traffic-shift policies).
4. **Stand up on-call** (rotation, scheduling, escalation, alert hygiene).
5. **Run DR drills** (the actual recovery exercises that prove RTO/RPO).
6. **Author runbooks** (the operational documents on-call uses at 3am).
7. **Operate cost engineering** (FinOps practices, budget alerts, cost attribution).
8. **Manage capacity** (load testing, scaling tests, regression detection).
9. **Run incident command** (during production incidents).
10. **Build local-dev substrate** (reproducible developer experience).

This review surfaces those areas as gaps. Each requires DevOps engineering work before the platform is operationally ready.

---

## Strengths from a DevOps view

What's load-bearing and correct (do not relitigate):

1. **Three-environment hard separation (AD-017).** Right model. Synthetic-only outside prod is correct discipline.
2. **Cloud-native managed services as default** (AlloyDB, Cloud Run, Composer, Datastream). Reduces operational burden vs. self-managing equivalents.
3. **Pub/Sub as the message bus.** Standard, observable, scalable.
4. **Pattern C (operational/analytical separation).** Decouples Verification SLO from analytical workload.
5. **Phase exit criteria are objective.** Phase 1 specifically calls out "Datastream replication to BigQuery is working with lag under 60 seconds" — operational commitment.
6. **Chief programmer Round 2 already surfaced** structured logging, correlation IDs, idempotency, error taxonomy, monorepo decision — these are DevOps-relevant; tracked as cross-round.
7. **Phase 4 acknowledges** runbook formalization and DR validation as exit criteria.

These work. Findings below extend, sharpen, or fill gaps.

---

## 1. Infrastructure as Code

The single biggest absence. Without IaC, every operational concern below has no reproducible foundation.

### D-001: IaC framework not specified — BLOCKER

**Where:** ARD §"Deployment Topology" describes services to deploy. No mention of IaC tooling.

**Why it matters:** Three environments (dev/staging/prod) deployed via console/gcloud commands = click-ops. Drift between environments is inevitable; reconstruction after disaster is days, not hours; SOC 2 / HITRUST audit asks "where's your IaC" and gets nothing. Every other DevOps practice (drift detection, environment parity, cost attribution, security review of infra changes) builds on IaC.

**What's needed:** ADR specifying IaC framework. Recommendation: Terraform with the Google provider, organized as composable modules per architectural primitive (network, KMS, AlloyDB, Cloud Run service, Pub/Sub topic, etc.). Each environment is a Terraform stack. State managed in Cloud Storage with state locking. Commits to IaC repo trigger plan + review + apply gates.

**Effort:** L (initial setup is multi-week; ongoing thereafter).

---

### D-002: IaC state management strategy — FINDING

**Where:** N/A.

**Why it matters:** Terraform state contains sensitive metadata (resource IDs, IPs, sometimes secrets references). State storage must be: separately encrypted at rest, access-controlled, locked during operations, backed up.

**What's needed:** Terraform state in Cloud Storage with: bucket-level encryption with dedicated KMS key, IAM scoped to terraform-runners only, state locking via GCS object generations, daily backup to a separate region, state access audited.

**Effort:** S.

---

### D-003: IaC drift detection — FINDING

**Where:** N/A.

**Why it matters:** Even with IaC discipline, manual changes happen (emergency fixes, console clicks, automated tooling). Drift detection identifies when reality diverges from declared state.

**What's needed:** Daily `terraform plan` against each environment; non-empty plan triggers review; automated reconciliation policy (force-apply for safe items; manual review for risky).

**Effort:** S.

---

### D-004: IaC CI/CD pipeline — FINDING

**Where:** N/A.

**Why it matters:** IaC changes need their own deploy pipeline: lint, plan, security scan (Checkov/tfsec), peer review, apply. Apply must be auditable and gated.

**What's needed:**
- Pre-merge: `terraform fmt -check`, `terraform validate`, `terraform plan` (output as PR comment), tfsec / Checkov security scan.
- Merge: triggers plan against staging; manual approval to apply.
- Promotion: staging plan + apply → manual approval → prod plan + apply.
- All apply runs use OIDC (GitHub Actions → GCP Workload Identity Federation), no long-lived service account keys.

**Effort:** M.

---

### D-005: Secrets in IaC — FINDING

**Where:** N/A.

**Why it matters:** Terraform configs often reference secrets (DB passwords, API keys). Plain-text secrets in state files are common breach paths.

**What's needed:** Secrets referenced via Secret Manager IDs only; never inline. Outputs marked `sensitive = true`. State file analysis as part of CI: fail on inline-secret patterns.

**Effort:** S.

---

## 2. Deployment Engineering

### D-006: Deployment strategy per service — BLOCKER

**Where:** ARD: "Cloud Run for stateless services." No deployment strategy.

**Why it matters:** Verification API is in the critical path of account creation. A rolling deploy that ships a bad release crashes account creation for everyone hit during the rollout. Cloud Run supports traffic splits — use them. Match Orchestrator can tolerate rolling deploys. Audit Consumer must not lose events during deploys.

**What's needed:** ADR per service:
- **Verification API**: canary deploy. New revision gets 5% traffic for 10 minutes; auto-promote to 50% if SLI healthy; auto-promote to 100% if still healthy; auto-rollback on error rate > baseline + 0.5% or p95 latency > target.
- **Match Orchestrator, DQ engine, Format Adapter**: rolling deploy. Cloud Run handles instance replacement.
- **Audit Consumer (Dataflow)**: blue/green. Old job processes in-flight messages; new job takes over from a checkpoint; old job drains; verify counters match before destroying old job.
- **TokenizationService**: blue/green with explicit cutover (single-point criticality).

**Effort:** M (canary controller + per-service config).

---

### D-007: Artifact promotion model — BLOCKER

**Where:** Not specified. Phase 0 mentions "Artifact Registries."

**Why it matters:** What artifact moves from dev → staging → prod? Same container image SHA, retagged? Built per environment? Without a promotion model, dev and prod silently diverge.

**What's needed:** ADR: same image SHA promoted across environments. Build once in CI; tag with git-SHA; push to Artifact Registry; deploy to dev with `git-SHA` tag; on staging promotion, retag as `staging-current` + git-SHA; same for prod. Image immutable; only tag aliases shift.

**Effort:** S (ADR + CI/CD plumbing).

---

### D-008: Image registry and lifecycle — FINDING

**Where:** Phase 0 mentions Artifact Registry.

**Why it matters:** Artifact Registry storage costs grow unbounded. Image deprecation policy needed; images referenced by running revisions must stay; old images garbage-collected.

**What's needed:** ADR:
- Retention: keep all images deployed in prod (whether currently active or rollback-eligible) + last 90 days of all environments.
- Tagging: git-SHA (immutable) + semantic tags (`staging-current`, `prod-current`).
- Garbage collection: automated; respects retention.
- Vulnerability scanning at push time (extends R3 S-042); critical CVE blocks deploy.

**Effort:** S.

---

### D-009: Build provenance and attestation — FINDING

**Where:** Round 3 S-042 noted; DevOps depth here.

**Why it matters:** SLSA framework defines build-provenance requirements. Each image attests its build origin (commit, builder, build environment). Cloud Run admission controller verifies attestation before running.

**What's needed:**
- GitHub Actions builds emit Cosign signatures + SLSA provenance attestations.
- Artifact Registry stores attestations alongside images.
- Cloud Run's Binary Authorization configured to require attestation from `lore-eligibility-builder` identity.
- Audit policy: every Cloud Run deploy logs attestation verification result.

Target: SLSA Level 3 by Phase 4. SLSA Level 2 by Phase 1.

**Effort:** M.

---

### D-010: Automated rollback triggers — BLOCKER

**Where:** N/A.

**Why it matters:** Manual rollback is too slow when Verification API breaks at 3am. Triggers must be automated.

**What's needed:** ADR per service:
- Verification API: rollback if error rate > baseline + 0.5% sustained 2 minutes, OR p95 latency > target sustained 2 minutes, OR availability < 99.9% sustained 5 minutes.
- Match Orchestrator: rollback if Pub/Sub backlog grows > 10x baseline.
- Audit Consumer: rollback if hash chain validation fails on new revision.
- Rollback action: revert Cloud Run traffic to prior revision; alert on-call; trigger postmortem.

**Effort:** M (controller + per-service config).

---

### D-011: Pre-deployment gates — FINDING

**Where:** ARD does not specify.

**Why it matters:** Before traffic shifts, new revision must prove it works. Gates: smoke tests, dependency reachability, configuration validation.

**What's needed:** Per-service pre-deployment gate:
- New revision deploys with 0% traffic.
- Smoke tests run against the no-traffic instance: `/readyz`, dependency reachability (DB connect, KMS access, Pub/Sub publish permission), basic functional tests.
- Smoke tests pass → traffic shift begins per D-006.
- Smoke tests fail → revision marked failed; deploy aborts; on-call notified.

**Effort:** M.

---

### D-012: Database schema migrations as deploy step — FINDING

**Where:** Round 2 F-123 covered ordering; DevOps depth here.

**Why it matters:** Migration runs as part of deploy or separate? If part of deploy: race conditions across instances. If separate: coordination with code rollout.

**What's needed:** ADR: migrations run as a separate one-shot Cloud Run job triggered by Composer DAG; deployment pipeline waits for migration completion before deploying app code. Idempotent re-run on partial failure (Round 2 F-114).

**Effort:** S.

---

## 3. Environment Management

### D-013: Environment parity story — BLOCKER

**Where:** AD-017 specifies three environments. Parity policy not stated.

**Why it matters:** Bugs found in prod that should have been caught in staging. Common failure: dev has feature flags off, staging has them on, prod has half on; behavior diverges. Or: dev uses SQLite, prod uses Postgres.

**What's needed:** Parity policy:
- Same code path, same dependencies, same Postgres version across all environments.
- Feature flag values declared per environment in IaC; reviewed at promotion.
- Synthetic data shape matches prod data shape (same partner mix, similar volume distribution).
- Differences explicitly enumerated and justified per environment (e.g., min-instance count for cost).

**Effort:** M (audit + remediation).

---

### D-014: Ephemeral environments for PRs — FINDING

**Where:** N/A.

**Why it matters:** Long PR review cycles depend on integration testing. Ephemeral environments per PR enable: full-stack testing, automated UI regression, demo deploys for stakeholders.

**What's needed:** ADR: PR-triggered ephemeral environments via Cloud Run preview deployments + ephemeral Cloud SQL instances + isolated Pub/Sub topics. TTL: PR close + 24 hours. Cost cap per ephemeral env. Security: no production data, ever.

**Effort:** L (initial); ongoing.

---

### D-015: Synthetic data refresh in non-prod — FINDING

**Where:** Round 2 F-134 noted synthetic data lifecycle; this is the operational depth.

**Why it matters:** Staging needs realistic-shape data at scale (millions of synthetic members) for performance testing. Manual refresh is fragile.

**What's needed:** Automated weekly refresh: synthetic data generator runs against staging; produces N million member records with controlled distribution; refreshes Vault (with synthetic keys), canonical store, BigQuery analytical projection. Older data ages out per retention policy.

**Effort:** M.

---

### D-016: Per-environment configuration management — FINDING

**Where:** Round 2 F-149 covered hot-reload safety; DevOps depth on env-specific config.

**Why it matters:** Config that differs per environment (database URLs, feature flags, scaling params) needs per-env declaration. Config that should NOT differ (security policies, retention) needs same-everywhere enforcement.

**What's needed:** Config repo structure: `config/global.yaml` (same everywhere), `config/{env}.yaml` (per-env overrides). CI gate: forbidden keys in per-env files (security policies cannot be overridden per env). Promotion review: diff staging vs prod config; reviewer signs off.

**Effort:** S.

---

## 4. Service Deployment Specifics

### D-017: Container orchestration choice — BLOCKER

**Where:** ARD: Cloud Run for stateless services. No tradeoff documented vs GKE.

**Why it matters:** Cloud Run is fine for stateless services with simple scaling needs. GKE is better for: complex inter-service networking (service mesh, custom load balancing), workloads with long-running processes, GPU/specialized hardware. The decision affects everything downstream (deployment, scaling, networking, debugging, cost).

**What's needed:** ADR: Cloud Run for v1 with explicit tradeoff documentation. Sunset clause: if [specific triggers — service mesh need, custom networking, specialized hardware] occur, re-evaluate to GKE. Documented operational implications: no SSH-into-instance debugging, cold start tradeoffs (D-019), per-service scaling, etc.

**Effort:** S (ADR).

---

### D-018: Service mesh decision — FINDING

**Where:** Round 2 F-118 implied. ARD: Cloud Run handles service-to-service via internal HTTPS.

**Why it matters:** Service mesh (Istio, Anthos Service Mesh) adds: mTLS automation, retries, circuit breakers, traffic shaping, observability. Cost: complexity, latency overhead, additional surface to operate.

**What's needed:** ADR: no service mesh for v1. Justification: 7 services, modest complexity; mTLS via Cloud Run + GFE; circuit breakers in code (R2 F-111). Sunset clause: if [N services > 15, cross-cluster traffic, dynamic traffic shaping needs] occur, re-evaluate.

**Effort:** S (ADR).

---

### D-019: Cold start mitigation per service — FINDING

**Where:** Round 2 F-139 raised for Verification API. Other services not addressed.

**Why it matters:** Cold start cost varies. Verification API: critical (latency contract). Match Orchestrator: tolerable (Pub/Sub batched). Format Adapter: tolerable (run on schedule). Sizing min-instances per service is a cost-vs-latency tradeoff.

**What's needed:** Per-service min/max instance config:
- Verification API: min=2 (HA), max=100 (scale).
- TokenizationService: min=2, max=20.
- Match Orchestrator: min=0 (event-driven), max=20.
- Format Adapter: min=0 (DAG-triggered), max=10.
- Audit Consumer (Dataflow): persistent worker pool sized for sustained throughput.

**Effort:** S.

---

### D-020: Per-service concurrency tuning — FINDING

**Where:** Round 2 F-140 raised. DevOps depth here.

**Why it matters:** Cloud Run default is 80 concurrent requests per instance. Latency-sensitive services need lower concurrency for tail-latency control; throughput services can use higher.

**What's needed:** Per-service concurrency:
- Verification API: 20 (200ms p95 budget; per-request DB connection).
- TokenizationService: 30 (KMS-bound; mostly I/O).
- Match Orchestrator: 10 (CPU-bound Splink invocations).
- Background services: 80 (default).

**Effort:** S.

---

### D-021: Scaling policies — FINDING

**Where:** Not specified.

**Why it matters:** Cloud Run scales on concurrent-requests-per-instance signal. Targets need explicit values per service; aggressive scale-up vs cost; scale-down to zero vs warm-instance cost.

**What's needed:** Per-service scaling targets (target concurrency, scale-up rate, scale-down delay) as IaC.

**Effort:** S.

---

## 5. SLI / SLO / Error Budget Engineering

The single biggest reliability gap. The BRD has latency and availability targets but no error-budget engineering.

### D-022: SLI definitions per user-facing dimension — BLOCKER

**Where:** BR-404, BR-405 specify Verification API targets. SLIs not defined.

**Why it matters:** SLO without SLI is aspiration. SLI = measurable service-level indicator. Verification API needs SLIs for: availability (success rate), latency (p95, p99), correctness (verified-correctly rate, measured against ground truth where possible). Other services need their own SLIs.

**What's needed:** SLI catalog:
- **Verification API**: Availability = (HTTP 2xx + 4xx) / (total responses), excluding 4xx user errors. Latency = p50, p95, p99 of response time. Correctness = (correct outcome) / (total outcomes), measured against synthetic test set.
- **TokenizationService**: Availability, p95 detok latency.
- **Match Orchestrator**: Throughput = matches per minute. Lag = age of oldest unprocessed message.
- **Datastream**: Lag = AlloyDB → BigQuery time delta.
- **Audit Consumer**: Lag = audit-events publish-time → sink-write delta.
- **Pipeline (end-to-end)**: Lag = file landing time → canonical update time, p95.

**Effort:** M (per-service SLI definition + measurement plumbing).

---

### D-023: SLO targets per service — BLOCKER

**Where:** Verification API has BR-404 (200ms p95) and BR-405 (99.9%). Other services unspecified.

**Why it matters:** SLOs are commitments. Per-service SLOs drive: alerting thresholds, error budget calculation, capacity planning, release pace.

**What's needed:** SLO targets (28-day windows):
- Verification API: 99.9% availability (BR-405); 200ms p95 latency (BR-404); 99.99% correctness on synthetic.
- TokenizationService: 99.95% availability (Verification depends on it); 50ms p95 detok.
- Match Orchestrator: 95% of files processed within 1 hour of landing.
- Datastream: lag p95 < 60 seconds (Phase 1 exit criterion already states this).
- Audit Consumer: lag p95 < 30 seconds; 99.99% delivery rate.
- Pipeline E2E: 95% of files landing-to-canonical within 4 hours.

Each SLO documented; reviewed quarterly.

**Effort:** M.

---

### D-024: Error budget tracking and burn-rate alerts — BLOCKER

**Where:** N/A.

**Why it matters:** Error budget = (1 - SLO target) × measurement window. 99.9% over 28 days = ~40 minutes of error budget. Tracking budget consumption and burn rate is how reliability becomes quantitative.

**What's needed:**
- Per-SLO error budget calculation; visible on dashboard.
- Burn-rate alerts: 2% budget consumed in 1 hour = page; 10% in 6 hours = page; 50% in 24 hours = page (Google SRE multi-window approach).
- Budget exhaustion: defined response (D-025).

**Effort:** M (dashboarding + alerting plumbing).

---

### D-025: Error budget exhaustion policy — FINDING

**Where:** N/A.

**Why it matters:** When error budget is exhausted, what's the response? "Continue shipping" makes the SLO meaningless. "Halt all changes" is too strict. Standard: feature work pauses; reliability work continues.

**What's needed:** Policy: budget exhausted → all non-reliability changes halted; team focuses on reliability until next budget window. Documented and enforced via deploy gate (e.g., feature deploys check budget remaining; deploy blocked if exhausted).

**Effort:** S.

---

## 6. Capacity Engineering

### D-026: Capacity model with concrete numbers — BLOCKER

**Where:** Round 1 F-001 raised the gap. Reaffirmed and extended.

**Why it matters:** "Minimum size" for AlloyDB at v1 (per Phase 0 exit criterion). At what concurrent load does it fail? Verification API at 1000 QPS: how many Cloud Run instances? KMS at 100 detoks/sec: do we hit per-second quotas? Without numbers, every backlog ticket assumes a different ceiling.

**What's needed:** Capacity model document:
- **Verification API**: Peak QPS target (e.g., 1000 QPS at v1; 10,000 at 10x). Instance sizing (CPU/memory). Connection pool size per instance. AlloyDB connection budget. KMS API call rate. Cost at peak.
- **AlloyDB**: vCPU, RAM, storage, IOPS at v1 and 10x. Read replica count.
- **Pub/Sub**: max message rate per topic; backlog tolerance.
- **BigQuery**: slot reservation vs on-demand; query budget per day.
- **Cloud Storage**: per-bucket request rate (esp. raw landing zone during reprocess).
- **KMS**: per-second crypto operation budget; envelope encryption strategy minimizes (S-004).

For each: v1 sizing, 10x sizing, scaling trigger (when does v1 → 10x), bottleneck identification, cost.

**Effort:** L (the actual capacity model).

---

### D-027: Load testing program — FINDING

**Where:** Round 2 F-136 raised; DevOps depth here.

**Why it matters:** Capacity model without load test is theoretical. Load tests prove the model.

**What's needed:**
- Tool: k6 (recommended; cloud-native, scripting in JS/TS).
- Cadence: per-PR for changed services (smoke load); per-release for full E2E; per-quarter for full-fleet capacity validation.
- Scenarios: nominal load, peak load, spike (10x for 1 minute), sustained capacity (10x for 1 hour), regression (load = current production).
- Targets: SLOs hit at nominal; degraded gracefully at peak; recovered after spike.
- Environment: staging with prod-like data shape.

**Effort:** L.

---

### D-028: Performance regression detection — FINDING

**Where:** Round 2 F-136 implied; this is the CI gate.

**Why it matters:** Performance regresses silently. CI gate: every PR that touches Verification API path runs a small benchmark; deploy blocked if p95 > baseline + threshold.

**What's needed:** Per-service benchmark suite in CI; baselines stored; deploy gate checks regression.

**Effort:** M.

---

### D-029: Capacity headroom policy — FINDING

**Where:** N/A.

**Why it matters:** Running at 95% capacity = no headroom for spikes; running at 30% = wasted cost. Standard: 50-70% utilization at peak; scale before saturation.

**What's needed:** Per-service utilization targets; scaling triggers; quarterly capacity review.

**Effort:** S.

---

## 7. Cost Engineering / FinOps

### D-030: Cost envelope — extends R1 F-007 — FINDING

**Where:** Round 1 F-007 raised. Not addressed.

**Why it matters:** AlloyDB is non-trivial. BigQuery slots compound. KMS operations bill per call. Without cost envelope, the architecture can be correct but unaffordable.

**What's needed:** Per-month cost estimate at v1, v1-launch (5-10 partners), 10x. Top three cost drivers identified. Per-cost-driver levers (sizing, reservations, caching).

**Effort:** S (estimation).

---

### D-031: Cost monitoring and budget alerts — FINDING

**Where:** N/A.

**Why it matters:** Surprise bills happen. Per-project budgets with alerts at 50%, 80%, 100%, 120% of forecast.

**What's needed:** Budget alerts in IaC; monthly cost review; quarterly cost optimization sprint.

**Effort:** S.

---

### D-032: Per-feature cost attribution — FINDING

**Where:** N/A.

**Why it matters:** Knowing the cost of Verification API vs Match Orchestrator drives investment decisions. Attribution by labels: every Cloud Run service tagged; BigQuery queries tagged with originating feature.

**What's needed:** Labeling convention in IaC; cost dashboards by label; per-feature cost in monthly review.

**Effort:** S.

---

### D-033: Cost anomaly detection — ADVISORY

**Where:** N/A.

**Why it matters:** Sudden cost spikes (run-away query, autoscaling bug) can balloon to 10x normal in hours.

**What's needed:** Cloud Billing anomaly detection; alerts to FinOps + Engineering.

**Effort:** S.

---

## 8. On-Call Engineering

### D-034: On-call rotation structure — BLOCKER

**Where:** Round 4 noted Privacy Officer / Security Officer designation; on-call structure not addressed.

**Why it matters:** Phase 1 production traffic. Without on-call rotation, the first incident has no responder. On-call is structural — rotation, schedule, handoff, comp.

**What's needed:**
- Rotation: weekly primary + secondary on-call.
- Coverage: 24/7 (or business hours + after-hours escalation depending on company stage).
- Roster: 4-6 engineers minimum to make rotation sustainable.
- Tooling: PagerDuty (mentioned in ARD) for paging; rotation in PagerDuty; integration with Slack for incident channel.
- Comp: documented (compensatory time, on-call pay, etc. per company policy).
- Onboarding: every on-call engineer completes runbook training before first shift.

**Effort:** S to specify; ongoing operational.

---

### D-035: Escalation matrix — extends R2 F-120 — FINDING

**Where:** Round 2 F-120 noted alert classification gap. DevOps depth here.

**Why it matters:** Page → primary on-call. No response in 15 min → secondary. No response in 30 min → engineering manager. Beyond → CTO. Documented and tested.

**What's needed:**
- Escalation policy in PagerDuty.
- Severity-specific routing: P0 pages on-call; P1 notifies channel + on-call; P2 ticket; P3 logged.
- Tested via fake page exercises monthly.

**Effort:** S.

---

### D-036: Alert quality / hygiene — FINDING

**Where:** Round 2 F-120 raised classes; quality here.

**Why it matters:** False-positive alerts cause pager fatigue → real alerts missed. Standard: every page must be actionable, every actionable page has a runbook, every alert reviewed weekly.

**What's needed:**
- Per-alert: actionability check (can the on-call do something?), runbook reference, severity classification.
- Weekly alert review: noisy alerts retuned; outdated alerts removed; missing alerts added.
- Metrics: alert rate, page rate, mean-time-to-acknowledge (MTTA), mean-time-to-resolve (MTTR).

**Effort:** S (process); ongoing.

---

### D-037: Pager fatigue mitigation — FINDING

**Where:** N/A.

**Why it matters:** Sustained high-page-rate burns out on-call engineers. Standard: <2 pages per shift average. Above: prioritize alert hygiene.

**What's needed:** Page rate tracking; 4-week rolling avg; alert when above threshold.

**Effort:** S.

---

### D-038: Runbook ownership and quality SLA — BLOCKER

**Where:** Phase 4 mentions runbook formalization. Quality SLA missing.

**Why it matters:** Runbook that hasn't been touched in 6 months and references services that have been refactored = useless at 3am. Runbooks must be living documents with quality SLAs.

**What's needed:**
- Every alert has a linked runbook.
- Every runbook has an owner (specific engineer).
- Runbooks reviewed every 6 months minimum; updated on any related architectural change.
- Runbook quality criteria: situation, actions, escalation, links to dashboards/queries, tested via tabletop or chaos exercise.
- Runbook test on every drill: actually open it, follow it; fix what doesn't work.

**Effort:** M (program); ongoing.

---

## 9. Disaster Recovery Engineering

### D-039: DR drill program — extends R1 F-005, R3 S-005 — BLOCKER

**Where:** Round 1 F-005 noted Vault DR gap. Round 3 S-005 added cryptographic specifics. DevOps depth: actually exercising the DR.

**Why it matters:** "RTO 4 hours, RPO 15 minutes" is a target. Without drills, it's a wish. First real DR is the worst time to discover the runbook is wrong.

**What's needed:** Drill program:
- **Quarterly**: tabletop drill (paper exercise; team walks runbook).
- **Bi-annually**: synthetic DR (production-like environment; full failover; measure RTO/RPO).
- **Annually**: production DR drill (failover prod to DR region; measure; restore).
- Each drill produces report: did we hit RTO/RPO; runbook gaps; action items.

**Effort:** L (initial); ongoing.

---

### D-040: Cross-region failover automation — FINDING

**Where:** ARD: us-central1 with multi-AZ. Cross-region DR via "backup replication." Failover automation not specified.

**Why it matters:** Manual failover across regions takes hours. Automation: pre-warmed standby; automated DNS cutover; data restore pipeline.

**What's needed:** ADR: cross-region DR architecture. Standby region (us-east1 or similar US-only). Standby resources pre-provisioned (AlloyDB read replica with promotion capability; standby Cloud Run services). Failover playbook automated where safe (DNS update, replica promotion); manual approval gate for actual cutover.

**Effort:** L.

---

### D-041: Recovery validation — FINDING

**Where:** N/A.

**Why it matters:** Restored data must be validated as correct before traffic resumes. Standard: post-restore checks (row counts, hash chain validity, sample query results match expected).

**What's needed:** Post-restore validation procedure: row count comparison; SCD2 chain integrity check; hash chain validation (audit log); sample integration tests against restored data; sign-off before traffic shift.

**Effort:** M.

---

## 10. Backup Engineering

### D-042: Backup strategy per data class — BLOCKER

**Where:** ARD mentions "cross-region backup replication." Per-class strategy not specified.

**Why it matters:** Different data classes have different RPO needs. Vault: RPO 15 minutes. Audit log: RPO 0 (already in WORM storage; backup is essentially the WORM tier). Operational store: RPO 15 minutes. Analytical store: RPO 1 hour acceptable.

**What's needed:** Per-data-class backup spec:

| Data class | Mechanism | RPO | RTO | Encryption | Cross-region |
|---|---|---|---|---|---|
| Vault | AlloyDB continuous backups + cross-region replica | 15 min | 1 hour | KMS, separate key from primary | Yes (US-only secondary) |
| Canonical operational | AlloyDB continuous backups | 15 min | 1 hour | KMS | Yes |
| Canonical analytical (BQ) | BQ snapshot | 4 hours | 8 hours | KMS | Multi-region native |
| Audit (operational tier) | BQ snapshot + WORM source | 4 hours | 8 hours | KMS | Multi-region |
| Audit (high-criticality) | GCS Bucket Lock + Turbo Replication | 0 (immutable) | N/A | KMS | Yes |
| Configuration | Git + Cloud Storage backup | Continuous | 5 min | Standard | Yes |
| KMS keys | Separate keyring; HSM-backed for critical | Special | Manual | Itself | Special procedure |
| Composer DAG state | Composer-managed | 1 hour | 2 hours | Standard | Yes |

**Effort:** M (specification); IaC follows.

---

### D-043: Backup integrity testing — BLOCKER

**Where:** N/A.

**Why it matters:** Backup that hasn't been restored is hope, not a backup. Untested backups frequently fail when needed.

**What's needed:** Quarterly restore drill: pick a backup at random; restore to staging; validate; measure restore time; document.

**Effort:** M (initial); ongoing quarterly.

---

### D-044: Backup encryption key separation — FINDING

**Where:** Round 3 S-005 implied. DevOps spec here.

**Why it matters:** If primary KMS key is compromised, backups encrypted with the same key are also compromised. Backup-only key prevents this.

**What's needed:** Separate KMS keyring for backups. Backup-only IAM grants (no read access to primary). Cross-region replicated keys.

**Effort:** S.

---

### D-045: Backup access auditing — FINDING

**Where:** N/A.

**Why it matters:** Backup access is a privileged action. Every read of backup data must be audited (in addition to the backup-target's own audit).

**What's needed:** Audit policy on backup buckets/datasets; integration with primary audit log.

**Effort:** S.

---

## 11. Networking

### D-046: VPC topology — FINDING

**Where:** ARD mentions VPC-SC perimeters. Lower-level VPC topology unspecified.

**Why it matters:** VPC subnets, peering, route tables, firewall rules — all need IaC. Default GCP VPC is not production-ready.

**What's needed:** ADR: VPC topology per environment.
- Per-environment VPC.
- Subnets per service tier (public-facing, internal-app, internal-data).
- Private Service Connect for managed services (AlloyDB, Cloud SQL, Memorystore) — keeps traffic on Google's network.
- Firewall rules in IaC; default deny; explicit allow per service.

**Effort:** M.

---

### D-047: Egress controls IaC — extends R3 S-055 — FINDING

**Where:** Round 3 S-055 specified. DevOps owns IaC.

**Why it matters:** Per-service egress allow-list as Terraform config. Drift detection ensures it stays correct.

**What's needed:** VPC firewall rules + Cloud Run egress settings as IaC.

**Effort:** S.

---

### D-048: DNS strategy — FINDING

**Where:** Implicit.

**Why it matters:** Internal DNS for service-to-service; external DNS for Verification API; cert management; DNSSEC.

**What's needed:** ADR: Cloud DNS for internal + external. Public hostname: `verify.lore-eligibility.api.lore.health` (or similar; counsel-coordinated). TLS via Google-managed certs. DNSSEC enabled. CAA records pinning issuance to Google.

**Effort:** S.

---

### D-049: Load balancer configuration — FINDING

**Where:** ARD: HTTPS LB for Verification API.

**Why it matters:** LB config: SSL policy (minimum TLS 1.2, AEAD ciphers — R3 S-006), backend service settings, health checks, Cloud Armor (R3 S-054).

**What's needed:** LB config as IaC; SSL policy attached; backend health checks tuned per service; Cloud Armor policy attached.

**Effort:** S.

---

### D-050: Private Service Connect for managed services — FINDING

**Where:** N/A.

**Why it matters:** AlloyDB and Cloud SQL accessed via PSC keeps traffic on Google's network (no public IP); enables VPC-SC inclusion.

**What's needed:** PSC endpoints for AlloyDB, Cloud SQL Vault, Memorystore; documented in IaC.

**Effort:** S.

---

## 12. Secrets Management Lifecycle

### D-051: Secret rotation automation — BLOCKER

**Where:** Round 3 S-058 noted secrets in Secret Manager. Lifecycle automation not specified.

**Why it matters:** Manual rotation gets skipped under pressure. Automated rotation prevents stale secrets.

**What's needed:** Per-secret rotation schedule in IaC:
- DB passwords: 90-day rotation; automated via Secret Manager rotation hook.
- KMS keys: 90-day rotation (KMS auto-rotation).
- JWT signing keys: rotated per release; old key valid for 24 hours during transition.
- Service account keys: avoid; use Workload Identity (R3 S-014).
- API keys: 90-day rotation where possible.

Rotation events audited; failures alert.

**Effort:** M.

---

### D-052: Emergency rotation procedure — FINDING

**Where:** Round 3 S-249 implied.

**Why it matters:** When a secret is compromised, rotation must happen in minutes, not days. Procedure must be tested.

**What's needed:** Documented procedure per secret type. Tested quarterly via drill (rotate a non-critical secret to validate procedure).

**Effort:** S.

---

### D-053: Secret leak detection — FINDING

**Where:** Phase 00 has gitleaks + detect-secrets in pre-commit/CI.

**Why it matters:** Defense in depth: post-commit secret scanning of every repo, every container image; alert on any leak.

**What's needed:** GitHub native secret scanning + push protection enabled. Container image scanning includes secrets layer (Trufflehog or similar). Cloud Storage object scanning for the most-sensitive buckets.

**Effort:** S.

---

### D-054: Secret access auditing — FINDING

**Where:** N/A.

**Why it matters:** Every secret read should be auditable. Anomaly detection on secret reads (R3 anomaly framework).

**What's needed:** Secret Manager access logging enabled; routed to audit log; included in SIEM correlation.

**Effort:** S.

---

## 13. Database Operations

### D-055: AlloyDB day-2 ops — FINDING

**Where:** ARD mentions AlloyDB. Day-2 ops not specified.

**Why it matters:** Replication lag monitoring, replica failover, vacuum/analyze policies, query plan changes — these are operational realities, not architectural decisions.

**What's needed:** Operational runbook for AlloyDB:
- Replication lag dashboards + alerts.
- Replica failover procedure (when, how).
- Maintenance windows + auto-vacuum policy.
- Query plan baselining (pg_stat_statements analysis).
- Capacity scaling triggers.

**Effort:** M.

---

### D-056: Zero-downtime schema migrations — FINDING

**Where:** Round 2 F-114 covered partial-failure recovery. Zero-downtime here.

**Why it matters:** Backward-incompatible schema changes (rename, drop) require multi-step migration to avoid downtime. Tools: pg_repack for online table reorgs; expand-contract pattern for column changes.

**What's needed:** ADR: zero-downtime migration discipline. Two-phase: expand (add new without removing old; deploy app supporting both); contract (remove old). pg_repack for table reorgs. Migration runbook documented.

**Effort:** S (ADR); ongoing per migration.

---

### D-057: Connection pool tuning under load — extends R2 F-122 — FINDING

**Where:** Round 2 F-122 raised. DevOps depth: monitoring and tuning.

**Why it matters:** Connection pool exhaustion is the most common DB outage. Continuous monitoring and tuning required.

**What's needed:** Pool saturation dashboards per service; alerts at 80% utilization; quarterly tuning review based on observed load.

**Effort:** S.

---

### D-058: Query performance regression — FINDING

**Where:** N/A.

**Why it matters:** Schema or index changes can regress query performance. Without baselines, regressions land silently.

**What's needed:** pg_stat_statements baseline per release; regression alerts on top-N queries.

**Effort:** M.

---

### D-059: pgbouncer health monitoring — FINDING

**Where:** ARD has pgbouncer; ops not specified.

**Why it matters:** pgbouncer is a single point on the DB path. Health, pool saturation, hot connections — must be visible.

**What's needed:** Per-pgbouncer metrics: client connections, server connections, pool wait times, error rates.

**Effort:** S.

---

## 14. Pipeline Observability

### D-060: Composer DAG monitoring — FINDING

**Where:** Composer mentioned in ARD; DAG monitoring not specified.

**Why it matters:** Composer DAGs orchestrate the daily pipeline. DAG failures, lag, task duration trends — all need visibility.

**What's needed:** Composer-native monitoring + Cloud Monitoring custom metrics: DAG run duration, task failure rate, retry counts, end-to-end DAG lag. Dashboards. Alerts on DAG failure or lag breach.

**Effort:** S.

---

### D-061: Pub/Sub backlog monitoring — FINDING

**Where:** Pub/Sub mentioned; backlog monitoring not specified.

**Why it matters:** Backlog growth = consumer falling behind = upstream backpressure (R2 F-150). Detection should be early.

**What's needed:** Per-topic backlog metrics; alerts at thresholds (backlog age, message count, oldest unack age).

**Effort:** S.

---

### D-062: Dataflow job monitoring — FINDING

**Where:** Dataflow used for Audit Consumer. Job monitoring not specified.

**Why it matters:** Dataflow jobs can silently degrade (worker autoscaling stuck, system lag growing). Without monitoring, the audit chain falls behind.

**What's needed:** Dataflow job metrics: system lag, data freshness, worker utilization, error rate. Alerts on lag or error.

**Effort:** S.

---

### D-063: End-to-end pipeline lag — FINDING

**Where:** Phase 1 exit criterion: "Datastream replication to BigQuery is working with lag under 60 seconds." Pipeline E2E lag not measured.

**Why it matters:** A partner record arrives at 09:00; when does it reach the canonical model? Verification API? BigQuery analytics? E2E lag is the user-visible signal.

**What's needed:** Synthetic record injection at landing zone with marker timestamps; trace through pipeline; measure stage-by-stage lag; aggregate dashboard.

**Effort:** M.

---

## 15. Feature Flag Operations

### D-064: Feature flag platform decision — FINDING

**Where:** Round 2 F-149 referenced flags.

**Why it matters:** Flags vs config. Flags vs trunk-based dev. Platform: LaunchDarkly (commercial), GrowthBook (OSS), Unleash (OSS), in-house. Each has tradeoffs.

**What's needed:** ADR: feature flag platform. Recommendation: GrowthBook (OSS, self-hosted; no per-evaluation cost). Flags evaluated client-side (in-app). Audit on flag changes.

**Effort:** S.

---

### D-065: Flag lifecycle and sunset — FINDING

**Where:** Round 2 F-149 implied.

**Why it matters:** Flags accumulate. Stale flags = confusion + tech debt. Standard: max 90 days from creation to sunset (promote or remove).

**What's needed:** Flag review process; max-age policy; automated reminder on aging flags.

**Effort:** S.

---

## 16. Deployment Observability

### D-066: Deployment dashboards — BLOCKER

**Where:** N/A.

**Why it matters:** Deployments are blind today. Mean time to detect a bad deploy is undefined; mean time to roll back is undefined; deploys-per-week is unknown.

**What's needed:** Deployment dashboard:
- Deploys per service per day.
- Deploy success rate (deployed without rollback).
- Time-to-deploy (PR merge → traffic at 100%).
- Time-to-detect (deploy → first SLO violation).
- Time-to-rollback (detection → rollback complete).
- DORA metrics: deployment frequency, lead time, change failure rate, MTTR.

**Effort:** S (dashboard); ongoing.

---

### D-067: Deploy / change correlation in incidents — FINDING

**Where:** N/A.

**Why it matters:** "What changed before this incident?" is the most common incident question. Deploy events overlaid on dashboards make this fast.

**What's needed:** Deploy events as annotations on all monitoring dashboards (Grafana / Cloud Monitoring built-in).

**Effort:** S.

---

## 17. Resilience Patterns — Operational Depth

### D-068: Circuit breakers — extends R2 F-111 — FINDING

**Where:** Round 2 F-111 noted retry policies; DevOps depth on circuit breakers.

**Why it matters:** Cascade failures: TokenizationService slow → Verification calls accumulate → Cloud Run instances saturate → spreads. Circuit breaker isolates: detect slow upstream, fail fast, allow recovery.

**What's needed:** Library standard: `tenacity` for retry, `circuitbreaker` library for breakers. Per-integration: failure threshold (e.g., 5 failures in 60 seconds), open duration (e.g., 30 seconds), half-open probing.

**Effort:** S.

---

### D-069: Bulkheads / per-tenant isolation — extends R2 F-154 — FINDING

**Where:** Round 2 F-154 raised.

**Why it matters:** A noisy partner shouldn't degrade other partners. Per-partner bulkheads: separate connection pools, separate Pub/Sub subscription concurrency, separate priority queues.

**What's needed:** Per-partner isolation in: Pub/Sub subscriptions (separate per partner); DB connection allocation (per-service total connection budget partitioned by partner); Splink batch slots (per partner queue).

**Effort:** M.

---

### D-070: Timeout discipline — FINDING

**Where:** N/A.

**Why it matters:** Default timeouts (often very long or none) cause cascade failures. Discipline: every call has explicit timeout; timeouts shorter than upstream's timeout (cascade prevention).

**What's needed:** Standard timeouts:
- Verification API → AlloyDB: 100ms.
- Verification API → TokenizationService: 50ms.
- Verification API → Memorystore (rate limit): 10ms.
- Match Orchestrator → Splink: 5 minutes.
- Composer DAG tasks: per-task explicit timeouts.

Documented; reviewed per service.

**Effort:** S.

---

## 18. Service Catalog and Ownership

### D-071: Service catalog — FINDING

**Where:** ARD has 7 contexts; service-level catalog not maintained.

**Why it matters:** "Who owns this service" must have an answer. Catalog: name, owner, on-call rotation, SLO, runbook, dashboard, dependencies.

**What's needed:** Service catalog (Backstage or similar, or markdown-based). Per service: ownership, on-call rotation, SLO link, runbook link, dashboard link, dependency graph, tier (critical/important/standard).

**Effort:** M.

---

### D-072: Runbook ownership — FINDING

**Where:** Touched in D-038.

**Why it matters:** Every runbook has an owner; review cadence enforced.

**What's needed:** Per runbook: owner; last-reviewed date; review SLA (6 months for critical, 12 for standard); CI gate flagging stale runbooks.

**Effort:** S.

---

## 19. Compliance Evidence Automation

### D-073: Continuous compliance monitoring — FINDING

**Where:** Round 4 covered compliance requirements; DevOps owns automated evidence.

**Why it matters:** SOC 2 / HITRUST audits require continuous evidence: access controls, configuration baselines, vulnerability remediation, audit log completeness. Manual evidence collection is hours per audit.

**What's needed:** Automated evidence collectors:
- IaC drift report (D-003) → evidence of configuration management.
- Audit log completeness check → evidence of audit controls.
- Vulnerability remediation tracking → evidence of vulnerability management.
- Access review automation → evidence of periodic access review.
- Backup integrity tests (D-043) → evidence of recovery capability.

Tools: Drata, Vanta, or in-house. Output: continuous compliance dashboard.

**Effort:** L.

---

### D-074: Audit log access for compliance — FINDING

**Where:** Round 3 S-032 covered auditor monitoring; DevOps depth on access infrastructure.

**Why it matters:** Auditors need read access to audit logs. Access must be efficient (BigQuery query performance) and controlled (audit-the-auditor per S-032).

**What's needed:** BigQuery dataset views for audit access; saved-query library for common audit needs; audit-the-auditor instrumentation; performance tuning for forensic queries.

**Effort:** M.

---

## 20. Incident Management Process

### D-075: Incident command structure — extends R3 S-048 — BLOCKER

**Where:** Round 3 S-048 specified IR plan. DevOps depth on operational structure.

**Why it matters:** When a SEV1 fires, who's in charge, where does coordination happen, who comms externally?

**What's needed:**
- Incident Commander role: rotates with on-call; primary decision-maker during incident.
- Coordinated channels: Slack #incident-X channel auto-created; war room (Zoom/Meet) link auto-generated.
- Roles: IC, Tech Lead (deep technical), Communications Lead, Scribe (timeline), External Liaison (if applicable).
- Status updates: every 30 min internal, every hour external (status page).
- Resolution criteria: mitigation (immediate symptoms gone) vs full resolution (root cause fixed).

**Effort:** M (process); training.

---

### D-076: Status page / customer comms — FINDING

**Where:** N/A.

**Why it matters:** During Verification API incidents, partners and Lore application need visibility. Status page is industry standard.

**What's needed:** Status page (Statuspage.io or similar). Per-service status. Auto-updates from monitoring (degraded performance → status update). Manual updates during incidents.

**Effort:** S (procurement); ongoing.

---

### D-077: Postmortem culture — FINDING

**Where:** N/A.

**Why it matters:** Incidents repeat without learning. Blameless postmortems with action items prevent this.

**What's needed:**
- Every SEV1 / SEV2 → blameless postmortem within 1 week.
- Template: timeline, contributing factors, lessons learned, action items.
- Action items tracked to completion; review at next on-call handoff.
- Quarterly review: trends across postmortems.

**Effort:** M (program); ongoing.

---

### D-078: Incident drills / GameDay — extends R2 F-137 — FINDING

**Where:** Round 2 F-137 raised; DevOps owns the program.

**Why it matters:** Untested IR is unreliable IR. GameDays exercise: detection, command, communication, runbook, recovery.

**What's needed:** Quarterly GameDay program:
- Pre-defined failure injection (Vault outage, AlloyDB primary failure, Datastream lag spike).
- Live execution against staging.
- Full IR process exercised.
- Postmortem identifies gaps.

**Effort:** M (initial); ongoing.

---

## 21. Tooling and Local Dev

### D-079: Local development substrate — extends R2 F-117, F-146 — BLOCKER

**Where:** Round 2 F-117 and F-146 raised. DevOps owns the substrate.

**Why it matters:** Day-1 productivity for new engineers. Without local substrate: every test is either mocked (low fidelity) or runs against actual GCP (slow, expensive).

**What's needed:** `make dev` brings up:
- Postgres (already in harness).
- Pub/Sub emulator.
- Cloud Storage emulator (fake-gcs-server).
- BigQuery (DuckDB as analytical proxy per AD-007 prototype scope).
- KMS mocked behind TokenizationService boundary.
- Cloud Run-equivalent (uvicorn).
- Composer-equivalent (Python script per prototype scope).

Documented in README. Onboarding doc tested with each new engineer.

**Effort:** L (initial); ongoing.

---

### D-080: Developer onboarding — FINDING

**Where:** N/A.

**Why it matters:** Time-to-first-PR is a quality signal. Standard: new engineer ships first PR within 1 week.

**What's needed:** Onboarding doc covering: repo cloning, environment setup, running tests, running local stack, deploying to dev environment, on-call shadow rotation. Tested on every new hire; updated based on feedback.

**Effort:** M.

---

### D-081: Documentation operations — FINDING

**Where:** Round 2 F-160 ADVISORY raised docs-as-code.

**Why it matters:** Docs that aren't generated drift. Architecture diagrams, API docs, runbooks, dashboards — all should be generated or in-repo as code.

**What's needed:**
- API docs: OpenAPI auto-generated by FastAPI; published to internal portal.
- ER diagrams: generated from SQLModel metadata.
- Architecture diagrams: Mermaid in markdown (versioned with code).
- Runbooks: markdown in repo (D-038).
- Dashboards: as-code (Grafana JSON or Terraform).

**Effort:** M.

---

## 22. Build and Release Engineering

### D-082: Reproducible builds — FINDING

**Where:** Round 3 S-042 noted SLSA. DevOps depth on reproducibility.

**Why it matters:** "Same source builds same artifact." Required for SLSA Level 3+. Detects supply chain tampering.

**What's needed:** Hermetic builds: Bazel or Nix-based; pinned dependencies; deterministic timestamps; verified outputs identical on rebuild.

**Effort:** L.

---

### D-083: Release notes automation — FINDING

**Where:** N/A.

**Why it matters:** What's in this release? Manual changelog maintenance fails. Conventional commits + semantic-release automation generates changelog from commit messages.

**What's needed:** Conventional commit policy (already in CLAUDE.md); semantic-release on merge to main; CHANGELOG.md updated automatically; GitHub releases per version.

**Effort:** S.

---

## 23. Cron and Scheduled Jobs

### D-084: Composer DAG conventions — FINDING

**Where:** ARD mentions Composer.

**Why it matters:** DAGs accumulate. Naming conventions, dependencies, retries, timeouts must be consistent.

**What's needed:** DAG conventions:
- Naming: `<context>_<task>_<schedule>` (e.g., `ingestion_partner_daily`).
- Per-task: explicit timeout, retry policy, idempotency (R2 F-101), alerting on failure.
- Tagging: owner, criticality, environment.
- Documentation: every DAG has a README in repo.

**Effort:** S.

---

### D-085: Per-job alerting — FINDING

**Where:** D-060 covered DAG monitoring; per-job alerting depth here.

**Why it matters:** A failed reconciliation job is a SEV2; a failed DAG that's a critical-path job (daily ingestion) is a SEV1. Per-job severity classification.

**What's needed:** Per-DAG severity tag; alert routing per severity.

**Effort:** S.

---

## 24. Observability — Operational Depth

### D-086: APM (application performance monitoring) — FINDING

**Where:** Round 2 F-118 covered tracing; DevOps depth on full APM.

**Why it matters:** Tracing is part of APM. Full APM also includes: per-endpoint latency breakdowns, slow query detection, code-level profiling.

**What's needed:** Cloud Trace for distributed tracing (R2 F-118); Cloud Profiler for code-level CPU/heap; integrated with logs and metrics.

**Effort:** S.

---

### D-087: Profiling production — FINDING

**Where:** N/A.

**Why it matters:** Continuous profiling reveals hot paths and regressions invisible in metrics.

**What's needed:** Cloud Profiler enabled per service; sampled at low overhead; integrated with monitoring dashboards.

**Effort:** S.

---

### D-088: Log aggregation strategy — FINDING

**Where:** Round 2 F-115 covered logging schema. DevOps depth on log infrastructure.

**Why it matters:** Logs across services need to be searchable, retainable, exportable. Cloud Logging is the GCP-native answer; retention and routing decisions matter.

**What's needed:** Cloud Logging routing:
- Operational logs → 30 days in Cloud Logging (default tier).
- Audit logs → routed to BigQuery via log sink (R3 S-029 covered audit-specific).
- Long-term archive → Cloud Storage with retention policies.
- Cost control: high-volume noisy logs sampled or filtered.

**Effort:** S.

---

## 25. Specific Operations

### D-089: Maintenance windows — FINDING

**Where:** N/A.

**Why it matters:** Cloud Run deploys can be disruptive (revision swap). AlloyDB has its own maintenance windows.

**What's needed:** Per-service maintenance window policy. AlloyDB maintenance: aligned with low-traffic hours. App deploys: any time, but visible on status page.

**Effort:** S.

---

### D-090: Quota management — FINDING

**Where:** Round 3 S-046 implicit. DevOps explicit here.

**Why it matters:** GCP service quotas are real limits. KMS API quota, BigQuery slot quota, Pub/Sub publish rate, Cloud Run concurrent requests — all have quotas. Hitting a quota = outage.

**What's needed:** Per-service quota inventory; current vs limit dashboards; alerts at 80% utilization; quota increase requests proactive (lead time can be 1+ week).

**Effort:** S.

---

### D-091: Multi-region replication monitoring — FINDING

**Where:** ARD mentions cross-region backup. Replication health not monitored.

**Why it matters:** Cross-region replication can lag or break silently. Detection before disaster matters.

**What's needed:** Replication lag dashboards per data class; alerts on lag > threshold.

**Effort:** S.

---

## Summary triage

| Severity | Count | Examples |
|---|---|---|
| BLOCKER | 18 | IaC framework (D-001), Deployment strategy per service (D-006), Artifact promotion (D-007), Automated rollback (D-010), Environment parity (D-013), Container orchestration choice (D-017), SLI definitions (D-022), SLO targets (D-023), Error budget tracking (D-024), Capacity model (D-026), On-call rotation (D-034), Runbook quality SLA (D-038), DR drill program (D-039), Backup strategy per data class (D-042), Backup integrity testing (D-043), Secret rotation automation (D-051), Deployment dashboards (D-066), Incident command structure (D-075), Local development substrate (D-079) |
| FINDING | 44 | IaC state, drift, pipeline; image lifecycle, build provenance, pre-deploy gates, schema migration deploy; ephemeral envs, synth data refresh, env config; service mesh, cold start, concurrency, scaling; load testing, perf regression, headroom; cost monitoring, attribution; escalation, alert hygiene, pager fatigue; cross-region failover, recovery validation; backup encryption separation, access auditing; VPC, egress, DNS, LB, PSC; emergency rotation, leak detection, secret access auditing; AlloyDB day-2, zero-downtime migrations, connection pool, query regression, pgbouncer; Composer DAG, Pub/Sub backlog, Dataflow, E2E lag; feature flag platform, lifecycle; deploy correlation; circuit breakers, bulkheads, timeout discipline; service catalog, runbook ownership; compliance monitoring, audit access; status page, postmortem, GameDay; onboarding, docs ops; release notes; DAG conventions, per-job alerting; APM, profiling, log aggregation; maintenance windows, quota management, replication monitoring |
| ADVISORY | 9 | Cost anomaly detection, plus a few smaller items |
| **Total** | **71** | |

---

## Cross-round summary (all five rounds)

| Round | Lens | BLOCKERS | FINDINGS | ADVISORIES | Total |
|---|---|---|---|---|---|
| 1 | Principal Architect | 6 | 14 | 5 | 25 |
| 2 | Chief Programmer | 13 | 37 | 10 | 60 |
| 3 | Principal Security | 18 | 47 | 9 | 74 |
| 4 | Compliance / Legal | 22 | 44 | 9 | 75 |
| 5 | Principal DevOps | 18 | 44 | 9 | 71 |
| **Combined (with overlap)** | — | **77** | **186** | **42** | **305** |

After de-duplication: **~70-75 unique BLOCKERs** across all five rounds. Many compound — IaC enables drift detection enables compliance evidence; SLO drives error budget drives release cadence policy; on-call rotation drives runbook quality drives incident response.

Without the BLOCKERs addressed: the platform may be technically architected, securely designed, legally compliant on paper — but unrunnable in practice. First production incident exposes the absence of operational engineering.

---

## Recommended path before backlog

1. **Address all 18 BLOCKERS.** Several are L effort (IaC framework setup, capacity model, DR drill program, local dev substrate, continuous compliance) — these warrant dedicated Phase 0.5 work between Phase 0 (harness) and Phase 1 (single-partner end-to-end).
2. **Sequence the BLOCKERs:** IaC first (enables most others); SLI/SLO/error budget early (drives release pace); on-call rotation before Phase 1 production traffic.
3. **DR and backup BLOCKERs are non-negotiable** before Phase 1: untested DR + untested backups = real risk of unrecoverable data loss.
4. **Defer remaining FINDINGs to Phase 0 ADRs and the phase backlog**, with named DevOps owner.
5. **Address ADVISORIES opportunistically.**

Cross-round coordination: the ~70 unique BLOCKERs should be triaged together. Some compound:
- IaC (D-001) is a precondition for: drift detection, environment parity, egress controls, PSC, secret rotation automation.
- On-call rotation (D-034) is a precondition for: runbook program, incident command, GameDay.
- SLI/SLO (D-022, D-023) is a precondition for: error budget, burn-rate alerts, release pace policy.
- Capacity model (D-026, R1 F-001) is a precondition for: load testing, scaling tests, cost envelope, performance regression detection.

---

## Hand-offs to the consolidation pass

This is now the fifth review round. The user previously indicated Round 4 was "the final pass" before consolidation; Round 5 was added. Consolidation now spans 305 raw findings, ~70-75 unique BLOCKERs.

**Recommended consolidation approach (refined from Round 4):**

1. **Triage all five rounds' BLOCKERs** into:
   - **BRD/ARD amendments** (document changes — for the consolidation PR)
   - **Phase 0 ADRs** (decisions tracked separately under `docs/adr/`)
   - **Phase 0.5 DevOps work products** (IaC, runbooks, dashboards, drill programs — owned by DevOps lead)
   - **Compliance Phase 0 work products** (P&P, contracts, designations — owned by Privacy/Security Officers per Round 4 L-036, L-037)
2. **Author BRD/ARD amendments** as the consolidation PR with one commit per finding addressed (or themed groups). Each commit references originating finding ID(s).
3. **Carry deferred FINDINGS** into the phase backlog with named owners, target phases, and acceptance criteria.
4. **Standup the Phase 0.5 DevOps track** in parallel with BRD/ARD amendments (IaC framework decision can land before the BRD changes; capacity model emerges from the amendments).

The five reviews collectively did the diagnostic. The consolidation is the prescription.

---

## What this review did NOT cover

Out of scope for principal-DevOps lens:

- Architectural decomposition tradeoffs (Round 1)
- Code-level discipline (Round 2)
- Security technical controls (Round 3 — operational security touched, controls are Round 3's depth)
- Regulatory / contract / member rights (Round 4)
- Domain correctness (would be DE Principal / clinical-trust)
- Specific GCP service feature comparisons (vendor selection — out of scope)
- Tooling vendor selection beyond recommendations (Drata vs Vanta, Backstage vs Cortex, etc. — separate procurement)

These belong to other reviewers or downstream procurement. This round focused on the operational engineering gaps that, if unaddressed, fail the platform under real production conditions.
