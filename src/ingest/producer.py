# src/ingest/producer.py
from __future__ import annotations

import logging
import os
import shutil
import threading
import time
from typing import Optional

from ..config.settings import Settings
from ..shared.events import ClipEvent
from ..bus.bus import Bus, TOPIC_CLIPS
from ..audit.buffer import AuditBuffer
from ..runtime.state import RuntimeState
from ..obs.datadog import span, metric_count, metric_dist
from .clipper import VideoClipper

log = logging.getLogger("sentinelops.producer")


class ClipProducer:
    def __init__(self, cfg: Settings, bus: Bus, audit: AuditBuffer, state: RuntimeState) -> None:
        self.cfg = cfg
        self.bus = bus
        self.audit = audit
        self.state = state

        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._janitor_thread: Optional[threading.Thread] = None
        self._running = False

        self.spool_dir = getattr(cfg, "clip_spool_dir", "./tmp/clips")
        os.makedirs(self.spool_dir, exist_ok=True)

        self.clip_ttl_s = 5 * 60
        self.janitor_interval_s = 30

    @property
    def running(self) -> bool:
        return self._running

    def start(self) -> None:
        if self._running:
            return
        self._stop.clear()

        if self._janitor_thread is None or not self._janitor_thread.is_alive():
            self._janitor_thread = threading.Thread(target=self._janitor_loop, daemon=True)
            self._janitor_thread.start()

        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        log.info("producer.started", extra={"spool_dir": self.spool_dir})

    def stop(self) -> None:
        self._stop.set()
        log.info("producer.stop_requested")

    def _janitor_loop(self) -> None:
        while not self._stop.is_set():
            try:
                deleted = self._delete_old_spooled_clips()
                if deleted:
                    log.info("janitor.deleted_old_clips", extra={"deleted": deleted})
            except Exception:
                log.exception("janitor.error")

            for _ in range(int(self.janitor_interval_s * 10)):
                if self._stop.is_set():
                    break
                time.sleep(0.1)

    def _delete_old_spooled_clips(self) -> int:
        now = time.time()
        cutoff = now - self.clip_ttl_s
        deleted = 0
        try:
            names = os.listdir(self.spool_dir)
        except FileNotFoundError:
            return 0

        for name in names:
            if not name.endswith(".mp4"):
                continue

            path = os.path.join(self.spool_dir, name)
            try:
                if not os.path.isfile(path):
                    continue
                st = os.stat(path)
            except FileNotFoundError:
                continue

            if st.st_mtime < cutoff:
                try:
                    os.remove(path)
                    deleted += 1
                except FileNotFoundError:
                    pass
                except PermissionError:
                    continue

        return deleted

    def _run(self) -> None:
        self._running = True
        try:
            clipper = VideoClipper(self.cfg.clip_seconds, self.cfg.sample_fps)
            camera_id = "cam-security-1"

            for clip in clipper.iter_clips(self.cfg.security_video_path):
                if self._stop.is_set():
                    break

                t0 = time.time()
                base_tags = {
                    "stage": "producer",
                    "use_case": "security",
                    "camera_id": camera_id,
                    "clip_index": clip.clip_index,
                }

                with span("sentinel.stage.producer", tags=base_tags) as s:
                    dd_trace_id = int(getattr(s, "trace_id", 0) or 0) if s else 0
                    dd_parent_id = int(getattr(s, "span_id", 0) or 0) if s else 0

                    evt = ClipEvent(
                        camera_id=camera_id,
                        clip_index=clip.clip_index,
                        clip_start_ts=clip.start_ts,
                        clip_end_ts=clip.end_ts,
                        clip_path="__will_set__",
                        dd_trace_id=dd_trace_id,
                        dd_parent_id=dd_parent_id,
                    )

                    durable_path = os.path.join(self.spool_dir, f"{evt.trace_id}_{clip.clip_index:06d}.mp4")

                    shutil.move(clip.path, durable_path)
                    evt.clip_path = durable_path

                    self.state.mark(evt.trace_id, "clip")

                    latency_ms = int((time.time() - t0) * 1000)

                    self.audit.add("stage", evt.trace_id, {
                        "event": "stage_end",
                        "stage": "producer",
                        "status": "ok",
                        "latency_ms": latency_ms,
                        "dd_trace_id": dd_trace_id,
                        "dd_parent_id": dd_parent_id,
                    })
                    self.audit.add("clip", evt.trace_id, evt.model_dump(mode="json"))

                    metric_count("sentinel.throughput.clips", 1, {"use_case": "security"})
                    metric_dist("sentinel.stage.latency_ms", latency_ms, {"stage": "producer"})

                    self.bus.publish(TOPIC_CLIPS, evt.model_dump(mode="json"))

                    log.info(
                        "producer.clip_published",
                        extra={
                            "event": "clip_published",
                            "trace_id": evt.trace_id,
                            "clip_index": evt.clip_index,
                            "camera_id": evt.camera_id,
                            "path": durable_path,
                            "dd_trace_id": dd_trace_id,
                            "dd_parent_id": dd_parent_id,
                        },
                    )

        except Exception:
            log.exception("producer.loop_failed")
        finally:
            self._running = False
            log.info("producer.stopped")
