# src/tools/base.py
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Tuple

@dataclass
class ToolResult:
    ok: bool
    data: Optional[Dict[str, Any]] = None
    error_type: Optional[str] = None 
    error: Optional[str] = None
    latency_ms: int = 0
    retryable: bool = False

def call_tool(name: str, fn: Callable[[], Dict[str, Any]], timeout_ms: int = 1000) -> ToolResult:
    t0 = time.time()
    try:
        data = fn()
        lat = int((time.time() - t0) * 1000)
        if lat > timeout_ms:
            return ToolResult(ok=False, error_type="timeout", error=f"{name} exceeded timeout", latency_ms=lat, retryable=True)
        return ToolResult(ok=True, data=data, latency_ms=lat)
    except Exception as e:
        lat = int((time.time() - t0) * 1000)
        return ToolResult(ok=False, error_type="dependency", error=str(e), latency_ms=lat, retryable=True)