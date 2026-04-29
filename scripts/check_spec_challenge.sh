#!/usr/bin/env bash
# check_spec_challenge.sh — T1.11 Constitutional Enforcement Gate
#
# Verifies that for any PR with feat: commits, a corresponding spec-challenge
# file exists in docs/spec-challenges/.
#
# Rule 20 (CLAUDE.md): Before spawning the software-developer, the PM MUST
# spawn the spec-challenger agent. Its output must be committed to
# docs/spec-challenges/P<N>-T<M>.md before development proceeds.
#
# Exit codes:
#   0 — gate passes: no feat: commits exist, or a spec-challenge file exists
#   1 — gate fails: feat: commits exist but docs/spec-challenges/ has no .md files
#
# Usage:
#   ./scripts/check_spec_challenge.sh
#
# CI integration: call this script in the CI pipeline after git checkout.
# The script inspects commits on the current branch vs the base branch,
# the same approach as check_attack_test_order.sh.

set -euo pipefail

# ---------------------------------------------------------------------------
# Locate the repo root (the directory containing docs/spec-challenges/).
# Traverse upward from the script's directory.
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
SPEC_CHALLENGES_DIR="${REPO_ROOT}/docs/spec-challenges"

# ---------------------------------------------------------------------------
# Identify the base branch to compare against.
# ---------------------------------------------------------------------------
_find_base_ref() {
    for ref in origin/main origin/master main master; do
        if git rev-parse --verify "${ref}" >/dev/null 2>&1; then
            echo "${ref}"
            return 0
        fi
    done
    echo ""
    return 0
}

BASE_REF=$(_find_base_ref)

# ---------------------------------------------------------------------------
# Collect commit messages for this branch only.
# ---------------------------------------------------------------------------
if [[ -n "${BASE_REF}" ]]; then
    COMMIT_MESSAGES=$(git log "${BASE_REF}..HEAD" --no-merges --format="%s" 2>/dev/null || true)
else
    COMMIT_MESSAGES=$(git log --no-merges --format="%s" 2>/dev/null || true)
fi

if [[ -z "${COMMIT_MESSAGES}" ]]; then
    echo "[spec-challenge] No branch commits found — pass (vacuous)."
    exit 0
fi

# ---------------------------------------------------------------------------
# Check for feat: commits on this branch.
# ---------------------------------------------------------------------------
HAS_FEAT_COMMIT=false
while IFS= read -r msg; do
    if [[ "${msg}" =~ ^feat: ]]; then
        HAS_FEAT_COMMIT=true
        break
    fi
done <<< "${COMMIT_MESSAGES}"

if [[ "${HAS_FEAT_COMMIT}" == "false" ]]; then
    echo "[spec-challenge] No feat: commits on branch — pass (no enforcement needed)."
    exit 0
fi

# ---------------------------------------------------------------------------
# feat: commits exist — verify docs/spec-challenges/ has at least one .md file.
# ---------------------------------------------------------------------------
if [[ ! -d "${SPEC_CHALLENGES_DIR}" ]]; then
    echo "[spec-challenge] VIOLATION: docs/spec-challenges/ directory not found." >&2
    echo "[spec-challenge] Create the directory and commit a spec-challenge .md file" >&2
    echo "[spec-challenge] before adding feat: commits to this branch." >&2
    exit 1
fi

# Count .md files (excluding .gitkeep — that's the empty-dir sentinel only).
MD_COUNT=$(find "${SPEC_CHALLENGES_DIR}" -maxdepth 1 -name "*.md" | wc -l | tr -d '[:space:]')

if [[ "${MD_COUNT}" -eq 0 ]]; then
    echo "[spec-challenge] VIOLATION: feat: commits exist but docs/spec-challenges/ has no .md files." >&2
    echo "[spec-challenge] Per Rule 20, the PM must commit spec-challenger output to" >&2
    echo "[spec-challenge] docs/spec-challenges/P<N>-T<M>.md before development." >&2
    echo "[spec-challenge] Current .md files in docs/spec-challenges/: 0" >&2
    exit 1
fi

echo "[spec-challenge] Found ${MD_COUNT} spec-challenge file(s) — PASS."
exit 0
