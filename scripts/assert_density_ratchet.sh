#!/usr/bin/env bash
# scripts/assert_density_ratchet.sh
#
# Baseline ratchet check for assert_density_baseline.txt (T51.5).
#
# Validates that:
#   1. The baseline file exists.
#   2. The baseline entry count has not grown relative to the recorded
#      maximum (stored in scripts/assert_density_baseline_max.txt).
#
# Usage:
#   bash scripts/assert_density_ratchet.sh
#
# Exit codes:
#   0 — Baseline count is within the ratchet (count <= max or max not set).
#   1 — Baseline count exceeds recorded maximum (regression detected).
#
# The ratchet floor file (assert_density_baseline_max.txt) records the
# committed baseline entry count. Entries can only decrease — every commit
# that adds new baseline entries must also update the max file.
#
# To record a new maximum after a legitimate addition:
#   bash scripts/assert_density_ratchet.sh --record
#
# Constitution mandate (Priority 0.5): every quality gate must have a
# programmatic enforcement mechanism. This script IS that mechanism.

set -euo pipefail

BASELINE="scripts/assert_density_baseline.txt"
MAX_FILE="scripts/assert_density_baseline_max.txt"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

count_entries() {
    # Count non-blank, non-comment lines in the baseline file
    grep -cE '^tests/' "${BASELINE}" 2>/dev/null || echo 0
}

# ---------------------------------------------------------------------------
# --record mode: update the max file and exit 0
# ---------------------------------------------------------------------------

if [[ "${1:-}" == "--record" ]]; then
    current=$(count_entries)
    echo "${current}" > "${MAX_FILE}"
    echo "assert-density-ratchet: Recorded new max = ${current} entries in ${MAX_FILE}"
    exit 0
fi

# ---------------------------------------------------------------------------
# Validation mode (default)
# ---------------------------------------------------------------------------

if [[ ! -f "${BASELINE}" ]]; then
    echo "ERROR: assert-density-ratchet: ${BASELINE} not found" >&2
    exit 1
fi

current=$(count_entries)

if [[ ! -f "${MAX_FILE}" ]]; then
    # No recorded max — this is the first run; record it and pass
    echo "${current}" > "${MAX_FILE}"
    echo "assert-density-ratchet: PASS (initialised max = ${current})"
    exit 0
fi

max=$(cat "${MAX_FILE}" | tr -d '[:space:]')

if [[ "${current}" -gt "${max}" ]]; then
    echo "ERROR: assert-density-ratchet: BASELINE REGRESSION" >&2
    echo "  Current entries: ${current}" >&2
    echo "  Recorded max:    ${max}" >&2
    echo "" >&2
    echo "  The baseline file has grown — baseline entries can only decrease." >&2
    echo "  To record a legitimate increase (requires PM approval and justification):" >&2
    echo "    bash scripts/assert_density_ratchet.sh --record" >&2
    exit 1
fi

echo "assert-density-ratchet: PASS (current=${current} <= max=${max})"
exit 0
