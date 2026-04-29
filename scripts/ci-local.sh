#!/usr/bin/env bash
# scripts/ci-local.sh
#
# Local CI gate — mirrors the GitHub Actions CI pipeline.
# Runs all quality gates and records results to the CI audit log.
#
# Usage:
#   make ci-local          # Standard invocation
#   bash scripts/ci-local.sh   # Direct invocation
#
# Exit codes:
#   0 — All gates passed
#   1 — One or more gates failed
#
# Audit: On completion (pass or fail), appends a signed entry to
# docs/ci-audit.jsonl. This file is committed to the repo and provides
# a tamper-evident audit trail of all CI runs.
#
# SKIP_MUTMUT=1: Mutation gate may be skipped ONLY during direct local runs.
# merge-pr.sh unconditionally unsets SKIP_MUTMUT before calling this script.
# See scripts/merge-pr.sh for the merge-time enforcement.

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

AUDIT_LOG="docs/ci-audit.jsonl"
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
COMMIT_SHA=$(git rev-parse HEAD 2>/dev/null || echo "no-commit")
COMMIT_SHORT=$(git rev-parse --short HEAD 2>/dev/null || echo "no-commit")
BRANCH=$(git branch --show-current 2>/dev/null || echo "detached")
RESULTS=()
FAILED=0

# ---------------------------------------------------------------------------
# Gate runner
# ---------------------------------------------------------------------------

run_gate() {
    local name="$1"
    shift
    local cmd="$*"

    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  GATE: ${name}"
    echo "  CMD:  ${cmd}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    local start_time
    start_time=$(date +%s)

    if eval "${cmd}"; then
        local end_time
        end_time=$(date +%s)
        local duration=$((end_time - start_time))
        echo "  ✓ PASS (${duration}s)"
        RESULTS+=("{\"gate\":\"${name}\",\"status\":\"PASS\",\"duration_s\":${duration}}")
    else
        local end_time
        end_time=$(date +%s)
        local duration=$((end_time - start_time))
        echo "  ✗ FAIL (${duration}s)"
        RESULTS+=("{\"gate\":\"${name}\",\"status\":\"FAIL\",\"duration_s\":${duration}}")
        FAILED=1
    fi
}

# ---------------------------------------------------------------------------
# Gates — mirrors .github/workflows/ci.yml
# ---------------------------------------------------------------------------

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  Lore Eligibility — Local CI Pipeline                              ║"
echo "║  Commit: ${COMMIT_SHORT} (${BRANCH})                      ║"
echo "║  Time:   ${TIMESTAMP}                                      ║"
echo "╚══════════════════════════════════════════════════════════════╝"

# Security
run_gate "gitleaks" "gitleaks detect --verbose --redact 2>&1"

# Lint & Static Analysis (only run if src/ or tests/ exist with .py files)
if find src/ tests/ -name '*.py' -print -quit 2>/dev/null | grep -q .; then
    run_gate "ruff-lint" "poetry run ruff check src/ tests/"
    run_gate "ruff-format" "poetry run ruff format --check src/ tests/"
    run_gate "mypy" "poetry run mypy src/"
    run_gate "bandit" "poetry run bandit -c pyproject.toml -r src/"
    # Regenerate vulture plugin whitelist from AST before running dead-code scan
    poetry run python scripts/vulture_pydantic_plugin.py > .vulture_generated.py
    run_gate "vulture" "poetry run vulture src/ .vulture_whitelist.py .vulture_generated.py --min-confidence 60"
else
    echo ""
    echo "  ⊘ SKIP: No Python files in src/ or tests/ — skipping lint gates"
    RESULTS+=("{\"gate\":\"lint-gates\",\"status\":\"SKIP\",\"duration_s\":0}")
fi

# Supply chain audit (pip-audit) — runs unconditionally
run_gate "pip-audit" "bash scripts/pip-audit.sh"

