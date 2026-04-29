#!/usr/bin/env python3
"""Automated documentation accuracy audit script — T39.3.

Reads README.md and verifies:
1. No stale phrases ("pre-development", "not yet built", etc.) are present.
2. All ``docs/*.md`` references resolve to existing files.
3. All backtick-wrapped ``src/...`` paths resolve to existing files.

Exit codes:
    0 — All checks passed.
    1 — One or more checks failed; failures printed to stdout.

Usage::

    python scripts/doc_audit.py
    python scripts/doc_audit.py --readme README.md --docs-dir docs/ --project-root .

Performance: designed to complete in under 3 seconds on a typical README.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Stale phrases that indicate the README has not been updated to reflect
# the current implementation status.
# ---------------------------------------------------------------------------

_STALE_PHRASES: tuple[str, ...] = (
    "pre-development",
    "not yet built",
    "nothing described below",
    "no implementation exists",
)

# ---------------------------------------------------------------------------
# Regex patterns for extracting references from README text.
# ---------------------------------------------------------------------------

# Matches Markdown link targets like (docs/FILE.md) or (docs/FILE.md#anchor)
_DOCS_LINK_RE = re.compile(r"\(docs/([^)\s#]+\.md)", re.IGNORECASE)

# Matches backtick-wrapped src/ paths like `src/lore_eligibility/module/file.py`
_SRC_PATH_RE = re.compile(r"`(src/[^`]+\.py)`")


def _check_stale_phrases(content: str) -> list[str]:
    """Scan README content for known stale phrases.

    Args:
        content: Full text of the README file.

    Returns:
        List of failure messages for each stale phrase found.
    """
    content_lower = content.lower()
    failures: list[str] = []
    for phrase in _STALE_PHRASES:
        if phrase in content_lower:
            failures.append(f"STALE PHRASE: '{phrase}' found in README")
    return failures


def _check_doc_references(content: str, docs_dir: Path) -> list[str]:
    """Verify that all docs/*.md references in README exist on disk.

    Args:
        content: Full text of the README file.
        docs_dir: Absolute path to the docs/ directory.

    Returns:
        List of failure messages for each missing referenced doc.
    """
    failures: list[str] = []
    for match in _DOCS_LINK_RE.finditer(content):
        filename = match.group(1)
        target = docs_dir / filename
        if not target.exists():
            failures.append(
                f"MISSING DOC: docs/{filename} referenced in README but not found on disk"
            )
    return failures


def _check_src_references(content: str, project_root: Path) -> list[str]:
    """Verify that all backtick-wrapped src/ paths exist on disk.

    Args:
        content: Full text of the README file.
        project_root: Absolute path to the project root directory.

    Returns:
        List of failure messages for each missing source path.
    """
    failures: list[str] = []
    for match in _SRC_PATH_RE.finditer(content):
        rel_path = match.group(1)
        target = project_root / rel_path
        if not target.exists():
            failures.append(f"MISSING SRC: {rel_path} referenced in README but not found on disk")
    return failures


def run_audit(
    readme_path: Path,
    docs_dir: Path,
    project_root: Path,
) -> int:
    """Run all documentation accuracy checks and print results.

    Args:
        readme_path: Absolute path to the README file.
        docs_dir: Absolute path to the docs/ directory.
        project_root: Absolute path to the project root.

    Returns:
        Exit code: 0 if all checks pass, 1 if any check fails.
    """
    # --- Validate inputs ---
    if not readme_path.exists():
        print(f"FAIL: README not found: {readme_path}")
        return 1

    content = readme_path.read_text(encoding="utf-8")
    failures: list[str] = []

    # --- Run checks ---
    failures.extend(_check_stale_phrases(content))
    failures.extend(_check_doc_references(content, docs_dir))
    failures.extend(_check_src_references(content, project_root))

    # --- Report results ---
    if failures:
        print("doc_audit.py — FAIL")
        for failure in failures:
            print(f"  {failure}")
        return 1

    print("doc_audit.py — OK: all checks passed")
    print(f"  Checked stale phrases: {len(_STALE_PHRASES)}")
    print(f"  Checked doc references and src paths in: {readme_path.name}")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser.

    Returns:
        Configured ArgumentParser instance.
    """
    parser = argparse.ArgumentParser(
        description="Verify README.md is accurate and up-to-date.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--readme",
        type=Path,
        default=None,
        help="Path to README.md (default: <project-root>/README.md)",
    )
    parser.add_argument(
        "--docs-dir",
        type=Path,
        default=None,
        help="Path to docs/ directory (default: <project-root>/docs/)",
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=None,
        help="Project root directory (default: parent of this script's parent)",
    )
    return parser


def main() -> int:
    """Entry point for the doc audit script.

    Returns:
        Exit code: 0 on success, 1 on failure.
    """
    parser = _build_parser()
    args = parser.parse_args()

    # Resolve defaults relative to the script's location
    script_dir = Path(__file__).resolve().parent
    default_root = script_dir.parent

    project_root: Path = args.project_root.resolve() if args.project_root else default_root
    readme_path: Path = args.readme.resolve() if args.readme else project_root / "README.md"
    docs_dir: Path = args.docs_dir.resolve() if args.docs_dir else project_root / "docs"

    return run_audit(readme_path, docs_dir, project_root)


if __name__ == "__main__":
    sys.exit(main())
