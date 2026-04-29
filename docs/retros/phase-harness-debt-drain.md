# Phase Retro — Harness Debt Drain

| Field | Value |
|-------|-------|
| **Branch** | `chore/harness-debt-drain` |
| **Classification** | Lightweight phase (CLAUDE.md Rule 30) |
| **Pipeline** | software-developer → qa-reviewer → fix-round software-developer |
| **Date** | 2026-04-29 |
| **Outcome** | All 17 CI gates PASS or appropriately SKIP. Ready for PR. |

---

## Trigger

PR #11 (synthesis) and the comprehensive backlog merge (PR #12) revealed via the local CI gate that harness debt had accumulated unobserved. Investigation showed PR #11 was merged manually via the GitHub UI rather than through `make merge-pr`, so the local gate had not run for some time. Backlog PR #12 was the first run since whenever the harness was last clean. 8 of 17 gates failed on first attempt, none caused by the docs PR.

---

## Scope

| Track | Issue | Resolution |
|-------|-------|------------|
| Lint | ruff E501 (`__init__.py:1` long docstring), PT006 (parametrize tuple), RUF003 (ambiguous `×` in comment) | Manual fixes; rephrase docstring; tuple syntax; ASCII `x` |
| Format | 8 files needed line-length-driven autoformat | `ruff format` applied |
| Typing | `logging_config.py` returning Any from `BoundLogger`-declared function | First pass cast to `stdlib.BoundLogger` (incorrect — QA caught); second pass corrected to `structlog.types.FilteringBoundLogger` |
| Dead-code | 4 vulture entries at 60% confidence — `version` (CLI), `AUTH_EXEMPT_ROUTES`, `DataIntegrityError`, `IdentityResolutionError` (public API) | Whitelisted in `.vulture_whitelist.py` with per-entry runtime call-site comments |
| Test rigor | assert-density 2.30 < 2.5 floor; two test files below 2.0 per-file | Tightened with meaningful assertions (counterexamples to prove gates active) |
| Docstrings | `create_app` had spurious `Raises` section without raise statements | Removed |
| Repo hygiene | `poetry.lock` and `docs/ci-audit.jsonl` untracked | Now tracked |
| Mutation testing | mutmut-security at 40.79% on `bootstrapper/config_validation.py` (45 of 76 mutants survived) | Added 14 behavior-pinning tests; kill rate 100% (40-point margin above 60% floor) |
| Test-suite leak | 3 logging tests captured stderr after `configure_logging` had snapshot it | `redirect_stderr` moved to wrap the configure call |
| QA Finding 1 | Type cast in `logging_config.py:264` was factually wrong (the cast lied to the type checker) | Corrected target type after runtime probe; cast retained because upstream is `Any`-typed |
| QA Finding 2 | `test_every_non_exempt_route_has_auth_dependency` had a parity assertion that couldn't fail | Replaced with skip-or-assert behavior gate; negative-test verified the test now CAN fail |

15 commits total on the branch.

---

## What worked

- **Two-phase execution.** Phase A drained mechanical debt (lint/format/typing/vulture/density/docstring/tracking). Phase B addressed mutmut as a separate dispatch with a focused brief. Splitting kept each pass scope-bounded and easier to review.
- **PM verification before review dispatch.** Running `bash scripts/ci-local.sh` independently after the developer reported back caught no regressions but proved the discipline; both verification runs went into the audit log as evidence.
- **QA review with full system context (Rule 23).** The qa-reviewer flagged that the BoundLogger cast was *factually wrong*, not just stylistically off — confirmed by runtime probe. A diff-only review would not have caught this; reading the type annotation against the structlog `wrapper_class` configuration was the move.
- **Behavioral mutmut tests, not metric-gaming.** Tests pinned operator-facing error wording (HIPAA citations, `Generate via:` hints) — language that matters when a prod operator reads the validation failure. The "no `XX` substring" assertion in `test_all_error_branches_message_has_no_sentinel_markers` killed 13 mutants in a single test by asserting on a real invariant of error-message rendering.
- **Negative-test verification on Finding 2 fix.** Developer monkey-patched `create_app` to register `/secret` without auth, ran the test, observed AssertionError. Proved the gate is now functional. This is the right shape of evidence for "I made a vacuous test non-vacuous."
- **Lightweight pipeline (Rule 30) was the correct classification.** No new endpoints, no new dependencies, no security-critical production code change (only test additions for mutmut). Skipping spec-challenger / red-team / devops / architecture / phase-boundary-auditor was right.

