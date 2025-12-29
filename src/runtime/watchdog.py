# src/runtime/watchdog.py
from __future__ import annotations

import time
import threading
from typing import Dict

from ..config.settings import Settings
from ..audit.buffer import AuditBuffer
from ..obs.datadog import metric_count, dd_event
from .state import RuntimeState

SLO_BY_STAGE = {
    "observer": "slo_observer_ms",
    "thinker": "slo_thinker_ms",
    "doer": "slo_doer_ms",
    "dispatcher": "slo_dispatcher_ms",
}


class Watchdog:
    def __init__(self, cfg: Settings, audit: AuditBuffer, state: RuntimeState) -> None:
        self.cfg = cfg
        self.audit = audit
        self.state = state
        self._stop = threading.Event()
        self._fired: Dict[str, float] = {}

    def stop(self) -> None:
        self._stop.set()

    def run(self) -> None:
        while not self._stop.is_set():
            self._tick()
            time.sleep(0.25)

    def _tick(self) -> None:
        now = time.time()

        with self.state._lock:
            inflight = list(self.state.inflight.items())

        for key, inf in inflight:
            slo_attr = SLO_BY_STAGE.get(inf.stage)
            if not slo_attr:
                continue
            slo_ms = int(getattr(self.cfg, slo_attr))
            elapsed_ms = int((now - inf.start_ts) * 1000)
            if elapsed_ms < slo_ms:
                continue

            last = self._fired.get(key, 0.0)
            if now - last < 10.0:
                continue
            self._fired[key] = now

            payload = {
                "event": "stage_timeout",
                "stage": inf.stage,
                "trace_id": inf.trace_id,
                "clip_index": inf.clip_index,
                "elapsed_ms": elapsed_ms,
                "slo_ms": slo_ms,
                "impact": "pipeline_delay_or_missed_action",
                "runbook": [
                    "Check tool error-rate for dependencies",
                    "Inspect LLM latency and token spikes",
                    "Enable degrade mode if repeated",
                ],
            }
            self.audit.add("stage_timeout", inf.trace_id, payload)
            metric_count("sentinel.stage.timeout", 1, {"stage": inf.stage})

            dd_event(
                title=f"SLO breach: {inf.stage}",
                text=f"Stage {inf.stage} exceeded SLO: {elapsed_ms}ms > {slo_ms}ms. trace_id={inf.trace_id} clip_index={inf.clip_index}",
                tags={
                    "stage": inf.stage,
                    "trace_id": inf.trace_id,
                    "clip_index": inf.clip_index,
                    "service": self.cfg.dd_service,
                    "env": self.cfg.dd_env,
                    "version": self.cfg.dd_version,
                },
                alert_type="warning",
            )
