# src/shared/vertex.py
from __future__ import annotations

import logging
from vertexai import init as vertex_init
from vertexai.generative_models import GenerativeModel

from ..config.settings import Settings

log = logging.getLogger("sentinelops.vertex")


def init_vertex_if_enabled(cfg: Settings) -> None:
    if not cfg.use_gemini:
        log.info("vertex.disabled_stub_mode", extra={"use_gemini": False})
        return

    vertex_init(project=cfg.gcp_project, location=cfg.gcp_region)
    log.info(
        "vertex.initialized",
        extra={"project": cfg.gcp_project, "region": cfg.gcp_region},
    )


def model_if_enabled(cfg: Settings, model_name: str) -> GenerativeModel | None:
    if not cfg.use_gemini:
        return None
    return GenerativeModel(model_name)