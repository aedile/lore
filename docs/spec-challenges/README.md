# Spec Challenges

This directory holds the output of the `spec-challenger` agent (CLAUDE.md
Rule 20). Before any phase containing a `feat:` commit, the PM MUST spawn
the spec-challenger with the full task spec; its output (missing acceptance
criteria, negative cases, attack vectors) is committed here as
`<task-id>.md` and incorporated into the developer brief.

The CI gate `scripts/check_spec_challenge.sh` audits the git log: if any
`feat:` commit exists on a branch, this directory must contain at least
one `.md` file.

## Filename convention

`P<phase>-T<task>.md`  — e.g. `P03-T3.1.md` for the spec challenge of
Phase 03 Task 1.
