#!/usr/bin/env python3
"""Fix companion module sentinel tests by adding st_size assertion.

These tests look like:
    companion = Path(__file__).parent / "test_foo_attack.py"
    assert companion.exists(), (
        f"Companion attack module {companion.name!r} must exist in {companion.parent}"
    )

We need to add AFTER the closing paren:
    assert companion.stat().st_size > 0, (
        f"Companion module {companion.name!r} must be non-empty"
    )

Strategy: find functions where test name is test_attack_coverage_via_companion_module,
find the companion.exists() assert, find its end (closing paren), insert after.
"""

from __future__ import annotations

import ast
from pathlib import Path


def find_companion_test_files() -> list[Path]:
    """Find all test files containing test_attack_coverage_via_companion_module."""
    test_dirs = [
        Path("tests/unit"),
        Path("tests/unit/bootstrapper"),
    ]
    result = []
    for d in test_dirs:
        if d.exists():
            for f in sorted(d.glob("test_*.py")):
                result.append(f)
    return result


def fix_file(path: Path) -> int:
    """Fix companion module tests in a file. Returns number of fixes made."""
    try:
        source = path.read_text()
        tree = ast.parse(source)
    except SyntaxError as e:
        print(f"  PARSE ERROR {path}: {e}")
        return 0

    lines = source.splitlines()

    # Find all test_attack_coverage_via_companion_module functions
    companion_funcs = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            if node.name == "test_attack_coverage_via_companion_module":
                companion_funcs.append(node)

    if not companion_funcs:
        return 0

    fixes = []

    for func in companion_funcs:
        # Check if it already has st_size assertion
        func_lines = "\n".join(lines[func.lineno - 1 : func.end_lineno])
        if "st_size" in func_lines:
            continue  # Already fixed

        # Find the assert companion.exists() line
        exists_line_idx = None
        for i in range(func.lineno - 1, func.end_lineno):
            if i < len(lines) and "companion.exists()" in lines[i]:
                exists_line_idx = i
                break

        if exists_line_idx is None:
            print(f"  SKIP (no exists() assertion): {path}:{func.lineno}:{func.name}")
            continue

        # Find the end of the assert statement (closing paren or end of line)
        # If line has an unclosed paren, walk forward until depth returns to 0
        depth = 0
        end_idx = exists_line_idx
        for i in range(exists_line_idx, min(func.end_lineno, len(lines))):
            for ch in lines[i]:
                if ch == "(":
                    depth += 1
                elif ch == ")":
                    depth -= 1
            if i > exists_line_idx and depth <= 0:
                end_idx = i
                break
            elif i == exists_line_idx and depth == 0:
                end_idx = i
                break

        # Get indentation
        indent = len(lines[exists_line_idx]) - len(lines[exists_line_idx].lstrip())
        indent_str = " " * indent

        # Build the new assertion
        new_lines = [
            f"{indent_str}assert companion.stat().st_size > 0, (",
            f'{indent_str}    f"Companion module {{companion.name!r}} must be non-empty"',
            f"{indent_str})",
        ]

        fixes.append((end_idx + 1, new_lines))
        print(f"  Will fix: {path}:{func.lineno}:{func.name} (insert after line {end_idx + 1})")

    if not fixes:
        return 0

    # Apply fixes in reverse order to preserve line numbers
    for insert_at, new_lines in sorted(fixes, reverse=True):
        lines.insert(insert_at, "")  # blank line separator
        for _i, nl in enumerate(reversed(new_lines)):
            lines.insert(insert_at, nl)

    # Verify syntax
    new_source = "\n".join(lines) + "\n"
    try:
        ast.parse(new_source)
    except SyntaxError as e:
        print(f"  SYNTAX ERROR after fix {path}: {e}")
        return 0

    path.write_text(new_source)
    return len(fixes)


def main() -> None:
    """Fix all companion module tests."""
    # Files with companion violations from the violations list
    companion_files = [
        Path("tests/unit/test_adapter_extractor.py"),
        Path("tests/unit/test_adapter_version.py"),
        Path("tests/unit/test_air_gap.py"),
        Path("tests/unit/test_ast_analyzer.py"),
        Path("tests/unit/test_compile_api.py"),
        Path("tests/unit/test_compile_job_store.py"),
        Path("tests/unit/test_compile_lifecycle.py"),
        Path("tests/unit/test_compiler_routes.py"),
        Path("tests/unit/test_consistency_check.py"),
        Path("tests/unit/test_consistency_gate.py"),
        Path("tests/unit/test_corpus_converter.py"),
        Path("tests/unit/test_database.py"),
        Path("tests/unit/test_demo.py"),
        Path("tests/unit/test_doc_audit.py"),
        Path("tests/unit/test_docker_infrastructure.py"),
        Path("tests/unit/test_dockerfile.py"),
        Path("tests/unit/test_fallback_cascade.py"),
        Path("tests/unit/test_health.py"),
        Path("tests/unit/test_hmac_signing.py"),
        Path("tests/unit/test_key_manager.py"),
        Path("tests/unit/test_logging_config.py"),
        Path("tests/unit/test_mlx_runtime.py"),
        Path("tests/unit/test_mlx_serving_wiring.py"),
        Path("tests/unit/test_mutation_security.py"),
        Path("tests/unit/test_ollama_runtime.py"),
        Path("tests/unit/test_orchestrator.py"),
        Path("tests/unit/test_pipeline_orchestrator.py"),
        Path("tests/unit/test_pydantic_gate.py"),
        Path("tests/unit/test_resynth_queue.py"),
        Path("tests/unit/test_router_api.py"),
        Path("tests/unit/test_schema_fingerprinter.py"),
        Path("tests/unit/test_schema_validator.py"),
        Path("tests/unit/test_serving_backend.py"),
        Path("tests/unit/test_simulation_controller.py"),
        Path("tests/unit/test_supply_chain.py"),
        Path("tests/unit/test_teacher_runtime.py"),
        Path("tests/unit/test_tool_call_gate.py"),
        Path("tests/unit/test_tool_registry.py"),
        Path("tests/unit/test_vram_preflight.py"),
        Path("tests/unit/bootstrapper/test_di_wiring.py"),
    ]

    total = 0
    for path in companion_files:
        if not path.exists():
            print(f"NOT FOUND: {path}")
            continue
        n = fix_file(path)
        total += n

    print(f"\nTotal fixes applied: {total}")


if __name__ == "__main__":
    main()
