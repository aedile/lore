"""Mutmut gate logic -- pure Python helpers for the mutation testing CI gate.

This module contains the testable business logic extracted from the shell-level
mutation testing gate. It is intentionally free of I/O side effects so that all
behaviors can be unit-tested without running mutmut.

The shell scripts (``scripts/ci-local.sh``, ``scripts/mutmut-gate.sh``) call
the ``main()`` entry point which orchestrates subprocess invocation,
result parsing, and audit log writing. The pure logic lives here.

Constitution Priority 4: Mutation score >= configured threshold on
security-critical modules.  Constitution Priority 1: Quality Gates are
Unbreakable -- SKIP_MUTMUT must be blocked at merge time.

Task: T30.1 -- Integrate mutmut security gate into ci-local.sh
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------


class GateStatus(str, Enum):
    """Status of a single mutmut gate evaluation."""

    PASS = "PASS"  # noqa: S105  # nosec B105
    FAIL = "FAIL"
    SKIP = "SKIP"


@dataclass
class GateResult:
    """Result of evaluating the mutmut gate for a single module.

    All fields are required to populate the ci-audit.jsonl entry.

    Attributes:
        module_name: Logical name of the module being evaluated.
        status: ``PASS``, ``FAIL``, or ``SKIP``.
        score: Mutation score as a percentage (0.0-100.0).
        threshold: Configured threshold percentage.
        killed: Number of mutants killed by tests.
        total: Total number of mutants generated.
        message: Human-readable description of the result.
    """

    module_name: str
    status: GateStatus
    score: float
    threshold: int
    killed: int
    total: int
    message: str = field(default="")

    def to_dict(self) -> dict[str, object]:
        """Serialise to a JSON-compatible dict for ci-audit.jsonl.

        Returns:
            Dictionary with all fields; ``status`` is the enum value string.
        """
        return {
            "module_name": self.module_name,
            "status": self.status.value,
            "score": round(self.score, 2),
            "threshold": self.threshold,
            "killed": self.killed,
            "total": self.total,
            "message": self.message,
        }


# ---------------------------------------------------------------------------
# SKIP_MUTMUT logic
# ---------------------------------------------------------------------------


def should_skip_mutmut(env_value: str) -> bool:
    """Return True iff SKIP_MUTMUT should be honoured.

    Uses an EXACT string match against ``"1"`` -- not a truthy or non-empty
    check -- to prevent accidental bypass via ``"true"``, ``"yes"``, ``"0"``,
    etc.

    This is the Python equivalent of the Bash expression::

        [[ "${SKIP_MUTMUT:-}" == "1" ]]

    Args:
        env_value: The value of the ``SKIP_MUTMUT`` environment variable.
            Pass an empty string ``""`` when the variable is absent (shell
            ``${SKIP_MUTMUT:-}`` semantics).

    Returns:
        ``True`` only when ``env_value`` is the exact string ``"1"``.
    """
    return env_value == "1"


# ---------------------------------------------------------------------------
# Score computation
# ---------------------------------------------------------------------------


def compute_mutation_score(*, killed: int, total: int) -> float:
    """Compute mutation score as a percentage.

    Args:
        killed: Number of mutants killed by the test suite.
        total: Total number of mutants generated (must be > 0).

    Returns:
        Score as a float percentage in [0.0, 100.0].

    Raises:
        ValueError: If ``total`` is zero or negative (vacuous pass prevention).
    """
    if total <= 0:
        raise ValueError(
            f"total mutants must be > 0 to compute a score; got total={total}. "
            "Zero total mutants indicates a scope or configuration error."
        )
    return (killed / total) * 100.0


# ---------------------------------------------------------------------------
# Gate evaluation
# ---------------------------------------------------------------------------


def evaluate_gate(
    *,
    module_name: str,
    killed: int,
    total: int,
    threshold: int,
) -> GateResult:
    """Evaluate whether the mutation score meets the configured threshold.

    Args:
        module_name: Logical name for the module being evaluated (used in
            the result message and audit log).
        killed: Number of mutants killed by tests.
        total: Total number of mutants generated.
        threshold: Minimum acceptable mutation score (integer percentage).

    Returns:
        A :class:`GateResult` with the appropriate ``status``, ``score``,
        and ``message``.  The status is:

        - ``FAIL`` when ``total == 0`` (zero-mutants guard -- scope error).
        - ``FAIL`` when ``score < threshold``.
        - ``PASS`` when ``score >= threshold``.
    """
    # Zero total mutants -- scope is wrong; vacuous pass not acceptable.
    if total == 0:
        return GateResult(
            module_name=module_name,
            status=GateStatus.FAIL,
            score=0.0,
            threshold=threshold,
            killed=0,
            total=0,
            message=(
                f"{module_name}: zero mutants generated -- "
                "scope error or mutmut configuration problem. "
                "Check paths_to_mutate and do_not_mutate in pyproject.toml."
            ),
        )

    score = compute_mutation_score(killed=killed, total=total)

    if score >= threshold:
        return GateResult(
            module_name=module_name,
            status=GateStatus.PASS,
            score=score,
            threshold=threshold,
            killed=killed,
            total=total,
            message=f"{module_name}: {score:.1f}% >= {threshold}% threshold -- PASS",
        )

    return GateResult(
        module_name=module_name,
        status=GateStatus.FAIL,
        score=score,
        threshold=threshold,
        killed=killed,
        total=total,
        message=(
            f"{module_name}: {score:.1f}% < {threshold}% threshold -- FAIL. "
            f"Killed {killed}/{total} mutants. "
            f"Run 'make mutmut' and 'poetry run mutmut results' to see survivors."
        ),
    )


# ---------------------------------------------------------------------------
# Output parsing
# ---------------------------------------------------------------------------

# Primary pattern: "N out of M mutants killed."
_PATTERN_PRIMARY = re.compile(r"(\d+)\s+out\s+of\s+(\d+)\s+mutants?\s+killed", re.IGNORECASE)

# Alternative pattern: "survived: N killed: M total: T"
_PATTERN_ALT = re.compile(r"survived:\s*(\d+)\s+killed:\s*(\d+)\s+total:\s*(\d+)", re.IGNORECASE)

# Mutmut 3.x export-cicd-stats JSON pattern (killed/survived/total keys)
_PATTERN_JSON_KILLED = re.compile(r'"killed"\s*:\s*(\d+)')
_PATTERN_JSON_TOTAL = re.compile(r'"total"\s*:\s*(\d+)')


def parse_mutmut_output(output: str) -> tuple[int, int]:
    """Extract (killed, total) from mutmut stdout or cicd-stats output.

    Supports three output formats:

    1. ``"N out of M mutants killed."`` -- standard mutmut 3.x run output.
    2. ``"survived: N killed: M total: T"`` -- alternative summary format.
    3. JSON with ``"killed"`` and ``"total"`` keys -- ``export-cicd-stats`` format.

    Args:
        output: The captured stdout from ``mutmut run`` or ``mutmut results``
            or the contents of ``mutants/mutmut-cicd-stats.json``.

    Returns:
        A ``(killed, total)`` tuple of integers.

    Raises:
        ValueError: If no recognisable summary pattern is found in ``output``.
    """
    # Try primary format first
    m = _PATTERN_PRIMARY.search(output)
    if m:
        killed = int(m.group(1))
        total = int(m.group(2))
        return killed, total

    # Try alternative format
    m = _PATTERN_ALT.search(output)
    if m:
        killed = int(m.group(2))
        total = int(m.group(3))
        return killed, total

    # Try JSON format (mutmut export-cicd-stats)
    m_killed = _PATTERN_JSON_KILLED.search(output)
    m_total = _PATTERN_JSON_TOTAL.search(output)
    if m_killed and m_total:
        return int(m_killed.group(1)), int(m_total.group(1))

    raise ValueError(
        f"No mutmut summary pattern found in output. "
        f"Expected 'N out of M mutants killed.' or JSON with killed/total keys. "
        f"Output preview: {output[:200]!r}"
    )


# ---------------------------------------------------------------------------
# Threshold reader
# ---------------------------------------------------------------------------

# Path to pyproject.toml relative to project root.
_PYPROJECT_PATH = Path(__file__).parent.parent / "pyproject.toml"

# Mapping from logical threshold key to pyproject.toml key name.
_THRESHOLD_KEYS: dict[str, str] = {
    "security": "threshold_security",
    "auth": "threshold_auth",
}


def read_threshold(key: str, pyproject_path: Path | None = None) -> int:
    """Read a mutation score threshold from ``pyproject.toml``.

    Args:
        key: Logical threshold key -- one of ``"security"`` or ``"auth"``.
        pyproject_path: Optional override path to ``pyproject.toml``.
            Defaults to the project root ``pyproject.toml``.

    Returns:
        Integer threshold value (e.g. ``60`` for 60%).

    Raises:
        ValueError: If ``key`` is not one of the recognised threshold keys.
        KeyError: If the ``[tool.mutmut]`` section or the threshold key is
            absent from ``pyproject.toml``.
    """
    if key not in _THRESHOLD_KEYS:
        raise ValueError(
            f"Unknown threshold key: {key!r}. Valid keys: {sorted(_THRESHOLD_KEYS.keys())}"
        )

    toml_key = _THRESHOLD_KEYS[key]
    path = pyproject_path or _PYPROJECT_PATH

    import tomllib

    with open(path, "rb") as f:
        data = tomllib.load(f)

    mutmut_config = data.get("tool", {}).get("mutmut", {})
    if toml_key not in mutmut_config:
        raise KeyError(
            f"Threshold key '{toml_key}' not found in [tool.mutmut] section of "
            f"{path}. Add 'threshold_{key} = N' to [tool.mutmut]."
        )

    return int(mutmut_config[toml_key])


# ---------------------------------------------------------------------------
# CLI entry point (used by shell scripts)
# ---------------------------------------------------------------------------


def main() -> int:  # noqa: DOC502
    """CLI entry point for the mutmut gate.

    Reads a JSON file produced by ``mutmut export-cicd-stats`` from a file
    path argument, evaluates the gate, and prints results.

    Returns:
        Exit code: 0 for PASS, 1 for FAIL.
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="Evaluate mutmut gate results against configured thresholds."
    )
    parser.add_argument(
        "--stats-file",
        required=True,
        help="Path to mutmut-cicd-stats.json produced by 'mutmut export-cicd-stats'",
    )
    parser.add_argument(
        "--module-name",
        required=True,
        help="Logical name of the module being evaluated (for audit log)",
    )
    parser.add_argument(
        "--threshold-key",
        required=True,
        choices=list(_THRESHOLD_KEYS.keys()),
        help="Threshold key to read from pyproject.toml [tool.mutmut]",
    )
    args = parser.parse_args()

    stats_path = Path(args.stats_file)
    if not stats_path.exists():
        print(
            f"ERROR: Stats file not found: {stats_path}. "
            "Run 'poetry run mutmut export-cicd-stats' first.",
            file=sys.stderr,
        )
        return 1

    try:
        with open(stats_path) as f:
            stats = json.load(f)
        killed = int(stats["killed"])
        total = int(stats["total"])
    except (json.JSONDecodeError, KeyError, ValueError) as exc:
        print(f"ERROR: Failed to parse stats file {stats_path}: {exc}", file=sys.stderr)
        return 1

    try:
        threshold = read_threshold(args.threshold_key)
    except (KeyError, ValueError) as exc:
        print(f"ERROR: Failed to read threshold: {exc}", file=sys.stderr)
        return 1

    result = evaluate_gate(
        module_name=args.module_name,
        killed=killed,
        total=total,
        threshold=threshold,
    )

    print(f"  Mutation score for {result.module_name}: {result.message}")
    print(json.dumps(result.to_dict(), indent=2))

    return 0 if result.status == GateStatus.PASS else 1


if __name__ == "__main__":
    sys.exit(main())
