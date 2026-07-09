"""Structured JSON logging.

Emits one JSON object per log line so Databricks driver logs / ADF activity
output can be parsed downstream. Every log carries a stable set of context
fields (env, pipeline, run_id, layer) set once via ``configure``.

Usage (top of a notebook):
    from utils.logging import get_logger
    log = get_logger("bronze_ingestion", env=env, run_id=run_id)
    log.info("merge_complete", rows_written=1234, table="bronze.gh_events_batch")
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any


class _JsonFormatter(logging.Formatter):
    """Render LogRecords as single-line JSON, merging nested context fields."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
        }
        # Context is stashed under a single, collision-safe attribute so keys
        # like `name`/`module` (reserved on LogRecord) can be logged freely.
        ctx = getattr(record, "context_fields", None)
        if isinstance(ctx, dict):
            payload.update(ctx)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


class _ContextAdapter(logging.LoggerAdapter):
    """Attach persistent context and pass call-site kwargs as nested context."""

    # Standard logging kwargs that must be forwarded as-is, not treated as context.
    _PASSTHROUGH = ("exc_info", "stack_info", "stacklevel")

    def process(self, msg: str, kwargs: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        # Everything the caller passed that isn't a standard logging kwarg is
        # context. Nest it under a single `extra` key so it never collides with
        # reserved LogRecord attributes (name, module, msg, ...).
        call_extra = {k: kwargs.pop(k) for k in list(kwargs) if k not in self._PASSTHROUGH}
        kwargs["extra"] = {"context_fields": {**(self.extra or {}), **call_extra}}
        return msg, kwargs


def get_logger(name: str, level: int = logging.INFO, **context: Any) -> _ContextAdapter:
    """Return a JSON logger bound to ``context`` (env, run_id, pipeline, ...)."""
    logger = logging.getLogger(name)
    if not any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(_JsonFormatter())
        logger.addHandler(handler)
        logger.propagate = False
    logger.setLevel(level)
    return _ContextAdapter(logger, context)