---

## What needs attention going forward

### BLOCKER advisory: enforce `make merge-pr` for ALL merges to main

| Field | Value |
|-------|-------|
| **ID** | ADV-001 |
| **Severity** | BLOCKER |
| **Source** | Phase retro, harness-debt-drain |
| **Target task** | _not yet filed; phase entry-gate work for next code-bearing phase_ |

**Issue.** PR #11 was merged via the GitHub UI directly. Per CLAUDE.md Rule 12, the PM merges with `make merge-pr` exclusively; bare `gh pr merge` or UI merges bypass the local CI gate and the audit-log entry. The user is the human authority and may choose to merge directly, but doing so accumulates harness debt invisibly until someone runs the gate and discovers it has been broken for weeks. This entire phase exists because of one bypass.

**How to apply.** Before next code-bearing PR work resumes: file a task to enable `main` branch protection (per Phase 00 T0.10 still TODO), with required status checks that reproduce the local gate's most blocking checks (gitleaks, ruff, mypy, bandit, pre-commit, unit-tests). Branch protection makes the gate non-bypassable from the GitHub UI. This is also captured in the CONSTITUTION assumption that branch protection is on.

### FINDING (deferred per Rule 16): vulture-whitelist comment cosmetic inaccuracy

| Field | Value |
|-------|-------|
| **ID** | ADV-002 |
| **Severity** | ADVISORY (cosmetic) |
| **Source** | QA review, drain-qa |
| **Target task** | Polish phase batch (Phase 10) |

**Issue.** `.vulture_whitelist.py:12-14` comment for `version` describes the entry point as `[project.scripts]` directly, but the actual entry is `lore-eligibility = "lore_eligibility.cli:cli"` (the click group), with `version` exposed as a Click subcommand under that group. The comment is mildly inaccurate but the whitelist entry itself is legitimate (verified reachable code).

**How to apply.** Batch into Phase 10 polish task per Rule 16 (cosmetic-only findings).

### ADVISORY: stderr leak in two logging tests

| Field | Value |
|-------|-------|
| **ID** | ADV-003 |
| **Severity** | ADVISORY |
| **Source** | QA review, drain-qa |
| **Target task** | Phase 10 polish OR next time test_logging_config.py is touched |

**Issue.** `test_get_logger_returns_bound_logger_with_name` and `test_configure_logging_is_idempotent` in `tests/unit/test_logging_config.py` do not redirect stderr, so they leak to real stderr during pytest runs. Visible noise during test execution, no correctness impact.

**How to apply.** Consider an autouse `redirect_stderr` fixture in `tests/unit/conftest.py` that wraps logging tests — or per-test redirect like the other logging tests use. Defer; non-blocking.

### ADVISORY: auth-coverage test currently SKIPs

| Field | Value |
|-------|-------|
| **ID** | ADV-004 |
| **Severity** | ADVISORY (informational) |
| **Source** | QA-findings fix |
| **Target task** | Auto-resolves when first non-exempt route lands |

**Issue.** `test_every_non_exempt_route_has_auth_dependency` now SKIPs in CI output because only `/health` is registered (all routes exempt). This is loud and visible — a deliberate improvement over the prior silent-pass on a vacuous assertion. As soon as any non-exempt route is registered, the test auto-activates.

**How to apply.** No action required this phase. Recheck during Phase 1 verification gate when first real route lands.

---

## Metrics

- Commits: 15 (12 from initial drain + 3 from QA-fix round)
- Tests added: 14 mutmut-killing + 6 assert-density tightening = 20 net new tests
- LOC change (production): ~5 lines (mypy cast type, docstring fix, stderr fixture)
- LOC change (test): ~280 added (mutmut + density tightening)
- LOC change (config/whitelist): ~10 lines
- LOC change (autoformat): no semantic LOC change; ~80 lines reflowed
- Mutation kill rate: 40.79% → 100% on `bootstrapper/config_validation.py`
- Coverage: stable at 100% on touched files
- Gates green: 17/17 PASS or appropriate SKIP
- Pipeline duration: ~2 dispatches × ~3-5 min each + 1 fix round ~3 min + PM verifications ~30s each

---

## Recommendation

Push branch and open PR. User merges via `make merge-pr PR=<number>` (NOT GitHub UI — see ADV-001) to ensure this becomes the new audit-log baseline.
