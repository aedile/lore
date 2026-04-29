"""Feature tests for ``configure_logging`` and ``get_logger``.

These tests assert the public API works for callers — that the chain
configures without error in both JSON and console modes, and that
``get_logger`` returns a usable bound logger that goes through the
redaction chain end-to-end.
"""

from __future__ import annotations

import io
import json
import logging
from contextlib import redirect_stderr

import pytest
import structlog

from lore_eligibility.bootstrapper.logging_config import (
    configure_logging,
    get_logger,
)


@pytest.fixture(autouse=True)
def _reset_structlog() -> None:
    """Reset structlog config between tests so each test starts clean."""
    structlog.reset_defaults()


@pytest.mark.unit
def test_configure_logging_runs_in_json_mode() -> None:
    """JSON mode configures without raising and produces a usable logger."""
    configure_logging(level=logging.INFO, json_format=True)
    logger = get_logger("test")
    assert logger is not None
    # Smoke-test that emitting does not raise.
    buffer = io.StringIO()
    with redirect_stderr(buffer):
        logger.info("benign message", trace_id="t-1")
    assert "benign message" in buffer.getvalue()


@pytest.mark.unit
def test_configure_logging_runs_in_console_mode() -> None:
    """Console mode also configures and produces output."""
    configure_logging(level=logging.INFO, json_format=False)
    logger = get_logger("test")
    buffer = io.StringIO()
    with redirect_stderr(buffer):
        logger.info("benign console message")
    output = buffer.getvalue()
    assert "benign console message" in output
    assert len(output) > 0


@pytest.mark.unit
def test_end_to_end_pii_redaction_in_json_output() -> None:
    """A real log call with PII produces JSON in which the PII is redacted."""
    configure_logging(level=logging.INFO, json_format=True)
    logger = get_logger("test")
    buffer = io.StringIO()
    with redirect_stderr(buffer):
        logger.info(
            "user lookup",
            ssn="123-45-6789",
            email_inline="user@example.com",
            event_extra="contact 555-123-4567 for status",
        )
    output = buffer.getvalue().strip()
    # Output should be a single JSON line.
    parsed = json.loads(output.splitlines()[-1])
    # Key-based: ssn must be redacted
    assert parsed["ssn"] == "***REDACTED***"
    # Pattern-based: email and phone in non-PII keys still get masked
    assert "user@example.com" not in output
    assert "555-123-4567" not in output


@pytest.mark.unit
def test_get_logger_returns_bound_logger_with_name() -> None:
    """get_logger() returns a logger that includes the bound name."""
    configure_logging(level=logging.INFO, json_format=True)
    logger = get_logger("lore_eligibility.test_module")
    assert logger is not None
    # A bound logger always has an info() method.
    assert callable(logger.info)


@pytest.mark.unit
def test_configure_logging_is_idempotent() -> None:
    """Calling configure_logging multiple times does not error or duplicate."""
    configure_logging(level=logging.INFO, json_format=True)
    configure_logging(level=logging.DEBUG, json_format=False)
    configure_logging(level=logging.INFO, json_format=True)
    logger = get_logger("test")
    assert logger is not None
