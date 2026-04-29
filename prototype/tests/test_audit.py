"""Tests for prototype.audit + prototype.vault — A8 acceptance.

Covers PROTOTYPE_PRD.md A8 acceptance:
- AuditChain.append + validate round-trip is clean across multiple events.
- Tampering with one entry breaks the chain at that line and is detected.
- RedactionScanner reports zero matches against an audit chain produced by
  the prototype (only tokens in the audit log).
- Vault store/reveal/tombstone behaves: revealed plaintext matches; after
  tombstone, reveal returns None; the token row stays referenceable.
"""

from __future__ import annotations

import json
from pathlib import Path

from prototype.audit import (
    AuditChain,
    AuditEvent,
    PIIMatch,
    RedactionScanner,
)
from prototype.vault import Vault

# ---------------------------------------------------------------------------
# Vault: store / reveal / tombstone
# ---------------------------------------------------------------------------


def test_vault_store_and_reveal_round_trip(tmp_path: Path) -> None:
    vault = Vault(tmp_path / "vault.sqlite")
    token = vault.store(field_class="email", plaintext="sarah@example.invalid")
    assert token.startswith("vt_")
    assert vault.reveal(token) == "sarah@example.invalid"


def test_vault_reveal_returns_none_for_unknown_token(tmp_path: Path) -> None:
    vault = Vault(tmp_path / "vault.sqlite")
    assert vault.reveal("vt_does_not_exist") is None


def test_vault_tombstone_blanks_plaintext(tmp_path: Path) -> None:
    vault = Vault(tmp_path / "vault.sqlite")
    token = vault.store(field_class="phone", plaintext="555-555-1212")
    assert vault.reveal(token) == "555-555-1212"
    assert vault.tombstone(token) is True
    assert vault.reveal(token) is None


def test_vault_tombstone_idempotent(tmp_path: Path) -> None:
    vault = Vault(tmp_path / "vault.sqlite")
    token = vault.store(field_class="phone", plaintext="555-555-1212")
    assert vault.tombstone(token) is True
    # Second tombstone is a no-op (already tombstoned).
    assert vault.tombstone(token) is False


def test_vault_tombstoned_token_still_referenceable_via_audit(tmp_path: Path) -> None:
    """After tombstone, the token row remains so historical audit references
    resolve cleanly to None (rather than dangling)."""
    vault = Vault(tmp_path / "vault.sqlite")
    token = vault.store(field_class="ssn_full", plaintext="987-65-4321")
    vault.tombstone(token)
    # Reveal still resolves the token (returns None) — no exception.
    assert vault.reveal(token) is None


def test_vault_persists_across_reopen(tmp_path: Path) -> None:
    path = tmp_path / "vault.sqlite"
    v1 = Vault(path)
    token = v1.store(field_class="email", plaintext="sarah@example.invalid")
    v1.close()

    v2 = Vault(path)
    assert v2.reveal(token) == "sarah@example.invalid"


# ---------------------------------------------------------------------------
# AuditChain — hash chain + tamper detection
# ---------------------------------------------------------------------------


def _evt(event_class: str, target: str = "tok-001") -> AuditEvent:
    return AuditEvent(
        event_class=event_class,
        actor_role="prototype-system",
        target_token=target,
        outcome="SUCCESS",
        trigger="test",
    )


def test_chain_append_validates_clean(tmp_path: Path) -> None:
    chain = AuditChain(tmp_path / "audit.jsonl")
    for event_class in ("INGEST_RECEIVED", "DQ_PASSED", "MATCH_RESOLVED"):
        chain.append(_evt(event_class))

    result = chain.validate()
    assert result.valid is True
    assert result.entries_checked == 3
    assert result.broken_at_line is None


def test_chain_append_returns_self_hash(tmp_path: Path) -> None:
    chain = AuditChain(tmp_path / "audit.jsonl")
    h = chain.append(_evt("INGEST_RECEIVED"))
    assert len(h) == 64  # SHA-256 hex


def test_chain_first_entry_uses_genesis_prior_hash(tmp_path: Path) -> None:
    chain = AuditChain(tmp_path / "audit.jsonl")
    chain.append(_evt("INGEST_RECEIVED"))
    entries = list(chain)
    assert entries[0]["prior_event_hash"] == "0" * 64


def test_chain_subsequent_entry_links_to_previous_self_hash(tmp_path: Path) -> None:
    chain = AuditChain(tmp_path / "audit.jsonl")
    h1 = chain.append(_evt("INGEST_RECEIVED"))
    chain.append(_evt("DQ_PASSED"))
    entries = list(chain)
    assert entries[1]["prior_event_hash"] == h1


