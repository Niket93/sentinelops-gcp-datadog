# src/obs/dd_api.py
from __future__ import annotations
import requests
from typing import Any, Dict, Optional

class DatadogAPIv2:
    def __init__(self, api_key: str, app_key: str, site: str) -> None:
        self.api_key = (api_key or "").strip()
        self.app_key = (app_key or "").strip()
        self.site = (site or "datadoghq.com").strip()
        self.enabled = bool(self.api_key and self.app_key)

    def _headers(self) -> Dict[str, str]:
        return {
            "DD-API-KEY": self.api_key,
            "DD-APPLICATION-KEY": self.app_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def post(self, path: str, payload: Dict[str, Any], timeout_s: float = 4.0) -> Optional[Dict[str, Any]]:
        if not self.enabled:
            return None
        url = f"https://api.{self.site}{path}"
        r = requests.post(url, headers=self._headers(), json=payload, timeout=timeout_s)
        if r.status_code >= 300:
            raise RuntimeError(f"Datadog API error {r.status_code}: {r.text[:300]}")
        return r.json()