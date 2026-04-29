# Architecture Review — Round 8: Expert Project Manager (Scaled Agile + Agents)

| Field | Value |
|---|---|
| **Round** | 8 of N |
| **Reviewer lens** | Expert Project Manager — scaled agile delivery, hybrid framework, agent-as-team-member methodology, schedule realism, dependency management, backlog discipline, ceremony cadence, risk-at-delivery-level, achievability |
| **Documents** | `docs/BUSINESS_REQUIREMENTS.md` (BRD), `docs/ARCHITECTURE_REQUIREMENTS.md` (ARD) |
| **Date** | 2026-04-29 |
| **Prior rounds** | `docs/reviews/01-principal-architect.md` through `docs/reviews/07-executive.md` |
| **Method context** | "Hybrid scaled agile approach leveraging agents in the scaled agile methodology" — per the user's framing |

This review reads the documents the way a Release Train Engineer or Program Manager about to plan delivery reads them. Where prior rounds asked "is this right" or "is this safe" or "is this valuable," this round asks **"is this achievable, and how would we actually deliver it"**. The achievability question is the user's explicit ask: *"Is this plan actually achievable?"* That question can only be answered if the plan is concrete enough to test against capacity, dependencies, and risk — and currently it isn't.

The user also flagged a distinctive twist: **agents as participants in scaled agile**. This is emerging practice with limited industry precedent. This review treats it seriously: agents as team members have different capacity profiles, quality verification needs, coordination patterns, and ceremony fit than humans. The harness already addresses single-stream agent work (CLAUDE.md, .claude/agents/, phase backlog); scaling to parallel agent-driven streams introduces new gaps.

Severity per Constitution Rule 29 (BLOCKER / FINDING / ADVISORY).

---

## TL;DR

**Is this plan actually achievable? Answer: unknown — the plan isn't concrete enough to test for achievability.**

The BRD/ARD describe what the platform must do and how it's architected. They don't describe a *delivery plan*: when, by whom, in what order, with what dependencies, against what capacity, under what cadence, with what risk surface. Phase exit criteria exist (good); phase durations, team assignments, sprint structure, story decomposition, dependency graphs, capacity model, and ceremony cadence don't (insufficient).

Specifically, the achievability question fails in five dimensions:

1. **No timeline.** Phase 0 = 2 weeks? 6 months? 18 months? Unknown. Total program duration unknowable. "Achievable" requires a target to test against.
2. **No team / capacity.** How many engineers? What roles? What % time on this vs other work? Sequelae PH timezone overlap with US? Agent capacity? Ramp time for new hires? All unstated.
3. **No critical path.** Within Phase 0 alone: IaC, KMS, IAM groups, VPC-SC perimeters, AlloyDB, Pub/Sub topics, Composer cluster, baseline observability, no-op service. Some sequential, some parallel. Without dependency analysis, schedule risk is unbounded.
4. **No backlog decomposition.** BRs are policy-level, not story-level. Each BR explodes into multiple stories that need estimation, dependency mapping, prioritization. Today: zero of that exists.
5. **No scaled agile framework chosen.** "Hybrid scaled agile" is the user's intent, but which framework provides the spine — SAFe? Scrum@Scale? LeSS? Custom? — is unspecified. Each has different ceremonies, roles, artifacts. With agents in the mix, additional adaptation is needed.

A reasonable first-cut estimate for the program as scoped, executed by a 6-12 person mixed agent/human team in a regulated healthcare context, is **9-18 months** to Phase 2 (production cutover with all v1 BRs satisfied) and **another 6-12 months** to Phase 4 (attestation readiness). With aggressive parallelism and a strong PMO, the lower bound is achievable; without explicit project management discipline, the upper bound is conservative. The current docs do not enable judgment between those two outcomes.

**76 findings: 16 BLOCKERS, 49 FINDINGS, 11 ADVISORIES.**

After consolidating across all eight rounds, the unique BLOCKER set spans approximately **105-115 items**. With PM BLOCKERs addressed, the plan becomes testable for achievability — capacity vs. scope, dependencies vs. critical path, risk vs. mitigation, cadence vs. ceremony fit. Without them, the plan remains aspirational.

---

## What the PM Lens Owns That Prior Rounds Could Not

Prior rounds addressed *what* and *why*. This round addresses *when, by whom, in what order, with what cadence, under what risk*.

Specifically, no prior round had standing to:

1. **Test achievability** of the scope against capacity and time
2. **Decompose BRs into delivery-level stories** with estimation
3. **Identify the critical path** within and across phases
4. **Map cross-phase, cross-team, cross-organizational dependencies**
5. **Define scaled agile framework** and adapt for agent participation
6. **Establish ceremony cadence** (PI planning, sprint, daily standup, demo, retro)
7. **Define delivery-level risk register** (schedule, scope, quality, team, external)
8. **Establish capacity model** with agents-as-team-members
9. **Define communication and stakeholder engagement plan** at execution level
10. **Establish change management process** for scope, schedule, and resource changes during execution

This review surfaces those gaps. Most resolution requires PM engagement; some require executive (Round 7) and engineering leadership coordination.

---

## Strengths from a PM View

What's correct and should be preserved:

1. **Phase exit criteria are objective and testable.** Phases end on something measurable. Critical PM artifact — most projects fail because phases end on opinion.
2. **Phase 0 explicitly acknowledged as foundation.** Recognition that infrastructure precedes value. Many projects skip this and pay later.
3. **Risk-aware sequencing.** Phase 1 single-partner end-to-end before Phase 2 production cutover before Phase 3 scale before Phase 4 hardening. Right shape.
4. **Compliance baked into early phases.** Phase 0 establishes IAM, VPC-SC, KMS — compliance prerequisites. Right sequencing.
5. **Configuration-driven onboarding (BR-802).** Reduces marginal cost per partner. Important PM signal: scope grows linearly with partners, not exponentially.
6. **Constitution + CLAUDE.md harness already exists.** Per-phase retros, advisory drain, spec-challenge, multi-reviewer pattern. PM scaffolding is partially in place at the harness level.
7. **Two-gate test policy (Rule 18).** Avoids regression vs. test bloat. Protects velocity.
8. **Open Architectural Questions explicit.** Acknowledged uncertainty — better than buried uncertainty.

These work. Findings extend or fill gaps around them.

---

## 1. Schedule, Capacity, and Achievability

The achievability question lives here. Without these, "achievable" is unknowable.

### P-001: No timeline estimate per phase — BLOCKER

**Where:** ARD §"Phased Delivery" describes 5 phases with technical exit criteria. No durations, target dates, or estimation basis.

**Why it matters:** Without timelines:
- Investors, board, partners, and Lore application team cannot plan
- Capacity vs. scope cannot be tested
- Risk of slip cannot be quantified
- Phase 4 attestation timing (which gates large partner contracts) is unknowable
- "Achievable" is unanswerable

**What's needed:** Per-phase time estimate with confidence range. Schema:
- **Optimistic** (best case, all goes well): X weeks
- **Likely** (50% confidence): Y weeks
- **Pessimistic** (90% confidence): Z weeks
- **Estimation basis**: bottom-up from story estimates? Reference-class from similar projects? Team-velocity projection?

