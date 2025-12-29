# src/obs/logging.py
from __future__ import annotations

import logging
import os
import sys

from pythonjsonlogger import jsonlogger


class TraceContextFilter(logging.Filter):
    
    def filter(self, record: logging.LogRecord) -> bool:

        if not hasattr(record, "trace_id"):
            record.trace_id = ""

        record.service = os.getenv("DD_SERVICE", os.getenv("DD_SERVICE_NAME", "sentinelops"))
        record.env = os.getenv("DD_ENV", "dev")
        record.version = os.getenv("DD_VERSION", "0.1.0")

        try:
            from ddtrace import tracer
            span = tracer.current_span()
            if span:
                record.__dict__["dd.trace_id"] = str(span.trace_id)
                record.__dict__["dd.span_id"] = str(span.span_id)
            else:
                record.__dict__["dd.trace_id"] = ""
                record.__dict__["dd.span_id"] = ""
        except Exception:
            record.__dict__["dd.trace_id"] = ""
            record.__dict__["dd.span_id"] = ""

        return True


def setup_logging() -> None:
    level = os.getenv("LOG_LEVEL", "INFO").upper()

    root = logging.getLogger()
    root.setLevel(level)

    for h in list(root.handlers):
        root.removeHandler(h)

    handler = logging.StreamHandler(sys.stdout)

    fmt = (
        "%(asctime)s %(levelname)s %(name)s %(message)s "
        "%(service)s %(env)s %(version)s "
        "%(trace_id)s %(dd.trace_id)s %(dd.span_id)s"
    )
    formatter = jsonlogger.JsonFormatter(fmt)
    handler.setFormatter(formatter)
    handler.addFilter(TraceContextFilter())

    root.addHandler(handler)

    logging.getLogger("uvicorn").setLevel(os.getenv("UVICORN_LOG_LEVEL", "WARNING"))
    logging.getLogger("uvicorn.error").setLevel(os.getenv("UVICORN_LOG_LEVEL", "WARNING"))
    logging.getLogger("uvicorn.access").setLevel(os.getenv("UVICORN_LOG_LEVEL", "WARNING"))