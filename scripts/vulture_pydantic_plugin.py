"""Vulture whitelist generator for Pydantic, FastAPI, Enum, and pytest patterns.

This plugin scans Python source files and generates a vulture-compatible
whitelist of names that vulture's static analysis cannot detect as "used":

1. Pydantic ``BaseModel`` / ``BaseSettings`` field names — accessed via
   ``model_validate()`` and attribute access across module boundaries.
2. ``@field_validator`` / ``@model_validator`` decorated methods — called by
   Pydantic's metaclass, not via direct Python call syntax.
3. ``model_config`` attributes on Pydantic model classes.
4. FastAPI ``@router.get/post/put/delete/patch/head/options`` decorated
   route handler functions — registered by the ASGI framework.
5. ``Enum`` subclass member names — accessed via ``Member.VALUE`` or
   cross-module ``EnumClass.MEMBER`` lookups.
6. ``pytest.fixture`` decorated functions in conftest files — consumed by
   pytest's fixture injection mechanism, not direct call syntax.
7. Starlette ``BaseHTTPMiddleware.dispatch`` override methods — called by
   the ASGI request processing chain.

Usage (generate the static whitelist file):
    python3 scripts/vulture_pydantic_plugin.py > .vulture_generated.py

Then run vulture with both whitelist files:
    poetry run vulture src/ .vulture_whitelist.py .vulture_generated.py --min-confidence 60

Or with the Makefile:
    make lint  # automatically regenerates .vulture_generated.py

The plugin is PATTERN-BASED: it detects class hierarchies and decorator
patterns from the AST. It does NOT import any source module, ensuring
no side effects and no risk of circular imports.

Output format:
    The generated file contains bare Python identifier lines, one per name,
    which vulture's AST scanner recognises as "used" statements.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# AST analysis helpers
# ---------------------------------------------------------------------------


def _is_subclass_of(node: ast.ClassDef, bases: frozenset[str]) -> bool:
    """Return True if the class definition inherits from any name in ``bases``.

    Args:
        node: The class definition AST node.
        bases: Frozenset of base class name strings to check against.

    Returns:
        True if any of the node's base class names is in ``bases``.
    """
    for base in node.bases:
        name = _extract_name(base)
        if name and name in bases:
            return True
    return False


def _extract_name(node: ast.expr) -> str | None:
    """Extract a simple name string from an AST name or attribute node.

    Args:
        node: An AST expression that may be a Name or Attribute node.

    Returns:
        The name string, or None if the node is not a recognizable name.
    """
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _has_decorator(func: ast.FunctionDef | ast.AsyncFunctionDef, names: frozenset[str]) -> bool:
    """Return True if the function has any decorator matching any name in ``names``.

    Matches on the decorator's simple name (e.g., ``fixture`` from
    ``pytest.fixture``, or ``field_validator`` directly).

    Args:
        func: The function definition AST node.
        names: Frozenset of decorator name strings (simple names only) to match.

    Returns:
        True if any decorator matches.
    """
    for dec in func.decorator_list:
        name = _extract_name(dec)
        if name and name in names:
            return True
        # Handle @pytest.fixture, @router.get(...) etc.
        if isinstance(dec, ast.Call):
            func_node = dec.func
            name = _extract_name(func_node)
            if name and name in names:
                return True
    return False


def _is_router_decorator(func: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Return True if the function is decorated with a FastAPI/APIRouter HTTP method.

    Detects patterns like:
    - ``@router.get("/path")``
    - ``@app.post("/path")``
    - ``@router.delete("/path")``

    Args:
        func: The function definition AST node.

    Returns:
        True if the function appears to be an HTTP route handler.
    """
    _http_methods = frozenset({"get", "post", "put", "patch", "delete", "head", "options"})
    for dec in func.decorator_list:
        if isinstance(dec, ast.Call):
            func_node = dec.func
            if isinstance(func_node, ast.Attribute) and func_node.attr in _http_methods:
                return True
    return False


def _is_dispatch_override(
    func: ast.FunctionDef | ast.AsyncFunctionDef,
    class_bases: frozenset[str],
) -> bool:
    """Return True if this is a ``dispatch`` method inside a middleware class.

    Starlette's ``BaseHTTPMiddleware`` calls ``dispatch()`` via the ASGI chain,
    not via direct Python call syntax that vulture recognises.

    Args:
        func: The function definition AST node.
        class_bases: Frozenset of base class names for the enclosing class.

    Returns:
        True if this is a dispatch method in a middleware subclass.
    """
    _middleware_bases = frozenset({"BaseHTTPMiddleware", "HTTPMiddleware"})
    return func.name == "dispatch" and bool(class_bases & _middleware_bases)


# ---------------------------------------------------------------------------
# Per-file analysis
# ---------------------------------------------------------------------------