# Assertion density gate (T51.5) — global >= 2.5, per-file >= 2.0
# Baseline file grandfathers legitimate single-assertion tests (see T51.2).
# Global average is computed from non-grandfathered functions only (see T51.1).
# Exit 1 if non-grandfathered global average < 2.5 or any file average < 2.0.
if find tests/ -name 'test_*.py' -print -quit 2>/dev/null | grep -q .; then
    run_gate "assert-density" \
        "poetry run python scripts/assert_density_check.py \
            --baseline scripts/assert_density_baseline.txt \
            --global-threshold 2.5 \
            --per-file-threshold 2.0 \
            --json \
            $(find tests/ -name 'test_*.py' | tr '\n' ' ')"
else
    RESULTS+=("{\"gate\":\"assert-density\",\"status\":\"SKIP\",\"duration_s\":0}")
fi

# Baseline ratchet check (T51.5) — ensures baseline file never grows
run_gate "assert-density-ratchet" "bash scripts/assert_density_ratchet.sh"

# Tests (only run if tests exist)
if find tests/unit/ -name 'test_*.py' -print -quit 2>/dev/null | grep -q .; then
    run_gate "unit-tests" "poetry run pytest tests/unit/ --cov=src/lore_eligibility --cov-fail-under=95 -q --tb=short"
else
    echo ""
    echo "  ⊘ SKIP: No unit tests found — skipping test gate"
    RESULTS+=("{\"gate\":\"unit-tests\",\"status\":\"SKIP\",\"duration_s\":0}")
fi

if find tests/integration/ -name 'test_*.py' -print -quit 2>/dev/null | grep -q .; then
    run_gate "integration-tests" "poetry run pytest tests/integration/ -v --tb=short --no-cov"
else
    echo ""
    echo "  ⊘ SKIP: No integration tests found — skipping integration gate"
    RESULTS+=("{\"gate\":\"integration-tests\",\"status\":\"SKIP\",\"duration_s\":0}")
fi

# Mock-free integration test enforcement (mock-free integration policy)
if find tests/integration/ -name 'test_*.py' -print -quit 2>/dev/null | grep -q .; then
    run_gate "integration-mock-gate" "python3 scripts/check_integration_mocks.py tests/integration/"
else
    RESULTS+=("{\"gate\":\"integration-mock-gate\",\"status\":\"SKIP\",\"duration_s\":0}")
fi

# PII-in-test-fixtures gate (CONSTITUTION Priority 0 — HIPAA / PHI handling).
# Runs unconditionally even when fixture dirs are empty (vacuous pass).
run_gate "pii-in-fixtures" "python3 scripts/check_pii_in_fixtures.py"

# ---------------------------------------------------------------------------
# Mutation testing gate (T30.1)
#
# SKIP_MUTMUT=1 is honoured here for local development convenience.
# merge-pr.sh unconditionally unsets SKIP_MUTMUT before calling this script,
# so the gate ALWAYS runs at merge time (Constitution Priority 1).
#
# Timeout: 600s wall-clock via scripts/mutmut-gate.sh.
# Failure modes: timeout, zero mutants, score below threshold — all FAIL.
# ---------------------------------------------------------------------------

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  GATE: mutmut-security"
echo "  CMD:  bash scripts/mutmut-gate.sh"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

mutmut_start=$(date +%s)

if [[ "${SKIP_MUTMUT:-}" == "1" ]]; then
    echo ""
    echo "  ⊘ SKIP: SKIP_MUTMUT=1 — mutation gate skipped (local dev mode only)."
    echo "          This skip is NOT honoured during make merge-pr."
    RESULTS+=("{\"gate\":\"mutmut-security\",\"status\":\"SKIP\",\"duration_s\":0,\"note\":\"SKIP_MUTMUT=1\"}")
