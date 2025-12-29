# src/tools/sop_lookup.py
from __future__ import annotations

import json
import os
from typing import Any, Dict, List

class SopLookupTool:
    def __init__(self, sop_path: str = "./data/sop/assembly_sop.json") -> None:
        self.sop_path = sop_path
        self._cache: Dict[str, Any] | None = None

    def _load(self) -> Dict[str, Any]:
        if self._cache is not None:
            return self._cache
        if not os.path.exists(self.sop_path):
            raise RuntimeError(f"SOP file missing: {self.sop_path}")
        with open(self.sop_path, "r", encoding="utf-8") as f:
            self._cache = json.load(f)
        return self._cache

    def lookup(self, query: str) -> Dict[str, Any]:
        sop = self._load()
        steps = sop.get("steps", [])
        q = (query or "").lower()
        hits: List[Dict[str, Any]] = []
        for s in steps:
            text = f"{s.get('step_id','')} {s.get('description','')} {s.get('action','')}".lower()
            if q and q in text:
                hits.append({"id": s.get("step_id"), "text": s.get("description"), "action": s.get("action")})
        return {"hits": hits[:5], "count": len(hits)}