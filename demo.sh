#!/usr/bin/env bash
# demo.sh — Panel rehearsal driver for the lore-eligibility prototype.
#
# Brings up a one-shot Postgres on port 5440, runs the full A1->A8
# pipeline, prints a section per PRD acceptance criterion, and tears
# down. Re-runnable: setup_db drops tables first.
#
# Usage:
#     ./demo.sh
#
# Exits non-zero if the audit chain breaks or the redaction scanner
# finds anything.

set -euo pipefail

cd "$(dirname "$(realpath "$0")")"

cleanup() {
    echo ""
    echo ">>> Tearing down Postgres..."
    make prototype-pg-down >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo ">>> Lore Eligibility — Case Study 3 panel demo (one-command driver)"
echo ""
echo ">>> Spawning one-shot Postgres on 127.0.0.1:5440..."
make prototype-pg-up

echo ""
echo ">>> Running prototype demo..."
echo ""
make prototype-demo
demo_status=$?

if [[ $demo_status -eq 0 ]]; then
    echo ""
    echo ">>> Demo PASSED. Audit chain valid; redaction scanner clean."
else
    echo ""
    echo ">>> Demo FAILED with exit code $demo_status." >&2
fi

exit $demo_status
