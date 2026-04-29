#!/usr/bin/env python3
"""Mock-free integration test enforcement gate (T50.5).

Scans all ``test_*.py`` files in the target directory (default:
``tests/integration/``) and fails if any file imports or references
``unittest.mock``, ``MagicMock``, ``AsyncMock``, ``patch``, or ``Mock``
in actual code (not comments or docstrings) without a valid
``# integration-mock-allowed: <justification>`` comment on the same line.

The scanner detects mock patterns in **code lines only** — pure comment lines
(starting with ``#``) and docstring content are excluded to prevent false
positives from documentation that mentions mock names for educational purposes.

Usage
-----
    python scripts/check_integration_mocks.py [<directory>]

Arguments
---------
directory
    Directory to scan. Defaults to ``tests/integration/`` relative to the
    project root (two levels above this script's location).

Exit codes
----------
0
    No unapproved mock usage found.
1
    One or more unapproved mock usages detected, or one or more files were
    unreadable; output lists each violation.

Allowlist mechanism
-------------------
A line is *approved* if it contains ``# integration-mock-allowed:`` followed
by at least one non-whitespace character as the justification.

Examples::

    from unittest.mock import patch  # integration-mock-allowed: fault injection
    with patch("shutil.rmtree", ...):  # integration-mock-allowed: ENOSPC fault injection

Rules
-----
- The allowlist suppresses the violation for ONE LINE only (not file-level).
- The justification after the colon must be non-empty (not just whitespace).
- Aliased imports are detected: ``from unittest.mock import patch as _p``
  is flagged unless the import line carries the allowlist comment.
- Pure comment lines (``# ...``) are NOT scanned — only code lines.
- Unreadable files produce a violation entry and cause exit code 1 (fail-closed).

Wired into
----------
- ``scripts/ci-local.sh`` (``integration-mock-gate`` gate)
- ``.pre-commit-config.yaml`` (``integration-mock`` hook)
- ``.github/workflows/ci.yml`` (``integration-test`` job step)

CONSTITUTION Priority 0: Security — prevents mock contamination in
integration tests which undermines test efficacy.
Task: T50.5 — CI gate: mock-free integration enforcement
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Patterns that indicate unittest.mock usage in code lines.
_MOCK_PATTERNS: tuple[str, ...] = (
    "from unittest.mock import",
    "import unittest.mock",
    "unittest.mock.",
    "MagicMock",
    "AsyncMock",
    "patch(",
    "Mock(",
)

#: A valid allowlist comment: ``# integration-mock-allowed:`` followed by >=1
#: non-whitespace character. Empty or whitespace-only justifications are rejected.
_ALLOWLIST_RE: re.Pattern[str] = re.compile(r"#\s*integration-mock-allowed:\s*\S+")

#: Default scan directory relative to repository root.
_DEFAULT_SCAN_DIR = "tests/integration"


def _is_mock_line(line: str) -> bool:
    """Return True if the line is code (not a pure comment) with a mock pattern.

    Pure comment lines (stripped content starts with ``#``) are excluded.
    Lines that appear to be docstring prose (no Python syntax operators like
    ``=``, ``(``, ``.``, or ``import``) are also excluded to avoid false positives
    from module docstrings that reference mock names educationally.

    Args:
        line: A single source line (without trailing newline).

    Returns:
        True if the line is a code line containing a ``_MOCK_PATTERNS`` substring.
    """
    stripped = line.strip()
    # Skip pure comment lines
    if stripped.startswith("#"):
        return False
    # Skip bare prose lines (docstring content without Python syntax)
    # These are lines that only contain words/punctuation but no code operators.
    # Real mock usage always involves import, (, =, or a method call with .
    if not any(c in stripped for c in ("=", "(", "import", ".")):
        return False
    return any(pattern in line for pattern in _MOCK_PATTERNS)


def _is_approved(line: str) -> bool:
    """Return True if the line carries a valid allowlist comment.

    A valid allowlist comment is ``# integration-mock-allowed:`` followed
    by at least one non-whitespace character.

    Args:
        line: A single source line (without trailing newline).

    Returns:
        True if the line has a non-empty ``integration-mock-allowed`` comment.
    """
    return bool(_ALLOWLIST_RE.search(line))


def scan_file(path: Path) -> list[tuple[int, str]]:
    """Scan a single Python file for unapproved mock lines.

    Fails closed: if the file cannot be read (``OSError``), a violation entry
    is returned so the gate exits with code 1.  An unreadable file is treated
    as a potential tampering or configuration error and must not silently pass.

    Args:
        path: Absolute path to the ``.py`` file to scan.

    Returns:
        List of (line_number, line_content) tuples for each unapproved line.
        Empty list if all mock usages are approved or there are none.
        A single ``(0, "UNREADABLE: <error>")`` entry if the file cannot be read.
    """
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        return [(0, f"UNREADABLE: {exc}")]

    violations: list[tuple[int, str]] = []
    for lineno, line in enumerate(lines, start=1):
        if _is_mock_line(line) and not _is_approved(line):
            violations.append((lineno, line.rstrip()))

    return violations


def scan_directory(directory: Path) -> dict[Path, list[tuple[int, str]]]:
    """Scan all test_*.py files in the given directory for unapproved mocks.

    Scans recursively — subdirectories under ``directory`` are included.

    Args:
        directory: Root directory to scan (recursive).

    Returns:
        Mapping of file path to list of (lineno, line) violation tuples.
        Only files with violations appear in the mapping.
    """
    results: dict[Path, list[tuple[int, str]]] = {}
    for path in sorted(directory.rglob("test_*.py")):
        violations = scan_file(path)
        if violations:
            results[path] = violations
    return results


def main(argv: list[str] | None = None) -> int:
    """Run the integration mock gate.

    Args:
        argv: Command-line arguments. If ``None``, uses ``sys.argv[1:]``.

    Returns:
        Exit code: 0 for clean, 1 for violations found or unreadable files.
    """
    args = argv if argv is not None else sys.argv[1:]

    if args:
        scan_dir = Path(args[0])
    else:
        # Default: tests/integration/ relative to repo root
        repo_root = Path(__file__).resolve().parent.parent
        scan_dir = repo_root / _DEFAULT_SCAN_DIR

    if not scan_dir.exists():
        print(
            f"ERROR: Scan directory does not exist: {scan_dir}",
            file=sys.stderr,
        )
        return 1

    if not scan_dir.is_dir():
        print(
            f"ERROR: Scan path is not a directory: {scan_dir}",
            file=sys.stderr,
        )
        return 1

    violations = scan_directory(scan_dir)

    if not violations:
        print(
            f"integration-mock-gate: PASS — no unapproved mock usage in {scan_dir}",
        )
        return 0

    # Report violations
    total = sum(len(v) for v in violations.values())
    print(
        f"integration-mock-gate: FAIL — {total} unapproved mock line(s) "
        f"in {len(violations)} file(s) under {scan_dir}",
        file=sys.stderr,
    )
    print(file=sys.stderr)
    print(
        "To suppress a violation, add a line comment with non-empty justification:",
        file=sys.stderr,
    )
    print(
        "  # integration-mock-allowed: <reason why this mock is necessary>",
        file=sys.stderr,
    )
    print(file=sys.stderr)

    for filepath, file_violations in violations.items():
        rel = (
            filepath.relative_to(scan_dir.parent.parent)
            if scan_dir.parent.parent in filepath.parents
            else filepath
        )
        print(f"  {rel}:", file=sys.stderr)
        for lineno, line in file_violations:
            print(f"    line {lineno}: {line!r}", file=sys.stderr)

    return 1


if __name__ == "__main__":
    sys.exit(main())