else
    # Capture output to a temp file so we can both display it and extract the
    # mutation score for the CI audit entry. The score is emitted by
    # mutmut-gate.sh as a line of the form: MUTMUT_GATE_SCORE=<value>
    mutmut_tmp=$(mktemp)
    mutmut_exit=0
    bash scripts/mutmut-gate.sh 2>&1 | tee "${mutmut_tmp}" || mutmut_exit=${PIPESTATUS[0]}
    mutmut_end=$(date +%s)
    mutmut_duration=$((mutmut_end - mutmut_start))

    # Extract mutation score from captured output (format: MUTMUT_GATE_SCORE=XX.X)
    mutmut_score=$(grep -o 'MUTMUT_GATE_SCORE=[^[:space:]]*' "${mutmut_tmp}" \
        | tail -1 | cut -d'=' -f2 || echo "unknown")
    rm -f "${mutmut_tmp}"

    if [[ "${mutmut_exit}" -eq 0 ]]; then
        echo "  ✓ PASS (${mutmut_duration}s)"
        RESULTS+=("{\"gate\":\"mutmut-security\",\"status\":\"PASS\",\"duration_s\":${mutmut_duration},\"mutation_score\":\"${mutmut_score}%\"}")
    else
        echo "  ✗ FAIL (${mutmut_duration}s)"
        RESULTS+=("{\"gate\":\"mutmut-security\",\"status\":\"FAIL\",\"duration_s\":${mutmut_duration},\"mutation_score\":\"${mutmut_score}%\"}")
        FAILED=1
    fi
fi

# Import-linter (only if pyproject.toml has contracts)
if grep -q "importlinter" pyproject.toml 2>/dev/null; then
    run_gate "import-linter" "poetry run lint-imports"
else
    RESULTS+=("{\"gate\":\"import-linter\",\"status\":\"SKIP\",\"duration_s\":0}")
fi

# Pre-commit (if installed)
if command -v pre-commit &>/dev/null; then
    run_gate "pre-commit" "pre-commit run --all-files"
else
    echo ""
    echo "  ⊘ SKIP: pre-commit not installed"
    RESULTS+=("{\"gate\":\"pre-commit\",\"status\":\"SKIP\",\"duration_s\":0}")
fi

# Shellcheck (if .sh files exist)
if find scripts/ .claude/hooks/ -name '*.sh' -print -quit 2>/dev/null | grep -q .; then
    run_gate "shellcheck" "find scripts/ .claude/hooks/ -name '*.sh' -print0 | xargs -0 shellcheck --severity=warning"
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [[ "${FAILED}" -eq 0 ]]; then
    VERDICT="PASS"
    echo "  ✓ ALL GATES PASSED"
else
    VERDICT="FAIL"
    echo "  ✗ ONE OR MORE GATES FAILED"
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ---------------------------------------------------------------------------
# Audit log entry
# ---------------------------------------------------------------------------

# Build JSON array of gate results
GATES_JSON=$(printf '%s,' "${RESULTS[@]}")
GATES_JSON="[${GATES_JSON%,}]"

# Compute HMAC of the audit entry for tamper detection
# Uses the commit SHA as a lightweight integrity binding (not a secret —
# the goal is tamper detection, not forgery prevention)
AUDIT_PAYLOAD="{\"timestamp\":\"${TIMESTAMP}\",\"commit\":\"${COMMIT_SHA}\",\"branch\":\"${BRANCH}\",\"verdict\":\"${VERDICT}\",\"gates\":${GATES_JSON}}"
AUDIT_HASH=$(echo -n "${AUDIT_PAYLOAD}" | shasum -a 256 | cut -d' ' -f1)
AUDIT_ENTRY="{\"timestamp\":\"${TIMESTAMP}\",\"commit\":\"${COMMIT_SHA}\",\"branch\":\"${BRANCH}\",\"verdict\":\"${VERDICT}\",\"gates\":${GATES_JSON},\"integrity\":\"sha256:${AUDIT_HASH}\"}"

# Append to audit log
mkdir -p "$(dirname "${AUDIT_LOG}")"
echo "${AUDIT_ENTRY}" >> "${AUDIT_LOG}"
echo ""
echo "  Audit entry written to ${AUDIT_LOG}"
echo "  Integrity: sha256:${AUDIT_HASH}"

exit "${FAILED}"
