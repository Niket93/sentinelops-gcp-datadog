#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=Path(".env"))
except Exception:
    pass

DEFAULT_MONITORS_DIR = "datadog/monitors"
DEFAULT_DASHBOARDS_DIR = "datadog/dashboards"
DEFAULT_SLOS_DIR = "datadog/slos"


def die(msg: str, code: int = 2) -> None:
    print(f"[bootstrap] ERROR: {msg}", file=sys.stderr)
    raise SystemExit(code)


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


def load_json_files(dir_path: str) -> List[Tuple[str, Dict[str, Any]]]:
    p = Path(dir_path)
    if not p.exists():
        return []
    out: List[Tuple[str, Dict[str, Any]]] = []
    for fp in sorted(p.glob("*.json")):
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
            out.append((str(fp), data))
        except Exception as e:
            die(f"Failed parsing JSON {fp}: {e}")
    return out


def monitor_search(base: str, h: Dict[str, str], name: str) -> Optional[int]:
    try:
        r = requests.get(
            f"{base}/api/v1/monitor/search",
            headers=h,
            params={"query": f'name:"{name}"', "per_page": 50, "page": 0},
            timeout=10,
        )
        if r.status_code >= 300:
            return None
        js = r.json()
        for m in (js.get("monitors") or []):
            if str(m.get("name", "")).strip() == name:
                return int(m.get("id"))
        return None
    except Exception:
        return None


def monitor_list_find(base: str, h: Dict[str, str], name: str) -> Optional[int]:
    r = requests.get(f"{base}/api/v1/monitor", headers=h, timeout=20)
    r.raise_for_status()
    for m in r.json():
        if str(m.get("name", "")).strip() == name:
            return int(m.get("id"))
    return None


def upsert_monitor(base: str, h: Dict[str, str], monitor_def: Dict[str, Any]) -> int:
    name = str(monitor_def.get("name", "")).strip()
    if not name:
        die("Monitor JSON missing 'name'")

    mid = monitor_search(base, h, name)
    if mid is None:
        mid = monitor_list_find(base, h, name)

    if mid is None:
        r = requests.post(f"{base}/api/v1/monitor", headers=h, json=monitor_def, timeout=20)
        if r.status_code >= 300:
            die(f"Create monitor failed ({r.status_code}): {r.text[:400]}")
        created = r.json()
        return int(created["id"])

    r = requests.put(f"{base}/api/v1/monitor/{mid}", headers=h, json=monitor_def, timeout=20)
    if r.status_code >= 300:
        die(f"Update monitor {mid} failed ({r.status_code}): {r.text[:400]}")
    return mid


def dashboard_list_find(base: str, h: Dict[str, str], title: str) -> Optional[str]:
    r = requests.get(f"{base}/api/v1/dashboard", headers=h, timeout=20)
    r.raise_for_status()
    js = r.json()
    for d in (js.get("dashboards") or []):
        if str(d.get("title", "")).strip() == title:
            return str(d.get("id"))
    return None


def upsert_dashboard(base: str, h: Dict[str, str], dash_def: Dict[str, Any]) -> str:
    title = str(dash_def.get("title", "")).strip()
    if not title:
        die("Dashboard JSON missing 'title'")

    did = dashboard_list_find(base, h, title)
    if did is None:
        r = requests.post(f"{base}/api/v1/dashboard", headers=h, json=dash_def, timeout=20)
        if r.status_code >= 300:
            die(f"Create dashboard failed ({r.status_code}): {r.text[:400]}")
        created = r.json()
        return str(created["id"])

    r = requests.put(f"{base}/api/v1/dashboard/{did}", headers=h, json=dash_def, timeout=20)
    if r.status_code >= 300:
        die(f"Update dashboard {did} failed ({r.status_code}): {r.text[:400]}")
    return did


def slo_search(base: str, h: Dict[str, str], name: str) -> Optional[str]:
    try:
        r = requests.get(
            f"{base}/api/v1/slo/search",
            headers=h,
            params={"query": name, "per_page": 50, "page": 0},
            timeout=15,
        )
        if r.status_code >= 300:
            return None
        js = r.json()
        for s in (js.get("data") or []):
            if str(s.get("name", "")).strip() == name:
                return str(s.get("id"))
        return None
    except Exception:
        return None


