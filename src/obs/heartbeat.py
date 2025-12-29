# src/obs/heartbeat.py
from __future__ import annotations

import logging
import threading
import time
from typing import Dict, Optional

from .datadog import metric_gauge

log = logging.getLogger("sentinelops.heartbeat")


class HeartbeatEmitter:

    def __init__(self, interval_s: float = 10.0, tags: Optional[Dict[str, str]] = None) -> None:
        self.interval_s = float(interval_s)
        self.tags = tags or {}
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._start_ts = time.time()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        log.info("heartbeat.started", extra={"interval_s": self.interval_s})

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                metric_gauge("sentinel.app.heartbeat", 1.0, tags=self.tags)
                uptime = time.time() - self._start_ts
                metric_gauge("sentinel.app.uptime_s", float(uptime), tags=self.tags)
            except Exception:
                log.exception("heartbeat.emit_failed")
            time.sleep(self.interval_s)
