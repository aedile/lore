"""Audit chain + redaction scanner — A8 from PROTOTYPE_PRD.md.

Two pieces of the cross-cutting audit infrastructure:

1. ``AuditChain`` — append-only JSONL with a SHA-256 hash chain. Each entry
   carries ``prior_event_hash`` (the previous entry's ``self_hash``) plus
   its own ``self_hash`` computed over the canonical JSON of all other
   fields. Tampering with any field of any entry breaks the chain at that
   point and is detected by ``validate``.
2. ``RedactionScanner`` — regex-based PII detector. Scans plain text or
   JSONL files (with awareness of "timestamp" fields so ISO-date strings
   in chain timestamps don't false-positive). Used to assert "zero
   plaintext PII in any log line" before the panel walkthrough demo.

In production these two would be the audit Pub/Sub + Dataflow path and a
sampling job; the prototype keeps both local so the chain is verifiable
and the scanner runs in seconds for the demo.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from collections.abc import Iterable, Iterator
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AuditEvent:
    """Caller-supplied event payload. Matches the production audit_event shape
    minus the ``prior_event_hash`` + ``self_hash`` columns the chain adds on
    append.
    """

    event_class: str
    actor_role: str
    target_token: str
    outcome: str
    trigger: str
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    actor_principal: str = "prototype-system"
    context: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ChainValidationResult:
    """Outcome of ``AuditChain.validate``."""

    valid: bool
    entries_checked: int
    broken_at_line: int | None = None  # 1-indexed
    error: str | None = None


# ---------------------------------------------------------------------------
# Hash-chained audit log
# ---------------------------------------------------------------------------


_GENESIS_PRIOR_HASH = "0" * 64


class AuditChain:
    """Append-only JSONL with SHA-256 hash chain."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.touch(exist_ok=True)

    def append(self, event: AuditEvent) -> str:
        """Append ``event`` and return its ``self_hash``."""
        prior_hash = self._last_self_hash() or _GENESIS_PRIOR_HASH
        entry = self._entry_dict(event, prior_event_hash=prior_hash)
        self_hash = _entry_self_hash(entry)
        entry["self_hash"] = self_hash
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, sort_keys=True) + "\n")
        return self_hash

    def __iter__(self) -> Iterator[dict[str, Any]]:
        with self.path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                yield json.loads(line)

    def validate(self) -> ChainValidationResult:
        """Walk the chain start-to-end and return a structured verdict."""
        prior_hash = _GENESIS_PRIOR_HASH
        line_number = 0
        try:
            with self.path.open(encoding="utf-8") as f:
                for raw in f:
                    line_number += 1
                    raw = raw.strip()
                    if not raw:
                        continue
                    entry = json.loads(raw)
                    if entry.get("prior_event_hash") != prior_hash:
                        return ChainValidationResult(
                            valid=False,
                            entries_checked=line_number,
                            broken_at_line=line_number,
                            error="prior_event_hash mismatch",
                        )
                    expected = _entry_self_hash(
                        {k: v for k, v in entry.items() if k != "self_hash"}
                    )
                    if entry.get("self_hash") != expected:
                        return ChainValidationResult(
                            valid=False,
                            entries_checked=line_number,
                            broken_at_line=line_number,
                            error="self_hash mismatch",
                        )
                    prior_hash = entry["self_hash"]
        except json.JSONDecodeError as exc:
            return ChainValidationResult(
                valid=False,
                entries_checked=line_number,
                broken_at_line=line_number,
                error=f"json decode error: {exc}",
            )
        return ChainValidationResult(valid=True, entries_checked=line_number)

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------

    def _last_self_hash(self) -> str | None:
        last = None
        with self.path.open(encoding="utf-8") as f:
            for raw in f:
                raw = raw.strip()
                if raw:
                    last = raw
        if last is None:
            return None
        return json.loads(last).get("self_hash")  # type: ignore[no-any-return]

    @staticmethod
    def _entry_dict(event: AuditEvent, *, prior_event_hash: str) -> dict[str, Any]:
        d = asdict(event)
        d["prior_event_hash"] = prior_event_hash
        return d


