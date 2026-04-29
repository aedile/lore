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
    """A line with the opt-out comment is treated as clean.

    Sanity-check by removing the comment and confirming the *same* line
    body would otherwise have been flagged — guards against the test
    passing because of a regex bug rather than the suppression.
    """
    body = "ssn,123-45-6789,active"
    suppressed = gate.scan_line(f"{body}  # pii-allowed: faker-generated")
    assert suppressed == []
    # Without the marker the SSN must be flagged.
    unsuppressed = gate.scan_line(body)
    assert any(kind == "SSN" for kind, _ in unsuppressed)


@pytest.mark.unit
def test_pii_allowed_comment_is_case_insensitive() -> None:
    """The opt-out marker matches regardless of case."""
    # All four casings must suppress findings; the unsuppressed body
    # would otherwise produce an SSN finding, so this isn't vacuous.
    body = "ssn,123-45-6789"
    for marker in ("pii-allowed", "PII-ALLOWED", "Pii-Allowed", "PII-Allowed"):
        line = f"{body}  # {marker}: synthetic data"
        assert gate.scan_line(line) == [], f"casing {marker!r} did not suppress"
    # Confirm the body without the marker IS flagged.
    assert any(kind == "SSN" for kind, _ in gate.scan_line(body))


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
    email_findings = [(kind, sample) for kind, sample in findings if kind == "email"]
    assert email_findings == [], f"email {email} was flagged but should be exempt: {email_findings}"
    # The full email string itself must not appear in any finding sample —
    # protects against a partial match (e.g. flagging only the local-part).
    assert all(email not in sample for _, sample in findings)


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
    # The verbatim email address must appear in the captured sample so a
    # reviewer can see what tripped the gate, not just that something did.
    email_samples = [sample for kind, sample in findings if kind == "email"]
    assert any(email in sample for sample in email_samples), (
        f"email {email!r} not present in any captured sample {email_samples}"
    )


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
    # Adding a single PII row to the same file MUST flip the result —
    # this anchors the empty case against an active counterexample.
    fixture.write_text("id,name,score,ssn\n1,alpha,0.5,123-45-6789\n", encoding="utf-8")
    dirty = gate.scan_file(fixture)
    assert dirty, "expected scan_file to find PII once SSN row was added"


# ---------------------------------------------------------------------------
# main() entry point
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_main_returns_zero_on_clean_tree(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """main() returns 0 and produces no findings output when nothing is dirty."""
    (tmp_path / "fixtures").mkdir()
    (tmp_path / "fixtures" / "f.csv").write_text("id,score\n1,0.5\n", encoding="utf-8")
    code = gate.main([str(tmp_path / "fixtures")])
    assert code == 0
    captured = capsys.readouterr()
    # On a clean tree main() must NOT print findings — any "pii-allowed"
    # advice or sample digits would indicate a false positive in the gate.
    assert "pii-allowed" not in captured.out
    assert "123-45-6789" not in captured.out


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