def test_chain_tampering_with_field_breaks_validation(tmp_path: Path) -> None:
    """Mutate one event's outcome field on disk; validate must fail at that line."""
    path = tmp_path / "audit.jsonl"
    chain = AuditChain(path)
    chain.append(_evt("INGEST_RECEIVED"))
    chain.append(_evt("DQ_PASSED"))
    chain.append(_evt("MATCH_RESOLVED"))

    # Tamper with line 2: change outcome from SUCCESS to FAILURE.
    lines = path.read_text(encoding="utf-8").splitlines()
    entry2 = json.loads(lines[1])
    entry2["outcome"] = "FAILURE"
    lines[1] = json.dumps(entry2, sort_keys=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    result = chain.validate()
    assert result.valid is False
    assert result.broken_at_line == 2
    assert result.error == "self_hash mismatch"


def test_chain_inserting_an_extra_entry_breaks_validation(tmp_path: Path) -> None:
    """Inserting a forged entry between two real ones breaks the chain."""
    path = tmp_path / "audit.jsonl"
    chain = AuditChain(path)
    chain.append(_evt("INGEST_RECEIVED"))
    chain.append(_evt("DQ_PASSED"))

    lines = path.read_text(encoding="utf-8").splitlines()
    forged = json.loads(lines[1])
    forged["target_token"] = "tok-FORGED"
    lines.insert(1, json.dumps(forged, sort_keys=True))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    result = chain.validate()
    assert result.valid is False
    assert result.broken_at_line is not None


def test_chain_empty_file_validates() -> None:
    """A fresh, never-appended-to chain validates as 0 entries."""
    import tempfile

    with tempfile.NamedTemporaryFile(mode="w+", suffix=".jsonl", delete=False) as f:
        chain = AuditChain(f.name)
        result = chain.validate()
    assert result.valid is True
    assert result.entries_checked == 0


# ---------------------------------------------------------------------------
# RedactionScanner — pattern set + JSON-aware skipping
# ---------------------------------------------------------------------------


def test_scanner_finds_ssn() -> None:
    scanner = RedactionScanner()
    matches = scanner.scan_text("logged: SSN=987-65-4321 for member")
    assert any(m.pattern_name == "SSN" for m in matches)


def test_scanner_finds_phone_and_email_and_us_date() -> None:
    scanner = RedactionScanner()
    text = "phone=555-555-1212 dob=04/12/1985 email=sarah@example.com"
    matches = scanner.scan_text(text)
    names = {m.pattern_name for m in matches}
    assert names == {"PHONE", "DOB_US_DATE", "EMAIL"}


def test_scanner_excludes_example_invalid_emails() -> None:
    """example.invalid is RFC 2606 — never a real address; not a redaction risk."""
    scanner = RedactionScanner()
    matches = scanner.scan_text("contact sarah.johnson@example.invalid for details")
    assert all(m.pattern_name != "EMAIL" for m in matches)


def test_scanner_clean_audit_chain_reports_zero_matches(tmp_path: Path) -> None:
    """An audit chain produced by the prototype (only tokens, no plaintext)
    must report zero matches from the redaction scanner."""
    chain = AuditChain(tmp_path / "audit.jsonl")
    chain.append(_evt("INGEST_RECEIVED", target="vt_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"))
    chain.append(_evt("MATCH_RESOLVED", target="0bb02edc-5549-5ba0-9010-086a72080505"))
    chain.append(_evt("DELETION_EXECUTED", target="canon-001"))

    scanner = RedactionScanner()
    matches = scanner.scan_jsonl(tmp_path / "audit.jsonl")
    assert matches == [], f"Audit chain should be PII-free; got {matches}"


def test_scanner_jsonl_skips_timestamp_fields(tmp_path: Path) -> None:
    """ISO date strings inside the chain's `timestamp` field must NOT
    false-positive as DOB."""
    path = tmp_path / "audit.jsonl"
    chain = AuditChain(path)
    chain.append(_evt("INGEST_RECEIVED"))
    scanner = RedactionScanner()
    assert scanner.scan_jsonl(path) == []


def test_scanner_catches_planted_pii_in_jsonl(tmp_path: Path) -> None:
    """If something *did* leak PII into the chain, the scanner catches it."""
    path = tmp_path / "audit.jsonl"
    path.write_text(
        json.dumps(
            {
                "event_class": "INGEST_RECEIVED",
                "target_token": "987-65-4321",  # SSN-shaped plaintext, not a real token
                "context": {"phone": "555-555-1212"},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    scanner = RedactionScanner()
    matches = scanner.scan_jsonl(path)
    names = {m.pattern_name for m in matches}
    assert "SSN" in names
    assert "PHONE" in names


def test_pii_match_is_immutable() -> None:
    m = PIIMatch(path="/x", line_number=1, pattern_name="SSN", excerpt="...")
    import pytest

    with pytest.raises(AttributeError, match="frozen|cannot"):
        m.line_number = 2  # type: ignore[misc]
