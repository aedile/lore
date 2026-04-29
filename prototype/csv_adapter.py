"""CSV format adapter — A2 from PROTOTYPE_PRD.md.

One adapter per *format family* per AD-016 — not one per partner. Per-partner
differences (column names, date formats, SSN representation) live in the YAML
mapping config, not in code.

Yields source rows verbatim (column names + values as the CSV declares them);
normalization to the canonical staging shape happens in ``mapping_engine``.
"""

from __future__ import annotations

import csv
from collections.abc import Iterator
from pathlib import Path


def read_csv(path: Path | str) -> Iterator[dict[str, str]]:
    """Yield each CSV row as a dict keyed by source column name.

    The dict preserves whatever column names the CSV declares — name
    translation and normalization are deferred to the mapping engine.
    """
    p = Path(path)
    with p.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            yield dict(row)


def read_csv_columns(path: Path | str) -> list[str]:
    """Return the CSV header row as a list of column names."""
    p = Path(path)
    with p.open(newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        return next(reader)
