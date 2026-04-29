# Prototype Requirements Document: Case Study 3 Deliverable

## Document Purpose

This document is the build specification for the prototype that satisfies the original PDF prompt for Case Study 3. It is scoped narrowly to what gets built, what gets shown, and what the panel reads. It does not redo the BRD or ARD. Those documents remain authoritative for the production design; this document is what gets shipped in the remaining time budget.

The single purpose of every artifact in this document is to satisfy a specific deliverable in the PDF prompt.

## Relationship to Other Documents

- **PDF prompt (Case Study 3)** is the binding deliverable specification. Every artifact here traces back to a numbered PDF ask.
- **BRD.md** is the comprehensive business rules specification. Cited where a prototype artifact is the runnable expression of a BR.
- **ARD.md** is the comprehensive architecture specification. Cited where a prototype artifact is a bounded substitution per the ARD's Prototype Scope section.
- **PROBLEM_BRIEF.md** is upstream context and not directly referenced by the prototype.

## PDF Coverage Matrix

The PDF Case Study 3 prompt has eleven explicit deliverables plus the panel instruction layer. This matrix shows which artifact in this prototype satisfies each.

| PDF Ask | Artifact | Status Before This PRD |
| --- | --- | --- |
| 1. Strategic vision | BRD + ARD (referenced in walkthrough) | Done |
| 2. Clear DQ standards | A3 (DQ Engine), referenced from BRD | Done |
| 3. PII governance with privacy controls | A8 (Tokenization Stub) + audit emission, referenced from BRD/ARD | Done |
| 4. Bulk and incremental CDC integration | A2/A3 (snapshot-diff against prior feed; same code path for both modes) | Done |
| 5. Performance and freshness requirements | BRD NFR section, surfaced in walkthrough | Done |
| 6. Automated cleansing and curation | A2 + A3 + A4, runnable end-to-end | Buildable |
| 7. Identity verification system design | A6 (Verification API stub), per ARD Verification context | Buildable |
| 8. Availability and reliability requirements | BRD NFR section, surfaced in walkthrough | Done |
| 9. **SQL DDL for key tables** | H1 (lifted from ARD into walkthrough deck) | Done |
| 10. **Code snippet for inconsistency identification** | H2 (Splink + dedup snippets) | **Was a gap, addressed below** |
| 11. Justifications throughout | Walkthrough document (W1) | Buildable |
| Panel: working prototype | A1 through A8, integrated end-to-end | Buildable |

## Scope Boundaries

### In Scope (Built)

A1 through A8 below. Each is a discrete component with defined acceptance criteria. All run on the local Postgres-plus-DuckDB substrate per AD-007.

### Stubbed (Production Architecture Visible, Not Implemented)

Per ARD Prototype Scope section: Cloud KMS, Cloud Storage Bucket Lock, Datastream, VPC-SC, Cloud Composer, manual reviewer UI, real CAPTCHA integration. The interfaces and contracts that would call into these are honored; only the cloud-side implementation is replaced.

### Cited but Not Built

Phases 2 through 4 of the ARD's phased delivery plan. Operations runbooks. BAA chain documentation. SOC 2 / HITRUST attestation prep. Multi-region disaster recovery.

## Artifact Specifications

Each artifact is numbered (A1 through A8 for runnable components, H1 and H2 for hands-on artifacts the PDF specifically requests, W1 for the walkthrough document). Each carries acceptance criteria so "done" is unambiguous.

### A1: Synthetic Data Harness

**Purpose:** Generate reproducible partner feeds with seeded scenarios.

**Spec:** Python module producing CSV files for two synthetic partners. Outputs:

- 200 to 500 records per partner, configurable
- 5 to 10 deliberately problematic rows per feed: within-feed duplicates, cross-partner same-person near-duplicates, format errors (date variance, name typos, address format), missing required fields, schema drift on day 2 (one new column added)
- A "day 1" feed and a "day 2" feed for each partner to demonstrate snapshot-diff CDC and SCD2 history derivation
- A deletion test fixture: a record that gets deleted on day 1, then re-introduced on day 2, to demonstrate suppression