def slo_list_find(base: str, h: Dict[str, str], name: str) -> Optional[str]:
    offset = 0
    limit = 100
    while True:
        r = requests.get(f"{base}/api/v1/slo", headers=h, params={"offset": offset, "limit": limit}, timeout=20)
        r.raise_for_status()
        js = r.json()
        data = js.get("data") or []
        for s in data:
            if str(s.get("name", "")).strip() == name:
                return str(s.get("id"))
        if len(data) < limit:
            return None
        offset += limit


def _extract_slo_id(js: Dict[str, Any]) -> str:
    data = js.get("data")
    if isinstance(data, dict) and data.get("id"):
        return str(data["id"])
    if isinstance(data, list) and data and isinstance(data[0], dict) and data[0].get("id"):
        return str(data[0]["id"])
    raise ValueError(f"Unexpected SLO response shape: {str(js)[:300]}")


def upsert_slo(base: str, h: Dict[str, str], slo_def: Dict[str, Any]) -> str:
    name = str(slo_def.get("name", "")).strip()
    if not name:
        die("SLO JSON missing 'name'")

    sid = slo_search(base, h, name)
    if sid is None:
        sid = slo_list_find(base, h, name)

    if sid is None:
        r = requests.post(f"{base}/api/v1/slo", headers=h, json=slo_def, timeout=20)
        if r.status_code >= 300:
            die(f"Create SLO failed ({r.status_code}): {r.text[:400]}")
        created = r.json()
        return _extract_slo_id(created)

    r = requests.put(f"{base}/api/v1/slo/{sid}", headers=h, json=slo_def, timeout=20)
    if r.status_code >= 300:
        die(f"Update SLO {sid} failed ({r.status_code}): {r.text[:400]}")
    return sid


def main() -> None:
    ap = argparse.ArgumentParser(description="Create/Update Datadog monitors, dashboards, and SLOs from JSON.")
    ap.add_argument("--site", default=env("DD_SITE", "datadoghq.com"))
    ap.add_argument("--api-key", default=env("DD_API_KEY"))
    ap.add_argument("--app-key", default=env("DD_APP_KEY") or env("DD_APPLICATION_KEY") or env("DATADOG_APP_KEY"))
    ap.add_argument("--monitors-dir", default=DEFAULT_MONITORS_DIR)
    ap.add_argument("--dashboards-dir", default=DEFAULT_DASHBOARDS_DIR)
    ap.add_argument("--slos-dir", default=DEFAULT_SLOS_DIR)
    args = ap.parse_args()

    if not args.api_key:
        die("Missing DD_API_KEY (make sure .env is present or exported)")
    if not args.app_key:
        die("Missing DD_APP_KEY (Datadog Application Key)")

    base = api_base(args.site)
    h = headers(args.api_key, args.app_key)

    print(f"[bootstrap] site={args.site} base={base}")

    monitors = load_json_files(args.monitors_dir)
    dashboards = load_json_files(args.dashboards_dir)
    slos = load_json_files(args.slos_dir)

    created_monitors: List[Tuple[str, int]] = []
    created_dashboards: List[Tuple[str, str]] = []
    created_slos: List[Tuple[str, str]] = []

    for path, m in monitors:
        mid = upsert_monitor(base, h, m)
        created_monitors.append((path, mid))
        print(f"[bootstrap] ✅ monitor upserted id={mid} file={path}")

    for path, d in dashboards:
        did = upsert_dashboard(base, h, d)
        created_dashboards.append((path, did))
        print(f"[bootstrap] ✅ dashboard upserted id={did} file={path}")

    for path, s in slos:
        sid = upsert_slo(base, h, s)
        created_slos.append((path, sid))
        print(f"[bootstrap] ✅ slo upserted id={sid} file={path}")

    print("\n[bootstrap] Done.")
    if created_monitors:
        print("[bootstrap] Monitors:")
        for p, mid in created_monitors:
            print(f"  - {mid}  ({p})")
    if created_dashboards:
        print("[bootstrap] Dashboards:")
        for p, did in created_dashboards:
            print(f"  - {did}  ({p})")
    if created_slos:
        print("[bootstrap] SLOs:")
        for p, sid in created_slos:
            print(f"  - {sid}  ({p})")


if __name__ == "__main__":
    main()