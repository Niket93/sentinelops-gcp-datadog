#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Dict, Any

import requests


def env(name: str, default: str = "") -> str:
    return (os.getenv(name, default) or "").strip()


def api_base(site: str) -> str:
    return f"https://api.{site}"


def headers(api_key: str, app_key: str) -> Dict[str, str]:
    return {
        "DD-API-KEY": api_key,
        "DD-APPLICATION-KEY": app_key,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Export Datadog monitors/dashboards/SLOs (by tag filters).")
    ap.add_argument("--site", default=env("DD_SITE", "datadoghq.com"))
    ap.add_argument("--api-key", default=env("DD_API_KEY"))
    ap.add_argument("--app-key", default=env("DD_APP_KEY") or env("DD_APPLICATION_KEY") or env("DATADOG_APP_KEY"))
    ap.add_argument("--out-dir", default="datadog/exported")
    ap.add_argument("--tag", default="project:sentinelops")
    args = ap.parse_args()

    if not args.api_key or not args.app_key:
        raise SystemExit("Missing DD_API_KEY or DD_APP_KEY")

    base = api_base(args.site)
    h = headers(args.api_key, args.app_key)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    r = requests.get(f"{base}/api/v1/monitor", headers=h, timeout=20)
    r.raise_for_status()
    monitors = r.json()
    filtered_monitors = [m for m in monitors if args.tag in (m.get("tags") or [])]
    (out_dir / "monitors.json").write_text(json.dumps(filtered_monitors, indent=2), encoding="utf-8")

    r = requests.get(f"{base}/api/v1/dashboard", headers=h, timeout=20)
    r.raise_for_status()
    dashboards = r.json().get("dashboards") or []
    filtered_dashboards = [d for d in dashboards if "SentinelOps" in str(d.get("title", ""))]
    (out_dir / "dashboards_list.json").write_text(json.dumps(filtered_dashboards, indent=2), encoding="utf-8")

    r = requests.get(f"{base}/api/v1/slo", headers=h, params={"limit": 100, "offset": 0}, timeout=20)
    r.raise_for_status()
    slos = r.json().get("data") or []
    filtered_slos = [s for s in slos if args.tag in (s.get("tags") or [])]
    (out_dir / "slos.json").write_text(json.dumps(filtered_slos, indent=2), encoding="utf-8")

    print(f"[export] ✅ wrote {out_dir}/monitors.json, dashboards_list.json, slos.json")


if __name__ == "__main__":
    main()
