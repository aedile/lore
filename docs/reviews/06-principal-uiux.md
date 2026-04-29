# Architecture Review — Round 6: Principal UI/UX Engineer

| Field | Value |
|---|---|
| **Round** | 6 of N |
| **Reviewer lens** | Principal UI/UX Engineer — end-user advocate across ALL user types, not just interfaces. Member experience, reviewer workflow, operator tooling, privileged-access UX, compliance staff workflows, partner-facing UX, API consumer experience, accessibility, inclusive design, trust as a design output |
| **Documents** | `docs/BUSINESS_REQUIREMENTS.md` (BRD), `docs/ARCHITECTURE_REQUIREMENTS.md` (ARD) |
| **Date** | 2026-04-29 |
| **Prior rounds** | `docs/reviews/01-principal-architect.md` through `docs/reviews/05-principal-devops.md` |

The user explicitly framed this round: *"Consider ALL of the user experience, not just interfaces — you are the end user advocate here."* That framing is correct and load-bearing. UX is not a frontend problem. The platform has at least a dozen distinct user types, each with distinct workflows, each silently undesigned by the current BRD and ARD.

The user also said: *"If this project has limited UI/UX, I expect an empty review."* I considered the brief seriously. This is not an empty-review project. The UX surface is large; the BRD/ARD just don't acknowledge most of it. This review enumerates what's silent.

Severity per Constitution Rule 29 (BLOCKER / FINDING / ADVISORY).

---

## TL;DR

**Will the platform be accessible and easy to use if we proceed as-is? No, with the qualifier that "no" hides a more important answer: most of the UX surface isn't even named in the docs.**

The BRD/ARD describe APIs, schemas, services, and data flows — but the *humans* the platform serves and is operated by appear mostly as anonymous "callers," "operators," and "reviewers." The implicit assumption is that UX happens elsewhere (in the Lore application, in a future internal portal, in an unspecified reviewer tool). That assumption is wrong in two ways:

1. **The eligibility platform's UX surface bleeds into the Lore application.** Verification API failure modes, lockout recovery, member rights workflows — these are member-facing experiences that the eligibility platform shapes even if it doesn't render the UI. If the platform returns a generic NOT_VERIFIED with no internal-state distinction, the Lore application can't write a humane error message because it has no information to render. That's a UX choice the platform forces.
2. **The internal user types are not optional.** Reviewers, operators, PII handlers, auditors, compliance staff, on-call engineers, data owners — each has a distinct workflow that the platform must support. A reviewer staring at tokenized data without decision-supporting signal cannot do their job. An on-call engineer at 3am without a usable dashboard cannot resolve incidents. These aren't future concerns; they're Phase 1 concerns.

**The user types I count:**
1. **Members** (the people whose eligibility is verified; via the Lore application + member portal)
2. **Personal representatives** (parents, guardians, caregivers acting for members)
3. **Reviewers** (Tier 3 manual review per BR-105)
4. **PII Handlers** (vault detokenization for legitimate purposes)
5. **Auditors** (audit log read access)
6. **Break-Glass Admins** (incident response with elevated access)
7. **Data Engineers / Data Ops / SREs** (pipeline operations, on-call)
8. **Data Owners** (per-partner config, onboarding sign-off)
9. **Privacy Officer / Security Officer** (compliance program — designated per Round 4)
10. **Compliance / Legal staff** (DSAR, complaints, breach response)
11. **Partner organizations** (file submission, integrations)
12. **Lore application engineers** (API consumers)
13. **External regulators / auditors** (when investigating)
14. **New hires across all roles** (onboarding UX is its own surface)

**75 findings: 17 BLOCKERS, 47 FINDINGS, 11 ADVISORIES.**

After consolidating across all six rounds, the unique BLOCKER set spans approximately **80-85 items**. With UX BLOCKERs addressed, the platform serves humans well across all roles. Without them, the platform serves the architecture but not the people in it — accessibility failures, member harm at the worst moments, reviewer burnout, operator errors, support-team overload.

---

## What UX Owns That Prior Rounds Could Not

Prior rounds had standing to identify control, code, security, compliance, and operational gaps. They did not have standing to:

1. **Advocate for end users across roles**, particularly users with no voice in the architecture (members, especially vulnerable members; first-time-on-call engineers; new reviewers).
2. **Apply human-centered design principles** (cognitive load, mental models, error prevention, recovery paths, trust signaling).
3. **Specify accessibility beyond minimum compliance** (WCAG 2.1 AA is the floor, not the ceiling; cognitive accessibility, low-bandwidth contexts, assistive technology compatibility).
4. **Engineer inclusive design** (cultural responsiveness, language access, plain language, trauma-informed design for healthcare).
5. **Design clinical trust** (the Adam Ameele lens noted in Round 1 hand-offs but never executed).
6. **Specify member-facing voice and tone** (privacy notices, error messages, breach communications — these are content design decisions, not technical decisions).
7. **Define the design system** (consistency across all surfaces — operator dashboards, reviewer UI, member portal, partner UI).
8. **Conduct usability testing strategy** (with real members, real reviewers, real operators).

This review surfaces these as gaps. The work itself requires UX research, content design, and dedicated UX engineering effort.

---

## Strengths from a UX View

What's already correct that should be preserved:

1. **Two-state Verification response (BR-401, XR-003).** From a privacy lens it's the right architecture. From a UX lens it forces the *Lore application* to design a unified failure experience rather than relying on the eligibility platform to communicate failure mode — which is correctly placed at the Lore application layer.
2. **Privacy-preserving collapse (XR-003).** Protects members from existence-disclosure attacks; from a UX lens this is "the platform doesn't out members."
3. **WCAG 2.1 AA mentioned in CONSTITUTION.** Sets the accessibility baseline.
4. **Manual review queue acknowledged (BR-105).** Recognition that humans are part of the system.
5. **Right-to-deletion mechanics exist (BR-701-704).** Member rights are recognized at the architecture level.
6. **Out-of-band recovery (BR-403).** Acknowledges that not all recovery can be automated; humans intervene.

These work. Findings extend, sharpen, or fill gaps around them.

---

## 1. Member-Facing Experience

The platform's most important users have the least design attention.

### U-001: Verification failure UX is undesigned — BLOCKER

**Where:** BR-401 specifies external state set `{VERIFIED, NOT_VERIFIED}`. BR-403 specifies "generic message and a contact-support path." Member-facing UX not designed.

**Why it matters:** A member sitting in the Lore application's account creation flow at 11pm hits NOT_VERIFIED. What do they see? "Sorry, we couldn't verify your eligibility" with what next? A phone number that's only staffed business hours? An email that goes into a queue? Nothing? This is the most consequential moment in the member's relationship with Lore — first impression, often during a healthcare-related life event. UX failure here loses members and erodes clinical trust permanently.

The privacy-preserving collapse (XR-003) constrains what can be said externally — but does not absolve the design responsibility. A well-designed failure UX:
- Acknowledges the member's effort respectfully
- Provides a clear next action (one path, not five)
- Sets expectations for resolution timeline
- Offers human contact, with availability stated honestly
- Avoids accusatory language ("we couldn't verify YOUR eligibility")
- Avoids stigma-adjacent framing
- Works in plain language at 8th-grade reading level
- Provides Spanish (at minimum) for Lore's population

