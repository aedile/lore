#!/usr/bin/env python3
"""Rebuild the assertion density baseline by removing entries for deepened tests.

For each entry in the baseline file (file:line:funcname), check if:
1. The function at that line still has < 2 assertions (keep it)
2. The function now has >= 2 assertions (remove it - it's been deepened)
3. The line doesn't match any function (stale entry - remove it)

Also handles the case where the function moved to a different line by searching
for the funcname in the file and checking its current assertion count.

Usage:
    python scripts/rebuild_baseline.py
"""

from __future__ import annotations

import ast
from pathlib import Path


def count_outer_assertions(func_node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    """Count outer-scope assertions in a function, excluding nested function bodies."""
    count = 0

    def _visit(node: ast.AST, is_root: bool) -> None:
        nonlocal count
        if not is_root and isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            return
        if isinstance(node, ast.Assert):
            count += 1
        elif isinstance(node, ast.With):
            for item in node.items:
                expr = item.context_expr
                if _is_pytest_raises_call(expr):
                    count += 1
        for child in ast.iter_child_nodes(node):
            _visit(child, is_root=False)

    _visit(func_node, is_root=True)
    return count


def _is_pytest_raises_call(node: ast.expr) -> bool:
    """Return True if the node is a pytest.raises(...) call."""
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    # pytest.raises(...)
    if isinstance(func, ast.Attribute) and func.attr == "raises":
        return True
    # raises(...) (imported directly)
    if isinstance(func, ast.Name) and func.id == "raises":
        return True
    return False


def get_function_assertion_counts(filepath: Path) -> dict[str, tuple[int, int]]:
    """Return a dict of funcname -> (lineno, assertion_count) for all test functions."""
    try:
        source = filepath.read_text()
        tree = ast.parse(source)
    except (SyntaxError, OSError):
        return {}

    result: dict[str, tuple[int, int]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            if node.name.startswith("test_"):
                count = count_outer_assertions(node)
                result[node.name] = (node.lineno, count)

    return result


def main() -> None:
    """Rebuild the baseline file."""
    baseline_path = Path("scripts/assert_density_baseline.txt")
    ratchet_max_path = Path("scripts/assert_density_baseline_max.txt")

    original_lines = baseline_path.read_text().splitlines()
    kept_lines = []
    removed_count = 0
    stale_count = 0

    # Cache for file analysis
    file_cache: dict[str, dict[str, tuple[int, int]]] = {}

    for line in original_lines:
        stripped = line.strip()
        # Keep comments and blank lines
        if not stripped or stripped.startswith("#"):
            kept_lines.append(line)
            continue

        # Parse entry: file:line:funcname
        parts = stripped.split(":")
        if len(parts) != 3:
            kept_lines.append(line)
            continue

        filepath_str, lineno_str, funcname = parts
        try:
            baseline_line = int(lineno_str)
        except ValueError:
            kept_lines.append(line)
            continue

        filepath = Path(filepath_str)
        if not filepath.exists():
            # File doesn't exist — stale, remove
            print(f"  REMOVE (file gone): {stripped}")
            removed_count += 1
            stale_count += 1
            continue

        # Analyze the file
        cache_key = str(filepath)
        if cache_key not in file_cache:
            file_cache[cache_key] = get_function_assertion_counts(filepath)

        func_counts = file_cache[cache_key]

        if funcname not in func_counts:
            # Function no longer exists — stale, remove
            print(f"  REMOVE (func gone): {stripped}")
            removed_count += 1
            stale_count += 1
            continue

        actual_line, assertion_count = func_counts[funcname]

        if assertion_count >= 2:
            # Function now has 2+ assertions — deepened, remove from baseline
            print(f"  REMOVE (deepened, {assertion_count} asserts): {stripped}")
            removed_count += 1
        else:
            # Function still has < 2 assertions — keep in baseline
            # Update line number if it changed
            if actual_line != baseline_line:
                new_entry = f"{filepath_str}:{actual_line}:{funcname}"
                kept_lines.append(new_entry)
                print(f"  UPDATE line: {stripped} -> :{actual_line}:")
            else:
                kept_lines.append(line)

    # Remove consecutive blank lines
    cleaned = []
    prev_blank = False
    for line in kept_lines:
        is_blank = not line.strip()
        if is_blank and prev_blank:
            continue
        cleaned.append(line)
        prev_blank = is_blank

    new_content = "\n".join(cleaned) + "\n"
    baseline_path.write_text(new_content)

    # Count non-comment entries in new baseline
    new_count = sum(1 for line in cleaned if line.strip() and not line.strip().startswith("#"))

    # Update ratchet max
    ratchet_max_path.write_text(f"{new_count}\n")

    orig_count = sum(1 for ln in original_lines if ln.strip() and not ln.strip().startswith("#"))
    print(f"\nOriginal baseline entries: {orig_count}")
    print(f"Removed: {removed_count} (stale: {stale_count})")
    print(f"New baseline entries: {new_count}")
    print(f"Updated ratchet max: {new_count}")


if __name__ == "__main__":
    main()