_PYDANTIC_BASES: frozenset[str] = frozenset({"BaseModel", "BaseSettings", "SQLModel", "AuditEntry"})
_ENUM_BASES: frozenset[str] = frozenset({"Enum", "IntEnum", "StrEnum", "Flag", "IntFlag"})
_VALIDATOR_DECORATORS: frozenset[str] = frozenset({"field_validator", "model_validator"})
_FIXTURE_DECORATORS: frozenset[str] = frozenset({"fixture"})


def scan_file(path: Path) -> list[str]:
    """Scan a single Python source file and return names to mark as used.

    Args:
        path: Path to the Python source file to analyse.

    Returns:
        List of identifier name strings that should be treated as used by vulture.
        Returns an empty list on parse error (file is silently skipped).
    """
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
    except (SyntaxError, UnicodeDecodeError):
        return []

    names: list[str] = []
    is_conftest = path.name.startswith("conftest")

    for node in ast.walk(tree):
        # --- Pydantic BaseModel / BaseSettings fields ---
        if isinstance(node, ast.ClassDef) and _is_subclass_of(node, _PYDANTIC_BASES):
            for item in node.body:
                if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                    names.append(item.target.id)
                # model_config = SettingsConfigDict(...)
                if isinstance(item, ast.Assign):
                    for target in item.targets:
                        if isinstance(target, ast.Name) and target.id == "model_config":
                            names.append("model_config")

        # --- Enum members ---
        if isinstance(node, ast.ClassDef) and _is_subclass_of(node, _ENUM_BASES):
            for item in node.body:
                if isinstance(item, ast.Assign):
                    for target in item.targets:
                        if isinstance(target, ast.Name):
                            names.append(target.id)

        # --- FastAPI route handlers & @field_validator / @model_validator ---
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            if _is_router_decorator(node):
                names.append(node.name)
            if _has_decorator(node, _VALIDATOR_DECORATORS):
                names.append(node.name)

        # --- pytest fixtures in conftest files ---
        if is_conftest and isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            if _has_decorator(node, _FIXTURE_DECORATORS):
                names.append(node.name)

        # --- BaseHTTPMiddleware.dispatch overrides ---
        if isinstance(node, ast.ClassDef):
            base_names = frozenset(n for b in node.bases if (n := _extract_name(b)) is not None)
            for item in node.body:
                if isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef):
                    if _is_dispatch_override(item, base_names):
                        names.append(item.name)

    return names


def scan_directory(directory: Path | str) -> list[str]:
    """Scan all ``.py`` files in a directory tree and collect names to mark as used.

    Only ``.py`` files are processed; other file types are silently ignored.
    Files with syntax errors are silently skipped (not a crash condition).

    Args:
        directory: Root directory to scan recursively.

    Returns:
        Sorted, deduplicated list of identifier name strings.
    """
    root = Path(directory)
    all_names: list[str] = []
    if not root.exists():
        return all_names
    for py_file in root.rglob("*.py"):
        all_names.extend(scan_file(py_file))
    return sorted(set(all_names))


def generate_whitelist(directories: list[str] | None = None) -> list[str]:
    """Generate the complete set of names to whitelist from all source directories.

    Scans ``src/`` and ``tests/`` by default (relative to cwd, or resolved
    relative to this script's parent directory).

    Args:
        directories: Optional list of directory paths to scan. Defaults to
            ``["src/", "tests/"]`` resolved relative to the project root.

    Returns:
        Sorted, deduplicated list of identifier name strings.
    """
    if directories is not None:
        all_names: list[str] = []
        for d in directories:
            all_names.extend(scan_directory(Path(d)))
        return sorted(set(all_names))

    # Default: resolve relative to project root (parent of scripts/)
    project_root = Path(__file__).parent.parent
    src_dir = project_root / "src"
    tests_dir = project_root / "tests"

    all_names = []
    if src_dir.exists():
        all_names.extend(scan_directory(src_dir))
    if tests_dir.exists():
        all_names.extend(scan_directory(tests_dir))
    return sorted(set(all_names))


if __name__ == "__main__":
    # Called directly: print whitelist Python source to stdout.
    # Usage: python3 scripts/vulture_pydantic_plugin.py > .vulture_generated.py
    names = generate_whitelist()
    header = (
        "# AUTO-GENERATED by scripts/vulture_pydantic_plugin.py — DO NOT EDIT.\n"
        "# Regenerate with: python3 scripts/vulture_pydantic_plugin.py > .vulture_generated.py\n"
        "# This file marks Pydantic fields, FastAPI routes, Enum members,\n"
        "# and pytest fixtures as 'used' for vulture's static analysis.\n"
        "# ruff: noqa: F821 B018 E501\n\n"
    )
    sys.stdout.write(header)
    for name in names:
        sys.stdout.write(f"{name}\n")
    sys.exit(0)
