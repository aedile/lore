"""Prototype CLI entry point — ``poetry run python -m prototype demo``.

Connects to a Postgres instance from a DATABASE_URL env var (default:
the docker-compose-dev-db fallback) and runs the full panel demo,
printing a human-readable summary of each acceptance criterion.

Use ``make prototype-demo`` for the wired-up wrapper.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import psycopg

from prototype.demo import run_full_demo
from prototype.identity import TIER_1, TIER_2, TIER_3, TIER_4, TierThresholds

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FIXTURES = REPO_ROOT / "prototype" / "fixtures"
DEFAULT_OUTPUT = REPO_ROOT / "prototype" / "data"

# Default DSN matches the `prototype-pg-up` Makefile target — a stock
# postgres:16-alpine container on port 5440 with user/password = postgres.
# Override via DATABASE_URL or --dsn for any other environment.
_DEFAULT_DSN = "postgresql://postgres:postgres@127.0.0.1:5440/lore_eligibility"


def _print_section(title: str) -> None:
    print()
    print("=" * 78)
    print(title)
    print("=" * 78)


def _cli() -> int:
    parser = argparse.ArgumentParser(prog="python -m prototype")
    sub = parser.add_subparsers(dest="cmd", required=True)

    demo_p = sub.add_parser("demo", help="Run the full end-to-end panel demo.")
    demo_p.add_argument("--dsn", default=os.environ.get("DATABASE_URL", _DEFAULT_DSN))
    demo_p.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    demo_p.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    demo_p.add_argument("--match-high", type=float, default=20.0)
    demo_p.add_argument("--match-review", type=float, default=-18.0)

    args = parser.parse_args()
    if args.cmd != "demo":
        parser.error(f"unknown command: {args.cmd}")

    print(f"Connecting to Postgres: {args.dsn}")
    try:
        conn = psycopg.connect(args.dsn)
    except psycopg.OperationalError as exc:
        print(f"\nFAILED to connect: {exc}", file=sys.stderr)
        print(
            "Hint: start the dev DB with `make dev-db-only` (docker-compose), then re-run.",
            file=sys.stderr,
        )
        return 2

    args.output.mkdir(parents=True, exist_ok=True)
    result = run_full_demo(
        conn,
        fixtures_dir=args.fixtures,
        output_dir=args.output,
        thresholds=TierThresholds(high=args.match_high, review=args.match_review),
    )

    _print_section("PRD #1 — Day-1 pipeline")
    for feed in result.day1.feeds:
        print(
            f"  {feed.partner_id:10s}  raw={feed.raw_records:4d}  "
            f"deduped={feed.after_dedup:4d}  quarantined={feed.quarantined:3d}  "
            f"feed_quarantined={feed.feed_quarantined}  drift={feed.schema_drift}"
        )
    print(f"  canonical_inserted = {result.day1.canonical_inserted}")
    print(f"  enrollments        = {result.day1.enrollments_inserted}")
    print(f"  match_decisions    = {result.day1.match_decisions_inserted}")
    print(
        f"  review_queue       = {result.day1.review_queue_inserted}  (Tier 3 cases awaiting human review)"
    )

    _print_section("PRD #3 — Tier histogram (day 1)")
    for tier in (TIER_1, TIER_2, TIER_3, TIER_4):
        print(f"  {tier:30s} {result.day1.tier_histogram.get(tier, 0):5d}")

    _print_section("PRD #3 — Tier histogram (day 2)")
    for tier in (TIER_1, TIER_2, TIER_3, TIER_4):
        print(f"  {tier:30s} {result.day2.tier_histogram.get(tier, 0):5d}")

    _print_section("PRD #3 — Review queue (Tier 3 cases for human review)")
    cur = conn.cursor()
    cur.execute(
        """
        SELECT rq.candidate_record_ref, rq.score, md.score_breakdown
          FROM review_queue rq
          JOIN match_decision md ON md.decision_id = rq.decision_id
         ORDER BY rq.score DESC
        """
    )
    rows = cur.fetchall()
    if not rows:
        print("  (empty)")
    print(f"  {len(rows)} record(s) awaiting human review.")
    print(
        "  Each row's score_breakdown carries Splink's per-comparison Bayes "
        "factors (bf_*)\n  so the reviewer sees exactly which fields "
        "supported or weakened the decision."
    )
    print()
    for ref, score, breakdown in rows[:6]:  # cap output for readability
        print(f"  {ref:30s} weight={score:8.3f}")
        if breakdown:
            import json as _json

            try:
                bd = _json.loads(breakdown) if isinstance(breakdown, str) else breakdown
            except _json.JSONDecodeError:
                bd = {}
            top_bfs = sorted(
                (
                    (k, v)
                    for k, v in bd.items()
                    if k.startswith("bf_") and not k.startswith("bf_tf_")
                ),
                key=lambda kv: -float(kv[1]) if isinstance(kv[1], int | float) else 0,
            )[:5]
            for k, v in top_bfs:
                if isinstance(v, int | float):
                    print(f"      {k:25s} = {v:11.4f}")
                else:
                    print(f"      {k:25s} = {v}")
    if len(rows) > 6:
        print(f"  ... + {len(rows) - 6} more queued for review")

    _print_section("PRD #7 — Deletion + day-2 SUPPRESSED_DELETED")
    print(f"  Deleted member_id    = {result.deletion_target_member_id}")
    print(f"  Day-2 suppressed     = {result.day2.suppressed_count}")

    _print_section("PRD #2 — Day-2 pipeline")
    for feed in result.day2.feeds:
        print(
            f"  {feed.partner_id:10s}  raw={feed.raw_records:4d}  "
            f"deduped={feed.after_dedup:4d}  quarantined={feed.quarantined:3d}  "
            f"drift={feed.schema_drift}"
        )
    print(f"  canonical_inserted        = {result.day2.canonical_inserted}")
    print(f"  enrollments               = {result.day2.enrollments_inserted}")
    print(f"  match_decisions           = {result.day2.match_decisions_inserted}")
    print(f"  member_history (SCD2)     = {result.day2.member_history_inserted}")

    _print_section("PRD #5 — Audit chain validation")
    v = result.audit_chain_validation
    status = "PASS" if v.valid else "FAIL"
    print(f"  status        = {status}")
    print(f"  events        = {result.audit_event_count}")
    print(f"  chain path    = {result.audit_chain_path}")
    if not v.valid:
        print(f"  broken at line = {v.broken_at_line}")
        print(f"  error         = {v.error}")

    _print_section("PRD #6 — Redaction scanner")
    if not result.redaction_matches:
        print("  PASS — zero PII pattern matches across the audit chain.")
    else:
        print(f"  FAIL — {len(result.redaction_matches)} matches:")
        for m in result.redaction_matches[:5]:
            print(f"    {m.path}:{m.line_number}  {m.pattern_name}  '{m.excerpt}'")

    _print_section("Summary")
    pass_count = sum(
        [
            all(not f.feed_quarantined for f in result.day1.feeds),
            result.day2.member_history_inserted >= 1,
            result.day1.tier_histogram.get(TIER_2, 0) + result.day2.tier_histogram.get(TIER_2, 0)
            >= 1,
            v.valid,
            result.redaction_matches == [],
            result.day2.suppressed_count >= 1,
        ]
    )
    print(f"  Acceptance criteria covered by demo: {pass_count}/6")
    print(f"  Audit chain artifact: {result.audit_chain_path}")
    print()

    return 0 if (v.valid and not result.redaction_matches) else 1


if __name__ == "__main__":
    raise SystemExit(_cli())
