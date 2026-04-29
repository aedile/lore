#!/usr/bin/env python3
"""Assertion density enforcement script — T36.3 (extended T51.1).

Parses test files matching the ``test_*.py`` pattern using the ``ast`` module
and counts ``assert`` statements per function whose name starts with ``test_``.

``pytest.raises`` context managers are counted as 1 assertion each.

Exit codes
----------
- 0: No violations found (all test functions have >= 2 assertions, or no
     test files were provided, or all provided files are empty).
- 1: At least one violation found, OR a file could not be parsed.

In ``--json`` mode the exit code is determined by the ``--global-threshold``
and ``--per-file-threshold`` flags instead of the per-function floor.

Violation format (non-JSON mode)
---------------------------------
::

    <file>:<line>:<function_name> (N assertion(s))

Parametrized tests
------------------
Assertions in the function body are **always** counted, including functions
decorated with ``@pytest.mark.parametrize``.  The old exemption has been
removed because the body count is meaningful for reporting purposes.

Weak-assertion warnings
-----------------------
When ``--json`` is used, the tool emits a WARNING to stderr for any test
function whose assertions consist **entirely** of weak patterns:

- ``assert x is not None``
- ``assert isinstance(x, T)``
- ``assert hasattr(obj, attr)``
- ``assert len(x) > 0``
- ``assert bool(x)``

These warnings are informational — they do not affect the exit code.

Grandfathered violations
------------------------
When ``--baseline <file>`` is passed, functions listed in the baseline file
are not flagged as violations.  This allows existing low-density tests to be
grandfathered while requiring new tests to comply.

The global average in JSON mode is computed from **non-grandfathered**
functions only, so the threshold reflects current test quality rather than
being diluted by the legacy baseline.

JSON mode
---------
``--json`` causes the script to write a JSON report to stdout::

    {
        "global_avg": 2.31,
        "passed": false,
        "global_threshold": 3.0,
        "per_file_threshold": 2.0,
        "files": [
            {
                "path": "tests/unit/test_foo.py",
                "avg": 1.5,
                "below_per_file_threshold": true,
                "functions": [
                    {"name": "test_a", "line": 10, "count": 3, "grandfathered": false},
                    {"name": "test_b", "line": 25, "count": 0, "grandfathered": true}
                ]
            }
        ]
    }

Security note
-------------
This script operates exclusively on files passed as arguments.  It performs
no network access and writes no output files.

Usage::

    python scripts/assert_density_check.py [file1.py file2.py ...] \\
        [--baseline baseline.txt] \\
        [--json] \\
        [--global-threshold 3.0] \\
        [--per-file-threshold 2.0]

Task: T36.3 — Assertion density enforcement script
      T51.1 — Extended: JSON output, global/per-file thresholds, pytest.raises
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Safety: defensive recursion limit for very deep ASTs
# ---------------------------------------------------------------------------

sys.setrecursionlimit(5000)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Minimum number of assert statements per non-grandfathered test function
#: in non-JSON (legacy) mode.
_MIN_ASSERT_COUNT: int = 2

#: Default global average threshold when --json mode is active.
_DEFAULT_GLOBAL_THRESHOLD: float = 0.0  # 0 = no global gate in legacy mode

#: Default per-file threshold when --json mode is active.
_DEFAULT_PER_FILE_THRESHOLD: float = 0.0  # 0 = no per-file gate in legacy mode

#: Strings that identify a parametrize decorator (kept for reference, no longer
#: used to exempt tests from counting — body assertions are always counted).
_PARAMETRIZE_MARKERS: frozenset[str] = frozenset(
    ["parametrize", "mark.parametrize", "pytest.mark.parametrize"]
)

# ---------------------------------------------------------------------------
# AST helpers
# ---------------------------------------------------------------------------


def _count_asserts(func_node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    """Count assert statements and pytest.raises blocks in the function body.

    Counts only assertions that belong directly to this function scope —
    nested function and class definitions are excluded (their asserts are
    in a separate scope and must not inflate the outer function's count).

    Uses a custom recursive traversal rather than ``ast.walk()`` because
    ``ast.walk()`` does not support pruning: a ``continue`` statement on a
    ``FunctionDef`` node prevents re-visiting that node but does NOT prevent
    ``ast.walk()`` from enqueuing and visiting all of its children.

    Additionally counts each ``with pytest.raises(...)`` context manager as
    1 assertion, regardless of whether the body contains explicit asserts.

    Args:
        func_node: The function definition AST node.

    Returns:
        Number of effective assertions (asserts + pytest.raises blocks).
    """
    count = 0

    def _visit(node: ast.AST, is_root: bool) -> None:
        """Recursively visit AST nodes, skipping nested scopes.

        Args:
            node: The AST node to visit.
            is_root: True only for the top-level function node itself
                (prevents double-counting the root).
        """
        nonlocal count
        if not is_root and isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            # Nested scope — do not descend into it
            return
        if isinstance(node, ast.Assert):
            count += 1
        elif isinstance(node, ast.With):
            for item in node.items:
                if _is_pytest_raises_call(item.context_expr):
                    count += 1
        for child in ast.iter_child_nodes(node):
            _visit(child, is_root=False)

    _visit(func_node, is_root=True)
    return count


def _is_pytest_raises_call(node: ast.expr) -> bool:
    """Return True if the AST node is a ``pytest.raises(...)`` call.

    Matches both ``pytest.raises(Exc)`` and ``raises(Exc)`` forms.

    Args:
        node: An AST expression node (the context_expr of a with-item).

    Returns:
        True if the expression is a pytest.raises call.
    """
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    # pytest.raises(...)
    if isinstance(func, ast.Attribute) and func.attr == "raises":
        if isinstance(func.value, ast.Name) and func.value.id == "pytest":
            return True
    # raises(...)  — when from pytest import raises
    if isinstance(func, ast.Name) and func.id == "raises":
        return True
    return False


def _is_weak_assertion(assert_node: ast.Assert) -> bool:
    """Return True if an assertion is 'weak' (existence-only / padding).

    Weak patterns:
    - ``assert x is not None``
    - ``assert isinstance(x, T)``
    - ``assert hasattr(obj, attr)``
    - ``assert len(x) > 0``
    - ``assert bool(x)``

    Args:
        assert_node: An ast.Assert node.

    Returns:
        True if the assertion matches a weak pattern.
    """
    test = assert_node.test

    # assert x is not None
    if (
        isinstance(test, ast.Compare)
        and len(test.ops) == 1
        and isinstance(test.ops[0], ast.IsNot)
        and len(test.comparators) == 1
        and isinstance(test.comparators[0], ast.Constant)
        and test.comparators[0].value is None
    ):
        return True

    # assert isinstance(x, T)
    if (
        isinstance(test, ast.Call)
        and isinstance(test.func, ast.Name)
        and test.func.id == "isinstance"
    ):
        return True

    # assert hasattr(obj, attr)
    if isinstance(test, ast.Call) and isinstance(test.func, ast.Name) and test.func.id == "hasattr":
        return True

    # assert bool(x)
    if isinstance(test, ast.Call) and isinstance(test.func, ast.Name) and test.func.id == "bool":
        return True

    # assert len(x) > 0
    if (
        isinstance(test, ast.Compare)
        and isinstance(test.left, ast.Call)
        and isinstance(test.left.func, ast.Name)
        and test.left.func.id == "len"
        and len(test.ops) == 1
        and isinstance(test.ops[0], ast.Gt)
        and len(test.comparators) == 1
        and isinstance(test.comparators[0], ast.Constant)
        and test.comparators[0].value == 0
    ):
        return True

    return False


def _has_only_weak_assertions(func_node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Return True if the function has at least one assertion and ALL are weak.

    A function with no assertions is not considered weak (it has its own
    problem — zero assertions). A function with at least one strong assertion
    is not weak.

    Args:
        func_node: The function definition AST node.

    Returns:
        True if all assertions in the function are weak.
    """
    assert_nodes = [
        node
        for node in ast.walk(func_node)
        if isinstance(node, ast.Assert)
        and not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    ]
    if not assert_nodes:
        return False
    return all(_is_weak_assertion(a) for a in assert_nodes)


# ---------------------------------------------------------------------------
# File analysis
# ---------------------------------------------------------------------------


class _FunctionRecord:
    """Record for a single test function's assertion count.

    Attributes:
        name: The function name.
        line: The line number of the function definition.
        count: The number of effective assertions.
        weak_only: True if all assertions are weak.
        grandfathered: True if this function is in the baseline (exempt from
            per-function floor checks and excluded from the global average).
    """

    __slots__ = ("count", "grandfathered", "line", "name", "weak_only")

    def __init__(
        self, name: str, line: int, count: int, weak_only: bool, grandfathered: bool
    ) -> None:
        """Initialise a function record.

        Args:
            name: Function name.
            line: Line number.
            count: Assertion count.
            weak_only: Whether all assertions are weak.
            grandfathered: Whether this function is exempt via baseline.
        """
        self.name = name
        self.line = line
        self.count = count
        self.weak_only = weak_only
        self.grandfathered = grandfathered


def _analyse_file(
    file_path: Path,
    baseline: frozenset[str],
) -> tuple[list[_FunctionRecord], list[str], bool]:
    """Analyse a single test file for assertion density.

    Args:
        file_path: Path to the Python test file.
        baseline: Set of ``file:line:function_name`` strings that are
            grandfathered (exempt from the per-function floor check and
            excluded from the global average calculation).

    Returns:
        A tuple of (records, violation_lines, had_error) where:
        - ``records`` is a list of _FunctionRecord for each test_* function.
        - ``violation_lines`` is a list of formatted violation strings.
        - ``had_error`` is True if the file could not be parsed.
    """
    records: list[_FunctionRecord] = []
    violations: list[str] = []

    try:
        source = file_path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"ERROR: Cannot read {file_path}: {exc}", flush=True)
        return [], [], True

    if not source.strip():
        # Empty file — no functions, no violations
        return [], [], False

    try:
        tree = ast.parse(source, filename=str(file_path))
    except SyntaxError as exc:
        print(f"ERROR: Cannot parse {file_path}: {exc}", flush=True)
        return [], [], True

    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        if not node.name.startswith("test_"):
            continue

        assert_count = _count_asserts(node)
        weak_only = _has_only_weak_assertions(node)
        key = f"{file_path}:{node.lineno}:{node.name}"
        is_grandfathered = key in baseline
        records.append(
            _FunctionRecord(node.name, node.lineno, assert_count, weak_only, is_grandfathered)
        )

        if assert_count < _MIN_ASSERT_COUNT and not is_grandfathered:
            violation_line = f"{key} ({assert_count} assertion(s))"
            violations.append(violation_line)

    return records, violations, False


