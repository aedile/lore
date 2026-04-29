# Engineering Assumptions

This file records assumptions made during the design and implementation of
`lore-eligibility`. It is the engineering counterpart to the *business*
assumptions in `DOCUMENTS/PROBLEM_BRIEF.md` §"Assumptions" — those frame
the problem; these frame the solution.

Each assumption should state:

- The assumption
- Why it was made (constraint, time budget, or absent evidence)
- How it could be falsified (so we know when to revisit)
- The phase/ADR that owns it

---

## Active Assumptions

| ID | Assumption | Why | Falsified by | Owner |
|----|------------|-----|--------------|-------|
| EA-001 | Python 3.12 is the deployment target | HIPAA-conscious shops typically lag the latest Python; Lore's stack signals (DOCUMENTS/TECH_STACK.md) are conservative | Direct evidence that Lore ships on 3.13+ | ADR-0001 |
| EA-002 | The deployment target is GCP-native (BigQuery + Cloud SQL Postgres + Cloud Composer) | Inferred from `DOCUMENTS/TECH_STACK.md` (Confirmed: GCP, Airflow; Inferred: BigQuery, Cloud SQL) | Direct evidence of a different cloud or warehouse | Phase 02 (ARD) |
| EA-003 | Partner feeds are file-based (SFTP drops); real-time partner APIs are out of scope for v1 | PROBLEM_BRIEF assumption #1 | A partner contract requiring API ingestion | Phase 02 (ARD) |
| EA-004 | Snapshot-diff CDC is the implementation pattern for incremental updates | PROBLEM_BRIEF assumption #2 | A partner that produces a true change feed | Phase 02 (ARD) |

---

## Resolved Assumptions

| ID | Assumption | Resolution | Date |
|----|------------|------------|------|
| _none_ | — | — | — |

---

## How to add an assumption

Use the next sequential `EA-NNN` ID. Add a row in the active table. When the
assumption is later either confirmed (becomes a fact) or falsified (forces
a redesign), move it to "Resolved" with a one-line resolution note.