For Phase 0 specifically, given the scope (IaC, KMS keyrings, IAM, VPC-SC, Composer, AlloyDB, Cloud SQL Vault, observability baseline, CI/CD, no-op service end-to-end smoke test), a reasonable likely estimate is 8-14 weeks for a 4-6 person team. Phase 1 (single-partner end-to-end with all BRs sketched but minimum-feature): 12-20 weeks. Phase 2 (full v1 BR coverage including Splink, manual review queue, deletion ledger, hash-chained audit): 16-26 weeks. Phase 3 (multi-partner scale + tuning): 8-16 weeks. Phase 4 (attestation prep + external audit): 12-26 weeks (limited by external auditor cadence).

These are reviewer-supplied estimates without team capacity context — they need to be replaced by team-derived estimates.

**Effort:** M (estimation work; team engagement).

---

### P-002: No team capacity model — BLOCKER

**Where:** Round 7 E-025 raised talent strategy at executive level. PM-level capacity model is more granular.

**Why it matters:** Capacity model translates headcount into deliverable scope per time. Required:
- Per-role headcount (engineering, DevOps, security, compliance, design, PM, QA)
- Per-role allocation % to this platform vs. other work
- Per-role timezone (US, Sequelae PH UTC+8 — 16-hour gap from US Pacific)
- Agent capacity (always-available; context-window-bound; cost-per-token)
- Ramp time for new hires (typical: 30-60 days to first significant contribution; 90-180 days to fluency)
- Vacation, training, on-call burden, recruiting time
- Effective velocity (typical 60-70% of nominal hours)

Without this, sprint capacity is guessed. Sprint commitments are unfounded. PI plans are aspirational.

**What's needed:** Capacity model document. Lives in project-management section of repo or referenced PM tool (Jira, Linear). Updated quarterly.

**Effort:** M.

---

### P-003: No critical path analysis — BLOCKER

**Where:** Phase exit criteria don't expose dependencies between work items.

**Why it matters:** Within Phase 0 alone:
- IaC framework (D-001 from Round 5) must precede every other infrastructure work
- KMS keyring must precede any encryption operations
- IAM groups + Sequelae PH residency conditions must precede any service deployment
- VPC-SC perimeters must precede service-to-service communication
- AlloyDB instance must precede any canonical eligibility schema work
- Cloud SQL Vault must precede any tokenization work
- Pub/Sub topics with schemas must precede any inter-context eventing
- Observability baseline must precede any meaningful "is it working" assertion

Some sequential, some parallel. Without explicit critical path, the question "if X slips, what else slips" is unanswerable.

Across phases:
- Phase 0 IaC → Phase 1 service deployment
- Phase 1 single-partner end-to-end → Phase 2 production cutover
- Phase 2 BR completion → Phase 3 scale tuning
- Phase 3 production validation → Phase 4 attestation engagement

External critical path:
- BAA execution with each partner → partner data flow can begin
- Counsel-engaged work (Round 4 BLOCKERs) → policy/contract work can complete
- Privacy Officer + Security Officer designation (Round 4 L-036, L-037) → compliance program can operate
- IaC framework choice → DevOps Phase 0.5 work can begin

**What's needed:** Critical path analysis document or PM-tool representation. Updated as work progresses.

**Effort:** M.

---

### P-004: No dependency map across BRs — BLOCKER

**Where:** BRD lists BRs in domain groups; no dependency graph.

**Why it matters:** BRs depend on each other. Sample dependencies (illustrative; not exhaustive):
- BR-101 (tiered match) requires BR-201 (canonical eligibility state machine)
- BR-101 Tier 3 requires BR-105 (review queue exists)
- BR-401 (Verification API) requires BR-201 + BR-204 (re-enrollment for accurate state)
- BR-501 (audit event classes) requires shared/security/audit primitive (currently empty)
- BR-502 (audit content constraints) requires XR-005 (no PII in logs) and tokenization primitives
- BR-602 (snapshot-diff) requires BR-601 (within-feed dedup) results
- BR-701-704 (deletion) requires BR-201 (state machine) + tokenization vault + audit primitive

Without dependency map, sprint planning chooses BRs without knowing prereqs, leading to false starts.

**What's needed:** BR dependency graph. Visualized (Mermaid, dot-graph, PM-tool dependency view). Maintained as BRs are amended.

**Effort:** M (initial); ongoing.

---

### P-005: No estimation methodology — FINDING

**Where:** Implicit.

**Why it matters:** Different teams use different methodologies (story points, t-shirt sizing, person-days, ideal hours). Mixed-methodology programs produce non-comparable estimates. Agent capacity adds further complication.

**What's needed:** Single methodology stated. Recommendation: story points (relative sizing; team-velocity-based), with t-shirt sizing for backlog items not yet refined. Agent contributions sized in same units; agent velocity tracked separately.

**Effort:** S.

---

### P-006: No velocity assumptions — FINDING

**Where:** Implicit.

**Why it matters:** Velocity = completed-points-per-sprint. New teams have unknown velocity (typically 4-8 sprints to stabilize). New domains slow velocity. Mixed agent/human teams have different velocity profiles than human-only teams.

**What's needed:** Velocity assumption per team-quarter; revised as actual data accumulates.

**Effort:** S; ongoing.

---

### P-007: Buffer / contingency not incorporated — FINDING

**Where:** Implicit.

**Why it matters:** Estimates without buffer slip on first surprise. Standard PM practice: 15-25% buffer at phase level for unknowns; 5-10% buffer at sprint level for absorbed work.

**What's needed:** Explicit buffer policy. PM-managed.

**Effort:** S.

---

## 2. Scaled Agile Framework

The user said "hybrid scaled agile." Which framework provides the spine matters for everything else.

### P-008: Scaled agile framework not chosen — BLOCKER

**Where:** Not addressed.

**Why it matters:** Each framework has different ceremonies, roles, artifacts, and adaptation patterns:
- **SAFe (Scaled Agile Framework)**: PI planning every 8-12 weeks; ART (Agile Release Train) coordinates 5-12 teams; explicit roles (RTE, System Architect, Product Manager); heavy ceremony but well-established
- **Scrum@Scale**: organic scaling via Scrum-of-Scrums; lighter overhead; less prescriptive
- **LeSS (Large-Scale Scrum)**: minimal additional structure beyond Scrum; relies on cross-team feature teams
- **Spotify Model (informal)**: squads, tribes, chapters, guilds; self-organized; cultural rather than ceremonial
- **Custom hybrid**: combination of elements

Each works; not having one chosen leaves teams free-styling, leading to coordination drift.

**What's needed:** ADR or governance document: framework choice with rationale. For ACO scale (4-12 teams typical), SAFe and Scrum@Scale are the standard candidates; SAFe provides more structure (good for regulated environments) but more overhead; Scrum@Scale provides less overhead but requires stronger team self-organization.

**Recommendation**: SAFe Essential (lightest SAFe configuration) for the regulated environment + ART coordination + PI planning rigor; adapt with custom elements for agent participation.

**Effort:** S (ADR); ongoing operation.

---

### P-009: Program Increment (PI) cadence not specified — BLOCKER

**Where:** Not addressed.

