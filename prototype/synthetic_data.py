"""Synthetic data harness — A1 from PROTOTYPE_PRD.md.

Produces four reproducible CSV partner feeds (two synthetic partners x day-1 +
day-2) plus a scenario inventory JSON. Same seed produces byte-identical output.

Two partners deliberately use different schemas, date formats, and SSN
representations so the per-partner mapping engine (A2) and DQ engine (A3) have
real heterogeneity to chew on. Cross-partner near-duplicates seed the identity
resolution work in A4.

Running standalone:

    python -m prototype.synthetic_data --seed 42 --output prototype/fixtures
"""

from __future__ import annotations

import argparse
import csv
import json
import random
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from faker import Faker

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PARTNER_A = "PARTNER_A"
PARTNER_B = "PARTNER_B"

# PARTNER_A: PascalCase + snake_case mix, US date format, full SSN.
# PARTNER_A day 2 adds EligibilityStartDate — additive schema drift (BR-304).
PARTNER_A_DAY1_COLUMNS: list[str] = [
    "member_id",
    "FirstName",
    "LastName",
    "DOB",
    "SSN",
    "Street",
    "City",
    "State",
    "Zip",
    "Phone",
    "Email",
]
PARTNER_A_DAY2_COLUMNS: list[str] = [*PARTNER_A_DAY1_COLUMNS, "EligibilityStartDate"]

# PARTNER_B: snake_case throughout, ISO date format, ssn_last4 only.
PARTNER_B_COLUMNS: list[str] = [
    "ext_id",
    "given_name",
    "family_name",
    "date_of_birth",
    "ssn_last4",
    "address_line1",
    "address_city",
    "address_state",
    "address_zip",
    "phone_number",
    "email_address",
]