def _entry_self_hash(entry: dict[str, Any]) -> str:
    """Canonical JSON SHA-256 over every field except ``self_hash``."""
    canonical = json.dumps(
        {k: v for k, v in entry.items() if k != "self_hash"},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Redaction scanner
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PIIMatch:
    path: str
    line_number: int
    pattern_name: str
    excerpt: str


# Pattern set for the prototype. Production would tune false-positive rates.
_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    # 9-digit SSN with dashes. Faker-generated ITINs (900-prefix) are still PII-shaped.
    ("SSN", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    # US-format date.
    ("DOB_US_DATE", re.compile(r"\b\d{1,2}/\d{1,2}/\d{4}\b")),
    # 10-digit phone with dashes.
    ("PHONE", re.compile(r"\b\d{3}-\d{3}-\d{4}\b")),
    # Email with a recognisable TLD. Excludes example.invalid (RFC 2606 reserved).
    (
        "EMAIL",
        re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.(?!invalid\b)[A-Za-z]{2,}\b"),
    ),
)


class RedactionScanner:
    """Scan files for plaintext PII patterns.

    JSONL files: each line is parsed as JSON; the scanner walks the values,
    *skipping* fields that are commonly non-PII timestamps so ISO-date
    strings don't false-positive.

    Plain text files: each line is scanned in full.
    """

    SKIP_FIELDS_FOR_DATE_PATTERNS: tuple[str, ...] = (
        "timestamp",
        "created_at",
        "deleted_at",
        "tombstoned_at",
        "queued_at",
        "claimed_at",
        "resolved_at",
        "decided_at",
        "first_seen_at",
        "last_updated_at",
        "state_effective_from",
        "state_effective_to",
    )

    def scan_text(self, text: str, *, path: str = "<text>") -> list[PIIMatch]:
        matches: list[PIIMatch] = []
        for line_number, line in enumerate(text.splitlines(), start=1):
            for name, pattern in _PATTERNS:
                for m in pattern.finditer(line):
                    matches.append(
                        PIIMatch(
                            path=path,
                            line_number=line_number,
                            pattern_name=name,
                            excerpt=line[max(0, m.start() - 8) : m.end() + 8].strip(),
                        )
                    )
        return matches

    def scan_jsonl(self, path: Path | str) -> list[PIIMatch]:
        p = Path(path)
        matches: list[PIIMatch] = []
        with p.open(encoding="utf-8") as f:
            for line_number, raw in enumerate(f, start=1):
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    entry = json.loads(raw)
                except json.JSONDecodeError:
                    matches.extend(self.scan_text(raw, path=str(p)))
                    continue
                for hit in self._scan_value(entry):
                    matches.append(
                        PIIMatch(
                            path=str(p),
                            line_number=line_number,
                            pattern_name=hit[0],
                            excerpt=hit[1],
                        )
                    )
        return matches

    def scan_files(self, paths: Iterable[Path | str]) -> list[PIIMatch]:
        out: list[PIIMatch] = []
        for p in paths:
            pp = Path(p)
            if pp.suffix == ".jsonl":
                out.extend(self.scan_jsonl(pp))
            else:
                out.extend(self.scan_text(pp.read_text(encoding="utf-8"), path=str(pp)))
        return out

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------

    def _scan_value(
        self,
        value: Any,
        *,
        skip_date_patterns: bool = False,
        key_path: str = "",
    ) -> list[tuple[str, str]]:
        out: list[tuple[str, str]] = []
        if isinstance(value, dict):
            for k, v in value.items():
                child_skip = skip_date_patterns or k in self.SKIP_FIELDS_FOR_DATE_PATTERNS
                out.extend(self._scan_value(v, skip_date_patterns=child_skip, key_path=k))
        elif isinstance(value, list):
            for v in value:
                out.extend(
                    self._scan_value(v, skip_date_patterns=skip_date_patterns, key_path=key_path)
                )
        elif isinstance(value, str):
            for name, pattern in _PATTERNS:
                if skip_date_patterns and name in ("DOB_US_DATE",):
                    continue
                for m in pattern.finditer(value):
                    excerpt = value[max(0, m.start() - 8) : m.end() + 8]
                    out.append((name, excerpt))
        return out


__all__ = [
    "AuditChain",
    "AuditEvent",
    "ChainValidationResult",
    "PIIMatch",
    "RedactionScanner",
]