**Acceptance:** Same seed produces same output. Documented scenario inventory: which lines are dirty, which are clean, which are cross-partner matches.

**Time estimate:** 1.5 to 2 hours.

### A2: Format Adapter and Mapping Engine

**Purpose:** Read partner feeds, apply per-partner YAML mapping, emit canonical staging records.

**Spec:** One CSV format adapter (per AD-016, format adapters are code; mappings are YAML). Two YAML mapping files, one per synthetic partner, exercising different column orders, normalization rules, and field-tier assignments. Mapping engine consumes adapter output plus YAML and produces canonical staging dicts.

**Acceptance:** Adding a third synthetic partner requires only a new YAML file, not a code change. Test asserting this property exists.

**Time estimate:** 1.5 to 2 hours.

### A3: DQ Engine and Profiling

**Purpose:** Apply the BRD's data quality rules to staging records.

**Spec:** Implements BR-301 (field tiers), BR-302 (per-record quarantine), BR-303 (feed-level threshold), BR-304 (schema drift), BR-305 (profile baseline and drift). Quarantined records go to a local quarantine directory with metadata. Profile baselines are persisted as JSON per partner.

**Acceptance:**

- A clean feed processes through with zero quarantines
- A feed with deliberate Required-tier failures produces correct per-record quarantines
- A feed exceeding the 5% threshold produces feed-level quarantine
- Day 2 with an added column produces a SCHEMA_DRIFT_ADDITIVE notification, not a quarantine
- Day 2 with a removed column produces feed quarantine

**Time estimate:** 2 hours.

### A4: Identity Resolution (Splink on DuckDB)

**Purpose:** The technical heart. Demonstrates Tier 1 deterministic and Tier 2 to 4 probabilistic match decisions with explainable weights.

**Spec:** Per AD-011 and AD-012. Splink runs in-process against a DuckDB database loaded with staging records plus existing canonical records. Tier 1 evaluation runs as SQL pre-Splink. Splink scores remaining candidate pairs. Tier evaluation routes outcomes to MERGE / REVIEW / DISTINCT.

**Acceptance:**

- Tier 1 deterministic matches (partner_member_id + DOB + last_name same as canonical) auto-merge
- Tier 2 high-confidence probabilistic matches (e.g., name typo + same DOB + same SSN last 4) auto-merge with audit trail
- Tier 3 mid-confidence matches enter the review queue with score breakdown visible
- Tier 4 low-confidence pairs treated as distinct
- Match weight breakdown is queryable per pair (BR-104)

**Time estimate:** 2.5 to 3 hours.

### A5: Canonical Eligibility Store (Local Postgres)

**Purpose:** The operational source of truth. Implements the state machine, SCD2 history, and partner enrollment one-to-many.

**Spec:** Six tables per ARD Data Schemas section: `canonical_member`, `partner_enrollment`, `member_history`, `match_decision`, `deletion_ledger`, `review_queue`. State machine engine in Python enforces BR-202 transitions. Day 1 to day 2 ingestion produces SCD2 closure and opening rows.

**Acceptance:**

- DDL applies cleanly to a fresh Postgres instance
- Day 1 ingestion populates `canonical_member` and `partner_enrollment`
- Day 2 changes produce `member_history` rows with closed prior states and opened new states
- Forbidden state transitions raise an exception, not a silent update

**Time estimate:** 2 to 3 hours.

### A6: Verification API

**Purpose:** Demonstrates the public verification contract per ARD API Contracts section.

**Spec:** FastAPI service. Single endpoint `POST /v1/verify`. Reads from local Postgres. Returns `{VERIFIED, NOT_VERIFIED}` only. Logs internal state separately. Latency-equalized response (deliberate uniform delay) to prevent timing inference.

**Acceptance:**

- Verified canonical members return VERIFIED
- Non-existent identities return NOT_VERIFIED with the same shape
- Ineligible (past grace) members return NOT_VERIFIED with the same shape
- Pending-resolution members return NOT_VERIFIED with the same shape
- Three failed attempts within the window flip a lockout flag (in-memory; not Redis in prototype)
- No log line, in any service, contains plaintext PII

