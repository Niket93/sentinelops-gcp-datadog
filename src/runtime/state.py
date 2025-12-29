# src/runtime/state.py
from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class StageInFlight:
    start_ts: float
    stage: str
    trace_id: str
    clip_index: int
    dd_trace_id: int
    dd_parent_id: int


@dataclass
class TraceTimestamps:
    clip_ts: Optional[float] = None
    obs_ts: Optional[float] = None
    dec_ts: Optional[float] = None
    act_ts: Optional[float] = None


class RuntimeState:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.inflight: Dict[str, StageInFlight] = {}
        self.ts: Dict[str, TraceTimestamps] = {}

    def begin_stage(self, trace_id: str, stage: str, clip_index: int, dd_trace_id: int, dd_parent_id: int) -> str:
        key = f"{trace_id}:{stage}"
        with self._lock:
            self.inflight[key] = StageInFlight(
                start_ts=time.time(),
                stage=stage,
                trace_id=trace_id,
                clip_index=int(clip_index),
                dd_trace_id=int(dd_trace_id),
                dd_parent_id=int(dd_parent_id),
            )
        return key

    def end_stage(self, key: str) -> Optional[StageInFlight]:
        with self._lock:
            return self.inflight.pop(key, None)

    def mark(self, trace_id: str, kind: str) -> None:
        now = time.time()
        with self._lock:
            t = self.ts.get(trace_id) or TraceTimestamps()
            if kind == "clip":
                t.clip_ts = now
            elif kind == "observation":
                t.obs_ts = now
            elif kind == "decision":
                t.dec_ts = now
            elif kind == "action":
                t.act_ts = now
            self.ts[trace_id] = t

    def e2e_decision_latency_ms(self, trace_id: str) -> Optional[int]:
        with self._lock:
            t = self.ts.get(trace_id)
            if not t or t.clip_ts is None or t.dec_ts is None:
                return None
            return int((t.dec_ts - t.clip_ts) * 1000)

    def e2e_observation_latency_ms(self, trace_id: str) -> Optional[int]:
        with self._lock:
            t = self.ts.get(trace_id)
            if not t or t.clip_ts is None or t.obs_ts is None:
                return None
            return int((t.obs_ts - t.clip_ts) * 1000)