# src/main.py
from __future__ import annotations

from .config.settings import load_settings

cfg = load_settings(".env")

try:
    import ddtrace.auto
except Exception:
    pass

import logging
import threading
import uvicorn

from .bus.bus import Bus
from .audit.buffer import AuditBuffer
from .shared.vertex import init_vertex_if_enabled

from .obs.logging import setup_logging
from .obs.datadog import init_datadog, metric_gauge
from .obs.heartbeat import HeartbeatEmitter
from .obs.pipeline_metrics import PipelineMetricsEmitter

from .gameday.controller import GameDayController
from .runtime.state import RuntimeState
from .runtime.watchdog import Watchdog

from .tools.sop_lookup import SopLookupTool
from .tools.dispatcher import DispatcherTool

from .ingest.producer import ClipProducer
from .agents.observer import ObserverAgent
from .agents.thinker import ThinkerAgent
from .agents.doer import DoerAgent
from .web.api import build_app

log = logging.getLogger("sentinelops")


def main() -> None:
    cfg = load_settings(".env")

    setup_logging()
    log.info(
        "app.starting",
        extra={"service": cfg.dd_service, "env": cfg.dd_env, "version": cfg.dd_version},
    )

    init_datadog(cfg)
    init_vertex_if_enabled(cfg)

    metric_gauge(
        "sentinel.app.info",
        1.0,
        tags={
            "observer_model": cfg.gemini_observer_model,
            "thinker_model": cfg.gemini_thinker_model,
            "llmobs_enabled": str(cfg.dd_llmobs_enabled).lower(),
            "llmobs_agentless": str(cfg.dd_llmobs_agentless).lower(),
        },
    )

    bus = Bus()
    audit = AuditBuffer(max_events=4000)

    gameday = GameDayController(cfg, audit=audit)
    state = RuntimeState()

    hb = HeartbeatEmitter(interval_s=10.0, tags={"component": "heartbeat"})
    hb.start()

    pm = PipelineMetricsEmitter(bus=bus, interval_s=5.0, tags={"component": "pipeline"})
    pm.start()

    watchdog = Watchdog(cfg, audit=audit, state=state)
    threading.Thread(target=watchdog.run, daemon=True).start()

    sop_tool = SopLookupTool()
    dispatcher = DispatcherTool()

    producer = ClipProducer(cfg, bus=bus, audit=audit, state=state)
    observer = ObserverAgent(cfg, bus=bus, audit=audit, state=state, gameday=gameday)
    thinker = ThinkerAgent(cfg, bus=bus, audit=audit, state=state, gameday=gameday, sop_tool=sop_tool)
    doer = DoerAgent(cfg, bus=bus, audit=audit, state=state, gameday=gameday, dispatcher=dispatcher)

    threading.Thread(target=observer.run, daemon=True).start()
    threading.Thread(target=thinker.run, daemon=True).start()
    threading.Thread(target=doer.run, daemon=True).start()

    app = build_app(
        cfg,
        bus=bus,
        audit=audit,
        producer=producer,
        gameday=gameday,
        state=state,
        dispatcher=dispatcher,
    )

    log.info("app.ui_ready", extra={"url": f"http://{cfg.chat_host}:{cfg.chat_port}/ui"})
    uvicorn.run(app, host=cfg.chat_host, port=cfg.chat_port, access_log=False)


if __name__ == "__main__":
    main()