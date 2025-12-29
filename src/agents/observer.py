# src/agents/observer.py
from __future__ import annotations

import logging
import os
import re
import time
from datetime import datetime, timezone
from typing import Any, Dict

from vertexai.generative_models import Part

from ..config.settings import Settings
from ..shared.events import ClipEvent, ObservationEvent
from ..shared.vertex import model_if_enabled
from ..bus.bus import Bus, TOPIC_CLIPS, TOPIC_OBSERVATIONS
from ..audit.buffer import AuditBuffer
from ..runtime.state import RuntimeState
from ..gameday.controller import GameDayController
from ..obs.datadog import span, llm_span, llm_annotate_io, metric_count, metric_dist
from ..obs.tokens import estimate_tokens, estimate_cost
from .prompts import SECURITY_OBSERVER_PROMPT

log = logging.getLogger("sentinelops.observer")


def _parse_json(text: str) -> tuple[Dict[str, Any], bool]:
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return (
            {"summary": text.strip(), "signals": {"uncertainty": "high", "confidence_note": "no_json"}},
            False,
        )
    try:
        import json
        return (json.loads(m.group(0)), True)
    except Exception:
        return (
            {"summary": "Unparseable model output.", "signals": {"uncertainty": "high", "confidence_note": "json_parse_fail"}},
            False,
        )


def _audit_emit(audit: AuditBuffer, kind: str, trace_id: str, payload: Dict[str, Any]) -> None:
    audit.add(kind, trace_id, payload)
    try:
        log.info("audit", extra={"kind": kind, "trace_id": trace_id, **(payload or {})})
    except Exception:
        pass


