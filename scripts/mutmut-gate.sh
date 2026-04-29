#!/usr/bin/env bash
# scripts/mutmut-gate.sh
#
# Mutation testing gate — runs mutmut on security-critical modules and evaluates
# the mutation score against configured thresholds from pyproject.toml.
#
# Usage:
#   make mutmut-gate           # via Makefile target
#   bash scripts/mutmut-gate.sh  # direct invocation
#   SKIP_MUTMUT=1 bash scripts/mutmut-gate.sh  # local skip (developer only)
#
# Exit codes:
#   0 — All module gates passed (or SKIP_MUTMUT=1 during local run)
#   1 — One or more gates failed (or timeout, or zero mutants)
#
# CRITICAL: SKIP_MUTMUT=1 is honoured ONLY when this script is invoked
# directly (local development). The merge-pr.sh script unsets SKIP_MUTMUT
# before calling ci-local.sh, ensuring gate runs unconditionally at merge.
#
# Cache: mutants/ is cleared before every run to prevent stale cache
# poisoning. This is intentional — mutation testing should always produce
# fresh results from the current code state.
#
# Thresholds: read from pyproject.toml [tool.mutmut] — NOT hardcoded here.
#   threshold_security = 60   (shared/security/ modules)
#   threshold_auth = 50       (auth.py + token_blocklist.py)
#
# Per Constitution Priority 4: "Mutation testing (mutmut) MUST achieve the
# configured mutation score threshold on security-critical modules."
#
# Task: T30.1/T30.3

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# ---------------------------------------------------------------------------
# SKIP_MUTMUT check — exact match "1" only (per spec-challenger correction)
# ---------------------------------------------------------------------------

if [[ "${SKIP_MUTMUT:-}" == "1" ]]; then
    echo ""
    echo "  ⊘ SKIP: SKIP_MUTMUT=1 — mutation gate skipped (local dev mode only)."
    echo "          This skip is NOT honoured during make merge-pr."
    echo ""
    # Record skip in structured output for CI audit (ci-local.sh reads stdout)
    echo "MUTMUT_GATE_STATUS=SKIP"
    exit 0
fi

STATS_DIR="${PROJECT_ROOT}/mutants"
TIMEOUT_SECS=600

# ---------------------------------------------------------------------------
# Helper: run mutmut for a named scope and evaluate against threshold
# ---------------------------------------------------------------------------

run_module_gate() {
    local module_label="$1"
    local threshold_key="$2"

    echo ""
    echo "  --- Mutation gate: ${module_label} (threshold-key: ${threshold_key}) ---"

    # Clear mutants/ before each run to prevent stale cache poisoning
    rm -rf "${PROJECT_ROOT}/mutants"
    mkdir -p "${STATS_DIR}"

    # Run mutmut with wall-clock timeout via perl alarm (cross-platform)
    # Perl alarm sends SIGALRM (signal 14) when the timeout expires.
    echo "  Running: poetry run mutmut run (timeout: ${TIMEOUT_SECS}s)"
    local mutmut_exit=0

    # set -e is not set; || pattern captures exit code without stopping
    perl -e "alarm(${TIMEOUT_SECS}); exec @ARGV" \
        poetry run mutmut run 2>&1 \
        || mutmut_exit=$?

    # Check for SIGALRM timeout (exit code 142 = 128 + SIGALRM signal 14)
    if [[ "${mutmut_exit}" -eq 142 ]]; then
        echo "  ✗ FAIL: mutmut timed out after ${TIMEOUT_SECS}s"
        echo "MUTMUT_GATE_STATUS=FAIL"
        return 1
    fi

    # Export cicd stats (produces mutants/mutmut-cicd-stats.json)
    cd "${PROJECT_ROOT}" && poetry run mutmut export-cicd-stats 2>&1 || true

    local stats_file="${STATS_DIR}/mutmut-cicd-stats.json"
    if [[ ! -f "${stats_file}" ]]; then
        echo "  ✗ FAIL: mutmut stats file not found at ${stats_file}"
        echo "MUTMUT_GATE_STATUS=FAIL"
        return 1
    fi

    # Evaluate gate using Python helper (reads threshold from pyproject.toml)
    # Capture output so we can extract the score for the CI audit entry.
    local gate_result=0
    local gate_output
    gate_output=$(poetry run python scripts/mutmut_gate.py \
        --stats-file "${stats_file}" \
        --module-name "${module_label}" \
        --threshold-key "${threshold_key}" 2>&1) || gate_result=$?

    # Echo captured output so it appears in the build log
    echo "${gate_output}"

    # Extract score from JSON output (the Python script prints a JSON block)
    local score_val
    score_val=$(echo "${gate_output}" | python3 -c \
        "import sys, json, re; \
         txt = sys.stdin.read(); \
         m = re.search(r'\"score\":\\s*([0-9]+(?:\\.[0-9]+)?)', txt); \
         print(m.group(1) if m else 'unknown')" 2>/dev/null || echo "unknown")
    echo "MUTMUT_GATE_SCORE=${score_val}"

    if [[ "${gate_result}" -ne 0 ]]; then
        echo "  ✗ FAIL: ${module_label} mutation score below threshold"
        echo "MUTMUT_GATE_STATUS=FAIL"
        return 1
    fi

    echo "  ✓ PASS: ${module_label}"
    return 0
}

# ---------------------------------------------------------------------------
# Main: run security gate
#
# The gate runs mutmut using the configuration in pyproject.toml [tool.mutmut].
# Scope is controlled by do_not_mutate — shared/security/ and auth/token modules
# are included; all other modules are excluded.
#
# For separate auth threshold enforcement (threshold_auth vs threshold_security),
# a separate run with scoped config is tracked as T30.2 follow-up.
# For now, a single combined run uses threshold_security for the overall score.
# ---------------------------------------------------------------------------

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  Lore Eligibility — Mutation Testing Gate                          ║"
echo "╚══════════════════════════════════════════════════════════════╝"

OVERALL_FAILED=0

# Gate: shared/security/ modules (threshold_security = 60 from pyproject.toml)
if ! run_module_gate "shared/security" "security"; then
    OVERALL_FAILED=1
fi

echo ""
if [[ "${OVERALL_FAILED}" -eq 0 ]]; then
    echo "  ✓ ALL MUTATION GATES PASSED"
    echo "MUTMUT_GATE_STATUS=PASS"
else
    echo "  ✗ ONE OR MORE MUTATION GATES FAILED"
    echo "MUTMUT_GATE_STATUS=FAIL"
fi

exit "${OVERALL_FAILED}"
