# Prototype — Case Study 3 Panel Deliverable

The runnable demonstration for the Lore Health Staff Data Engineer panel
interview. This folder is **quarantined from the production-shaped harness**
(`src/lore_eligibility/`); it runs under a relaxed profile suited to the
~22-hour build budget on synthetic data described in
`../docs/PROTOTYPE_PRD.md`.

## Build artifacts

Tracked against the PRD's eight runnable artifacts plus the two hands-on
snippets and the walkthrough document:

| Artifact | Status | Path |
|---|---|---|
| A1 — Synthetic data harness | Planned | `synthetic_data.py` |
| A2 — Format adapter + YAML mapping | Planned | `adapters/` |
| A3 — DQ engine + profiling | Planned | `dq/` |
| A4 — Identity resolution (Splink on DuckDB) | Planned | `identity/` |
| A5 — Canonical Postgres store + state machine | Planned | `canonical/` |
| A6 — Verification API (FastAPI) | Planned | `verification/` |
| A7 — Deletion ledger + suppression | Planned | `deletion/` |
| A8 — Audit emission + tokenization stub | Planned | `audit/`, `tokenization/` |
| H2 — Cleansing snippets | Planned | `snippets/` |
| W1 — Walkthrough document | Planned | `docs/walkthrough.md` |

## Install prototype-only dependencies

Prototype dependencies (Splink, DuckDB, PyYAML, etc.) are kept out of the
production package. They are added incrementally per slice in
`requirements.txt` (created when the first prototype-only dependency lands).

```bash
poetry run pip install -r prototype/requirements.txt
```

## Run the end-to-end demo

(Populated as artifacts land.)

```bash
make prototype-demo
```

## Tests

The default `pytest` invocation collects only the production test suite under
`tests/`. Prototype tests run separately, bypassing the production coverage
gate:

```bash
poetry run pytest prototype/tests/ -o addopts="--tb=short"
```

## Run-dirty profile

This folder operates under a relaxed harness. See the project memory entry
for the full rules. Short version: TDD at artifact level, ruff lint+format,
PII discipline (no plaintext PII in logs, hash-chained audit, tokenization
vault) — and not much else. No PR ceremony, no review-agent pipeline, no 95%
coverage gate, no mypy strict, no mutation testing.

The production-shaped package under `src/lore_eligibility/` continues to
operate under the full harness defined in the repo-root `CLAUDE.md` and
`CONSTITUTION.md`.
