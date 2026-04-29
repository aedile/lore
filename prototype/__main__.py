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

from prototype.audit import AuditChain, AuditEvent
from prototype.canonical_lookup import PostgresCanonicalLookup
from prototype.csv_adapter import read_csv
from prototype.deletion import is_suppressed, operator_override
from prototype.demo import run_full_demo
from prototype.identity import TIER_1, TIER_2, TIER_3, TIER_4, TierThresholds
from prototype.verification import (
    VerificationSettings,
    create_app,
)

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

    _print_section("PRD #4 — Verification API live calls")
    _run_verification_demo(conn, args.fixtures)

    _print_section("BR-704 — Operator override (re-allow a suppressed identity)")
    _run_override_demo(conn, args.fixtures, result.audit_chain_path)

    _print_section("BR-402 — Brute-force progression (lockout after 3 failures)")
    _run_bruteforce_demo(conn, args.fixtures)

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


def _run_verification_demo(conn: object, fixtures_dir: Path) -> None:
    """Hit /v1/verify against PostgresCanonicalLookup with sample claims
    drawn from the day-1 fixture data and the deleted member, showing the
    XR-003 collapse to {VERIFIED, NOT_VERIFIED} across internal states."""
    from fastapi.testclient import TestClient

    lookup = PostgresCanonicalLookup(conn)
    client = TestClient(
        create_app(
            lookup=lookup,
            settings=VerificationSettings(response_floor_ms=10.0),
        )
    )

    # Pick three plaintext claims from the day-1 fixture CSV: a clean
    # PARTNER_A record (expect VERIFIED), the deletion-fixture record
    # (expect NOT_VERIFIED — DELETED state), and a not-found claim.
    rows = list(read_csv(fixtures_dir / "partner_a_day1.csv"))

    # Convert MM/DD/YYYY -> ISO YYYY-MM-DD for the API.
    def _iso(us_date: str) -> str:
        m, d, y = us_date.split("/")
        return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"

    # Find the deletion-fixture row from the inventory.
    import json as _json

    inventory = _json.loads((fixtures_dir / "scenario_inventory.json").read_text())
    deletion_pmid = next(
        e["partner_member_id"]
        for e in inventory["records"]
        if e["scenario"] == "deletion_fixture" and "partner_a_day1" in e["feed"]
    )
    deletion_row = next(r for r in rows if r["member_id"] == deletion_pmid)
    # Pick a clean record that won't be in any other scenario.
    clean_pmids = {
        e["partner_member_id"]
        for e in inventory["records"]
        if e["scenario"] == "clean" and "partner_a_day1" in e["feed"]
    }
    clean_row = next(r for r in rows if r["member_id"] in clean_pmids)

    cases = [
        (
            "Eligible member (active in canonical store)",
            clean_row["FirstName"],
            clean_row["LastName"],
            _iso(clean_row["DOB"]),
        ),
        (
            "Deleted member (DELETED state — internal collapse)",
            deletion_row["FirstName"],
            deletion_row["LastName"],
            _iso(deletion_row["DOB"]),
        ),
        ("Not found (no canonical member)", "Phantom", "Person", "1900-01-01"),
        (
            "Not found (different last name)",
            clean_row["FirstName"],
            "Different",
            _iso(clean_row["DOB"]),
        ),
    ]

    print(
        "  Hitting POST /v1/verify against PostgresCanonicalLookup. The\n"
        "  external response set is exactly {VERIFIED, NOT_VERIFIED} — same\n"
        "  shape across all internal states (BR-401 / XR-003 collapse).\n"
    )
    for label, first, last, dob in cases:
        body = {
            "claim": {"first_name": first, "last_name": last, "date_of_birth": dob},
            "context": {"client_id": "panel-demo", "request_id": "live"},
        }
        response = client.post("/v1/verify", json=body)
        status = response.json().get("status", "?")
        print(f"  {label:55s} -> {status}")