**Why it matters:** PI is the planning cadence in SAFe; equivalent exists in other frameworks. PI typical = 8-12 weeks (4-6 sprints of 2 weeks). PI planning event aligns multiple teams on deliverables for the increment.

For this platform, PI cadence aligns with:
- Phase boundaries (each phase is roughly 1-2 PIs)
- Quarterly executive review (Round 7 E-037 QBR)
- External audit cadence (annual penetration test, attestation engagement)

**What's needed:** PI cadence decision (8 vs 10 vs 12 weeks). PI planning event scheduled. Aligns with E-037 QBR quarterly cadence and Round 5 D-039 quarterly DR drill cadence.

**Effort:** S.

---

### P-010: Sprint cadence not specified — FINDING

**Where:** Not addressed.

**Why it matters:** 2-week sprints are most common. 1-week sprints have higher overhead but faster feedback. 3-week sprints have lower ceremony but slower feedback. Mixed sprint cadences across teams complicate cross-team coordination.

**What's needed:** Standard sprint cadence (recommendation: 2 weeks; aligned across all teams for PI coordination).

**Effort:** S.

---

### P-011: Agile ceremonies cadence — FINDING

**Where:** Not addressed.

**Why it matters:** Standard ceremonies for SAFe Essential:
- **Daily standup**: 15 min; team-internal; per team
- **Sprint planning**: 2-4 hours per 2-week sprint; per team
- **Sprint review (demo)**: 1-2 hours; per team; stakeholders attend
- **Sprint retrospective**: 1 hour; team-internal; per team
- **Backlog refinement**: 2-4 hours per sprint; team + PO
- **PI planning**: 2 days per quarter; ART-wide event; high-energy alignment
- **System demo**: 1 hour at end of each sprint; ART-wide; integrated demo
- **Inspect & Adapt (I&A)**: 4 hours at end of PI; ART retrospective + planning

**What's needed:** Ceremony cadence document; calendar invitations; facilitator assignments.

**Effort:** S (initial); ongoing.

---

### P-012: Cross-team coordination forum — FINDING

**Where:** Not addressed.

**Why it matters:** With 4-12 teams in an ART, cross-team dependencies surface daily. Standard forums:
- **Scrum-of-Scrums (SoS)**: daily 15-min; one rep per team; surface cross-team dependencies and impediments
- **PO sync**: weekly; product owners across teams align on priorities
- **System architect sync**: weekly; architectural alignment
- **Communities of Practice (CoP)**: monthly; cross-team practice sharing (security CoP, testing CoP, etc.)

**What's needed:** Forum structure; cadence; ownership.

**Effort:** S.

---

## 3. Agent-Specific Methodology

The user explicitly framed: "leveraging agents in the scaled agile methodology." This is emerging practice with limited industry precedent.

### P-013: Agent role in scaled agile undefined — BLOCKER

**Where:** CLAUDE.md defines per-phase agent roles for the harness (PM, software-developer, qa-reviewer, etc.). At scaled agile level, agent role is unaddressed.

**Why it matters:** Agents can play different roles:
- **Agent-as-developer**: agent writes code; human reviews; treated like a junior team member with high availability
- **Agent-as-reviewer**: agent reviews human or other-agent work; specialized review (security, architecture)
- **Agent-as-pair**: agent pairs with human in real time
- **Agent-as-scribe**: agent maintains documentation, minutes, retros
- **Agent-as-orchestrator**: agent coordinates multi-agent work (PM-style agent)

Each role has different process implications. Mixed-role agent teams require explicit role assignment.

CLAUDE.md's current pattern: PM agent (the user's session) orchestrates; software-developer subagent codes; review agents review. This pattern works for single-stream sequential work. Scaling to multiple parallel streams requires:
- Multiple software-developer streams in parallel (need coordination protocol)
- Multiple PM agents possible? Or always single-PM?
- Agent capacity allocation (which agent works on what)
- Human oversight cadence

**What's needed:** ADR: agent role(s) in scaled agile. Recommendation: extend CLAUDE.md harness pattern to multi-stream:
- Each squad has a PM agent (human-driven session) that orchestrates that squad's work
- Software-developer subagent per active work-stream within a squad
- Review subagents shared across squads (qa, security, architecture, devops review pools)
- Cross-squad coordination via human PM/RTE; agents cannot autonomously cross squad boundaries

**Effort:** M (ADR + CLAUDE.md extension).

---

### P-014: Agent capacity model — BLOCKER

**Where:** Round 5 D-026 raised infrastructure capacity model; agent capacity is different.

**Why it matters:** Agent capacity profile:
- **Always available**: 24/7, no shift constraints
- **Highly parallelizable**: many concurrent agent sessions possible
- **Context-window-bound**: each session has finite context; long work needs handoff or memory
- **Variable quality**: depends on task complexity, prompt clarity, context availability
- **Token-cost**: per-token pricing means high-throughput agent work has financial cost
- **Verification overhead**: every agent contribution needs review (per CLAUDE.md Rule 21, 22, 23, 24)

The result: agent capacity is **not** simply additive to human capacity. Adding 10 agent sessions doesn't 10x team velocity. The bottleneck shifts from agent throughput to human review capacity.

**What's needed:** Agent capacity model:
- Per-stream agent throughput (lines of code, stories closed per day)
- Human review capacity (lines reviewable per day per reviewer)
- Optimal ratio: agent-streams per human reviewer
- Cost-per-story (token cost + human review cost)
- Quality calibration (defect rate; rework rate)

**Effort:** M.

---

### P-015: Agent-human work handoff protocol — FINDING

**Where:** CLAUDE.md addresses single-session handoffs (PM → software-developer → reviewers). Multi-session, long-duration handoffs unaddressed.

**Why it matters:** Stories take longer than a single agent session. Specifically:
- Agent A starts story; context window fills; agent must hand off
- Agent B picks up; needs context (what was done, what's left, what's tricky)
- Without protocol: each agent rebuilds context from scratch (token-costly, error-prone)

CLAUDE.md memory system (the auto-memory mentioned in environment) addresses some of this. Sprint-level continuity needs explicit protocol.

**What's needed:**
- Per-story working document maintained by each agent
- Standardized handoff format (what's done, what's next, what's hard, what's pending review)
- Memory system entries per active story (already partially supported)

**Effort:** S.

---

### P-016: Definition of Done with agent contributions — FINDING

**Where:** CLAUDE.md has TDD + review pattern. DoD for agent-authored work exists implicitly.

**Why it matters:** Story is "done" means: code merged, tests passing, reviewed, deployed, demo'd. With agent contributions:
- Code merged: requires successful merge-pr.sh (programmatic merge gate per Rule 12)
- Tests passing: 95% coverage gate (Constitution Priority 4)
- Reviewed: which agents must review? At minimum qa-reviewer + red-team-reviewer per Rule 21
- Deployed: per environment promotion plan (Round 5 D-007)
- Demo'd: stakeholder visibility (sprint review)

Explicit DoD aligns expectations.

**What's needed:** DoD checklist per story type:
- All-stories DoD: tests + review + deployment to dev
- Feature DoD: above + acceptance criteria signed off + sprint demo
- Production-bound DoD: above + staging deployment + smoke tests + canary plan

**Effort:** S.

---

### P-017: Agent quality verification at scale — FINDING

