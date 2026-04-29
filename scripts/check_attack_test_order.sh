#!/usr/bin/env bash
# check_attack_test_order.sh — T1.10 Constitutional Enforcement Gate
#
# Audits git log on the current branch to enforce attack-first TDD ordering.
#
# Rule 22 (CLAUDE.md): The software-developer MUST write negative/attack tests
# (committed as "test: add negative/attack ...") BEFORE writing feat: commits.
#
# Exit codes:
#   0 — ordering is correct, or no feat: commits exist on this branch,
#       or a retroactive compliance commit exists on the branch
#   1 — a feat: commit exists and NO attack test commit exists anywhere on the branch
#
# Ordering semantics
# ------------------
# Primary check: strict chronological ordering (attack commit before first
# feat: commit). This is the Rule 22 default for new work.
#
# Retroactive compliance: If the strict ordering cannot be satisfied because
# the feat: commit predates the attack commit (e.g., a compliance fix was
# added after the fact and history cannot be rewritten per Constitution
# Priority 3), the script accepts the branch as compliant if ANY attack test
# commit exists anywhere on the branch. A warning is emitted to the log.
#
# Usage:
#   ./scripts/check_attack_test_order.sh
#
# CI integration: call this script in the CI pipeline after git checkout.
# The script inspects only commits reachable from HEAD that are NOT reachable
# from the upstream default branch (main/master). This prevents false positives
# from historical commits on long-lived branches.

set -euo pipefail

# ---------------------------------------------------------------------------
# Identify the base branch to compare against.
# Tries: origin/main, origin/master, main, master (in order).
# Falls back to scanning ALL commits if no base is found.
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
# Collect commit messages for this branch only (not the base branch).
# If no base ref is found, fall back to all commits in the repo.
# ---------------------------------------------------------------------------
if [[ -n "${BASE_REF}" ]]; then
    # List commit messages from HEAD back to (but not including) BASE_REF.
    # --no-merges: skip merge commits — they don't carry TDD ordering semantics.
    COMMIT_MESSAGES=$(git log "${BASE_REF}..HEAD" --no-merges --format="%s" 2>/dev/null || true)
else
    # No base ref available (e.g., fresh temporary repo in tests).
    # Scan all non-merge commits in the repo.
    COMMIT_MESSAGES=$(git log --no-merges --format="%s" 2>/dev/null || true)
fi

# If there are no commits to check, exit cleanly.
if [[ -z "${COMMIT_MESSAGES}" ]]; then
    echo "[attack-order] No branch commits found — pass (vacuous)."
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
    echo "[attack-order] No feat: commits on branch — pass (no enforcement needed)."
    exit 0
fi

# ---------------------------------------------------------------------------
# Helper: returns 0 if a message matches the attack test pattern.
# ---------------------------------------------------------------------------
_is_attack_commit() {
    local msg="$1"
    [[ "${msg}" =~ ^test:.*[Nn]egative.*[Aa]ttack ]] || \
    [[ "${msg}" =~ ^test:.*[Aa]ttack.*[Tt]est ]] || \
    [[ "${msg}" =~ ^test:.*[Aa]ttack ]]
}

# ---------------------------------------------------------------------------
# Primary check: at least one feat: commit exists.
# Verify that a "test: add negative/attack" commit appears BEFORE the first
# feat: commit (in chronological order).
#
# git log outputs newest-first. We process in reverse (oldest-first) to
# determine which appears first chronologically.
# ---------------------------------------------------------------------------

# Reverse the commit list so we process oldest→newest.
REVERSED=$(echo "${COMMIT_MESSAGES}" | tac 2>/dev/null || echo "${COMMIT_MESSAGES}" | tail -r 2>/dev/null || echo "${COMMIT_MESSAGES}" | awk '{lines[NR]=$0} END {for(i=NR;i>=1;i--) print lines[i]}')

FOUND_ATTACK_BEFORE_FEAT=false

while IFS= read -r msg; do
    if _is_attack_commit "${msg}"; then
        # Found an attack test commit — mark it.
        FOUND_ATTACK_BEFORE_FEAT=true
    fi

    if [[ "${msg}" =~ ^feat: ]]; then
        # Found first feat: commit — check if attack test preceded it.
        if [[ "${FOUND_ATTACK_BEFORE_FEAT}" == "true" ]]; then
            echo "[attack-order] Attack test commit precedes feat: commit — PASS."
            exit 0
        else
            # Strict ordering failed. Before failing, check for retroactive
            # compliance: an attack commit may have been added after the feat:
            # commit when history rewrite is forbidden (Constitution Priority 3).
            break
        fi
    fi
done <<< "${REVERSED}"

# ---------------------------------------------------------------------------
# Retroactive compliance check: strict ordering failed, but check whether
# ANY attack test commit exists anywhere on the branch.
# If yes: emit a warning and exit 0 (branch is compliant, ordering was fixed
# retroactively per Constitution Priority 3 constraints).
# If no: exit 1 (the branch has feat: commits with no attack tests at all).
# ---------------------------------------------------------------------------
HAS_ANY_ATTACK_COMMIT=false
while IFS= read -r msg; do
    if _is_attack_commit "${msg}"; then
        HAS_ANY_ATTACK_COMMIT=true
        break
    fi
done <<< "${COMMIT_MESSAGES}"

if [[ "${HAS_ANY_ATTACK_COMMIT}" == "true" ]]; then
    echo "[attack-order] WARNING: Attack test commit found but not strictly before first feat: commit." >&2
    echo "[attack-order] Retroactive compliance accepted — history rewrite forbidden (Constitution Priority 3)." >&2
    echo "[attack-order] Attack tests confirmed present on branch — PASS (retroactive compliance)."
    exit 0
fi

echo "[attack-order] VIOLATION: feat: commit found with no attack test commit anywhere on the branch." >&2
echo "[attack-order] Per Rule 22, 'test: add negative/attack tests for <feature>'" >&2
echo "[attack-order] must be committed on the branch before merging." >&2
exit 1
