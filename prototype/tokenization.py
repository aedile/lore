"""Tokenization stub — initial pieces of A8 from PROTOTYPE_PRD.md.

Per AD-009 the production design uses random tokens for non-joinable PII and
deterministic non-FPE tokens for joinable identifiers (the ones identity
resolution must compare across partners). The prototype implements only the
deterministic side here — it's the half A6 (verification API) needs.

For prototype scale we use HMAC-SHA-256 with a per-environment salt instead
of Cloud KMS. The interface is the same as the production contract; only
the backing is replaced (per ARD Stubbed-for-Prototype list).

The reverse direction (token -> plaintext, "vault" lookups) lands in A8
together with the random-token path and the JSONL audit chain.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import unicodedata
from datetime import date

# Default prototype salt. Override via the LORE_TOKEN_SALT env var.
# Production: this comes from Cloud KMS-wrapped material per AD-009.
_DEFAULT_SALT = b"prototype-salt-do-not-use-in-prod"


def _salt() -> bytes:
    return os.environ.get("LORE_TOKEN_SALT", "").encode("utf-8") or _DEFAULT_SALT


def _normalize_text(value: str) -> str:
    """NFC-normalise, lowercase, strip, collapse interior whitespace.

    Tokens are deterministic over the normalized form so:
    - Cross-partner identity resolution can match "Sarah Johnson" against
      "  sarah  johnson".
    - Unicode equivalents collapse to one token: "café" (NFC, single 'é')
      and "café" (NFD, 'e' + combining acute) tokenize identically.
      Without NFC normalisation an attacker could evade identity
      resolution by sending the alternate form.
    """
    nfc = unicodedata.normalize("NFC", value or "")
    return " ".join(nfc.strip().lower().split())


def _hmac_token(category: bytes, value: str) -> str:
    """Return a hex digest scoped by category. Category prevents same-value
    collisions across different field types (e.g. last_name vs first_name)."""
    payload = category + b":" + _normalize_text(value).encode("utf-8")
    return hmac.new(_salt(), payload, hashlib.sha256).hexdigest()


# ---------------------------------------------------------------------------
# Joinable tokens (deterministic non-FPE per AD-009)
# ---------------------------------------------------------------------------


def tokenize_name(first_name: str, last_name: str) -> str:
    """Single name_token for identity-resolution anchor (first + last)."""
    combined = f"{_normalize_text(first_name)}|{_normalize_text(last_name)}"
    return _hmac_token(b"name", combined)


def tokenize_last_name(value: str) -> str:
    return _hmac_token(b"last_name", value)


def tokenize_dob(value: str | date) -> str:
    """DOB tokenization — accepts ISO-string or date object."""
    if isinstance(value, date):
        value = value.isoformat()
    return _hmac_token(b"dob", value)


def tokenize_ssn_last4(value: str) -> str:
    return _hmac_token(b"ssn_last4", value)


def tokenize_partner_member_id(partner_id: str, partner_member_id: str) -> str:
    return _hmac_token(b"partner_member_id", f"{partner_id}|{partner_member_id}")


# ---------------------------------------------------------------------------
# Suppression hash (BR-703) — the deletion-ledger entry
# ---------------------------------------------------------------------------


def suppression_hash(
    *,
    last_name: str,
    dob: str | date,
    partner_id: str,
    partner_member_id: str,
) -> str:
    """Strict-tuple BR-703 hash. Catches same-partner re-introduction.

    Holds no recoverable PII — irreversibility is the point. The hash is
    deterministic, salted, and normalised for casing/whitespace.
    """
    if isinstance(dob, date):
        dob = dob.isoformat()
    parts = (
        _normalize_text(last_name),
        dob,
        _normalize_text(partner_id),
        _normalize_text(partner_member_id),
    )
    payload = b"suppression:" + "|".join(parts).encode("utf-8")
    return hashlib.sha256(_salt() + payload).hexdigest()


def suppression_hash_broad(*, dob: str | date, ssn_last4: str) -> str:
    """Broad BR-703 hash on (dob, ssn_last4) — catches cross-partner
    re-introduction with name typos.

    Used in addition to ``suppression_hash`` so the demo's
    delete-then-reintroduce-via-different-partner-with-name-typo flow
    surfaces SUPPRESSED_DELETED automatically. ``ssn_last4`` collisions
    inside a single DOB cohort are possible (1 in 10000) but acceptable
    for the prototype scale; production tunes this with additional
    discriminators per partner.
    """
    if isinstance(dob, date):
        dob = dob.isoformat()
    payload = b"suppression_broad:" + f"{dob}|{ssn_last4}".encode()
    return hashlib.sha256(_salt() + payload).hexdigest()


__all__ = [
    "suppression_hash",
    "suppression_hash_broad",
    "tokenize_dob",
    "tokenize_last_name",
    "tokenize_name",
    "tokenize_partner_member_id",
    "tokenize_ssn_last4",
]
