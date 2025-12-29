# src/config/settings.py
from __future__ import annotations

import os
from dataclasses import dataclass
from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    chat_host: str
    chat_port: int

    security_video_path: str
    clip_seconds: float
    sample_fps: int

    use_gemini: bool
    gcp_project: str
    gcp_region: str
    gemini_observer_model: str
    gemini_thinker_model: str

    dd_enabled: bool
    dd_env: str
    dd_service: str
    dd_version: str
    dd_agent_host: str
    dd_trace_agent_port: int
    dd_dogstatsd_port: int
    dd_site: str
    dd_api_key: str
    dd_llmobs_enabled: bool
    dd_llmobs_agentless: bool
    dd_llmobs_ml_app: str
    dd_app_key: str

    gameday_enabled: bool
    gameday_scenario: str
    gameday_force: bool

    slo_observer_ms: int
    slo_thinker_ms: int
    slo_doer_ms: int
    slo_dispatcher_ms: int
    slo_pipeline_e2e_ms: int

    cost_per_1k_input: float
    cost_per_1k_output: float


def _req(name: str) -> str:
    v = os.getenv(name, "").strip()
    if not v:
        raise RuntimeError(f"Missing required env var: {name}")
    return v


def _opt(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _opt_bool(name: str, default: bool = False) -> bool:
    v = os.getenv(name, str(default)).strip().lower()
    return v in {"1", "true", "yes", "y", "on"}


def _opt_int(name: str, default: int) -> int:
    try:
        return int(_opt(name, str(default)))
    except Exception:
        return int(default)


def _opt_float(name: str, default: float) -> float:
    try:
        return float(_opt(name, str(default)))
    except Exception:
        return float(default)


def load_settings(env_path: str = ".env") -> Settings:
    load_dotenv(env_path)

    use_gemini = _opt_bool("USE_GEMINI", True)

    gcp_project = _opt("GCP_PROJECT", "")
    if use_gemini and not gcp_project:
        raise RuntimeError("Missing required env var: GCP_PROJECT (required when USE_GEMINI=true)")

    return Settings(
        chat_host=_opt("CHAT_HOST", "127.0.0.1"),
        chat_port=int(_opt("CHAT_PORT", os.getenv("PORT", "8000"))),

        security_video_path=_req("SECURITY_VIDEO_PATH"),
        clip_seconds=float(_opt("CLIP_SECONDS", "2.0")),
        sample_fps=int(_opt("SAMPLE_FPS", "10")),

        use_gemini=use_gemini,
        gcp_project=gcp_project,
        gcp_region=_opt("GCP_REGION", "us-central1"),
        gemini_observer_model=_opt("GEMINI_OBSERVER_MODEL", "gemini-2.5-flash"),
        gemini_thinker_model=_opt("GEMINI_THINKER_MODEL", "gemini-2.5-pro"),

        dd_enabled=_opt_bool("DD_ENABLED", True),
        dd_env=_opt("DD_ENV", "dev"),
        dd_service=_opt("DD_SERVICE", "sentinelops"),
        dd_version=_opt("DD_VERSION", "0.1.0"),
        dd_agent_host=_opt("DD_AGENT_HOST", "127.0.0.1"),
        dd_trace_agent_port=_opt_int("DD_TRACE_AGENT_PORT", 8126),
        dd_dogstatsd_port=_opt_int("DD_DOGSTATSD_PORT", 8125),
        dd_site=_opt("DD_SITE", "datadoghq.com"),
        dd_api_key=_opt("DD_API_KEY", ""),
        dd_app_key=_opt("DD_APP_KEY", ""),
        dd_llmobs_enabled=_opt_bool("DD_LLMOBS_ENABLED", True),
        dd_llmobs_agentless=_opt_bool("DD_LLMOBS_AGENTLESS_ENABLED", False),
        dd_llmobs_ml_app=_opt("DD_LLMOBS_ML_APP", "sentinelops"),

        gameday_enabled=_opt_bool("GAMEDAY_ENABLED", True),
        gameday_scenario=_opt("GAMEDAY_SCENARIO", "none"),
        gameday_force=_opt_bool("GAMEDAY_FORCE", True),

        slo_observer_ms=_opt_int("SLO_OBSERVER_MS", 2500),
        slo_thinker_ms=_opt_int("SLO_THINKER_MS", 2000),
        slo_doer_ms=_opt_int("SLO_DOER_MS", 1500),
        slo_dispatcher_ms=_opt_int("SLO_DISPATCHER_MS", 1200),
        slo_pipeline_e2e_ms=_opt_int("SLO_PIPELINE_E2E_MS", 5000),

        cost_per_1k_input=_opt_float("COST_PER_1K_INPUT", 0.0005),
        cost_per_1k_output=_opt_float("COST_PER_1K_OUTPUT", 0.0015),
    )
