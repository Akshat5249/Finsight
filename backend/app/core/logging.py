"""
FinSight — Structured Logging Configuration
Phase 7, Prompt 22. Implements §15 of the Blueprint.

Provides:
  - JSON-formatted structured log output (machine-readable)
  - Human-readable console format for development
  - Per-request correlation ID logging (via middleware)
  - Configurable log level via LOG_LEVEL env var
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone


class _JSONFormatter(logging.Formatter):
    """
    Formats log records as single-line JSON objects.
    Fields: timestamp, level, logger, message, [exc_info].
    Suitable for log aggregation systems (Datadog, CloudWatch, Loki).
    """

    def format(self, record: logging.LogRecord) -> str:
        payload: dict = {
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "level":     record.levelname,
            "logger":    record.name,
            "message":   record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        if hasattr(record, "correlation_id"):
            payload["correlation_id"] = record.correlation_id
        return json.dumps(payload)


def configure_logging() -> None:
    """
    Configure application logging. Behaviour is driven by env vars:
      LOG_LEVEL   — DEBUG | INFO | WARNING | ERROR  (default: INFO)
      LOG_FORMAT  — json | text                     (default: text in dev, json in prod)
      APP_ENV     — development | production
    """
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level      = getattr(logging, level_name, logging.INFO)
    env        = os.getenv("APP_ENV", "development")
    fmt        = os.getenv("LOG_FORMAT", "json" if env == "production" else "text")

    root = logging.getLogger()
    root.setLevel(level)

    # Remove existing handlers (avoid duplicate logs on reload)
    root.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)

    if fmt == "json":
        handler.setFormatter(_JSONFormatter())
    else:
        handler.setFormatter(logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        ))

    root.addHandler(handler)

    # Silence noisy third-party loggers
    for noisy in ("uvicorn.access", "httpx", "httpcore", "sqlalchemy.engine"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    logging.getLogger(__name__).info(
        "Logging configured: level=%s format=%s env=%s", level_name, fmt, env
    )
