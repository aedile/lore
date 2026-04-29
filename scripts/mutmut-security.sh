#!/usr/bin/env bash
# Mutation testing on security-critical modules.
#
# Runs mutmut against the shared/security/ modules only — not the entire
# codebase. This keeps wall-clock time manageable (target: <30 min on a
# developer laptop; full codebase would take hours).
#
# Target mutation score: >=60% (per CONSTITUTION Priority 4 / Phase 55 gate).
#
# Usage:
#   make mutmut                # via Makefile target
#   bash scripts/mutmut-security.sh  # direct invocation
#
# Output:
#   mutmut stores results in .mutmut_cache/ (gitignored).
#   Run 'poetry run mutmut results' after this script to view the report.
#   Run 'poetry run mutmut show <N>' to see the diff for a specific survivor.
#
# NOTE: Do NOT add this script to CI. Mutation testing is a developer tool
#       for periodic security assurance, not a per-commit gate.
#
# Task: T11.2 — Mutation Testing on Security Modules
set -euo pipefail

echo "Running mutation testing on security-critical modules..."
echo "This may take 20–30 minutes on a developer laptop."
echo ""
echo "Scope:"
echo "  src/lore_eligibility/shared/security/hmac_signing.py"
echo "  src/lore_eligibility/shared/security/audit.py"
echo "  src/lore_eligibility/shared/security/vault.py"
echo "  src/lore_eligibility/shared/security/air_gap.py"
echo "  src/lore_eligibility/shared/security/model_integrity.py"
echo "  src/lore_eligibility/shared/security/key_manager.py"
echo ""

poetry run mutmut run \
    --paths-to-mutate "src/lore_eligibility/shared/security/hmac_signing.py" \
    --paths-to-mutate "src/lore_eligibility/shared/security/audit.py" \
    --paths-to-mutate "src/lore_eligibility/shared/security/vault.py" \
    --paths-to-mutate "src/lore_eligibility/shared/security/air_gap.py" \
    --paths-to-mutate "src/lore_eligibility/shared/security/model_integrity.py" \
    --paths-to-mutate "src/lore_eligibility/shared/security/key_manager.py" \
    --runner "poetry run pytest tests/unit/ -x -q --tb=no --no-header --no-cov" \
    2>&1 || true

echo ""
echo "Mutation testing complete."
echo "Run 'poetry run mutmut results' to view the full report."
echo "Run 'poetry run mutmut show <N>' to inspect a surviving mutant."
echo ""

poetry run mutmut results 2>&1 || true
