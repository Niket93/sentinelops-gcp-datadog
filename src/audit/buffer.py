# src/audit/buffer.py
from __future__ import annotations

import threading
from collections import deque
from datetime import datetime, timezone
from typing import Any, Deque, Dict, List, Literal, Optional
import uuid

AuditKind = Literal[
    "clip",
    "observation",
    "decision",
    "action",
    "chat",
    "tool_call",
    "tool_error",
    "stage",
    "stage_timeout",
    "security",
    "health",
]


class AuditBuffer:

    def __init__(self, max_events: int = 4000) -> None:
        self._lock = threading.Lock()
        self._events: Deque[dict[str, Any]] = deque(maxlen=max_events)

    def add(self, kind: AuditKind, trace_id: str, payload: Dict[str, Any]) -> str:
        eid = str(uuid.uuid4())
        ev = {
            "audit_id": eid,
            "ts": datetime.now(timezone.utc).isoformat(),
            "kind": kind,
            "trace_id": trace_id,
            "payload": payload or {},
        }
        with self._lock:
            self._events.append(ev)
        return eid

    def recent(self, limit: int = 200) -> List[dict[str, Any]]:
        lim = max(1, int(limit))
        with self._lock:
            items = list(self._events)[-lim:]
        return list(reversed(items))

    def kpi(self) -> dict[str, Any]:

        with self._lock:
            items = list(self._events)

        decisions = [x for x in items if x["kind"] == "decision"]
        observations = [x for x in items if x["kind"] == "observation"]
        actions = [x for x in items if x["kind"] == "action"]
        tool_errors = [x for x in items if x["kind"] == "tool_error"]
        stage_timeouts = [x for x in items if x["kind"] == "stage_timeout"]
        security_events = [x for x in items if x["kind"] == "security"]

        stop_line = 0
        alert = 0
        last_stop_ts: Optional[str] = None
        p = {"P1": 0, "P2": 0, "P3": 0}

        sent = 0
        failed = 0
        skipped = 0

        for a in actions:
            payload = a.get("payload") or {}
            act = (payload.get("action") or {}) if isinstance(payload.get("action"), dict) else {}
            t = str(act.get("type", "")).lower()
            pr = str(act.get("priority", "")).upper()
            status = str(payload.get("status", "")).lower()

            if pr in p:
                p[pr] += 1
            if status == "sent":
                sent += 1
            elif status == "failed":
                failed += 1
            elif status == "skipped":
                skipped += 1
            if t == "stop_line":
                stop_line += 1
                last_stop_ts = a["ts"]
            elif t == "alert":
                alert += 1

        return {
            "stop_line": stop_line,
            "alert": alert,
            "decisions": len(decisions),
            "observations": len(observations),
            "actions": len(actions),
            "action_sent": sent,
            "action_failed": failed,
            "action_skipped": skipped,
            "last_stop_line_ts": last_stop_ts,
            "priorities": p,
            "tool_errors": len(tool_errors),
            "stage_timeouts": len(stage_timeouts),
            "security_events": len(security_events),
        }