# Scenario tags written into the inventory.
SCENARIO_LEGEND: dict[str, str] = {
    "clean": "Normal record, all required fields populated, no mutations.",
    "within_feed_duplicate_winner": (
        "Last occurrence of a duplicated partner_member_id within a feed; "
        "should win in BR-601 last-record-wins dedup."
    ),
    "within_feed_duplicate_loser": (
        "Earlier occurrence of a duplicated partner_member_id; "
        "loses to the later row in BR-601 dedup."
    ),
    "missing_required_last_name": (
        "Last name field is empty — should fail BR-301 Required-tier validation "
        "and route to per-record quarantine (BR-302)."
    ),
    "invalid_required_dob": ("DOB field is empty — should fail BR-301 Required-tier validation."),
    "format_error_short_year": (
        "DOB rendered with 2-digit year (e.g., '4/12/85') — exercises "
        "date-format normalization in the DQ engine (A3)."
    ),
    "cross_partner_near_match": (
        "Same underlying truth identity present in both PARTNER_A and PARTNER_B "
        "feeds with deliberate mutations (name typo, address format diff). "
        "The Splink/DuckDB resolver (A4) must merge these via Tier 2 or "
        "queue them at Tier 3."
    ),
    "deletion_fixture": (
        "Drives the BR-701..BR-704 demonstration: appears on PARTNER_A day 1, "
        "absent from PARTNER_A day 2 (deleted between snapshots), "
        "re-introduced on PARTNER_B day 2 with a name typo. The deletion "
        "ledger must suppress the re-introduction to SUPPRESSED_DELETED."
    ),
    "tier3_ambiguity": (
        "Real-world coincidence: a PARTNER_B record shares first_name and "
        "ssn_last4 with a PARTNER_A truth but has different DOB + different "
        "last_name. Splink's match weight lands between the review and "
        "auto-merge thresholds (BR-101 Tier 3) — the pair routes to the "
        "review queue with the per-comparison breakdown so a human can "
        "decide MERGE vs DISTINCT."
    ),
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SyntheticDatasetSummary:
    """Result handle returned by ``generate``."""

    output_dir: Path
    seed: int
    feed_paths: dict[str, Path]
    inventory_path: Path


def generate(
    output_dir: Path | str,
    *,
    seed: int = 42,
    count_per_partner: int = 300,
) -> SyntheticDatasetSummary:
    """Generate four CSV feeds plus a scenario-inventory JSON file.

    Same ``seed`` produces byte-identical output across runs.
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    rng = random.Random(seed)
    faker = Faker(locale="en_US")
    faker.seed_instance(seed)

    truth_pool = _build_truth_pool(faker, rng, count=count_per_partner * 2)
    scenarios = _assign_scenarios(rng, truth_pool, count_per_partner)

    inventory_records: list[dict[str, Any]] = []
    feed_paths: dict[str, Path] = {}

    for feed_key, columns, rows, inv in _build_all_feeds(scenarios, count_per_partner):
        path = out / f"{feed_key}.csv"
        _write_csv(path, columns, rows)
        feed_paths[feed_key] = path
        for entry in inv:
            entry["feed"] = f"{feed_key}.csv"
            inventory_records.append(entry)

    inventory_path = out / "scenario_inventory.json"
    inventory_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "seed": seed,
                "count_per_partner": count_per_partner,
                "partners": [PARTNER_A, PARTNER_B],
                "scenarios": SCENARIO_LEGEND,
                "records": inventory_records,
            },
            indent=2,
        )
        + "\n",
    )

    return SyntheticDatasetSummary(
        output_dir=out,
        seed=seed,
        feed_paths=feed_paths,
        inventory_path=inventory_path,
    )


# ---------------------------------------------------------------------------
# Truth pool — the underlying "real" people the partner feeds project from.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TruthPerson:
    """An underlying synthetic identity. Both partners may project rows from it."""

    truth_id: str
    first_name: str
    last_name: str
    dob: date
    ssn: str  # full XXX-XX-XXXX, 900-prefix (ITIN range, never a real SSN)
    street: str
    city: str
    state: str
    zip_code: str
    phone: str
    email: str


def _build_truth_pool(faker: Faker, rng: random.Random, count: int) -> list[TruthPerson]:
    pool: list[TruthPerson] = []
    for i in range(count):
        first = faker.first_name()
        last = faker.last_name()
        # DOB between 1940 and 2005 — reasonable Medicare ACO eligibility range.
        dob_year = rng.randint(1940, 2005)
        dob_month = rng.randint(1, 12)
        dob_day = rng.randint(1, 28)
        dob = date(dob_year, dob_month, dob_day)
        pool.append(
            TruthPerson(
                truth_id=f"T{i:05d}",
                first_name=first,
                last_name=last,
                dob=dob,
                ssn=_fake_ssn(rng),
                street=faker.street_address(),
                city=faker.city(),
                state=faker.state_abbr(),
                zip_code=faker.zipcode(),
                phone=faker.numerify("###-###-####"),
                email=f"{first.lower()}.{last.lower()}@example.invalid",
            )
        )
    return pool


def _fake_ssn(rng: random.Random) -> str:
    """Return a fictional SSN in the 900-99-XXXX range (never issued as a real SSN)."""
    area = rng.randint(900, 999)
    group = rng.randint(70, 99)
    serial = rng.randint(1, 9999)
    return f"{area:03d}-{group:02d}-{serial:04d}"


# ---------------------------------------------------------------------------
# Scenario assignment — deterministic given seed
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Scenarios:
    """Indices/handles for the deliberately problematic rows in each feed."""

    partner_a_pool: list[TruthPerson]
    partner_b_pool: list[TruthPerson]
    cross_match_truths: list[TruthPerson]
    a_within_feed_dup_truth: TruthPerson
    a_missing_lname_truth: TruthPerson
    a_invalid_dob_truth: TruthPerson
    a_short_year_truth: TruthPerson
    deletion_truth: TruthPerson
    b_within_feed_dup_truth: TruthPerson
    b_missing_lname_truth: TruthPerson
    b_invalid_dob_truth: TruthPerson
    b_short_year_truth: TruthPerson
    # PARTNER_A truths whose first_name + ssn_last4 are reused by a separate
    # PARTNER_B doppelganger to produce a Tier 3 review-queue case.
    tier3_a_originals: list[TruthPerson]
    # Synthetic PARTNER_B records that collide on first_name + ssn_last4 only
    # — different real people, surfaced for human review.
    tier3_b_doppelgangers: list[TruthPerson]


def _assign_scenarios(
    rng: random.Random,
    pool: list[TruthPerson],
    count_per_partner: int,
) -> Scenarios:
    """Carve the truth pool into per-partner slices and pick scenario fixtures.

    The slices overlap only on the cross-partner-match truths so the rest of
    the records remain disjoint between partners.
    """
    partner_a_pool = list(pool[:count_per_partner])
    partner_b_pool = list(pool[count_per_partner : count_per_partner * 2])

    # Cross-partner near-matches: pick two truth-people from PARTNER_A's slice
    # and have them ALSO appear in PARTNER_B (mutated). The truth identity is
    # shared; the projected rows differ.
    cross_match_truths = [partner_a_pool[5], partner_a_pool[10]]

    # Tier-3 ambiguity originals — pick two PARTNER_A truths and synthesise
    # PARTNER_B doppelgangers that share their first_name + ssn_last4 only.
    tier3_a_originals = [partner_a_pool[50], partner_a_pool[55]]
    tier3_b_doppelgangers = _build_tier3_doppelgangers(tier3_a_originals, rng)

    return Scenarios(
        partner_a_pool=partner_a_pool,
        partner_b_pool=partner_b_pool,
        cross_match_truths=cross_match_truths,
        a_within_feed_dup_truth=partner_a_pool[20],
        a_missing_lname_truth=partner_a_pool[25],
        a_invalid_dob_truth=partner_a_pool[30],
        a_short_year_truth=partner_a_pool[35],
        deletion_truth=partner_a_pool[40],
        b_within_feed_dup_truth=partner_b_pool[5],
        b_missing_lname_truth=partner_b_pool[10],
        b_invalid_dob_truth=partner_b_pool[15],
        b_short_year_truth=partner_b_pool[20],
        tier3_a_originals=tier3_a_originals,
        tier3_b_doppelgangers=tier3_b_doppelgangers,
    )


def _build_tier3_doppelgangers(
    originals: list[TruthPerson],
    rng: random.Random,
) -> list[TruthPerson]:
    """Generate synthetic doppelgangers — different real people who share
    first_name + ssn_last4 with the originals. Different DOB + last_name +
    everything else, so Splink scores them at Tier 3 (review).
    """
    surnames = ["Anderson", "Williams", "Robinson", "Mitchell", "Jackson", "Patterson"]
    cities = ["Austin", "Boulder", "Cleveland", "Dover", "El Paso", "Frankfort"]
    states = ["TX", "CO", "OH", "DE", "TX", "KY"]

    doppels: list[TruthPerson] = []
    for i, orig in enumerate(originals):
        # Shift DOB by 10-15 years and rotate month/day so it's clearly
        # a different person born in a different decade.
        year_shift = rng.choice([-15, -10, 10, 15])
        new_year = max(1940, min(2005, orig.dob.year + year_shift))
        new_dob = date(new_year, ((orig.dob.month + 6) % 12) + 1, ((orig.dob.day + 7) % 28) + 1)
        # Same last 4 of SSN, different prefix.
        last4 = orig.ssn[-4:]
        new_area = rng.randint(900, 999)
        new_group = rng.randint(70, 99)
        new_ssn = f"{new_area:03d}-{new_group:02d}-{last4}"

        new_last = surnames[i % len(surnames)]
        new_city = cities[i % len(cities)]
        new_state = states[i % len(states)]
        new_first = orig.first_name  # shared with the PARTNER_A original
        doppels.append(
            TruthPerson(
                truth_id=f"T3D{i:03d}",
                first_name=new_first,
                last_name=new_last,
                dob=new_dob,
                ssn=new_ssn,
                street=f"{rng.randint(100, 999)} Different Ave",
                city=new_city,
                state=new_state,
                zip_code=f"{rng.randint(10000, 99999):05d}",
                phone=f"{rng.randint(200, 999):03d}-{rng.randint(200, 999):03d}-{rng.randint(1000, 9999):04d}",
                email=f"{new_first.lower()}.{new_last.lower()}@example.invalid",
            )
        )
    return doppels


# ---------------------------------------------------------------------------
# Feed builders
# ---------------------------------------------------------------------------


def _build_all_feeds(
    s: Scenarios,
    count_per_partner: int,
) -> list[tuple[str, list[str], list[dict[str, str]], list[dict[str, Any]]]]:
    return [
        ("partner_a_day1", PARTNER_A_DAY1_COLUMNS, *_build_partner_a_day1(s)),
        ("partner_a_day2", PARTNER_A_DAY2_COLUMNS, *_build_partner_a_day2(s)),
        ("partner_b_day1", PARTNER_B_COLUMNS, *_build_partner_b_day1(s)),
        ("partner_b_day2", PARTNER_B_COLUMNS, *_build_partner_b_day2(s)),
    ]


def _build_partner_a_day1(
    s: Scenarios,
) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
    rows: list[dict[str, str]] = []
    inventory: list[dict[str, Any]] = []

    for idx, person in enumerate(s.partner_a_pool):
        member_id = f"A{idx:05d}"
        scenario, mutations = _scenario_for_partner_a(person, s)
        row = _project_partner_a(person, member_id, mutations=mutations)
        rows.append(row)
        inventory.append(_inventory_entry(member_id, person.truth_id, scenario))

        # Within-feed duplicate: emit a SECOND row with the same member_id but
        # a different street (last record wins per BR-601).
        if scenario == "within_feed_duplicate_loser":
            row2 = _project_partner_a(person, member_id, mutations=("alt_street",))
            rows.append(row2)
            inventory.append(
                _inventory_entry(member_id, person.truth_id, "within_feed_duplicate_winner")
            )

    return rows, inventory


def _scenario_for_partner_a(person: TruthPerson, s: Scenarios) -> tuple[str, tuple[str, ...]]:
    if person.truth_id == s.a_within_feed_dup_truth.truth_id:
        return "within_feed_duplicate_loser", ()
    if person.truth_id == s.a_missing_lname_truth.truth_id:
        return "missing_required_last_name", ("blank_last_name",)
    if person.truth_id == s.a_invalid_dob_truth.truth_id:
        return "invalid_required_dob", ("blank_dob",)
    if person.truth_id == s.a_short_year_truth.truth_id:
        return "format_error_short_year", ("short_year_dob",)
    if person.truth_id == s.deletion_truth.truth_id:
        return "deletion_fixture", ()
    if any(person.truth_id == t.truth_id for t in s.cross_match_truths):
        return "cross_partner_near_match", ()
    return "clean", ()


def _scenario_for_partner_b(person: TruthPerson, s: Scenarios) -> tuple[str, tuple[str, ...]]:
    if person.truth_id == s.b_within_feed_dup_truth.truth_id:
        return "within_feed_duplicate_loser", ()
    if person.truth_id == s.b_missing_lname_truth.truth_id:
        return "missing_required_last_name", ("blank_last_name",)
    if person.truth_id == s.b_invalid_dob_truth.truth_id:
        return "invalid_required_dob", ("blank_dob",)
    if person.truth_id == s.b_short_year_truth.truth_id:
        return "format_error_short_year", ("short_year_dob",)
    return "clean", ()


def _build_partner_a_day2(
    s: Scenarios,
) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
    """Day 2 = day 1 minus the deletion fixture, plus the EligibilityStartDate column."""
    rows: list[dict[str, str]] = []
    inventory: list[dict[str, Any]] = []

    eligibility_start = date(2026, 1, 1).isoformat()

    for idx, person in enumerate(s.partner_a_pool):
        member_id = f"A{idx:05d}"
        if person.truth_id == s.deletion_truth.truth_id:
            # Absent on day 2 — this is the "deletion between days" fixture.
            continue

        scenario, mutations = _scenario_for_partner_a(person, s)
        # On day 2, drop the day-1-specific within-feed dup so we don't carry
        # the duplicate forward — it's a day-1 phenomenon. Day 2 just shows
        # the canonical post-dedup view.
        if scenario == "within_feed_duplicate_loser":
            scenario, mutations = "clean", ()

        row = _project_partner_a(person, member_id, mutations=mutations)
        row["EligibilityStartDate"] = eligibility_start
        rows.append(row)
        inventory.append(_inventory_entry(member_id, person.truth_id, scenario))

    return rows, inventory


def _build_partner_b_day1(
    s: Scenarios,
) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
    """PARTNER_B day 1 = its own pool + cross-partner near-matches.

    Native PARTNER_B records carry their own scenarios (within-feed duplicate,
    missing last name, invalid DOB, short-year format error) so the DQ engine
    has problematic rows to chew on for both partners.
    """
    rows: list[dict[str, str]] = []
    inventory: list[dict[str, Any]] = []

    for idx, person in enumerate(s.partner_b_pool):
        ext_id = f"B{idx:05d}"
        scenario, mutations = _scenario_for_partner_b(person, s)
        rows.append(_project_partner_b(person, ext_id, mutations=mutations))
        inventory.append(_inventory_entry(ext_id, person.truth_id, scenario))

        # Within-feed duplicate (loser → winner).
        if scenario == "within_feed_duplicate_loser":
            rows.append(_project_partner_b(person, ext_id, mutations=("alt_street",)))
            inventory.append(
                _inventory_entry(ext_id, person.truth_id, "within_feed_duplicate_winner")
            )

    # Cross-partner near-matches: same truths as in PARTNER_A.
    for offset, truth in enumerate(s.cross_match_truths):
        ext_id = f"B9{offset:04d}"
        mutation = "name_typo_last" if offset == 0 else "address_format_diff"
        rows.append(_project_partner_b(truth, ext_id, mutations=(mutation,)))
        inventory.append(_inventory_entry(ext_id, truth.truth_id, "cross_partner_near_match"))

    # Tier-3 ambiguity doppelgangers — share first_name + ssn_last4 with a
    # PARTNER_A original but are different people. Splink scores them in the
    # review-queue band.
    for offset, doppel in enumerate(s.tier3_b_doppelgangers):
        ext_id = f"B8{offset:04d}"
        rows.append(_project_partner_b(doppel, ext_id))
        entry = _inventory_entry(ext_id, doppel.truth_id, "tier3_ambiguity")
        entry["paired_with_truth_id"] = s.tier3_a_originals[offset].truth_id
        inventory.append(entry)

    return rows, inventory


def _build_partner_b_day2(
    s: Scenarios,
) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
    """PARTNER_B day 2 = day 1 carry-forward + reintroduction of the deletion fixture.

    Within-feed duplicates are not carried forward (they're a day-1 ingestion
    phenomenon). Required-tier failures persist (those records are still
    broken on the partner side).
    """
    rows: list[dict[str, str]] = []
    inventory: list[dict[str, Any]] = []

    for idx, person in enumerate(s.partner_b_pool):
        ext_id = f"B{idx:05d}"
        scenario, mutations = _scenario_for_partner_b(person, s)
        if scenario == "within_feed_duplicate_loser":
            scenario, mutations = "clean", ()
        rows.append(_project_partner_b(person, ext_id, mutations=mutations))
        inventory.append(_inventory_entry(ext_id, person.truth_id, scenario))

    for offset, truth in enumerate(s.cross_match_truths):
        ext_id = f"B9{offset:04d}"
        mutation = "name_typo_last" if offset == 0 else "address_format_diff"
        rows.append(_project_partner_b(truth, ext_id, mutations=(mutation,)))
        inventory.append(_inventory_entry(ext_id, truth.truth_id, "cross_partner_near_match"))

    # Deletion-fixture reintroduction with last-name typo — Identity Resolution
    # must link it back to the (deleted) canonical record and route to
    # SUPPRESSED_DELETED via the deletion ledger (BR-703).
    deletion_ext_id = "B99999"
    rows.append(
        _project_partner_b(s.deletion_truth, deletion_ext_id, mutations=("name_typo_last",))
    )
    inventory.append(
        _inventory_entry(deletion_ext_id, s.deletion_truth.truth_id, "deletion_fixture")
    )

    return rows, inventory


# ---------------------------------------------------------------------------
# Projection: TruthPerson + mutations -> partner-shaped row
# ---------------------------------------------------------------------------


def _project_partner_a(
    person: TruthPerson,
    member_id: str,
    *,
    mutations: tuple[str, ...] = (),
) -> dict[str, str]:
    last_name = "" if "blank_last_name" in mutations else person.last_name
    if "short_year_dob" in mutations:
        dob_str = f"{person.dob.month}/{person.dob.day}/{person.dob.year % 100}"
    elif "blank_dob" in mutations:
        dob_str = ""
    else:
        dob_str = person.dob.strftime("%m/%d/%Y")

    street = person.street if "alt_street" not in mutations else _alt_street(person.street)

    return {
        "member_id": member_id,
        "FirstName": person.first_name,
        "LastName": last_name,
        "DOB": dob_str,
        "SSN": person.ssn,
        "Street": street,
        "City": person.city,
        "State": person.state,
        "Zip": person.zip_code,
        "Phone": person.phone,
        "Email": person.email,
    }


def _project_partner_b(
    person: TruthPerson,
    ext_id: str,
    *,
    mutations: tuple[str, ...] = (),
) -> dict[str, str]:
    if "blank_last_name" in mutations:
        last_name = ""
    elif "name_typo_last" in mutations:
        last_name = _typo_last_name(person.last_name)
    else:
        last_name = person.last_name

    if "blank_dob" in mutations:
        dob_str = ""
    elif "short_year_dob" in mutations:
        # PARTNER_B uses ISO; the format-error variant is YY-MM-DD.
        dob_str = f"{person.dob.year % 100:02d}-{person.dob.month:02d}-{person.dob.day:02d}"
    else:
        dob_str = person.dob.isoformat()

    if "address_format_diff" in mutations:
        address_line1 = _reformat_address(person.street)
    elif "alt_street" in mutations:
        address_line1 = _alt_street(person.street)
    else:
        address_line1 = person.street

    return {
        "ext_id": ext_id,
        "given_name": person.first_name,
        "family_name": last_name,
        "date_of_birth": dob_str,
        "ssn_last4": person.ssn[-4:],
        "address_line1": address_line1,
        "address_city": person.city,
        "address_state": person.state,
        "address_zip": person.zip_code,
        "phone_number": person.phone,
        "email_address": person.email,
    }


def _typo_last_name(name: str) -> str:
    """Drop one of the consonants — e.g., 'Johnson' -> 'Jonson'."""
    if len(name) < 3:
        return name + "x"
    return name[:2] + name[3:]


def _reformat_address(street: str) -> str:
    """Replace 'Apt N' with '#N' or vice versa to trip naive SQL dedup."""
    if " Apt " in street:
        return street.replace(" Apt ", " #", 1)
    return street + " #1"


def _alt_street(street: str) -> str:
    """Return a different-but-related street string for the duplicate-loser row."""
    return f"{street} (prior)"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _inventory_entry(partner_member_id: str, truth_id: str, scenario: str) -> dict[str, Any]:
    return {
        "partner_member_id": partner_member_id,
        "truth_id": truth_id,
        "scenario": scenario,
    }


def _write_csv(path: Path, columns: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({col: row.get(col, "") for col in columns})


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _cli() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic partner feeds (PRD A1).")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=Path, default=Path("prototype/fixtures"))
    parser.add_argument("--count-per-partner", type=int, default=300)
    args = parser.parse_args()

    summary = generate(
        args.output,
        seed=args.seed,
        count_per_partner=args.count_per_partner,
    )
    print(f"seed={summary.seed}  output_dir={summary.output_dir}")
    for key, path in summary.feed_paths.items():
        print(f"  {key:18s} {path}")
    print(f"  inventory          {summary.inventory_path}")


if __name__ == "__main__":
    _cli()
