# src/gameday/controller.py
from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Dict, Optional

from ..config.settings import Settings
from ..audit.buffer import AuditBuffer
from ..obs.datadog import metric_count

VALID_SCENARIOS = {"none", "dispatcher_outage", "long_running_observer", "injection"}

@dataclass
class GameDayStatus:
    enabled: bool
    scenario: str
    since_ts: float
    force: bool

class GameDayController:
    def __init__(self, cfg: Settings, audit: AuditBuffer) -> None:
        self.cfg = cfg
        self.audit = audit
        self._lock = threading.Lock()
        self._scenario = cfg.gameday_scenario if cfg.gameday_enabled else "none"
        if self._scenario not in VALID_SCENARIOS:
            self._scenario = "none"
        self._since = time.time()
        self._force = bool(cfg.gameday_force)

    def status(self) -> GameDayStatus:
        with self._lock:
            return GameDayStatus(enabled=self.cfg.gameday_enabled, scenario=self._scenario, since_ts=self._since, force=self._force)

    def set_scenario(self, scenario: str) -> None:
        if scenario not in VALID_SCENARIOS:
            scenario = "none"
        with self._lock:
            self._scenario = scenario
            self._since = time.time()
        self.audit.add("health", "gameday", {"event": "scenario_set", "scenario": scenario})
        metric_count("sentinel.gameday.scenario_set", 1, {"scenario": scenario})

    def reset(self) -> None:
        self.set_scenario("none")

    def active(self, scenario: str) -> bool:
        if not self.cfg.gameday_enabled:
            return False
        with self._lock:
            return self._scenario == scenario

    def tags(self) -> Dict[str, str]:
        st = self.status()
        return {"scenario": st.scenario, "gameday": str(st.enabled).lower()}