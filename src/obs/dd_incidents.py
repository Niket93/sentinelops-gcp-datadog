# src/obs/dd_incidents.py
from __future__ import annotations

from typing import Any, Dict, Optional, List
import logging

from .dd_api import DatadogAPIv2

log = logging.getLogger("sentinelops.obs.incidents")


def _normalize_severity(severity: str) -> str:
    s = (severity or "").strip().upper()
    if not s.startswith("SEV-"):
        return "SEV-2"
    if s not in {"SEV-1", "SEV-2", "SEV-3", "SEV-4", "SEV-5"}:
        return "SEV-2"
    return s


def _normalize_customer_impact(scope: str) -> str:
    s = (scope or "").strip()
    return s or "Unknown"


def _summary_markdown(title: str, summary: str, metadata: Optional[Dict[str, Any]] = None) -> str:
    base = []
    base.append(f"## Summary\n{(summary or '').strip() or 'No summary provided.'}\n")

    if metadata:
        base.append("## Context\n")
        for k, v in metadata.items():
            base.append(f"- **{k}**: {v}")
        base.append("")

    base.append("## Runbook\n- Check SentinelOps dashboard\n- Inspect dispatcher dependency\n- Review traces/logs for correlated failures\n")
    return "\n".join(base).strip() + "\n"


class DatadogIncidentClient:

    def __init__(self, api: DatadogAPIv2) -> None:
        self.api = api

    def create_incident(
        self,
        title: str,
        summary: str,
        severity: str = "SEV-2",
        tags: Optional[List[str]] = None,
        customer_impact: str = "Unknown",
        metadata: Optional[Dict[str, Any]] = None,
        is_test: bool = True,
    ) -> Optional[Dict[str, Any]]:

        title = (title or "").strip() or "SentinelOps Incident"
        sev = _normalize_severity(severity)
        impact = _normalize_customer_impact(customer_impact)

        # Generate markdown content (summary + metadata)
        # We put metadata here to avoid 400s from 'fields' schema validation
        md = _summary_markdown(title=title, summary=summary, metadata=metadata)

        # Fields: only specific ones we know (severity, summary)
        # Datadog V2 fields are strict.
        fields = {}
        fields["severity"] = {"value": sev}
        fields["summary"] = {"value": md}  # Map markdown summary/metadata to the Summary field

        payload: Dict[str, Any] = {
            "data": {
                "type": "incidents",
                "attributes": {
                    "title": title,
                    "fields": fields,
                    # Removed initial_cells to avoid "attributes was unexpected" schema error
                }
            }
        }
        
        try:
            resp = self.api.post("/api/v2/incidents", payload)
            log.info("incident.created", extra={"title": title, "incident_id": resp.get("data", {}).get("id")})
            return resp
        except Exception as e:
            log.error("incident.create_failed", extra={"error": str(e), "title": title})
            raise e