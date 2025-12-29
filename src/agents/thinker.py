# src/agents/thinker.py
from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

from ..config.settings import Settings
from ..shared.events import ObservationEvent, DecisionEvent
from ..shared.vertex import model_if_enabled
from ..bus.bus import Bus, TOPIC_OBSERVATIONS, TOPIC_DECISIONS
from ..audit.buffer import AuditBuffer
from ..runtime.state import RuntimeState
from ..gameday.controller import GameDayController
from ..obs.datadog import (
    span,
    llm_span,
    llm_annotate_io,
    metric_count,
    metric_dist,
    create_incident,
)
from ..obs.tokens import estimate_tokens, estimate_cost
from ..tools.base import call_tool
from ..tools.sop_lookup import SopLookupTool
from .prompts import SECURITY_THINKER_SYSTEM

log = logging.getLogger("sentinelops.thinker")


def _audit_emit(audit: AuditBuffer, kind: str, trace_id: str, payload: Dict[str, Any]) -> None:
    audit.add(kind, trace_id, payload)
    try:
        log.info("audit", extra={"kind": kind, "trace_id": trace_id, **(payload or {})})
    except Exception:
        pass


def _parse_json_soft(text: str) -> tuple[Dict[str, Any], bool]:
    try:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if not m:
            raise ValueError("no_json")
        return json.loads(m.group(0)), True
    except Exception:
        return {
            "assessment": {"violation": False, "rule_id": "other", "severity": "low", "confidence": 0.0, "risk": "unparsed_llm_output"},
            "recommended_actions": [],
            "rationale": {"short": "Model output could not be parsed.", "citations": []},
            "evidence": {"reason": "thinker_json_parse_fail", "clip_range": [0, 0]},
        }, False


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


def _normalize_actions(actions: Any) -> List[Dict[str, Any]]:
    if not isinstance(actions, list):
        return []
    out: List[Dict[str, Any]] = []
    for a in actions:
        if not isinstance(a, dict):
            continue
        out.append({
            "type": _canonical_action_type(str(a.get("type", ""))),
            "target": str(a.get("target", "console") or "console"),
            "priority": _canonical_priority(str(a.get("priority", ""))),
            "message": str(a.get("message", "") or "Action recommended.").strip(),
        })
    return out[:1]


def _yn(v: object) -> str:
    if isinstance(v, str):
        s = v.strip().lower()
        if s in {"yes", "no", "uncertain"}:
            return s
    return "uncertain"


