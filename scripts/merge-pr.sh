#!/usr/bin/env bash
# scripts/merge-pr.sh
#
# Programmatic merge gate — the ONLY way to merge a PR in this project.
# Runs local CI, records audit entry, and merges only on PASS.
#
# This script replaces direct `gh pr merge` calls. CLAUDE.md Rule 12
# mandates this script as the merge mechanism. Direct `gh pr merge`
# is a process violation.
#
# Usage:
#   make merge-pr PR=<number>
#   bash scripts/merge-pr.sh <pr-number>
#
# What it does:
#   1. Fetches the PR branch and checks it out
#   2. Unsets SKIP_MUTMUT — mutation gate ALWAYS runs at merge (Constitution P1)
#   3. Runs scripts/ci-local.sh (full quality gate battery)
#   4. If CI FAILS: prints error, refuses to merge, exits 1
#   5. If CI PASSES: stages+commits the audit entry, pushes, merges via gh
#
# This is a PROGRAMMATIC GATE. There is no --force, --skip, or override flag.
# If CI fails, the only path forward is to fix the code and try again.
#
# SKIP_MUTMUT: This script unconditionally unsets SKIP_MUTMUT before running
# ci-local.sh. The mutation gate MUST run at merge time regardless of any
# developer-set environment variables. This implements Constitution Priority 1:
# "Quality Gates are Unbreakable."

set -euo pipefail

# ---------------------------------------------------------------------------
# Argument validation
# ---------------------------------------------------------------------------

PR_NUMBER="${1:-}"

if [[ -z "${PR_NUMBER}" ]]; then
    echo "ERROR: PR number required."
    echo "Usage: make merge-pr PR=<number>"
    echo "       bash scripts/merge-pr.sh <pr-number>"
    exit 1
fi

# ---------------------------------------------------------------------------
# Verify gh CLI is available and authenticated
# ---------------------------------------------------------------------------

if ! command -v gh &>/dev/null; then
    echo "ERROR: gh CLI not found. Install: https://cli.github.com/"
    exit 1
fi

if ! gh auth status &>/dev/null; then
    echo "ERROR: gh CLI not authenticated. Run: gh auth login"
    exit 1
fi

# ---------------------------------------------------------------------------
# Fetch PR metadata
# ---------------------------------------------------------------------------

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  Lore Eligibility — Merge Gate                                     ║"
echo "║  PR: #${PR_NUMBER}                                         ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

PR_BRANCH=$(gh pr view "${PR_NUMBER}" --json headRefName --jq '.headRefName' 2>/dev/null)
if [[ -z "${PR_BRANCH}" ]]; then
    echo "ERROR: Could not resolve branch for PR #${PR_NUMBER}."
    echo "       Is the PR open? Is the repo correct?"
    exit 1
fi

PR_TITLE=$(gh pr view "${PR_NUMBER}" --json title --jq '.title')
echo "  Branch: ${PR_BRANCH}"
echo "  Title:  ${PR_TITLE}"
echo ""

# ---------------------------------------------------------------------------
# Checkout the PR branch
# ---------------------------------------------------------------------------

echo "Fetching and checking out PR branch..."
git fetch origin "${PR_BRANCH}" 2>/dev/null
git checkout "${PR_BRANCH}" 2>/dev/null
git pull origin "${PR_BRANCH}" --ff-only 2>/dev/null

# ---------------------------------------------------------------------------
# Enforce mutation gate — unset SKIP_MUTMUT unconditionally
#
# SKIP_MUTMUT=1 is permitted only for local development runs.
# At merge time, the mutation gate MUST always execute.
# This implements Constitution Priority 1: "Quality Gates are Unbreakable."
# ---------------------------------------------------------------------------

if [[ -n "${SKIP_MUTMUT:-}" ]]; then
    echo ""
    echo "  NOTE: SKIP_MUTMUT was set to '${SKIP_MUTMUT}' — unsetting for merge run."
    echo "        The mutation gate runs unconditionally at merge time."
fi
unset SKIP_MUTMUT

# ---------------------------------------------------------------------------
# Run local CI
# ---------------------------------------------------------------------------

echo ""
echo "Running local CI pipeline..."
echo ""

if bash scripts/ci-local.sh; then
    CI_RESULT="PASS"
else
    CI_RESULT="FAIL"
fi

# ---------------------------------------------------------------------------
# Gate decision
# ---------------------------------------------------------------------------

if [[ "${CI_RESULT}" == "FAIL" ]]; then
    echo ""
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║  ✗ MERGE BLOCKED — CI FAILED                              ║"
    echo "║                                                            ║"
    echo "║  Fix the failing gates and run: make merge-pr PR=${PR_NUMBER}  ║"
    echo "║  Direct 'gh pr merge' is a process violation.              ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    exit 1
fi

# ---------------------------------------------------------------------------
# CI passed — commit audit entry and merge
# ---------------------------------------------------------------------------

echo ""
echo "CI passed. Committing audit entry and merging..."

# Stage and commit the audit log update
git add docs/ci-audit.jsonl
# Rescan secrets baseline — ci-audit SHA-256 integrity hashes trigger detect-secrets
poetry run detect-secrets scan > .secrets.baseline
git add .secrets.baseline
git commit -m "chore: ci-audit PASS — $(git rev-parse --short HEAD) on ${PR_BRANCH}

Local CI pipeline passed all gates. Audit entry appended to docs/ci-audit.jsonl.
This commit is auto-generated by scripts/merge-pr.sh (Constitution Priority 1)."

# Push the audit commit
git push origin "${PR_BRANCH}"

# Merge the PR (--merge preserves TDD commit trail per Constitution Priority 3)
gh pr merge "${PR_NUMBER}" --merge --body "Merged via \`make merge-pr\` — local CI PASS verified.

Audit trail: \`docs/ci-audit.jsonl\` contains the CI run record for this merge."

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  ✓ PR #${PR_NUMBER} MERGED — CI PASS verified               ║"
echo "╚══════════════════════════════════════════════════════════════╝"
