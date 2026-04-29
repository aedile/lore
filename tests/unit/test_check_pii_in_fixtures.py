"""Tests for the PII-in-test-fixtures gate script.

Cover both the pure scan logic (scan_line, scan_file) and the CLI
entry point. The script has zero third-party deps, so we test it as
plain Python.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# The script lives outside the package; add scripts/ to sys.path for import.
_SCRIPTS_DIR = Path(__file__).parent.parent.parent / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))

import check_pii_in_fixtures as gate  # noqa: E402

# ---------------------------------------------------------------------------
# scan_line — attack
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.attack
@pytest.mark.parametrize(
    ("line", "expected_kind"),
    [
        ("ssn,123-45-6789,active", "SSN"),
        ("Patient born 1985-03-15 verified", "DOB-shape"),
        ("Contact: 555-123-4567", "phone"),
        ("Send to jane.doe@gmail.com today", "email"),
    ],
)
def test_scan_line_flags_realistic_pii(line: str, expected_kind: str) -> None:
    """Each PII shape is detected on a representative line."""
    findings = gate.scan_line(line)
    assert findings, f"expected a finding for line: {line!r}"
    kinds = {kind for kind, _ in findings}
    assert expected_kind in kinds


@pytest.mark.unit
@pytest.mark.attack
def test_scan_line_finds_multiple_pii_in_one_line() -> None:
    """A single line containing multiple PII shapes flags each one."""
    line = "user jane.doe@gmail.com (SSN 123-45-6789) phone 555-123-4567"
    findings = gate.scan_line(line)
    kinds = {kind for kind, _ in findings}
    assert {"SSN", "phone", "email"}.issubset(kinds)
    assert len(findings) >= 3


# ---------------------------------------------------------------------------
# scan_line — opt-out
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_pii_allowed_comment_suppresses_findings() -> None:
    """A line with the opt-out comment is treated as clean."""
    line = "ssn,123-45-6789,active  # pii-allowed: faker-generated"
    findings = gate.scan_line(line)
    assert findings == []


@pytest.mark.unit
def test_pii_allowed_comment_is_case_insensitive() -> None:
    """The opt-out marker matches regardless of case."""
    line = "ssn,123-45-6789  # PII-Allowed: synthetic data"
    findings = gate.scan_line(line)
    assert findings == []


# ---------------------------------------------------------------------------
# Email exemption logic
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize(
    "email",
    [
        "user@example.com",
        "test@example.org",
        "anyone@example.net",
        "any@localhost",
        "fake@foo.invalid",
        "test@bar.test",
        "dev@baz.local",
    ],
)
def test_exempt_email_domains_are_not_flagged(email: str) -> None:
    """Conventional test/fictional domains do not produce findings."""
    line = f"contact: {email}"
    findings = gate.scan_line(line)
    assert all(kind != "email" for kind, _ in findings), (
        f"email {email} was flagged but should be exempt"
    )


@pytest.mark.unit
@pytest.mark.attack
@pytest.mark.parametrize(
    "email",
    [
        "real.person@gmail.com",
        "patient@protonmail.com",
        "subscriber@aol.com",
    ],
)
def test_realistic_email_domains_are_flagged(email: str) -> None:
    """Real-world email domains are flagged as PII."""
    line = f"contact: {email}"
    findings = gate.scan_line(line)
    kinds = {kind for kind, _ in findings}
    assert "email" in kinds


# ---------------------------------------------------------------------------
# scan_file — integration
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_scan_file_reports_findings_with_lineno(tmp_path: Path) -> None:
    """scan_file returns (path, lineno, kind, sample) tuples."""
    fixture = tmp_path / "fixture.csv"
    fixture.write_text(
        "id,ssn\n1,123-45-6789\n2,987-65-4321\n",
        encoding="utf-8",
    )
    findings = gate.scan_file(fixture)
    assert len(findings) == 2
    line_numbers = {f[1] for f in findings}
    assert line_numbers == {2, 3}
    samples = {f[3] for f in findings}
    assert "123-45-6789" in samples
    assert "987-65-4321" in samples


@pytest.mark.unit
def test_scan_file_returns_empty_on_clean_input(tmp_path: Path) -> None:
    """A file with no PII shapes returns an empty list."""
    fixture = tmp_path / "clean.csv"
    fixture.write_text("id,name,score\n1,alpha,0.5\n2,beta,0.7\n", encoding="utf-8")
    findings = gate.scan_file(fixture)
    assert findings == []


# ---------------------------------------------------------------------------
# main() entry point
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_main_returns_zero_on_clean_tree(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """main() returns 0 when no PII is found."""
    (tmp_path / "fixtures").mkdir()
    (tmp_path / "fixtures" / "f.csv").write_text("id,score\n1,0.5\n", encoding="utf-8")
    code = gate.main([str(tmp_path / "fixtures")])
    assert code == 0


@pytest.mark.unit
@pytest.mark.attack
def test_main_returns_one_on_dirty_tree(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """main() returns 1 and prints findings when PII is found."""
    (tmp_path / "fixtures").mkdir()
    (tmp_path / "fixtures" / "f.csv").write_text("id,ssn\n1,123-45-6789\n", encoding="utf-8")
    code = gate.main([str(tmp_path / "fixtures")])
    assert code == 1
    captured = capsys.readouterr()
    assert "123-45-6789" in captured.out
    assert "pii-allowed" in captured.out