class ThinkerAgent:
    def __init__(
        self,
        cfg: Settings,
        bus: Bus,
        audit: AuditBuffer,
        state: RuntimeState,
        gameday: GameDayController,
        sop_tool: SopLookupTool,
    ) -> None:
        self.cfg = cfg
        self.bus = bus
        self.audit = audit
        self.state = state
        self.gameday = gameday
        self.sop_tool = sop_tool
        self.model = model_if_enabled(cfg, cfg.gemini_thinker_model)

        self._cooldown_s = 4
        self._last_emit: Dict[str, float] = {}

    def _cooldown_ok(self, key: str) -> bool:
        now = time.time()
        last = self._last_emit.get(key, 0.0)
        if now - last < self._cooldown_s:
            return False
        self._last_emit[key] = now
        return True

    def _should_trigger(self, obs: ObservationEvent) -> Tuple[bool, str]:
        s = obs.signals or {}
        walkway = _yn(s.get("walkway_violation")) == "yes"
        restricted = _yn(s.get("restricted_area_entry")) == "yes"
        prox = _yn(s.get("unsafe_proximity_to_machine")) == "yes"
        machine = _yn(s.get("machine_operating")) == "yes"
        panel = _yn(s.get("panel_open")) == "yes"
        guard = _yn(s.get("guard_open")) == "yes"

        if panel and machine:
            return True, "panel_open_while_operating"
        if guard and machine:
            return True, "guard_open_while_operating"
        if prox and machine:
            return True, "unsafe_proximity_while_operating"
        if restricted:
            return True, "restricted_area_entry"
        if walkway:
            return True, "walkway_violation"
        return False, ""

    def handle_observation(self, msg: dict) -> None:
        obs = ObservationEvent(**msg)
        trigger, rule = self._should_trigger(obs)
        if not trigger:
            return

        dedup_key = f"{obs.camera_id}:{rule}"
        if not self._cooldown_ok(dedup_key):
            return

        stage_key = self.state.begin_stage(obs.trace_id, "thinker", obs.clip_index, obs.dd_trace_id, obs.dd_parent_id)

        _audit_emit(self.audit, "stage", obs.trace_id, {
            "event": "stage_start",
            "stage": "thinker",
            "rule_id": rule,
            **self.gameday.tags(),
        })

        t0 = time.time()
        status = "ok"
        parse_ok = True

        tags = {
            "stage": "thinker",
            "agent": "thinker",
            "use_case": "security",
            "camera_id": obs.camera_id,
            "clip_index": obs.clip_index,
            "trace_id": obs.trace_id,
            "rule_id": rule,
            "model_name": self.cfg.gemini_thinker_model,
            **self.gameday.tags(),
        }

        try:
            tool_res = call_tool("sop_lookup", lambda: self.sop_tool.lookup(rule), timeout_ms=700)

            metric_dist("sentinel.tool.latency_ms", tool_res.latency_ms, {"tool": "sop_lookup", **self.gameday.tags()})
            metric_count("sentinel.tool.calls", 1, {"tool": "sop_lookup", **self.gameday.tags()})

            _audit_emit(self.audit, "tool_call", obs.trace_id, {
                "event": "tool_call",
                "tool_name": "sop_lookup",
                "ok": tool_res.ok,
                "latency_ms": tool_res.latency_ms,
                "error_type": tool_res.error_type,
                "error": tool_res.error,
                **self.gameday.tags(),
            })

            citations: List[Dict[str, Any]] = []
            if tool_res.ok and tool_res.data:
                hits = tool_res.data.get("hits") or []
                if isinstance(hits, list):
                    for h in hits[:3]:
                        if isinstance(h, dict):
                            citations.append({"source": "sop_lookup", "id": h.get("id"), "text": h.get("text")})
                if not hits:
                    metric_count("sentinel.rag.no_results", 1, {"tool": "sop_lookup", **self.gameday.tags()})
            else:
                _audit_emit(self.audit, "tool_error", obs.trace_id, {
                    "event": "tool_error",
                    "tool_name": "sop_lookup",
                    "error_type": tool_res.error_type,
                    "error": tool_res.error,
                    **self.gameday.tags(),
                })
                metric_count("sentinel.tool.error", 1, {"tool": "sop_lookup", "error_type": tool_res.error_type or "dependency", **self.gameday.tags()})

            if self.model is None:
                out = {
                    "assessment": {"violation": True, "rule_id": rule, "severity": "medium", "confidence": 0.6, "risk": "stub_mode"},
                    "recommended_actions": [{"type": "alert", "target": "console", "message": f"Investigate: {rule}", "priority": "P2"}],
                    "rationale": {"short": "Stub mode decision.", "citations": citations},
                    "evidence": {"reason": "stub", "clip_range": [obs.clip_index, obs.clip_index]},
                }
                parse_ok = True
                metric_count("sentinel.llm.calls", 1, {"agent": "thinker", "model": "stub", **self.gameday.tags()})
                dd_trace_id_out = obs.dd_trace_id
                dd_parent_id_out = obs.dd_parent_id
            else:
                payload = {
                    "camera_id": obs.camera_id,
                    "ts": obs.ts.isoformat(),
                    "clip_index": obs.clip_index,
                    "summary": obs.summary,
                    "signals": obs.signals,
                    "trigger_rule": rule,
                    "policy_citations": citations,
                }

                prompt = SECURITY_THINKER_SYSTEM + "\n\n" + "POLICY_CITATIONS:\n" + json.dumps(citations) + "\n"
                inp = f"OBS={json.dumps(payload)}"

                llm_t0 = time.time()
                input_tokens = estimate_tokens(prompt) + estimate_tokens(inp)

                with span("sentinel.stage.thinker", tags=tags, dd_trace_id=obs.dd_trace_id, dd_parent_id=obs.dd_parent_id) as s:
                    dd_trace_id_out = int(getattr(s, "trace_id", obs.dd_trace_id) or obs.dd_trace_id) if s else obs.dd_trace_id
                    dd_parent_id_out = int(getattr(s, "span_id", obs.dd_parent_id) or obs.dd_parent_id) if s else obs.dd_parent_id

                    with llm_span(model=self.cfg.gemini_thinker_model, name="thinker_decide", tags=tags):
                        raw = self.model.generate_content(
                            [prompt, inp],
                            generation_config={"temperature": 0.1, "max_output_tokens": 2000},
                        ).text

                    out, parse_ok = _parse_json_soft(raw)
                    llm_latency_ms = int((time.time() - llm_t0) * 1000)

                    output_tokens = estimate_tokens(raw)
                    tc = estimate_cost(input_tokens, output_tokens, self.cfg.cost_per_1k_input, self.cfg.cost_per_1k_output)

                    metric_count("sentinel.llm.calls", 1, {"agent": "thinker", "model": self.cfg.gemini_thinker_model, **self.gameday.tags()})
                    metric_dist("sentinel.llm.latency_ms", llm_latency_ms, {"agent": "thinker", "model": self.cfg.gemini_thinker_model, **self.gameday.tags()})
                    metric_count("sentinel.llm.parse_ok", 1 if parse_ok else 0, {"agent": "thinker", **self.gameday.tags()})
                    metric_count("sentinel.llm.parse_fail", 0 if parse_ok else 1, {"agent": "thinker", **self.gameday.tags()})
                    metric_dist("sentinel.llm.tokens.total", tc.total_tokens, {"agent": "thinker", **self.gameday.tags()})
                    metric_dist("sentinel.llm.cost.usd", tc.total_cost, {"agent": "thinker", **self.gameday.tags()})

                    llm_annotate_io(
                        input_messages=[{"role": "system", "content": "SECURITY_THINKER_SYSTEM"}, {"role": "user", "content": inp}],
                        output_messages=[{"role": "assistant", "content": raw[:2000]}],
                        metadata={"agent": "thinker", "rule_id": rule, "scenario": self.gameday.status().scenario},
                        metrics={
                            "input_tokens": float(tc.input_tokens),
                            "output_tokens": float(tc.output_tokens),
                            "total_tokens": float(tc.total_tokens),
                            "cost_usd": float(tc.total_cost),
                            "latency_ms": float(llm_latency_ms),
                            "parse_ok": 1.0 if parse_ok else 0.0,
                        },
                        tags=tags,
                    )

                    _audit_emit(self.audit, "health", obs.trace_id, {
                        "event": "llm_call",
                        "agent": "thinker",
                        "model": self.cfg.gemini_thinker_model,
                        "latency_ms": llm_latency_ms,
                        "parse_ok": parse_ok,
                        "input_tokens": tc.input_tokens,
                        "output_tokens": tc.output_tokens,
                        "total_tokens": tc.total_tokens,
                        "cost_usd": tc.total_cost,
                        **self.gameday.tags(),
                    })

            assessment = out.get("assessment", {}) if isinstance(out.get("assessment"), dict) else {}
            actions = _normalize_actions(out.get("recommended_actions"))

            if not bool(assessment.get("violation", False)) or not actions:
                return

            grounding_ok = tool_res.ok and bool(citations)
            if not grounding_ok and actions and actions[0]["type"] == "stop_line":
                actions[0]["type"] = "alert"
                actions[0]["priority"] = "P1"
                actions[0]["message"] = "Potential high-risk event detected; policy grounding unavailable—alert supervisor to verify before stopping line."
                _audit_emit(self.audit, "health", obs.trace_id, {
                    "event": "degradation",
                    "reason": "low_grounding",
                    "rule_id": rule,
                    **self.gameday.tags(),
                })
                metric_count("sentinel.degradation.low_grounding", 1, {"agent": "thinker", **self.gameday.tags()})

            decision = DecisionEvent(
                trace_id=obs.trace_id,
                dd_trace_id=dd_trace_id_out,
                dd_parent_id=dd_parent_id_out,
                clip_id=obs.clip_id,
                observation_id=obs.observation_id,
                camera_id=obs.camera_id,
                clip_index=obs.clip_index,
                ts=datetime.now(timezone.utc),
                assessment={
                    "violation": True,
                    "rule_id": str(assessment.get("rule_id", rule) or rule),
                    "severity": str(assessment.get("severity", "medium") or "medium"),
                    "confidence": float(assessment.get("confidence", 0.0) or 0.0),
                    "risk": str(assessment.get("risk", "safety_risk") or "safety_risk"),
                },
                recommended_actions=actions,
                rationale={
                    "short": (out.get("rationale", {}) or {}).get("short", "LLM decision."),
                    "citations": citations,
                },
                evidence=out.get("evidence", {"reason": "security_single_clip", "clip_range": [obs.clip_index, obs.clip_index]}),
                model={"name": self.cfg.gemini_thinker_model, "latency_ms": int((time.time() - t0) * 1000)},
            )

            self.state.mark(decision.trace_id, "decision")
            _audit_emit(self.audit, "decision", decision.trace_id, decision.model_dump(mode="json"))
            self.bus.publish(TOPIC_DECISIONS, decision.model_dump(mode="json"))

            e2e_ms = self.state.e2e_decision_latency_ms(decision.trace_id)
            if e2e_ms is not None:
                metric_dist("sentinel.e2e.decision_latency_ms", e2e_ms, {"use_case": "security", **self.gameday.tags()})
                _audit_emit(self.audit, "health", decision.trace_id, {
                    "event": "e2e_decision_latency",
                    "latency_ms": e2e_ms,
                    **self.gameday.tags(),
                })

                if e2e_ms > int(self.cfg.slo_pipeline_e2e_ms):
                    metric_count("sentinel.slo.e2e_decision_latency_breach", 1, {"use_case": "security", **self.gameday.tags()})
                    _audit_emit(self.audit, "stage_timeout", decision.trace_id, {
                        "event": "e2e_slo_breach",
                        "latency_ms": e2e_ms,
                        "slo_ms": int(self.cfg.slo_pipeline_e2e_ms),
                        **self.gameday.tags(),
                    })

                    # ✅ NEW: Create incident for SLO breach
                    create_incident(
                        title="SentinelOps: E2E Decision Latency SLO breach",
                        summary=f"E2E decision latency {e2e_ms}ms exceeded SLO {self.cfg.slo_pipeline_e2e_ms}ms. trace_id={decision.trace_id}",
                        severity="SEV-3",
                        tags={"signal": "latency", "trace_id": decision.trace_id, "rule_id": rule, **self.gameday.tags()},
                        metadata={
                            "trace_id": decision.trace_id,
                            "camera_id": decision.camera_id,
                            "clip_index": str(decision.clip_index),
                            "rule_id": rule,
                            "latency_ms": str(e2e_ms),
                            "slo_ms": str(self.cfg.slo_pipeline_e2e_ms),
                        },
                    )

        except Exception as e:
            status = "error"
            parse_ok = False
            _audit_emit(self.audit, "tool_error", obs.trace_id, {
                "event": "thinker_exception",
                "tool_name": "thinker",
                "error_type": "dependency",
                "error": str(e),
                **tags,
            })
            metric_count("sentinel.pipeline.failed", 1, {"reason": "thinker_exception"})
            metric_count("sentinel.stage.error", 1, {"stage": "thinker", **self.gameday.tags()})
            log.exception("thinker.handle_observation_failed", extra={"trace_id": obs.trace_id})

        finally:
            self.state.end_stage(stage_key)
            elapsed_ms = int((time.time() - t0) * 1000)

            _audit_emit(self.audit, "stage", obs.trace_id, {
                "event": "stage_end",
                "stage": "thinker",
                "status": status,
                "latency_ms": elapsed_ms,
                "parse_ok": parse_ok,
                "rule_id": rule,
                **self.gameday.tags(),
            })
            metric_dist("sentinel.stage.latency_ms", elapsed_ms, {"stage": "thinker", **self.gameday.tags()})

    def run(self) -> None:
        while True:
            msg = self.bus.consume(TOPIC_OBSERVATIONS, timeout_s=1.0)
            if msg is None:
                continue
            try:
                self.handle_observation(msg)
            except Exception as e:
                log.exception("thinker.loop_error", extra={"error": str(e)})
