# Prototype — Case Study 3 Panel Deliverable

The runnable demonstration for the Lore Health Staff Data Engineer panel
interview. This folder is **quarantined from the production-shaped harness**
(`src/lore_eligibility/`); it runs under a relaxed profile suited to the
~22-hour build budget on synthetic data described in
`../docs/PROTOTYPE_PRD.md`.

## Documentation

- **`../docs/PROTOTYPE_PRD.md`** — build spec (what gets built, acceptance criteria).
- **`docs/walkthrough.md`** (W1) — panel-facing prose narrative: problem framing, strategic vision, identity-resolution rationale, lens-specific framing for each interviewer.
- **`docs/notebook.md`** — runtime notebook: sample inputs, captured outputs, stats, audit-chain entries. The "show me what it actually does" doc.

## Build artifacts

Tracked against the PRD's eight runnable artifacts plus the two hands-on
snippets and the walkthrough document:

| Artifact | Status | Path |
|---|---|---|
| A1 — Synthetic data harness | Done | `synthetic_data.py` + `fixtures/` |
| A2 — Format adapter + YAML mapping | Done | `csv_adapter.py`, `mapping_engine.py`, `mappings/` |
| A3 — DQ engine + profiling | Done | `dq.py` |
| A4 — Identity resolution (Splink on DuckDB) | Done | `identity.py` |
| A5 — Canonical Postgres store + state machine | Done | `canonical/` |
| A6 — Verification API (FastAPI) | Done | `verification.py`, `tokenization.py` |
| A7 — Deletion ledger + suppression | Done | `deletion.py` |
| A8 — Audit emission + tokenization stub | Done | `audit.py`, `vault.py` |
| H2 — Cleansing snippets | Done | `snippets/h2_splink_demo.py`, `snippets/h2_dedup_query.sql` |
| W1 — Walkthrough document | Drafted | `docs/walkthrough.md` |
| Demo runner | Done | `demo.py`, `__main__.py` |
| End-to-end test | Done | `tests/test_e2e_demo.py` |

## Install prototype-only dependencies

Prototype dependencies (Splink, DuckDB, PyYAML, etc.) are kept out of the
production package. They are added incrementally per slice in
`requirements.txt` (created when the first prototype-only dependency lands).

```bash
poetry run pip install -r prototype/requirements.txt
```

## Run the end-to-end demo

```bash
# 1. Spawn a one-shot Postgres for the prototype on host port 5440.
#    (Lighter than `make dev-db-only`, which expects production-style
#    secret-file provisioning.)
make prototype-pg-up

# 2. Run the full panel demo. Prints a section per PRD acceptance criterion;
#    exits 1 if the audit chain breaks or redaction scanner hits anything.
make prototype-demo

# 3. Tear down when finished.
make prototype-pg-down

# Optional: just the Splink near-duplicate snippet (panel hands-on artifact).
make prototype-h2
```

The `make prototype-demo` target runs ~4-7 seconds and prints a section
per PRD acceptance criterion (#1 day-1 pipeline, #2 day-2 pipeline + SCD2
+ suppression, #3 tier histogram, #5 audit chain validation, #6 redaction
scan, #7 deletion + suppression). Exits 1 if anything fails.

For the one-command panel-rehearsal driver, see `./demo.sh` in the repo root.

## Tests

The default `pytest` invocation collects only the production test suite under
`tests/`. Prototype tests run separately, bypassing the production coverage
gate:

```bash
make prototype-test
# or:
poetry run pytest prototype/tests/ -o addopts="--tb=short"
```

Suite size as of W1: **153 tests, ~8 seconds**. The end-to-end test
(`tests/test_e2e_demo.py`) runs the full pipeline against a temp Postgres
spawned by pytest-postgresql and asserts every numbered acceptance criterion
in `../docs/PROTOTYPE_PRD.md`.

## Run-dirty profile

This folder operates under a relaxed harness. See the project memory entry
for the full rules. Short version: TDD at artifact level, ruff lint+format,
PII discipline (no plaintext PII in logs, hash-chained audit, tokenization
vault) — and not much else. No PR ceremony, no review-agent pipeline, no 95%
coverage gate, no mypy strict, no mutation testing.

The production-shaped package under `src/lore_eligibility/` continues to
operate under the full harness defined in the repo-root `CLAUDE.md` and
`CONSTITUTION.md`.