# ---------------------------------------------------------------------------
# Baseline loading
# ---------------------------------------------------------------------------


def _load_baseline(baseline_path: Path) -> frozenset[str]:
    """Load grandfathered function keys from a baseline file.

    Each line in the baseline file should be in the format
    ``file:line:function_name`` (matching violation output format).

    Args:
        baseline_path: Path to the baseline file.

    Returns:
        Frozenset of baseline keys (stripped, non-comment lines).
        Returns an empty frozenset if the file does not exist or cannot
        be read (e.g., due to a race condition or permission error).
    """
    try:
        lines = baseline_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return frozenset()
    return frozenset(
        line.strip() for line in lines if line.strip() and not line.strip().startswith("#")
    )


# ---------------------------------------------------------------------------
# JSON report builder
# ---------------------------------------------------------------------------


def _build_json_report(
    file_paths: list[Path],
    all_records: dict[Path, list[_FunctionRecord]],
    global_threshold: float,
    per_file_threshold: float,
) -> tuple[dict[str, object], bool]:
    """Build the JSON report and determine pass/fail status.

    The global average is computed from **non-grandfathered** functions only.
    Grandfathered (baselined) functions are excluded so that the threshold
    reflects current test quality rather than being diluted by legacy entries.

    Per-file averages also exclude grandfathered functions for consistency.

    Args:
        file_paths: Ordered list of file paths that were analysed.
        all_records: Mapping from file path to list of function records.
        global_threshold: Required global average (0 = no gate).
        per_file_threshold: Required per-file average (0 = no gate).

    Returns:
        Tuple of (report_dict, passed) where passed is True if all thresholds
        are met (or no thresholds are set).
    """
    files_data: list[dict[str, object]] = []
    total_count = 0
    total_funcs = 0

    for fp in file_paths:
        records = all_records.get(fp, [])
        # Exclude grandfathered functions from threshold calculations
        active_records = [r for r in records if not r.grandfathered]
        func_count = len(active_records)
        assert_sum = sum(r.count for r in active_records)
        if func_count > 0:
            file_avg = assert_sum / func_count
        else:
            file_avg = 0.0

        total_count += assert_sum
        total_funcs += func_count

        below = per_file_threshold > 0 and func_count > 0 and file_avg < per_file_threshold
        files_data.append(
            {
                "path": str(fp),
                "avg": float(file_avg),
                "below_per_file_threshold": bool(below),
                "functions": [
                    {
                        "name": r.name,
                        "line": r.line,
                        "count": r.count,
                        "grandfathered": r.grandfathered,
                    }
                    for r in records
                ],
            }
        )

    global_avg = total_count / total_funcs if total_funcs > 0 else 0.0
    global_fail = global_threshold > 0 and total_funcs > 0 and global_avg < global_threshold
    per_file_fail = any(entry["below_per_file_threshold"] for entry in files_data)
    passed = not global_fail and not per_file_fail

    report: dict[str, object] = {
        "global_avg": float(global_avg),
        "passed": bool(passed),
        "global_threshold": float(global_threshold),
        "per_file_threshold": float(per_file_threshold),
        "files": files_data,
    }
    return report, passed


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> int:
    """Parse arguments and run assertion density check.

    Returns:
        Exit code: 0 (no violations / thresholds met), 1 (violations or errors).
    """
    args = sys.argv[1:]
    baseline: frozenset[str] = frozenset()
    file_args: list[str] = []
    json_mode: bool = False
    global_threshold: float = 0.0
    per_file_threshold: float = 0.0

    i = 0
    while i < len(args):
        if args[i] == "--baseline" and i + 1 < len(args):
            baseline = _load_baseline(Path(args[i + 1]))
            i += 2
        elif args[i] == "--json":
            json_mode = True
            i += 1
        elif args[i] == "--global-threshold" and i + 1 < len(args):
            global_threshold = float(args[i + 1])
            i += 2
        elif args[i] == "--per-file-threshold" and i + 1 < len(args):
            per_file_threshold = float(args[i + 1])
            i += 2
        else:
            file_args.append(args[i])
            i += 1

    if not file_args:
        # No files to check — exit 0
        if json_mode:
            report: dict[str, object] = {
                "global_avg": 0.0,
                "passed": True,
                "global_threshold": global_threshold,
                "per_file_threshold": per_file_threshold,
                "files": [],
            }
            print(json.dumps(report))
        return 0

    all_records: dict[Path, list[_FunctionRecord]] = {}
    all_violations: list[str] = []
    had_any_error = False
    file_paths: list[Path] = []

    for file_arg in file_args:
        file_path = Path(file_arg)
        file_paths.append(file_path)
        records, violations, had_error = _analyse_file(file_path, baseline)
        all_records[file_path] = records
        all_violations.extend(violations)
        if had_error:
            had_any_error = True

    if json_mode:
        if had_any_error:
            # In JSON mode with parse errors, emit minimal error report
            # Error messages already printed to stdout by _analyse_file
            error_report: dict[str, object] = {
                "global_avg": 0.0,
                "passed": False,
                "global_threshold": global_threshold,
                "per_file_threshold": per_file_threshold,
                "files": [],
                "error": "One or more files could not be parsed",
            }
            print(json.dumps(error_report))
            return 1

        # Emit weak-assertion warnings to stderr (informational only)
        for fp, records in all_records.items():
            for record in records:
                if record.weak_only and not record.grandfathered:
                    print(
                        f"WARNING: {fp}:{record.line}:{record.name} "
                        "has only weak (existence-only) assertions",
                        file=sys.stderr,
                        flush=True,
                    )

        report_dict, passed = _build_json_report(
            file_paths, all_records, global_threshold, per_file_threshold
        )
        print(json.dumps(report_dict))
        return 0 if passed else 1

    # Legacy (non-JSON) mode: per-function floor check
    if all_violations:
        print("Assertion density violations (< 2 assertions per test function):")
        for line in all_violations:
            print(f"  {line}")

    if all_violations or had_any_error:
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
