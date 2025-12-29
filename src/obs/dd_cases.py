# src/obs/dd_cases.py
from __future__ import annotations
from typing import Any, Dict, Optional, List
from .dd_api import DatadogAPIv2

class DatadogCaseClient:
    def __init__(self, api: DatadogAPIv2) -> None:
        self.api = api

    def create_case(
        self,
        title: str,
        description: str,
        case_type: str = "STANDARD",
        priority: str = "NOT_DEFINED",
        tags: Optional[List[str]] = None,
        project_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        payload: Dict[str, Any] = {
            "data": {
                "type": "case",
                "attributes": {
                    "title": title,
                    "description": description,
                    "type": case_type, 
                    "priority": priority,
                },
            }
        }

        # if tags:
        #    payload["data"]["attributes"]["tags"] = tags

        if project_id:
            payload["data"]["relationships"] = {
                "project": {"data": {"id": project_id, "type": "project"}}
            }

        return self.api.post("/api/v2/cases", payload)
