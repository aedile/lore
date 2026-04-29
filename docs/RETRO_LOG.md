# lore-eligibility — Retrospective Log

Summary ledger of phase retrospectives and open advisory items.
Per-phase retrospective details live in `docs/retros/phase-NN.md`.

---

## Phase Summary Table

| Phase | Name | ACs met | Issues | Advisories opened | Retro file |
|-------|------|---------|--------|-------------------|------------|
| 00 | Harness foundation | _in progress_ | — | — | `docs/retros/phase-00.md` (pending) |
| —  | Harness debt drain (lightweight) | All — 17/17 gates green | 1 BLOCKER advisory (ADV-001 enforce make merge-pr); 2 deferred (ADV-002, ADV-003); 1 informational (ADV-004) | 4 (1 blocker, 2 deferred, 1 informational) | `docs/retros/phase-harness-debt-drain.md` |

---

## Open Advisory Items

Advisory findings without a resolved target task are tracked here.
Drain (delete) rows when their target task is completed.

| ID | Source | Target Task | Severity | Advisory |
|----|--------|-------------|----------|----------|
| ADV-001 | Phase retro, harness-debt-drain | Pre-Phase-1 entry gate (enable main branch protection per T0.10) | BLOCKER | PR #11 was merged via GitHub UI, bypassing `make merge-pr`. UI merges bypass local CI and audit log; harness debt accumulates invisibly until someone runs the gate. Enable main branch protection with required status checks before next code-bearing PR work resumes. |
| ADV-002 | QA review, drain-qa | Phase 10 polish batch | DEFERRED (cosmetic) | `.vulture_whitelist.py:12` comment for `version` says `[project.scripts]` entry point; actual entry is `lore-eligibility = lore_eligibility.cli:cli` with `version` as a Click subcommand. Whitelist entry itself is legitimate. |
| ADV-003 | QA review, drain-qa | Next time `test_logging_config.py` is touched | DEFERRED | Two logging tests (`test_get_logger_returns_bound_logger_with_name`, `test_configure_logging_is_idempotent`) leak stderr during pytest. No correctness impact; visible noise. Add autouse `redirect_stderr` fixture or per-test redirect when next touched. |
| ADV-004 | QA-findings fix | Auto-resolves when first non-exempt route lands in Phase 1 | INFORMATIONAL | `test_every_non_exempt_route_has_auth_dependency` now SKIPs in CI output (only `/health` registered, all routes exempt). Deliberate improvement over prior vacuous-pass; auto-activates when first non-exempt route lands. |