class ObserverAgent:
    def __init__(self, cfg: Settings, bus: Bus, audit: AuditBuffer, state: RuntimeState, gameday: GameDayController) -> None:
        self.cfg = cfg
        self.bus = bus
        self.audit = audit
        self.state = state
        self.gameday = gameday
        self.model = model_if_enabled(cfg, cfg.gemini_observer_model)

    def handle_clip(self, msg: dict) -> None:
        clip = ClipEvent(**msg)

        stage_key = self.state.begin_stage(
            clip.trace_id, "observer", clip.clip_index, clip.dd_trace_id, clip.dd_parent_id
        )

        _audit_emit(self.audit, "stage", clip.trace_id, {
            "event": "stage_start",
            "stage": "observer",
            "clip_index": clip.clip_index,
            "dd_trace_id": clip.dd_trace_id,
            "dd_parent_id": clip.dd_parent_id,
            **self.gameday.tags(),
        })

        t0 = time.time()
        status = "ok"
        parse_ok = True
        out: Dict[str, Any] = {}

        tags = {
            "stage": "observer",
            "agent": "observer",
            "use_case": "security",
            "camera_id": clip.camera_id,
            "clip_index": clip.clip_index,
            "trace_id": clip.trace_id,
            "model_name": self.cfg.gemini_observer_model,
            **self.gameday.tags(),
        }

        try:
            if not os.path.exists(clip.clip_path):
                status = "error"
                _audit_emit(self.audit, "tool_error", clip.trace_id, {
                    "event": "clip_missing",
                    "tool_name": "clip_spool",
                    "error_type": "bad_response",
                    "error": "clip_missing",
                    **tags,
                })
                metric_count("sentinel.pipeline.failed", 1, {"reason": "clip_missing"})
                metric_count("sentinel.tool.error", 1, {"tool": "clip_spool", "error_type": "clip_missing", **self.gameday.tags()})
                return

            if self.gameday.active("long_running_observer") and self.cfg.gameday_force:
                time.sleep((self.cfg.slo_observer_ms + 700) / 1000.0)

            with span(
                "sentinel.stage.observer",
                tags=tags,
                dd_trace_id=clip.dd_trace_id,
                dd_parent_id=clip.dd_parent_id,
            ) as s:

                dd_trace_id_out = int(getattr(s, "trace_id", clip.dd_trace_id) or clip.dd_trace_id) if s else clip.dd_trace_id
                dd_parent_id_out = int(getattr(s, "span_id", clip.dd_parent_id) or clip.dd_parent_id) if s else clip.dd_parent_id

                if self.model is None:
                    out = {
                        "summary": "Stub observation: camera view uncertain.",
                        "signals": {
                            "people_present": "uncertain",
                            "people_count": "uncertain",
                            "walkway_violation": "uncertain",
                            "restricted_area_entry": "uncertain",
                            "machine_operating": "uncertain",
                            "panel_open": "uncertain",
                            "guard_open": "uncertain",
                            "unsafe_proximity_to_machine": "uncertain",
                            "uncertainty": "high",
                            "confidence_note": "USE_GEMINI=false",
                        },
                    }
                    parse_ok = True
                    metric_count("sentinel.llm.calls", 1, {"agent": "observer", "model": "stub", **self.gameday.tags()})
                else:
                    with open(clip.clip_path, "rb") as f:
                        video_bytes = f.read()

                    if len(video_bytes) < 1024:
                        status = "error"
                        _audit_emit(self.audit, "tool_error", clip.trace_id, {
                            "event": "video_too_small",
                            "tool_name": "video_read",
                            "error_type": "bad_response",
                            "error": "video_too_small",
                            **tags,
                        })
                        metric_count("sentinel.pipeline.failed", 1, {"reason": "video_too_small"})
                        metric_count("sentinel.tool.error", 1, {"tool": "video_read", "error_type": "video_too_small", **self.gameday.tags()})
                        return

                    llm_t0 = time.time()
                    prompt = SECURITY_OBSERVER_PROMPT
                    input_tokens = estimate_tokens(prompt)

                    with llm_span(model=self.cfg.gemini_observer_model, name="observer_video", tags=tags):
                        resp = self.model.generate_content(
                            [prompt, Part.from_data(data=video_bytes, mime_type="video/mp4")],
                            generation_config={"temperature": 0.0, "max_output_tokens": 2500},
                        )

                    raw = resp.text or ""
                    out, parse_ok = _parse_json(raw)
                    llm_latency_ms = int((time.time() - llm_t0) * 1000)

                    output_tokens = estimate_tokens(raw)
                    tc = estimate_cost(input_tokens, output_tokens, self.cfg.cost_per_1k_input, self.cfg.cost_per_1k_output)

                    metric_count("sentinel.llm.calls", 1, {"agent": "observer", "model": self.cfg.gemini_observer_model, **self.gameday.tags()})
                    metric_dist("sentinel.llm.latency_ms", llm_latency_ms, {"agent": "observer", "model": self.cfg.gemini_observer_model, **self.gameday.tags()})
                    metric_count("sentinel.llm.parse_ok", 1 if parse_ok else 0, {"agent": "observer", **self.gameday.tags()})
                    metric_count("sentinel.llm.parse_fail", 0 if parse_ok else 1, {"agent": "observer", **self.gameday.tags()})
                    metric_dist("sentinel.llm.tokens.total", tc.total_tokens, {"agent": "observer", **self.gameday.tags()})
                    metric_dist("sentinel.llm.cost.usd", tc.total_cost, {"agent": "observer", **self.gameday.tags()})

                    llm_annotate_io(
                        input_messages=[{"role": "system", "content": "SECURITY_OBSERVER_PROMPT"}, {"role": "user", "content": "video/mp4"}],
                        output_messages=[{"role": "assistant", "content": raw[:2000]}],
                        metadata={"agent": "observer", "camera_id": clip.camera_id, "clip_index": clip.clip_index, "scenario": self.gameday.status().scenario},
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

                    _audit_emit(self.audit, "health", clip.trace_id, {
                        "event": "llm_call",
                        "agent": "observer",
                        "model": self.cfg.gemini_observer_model,
                        "latency_ms": llm_latency_ms,
                        "parse_ok": parse_ok,
                        "input_tokens": tc.input_tokens,
                        "output_tokens": tc.output_tokens,
                        "total_tokens": tc.total_tokens,
                        "cost_usd": tc.total_cost,
                        **self.gameday.tags(),
                    })

                obs = ObservationEvent(
                    trace_id=clip.trace_id,
                    dd_trace_id=dd_trace_id_out,
                    dd_parent_id=dd_parent_id_out,
                    clip_id=clip.clip_id,
                    camera_id=clip.camera_id,
                    clip_index=clip.clip_index,
                    ts=datetime.now(timezone.utc),
                    summary=str(out.get("summary", "") or "").strip(),
                    signals=out.get("signals", {}) if isinstance(out.get("signals"), dict) else {},
                    model={"name": self.cfg.gemini_observer_model, "latency_ms": int((time.time() - t0) * 1000)},
                )

                self.state.mark(obs.trace_id, "observation")
                _audit_emit(self.audit, "observation", obs.trace_id, obs.model_dump(mode="json"))
                self.bus.publish(TOPIC_OBSERVATIONS, obs.model_dump(mode="json"))

        except Exception as e:
            status = "error"
            parse_ok = False
            _audit_emit(self.audit, "tool_error", clip.trace_id, {
                "event": "observer_exception",
                "tool_name": "observer",
                "error_type": "dependency",
                "error": str(e),
                **tags,
            })
            metric_count("sentinel.pipeline.failed", 1, {"reason": "observer_exception"})
            metric_count("sentinel.stage.error", 1, {"stage": "observer", **self.gameday.tags()})
            log.exception("observer.handle_clip_failed", extra={"trace_id": clip.trace_id})

        finally:
            self.state.end_stage(stage_key)
            elapsed_ms = int((time.time() - t0) * 1000)

            _audit_emit(self.audit, "stage", clip.trace_id, {
                "event": "stage_end",
                "stage": "observer",
                "status": status,
                "latency_ms": elapsed_ms,
                "parse_ok": parse_ok,
                **self.gameday.tags(),
            })

            metric_dist("sentinel.stage.latency_ms", elapsed_ms, {"stage": "observer", **self.gameday.tags()})
            if status != "ok":
                metric_count("sentinel.stage.error", 1, {"stage": "observer", **self.gameday.tags()})

    def run(self) -> None:
        while True:
            msg = self.bus.consume(TOPIC_CLIPS, timeout_s=1.0)
            if msg is None:
                continue
            try:
                self.handle_clip(msg)
            except Exception as e:
                log.exception("observer.loop_error", extra={"error": str(e)})
