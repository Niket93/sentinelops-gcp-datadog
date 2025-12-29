# src/tools/dispatcher.py
from __future__ import annotations

import time
from typing import Any, Dict

class DispatcherTool:
    def __init__(self) -> None:
        self.simulated_down = False
        self.simulated_latency_ms = 0

    def set_down(self, down: bool) -> None:
        self.simulated_down = bool(down)

    def set_latency(self, latency_ms: int) -> None:
        self.simulated_latency_ms = max(0, int(latency_ms))

    def send(self, action: Dict[str, Any]) -> Dict[str, Any]:
        if self.simulated_latency_ms:
            time.sleep(self.simulated_latency_ms / 1000.0)
        if self.simulated_down:
            raise RuntimeError("dispatcher_unavailable")
        return {"delivered": True, "target": action.get("target", "console")}