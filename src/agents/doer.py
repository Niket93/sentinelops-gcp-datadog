# src/agents/doer.py
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List

from ..config.settings import Settings
from ..shared.events import DecisionEvent, ActionEvent
from ..shared.vertex import model_if_enabled
from ..bus.bus import Bus, TOPIC_DECISIONS, TOPIC_ACTIONS
from ..audit.buffer import AuditBuffer
from ..runtime.state import RuntimeState
from ..gameday.controller import GameDayController
from ..obs.datadog import (
    span,
    llm_span,
    llm_annotate_io,
    metric_count,
    metric_dist,
    dd_event,
    create_incident,
    create_case,
)
from ..obs.tokens import estimate_tokens, estimate_cost
from ..tools.base import call_tool
from ..tools.dispatcher import DispatcherTool
from .prompts import DOER_SYSTEM

log = logging.getLogger("sentinelops.doer")


def _audit_emit(audit: AuditBuffer, kind: str, trace_id: str, payload: Dict[str, Any]) -> None:
    audit.add(kind, trace_id, payload)
    try:
        log.info("audit", extra={"kind": kind, "trace_id": trace_id, **(payload or {})})
    except Exception:
        pass


def _canonical_action_type(t: str) -> str:
    s = (t or "").strip().lower().replace("-", "_").replace(" ", "_")
    if s in {"stop", "stopline", "stop_line", "halt", "shutdown"}:
        return "stop_line"
    if s in {"alert", "warn", "notify"}:
        return "alert"
    return s or "alert"


def _canonical_priority(p: str) -> str:
    s = (p or "").strip().upper()
    if s in {"P1", "P2", "P3"}:
        return s
    if s in {"1", "2", "3"}:
        return f"P{s}"
    return "P2"


def _parse_json_soft(text: str) -> tuple[Dict[str, Any], bool]:
    try:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start:end + 1]), True
    except Exception:
        pass
    return {"actions": []}, False