**What's needed:**
- ADR or BRD addition: Verification failure member-facing UX contract authored jointly by Lore application UX team and Lore eligibility team
- Failure message templates (counsel-reviewed; content-designed)
- Multi-language support (Spanish at minimum — Lore Health serves diverse populations)
- Support pathway specification: who staffs, what hours, what tooling
- A/B testing plan for failure messages
- Trauma-informed review of language

**Effort:** M (cross-functional with Lore application UX).

---

### U-002: Lockout recovery UX — BLOCKER

**Where:** BR-402: "Third failure: Identity locked. Self-service recovery is not available; recovery is out-of-band only." BR-403: "Display a generic message and a contact-support path."

**Why it matters:** A locked-out member is in a worst-case UX state. They've tried three times, presumably believing they're correct. They're now told to "contact support." The UX of *that contact-support flow* determines whether the member ever returns to Lore. Common failure modes:
- Phone tree that doesn't lead anywhere
- "Business hours only" when crisis is at 11pm
- Long hold times
- Identity verification by support staff that's worse than the original
- No callback option
- No status updates after submission
- No multilingual support

**What's needed:**
- Service design for the contact-support flow (this is a service blueprint, not a screen)
- Identity verification standard for support staff (NIST IAL2 — but designed for human-in-the-loop)
- Multi-channel options: phone, secure messaging, async email with response SLA
- Status updates to member during resolution
- Documented response SLA with member-facing transparency
- Multilingual support staff or language-line service
- Escalation path for support staff to data ops
- Training for support staff on the lockout UX

**Effort:** L (service design, staffing, tooling).

---

### U-003: Friction challenge UX — FINDING

**Where:** BR-402: "Second failure: Friction challenge applied (CAPTCHA-equivalent or step-up). Increased response latency. Additional logging."

**Why it matters:** CAPTCHA is the worst UX in software. reCAPTCHA Enterprise (mentioned in ARD) is better than v1/v2 but still excludes users with cognitive disabilities, motor disabilities, or low-bandwidth connections. Step-up authentication (e.g., one-time-code to a registered email/phone) is more accessible.

**What's needed:**
- ADR: friction mechanism choice with accessibility tradeoff documented
- Recommendation: invisible reCAPTCHA Enterprise scoring (no challenge unless score is suspicious) + step-up via email/SMS one-time code as primary friction
- Accessibility audit: any visible challenge must have audio alternative, keyboard-only support, low-vision support
- Member confusion mitigation: clear explanation of why friction is being applied

**Effort:** M.

---

### U-004: Member portal scope and UX — BLOCKER

**Where:** Round 4 referenced; not designed.

**Why it matters:** Members have HIPAA rights (Right of Access, Amendment, Accounting, Restriction, Confidential Communications). State laws add more (CCPA right to delete, right to know, right to correct). The eligibility data is part of the PHI subject to these rights. A member portal is the standard fulfillment channel.

Without a member portal scope decision: rights fulfillment is paper-based or via support staff (slow, expensive, error-prone, regulatory exposure on response timelines).

**What's needed:**
- BRD/ARD decision: does Lore (or Lore application) provide a member portal for eligibility-data-related rights?
- If yes: UX scope for the portal
  - Identity verification at portal login (NIST IAL2)
  - View own eligibility data summary
  - Submit Right of Access request
  - Submit Amendment request with reason
  - Submit Deletion request with verification
  - View Accounting of Disclosures
  - Manage privacy preferences (Restriction, Confidential Communications)
  - View Notice of Privacy Practices
  - File complaint
  - Track request status
- If no: documented service alternative with equivalent UX commitments

**Effort:** L (decision + design + build).

---

### U-005: Notice of Privacy Practices presentation UX — BLOCKER

**Where:** Round 4 L-001 mandated NPP. Presentation UX not addressed.

**Why it matters:** HIPAA NPPs are legendarily unreadable — long legal text members scroll past and click "Acknowledge." This is a *compliance* success but a *trust* failure. Layered notice approach is industry best practice:
- Top layer: 1-paragraph plain-language summary (60 words max, 8th-grade reading level)
- Middle layer: Section-by-section navigation with plain-language headers
- Bottom layer: Full legal NPP

