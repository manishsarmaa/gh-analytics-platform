"""Unit tests for structured JSON logging."""

from __future__ import annotations

import json
import logging

import pytest

from utils.logging import get_logger


@pytest.mark.unit
def test_logger_emits_json_with_context(capsys: pytest.CaptureFixture[str]) -> None:
    log = get_logger("test_logger_json", env="dev", run_id="abc123")
    log.info("merge_complete", rows_written=42, table="bronze.gh_events_batch")

    line = capsys.readouterr().out.strip().splitlines()[-1]
    record = json.loads(line)

    assert record["event"] == "merge_complete"
    assert record["level"] == "INFO"
    assert record["env"] == "dev"
    assert record["run_id"] == "abc123"
    assert record["rows_written"] == 42
    assert record["table"] == "bronze.gh_events_batch"
    assert "ts" in record


@pytest.mark.unit
def test_logger_does_not_duplicate_handlers() -> None:
    a = get_logger("test_no_dup")
    b = get_logger("test_no_dup")
    assert a.logger is b.logger
    assert len([h for h in a.logger.handlers if isinstance(h, logging.StreamHandler)]) == 1


@pytest.mark.unit
def test_reserved_logrecord_keys_do_not_crash(capsys: pytest.CaptureFixture[str]) -> None:
    # `name`/`module` collide with LogRecord attributes; the logger must accept
    # them as context, not raise KeyError (regression from dq_checks).
    log = get_logger("test_reserved")
    log.info("check", name="unique:event_id", module="dq", passed=True)
    record = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert record["event"] == "check"
    assert record["name"] == "unique:event_id"
    assert record["module"] == "dq"
    assert record["passed"] is True


@pytest.mark.unit
def test_exception_is_captured(capsys: pytest.CaptureFixture[str]) -> None:
    log = get_logger("test_exc")
    try:
        raise ValueError("boom")
    except ValueError:
        log.error("failed", exc_info=True)
    record = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert record["event"] == "failed"
    assert "ValueError: boom" in record["exc"]