**Where:** Round 2 F-103, Round 3 multiple findings on review. PM perspective: scaling.

**Why it matters:** With multiple parallel agent-driven streams, review burden compounds. Risks:
- Reviewers (human or agent) become bottleneck
- Review quality drops under volume
- Cross-stream consistency erodes (different agents make different choices)
- Architectural drift (each stream's local optima not globally optimal)

**What's needed:**
- Review pooling (reviewers serve multiple streams; load-balanced)
- Architectural review at story level (lightweight; flag escalation)
- Cross-stream consistency check (weekly architecture sync)
- Calibration tests for agent reviewers (random pre-known cases mixed in; track agent reviewer accuracy)

**Effort:** M.

---

### P-018: Token cost as program cost line item — FINDING

**Where:** Round 5 D-030 covered cost envelope; agent token cost is a distinct category.

**Why it matters:** Heavy agent usage has real cost. Per-program estimate:
- Average tokens per story (input + output + review): 100k-500k
- Per-story token cost (current pricing): $5-50
- Stories per program: 200-1000
- Total token cost: $1k-50k per phase, scaling with usage

Modest by enterprise-software-development standards but a real line item.

**What's needed:** Token budget per phase; cost tracking; ROI calibration (token cost vs. equivalent human-time cost).

**Effort:** S.

---

### P-019: Agent escalation paths — FINDING

**Where:** CLAUDE.md Rule 12 addresses merge-gate. Agent-blocked situations unaddressed.

**Why it matters:** Agents get stuck:
- Ambiguous spec (spec-challenger output incomplete)
- Test failures with unclear root cause
- Tool/environment failure
- Architectural ambiguity
- External dependency unavailable

Escalation: agent → human PM → human technical lead → human architect/CTO. Clear path prevents dead-end loops.

**What's needed:** Escalation path with response SLAs.

**Effort:** S.

---

### P-020: Multi-agent coordination — FINDING

**Where:** CLAUDE.md addresses single-stream sequential agents. Parallel multi-agent streams unaddressed.

**Why it matters:** Two parallel agent streams may step on each other:
- Both modify the same file (conflict)
- Both attempt to merge to main (merge-pr.sh contention)
- Both need the same shared resource (database test fixture, Pub/Sub topic, etc.)

**What's needed:**
- Stream-isolation protocol (per-stream branches; per-stream test resources)
- Merge-queue for shared resources (sequential merge; conflict detection)
- Cross-stream broadcast for breaking changes

**Effort:** M.

---

## 4. Backlog Management

### P-021: BRs not decomposed into stories — BLOCKER

**Where:** BRD has 70+ BRs at policy level. Implementation stories unspecified.

**Why it matters:** A BR is not a story. BR-101 (tiered match) implementation = many stories: deterministic anchor lookup, Splink integration, threshold configuration, score persistence, score breakdown UI, reviewer queue integration, calibration tests, audit emission per match. Each story is sized, estimated, dependency-mapped.

Without BR → story decomposition: sprint planning has no work units; PI planning has no items; estimation is impossible.

**What's needed:** BR decomposition exercise:
- Per BR, list implementation stories
- Each story has acceptance criteria (Given/When/Then or equivalent)
- Each story is INVEST-compliant (Independent, Negotiable, Valuable, Estimable, Small, Testable)
- Stories enter the product backlog

This work happens in the PM tool (Jira / Linear / GitHub Projects) — not in BRD/ARD which remain policy-level.

**Effort:** L (across all BRs); ongoing per amendment.

---

### P-022: Product backlog tooling — BLOCKER

**Where:** Implicit. The harness has `docs/backlog/phase-NN-*.md` files (currently only phase-00).

**Why it matters:** Static markdown is fine for one phase's planning; not fine for multi-phase, multi-team backlog management. Need: Jira / Linear / GitHub Projects with:
- Hierarchical decomposition (epic / story / task)
- Status tracking
- Dependency relationships
- Estimation fields
- Velocity tracking
- Sprint and PI assignment
- Reporting

**What's needed:** Tool decision and adoption. Recommendation: Linear (lighter, integrated with GitHub) or Jira (heavier, more SAFe-native). Decision factors: org standardization, integration with existing tools, agent-API support.

**Effort:** S (decision); M (setup); ongoing.

---

### P-023: Definition of Ready (DoR) — FINDING

**Where:** Not specified.

**Why it matters:** Stories pulled into a sprint without DoR met = sprint failures. Standard DoR:
- Story has clear acceptance criteria
- Story is estimated
- Dependencies identified and resolved (or accepted)
- Story is INVEST-compliant
- Spec-challenger run (per CLAUDE.md Rule 20)
- Design discussion held (or not needed)

**What's needed:** DoR checklist; gate at sprint planning.

**Effort:** S.

---

### P-024: Backlog refinement cadence — FINDING

**Where:** Not specified.

**Why it matters:** Backlog refinement keeps the backlog healthy. Without cadence: unrefined backlog at sprint planning; sprint planning slows or fails. Standard: 5-10% of sprint capacity allocated to refinement; weekly 1-2 hour refinement meetings.

**What's needed:** Refinement cadence; calendar; ownership (Product Owner + team).

**Effort:** S.

---

### P-025: Prioritization framework — FINDING

**Where:** Round 7 E-002 raised strategic tier; PM-level prioritization is more granular.

**Why it matters:** Within a tier, which story first? SAFe uses WSJF (Weighted Shortest Job First) = Cost of Delay / Job Size. Other frameworks: MoSCoW (Must/Should/Could/Won't), value-based, dependency-driven.

**What's needed:** Prioritization framework. Recommendation: WSJF for SAFe-compatible scoring; MoSCoW for stakeholder communication; dependency-driven order within MoSCoW tiers.

**Effort:** S.

---

### P-026: Story format / acceptance criteria — FINDING

**Where:** Not specified.

**Why it matters:** Consistent story format aids estimation, review, and demo. Standard:
- **Story**: "As a [role], I want [capability], so that [outcome]"
- **AC**: Given/When/Then format or bulleted list with explicit testability

**What's needed:** Story template; AC template; examples.

**Effort:** S.

---

## 5. Risk Management at Delivery Level

### P-027: Delivery-level risk register — BLOCKER

**Where:** Round 7 E-008 raised executive risk register. Delivery risks are different category.

**Why it matters:** Delivery risks include:
- Schedule slip (per phase, per quarter)
- Scope creep (BR amendments inflate work)
- Team turnover (especially Privacy Officer, lead architect, key SREs)
- External dependency (BAA negotiation; counsel availability; partner SFTP setup)
- Technology learning curve (Splink adoption; new GCP services)
- Cross-team dependency (Lore application team availability for joint UX work; partner team responsiveness)
- Compliance overhead (HIPAA reviews slow agile delivery)
- Quality (defect rate; rework rate; test coverage maintenance)
- Cost (token cost over budget; GCP cost over budget)

**What's needed:** Delivery risk register:

| Risk | Likelihood | Impact (schedule/scope/quality) | Owner | Mitigation | Trigger |
|---|---|---|---|---|---|
| Phase 0 IaC takes >3 months | Moderate | Schedule (cascade) | DevOps Lead | Time-box; reduce scope | Week 6 of Phase 0 without IaC framework decision |
| Counsel-engaged work delays Round 4 BLOCKERs | High | Schedule + Compliance | General Counsel | Engage counsel in Phase 0; not Phase 4 | Counsel response time > 2 weeks |
| Sequelae PH timezone reduces effective collaboration | Moderate | Velocity | Engineering Lead | Async-first; documented handoff; overlap windows | Cross-timezone PR cycle > 48 hours |
| Splink learning curve slows Phase 2 | Moderate | Schedule | Data Engineering Lead | Spike in Phase 1; training; vendor support | Phase 2 week 4 without working Splink integration |
| HIPAA-aware compliance review slows release cadence | High | Velocity | Compliance Lead | Pre-approval workflows; embedded compliance reviewer | Compliance review > 1 week per release |
| Agent token cost exceeds budget | Low-Moderate | Cost | PM | Track per-story; cap per-stream; alternative review patterns | Monthly burn > 1.5x budget |

**Effort:** M (initial); ongoing review.

---

### P-028: Schedule risk per phase — FINDING

**Where:** Not addressed.

**Why it matters:** Each phase has unique risks. Phase 0 = foundation-heavy (high overrun risk). Phase 2 = highest BR concentration (complexity risk). Phase 4 = external auditor dependency.

**What's needed:** Per-phase risk profile + mitigation.

**Effort:** S.

---

### P-029: Scope creep prevention — FINDING

**Where:** ARD §"Open Architectural Questions" lists 6 questions. As answers come in, scope grows.

**Why it matters:** Each open question, if answered unfavorably, expands scope. Add new partner data formats: scope grows. Add Sequelae PH ML feature engineering path (Round 1 F-014): scope grows. Without scope-creep prevention, Phase 1 doesn't end.

**What's needed:** Scope baseline (BRD frozen at version date); change management process for amendments; impact assessment per amendment.

**Effort:** S (process); ongoing.

---

### P-030: External dependency tracking — FINDING

**Where:** Implicit.

**Why it matters:** External dependencies are project-level risks:
- BAA execution per partner (legal, partner ops)
- Counsel-engaged work (Round 4 BLOCKERs)
- Privacy Officer + Security Officer hire (Round 4 L-036, L-037)
- External attestation auditor selection and engagement
- Lore application team's roadmap (joint UX work, joint integration testing)
- Partner-side technical readiness (SFTP setup, file format readiness)

Each has its own timeline. Project must track and surface delays.

**What's needed:** External dependency tracker; weekly review; escalation triggers.

**Effort:** S.

---

### P-031: Cross-team dependencies — FINDING

**Where:** Not addressed at PM level.

**Why it matters:** Lore application team, partner ops team, compliance team — each has its own backlog. Cross-team dependencies need explicit management.

**What's needed:** Cross-team dependency tracking; PI-level coordination.

**Effort:** S.

---

## 6. Communication and Stakeholder Engagement

### P-032: Stakeholder communication plan — BLOCKER

**Where:** Round 7 E-035 raised executive reporting; broader stakeholder plan missing.

**Why it matters:** Stakeholders by category:
- **Executive**: monthly highlights; quarterly strategic reviews; ad-hoc on existential issues (Round 7)
- **Board**: quarterly; ad-hoc on existential issues (Round 7)
- **Engineering teams**: daily standups; sprint reviews; PI demos; retrospectives
- **Compliance / Legal**: weekly during high-engagement periods (Round 4 BLOCKER work); monthly otherwise
- **Lore application team**: weekly cross-team sync; sprint demos; SLA reporting
- **Partners**: per-partner cadence (account team-driven)
- **Members**: at-incident only (breach notifications) or per ongoing communication strategy
- **Regulators**: at-inquiry only

Each has different content, cadence, format.

**What's needed:** RACI matrix + stakeholder communication plan. Lives in PM artifact.

**Effort:** M.

---

### P-033: Status reporting cadence — FINDING

**Where:** Round 7 E-035 covered executive cadence.

**Why it matters:** Status reports trickle up: team-level sprint reports → ART-level PI reports → executive dashboards → board reports. Cadence and content per level.

**What's needed:** Status reporting templates per level.

**Effort:** S.

---

### P-034: Sprint review / system demo cadence — FINDING

**Where:** Not addressed.

**Why it matters:** Sprint review demonstrates team progress to stakeholders. System demo (SAFe) demonstrates integrated cross-team progress. Each sprint = sprint review per team; each PI = system demo across teams.

**What's needed:** Demo cadence; participant lists; format.

**Effort:** S.

---

### P-035: Retrospective cadence at multiple levels — FINDING

**Where:** CLAUDE.md has per-phase retros. Sprint retros and PI retros not specified.

**Why it matters:** Retros at multiple levels:
- Sprint retro (team-internal; what worked / didn't / change next sprint) — every 2 weeks
- PI retro / Inspect & Adapt (ART-wide) — every quarter
- Phase retro (strategic-level; in CLAUDE.md) — per phase
- Annual retro (program-level)

Each has different scope and outcome.

**What's needed:** Multi-level retro cadence. Sprint retros are most frequent and most missed under pressure.

**Effort:** S.

---

### P-036: Knowledge management — FINDING

**Where:** Not addressed.

**Why it matters:** Mixed Sequelae PH / US / agent team — knowledge silos risk. Standard:
- Documentation in repo (already partial)
- Onboarding docs (Round 5 D-080)
- Searchable knowledge base
- Recorded demos / walkthroughs
- Architecture diagrams (Round 5 D-081)

**What's needed:** Knowledge management strategy. Lives in tooling decision (Confluence? Notion? Backstage?).

**Effort:** M.

---

## 7. Change Management

### P-037: Change request process — BLOCKER

**Where:** ARD §"Closing Note" mentions amendments. Change request process unspecified.

**Why it matters:** Changes happen. BR amendments. ARD amendments. Scope additions. Schedule slips. Without process, changes are ad-hoc; impact analysis is missed; stakeholders are surprised.

**What's needed:** Change request process:
- Submission: who can request, in what form
- Triage: who reviews, against what criteria
- Impact assessment: schedule, scope, cost, risk
- Approval: per change tier (small / medium / large)
- Communication: who's notified
- Tracking: change log

**Effort:** M (initial); ongoing.

---

### P-038: Scope change tracking — FINDING

**Where:** Not addressed.

**Why it matters:** Original scope vs. current scope. Variance reporting. Story count, point estimate, delivery date evolution tracked over time.

**What's needed:** Scope baseline + variance report.

**Effort:** S (process); ongoing.

---

### P-039: Schedule change tracking — FINDING

**Where:** Not addressed.

**Why it matters:** Plan vs. actual. Phase end-date variance. Per-PI commit vs. delivered.

**What's needed:** Schedule variance reporting.

**Effort:** S.

---

### P-040: Decision log — FINDING

**Where:** Round 7 E-031 raised decision authority. Decision log is its operational expression.

**Why it matters:** Project-level decisions (separate from architectural ADRs) include: priority changes, resource reassignments, sprint commitment changes, vendor selections, milestone reschedules. Without log: decisions repeat, context lost.

**What's needed:** Decision log (lightweight; project-tool-resident).

**Effort:** S.

---

## 8. Quality and Definitions

### P-041: Acceptance criteria for BRs — FINDING

**Where:** BRs have enforcement mechanisms. Delivery-level acceptance criteria distinct.

**Why it matters:** BR-303 enforcement: "test asserting the feed-quarantine trigger fires at the threshold boundary." That's design-time spec. Delivery-level AC: "Given a feed at threshold-1, when processed, then no quarantine event; given threshold+1, then quarantine event." Specific, testable, demonstrable.

**What's needed:** Per-BR delivery-level AC. Captured at story-decomposition (P-021).

**Effort:** S per BR; M total.

---

### P-042: Test plan per BR — FINDING

**Where:** Implicit in CLAUDE.md TDD discipline.

**Why it matters:** PM perspective: each BR has a testable expression. Story-level acceptance tests; integration tests; end-to-end tests. Test pyramid per BR.

**What's needed:** Test plan template; applied per BR during decomposition.

**Effort:** S.

---

### P-043: Demo strategy per BR — FINDING

**Where:** Not addressed.

**Why it matters:** Sprint demos show working software to stakeholders. Each BR has a demo path: synthetic data → trigger → expected outcome → audit visible. Demo strategy designed during story decomposition.

**What's needed:** Per-BR demo specification. Captured at decomposition.

**Effort:** S.

---

## 9. Hybrid Specifics

The user said "hybrid." Some elements of the program are agile-shaped; others are not.

### P-044: Hybrid waterfall + agile structure — FINDING

**Where:** Not addressed.

**Why it matters:** Some work is fundamentally waterfall-shaped:
- Counsel-engaged work (Round 4 BLOCKERs): drafted, reviewed, ratified (sequential)
- BAA negotiation (sequential; counsel-led)
- Attestation engagement (auditor-driven; sequential phases)
- Regulatory submission / response (deadline-driven; sequential)

Other work is agile-shaped:
- Engineering iteration
- UX research
- Operations tuning

Hybrid coordination is the PM's challenge. Non-agile work has dependencies on agile work and vice versa.

**What's needed:** Hybrid coordination model:
- Waterfall workstreams have phase gates aligned to agile PI boundaries
- Agile workstreams have non-blocking dependencies on waterfall checkpoints
- PM coordinates across paradigms

**Effort:** M.

---

### P-045: Phase-gate vs continuous flow — FINDING

**Where:** Phases have exit criteria (gate-based). Continuous flow within phases unaddressed.

**Why it matters:** Within a phase, continuous flow per story (Kanban-style) or batch per sprint? Different cadence for different work types.

**What's needed:** Per-workstream flow model.

**Effort:** S.

---

### P-046: Compliance milestones gating engineering — FINDING

**Where:** Implicit.

**Why it matters:** BAA execution gates partner data flow. Privacy Officer designation gates compliance program. Each is a non-engineering milestone that gates engineering work. Schedule must reflect.

**What's needed:** Compliance milestone calendar; integration with engineering schedule.

**Effort:** S.

---

## 10. Roles and Authority

### P-047: Product Owner role — BLOCKER

**Where:** Not addressed.

**Why it matters:** Every backlog needs an owner. Per scaled-agile team, Product Owner (PO) prioritizes. With multiple teams, Product Manager (PM) coordinates POs. Without explicit PO assignment, prioritization is ad-hoc, contested, or absent.

**What's needed:** PO designation per squad; PM designation overall. Roles per Round 7 E-031 decision authority.

**Effort:** S.

---

### P-048: Scrum Master / RTE role — FINDING

**Where:** Not addressed.

**Why it matters:** Scrum Master facilitates team-level ceremonies; RTE (Release Train Engineer in SAFe) facilitates ART-level ceremonies. Without these, ceremonies happen but lack discipline.

**What's needed:** SM per team; RTE per ART (likely 1 RTE for the whole platform program at this stage).

**Effort:** S.

---

### P-049: Architect role in agile — FINDING

**Where:** Round 7 E-032 raised ARB. SAFe System/Solution Architect role is its agile expression.

**Why it matters:** Continuous architecture (vs. upfront): system architect participates in ceremonies, refines architecture incrementally, makes architectural decisions in flight.

**What's needed:** Architect role assigned per ART. Participates in PI planning, system demo, I&A.

**Effort:** S.

---

### P-050: Product Management vs Product Owner — FINDING

**Where:** Not addressed.

**Why it matters:** SAFe distinguishes:
- **Product Manager**: external-facing, customer-validated; owns ART-level program backlog
- **Product Owner**: team-facing, sprint-validated; owns team backlog

For this platform, PM-equivalent owns the BRD priorities and partner relationships; PO-equivalent owns squad-level backlog.

**What's needed:** Role distinction; assignments.

**Effort:** S.

---

## 11. Tooling

### P-051: Project management tooling decision — FINDING

**Where:** Round 5 D-064 raised feature flags; PM tooling distinct.

**Why it matters:** PM tool choice affects every other PM concern. Considerations:
- SAFe-native (Jira's SAFe edition, Atlassian Plans)
- Lightweight (Linear, Asana, Notion projects)
- Integrated with code (GitHub Projects, Linear)
- Agent-API friendly (which tools have good APIs for agent integration)

**What's needed:** Tool decision.

**Effort:** S (decision); M (setup).

---

### P-052: Roadmap visualization — FINDING

**Where:** Not addressed.

**Why it matters:** Roadmap (Now / Next / Later) communicates direction without committing to dates beyond the next 1-2 quarters. Internal vs. partner-facing roadmaps differ.

**What's needed:** Roadmap format; cadence (quarterly refresh); audience-specific versions.

**Effort:** S.

---

### P-053: Capacity planning tooling — ADVISORY

**Where:** Implicit.

**Why it matters:** Forecasting team capacity over multi-quarter horizon helps spot constraint windows. Tools: Tempo, Float, in-house.

**What's needed:** Capacity tool decision (could defer until team is larger).

**Effort:** S.

---

## 12. Specific Business Rule Revisits (PM Lens)

The user explicitly directed: revisit business rules with PM eyes.

### P-054: BR-101 (Tiered match) — sized as multiple stories — FINDING

**PM observation:** BR-101 is one rule; implementation is many stories:
- Tier 1 deterministic anchor (story)
- Splink integration (story or epic)
- Tier 2 / 3 / 4 score-based decisions (story per tier)
- Threshold configuration (story)
- Score breakdown persistence (story)
- Reviewer queue integration for Tier 3 (story)
- Audit emission for each tier (story)

Probably 8-12 stories. Estimate: 30-50 story points across 2-4 sprints. PM-relevant question: which stories first? Recommendation: Tier 1 + audit + queue stub (Phase 1 minimum); Tier 2/3/4 + Splink (Phase 2).

**What's needed:** BR-101 epic with story-level decomposition.

---

### P-055: BR-201 (State machine) — foundational dependency — FINDING

**PM observation:** State machine is foundation. BR-101 depends on it (matches result in transitions); BR-401 depends on it (Verification reads state); BR-501 depends on it (state changes audit-emit). High dependency-fan-out → critical path candidate.

**Implication:** Phase 1 must include state-machine implementation; cannot be deferred.

---

### P-056: BR-401-405 (Verification API) — UX dependency — FINDING

**PM observation:** Round 6 BLOCKERs (U-001 verification failure UX, U-002 lockout recovery UX) are dependent on Verification implementation. Engineering and UX work must coordinate. PM-relevant: parallel tracks with explicit sync points.

**Implication:** Verification engineering and Lore application UX teams need PI-level alignment.

---

### P-057: BR-501-505 (Audit) — cross-cutting — FINDING

**PM observation:** Audit emission is cross-cutting; every BR-implementation story touches it. Without unified audit primitive (currently empty per HIPAA_POSTURE.md), each story implements its own. Without unification: drift.

**Implication:** Audit primitive (shared/security/audit) must precede most other implementation work. Phase 1 critical-path item.

---

### P-058: BR-606 (Replay) — late-phase — FINDING

**PM observation:** Replay is BR-606. It depends on stable canonical model (BR-201), idempotent stages (BR-601-604), and audit (BR-501). Implementation in Phase 2 or later.

**Implication:** PM-relevant: defer to Phase 2; signal early to ops who may want this for incident response.

---

### P-059: BR-701-704 (Deletion) — Phase 2+ — FINDING

**PM observation:** Deletion has cross-cutting impact: vault, canonical model, audit chain, ledger. Implementation effort high; can't safely be Phase 1.

**Implication:** Phase 2 scope; right-to-deletion policy commitment needs early communication to members.

---

### P-060: XR-001/XR-002 (Configuration) — must precede most BRs — FINDING

**PM observation:** Layered configurability is foundation. Without it, rules with parameters can't be implemented per spec. Phase 0.5 / early Phase 1 work.

**Implication:** Configuration management library is critical-path dependency.

---

## 13. Achievability Assessment

The user asked: "Is this plan actually achievable?"

### P-061: Achievability — current state — BLOCKER

**Where:** Not testable as written.

**Why it matters:** Per the TL;DR, "achievable" is unanswerable without:
1. Timeline estimates (P-001)
2. Capacity model (P-002)
3. Critical path (P-003)
4. Dependency map (P-004)
5. Framework choice (P-008)

These are prerequisite to any achievability judgment.

Once those exist, achievability test:
- Capacity per phase × phase duration ≥ phase scope (in story points)?
- Critical path doesn't exceed phase duration?
- External dependencies resolve in time?
- Risk margin available?

**Reviewer's preliminary assessment** (caveats: without capacity model; without team confirmation):

| Phase | Likely duration (mixed agent/human team of 6-12) | Achievable? | Caveats |
|---|---|---|---|
| Phase 0 (foundation) | 8-14 weeks | Yes | Dependent on IaC framework decision velocity; counsel engagement timely |
| Phase 1 (single partner E2E) | 12-20 weeks | Yes | Dependent on partner readiness; UX parallel work |
| Phase 2 (production cutover, all v1 BRs) | 16-26 weeks | Conditional | Dependent on Splink learning curve; deletion ledger; audit chain; reviewer UX |
| Phase 3 (multi-partner scale) | 8-16 weeks | Yes | Dependent on configuration-driven onboarding actually being configuration-driven |
| Phase 4 (attestation prep + audit) | 12-26 weeks | Conditional | Dependent on attestation choice (HITRUST = longer; SOC 2 = shorter); auditor cadence |
| **Total** | **56-102 weeks (1-2 years)** | Conditional | Dependent on the above + addressing the cross-round BLOCKERs |

The total range is wide. With ~95-100 unique BLOCKERs across 8 review rounds, addressing them takes time. Phase 0 + Phase 1 work cannot proceed without ~30-40 of the BLOCKERs resolved (counsel work, IaC decision, framework choice, capacity model, etc.).

**Verdict**: the plan is *likely achievable* in the 18-24 month range with disciplined execution. *Less than 18 months* is likely unrealistic given the BLOCKER backlog. *More than 30 months* indicates the scope exceeds organizational capacity and re-scoping is needed.

**What's needed:** Bottom-up estimation by the actual team (replaces this reviewer's top-down estimate); formal achievability analysis at PI planning.

**Effort:** L (the actual planning work).

---

## 14. Cross-Cutting

### P-062: Compliance overhead vs. agile velocity — FINDING

**Where:** Round 4 BLOCKERs imply compliance overhead.

**Why it matters:** HIPAA processes can slow agile delivery by 20-40%. Documentation, sign-offs, audits, training records — each has time cost. PM must budget.

**What's needed:** Compliance overhead allocated in capacity model. Embedded compliance reviewers (vs. gate-based reviews) reduce friction.

**Effort:** S.

---

### P-063: Team-of-teams coordination at scale — FINDING

**Where:** Round 5 D-071 covered service catalog. PM coordination here.

**Why it matters:** As ART grows from 1 squad to 4-12 squads, coordination overhead grows. Scrum-of-scrums, PO-sync, system architect sync, communities of practice — each is a meeting cost but enables coordination.

**What's needed:** Coordination layer scales with team count. Watch over-meeting tax.

**Effort:** S; ongoing.

---

### P-064: Continuous improvement — FINDING

**Where:** Phase retros exist (CLAUDE.md). Cross-PI continuous improvement at program level.

**Why it matters:** Each PI's I&A produces improvement actions. Without tracking, actions die. Action tracking + completion gates closing of I&A.

**What's needed:** I&A action tracking; completion review at next PI.

**Effort:** S.

---

### P-065: Onboarding agents and humans — FINDING

**Where:** Round 5 D-080 covered engineer onboarding; PM perspective broader.

**Why it matters:** Onboarding for:
- New human engineer (Round 5 D-080)
- New PO (project context, BRD/ARD familiarity, partner relationships)
- New compliance staff (regulatory knowledge transfer)
- New agent role (CLAUDE.md update, role-specific context)
- New stakeholder (program orientation)

Each has standardized path.

**What's needed:** Onboarding programs per role; tested with each new joiner.

**Effort:** M.

---

### P-066: Burndown / burnup — ADVISORY

**Where:** Not addressed.

**Why it matters:** Sprint burndown is team-level; release burnup is program-level. Visualizes progress; spots trouble early.

**What's needed:** Burndown / burnup in PM tool.

**Effort:** S; tool-driven.

---

### P-067: Cumulative flow diagram — ADVISORY

**Where:** Not addressed.

**Why it matters:** CFD shows WIP, throughput, lead time. Spots bottlenecks (where work piles up).

**What's needed:** CFD in PM tool.

**Effort:** S.

---

### P-068: WIP limits — ADVISORY

**Where:** Not addressed.

**Why it matters:** Without WIP limits, work-in-progress balloons; lead time grows; quality drops. Standard: WIP limit per state per team.

**What's needed:** WIP limit policy.

**Effort:** S.

---

## 15. Specific Findings Cross-Referenced

### P-069: Round 7 E-001 (business value per rule) — PM application — FINDING

**PM observation:** Round 7 raised business value at executive level. PM application: business value drives WSJF prioritization (cost of delay component). Without business value, prioritization is gut feel.

**Implication:** Round 7 E-001 BLOCKER must resolve before WSJF prioritization can be applied.

---

### P-070: Round 5 D-022/D-023 (SLI/SLO) — PM cadence — FINDING

**PM observation:** Round 5 raised SLI/SLO BLOCKERs. PM cadence: SLO compliance is reviewed per PI; SLO breach pattern triggers Inspect & Adapt action items.

**Implication:** SLO must be defined before PI 1 starts; SLO review is recurring agenda item.

---

### P-071: Round 4 BLOCKERs (compliance) — phase distribution — FINDING

**PM observation:** Round 4 has 22 BLOCKERs. Many counsel-engaged; not bursty work. Distribute across phases:
- Phase 0: Privacy Officer + Security Officer designation; counsel engagement plan; foundational P&P; PHI inventory; risk assessment
- Phase 1: NPP authoring; first BAA; first partner data sharing agreement
- Phase 2: Right of Access workflow; complaint procedure; breach notification infrastructure; state law matrix
- Phase 3: subprocessor reviews; partner-side deletion contracts
- Phase 4: full attestation engagement; remaining compliance polish

**Implication:** Phase distribution prevents end-loading.

---

### P-072: Round 6 BLOCKERs (UI/UX) — phase distribution — FINDING

**PM observation:** Round 6 has 17 BLOCKERs. UX work is iterative (research, prototype, test, refine). Distribute:
- Phase 0: design system commitment; user research program plan; accessibility commitment; inclusive design framework
- Phase 1: verification failure UX (BR-401 implementation must include); lockout recovery service blueprint; member rights workflow
- Phase 2: reviewer UX with tokenized data; audit log search UX
- Phase 3: scaling UX (multi-partner reviewer workload)
- Phase 4: comprehensive accessibility audit; user research summary

**Implication:** UX work parallels engineering; not deferred to "later."

---

## Summary triage

| Severity | Count | Examples |
|---|---|---|
| BLOCKER | 16 | Timeline estimates (P-001), Capacity model (P-002), Critical path (P-003), BR dependency map (P-004), Framework choice (P-008), PI cadence (P-009), Agent role definition (P-013), Agent capacity model (P-014), BR decomposition into stories (P-021), PM tool decision (P-022), Delivery risk register (P-027), Stakeholder communication plan (P-032), Change request process (P-037), Product Owner designation (P-047), Achievability test (P-061) |
| FINDING | 49 | Estimation methodology, velocity assumptions, buffer policy, sprint cadence, ceremony cadence, cross-team forum, agent handoff protocol, DoD with agents, agent quality at scale, token cost, agent escalation, multi-agent coordination, DoR, refinement cadence, prioritization framework, story format, schedule risk, scope creep prevention, external dependency tracking, cross-team dependencies, status reporting, demo cadence, retro cadence, knowledge management, scope change tracking, schedule change tracking, decision log, AC for BRs, test plan per BR, demo per BR, hybrid coordination, phase-gate vs flow, compliance milestones, SM/RTE roles, architect in agile, PM vs PO, PM tooling, roadmap viz, BR-101 decomposition, BR-201 critical path, BR-401-405 UX dependency, BR-501-505 cross-cutting, BR-606 late-phase, BR-701-704 Phase 2+, XR-001/002 foundation, compliance overhead, team coordination at scale, continuous improvement, onboarding, R7 E-001 application, R5 SLO PM cadence, R4 compliance phase distribution, R6 UX phase distribution |
| ADVISORY | 11 | Capacity tool, agent context mgmt, burndown/burnup, CFD, WIP limits, plus a few smaller items |
| **Total** | **76** | |

---

## Cross-round summary (all eight rounds)

| Round | Lens | BLOCKERS | FINDINGS | ADVISORIES | Total |
|---|---|---|---|---|---|
| 1 | Principal Architect | 6 | 14 | 5 | 25 |
| 2 | Chief Programmer | 13 | 37 | 10 | 60 |
| 3 | Principal Security | 18 | 47 | 9 | 74 |
| 4 | Compliance / Legal | 22 | 44 | 9 | 75 |
| 5 | Principal DevOps | 18 | 44 | 9 | 71 |
| 6 | Principal UI/UX | 17 | 47 | 11 | 75 |
| 7 | Executive | 16 | 39 | 11 | 66 |
| 8 | Project Manager | 16 | 49 | 11 | 76 |
| **Combined (with overlap)** | — | **126** | **321** | **75** | **522** |

After de-duplication across all eight rounds: **~105-115 unique BLOCKERs**.

---

## What this round specifically owns

What I could surface that prior rounds couldn't:

1. **Timeline estimation and achievability test** — the user's explicit ask
2. **Capacity model** including agents — distinct from infrastructure capacity (Round 5)
3. **Critical path analysis** — within and across phases
4. **BR dependency map** — engineering depends on this; PM owns it
5. **Scaled agile framework choice** with agent adaptation
6. **Agent role in scaled agile** — emerging practice; PM-led decision
7. **Multi-agent coordination** — beyond CLAUDE.md's single-stream pattern
8. **BR decomposition into delivery stories** — translates BRD policy to executable work
9. **Delivery-level risk register** — distinct from executive (Round 7) and engineering risks
10. **Stakeholder communication plan** — operational expression of Round 7's strategic communication
11. **Change request process** — manages amendments without paralysis
12. **Product Owner / PM / RTE / Architect role definitions** in scaled agile
13. **PM tooling decision** — consequential for every other PM concern
14. **Compliance + UX phase distribution** — translates Round 4 / Round 6 BLOCKERs into phase plans
15. **Hybrid waterfall + agile coordination** — for compliance and counsel-engaged work
16. **Achievability assessment** — the bottom-line answer to the user's question

---

## What this review did NOT cover

Out of scope for PM lens:

- Architectural decomposition (Round 1)
- Code-level discipline (Round 2)
- Security technical controls (Round 3)
- Regulatory mandates (Round 4)
- Operational engineering (Round 5)
- User experience design (Round 6)
- Strategic / executive concerns (Round 7)
- Domain correctness (DE Principal — not yet conducted)

These belong to other reviewers. This round focused on the *delivery* gaps — when, by whom, in what order, with what cadence, under what risk surface.

---

## Closing note on achievability

Direct answer to the user's question: *"Is this plan actually achievable?"*

**The plan, as currently expressed in BRD/ARD, is not testable for achievability.** No timeline. No capacity. No critical path. No dependency map. No framework. No backlog at story level. The achievability question presumes a plan; what exists is a specification.

**The platform itself is achievable at scope** for a 6-12 person mixed agent/human team with discipline, in approximately 18-24 months end-to-end. This is reviewer judgment, not team estimation. It assumes:
- ~95-100 unique cross-round BLOCKERs are addressed (some at phase 0, some throughout)
- Counsel engagement is timely
- Privacy/Security Officers are designated early
- Sequelae PH timezone collaboration is well-managed
- Agent capacity is leveraged appropriately (not over-relied-on)
- Scope creep is managed
- Phase 4 attestation is realistic for chosen framework (HITRUST is longer than SOC 2)

**The plan is *not* achievable in less than 12 months** at full v1 scope. Phase 0 alone, with the cross-round BLOCKER backlog, is likely 8-14 weeks.

**The plan is *also not* worth proceeding without addressing the PM BLOCKERs above.** Without timeline, capacity, critical path, framework, and backlog — execution will be reactive. Reactive execution in regulated healthcare is the path to schedule slips, compliance gaps, and member harm.
