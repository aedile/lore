#!/usr/bin/env python3
"""Scan test fixtures and sample data for PII-shaped values.

CONSTITUTION Priority 0 (HIPAA / PHI handling): no real PII may be
committed to the repository. CLAUDE.md states all test data must be
fictional / Faker-generated. This script is the programmatic gate
that enforces it.

Scans `tests/fixtures/`, `tests/integration/`, and `sample_data/` (any
that exist) for SSN-shaped, phone-shaped, real-looking-email-shaped,
and ISO-date-shaped substrings. Flags every match unless the line
carries an explicit `# pii-allowed: <reason>` comment.

Usage:
    python3 scripts/check_pii_in_fixtures.py
    python3 scripts/check_pii_in_fixtures.py path/to/dir [more/paths ...]

Exit codes:
    0 — clean
    1 — violations found (printed to stdout)
    2 — usage / runtime error

This script intentionally has zero third-party dependencies so it can
run in the bare pre-commit environment without the poetry venv.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------

SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
PHONE_RE = re.compile(r"\b(?:\+?1[-.\s])?\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}\b")
EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+\b")
# DOB: ISO date with year 1900-2030 (catches plausible birth dates while
# letting future-dated test timestamps through unflagged).
DOB_RE = re.compile(r"\b(?:19|20)\d{2}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])\b")

#: Email domains that are conventionally fictional and therefore exempt.
EXEMPT_EMAIL_DOMAINS: frozenset[str] = frozenset(
    {
        "example.com",
        "example.org",
        "example.net",
        "localhost",
        "noreply.invalid",
        "faker.com",
    }
)

#: Suffixes that mark a domain as fictional by convention (RFC 6761).
EXEMPT_EMAIL_SUFFIXES: tuple[str, ...] = (".invalid", ".test", ".local")

#: Per-line opt-out marker.
ALLOW_COMMENT_RE = re.compile(r"#\s*pii-allowed:", re.IGNORECASE)

#: File extensions that are scanned. Binary files (parquet, sqlite,
#: images) are skipped. SQL fixtures are scanned because partner-feed
#: examples are often committed as .sql.
SCANNED_EXTENSIONS: frozenset[str] = frozenset(
    {".py", ".json", ".jsonl", ".csv", ".tsv", ".txt", ".yaml", ".yml", ".sql", ".md"}
)

#: Default scan roots.
DEFAULT_ROOTS: tuple[str, ...] = (
    "tests/fixtures/",
    "tests/integration/",
    "sample_data/",
)


# ---------------------------------------------------------------------------
# Core scan
# ---------------------------------------------------------------------------


def is_email_exempt(email: str) -> bool:
    """Return True if the email's domain is conventionally fictional."""
    domain = email.rsplit("@", 1)[-1].lower()
    if domain in EXEMPT_EMAIL_DOMAINS:
        return True
    return any(domain.endswith(suffix) for suffix in EXEMPT_EMAIL_SUFFIXES)


def scan_line(line: str) -> list[tuple[str, str]]:
    """Return list of (kind, sample) tuples for PII matches in one line.

    A line ending with ``# pii-allowed: <reason>`` is exempt entirely.
    Empty list is returned when the line is clean or exempted.
    """
    if ALLOW_COMMENT_RE.search(line):
        return []
    findings: list[tuple[str, str]] = []
    for match in SSN_RE.finditer(line):
        findings.append(("SSN", match.group()))
    for match in PHONE_RE.finditer(line):
        findings.append(("phone", match.group()))
    for match in DOB_RE.finditer(line):
        findings.append(("DOB-shape", match.group()))
    for match in EMAIL_RE.finditer(line):
        if not is_email_exempt(match.group()):
            findings.append(("email", match.group()))
    return findings


def scan_file(path: Path) -> list[tuple[Path, int, str, str]]:
    """Scan a single file. Returns (path, lineno, kind, sample) per finding."""
    findings: list[tuple[Path, int, str, str]] = []
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            for lineno, line in enumerate(fh, start=1):
                for kind, sample in scan_line(line):
                    findings.append((path, lineno, kind, sample))
    except OSError as exc:  # noqa: BLE001 — graceful degrade on unreadable files
        print(f"WARN: could not read {path}: {exc}", file=sys.stderr)
    return findings


def collect_files(roots: list[str]) -> list[Path]:
    """Walk roots and return every file with a scanned extension."""
    files: list[Path] = []
    for root_str in roots:
        root = Path(root_str)
        if not root.exists():
            continue
        if root.is_file():
            if root.suffix.lower() in SCANNED_EXTENSIONS:
                files.append(root)
            continue
        for path in root.rglob("*"):
            if path.is_file() and path.suffix.lower() in SCANNED_EXTENSIONS:
                files.append(path)
    return files


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns process exit code."""
    parser = argparse.ArgumentParser(
        description="Scan test fixtures and sample data for PII-shaped values."
    )
    parser.add_argument(
        "paths",
        nargs="*",
        help="Files or directories to scan. Defaults to tests/fixtures/, "
        "tests/integration/, sample_data/.",
    )
    args = parser.parse_args(argv)

    roots = args.paths if args.paths else list(DEFAULT_ROOTS)
    files = collect_files(roots)

    all_findings: list[tuple[Path, int, str, str]] = []
    for path in files:
        all_findings.extend(scan_file(path))

    if not all_findings:
        return 0

    print(f"PII-shaped values found in {len({f[0] for f in all_findings})} file(s):")
    for path, lineno, kind, sample in all_findings:
        print(f"  {path}:{lineno} — {kind}: {sample}")
    print()
    print("If a line is intentionally fictional / Faker-generated test data, annotate it with:")
    print("    # pii-allowed: <one-sentence justification>")
    print()
    print(
        "If you committed real PII by accident, remove it immediately and "
        "follow CLAUDE.md PII Emergency procedure."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
