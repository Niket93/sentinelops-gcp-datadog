# src/obs/dd_events.py
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import requests

log = logging.getLogger("sentinelops.dd_events")


class DatadogEventClient:
    
    def __init__(self, api_key: str, site: str) -> None:
        self.api_key = (api_key or "").strip()
        self.site = (site or "datadoghq.com").strip()
        self.enabled = bool(self.api_key)

    def send_event(
        self,
        title: str,
        text: str,
        tags: Optional[Dict[str, Any]] = None,
        alert_type: str = "info",
    ) -> None:
        if not self.enabled:
            return

        url = f"https://api.{self.site}/api/v1/events"
        payload = {
            "title": title,
            "text": text,
            "tags": [f"{k}:{v}" for k, v in (tags or {}).items()],
            "alert_type": alert_type,
        }
        headers = {"DD-API-KEY": self.api_key, "Content-Type": "application/json"}

        try:
            r = requests.post(url, json=payload, headers=headers, timeout=2.5)
            if r.status_code >= 300:
                log.warning(
                    "dd_event.failed",
                    extra={"status_code": r.status_code, "body": (r.text or "")[:300]},
                )
        except Exception:
            log.exception("dd_event.exception")