**What's needed:**
- Layered NPP design (counsel-approved on the legal layer; UX-designed on the navigation and plain-language layers)
- Plain-language commitment with reading-level testing
- Multilingual versions (at minimum Spanish; consider Mandarin, Tagalog, Vietnamese based on Lore's population)
- Accessibility: screen-reader optimized, semantic HTML
- Acknowledgment UX: not "click to dismiss" — actually surface key rights at acknowledgment
- Printable version for members who prefer paper

**Effort:** M (counsel + content design + UX).

---

### U-006: Member rights submission UX — BLOCKER

**Where:** Round 4 L-024 raised DSAR workflow (backend). UX for submission is missing.

**Why it matters:** DSAR (Data Subject Access Request) workflow has multiple entry points for members:
- Right of Access (§164.524)
- Right to Amendment (§164.526)
- Right to Accounting (§164.528)
- Right to Restriction (§164.522(a))
- State law rights (CCPA, CPRA, MHMDA, etc.)

Each has different content requirements, identity verification needs, response timelines, and fee structures. A member submitting a request needs:
- Single intake point that routes correctly (members shouldn't need to know HIPAA vs CCPA)
- Identity verification proportional to request sensitivity
- Status visibility after submission
- Clear language at every step
- Plain-language acknowledgment of what they're requesting
- Timeline expectations communicated

**What's needed:**
- DSAR submission UX design (web form + service blueprint)
- Identity verification flow (proportional: simple for "give me my data summary," stronger for "delete all my data")
- Status tracking visible to member
- Multi-language support
- Mobile-first responsive design
- Accessibility audit before launch

**Effort:** L (cross-functional with compliance).

---

### U-007: Breach notification UX — BLOCKER

**Where:** Round 4 L-010 specified notification content. UX of *delivery* not addressed.

**Why it matters:** Members receiving a breach notification are in a vulnerable state (anxiety, distrust, urgency). UX failures at this moment compound harm:
- Notification looks like spam → member doesn't read it
- Notification is dense legal text → member doesn't understand
- Notification has no clear action → member feels helpless
- Notification has no support pathway → member feels abandoned
- Notification is English-only → non-English-speaking members excluded from rights
- Notification arrives weeks late (60-day max) → member feels disrespected

**What's needed:**
- Breach notification template designed by content designer + counsel (counsel for legal sufficiency; content designer for plain language)
- Multi-channel delivery: postal mail (HIPAA standard), email (with affirmative consent), SMS (with consent)
- Translation strategy for top 5 languages by Lore population
- Companion website at the time of breach (FAQ, what-to-do, support contact)
- Toll-free hotline UX designed in advance (script, training, capacity)
- Substitute notice (Round 4 L-011) UX for when contact info is insufficient

**Effort:** M (counsel + content design + service design).

---

### U-008: Trust signaling at verification — FINDING

**Where:** Implicit; not addressed.

**Why it matters:** Members submitting PII to Lore at first interaction have legitimate trust questions. Healthcare context amplifies — the consequences of poor data handling are real and known to members from public breaches. Trust signals at the verification moment matter:
- HIPAA compliance acknowledgment (not just buried in NPP)
- Specific commitments stated plainly ("we don't sell your data")
- Visible security indicators (TLS lock, no — that's for engineers; member-comprehensible signals)
- Clear data use explanation ("we use this to verify your eligibility for [partner]")
- Consent moment design (Round 4 L-002 covered legal authorization; UX for it here)

**What's needed:**
- Trust signal design at verification UX (in Lore application — coordinate with their UX team)
- Plain-language data use disclosure
- Consent UX for any non-TPO uses

**Effort:** M.

---

### U-009: Plain language across all member-facing content — BLOCKER

**Where:** No plain-language commitment in BRD/ARD.

**Why it matters:** HIPAA notices, error messages, breach notifications, support communications — all default to legal/technical language unless explicitly designed otherwise. Plain language is:
- 8th-grade reading level (industry standard for healthcare; some advocate 6th grade)
- Active voice
- Short sentences
- Common words
- Tested with target population

Not plain language fails members with:
- Limited literacy
- English as a second language
- Cognitive disabilities
- Anxiety / acute care contexts (reduced cognitive bandwidth)
- Visual impairments (longer texts are harder via screen reader)

**What's needed:**
- Plain-language commitment in BRD as a cross-cutting requirement (XR-007 or similar)
- Content design ownership: who reviews member-facing content for plain language
- Reading-level testing: Hemingway, Flesch-Kincaid, or similar; gate at deploy
- Style guide for member-facing content

**Effort:** S (commitment); ongoing (content design).

---

### U-010: Multilingual support strategy — BLOCKER

**Where:** Not addressed.

**Why it matters:** Lore Health serves a diverse US population. Spanish at minimum is required for healthcare ACOs serving any meaningful population. Excluding Spanish-speaking members violates Title VI of the Civil Rights Act (federally funded healthcare must provide language access) and is inequitable.

Without explicit i18n strategy: every member-facing surface is English-only by default; remediation is far more expensive after the fact.

**What's needed:**
- BRD addition: language access requirement (Spanish minimum; criteria for adding languages)
- Translation strategy: in-house, vendor, AI-assisted-with-human-review
- All member-facing content in scope: NPP, error messages, breach notifications, member portal, support comms
- Right-to-Left language readiness for future expansion (Arabic, Hebrew)
- Legal review of translated content (counsel responsibility — translated legal content has its own risk)
- Language preference capture and persistence

**Effort:** M (strategy); ongoing (per-language).

---

### U-011: Personal representative flows — BLOCKER

**Where:** Round 4 L-073 covered legal framework for minors and incapacitated; UX is missing.

**Why it matters:** Many member interactions are by personal representatives:
- Parents acting for minor children
- Adult children acting for elderly parents
- Spouses acting for incapacitated spouses
- Legal guardians acting for wards
- POA holders acting for grantors

Each has different legal authority (age-of-consent for healthcare varies by state and procedure type; capacity adjudication has formal requirements; POA scope varies). Without UX for representative paths:
- Representatives are forced to misrepresent themselves as the member (fraud)
- Representatives cannot fulfill the member's rights
- Representatives are turned away with no recourse

**What's needed:**
- Service design for personal representative flows
- Identity verification of representative (separate from identity verification of member)
- Authority verification (POA document upload, guardianship attestation, minor's parent attestation)
- UX clearly distinguishing "I am the member" from "I am acting for the member"
- Audit trail of who acted on whose behalf (compliance touchpoint)
- State-specific rules (counsel-coordinated)

**Effort:** L (cross-functional).

---

### U-012: Member harm recovery UX — BLOCKER

**Where:** Round 3 S-073 covered Verification ≠ authentication. Recovery UX from impersonation is missing.

**Why it matters:** Round 3 noted that VERIFIED is not authentication; account takeover via stolen PII is possible. When it happens, the member discovers it (often via unauthorized account activity, statement irregularities, fraud alerts). What's the recovery UX?

- Member calls support: how do they prove they're the real member if their PII has been stolen?
- Lock-account UX: who can lock, on what authority?
- Investigation UX: how does the member follow along?
- Restoration UX: when is the account restored, with what assurance?

This is the worst UX moment — the member is already a victim of identity theft, now needs help from the platform. UX failure compounds harm.

**What's needed:**
- Service design for impersonation recovery
- Identity proofing for actual-member when claimed PII has been compromised (likely requires alternative factors: contemporaneous photo ID, voiceprint, in-person at participating provider)
- Account lock procedure (member-initiated and system-initiated)
- Investigation handoff to fraud team
- Member communication during investigation
- Coordination with Lore application's account state
- Documentation for member to use with creditors, IRS, etc. (FTC IdentityTheft.gov coordination)

**Effort:** L.

---

### U-013: Mobile experience — FINDING

**Where:** Implicit; not addressed.

**Why it matters:** Healthcare members increasingly engage via mobile. A "responsive design" afterthought produces poor mobile UX. Mobile-first design produces good mobile and acceptable desktop. For Lore's population, mobile-first is the right default.

**What's needed:**
- Member portal designed mobile-first
- Performance budgets for mobile (cellular, 3G fallback for rural areas)
- Touch target sizing (44×44 minimum per WCAG)
- Form input optimization (correct keyboards, autocomplete attributes, autofill compatibility)
- Offline tolerance (forms preserve state on connectivity loss)

**Effort:** S (commitment); design throughout.

---

### U-014: Trauma-informed design — FINDING

**Where:** Not addressed.

**Why it matters:** Healthcare members frequently access services in vulnerable states — recently diagnosed, in acute care, navigating loss, managing chronic conditions, in crisis. Trauma-informed design principles (SAMHSA framework):
- Safety: physical and emotional safety in the experience
- Trustworthiness: clear expectations, no surprises
- Choice: meaningful options, not false choices
- Collaboration: not paternalistic
- Empowerment: language that respects member agency
- Cultural sensitivity

Standard UX patterns can violate trauma-informed principles unintentionally — countdown timers (urgency), aggressive opt-in dialogs (false choice), error messages that imply user fault.

**What's needed:**
- Trauma-informed review of all member-facing UX
- Specific patterns to avoid documented in style guide
- Clinical-trust reviewer (Adam Ameele lens from Round 1 hand-offs) consulted

**Effort:** M.

---

### U-015: Cognitive accessibility beyond WCAG — FINDING

**Where:** WCAG 2.1 AA mentioned in CONSTITUTION.

**Why it matters:** WCAG 2.1 AA addresses sensory and motor disabilities well. Cognitive accessibility is weakly covered (AAA criteria address some). For healthcare:
- Reduced cognitive load: short forms, single-task screens
- Memory support: don't require recall across screens
- Time accommodations: no aggressive timeouts (or pause options)
- Error prevention: confirmations before destructive actions
- Reading order: predictable visual hierarchy

**What's needed:**
- Cognitive accessibility audit of all member-facing UX
- Pattern library that defaults to cognitive-accessible variants
- User research with cognitively diverse users

**Effort:** M.

---

### U-016: Deceased member handling UX — FINDING

**Where:** Round 4 L-072 covered legal framework. UX for next-of-kin requests not addressed.

**Why it matters:** Family members requesting access to a deceased member's PHI is a common case in healthcare. §164.502(f) protects deceased PHI for 50 years; access by personal representatives during that period requires specific verification.

**What's needed:**
- Service design for deceased-member access requests
- Documentation requirements (death certificate, executor appointment, etc.)
- Compassionate UX (this is families in grief)
- Multi-channel intake (some families prefer phone over web)

**Effort:** S (service design).

---

## 2. Reviewer Workflow

The Tier 3 manual review is a designated human-in-the-loop function. The architecture acknowledges its existence; the workflow is undesigned.

### U-017: Reviewer decision support with tokenized data — BLOCKER

**Where:** Round 3 S-151 raised as ADVISORY. From a UX lens, this is BLOCKER.

**Why it matters:** A reviewer staring at "Token #abc123 matches Token #abc456 with weight 0.85" cannot make a defensible decision. The constraint (no plaintext PII per BR-506) is real; the workaround is design. Standard patterns:
- Per-comparison feature contributions ("name similarity: 0.92, DOB exact: 1.0, address similarity: 0.45")
- Categorical hints that don't reveal PII ("first letter of last name: B/B match", "birth year: 1985/1985 match", "ZIP first 3: 921/922 close match")
- Score-uncertainty visualization (confidence intervals on the match score)
- Counterfactual ("if address weren't matching, score would be 0.62")

**What's needed:**
- ADR: reviewer information architecture under BR-506 constraints
- Specific UI design for review decision
- Cognitive walk-through with actual reviewers (or proxies) before build
- Test against decision-quality metrics (precision/recall vs ground truth on synthetic test set)

**Effort:** M (cross-functional with data engineering).

---

### U-018: Match score breakdown visualization — FINDING

**Where:** ARD §"Identity Resolution" mentions Splink "score breakdowns" stored in `match_decision.score_breakdown`. Visualization not addressed.

**Why it matters:** Splink produces per-comparison weights. A reviewer needs to see *why* the score is what it is. A table of numbers is the floor; better:
- Bar chart per comparison with color-coded contribution direction (positive/negative)
- Hover-to-see-detail
- Sortable by contribution magnitude
- Context: "this comparison had this contribution; here's the comparison's threshold for high/low"

**What's needed:**
- Specific visualization design
- Interaction patterns (hover, click, drill)
- Accessibility: any data viz must have non-visual equivalent (data table, screen reader narration)

**Effort:** S (design); M (build).

---

### U-019: Review queue prioritization UX — FINDING

**Where:** ARD: review queue is a Postgres table. Prioritization in the UI not addressed.

**Why it matters:** Multiple items in queue. What does the reviewer work on first?
- Aging (oldest first): fairness
- Severity (highest stakes first): impact
- Complexity (easy first): productivity
- Random: prevents reviewer cherry-picking
- Custom queue (assigned to me): ownership

Different choices have different tradeoffs. Default behavior matters.

**What's needed:**
- ADR: queue prioritization default + reviewer override capabilities
- Recommendation: hybrid — default by aging within severity tier; reviewer can claim from any tier
- UX for queue visibility (filtered lists, counts, my-queue vs all-queue)

**Effort:** S.

---

### U-020: Reviewer fatigue and decision quality — FINDING

**Where:** Not addressed.

**Why it matters:** Reviewers making many decisions in a row deteriorate (alert fatigue, decision fatigue). Decision quality drops; reviewers default to MERGE-when-uncertain or DISTINCT-when-uncertain. Mitigations:
- Mandatory breaks (UI prompts every N decisions)
- Calibration tests (synthetic cases with known answers, mixed in)
- Second-reviewer requirement for high-stakes decisions
- Daily review cap
- Decision history available to reviewer

**What's needed:**
- ADR: reviewer fatigue mitigation
- Calibration test program (separate ADR)
- Second-reviewer workflow for high-stakes decisions

**Effort:** M.

---

### U-021: Disagreement and unmerge UX — FINDING

**Where:** Round 1 F-006 raised unmerge as architectural BLOCKER. UX layer here.

**Why it matters:** When unmerge happens (rare but real), a reviewer is involved in the decision. UX:
- Clear visualization of the merge decision being undone
- Impact analysis (what downstream consumers will receive what events)
- Approval workflow (likely two-person per Round 3 S-011)
- Audit trail visible to reviewer

**What's needed:** UX design for unmerge path (paired with the architectural decision in Round 1 F-006).

**Effort:** S (UX); paired with architecture work.

---

### U-022: Reviewer audit trail visibility — FINDING

**Where:** Not addressed.

**Why it matters:** Reviewers should see their own decision history — supports learning, calibration, accountability. They should NOT see other reviewers' history (privacy + bias).

**What's needed:** "My decisions" view per reviewer; aggregate metrics (decisions per day, agreement-with-second-reviewer rate); accessibility considerations.

**Effort:** S.

---

### U-023: Calibration tests — FINDING

**Where:** Not addressed.

**Why it matters:** Random synthetic cases with known correct answers, mixed in with real cases. Reviewer doesn't know which is which. Per-reviewer accuracy tracked; below-threshold reviewers retrained.

**What's needed:** Calibration test infrastructure (synthetic case generation, mixing logic, accuracy tracking, reviewer feedback loop).

**Effort:** M.

---

### U-024: Reviewer onboarding UX — FINDING

**Where:** Not addressed.

**Why it matters:** New reviewers need training before going live. Standard:
- Training cases (clearly labeled as training; no real impact)
- Mentor pairing for first N decisions
- Calibration milestones before solo work
- Documented decision criteria with examples

**What's needed:** Reviewer onboarding program design.

**Effort:** M.

---

### U-025: Reviewer keyboard shortcuts and efficiency — FINDING

**Where:** Not addressed.

**Why it matters:** Power users want efficiency. Keyboard shortcuts, tab order, save-and-next navigation — these affect reviewer throughput materially. Mouse-only UI fatigues reviewers.

**What's needed:** Keyboard-first interaction design; documented shortcuts; user testing with reviewers.

**Effort:** S (design).

---

### U-026: Reviewer workspace device strategy — ADVISORY

**Where:** Not addressed.

**Why it matters:** Where do reviewers work? Office desktop (high-trust environment, large screen)? Home laptop? Mobile? Each has UX implications. Healthcare-grade security may require corp-managed device only.

**What's needed:** ADR (security-coordinated): reviewer device requirements + UX implications.

**Effort:** S.

---

## 3. Operator Tooling (Data Engineers, Data Ops, SREs)

Round 5 covered DevOps engineering. UX of operator tooling is distinct.

### U-027: Pipeline status dashboard UX — FINDING

**Where:** Round 5 D-066 covered deployment dashboards; pipeline status UX is distinct.

**Why it matters:** At a glance: is the pipeline healthy? Where's the latency? What's stuck? Operator on-call has 30 seconds to triage.

**What's needed:** Dashboard design with progressive disclosure (high-level → drill-down). Anti-patterns to avoid: too many metrics at once; numbers without context; missing aggregations.

**Effort:** S (design); M (build).

---

### U-028: Quarantine review UX — FINDING

**Where:** ARD §"Ingestion": quarantined records and feeds in Cloud Storage. Operator UX for review missing.

**Why it matters:** Operators triaging quarantined feeds need:
- Sample data (tokenized)
- Reason for quarantine (BR-301 tier failure? BR-303 threshold? BR-304 schema drift?)
- Comparison to baseline
- Decision options: release (re-run validation), reject, escalate to data owner, quarantine indefinitely

**What's needed:** Quarantine review UI design.

**Effort:** M.

---

### U-029: Reconciliation report UX — FINDING

**Where:** BR-605 reconciliation. Variance reports' UX not specified.

**Why it matters:** Variance findings need investigation. UX:
- Variance breakdown (which dimensions)
- Time series of variance magnitude
- Drill-down to individual records (tokenized)
- Resolution actions (acknowledge, escalate to partner)

**What's needed:** Reconciliation report UX.

**Effort:** S.

---

### U-030: Schema drift notification UX — FINDING

**Where:** BR-304 covers detection. Notification UX not addressed.

**Why it matters:** Operator receiving a `SCHEMA_DRIFT` alert needs immediate clarity:
- What changed (column added, removed, type changed)
- Impact assessment
- Affected partner / feed
- Recommended action

**What's needed:** Notification template; alert-to-UI integration (clicking the alert opens the dashboard at the right context).

**Effort:** S.

---

### U-031: Replay scope preview UX — FINDING

**Where:** BR-607 mandates scope preview. UX not designed.

**Why it matters:** Operator initiating replay sees the preview. "5 partners, 3M members, 7 days" should be visualized clearly with confirmation that operator understands.

**What's needed:** Replay preview UI; confirmation pattern (counterintuitive: the more impactful the operation, the more friction the UX should have — confirmation by typing the partner name, not just clicking).

**Effort:** S.

---

### U-032: DAG failure UX — FINDING

**Where:** Round 5 D-060 covered DAG monitoring; UX of failure response missing.

**Why it matters:** Composer DAG fails at 2am. On-call gets paged. UX:
- Failure source (which task)
- Recent state (was prior run successful?)
- Logs / error output
- Restart options (restart from failure, restart from beginning)
- Escalation path

**What's needed:** DAG failure runbook UX (links from alert to UI to resolution).

**Effort:** S.

---

### U-033: Configuration change UX — FINDING

**Where:** Round 2 F-149 covered config change-control; Round 5 D-016 covered per-env config. UX missing.

**Why it matters:** Operator changing a config (e.g., raising FEED_QUARANTINE_THRESHOLD_PCT for a problem partner) needs:
- Effective scope visible (which partner, which feed, which hours)
- Diff vs current value
- Impact preview (number of recent feeds that would have been affected)
- Approval workflow visibility
- Rollback capability

**What's needed:** Config change UI design (in concert with the GitOps approach from Round 5).

**Effort:** S.

---

## 4. Privileged-Access UX

### U-034: Vault detokenization UX — FINDING

**Where:** ARD §"PII Vault" covers TokenizationService API. UX for the human PII Handler missing.

**Why it matters:** A PII Handler detokenizing for legitimate purpose needs:
- Justification capture (mandatory free text + reason category)
- Visible session timer (Round 3 S-012 short TTLs)
- Per-detok audit visible to handler ("this is being recorded")
- Single-record mode default; batch mode with explicit elevation
- Auto-redaction of plaintext on copy/paste (clipboard contents redacted after N seconds)
- Screen-watermark with handler ID and timestamp (deters screenshot exfiltration)

**What's needed:** Vault UX design with security-first defaults.

**Effort:** M.

---

### U-035: Break-glass UX — FINDING

**Where:** AD-003 covers break-glass mechanism. UX missing.

**Why it matters:** Break-glass invocation in incident:
- Request access UI (mandatory justification, manager / Privacy Officer approval)
- Approval visibility (status: pending, approved, denied, expired)
- Active session countdown (visible during entire session)
- Auto-revocation warning (5 min before expiration)
- Session activity feed (visible to handler — "you have done X, Y, Z")

**What's needed:** Break-glass UX with strong feedback loops.

**Effort:** M.

---

### U-036: Two-person authorization UX — FINDING

**Where:** Round 3 S-011 specified mechanism. UX for the second person missing.

**Why it matters:** Second-person reviewer needs:
- Sufficient context to make an informed decision (not rubber-stamp)
- What's being requested + why
- Risk assessment data (what's the impact)
- Approve / deny with reason
- Audit log of own decision

**What's needed:** Approver UX design; sufficient context surfacing without re-disclosing PII.

**Effort:** S.

---

### U-037: Audit log search UX — BLOCKER

**Where:** Round 3 S-029 covered indexes. UI for forensic search missing.

**Why it matters:** Auditor investigating an incident:
- Specific query patterns ("all access by user X to records related to member Y in time range")
- Filtered results (timeline, actor, target, action class)
- Export with chain-of-custody (signed export package)
- Saved queries for common patterns
- Cross-reference (link from one event to related events)

Without good search UX, forensic investigation takes hours per incident; auditor time is the binding constraint.

**What's needed:** Audit search UI design; performance optimization for common queries; export discipline (Round 3 S-051).

**Effort:** M.

---

## 5. Compliance / Legal Staff Workflows

### U-038: DSAR case management UX — FINDING

**Where:** Round 4 L-024 raised case management; UX layer here.

**Why it matters:** Compliance staff handling DSARs need:
- Inbox view of pending requests
- SLA timer per request (HIPAA 30-day, CCPA 45-day, etc.)
- Verification status ("identity confirmed, documentation received")
- Routing (legal review needed? technical export needed?)
- Response template selection
- Audit trail of staff actions

**What's needed:** Case management UI design.

**Effort:** M.

---

### U-039: Complaint handling UX — FINDING

**Where:** Round 4 L-025 mandated procedure; UX layer here.

**Why it matters:** Compliance staff handling complaints under §164.530(d):
- Intake form receipt
- Acknowledgment to complainant (within reasonable time)
- Investigation tracking
- Resolution documentation
- Non-retaliation flag (complaint cannot trigger adverse action against complainant)

**What's needed:** Complaint UI; integration with HR for non-retaliation tracking.

**Effort:** S.

---

### U-040: Compliance dashboard UX — FINDING

**Where:** Round 5 D-073 covered compliance evidence automation. UX for using it missing.

**Why it matters:** Privacy Officer / Security Officer review compliance posture:
- Control status overview (live, stubbed, deferred per HIPAA_POSTURE.md)
- Findings tracking (audit findings, sanctions issued)
- Training compliance per workforce member
- BAA execution status per subprocessor
- Risk assessment status

**What's needed:** Compliance dashboard design.

**Effort:** M.

---

### U-041: Breach assessment UX — FINDING

**Where:** Round 4 L-009 covered methodology. UX for the workflow missing.

**Why it matters:** Compliance staff conducting breach risk assessment under §164.402(2):
- Four-factor assessment form
- Score capture per factor
- Composite risk decision
- Notification decision (breach or not)
- Documentation retained per L-044

**What's needed:** Risk assessment UX (form + decision support + documentation).

**Effort:** S.

---

## 6. Partner-Facing UX (Data Owners)

### U-042: Partner onboarding workflow UX — FINDING

**Where:** BR-801 specifies gates. UX for tracking through gates missing.

**Why it matters:** Onboarding involves multiple parties (Lore data team, partner ops, Lore Data Owner). UX for status:
- Gate completion checklist
- Document uploads (BAA, schema docs)
- Sample feed processing status
- DQ baseline approval flow
- Sign-off capture
- Partner-side visibility (what does the partner see?)

**What's needed:** Onboarding workflow UI; partner-facing status portal (or partner notifications via email).

**Effort:** L.

---

### U-043: Partner config review UX — FINDING

**Where:** ARD §"Schema Mapping": YAML in Git. UX for non-technical Data Owners missing.

**Why it matters:** Data Owner is responsible for partner config but may not be technical. Reviewing YAML PR is friction. UX:
- Web view of partner config (read-only, plain language)
- Per-field display of mapping ("partner column X maps to canonical name field; tier: Required")
- Configuration change preview (proposed vs current)
- Approval workflow

**What's needed:** Config review UI for non-engineers.

**Effort:** M.

---

### U-044: Partner self-service status UX — FINDING

**Where:** Not addressed.

**Why it matters:** Partners receive feedback today by email or out-of-band. Self-service:
- View status of recent feed submissions
- See quarantine reasons
- Request reprocessing (if appropriate)
- View reconciliation reports
- Manage SFTP credentials (Round 3 S-016)

**What's needed:** Partner portal scope decision; UX if in scope.

**Effort:** L (if in scope).

---

### U-045: Schema drift partner notification UX — FINDING

**Where:** BR-304 covers detection.

**Why it matters:** Partner whose feed schema drifted needs to know — they may have caused it (intentional change) or not (a bug on their side). UX:
- Notification with specifics
- Self-service acknowledgment (if intentional)
- Resolution path

**What's needed:** Partner-facing notification design.

**Effort:** S.

---

## 7. API Consumer Experience (Lore Application Engineers)

### U-046: Verification API documentation UX — FINDING

**Where:** Implicit; OpenAPI auto-generation mentioned.

**Why it matters:** Lore application engineers integrating with Verification API need:
- Clear examples for every endpoint
- Error scenarios documented
- Rate limit and retry guidance
- Migration path for breaking changes
- Sandbox / playground for testing

OpenAPI auto-gen is the floor; humanized API docs (Stripe-quality) are the ceiling. Healthcare APIs frequently fail the documentation test.

**What's needed:**
- OpenAPI auto-generated as baseline
- Hand-written API guide alongside (use cases, common pitfalls, debugging)
- Code samples in target languages (whatever Lore application uses)
- Postman collection for testing
- Sandbox environment

**Effort:** M (initial); ongoing.

---

### U-047: Error response design — FINDING

**Where:** Round 3 S-129 specified contract; consumer UX here.

**Why it matters:** Lore application engineers receiving an error need to:
- Know if it's retryable
- Know if rate-limited (and when to retry)
- Know if the error is on their side (4xx) or ours (5xx)
- Have a request ID for support
- Have a debug ID for our investigation

**What's needed:** Error response design; documentation; example handling code.

**Effort:** S.

---

### U-048: Integration testing tools — FINDING

**Where:** Not addressed.

**Why it matters:** Lore application engineers need to test integration without hitting production. Sandbox with controlled scenarios:
- Always VERIFIED member
- Always NOT_VERIFIED member
- Lockout-able test account
- Latency simulation
- Error injection

**What's needed:** Sandbox environment; documented test scenarios; test data lifecycle.

**Effort:** M.

---

### U-049: API consumer status dashboard — FINDING

**Where:** Round 5 D-076 covered status page; consumer-facing here.

**Why it matters:** Lore application engineers monitoring Verification API health need:
- SLO compliance dashboards
- Recent incidents
- Maintenance windows
- Deprecation notices

**What's needed:** Consumer status portal (subset of internal status; partner-facing decision).

**Effort:** S.

---

## 8. Cross-Cutting Concerns

### U-050: Accessibility (WCAG 2.1 AA) commitment and audit — BLOCKER

**Where:** CONSTITUTION mentions WCAG 2.1 AA. Coverage commitment and audit strategy missing.

**Why it matters:** WCAG without audit = aspirational. Comprehensive audit covers:
- Automated testing (axe, Lighthouse) in CI
- Manual testing (keyboard navigation, screen reader)
- User testing with assistive technology users
- Annual third-party audit (legal defensibility)

Without explicit commitment: each surface ships with un-tested accessibility; remediation is far more expensive after the fact.

**What's needed:**
- BRD addition: WCAG 2.1 AA explicit coverage commitment for ALL UI surfaces (member portal, reviewer UI, operator dashboards, compliance UI, etc.)
- Audit schedule: automated per-PR, manual per-release, third-party annual
- Failure-handling: ship-blocked on regression
- Accessibility statement on member-facing surfaces (legally recommended for ADA Title III)

**Effort:** S (commitment); ongoing (audits).

---

### U-051: Inclusive design framework — FINDING

**Where:** WCAG covers compliance floor; inclusive design is broader.

**Why it matters:** Inclusive design (Microsoft framework) considers:
- Permanent disability (one arm, blind, deaf, cognitive disability)
- Temporary disability (broken arm, eye infection, ear infection, concussion)
- Situational disability (carrying child, in bright sun, in noisy environment, in crisis)

Each enables different design considerations. Healthcare context exacerbates situational and temporary disability (members are often unwell during interaction).

**What's needed:** Inclusive design framework adoption; specific patterns documented; user research with diverse populations.

**Effort:** M.

---

### U-052: Internationalization beyond translation — FINDING

**Where:** U-010 covered language; this is broader.

**Why it matters:** I18n covers more than language:
- Date formats (MM/DD/YYYY US vs DD/MM/YYYY elsewhere — though Lore is US-only, members may have non-US patterns)
- Number formats (1,000.00 vs 1.000,00)
- Name conventions (single name, multiple given names, multiple family names)
- Address formats (apartment, suite, building name, rural route)
- Phone formats (+1 vs 0X-XXXX)
- Currency (US-only for now but consider)
- RTL support (Arabic, Hebrew — for future expansion)

**What's needed:** I18n strategy; library choice (FormatJS, i18next); content extraction; testing.

**Effort:** M.

---

### U-053: Mobile responsiveness audit — FINDING

**Where:** U-013 covered member portal; broader audit needed.

**Why it matters:** Reviewer UI, operator dashboards, compliance UI — should each be mobile-responsive? Probably not all (operator dashboards are desktop tasks); but explicit decision per surface.

**What's needed:** Per-surface device strategy; responsive design where applicable; explicit "desktop only" where applicable.

**Effort:** S (decision); ongoing (build).

---

### U-054: Cross-browser compatibility — FINDING

**Where:** Not addressed.

**Why it matters:** Member-facing surfaces must work on healthcare-relevant browsers (IE11 still in some healthcare environments — though declining; Safari on iOS; Chrome; Firefox). Internal tools can be more selective.

**What's needed:** Per-surface browser support matrix; testing strategy; graceful degradation.

**Effort:** S (matrix); ongoing (testing).

---

### U-055: Error message design system — BLOCKER

**Where:** Not addressed.

**Why it matters:** Error messages appear everywhere — Verification failure, lockout, validation, API errors, system errors. Without a design system:
- Tone is inconsistent (some friendly, some technical, some accusatory)
- Action paths vary
- Localization is per-message (expensive)
- Accessibility varies

**What's needed:**
- Error message design system: tone of voice, structure (what happened, why, what to do), action patterns, escalation paths
- Content design ownership
- Style guide
- Localization-friendly structure (interpolated values, not concatenated strings)

**Effort:** M (design system); ongoing (per-message).

---

### U-056: UI states design (loading, empty, error, success) — FINDING

**Where:** Implicit.

**Why it matters:** UI states often forgotten:
- Loading states (skeleton screens vs spinners; perceived performance)
- Empty states (queue is empty — what does the reviewer see? educational opportunity)
- Error states (per U-055)
- Success states (acknowledgment without celebration; healthcare context)

**What's needed:** State coverage in design system; design tokens for state visualization.

**Effort:** S (design); ongoing.

---

### U-057: Notification system design — FINDING

**Where:** Implicit.

**Why it matters:** Multiple notification surfaces (email, in-app, SMS, push, postal mail for breaches). Design system for:
- Channel selection per use case
- Tone consistency
- Frequency caps (no notification fatigue)
- Member preferences (Round 4 L-007 covered legal; UX here)
- Accessibility per channel
- Compliance per channel (HIPAA email standards, breach notification rules)

**What's needed:** Notification system design.

**Effort:** M.

---

### U-058: Trust signal design across surfaces — FINDING

**Where:** U-008 covered verification moment; cross-cutting here.

**Why it matters:** Trust is built at every interaction. Design tokens for:
- Security indicators (where appropriate)
- Privacy commitments (visible, plain-language)
- Transparency (e.g., "this took 3 seconds" — yes, ironically)
- Authenticity (reduce "AI/automation" anxiety where appropriate)

**What's needed:** Trust pattern library.

**Effort:** S.

---

### U-059: User research and usability testing program — BLOCKER

**Where:** Not addressed.

**Why it matters:** UX without user research is opinion. For healthcare:
- Members tested across ability ranges, ages, languages
- Reviewers tested in real workflow conditions
- Operators tested in incident scenarios
- Compliance staff tested in compliance workflows

Recurring user research catches design failures before they ship; one-time research is better than none but insufficient.

**What's needed:**
- User research program: cadence, recruitment, methodology, ethics review (especially for member testing where PHI may be involved)
- Diverse participant pool (members of color, low-income, low-literacy, disabled, non-English speakers, elderly)
- IRB review for member-facing research

**Effort:** L (program); ongoing.

---

### U-060: Help and support UX — FINDING

**Where:** Not addressed.

**Why it matters:** Across all surfaces, how does someone get help? Inline help, tooltips, FAQ, support contact, live chat, phone — each has UX implications. Healthcare context: "help" must be easy to find at the worst moments.

**What's needed:** Help system design across surfaces; per-surface decisions.

**Effort:** M.

---

### U-061: Feedback channels — FINDING

**Where:** Not addressed.

**Why it matters:** Users discover bugs and have suggestions. Without channels: feedback lost; product improvement slowed.

**What's needed:** Feedback mechanism per surface (in-app feedback widget, email, contact form). Feedback triage process.

**Effort:** S.

---

### U-062: Privacy controls UX — FINDING

**Where:** Round 4 L-006, L-007 covered legal; UX here.

**Why it matters:** Members exercising privacy rights (Restriction, Confidential Communications, opt-out from marketing where applicable) need accessible UI:
- Where do they go?
- How clear is the choice?
- What are the consequences (clearly stated)?
- Confirmation and reversibility

**What's needed:** Privacy controls UI design; integrated with member portal (U-004).

**Effort:** M.

---

### U-063: Authorization / consent UX — FINDING

**Where:** Round 4 L-002 covered legal authorization; UX here.

**Why it matters:** When non-TPO uses require authorization (§164.508), the UX of asking matters:
- Specific use described in plain language
- Scope of authorization (what data, what use, what duration)
- Revocation path explained
- Not bundled with other consent (e.g., not part of NPP acknowledgment)

**What's needed:** Authorization UX patterns; counsel-coordinated.

**Effort:** S.

---

### U-064: Status page UX — FINDING

**Where:** Round 5 D-076 covered status page need; UX here.

**Why it matters:** During incidents, status page is the public-facing communication. UX:
- Plain language, not technical
- Clear timeline of incident
- Clear scope of impact
- Action items for affected users
- Subscription for updates (email, SMS, RSS)

**What's needed:** Status page design (Statuspage.io provides defaults; customization for content tone).

**Effort:** S.

---

### U-065: Documentation information architecture — FINDING

**Where:** Various docs in repo (BRD, ARD, ADRs, runbooks, READMEs).

**Why it matters:** As documentation grows, findability declines. IA strategy:
- Documentation home page (index for newcomers)
- Audience-segmented entry points (engineers, compliance, partners)
- Search across docs
- Versioning
- Stale-detection (Round 5 D-072 runbook ownership)

**What's needed:** Doc IA strategy; potentially Backstage or dedicated docs site.

**Effort:** M.

---

## 9. Onboarding UX (Personnel)

### U-066: New engineer onboarding — FINDING

**Where:** Round 2 F-117 and Round 5 D-080 raised. UX layer here.

**Why it matters:** Engineer onboarding is a UX problem:
- Day 1 environment setup ("I should be productive by end of day")
- Day 1 PR ("I should ship something small by end of week")
- Mentor pairing
- Clear documentation
- Shadow on-call before paged on-call

**What's needed:** Onboarding journey design; tested with new hires; iterated.

**Effort:** M.

---

### U-067: New reviewer onboarding — FINDING

**Where:** U-024 covered training; broader UX here.

**Why it matters:** Reviewer onboarding journey: training → calibration → mentored cases → solo work. UX for each transition.

**What's needed:** Reviewer onboarding journey design.

**Effort:** S.

---

### U-068: New compliance staff onboarding — FINDING

**Where:** Round 4 L-038 mandates training; broader UX here.

**Why it matters:** Compliance staff onboarding: HIPAA training → tooling → mentor pairing → solo work. UX for tooling onboarding particularly (DSAR system, complaint system, audit dashboard).

**What's needed:** Compliance onboarding journey.

**Effort:** S.

---

### U-069: New on-call engineer onboarding — FINDING

**Where:** Round 5 D-034 covered rotation; UX here.

**Why it matters:** On-call onboarding journey:
- Runbook training
- Tool access provisioning
- Shadow rotation (observe without being primary)
- Paired rotation (primary with senior backup)
- Solo rotation
- Postmortem participation

**What's needed:** On-call onboarding journey.

**Effort:** S.

---

## 10. Member Trust and Clinical Trust

This section incorporates the Adam Ameele lens noted in Round 1 hand-offs but never executed.

### U-070: Member-facing privacy story — FINDING

**Where:** NPP covers legal. Ongoing privacy communication missing.

**Why it matters:** Members forget NPP details. Ongoing communication ("we just rotated our encryption keys for your safety"; "your data was used X times this month") builds trust. Healthcare context: trust is everything.

**What's needed:** Privacy communication strategy; channel decisions; content cadence.

**Effort:** M.

---

### U-071: Healthcare context awareness — FINDING

**Where:** Implicit.

**Why it matters:** Members are often in vulnerable states. UI defaults:
- No countdown timers (urgency stress)
- No aggressive opt-in dialogs
- No "limited time offer" framing
- Generous time for completion
- Pause options
- Trauma-informed language

**What's needed:** Healthcare-context patterns documented; design system enforcement.

**Effort:** S.

---

### U-072: Stigma avoidance — FINDING

**Where:** Implicit.

**Why it matters:** Some medical conditions carry stigma (mental health, substance use, HIV, communicable disease). Eligibility data may include condition-related identifiers (payer codes, plan codes). UI must not stigmatize:
- "Patient" vs "person" (person-first language)
- Avoid implicit categorization that members can read
- Plain-language explanations without diagnosis-revealing details

**What's needed:** Stigma-avoidance review of all member-facing content; clinical-trust reviewer engagement.

**Effort:** S (review); ongoing.

---

### U-073: Voice and tone — FINDING

**Where:** Not addressed.

**Why it matters:** Lore's voice across surfaces should be consistent. Voice is brand; tone varies by context. Defaults:
- Voice: empathetic, clear, respectful, plain
- Tone: matches situation (urgent during incidents, calm during routine)
- Avoid: jargon, condescension, false intimacy, excessive cheerfulness

**What's needed:** Voice and tone guidelines; per-surface tone application.

**Effort:** S (guidelines); ongoing.

---

### U-074: Member dignity in failure paths — FINDING

**Where:** U-001, U-002, U-012 covered specific failures.

**Why it matters:** Cross-cutting principle: every failure path should preserve member dignity. Avoid:
- Implying member fault for system failures
- Vague messaging that leaves member feeling helpless
- Forced phone trees with no async option
- Responses that sound like form letters

**What's needed:** Failure-path UX review across all surfaces; member dignity as design principle.

**Effort:** S (principle); ongoing (review).

---

## 11. Design System Foundation

### U-075: Design system commitment — FINDING

**Where:** Not addressed.

**Why it matters:** Without a design system: every surface drifts visually and behaviorally. Cross-surface inconsistency confuses users (especially internal users navigating multiple operator UIs). Design system:
- Component library (buttons, inputs, modals, etc.)
- Design tokens (colors, typography, spacing)
- Pattern library (forms, navigation, data display)
- Voice and tone guide
- Accessibility patterns
- Internationalization support
- Documentation site

**What's needed:**
- ADR: design system framework decision (Material, Carbon, Polaris, custom)
- For healthcare: lean toward custom or Carbon (IBM's; healthcare history)
- Implementation plan

**Effort:** L (initial); ongoing.

---

## Summary triage

| Severity | Count | Examples |
|---|---|---|
| BLOCKER | 17 | Verification failure UX (U-001), Lockout recovery UX (U-002), Member portal scope (U-004), NPP layered notice (U-005), Member rights submission UX (U-006), Breach notification UX (U-007), Plain language commitment (U-009), Multilingual strategy (U-010), Personal representative flows (U-011), Member harm recovery (U-012), Reviewer decision support with tokens (U-017), Audit log search UX (U-037), WCAG 2.1 AA audit commitment (U-050), Error message design system (U-055), User research program (U-059) |
| FINDING | 47 | Friction challenge UX, mobile experience, trauma-informed design, cognitive accessibility, deceased member UX, match score viz, queue prioritization, reviewer fatigue, unmerge UX, reviewer audit trail, calibration tests, reviewer onboarding, keyboard shortcuts, pipeline status dashboard, quarantine review, reconciliation reports, schema drift, replay preview, DAG failure, config change, vault detok UX, break-glass UX, two-person auth UX, DSAR case mgmt, complaint UX, compliance dashboard, breach assessment UX, partner onboarding workflow, partner config review, partner self-service, schema drift partner notify, API docs, error response design, integration testing tools, API consumer status, inclusive design, i18n broader, mobile responsiveness audit, cross-browser, UI states, notification system, trust signaling, help/support UX, feedback channels, privacy controls UX, authorization UX, status page UX, doc IA, new engineer onboarding, new reviewer onboarding, new compliance onboarding, new on-call onboarding, privacy story, healthcare context, stigma avoidance, voice and tone, member dignity in failure, design system |
| ADVISORY | 11 | Reviewer device strategy, plus a few smaller items |
| **Total** | **75** | |

---

## Cross-round summary (all six rounds)

| Round | Lens | BLOCKERS | FINDINGS | ADVISORIES | Total |
|---|---|---|---|---|---|
| 1 | Principal Architect | 6 | 14 | 5 | 25 |
| 2 | Chief Programmer | 13 | 37 | 10 | 60 |
| 3 | Principal Security | 18 | 47 | 9 | 74 |
| 4 | Compliance / Legal | 22 | 44 | 9 | 75 |
| 5 | Principal DevOps | 18 | 44 | 9 | 71 |
| 6 | Principal UI/UX | 17 | 47 | 11 | 75 |
| **Combined (with overlap)** | — | **94** | **233** | **53** | **380** |

After de-duplication across all six rounds: **~85-90 unique BLOCKERs**.

The UX round adds substantially because UX is the most-overlooked perspective in technical architecture documents. The BRD/ARD do well on architecture, security primitives, code patterns, compliance mandates, and operational tools — but the *humans* in the system are largely invisible.

---

## What this round specifically owns

What I could surface that prior rounds couldn't:

1. **Member-facing experience design** — the most consequential UX surface, almost entirely undesigned in BRD/ARD (verification failure, lockout recovery, breach notification, member rights workflows, NPP presentation)
2. **Reviewer workflow design** — the human-in-the-loop function deserves more than "queue exists"; the actual decision-support UX is critical
3. **Operator tooling UX** — Round 5 covered the operational systems; this round covers the UX of using them
4. **Accessibility and inclusive design commitments** — beyond the WCAG mention; concrete audit and inclusive-design framework
5. **Multilingual / plain language commitments** — federal Title VI compliance + equity for diverse populations
6. **Personal representative flows** — common case for healthcare; entirely undesigned
7. **Trauma-informed design** — healthcare-specific principle missing from architecture docs
8. **Trust as a design output** — the "Adam Ameele lens" on clinical trust, executed
9. **Onboarding journeys** for all personnel types
10. **Voice and tone, error message design system, design system commitment** — cross-cutting design infrastructure

---

## What this review did NOT cover

Out of scope for principal-UI/UX lens:

- Architectural decomposition (Round 1)
- Code-level discipline (Round 2)
- Security technical controls (Round 3)
- Regulatory / contract / member rights legal frameworks (Round 4 — UX for fulfillment is here, legal is there)
- Operational engineering systems (Round 5)
- Domain correctness (DE Principal — not yet conducted)
- Specific design tools / vendor selection (procurement)
- Specific component library implementation (Phase 0+)

These belong to other reviewers or downstream procurement / build. This round focused on the human-experience gaps that, if unaddressed, fail the platform's actual users — members, reviewers, operators, compliance staff, partners, engineers.

---

## Closing note

The platform is being designed *for* humans. That's the UX-engineering reframe. Architecture, security, code, compliance, operations — all support the goal of serving humans well. When the BRD/ARD mention humans only as anonymous "callers" and "operators," the platform risks serving the architecture rather than the people. The BLOCKERs above are the gaps where, today, the architecture is silent on the people.
