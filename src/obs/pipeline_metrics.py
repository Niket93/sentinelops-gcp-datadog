# src/obs/pipeline_metrics.py
from __future__ import annotations

import logging
import threading
import time
from typing import Dict, Optional

from ..bus.bus import Bus
from .datadog import metric_count, metric_gauge

log = logging.getLogger("sentinelops.pipeline_metrics")


class PipelineMetricsEmitter:

    def __init__(self, bus: Bus, interval_s: float = 5.0, tags: Optional[Dict[str, str]] = None) -> None:
        self.bus = bus
        self.interval_s = float(interval_s)
        self.tags = tags or {}
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        log.info("pipeline_metrics.started", extra={"interval_s": self.interval_s})

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                depths = {
                    "clips": self.bus.qsize(self.bus.TOPIC_CLIPS),
                    "observations": self.bus.qsize(self.bus.TOPIC_OBSERVATIONS),
                    "decisions": self.bus.qsize(self.bus.TOPIC_DECISIONS),
                    "actions": self.bus.qsize(self.bus.TOPIC_ACTIONS),
                }

                for topic, depth in depths.items():
                    metric_gauge(
                        "sentinel.pipeline.queue_depth",
                        float(depth),
                        tags={"topic": topic, **self.tags},
                    )

                metric_count("sentinel.pipeline.metrics_tick", 1, tags=self.tags)
            except Exception:
                log.exception("pipeline_metrics.emit_failed")
            time.sleep(self.interval_s)