**Time estimate:** 1.5 hours.

### A7: Deletion Ledger and Suppression

**Purpose:** Demonstrates BR-701 through BR-704: deletion request to vault tombstone to ledger insert to suppression-on-reingest.

**Spec:** A small CLI or script that takes a member_id, executes the deletion sequence (vault tombstone, canonical record nulling, ledger hash insert), and emits the audit events. Identity Resolution's pre-publication step queries the ledger and routes hash matches to a SUPPRESSED_DELETED state.

**Acceptance:**

- Delete a member on day 1
- Day 2 feed re-introduces the same member (per the A1 fixture)
- Day 2 ingestion routes that record to SUPPRESSED_DELETED, not to ELIGIBLE_ACTIVE
- Operator override exists as a function call that emits a DELETION_OVERRIDE event

**Time estimate:** 1.5 hours.

### A8: Audit Emission and Tokenization Stub

**Purpose:** Cross-cutting. Every state change emits an audit event. PII never appears in plaintext outside the vault stub.

**Spec:**

- TokenizationService stub. Local SQLite-backed vault. Random tokens for non-deterministic PII; deterministic-not-FPE tokens for joinable identifiers (per AD-009). The interface (`tokenize`, `detokenize`, `tombstone`) matches the production contract. Implementation backing is replaced; callers do not change.
- Audit events written to a local JSON Lines file with hash-chain on each entry. The chain validator is a separate function that walks the file and asserts continuity.
- Redaction scanner is a regex pass over the audit log file plus all service logs, asserting no plaintext PII patterns appear anywhere.

**Acceptance:**

- Hash chain validates clean across the full pipeline run
- Redaction scanner reports zero matches against PII patterns
- Tampering with one entry breaks the chain at that point and is detected

**Time estimate:** 1 to 1.5 hours.

## Hands-On Artifacts (PDF Items 9 and 10)

The PDF asks for two specific hands-on artifacts. These are lifted from the prototype build into standalone form for the walkthrough.

### H1: SQL DDL for Key Tables

Already produced in ARD Data Schemas section. Six tables. For the walkthrough, the canonical_member and partner_enrollment tables are the headline; the others are referenced as supporting structure.

**No additional build work.** Lift from ARD into the walkthrough deck.

### H2: Cleansing and Inconsistency Identification Snippet

The PDF asks for "a code snippet or SQL query illustrating how you would identify or cleanse a specific type of data inconsistency (e.g., duplicate PII, format errors)."

**Two snippets, one headline and one supporting.** Both fall directly out of A3 and A4 build work; this section specifies their final shape.

#### Headline: Splink near-duplicate detection with explainable weights

Demonstrates probabilistic identity resolution catching a near-duplicate that simple SQL deduplication cannot. The explainability of the per-comparison weights is the differentiator (BR-104) and the part that lands with Lansdell- and Ruch-flavored audiences.

