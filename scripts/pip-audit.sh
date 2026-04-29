#!/usr/bin/env bash
# scripts/pip-audit.sh
#
# Supply chain audit wrapper for Lore Eligibility.
# Runs pip-audit against the project's installed dependencies with documented
# CVE exceptions. This script is invoked by scripts/ci-local.sh as a named gate.
#
# Usage:
#   bash scripts/pip-audit.sh          # Direct invocation
#   make ci-local                      # Via CI gate (preferred)
#
# Note on --strict: pip-audit --strict treats editable-package skips as fatal
# errors. Since lore_eligibility itself is installed as editable (poetry install), we
# omit --strict and use --skip-editable instead. The gate still fails on any
# unignored CVE; --strict is not required to achieve that behaviour.
#
# SBOM generation (CycloneDX JSON format, not a CI gate — on-demand only):
#   poetry run pip-audit --skip-editable --format cyclonedx-json > sbom.json
#
# To add a new CVE exception:
#   1. Add a comment above the --ignore-vuln line with CVE ID, affected package,
#      version range, justification, and tracking status.
#   2. Ensure the exception is also documented in docs/SUPPLY_CHAIN.md.
#   3. Set a review date — exceptions must be re-evaluated when fixes are released.

set -euo pipefail

# ---------------------------------------------------------------------------
# Build the pip-audit command with documented CVE exceptions.
# Each --ignore-vuln flag must be preceded by a justification comment.
# Undocumented exceptions are rejected by test_supply_chain_attack.py.
# ---------------------------------------------------------------------------

# Construct the argument list for pip-audit so each CVE exception can be
# accompanied by a comment directly above its --ignore-vuln flag.
AUDIT_ARGS=(
    --skip-editable
    --desc on
)

# CVE-2026-4539: pygments <=2.19.2 — ReDoS in AdlLexer (archetype.py).
# pygments is a dev-only dependency (REPL/documentation highlighting).
# No production code path reaches AdlLexer. No fix released at time of
# writing. Track: https://github.com/pygments/pygments/issues — review
# when pygments 2.20+ is released.
AUDIT_ARGS+=(--ignore-vuln CVE-2026-4539)

# CVE-2026-3219: pip <=26.0.1 — vulnerability in pip itself.
# As of 2026-04-17, pip 26.0.1 IS the latest available version; no upstream
# fix has been released yet (pip-audit reports no fix versions). pip is a
# build-time/CI-only tool; it is NOT installed or shipped as a production
# runtime dependency of lore_eligibility. The attack surface is limited to the
# CI runner bootstrap step and developer local environments.
# RESOLUTION: Remove this ignore when pip releases a version > 26.0.1 that
# fixes CVE-2026-3219. Track: https://github.com/pypa/pip/security/advisories
AUDIT_ARGS+=(--ignore-vuln CVE-2026-3219)

# CVE-2026-25645: RESOLVED — requests upgraded to 2.33.0+ (T13.0).
# Exception removed from audit script. Fix was to pin requests^2.33.0
# in pyproject.toml as a direct dependency constraint.

poetry run pip-audit "${AUDIT_ARGS[@]}" 2>&1
