#!/usr/bin/env bash
set -euo pipefail

# Load .env
set -a
source .env
set +a

mkdir -p logs

echo "[demo] ✅ Datadog smoketest..."
python3 scripts/dd_smoketest.py || true

# echo "[demo] ✅ Bootstrapping Datadog monitors/dashboard/SLO..."
# python3 scripts/datadog_bootstrap.py

echo "[demo] ✅ Starting SentinelOps app..."
python3 -m src.main 2>&1 | tee logs/sentinelops.jsonl &
APP_PID=$!

cleanup() {
  echo "[demo] stopping app pid=$APP_PID"
  kill "$APP_PID" >/dev/null 2>&1 || true
}
trap cleanup EXIT

# Wait until the app is actually ready
echo "[demo] ⏳ Waiting for /healthz..."
for i in {1..30}; do
  if curl -sf "http://${CHAT_HOST}:${CHAT_PORT}/healthz" >/dev/null; then
    echo "[demo] ✅ App is healthy"
    break
  fi
  sleep 0.5
done

echo "[demo] ✅ Creating Incident + Case smoketest..."
python3 scripts/dd_create_incident_case_smoketest.py

# sleep 3

# echo "[demo] ✅ Running traffic generator..."
# python3 scripts/traffic_generator.py --url "http://${CHAT_HOST}:${CHAT_PORT}" --baseline 30 --dispatcher 25 --injection 10 --latency 25

echo "[demo] ✅ Demo Complete"
echo "[demo] UI: http://${CHAT_HOST}:${CHAT_PORT}/ui"