class DoerAgent:
    def __init__(
        self,
        cfg: Settings,
        bus: Bus,
        audit: AuditBuffer,
        state: RuntimeState,
        gameday: GameDayController,
        dispatcher: DispatcherTool,
    ) -> None:
        self.cfg = cfg
        self.bus = bus
        self.audit = audit
        self.state = state
        self.gameday = gameday
        self.dispatcher = dispatcher
        self.model = model_if_enabled(cfg, cfg.gemini_thinker_model)

        self._last: Dict[str, float] = {}

    def _dedup(self, key: str, cooldown_s: int = 20) -> bool:
        now = time.time()
        last = self._last.get(key, 0.0)
        if now - last < cooldown_s:
            return False
        self._last[key] = now
        return True

    def _enrich_actions(self, dec: DecisionEvent) -> tuple[List[Dict[str, Any]], bool, int, Dict[str, Any]]:
        base = []
        for a in (dec.recommended_actions or [])[:1]:
            base.append({
                "type": _canonical_action_type(str(a.get("type", ""))),
                "target": str(a.get("target", "console") or "console"),
                "priority": _canonical_priority(str(a.get("priority", ""))),
                "message": str(a.get("message", "") or "").strip(),
            })

        if self.model is None:
            a0 = base[0] if base else {"type": "alert", "target": "console", "priority": "P2", "message": "Investigate incident."}
            a0["execution_steps"] = ["Inspect area", "Confirm condition", "Log outcome"]
            return [a0], True, 0, {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "cost_usd": 0.0}

        prompt_obj = {
            "camera_id": dec.camera_id,
            "clip_index": dec.clip_index,
            "assessment": dec.assessment,
            "recommended_actions": base,
        }

        llm_t0 = time.time()
        system = DOER_SYSTEM
        user = f"DECISION={json.dumps(prompt_obj)}"
        input_tokens = estimate_tokens(system) + estimate_tokens(user)

        with llm_span(model=self.cfg.gemini_thinker_model, name="doer_enrich", tags={"agent": "doer", "trace_id": dec.trace_id, **self.gameday.tags()}):
            raw = self.model.generate_content(
                [system, user],
                generation_config={"temperature": 0.2, "max_output_tokens": 1200},
            ).text

        out, parse_ok = _parse_json_soft(raw)
        llm_latency_ms = int((time.time() - llm_t0) * 1000)
        output_tokens = estimate_tokens(raw)
        tc = estimate_cost(input_tokens, output_tokens, self.cfg.cost_per_1k_input, self.cfg.cost_per_1k_output)

        metric_count("sentinel.llm.calls", 1, {"agent": "doer", "model": self.cfg.gemini_thinker_model, **self.gameday.tags()})
        metric_dist("sentinel.llm.latency_ms", llm_latency_ms, {"agent": "doer", "model": self.cfg.gemini_thinker_model, **self.gameday.tags()})
        metric_count("sentinel.llm.parse_ok", 1 if parse_ok else 0, {"agent": "doer", **self.gameday.tags()})
        metric_count("sentinel.llm.parse_fail", 0 if parse_ok else 1, {"agent": "doer", **self.gameday.tags()})
        metric_dist("sentinel.llm.tokens.total", tc.total_tokens, {"agent": "doer", **self.gameday.tags()})
        metric_dist("sentinel.llm.cost.usd", tc.total_cost, {"agent": "doer", **self.gameday.tags()})

        llm_annotate_io(
            input_messages=[{"role": "system", "content": "DOER_SYSTEM"}, {"role": "user", "content": user}],
            output_messages=[{"role": "assistant", "content": (raw or "")[:2000]}],
            metadata={"agent": "doer", "scenario": self.gameday.status().scenario},
            metrics={
                "input_tokens": float(tc.input_tokens),
                "output_tokens": float(tc.output_tokens),
                "total_tokens": float(tc.total_tokens),
                "cost_usd": float(tc.total_cost),
                "latency_ms": float(llm_latency_ms),
                "parse_ok": 1.0 if parse_ok else 0.0,
            },
            tags={"agent": "doer", "trace_id": dec.trace_id, **self.gameday.tags()},
        )

        _audit_emit(self.audit, "health", dec.trace_id, {
            "event": "llm_call",
            "agent": "doer",
            "model": self.cfg.gemini_thinker_model,
            "latency_ms": llm_latency_ms,
            "parse_ok": parse_ok,
            "input_tokens": tc.input_tokens,
            "output_tokens": tc.output_tokens,
            "total_tokens": tc.total_tokens,
            "cost_usd": tc.total_cost,
            **self.gameday.tags(),
        })

        actions = out.get("actions", [])
        if not isinstance(actions, list) or not actions:
            a0 = base[0] if base else {"type": "alert", "target": "console", "priority": "P2", "message": "Investigate incident."}
            a0["execution_steps"] = ["Inspect area", "Confirm condition", "Log outcome"]
            return [a0], False, llm_latency_ms, {"input_tokens": tc.input_tokens, "output_tokens": tc.output_tokens, "total_tokens": tc.total_tokens, "cost_usd": tc.total_cost}

        a = actions[0] if isinstance(actions[0], dict) else {}
        enriched = {
            "type": _canonical_action_type(str(a.get("type", base[0]["type"] if base else "alert"))),
            "target": str(a.get("target", "console") or "console"),
            "priority": _canonical_priority(str(a.get("priority", base[0]["priority"] if base else "P2"))),
            "message": str(a.get("message", "") or (base[0]["message"] if base else "Action recommended.")).strip(),
            "execution_steps": a.get("execution_steps", []),
            "notes": str(a.get("notes", "") or "").strip(),
        }
        if base and enriched["type"] != base[0]["type"]:
            enriched["type"] = base[0]["type"]

        return [enriched], parse_ok, llm_latency_ms, {"input_tokens": tc.input_tokens, "output_tokens": tc.output_tokens, "total_tokens": tc.total_tokens, "cost_usd": tc.total_cost}

    def handle_decision(self, msg: dict) -> None:
        dec = DecisionEvent(**msg)
        sev = str(dec.assessment.get("severity", "low")).lower()
        base_key = f"{dec.camera_id}:{sev}"

        stage_key = self.state.begin_stage(dec.trace_id, "doer", dec.clip_index, dec.dd_trace_id, dec.dd_parent_id)

        _audit_emit(self.audit, "stage", dec.trace_id, {"event": "stage_start", "stage": "doer", **self.gameday.tags()})

        t0 = time.time()
        status = "ok"

        tags = {
            "stage": "doer",
            "agent": "doer",
            "use_case": "security",
            "camera_id": dec.camera_id,
            "clip_index": dec.clip_index,
            "trace_id": dec.trace_id,
            "rule_id": str(dec.assessment.get("rule_id", "")),
            **self.gameday.tags(),
        }

        try:
            if self.gameday.active("dispatcher_outage") and self.cfg.gameday_force:
                self.dispatcher.set_down(True)
            else:
                self.dispatcher.set_down(False)

            with span("sentinel.stage.doer", tags=tags, dd_trace_id=dec.dd_trace_id, dd_parent_id=dec.dd_parent_id) as s:
                dd_trace_id_out = int(getattr(s, "trace_id", dec.dd_trace_id) or dec.dd_trace_id) if s else dec.dd_trace_id
                dd_parent_id_out = int(getattr(s, "span_id", dec.dd_parent_id) or dec.dd_parent_id) if s else dec.dd_parent_id

                actions, parse_ok, _, _ = self._enrich_actions(dec)

                for a in actions[:1]:
                    a_type = _canonical_action_type(str(a.get("type", "")))
                    dedup_key = f"{base_key}:{a_type}"

                    metric_count("sentinel.action.attempted", 1, {"action_type": a_type, **self.gameday.tags()})

                    if not self._dedup(dedup_key):
                        evt = ActionEvent(
                            trace_id=dec.trace_id,
                            dd_trace_id=dd_trace_id_out,
                            dd_parent_id=dd_parent_id_out,
                            decision_id=dec.decision_id,
                            camera_id=dec.camera_id,
                            ts=datetime.now(timezone.utc),
                            action=a,
                            status="skipped",
                            provider="dedup",
                        )
                        _audit_emit(self.audit, "action", evt.trace_id, {**evt.model_dump(mode="json"), "status": "skipped"})
                        self.bus.publish(TOPIC_ACTIONS, evt.model_dump(mode="json"))
                        metric_count("sentinel.action.skipped", 1, {"action_type": a_type, **self.gameday.tags()})
                        metric_count("sentinel.pipeline.completed", 1, {"outcome": "skipped", "action_type": a_type})
                        continue

                    disp_key = self.state.begin_stage(dec.trace_id, "dispatcher", dec.clip_index, dd_trace_id_out, dd_parent_id_out)
                    disp_t0 = time.time()

                    _audit_emit(self.audit, "stage", dec.trace_id, {"event": "stage_start", "stage": "dispatcher", "action_type": a_type, **self.gameday.tags()})

                    tool_res = call_tool("dispatcher", lambda: self.dispatcher.send(a), timeout_ms=self.cfg.slo_dispatcher_ms)

                    self.state.end_stage(disp_key)
                    disp_latency_ms = int((time.time() - disp_t0) * 1000)

                    metric_dist("sentinel.stage.latency_ms", disp_latency_ms, {"stage": "dispatcher", **self.gameday.tags()})
                    metric_count("sentinel.tool.calls", 1, {"tool": "dispatcher", **self.gameday.tags()})
                    metric_dist("sentinel.tool.latency_ms", tool_res.latency_ms, {"tool": "dispatcher", **self.gameday.tags()})

                    if tool_res.ok:
                        evt = ActionEvent(
                            trace_id=dec.trace_id,
                            dd_trace_id=dd_trace_id_out,
                            dd_parent_id=dd_parent_id_out,
                            decision_id=dec.decision_id,
                            camera_id=dec.camera_id,
                            ts=datetime.now(timezone.utc),
                            action=a,
                            status="sent",
                            provider="dispatcher",
                        )
                        _audit_emit(self.audit, "action", evt.trace_id, {**evt.model_dump(mode="json"), "status": "sent"})
                        self.bus.publish(TOPIC_ACTIONS, evt.model_dump(mode="json"))
                        metric_count("sentinel.action.sent", 1, {"action_type": a_type, **self.gameday.tags()})
                        metric_dist("sentinel.action.delivery_latency_ms", tool_res.latency_ms, {"action_type": a_type, **self.gameday.tags()})
                        metric_count("sentinel.pipeline.completed", 1, {"outcome": "sent", "action_type": a_type})
                    else:
                        _audit_emit(self.audit, "tool_error", dec.trace_id, {
                            "event": "dispatcher_failed",
                            "tool_name": "dispatcher",
                            "error_type": tool_res.error_type or "dependency",
                            "error": tool_res.error or "dispatcher_failed",
                            "action_type": a_type,
                            **self.gameday.tags(),
                        })
                        metric_count("sentinel.tool.error", 1, {"tool": "dispatcher", "error_type": tool_res.error_type or "dependency", **self.gameday.tags()})
                        metric_count("sentinel.pipeline.completed", 1, {"outcome": "failed", "action_type": a_type})

                        dd_event(
                            title="Dispatcher action delivery failed",
                            text=f"Dispatcher failed: action_type={a_type} trace_id={dec.trace_id} error={tool_res.error or 'unknown'}",
                            tags={
                                "tool": "dispatcher",
                                "action_type": a_type,
                                "trace_id": dec.trace_id,
                                "stage": "dispatcher",
                                "camera_id": dec.camera_id,
                                "clip_index": dec.clip_index,
                                **self.gameday.tags(),
                            },
                            alert_type="error",
                        )

                        # ✅ NEW: create Incident (reliability)
                        create_incident(
                            title="SentinelOps: Dispatcher delivery failure",
                            summary=f"Dispatcher failed delivering action_type={a_type}. trace_id={dec.trace_id} error={tool_res.error}",
                            severity="SEV-2",
                            tags={"signal": "action", "tool": "dispatcher", "trace_id": dec.trace_id, **self.gameday.tags()},
                            metadata={
                                "trace_id": dec.trace_id,
                                "camera_id": dec.camera_id,
                                "clip_index": str(dec.clip_index),
                                "action_type": a_type,
                                "error": tool_res.error or "dispatcher_failed",
                            },
                        )

                        # ✅ OPTIONAL: create Case too (makes demo stronger if Cases enabled)
                        create_case(
                            title="SentinelOps: Dispatcher outage investigation",
                            description=(
                                f"Action delivery failing.\n"
                                f"trace_id={dec.trace_id}\n"
                                f"action_type={a_type}\n"
                                f"error={tool_res.error}\n"
                                f"scenario={self.gameday.status().scenario}\n"
                                f"camera_id={dec.camera_id} clip_index={dec.clip_index}"
                            ),
                            tags={"signal": "action", "tool": "dispatcher", "trace_id": dec.trace_id, **self.gameday.tags()},
                            priority="HIGH",
                        )

                        evt = ActionEvent(
                            trace_id=dec.trace_id,
                            dd_trace_id=dd_trace_id_out,
                            dd_parent_id=dd_parent_id_out,
                            decision_id=dec.decision_id,
                            camera_id=dec.camera_id,
                            ts=datetime.now(timezone.utc),
                            action={**a, "target": "pager", "message": f"{a.get('message','')} (Dispatcher down → fallback)"},
                            status="failed",
                            provider="dispatcher",
                            error=tool_res.error or "dispatcher_failed",
                        )
                        _audit_emit(self.audit, "action", evt.trace_id, {**evt.model_dump(mode="json"), "status": "failed"})
                        self.bus.publish(TOPIC_ACTIONS, evt.model_dump(mode="json"))
                        metric_count("sentinel.action.failed", 1, {"action_type": a_type, **self.gameday.tags()})

        except Exception as e:
            status = "error"
            _audit_emit(self.audit, "tool_error", dec.trace_id, {
                "event": "doer_exception",
                "tool_name": "doer",
                "error_type": "dependency",
                "error": str(e),
                **tags,
            })
            metric_count("sentinel.pipeline.failed", 1, {"reason": "doer_exception"})
            metric_count("sentinel.stage.error", 1, {"stage": "doer", **self.gameday.tags()})
            log.exception("doer.handle_decision_failed", extra={"trace_id": dec.trace_id})

        finally:
            self.state.end_stage(stage_key)
            elapsed_ms = int((time.time() - t0) * 1000)

            _audit_emit(self.audit, "stage", dec.trace_id, {
                "event": "stage_end",
                "stage": "doer",
                "status": status,
                "latency_ms": elapsed_ms,
                **self.gameday.tags(),
            })
            metric_dist("sentinel.stage.latency_ms", elapsed_ms, {"stage": "doer", **self.gameday.tags()})

    def run(self) -> None:
        while True:
            msg = self.bus.consume(TOPIC_DECISIONS, timeout_s=1.0)
            if msg is None:
                continue
            try:
                self.handle_decision(msg)
            except Exception:
                log.exception("doer.loop_error")