```python
# splink_demo.py — Identity resolution with explainable match weights
# Implements BR-101 tiered match policy; runs against AD-012 DuckDB backend.

from splink.duckdb.linker import DuckDBLinker
from splink.duckdb.comparison_library import (
    exact_match,
    levenshtein_at_thresholds,
    jaro_winkler_at_thresholds,
)

# Two records refer to the same person. Partner_member_id differs (cross-partner),
# last name has a typo, address format differs. SSN last-4 and DOB match.
records = [
    {
        "record_id": "PARTNER_A_001",
        "first_name": "Sarah",   "last_name": "Johnson",
        "dob": "1985-04-12",     "address": "123 Main St Apt 4B",
        "ssn_last_4": "4321",
    },
    {
        "record_id": "PARTNER_B_557",
        "first_name": "Sarah",   "last_name": "Jonson",            # typo
        "dob": "1985-04-12",     "address": "123 Main Street #4B", # format diff
        "ssn_last_4": "4321",
    },
    # ... additional records for blocking and EM training
]

settings = {
    "link_type": "dedupe_only",
    "blocking_rules_to_generate_predictions": ["l.dob = r.dob"],
    "comparisons": [
        exact_match("dob"),
        jaro_winkler_at_thresholds("first_name", [0.9, 0.7]),
        jaro_winkler_at_thresholds("last_name", [0.9, 0.7]),
        levenshtein_at_thresholds("address", [3, 6]),
        exact_match("ssn_last_4"),
    ],
    "retain_intermediate_calculation_columns": True,
}

linker = DuckDBLinker(records, settings)
linker.estimate_u_using_random_sampling(max_pairs=1e6)
linker.estimate_parameters_using_expectation_maximisation("l.dob = r.dob")
predictions = linker.predict()

# BR-101 tier policy
def tier_outcome(match_weight: float) -> str:
    if match_weight >= 8.0:    return "TIER_2_PROB_HIGH"      # auto-merge
    elif match_weight >= 4.0:  return "TIER_3_PROB_REVIEW"    # queue
    else:                       return "TIER_4_DISTINCT"       # no merge

for row in predictions.as_pandas_dataframe().itertuples():
    tier = tier_outcome(row.match_weight)
    print(
        f"{row.record_id_l} <-> {row.record_id_r}: "
        f"weight={row.match_weight:.2f} -> {tier}"
    )
    # Per-comparison decomposition is in row.bf_first_name, row.bf_last_name, etc.
    # That decomposition is what makes the decision auditable per BR-104.
```

#### Supporting: Within-feed deduplication with audit trail

Demonstrates BR-601 last-record-wins deduplication. Simple, runnable, satisfies the literal "duplicate PII" example in the prompt.

```sql
-- BR-601: Within-feed deduplication, last-record-wins, with audit emission
WITH ranked AS (
    SELECT
        partner_id,
        partner_member_id,
        first_name, last_name, dob, ssn_last_4, address,
        feed_line_number,
        COUNT(*) OVER (
            PARTITION BY partner_id, partner_member_id
        ) AS dup_count,
        ROW_NUMBER() OVER (
            PARTITION BY partner_id, partner_member_id
            ORDER BY feed_line_number DESC
        ) AS reverse_rank
    FROM staging_records
    WHERE feed_id = :current_feed_id
)
SELECT
    *,
    CASE
        WHEN dup_count > 1 AND reverse_rank = 1 THEN 'DEDUP_WINNER'
        WHEN dup_count > 1                       THEN 'DEDUP_LOSER'
        ELSE                                          'UNIQUE'
    END AS dedup_status
FROM ranked;

-- Audit emission for resolved duplicates (XR-005: tokens only, no plaintext PII)
INSERT INTO audit_event (event_class, target_token, context, ts)
SELECT
    'WITHIN_FEED_DEDUP',
    name_token,
    jsonb_build_object(
        'partner_id',         partner_id,
        'partner_member_id',  partner_member_id,
        'duplicate_count',    dup_count,
        'kept_line',          feed_line_number,
        'feed_id',            :current_feed_id
    ),
    NOW()
FROM ranked
WHERE dup_count > 1 AND reverse_rank = 1;
```

**Acceptance:** Both snippets execute against the prototype's actual data. The Splink snippet outputs match weights and tier assignments for at least one near-duplicate pair from the synthetic data harness (A1). The SQL snippet executes against the staging table and produces correct dedup_status labels for known duplicates.

## W1: Walkthrough Document

**Purpose:** The artifact the panel reads. Surfaces decisions, defers depth to BRD/ARD.

**Format:** Single markdown file, 5 to 8 pages printed equivalent. Sections:

1. **Problem framing** (one page). The case in own words. Why eligibility data is revenue-critical for an ACO.
2. **Strategic vision** (one page). Bounded contexts as data products. Pattern C separation. Configuration-driven onboarding.
3. **Identity resolution as the technical heart** (one to two pages). Tiered match policy. Splink choice rationale. Worked example with the H2 headline snippet output.
4. **PII governance and audit** (one page). Vault pattern. Zero-PII-in-logs. Sequelae PH boundary as architecture. Hash chain.
5. **Cleansing in action** (one page). Pipeline flow. H2 supporting snippet. Quarantine handling. Schema drift policy.
6. **Identity verification design** (one page). Privacy-preserving collapse. Brute force progression. API contract.
7. **Phased delivery and what's prototyped** (one page). The five phases. Prototype scope as bounded subset.
8. **What I would ask in week one** (one page). The open questions from BRD/ARD as conversation starters, not gaps.