def _run_override_demo(conn: object, fixtures_dir: Path, chain_path: Path) -> None:
    """Demonstrate BR-704 operator override:

    1. Suppression hash for the deletion fixture's broad form is in the ledger.
    2. is_suppressed(...) returns True before override.
    3. Operator runs operator_override(target_hash, reason).
    4. is_suppressed(...) returns False after.
    5. DELETION_OVERRIDE event lands on the audit chain. Chain validates.
    """
    import json as _json

    inventory = _json.loads((fixtures_dir / "scenario_inventory.json").read_text())
    deletion_pmid = next(
        e["partner_member_id"]
        for e in inventory["records"]
        if e["scenario"] == "deletion_fixture" and "partner_a_day1" in e["feed"]
    )
    rows = list(read_csv(fixtures_dir / "partner_a_day1.csv"))
    target = next(r for r in rows if r["member_id"] == deletion_pmid)

    last_name = target["LastName"]
    m, d, y = target["DOB"].split("/")
    dob = f"{int(y):04d}-{int(m):02d}-{int(d):02d}"
    ssn_last4 = target["SSN"][-4:] if target["SSN"] else None

    # Simulate the day-2 reintroduction's identity (PARTNER_B:B99999 with
    # a name typo) — that's the record that got suppressed.
    reintro_last_name = _typo_last_name(last_name)
    suppressed_before = is_suppressed(
        conn,
        last_name=reintro_last_name,
        dob=dob,
        partner_id="PARTNER_B",
        partner_member_id="B99999",
        ssn_last4=ssn_last4,
    )
    print(f"  Before override: is_suppressed(...) = {suppressed_before}")

    # Look up a broad suppression hash from the ledger to override. The
    # broad hash is the only one that catches the cross-partner-name-typo
    # reintroduction; in production the operator UI would show it.
    cur = conn.cursor()
    cur.execute(
        """
        SELECT suppression_hash
          FROM deletion_ledger
         ORDER BY ledger_id DESC
        """
    )
    hashes = [row[0] for row in cur.fetchall()]

    # Try each hash; the broad one will lift the broad-hash suppression
    # for this identity.
    chain = AuditChain(chain_path)
    overridden_hashes: list[str] = []
    for h in hashes:
        try:
            event = operator_override(
                conn,
                target_hash=h,
                reason="legal-cleared re-enrollment after appeal",
            )
            chain.append(
                AuditEvent(
                    event_class=event.event_class,
                    actor_role=event.actor_role,
                    target_token=event.target_token,
                    outcome=event.outcome,
                    trigger=event.trigger,
                    context=event.context,
                )
            )
            overridden_hashes.append(h)
        except ValueError:
            # Hash not found — shouldn't happen since we read from the ledger.
            continue
    conn.commit()

    suppressed_after = is_suppressed(
        conn,
        last_name=reintro_last_name,
        dob=dob,
        partner_id="PARTNER_B",
        partner_member_id="B99999",
        ssn_last4=ssn_last4,
    )
    print(f"  After override:  is_suppressed(...) = {suppressed_after}")
    print(f"  Override applied to {len(overridden_hashes)} ledger row(s).")

    revalid = chain.validate()
    print(
        f"  Audit chain after DELETION_OVERRIDE event: "
        f"{'VALID' if revalid.valid else 'BROKEN at line ' + str(revalid.broken_at_line)}"
    )


def _typo_last_name(name: str) -> str:
    """Match the synthetic-data typo rule: drop the third character."""
    if len(name) < 3:
        return name + "x"
    return name[:2] + name[3:]


def _run_bruteforce_demo(conn: object, fixtures_dir: Path) -> None:
    """Demonstrate BR-402 progressive friction:

    1. Three failed verifies against a non-existent (name, dob) anchor lock it.
    2. A fourth verify on the same anchor still NOT_VERIFIED (lockout
       short-circuit) — even if we used the correct details.
    3. A verify against a DIFFERENT real identity still resolves to VERIFIED,
       proving lockout is per-anchor not global.
    """
    from fastapi.testclient import TestClient

    lookup = PostgresCanonicalLookup(conn)
    # Persistent TestClient so the in-memory BruteForceTracker accumulates
    # state across all attempts in this section.
    client = TestClient(
        create_app(
            lookup=lookup,
            settings=VerificationSettings(response_floor_ms=10.0),
        )
    )

    # Pick a real ELIGIBLE_ACTIVE clean record for the per-anchor isolation
    # test at the end.
    import json as _json

    inventory = _json.loads((fixtures_dir / "scenario_inventory.json").read_text())
    rows = list(read_csv(fixtures_dir / "partner_a_day1.csv"))
    clean_pmids = {
        e["partner_member_id"]
        for e in inventory["records"]
        if e["scenario"] == "clean" and "partner_a_day1" in e["feed"]
    }
    real_row = next(r for r in rows if r["member_id"] in clean_pmids)
    m, d, y = real_row["DOB"].split("/")
    real_dob_iso = f"{int(y):04d}-{int(m):02d}-{int(d):02d}"

    def _verify(first: str, last: str, dob: str, label: str) -> str:
        body = {
            "claim": {"first_name": first, "last_name": last, "date_of_birth": dob},
            "context": {"client_id": "panel-attacker", "request_id": label},
        }
        return client.post("/v1/verify", json=body).json().get("status", "?")

    # Three failures against the same fake anchor.
    print("  Attacker probes a non-existent identity 3 times:")
    for i in range(1, 4):
        status = _verify("Phantom", "Probe", "1900-01-01", f"attempt-{i}")
        print(f"    Attempt {i}: {status}")

    # Fourth attempt — same anchor, now locked out short-circuit.
    print()
    status = _verify("Phantom", "Probe", "1900-01-01", "attempt-4")
    print(f"  Attempt 4 on the locked anchor: {status}  (BR-402 short-circuit)")

    # Per-anchor isolation: a real eligible member on a different anchor
    # still resolves correctly.
    real_status = _verify(
        real_row["FirstName"],
        real_row["LastName"],
        real_dob_iso,
        "real-user-on-different-anchor",
    )
    print(f"  A real eligible member on a different anchor: {real_status}")
    print(
        "  Lockout is scoped per (name_token, dob_token); attackers cannot DoS "
        "the entire user base by probing one identity."
    )


if __name__ == "__main__":
    raise SystemExit(_cli())
