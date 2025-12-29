# src/obs/datadog.py
from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from typing import Any, Dict, Optional

from ..config.settings import Settings
from .dd_events import DatadogEventClient

# NEW: v2 API + incident/case clients
from .dd_api import DatadogAPIv2
from .dd_incidents import DatadogIncidentClient
from .dd_cases import DatadogCaseClient

log = logging.getLogger("sentinelops")

_DD_OK = False
_STATS = None
_LLMOBS = None
_DD_EVENTS: DatadogEventClient | None = None

# NEW: Datadog v2 API + Incident + Case clients
_DD_APIv2: DatadogAPIv2 | None = None
_INCIDENTS: DatadogIncidentClient | None = None
_CASES: DatadogCaseClient | None = None


def _safe_tags(tags: Dict[str, Any]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for k, v in (tags or {}).items():
        if v is None:
            continue
        out[str(k)] = str(v)
    return out


def init_datadog(cfg: Settings) -> None:
    global _DD_OK, _STATS, _LLMOBS, _DD_EVENTS
    global _DD_APIv2, _INCIDENTS, _CASES

    if not cfg.dd_enabled:
        log.warning("dd.disabled", extra={"DD_ENABLED": False})
        _DD_OK = False
        _STATS = None
        _LLMOBS = None
        _DD_EVENTS = None
        _DD_APIv2 = None
        _INCIDENTS = None
        _CASES = None
        return

    # ddtrace patching
    try:
        import ddtrace
        from ddtrace import patch

        patch(fastapi=True, vertexai=True)
        _DD_OK = True
    except Exception as e:
        log.warning("dd.ddtrace_unavailable", extra={"error": str(e)})
        _DD_OK = False

    # DogStatsD
    try:
        from datadog import DogStatsd

        base_tags = [
            f"service:{cfg.dd_service}",
            f"env:{cfg.dd_env}",
            f"version:{cfg.dd_version}",
        ]

        _STATS = DogStatsd(
            host=cfg.dd_agent_host,
            port=cfg.dd_dogstatsd_port,
            namespace="",
            constant_tags=base_tags,
        )
    except Exception as e:
        _STATS = None
        log.warning("dd.dogstatsd_unavailable", extra={"error": str(e)})

    # Events API client (v1 events endpoint)
    try:
        _DD_EVENTS = DatadogEventClient(api_key=cfg.dd_api_key, site=cfg.dd_site)
    except Exception as e:
        _DD_EVENTS = None
        log.warning("dd.events_client_failed", extra={"error": str(e)})

    # NEW: v2 Incident + Case clients (requires DD_API_KEY + DD_APP_KEY)
    try:
        _DD_APIv2 = DatadogAPIv2(api_key=cfg.dd_api_key, app_key=cfg.dd_app_key, site=cfg.dd_site)
        _INCIDENTS = DatadogIncidentClient(_DD_APIv2) if _DD_APIv2 and _DD_APIv2.enabled else None
        _CASES = DatadogCaseClient(_DD_APIv2) if _DD_APIv2 and _DD_APIv2.enabled else None
    except Exception as e:
        _DD_APIv2 = None
        _INCIDENTS = None
        _CASES = None
        log.warning("dd.v2_clients_failed", extra={"error": str(e)})

    # LLMObs
    if _DD_OK and cfg.dd_llmobs_enabled:
        try:
            from ddtrace.llmobs import LLMObs

            kwargs = {
                "ml_app": cfg.dd_llmobs_ml_app or cfg.dd_service,
                "integrations_enabled": True,
            }
            if cfg.dd_llmobs_agentless and cfg.dd_api_key:
                kwargs.update(
                    {
                        "api_key": cfg.dd_api_key,
                        "site": cfg.dd_site,
                        "agentless_enabled": True,
                    }
                )
            _LLMOBS = LLMObs
            _LLMOBS.enable(**kwargs)
            log.info("dd.llmobs_enabled", extra={"ml_app": cfg.dd_llmobs_ml_app})
        except Exception as e:
            _LLMOBS = None
            log.warning("dd.llmobs_enable_failed", extra={"error": str(e)})
    else:
        _LLMOBS = None

    log.info(
        "dd.init_complete",
        extra={
            "ddtrace": _DD_OK,
            "dogstatsd": bool(_STATS),
            "llmobs": bool(_LLMOBS),
            "events_api": bool(_DD_EVENTS and _DD_EVENTS.enabled),
            "incidents_api": bool(_INCIDENTS and _DD_APIv2 and _DD_APIv2.enabled),
            "cases_api": bool(_CASES and _DD_APIv2 and _DD_APIv2.enabled),
            "agent_host": cfg.dd_agent_host,
            "trace_port": cfg.dd_trace_agent_port,
            "dogstatsd_port": cfg.dd_dogstatsd_port,
            "site": cfg.dd_site,
        },
    )


def dd_enabled() -> bool:
    return bool(_DD_OK)


def metric_count(name: str, value: int = 1, tags: Dict[str, Any] | None = None) -> None:
    if _STATS is None:
        return
    _STATS.increment(name, value, tags=[f"{k}:{v}" for k, v in _safe_tags(tags or {}).items()])


def metric_gauge(name: str, value: float, tags: Dict[str, Any] | None = None) -> None:
    if _STATS is None:
        return
    _STATS.gauge(name, value, tags=[f"{k}:{v}" for k, v in _safe_tags(tags or {}).items()])


def metric_hist(name: str, value: float, tags: Dict[str, Any] | None = None) -> None:
    """
    histogram is fine for avg/max/count, but NOT reliable for p95/p99 queries in Datadog dashboards.
    Keep this for legacy use, but prefer metric_dist for latency percentiles.
    """
    if _STATS is None:
        return
    _STATS.histogram(name, value, tags=[f"{k}:{v}" for k, v in _safe_tags(tags or {}).items()])


def metric_dist(name: str, value: float, tags: Dict[str, Any] | None = None) -> None:
    """
    distribution is required for p50/p95/p99 queries on dashboards.
    """
    if _STATS is None:
        return
    try:
        _STATS.distribution(name, value, tags=[f"{k}:{v}" for k, v in _safe_tags(tags or {}).items()])
    except Exception:
        _STATS.histogram(name, value, tags=[f"{k}:{v}" for k, v in _safe_tags(tags or {}).items()])


def dd_event(title: str, text: str, tags: Dict[str, Any] | None = None, alert_type: str = "info") -> None:
    if _DD_EVENTS is None or not _DD_EVENTS.enabled:
        return
    try:
        _DD_EVENTS.send_event(title=title, text=text, tags=tags, alert_type=alert_type)
    except Exception:
        return


# NEW: Incident + Case helpers
def create_incident(
    title: str,
    summary: str,
    severity: str = "SEV-2",
    tags: Dict[str, Any] | None = None,
    customer_impact: str = "Unknown",
    metadata: Dict[str, Any] | None = None,
) -> Optional[Dict[str, Any]]:
    if _INCIDENTS is None:
        return None
    tag_list = [f"{k}:{v}" for k, v in _safe_tags(tags or {}).items()]
    try:
        return _INCIDENTS.create_incident(
            title=title,
            summary=summary,
            severity=severity,
            tags=tag_list,
            customer_impact=customer_impact,
            metadata=metadata or {},
        )
    except Exception:
        return None


def create_case(
    title: str,
    description: str,
    tags: Dict[str, Any] | None = None,
    case_type: str = "STANDARD",
    priority: str = "NOT_DEFINED",
    project_id: str | None = None,
) -> Optional[Dict[str, Any]]:
    if _CASES is None:
        return None
    tag_list = [f"{k}:{v}" for k, v in _safe_tags(tags or {}).items()]
    try:
        return _CASES.create_case(
            title=title,
            description=description,
            tags=tag_list,
            case_type=case_type,
            priority=priority,
            project_id=project_id,
        )
    except Exception:
        return None


@contextmanager
def span(
    name: str,
    tags: Dict[str, Any] | None = None,
    dd_trace_id: int | None = None,
    dd_parent_id: int | None = None,
):
    if not _DD_OK:
        try:
            yield None
        finally:
            return

    s = None
    t0 = time.time()
    try:
        from ddtrace import tracer
        from ddtrace.trace import Context

        child_of = None
        if dd_trace_id and dd_parent_id:
            child_of = Context(trace_id=int(dd_trace_id), span_id=int(dd_parent_id))

        s = tracer.start_span(name, child_of=child_of)

        for k, v in _safe_tags(tags or {}).items():
            s.set_tag(k, v)

        yield s

    finally:
        try:
            if s is not None:
                s.set_tag("duration_ms", int((time.time() - t0) * 1000))
        except Exception:
            pass
        try:
            if s is not None:
                s.finish()
        except Exception:
            pass


@contextmanager
def llm_span(model: str, name: str, tags: Dict[str, Any] | None = None):
    if _LLMOBS is None:
        with span(f"llm.{name}", tags=tags):
            try:
                yield
            finally:
                return

    ctx = None
    try:
        ctx = _LLMOBS.llm(model=model, name=name)
        ctx.__enter__()

        if tags:
            try:
                _LLMOBS.annotate(tags=_safe_tags(tags))
            except Exception:
                pass

        yield

    except Exception:
        with span(f"llm.{name}", tags=tags):
            yield

    finally:
        try:
            if ctx is not None:
                ctx.__exit__(None, None, None)
        except Exception:
            pass


def llm_annotate_io(
    input_messages: Any | None = None,
    output_messages: Any | None = None,
    metadata: Dict[str, Any] | None = None,
    metrics: Dict[str, float] | None = None,
    tags: Dict[str, Any] | None = None,
) -> None:
    if _LLMOBS is None:
        return
    try:
        _LLMOBS.annotate(
            input_data=input_messages,
            output_data=output_messages,
            metadata=metadata or {},
            metrics=metrics or {},
            tags=_safe_tags(tags or {}),
        )
    except Exception:
        return