**The three interview lenses surface as framing emphasis, not separate documents:**

- **Mike Griffin (Wayfinding):** lead with section 6, especially the integration contract. Every failure mode explicit.
- **Jonathon Gaff (data engineering):** lead with sections 2, 3, 4. Architectural decisions, schema, audit posture.
- **Adam Ameele (clinical):** lead with section 1's framing. Translate sections 3 and 4 into clinical-trust terms: a wrong identity merge means clinical context bleeds across people; a partial deletion means a person who asked to leave is silently re-onboarded; the architecture is the substrate that prevents these.

**Time estimate:** 2 to 3 hours.

## Build Sequence and Time Budget

22 hours of working time remaining. Sequenced to absorb interruptions and to keep a working end-to-end pipeline visible at every checkpoint.

| Phase | Artifacts | Time | Cumulative | Done state |
| --- | --- | --- | --- | --- |
| A. Foundation | A1 + A5 schema | 4 hrs | 4 hrs | Synthetic feeds exist; Postgres canonical schema deployed |
| B. Pipeline | A2 + A3 | 4 hrs | 8 hrs | Day 1 feed lands canonical staging records, DQ runs |
| C. Identity | A4 | 3 hrs | 11 hrs | Splink runs end-to-end, tier outcomes in match_decision |
| D. Verification + Deletion | A6 + A7 | 3 hrs | 14 hrs | API serves; deletion + suppression demo works |
| E. Audit + Polish | A8 + integration | 2 hrs | 16 hrs | Hash chain validates; redaction scan clean |
| F. Hands-on artifacts | H2 finalization | 1 hr | 17 hrs | Snippets execute against prototype data, output captured |
| G. Walkthrough doc | W1 | 3 hrs | 20 hrs | Document complete, decisions surfaced, lens-specific framings noted |
| H. Rehearsal buffer | dry run, fixes | 2 hrs | 22 hrs | Walkthrough rehearsed once aloud, demo runs cleanly |

**Buffer policy:** if any phase runs over by more than 30%, cut the next-lowest-priority artifact rather than burning rehearsal time. Priority order from highest to lowest: A4 (identity resolution), A3 (DQ), A5 (canonical), A6 (verification), A7 (deletion), A8 (audit), W1 (walkthrough). Rehearsal is non-negotiable.

## Acceptance Criteria for "Done"

The prototype ships when all of the following are true:

1. A single command runs the full day-1 pipeline end-to-end on synthetic data without errors
2. A single command runs the day-2 pipeline producing SCD2 history, suppression, and re-resolution events
3. The Splink demo produces visible match weight breakdowns for at least three pair scenarios (Tier 2, Tier 3, Tier 4)
4. The verification API responds correctly on at least four canonical-state combinations with the same response shape
5. The hash-chain validator reports clean across the full run
6. The redaction scanner reports zero PII pattern matches across all log output
7. The deletion-then-reintroduce demo produces a SUPPRESSED_DELETED routing without operator intervention
8. The walkthrough document is complete and rehearsed at least once aloud

A panel walkthrough should require at most 15 minutes of live demo plus 30 to 40 minutes of architecture discussion driven from W1.

## Open Items Going Into the Build

- Splink threshold defaults (`MATCH_THRESHOLD_HIGH`, `MATCH_THRESHOLD_REVIEW`) will be tuned during A4 against the synthetic data with seeded ground truth. Document the tuning in W1.
- The redaction scanner regex set: SSN, full email, phone with area code, and DOB-as-date are the headline patterns. Additional patterns may emerge from log review in Phase E.
- Whether to surface the H2 snippets inline in the walkthrough or as a code appendix. Inline is more demonstrative; appendix is cleaner for the document. Default to inline with a "see also full code at: prototype/splink_demo.py" pointer.
