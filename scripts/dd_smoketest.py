#!/usr/bin/env python3
import os
import time
from datadog import DogStatsd

def main():
    host = os.getenv("DD_AGENT_HOST", "127.0.0.1")
    port = int(os.getenv("DD_DOGSTATSD_PORT", "8125"))

    service = os.getenv("DD_SERVICE", "sentinelops")
    env = os.getenv("DD_ENV", "dev")
    version = os.getenv("DD_VERSION", "0.1.0")

    statsd = DogStatsd(host=host, port=port)

    tags = [f"service:{service}", f"env:{env}", f"version:{version}", "smoketest:true"]

    statsd.increment("sentinel.smoketest.metric", 1, tags=tags)
    statsd.gauge("sentinel.smoketest.gauge", 123, tags=tags)

    print(f"[smoketest] ✅ sent metrics to DogStatsD {host}:{port} tags={tags}")

    try:
        from ddtrace import tracer
        with tracer.trace("sentinel.smoketest.trace", service=service) as span:
            span.set_tag("env", env)
            span.set_tag("version", version)
            span.set_tag("smoketest", "true")
            time.sleep(0.1)
        print("[smoketest] ✅ sent trace via ddtrace")
    except Exception as e:
        print("[smoketest] ⚠️ trace skipped:", e)

if __name__ == "__main__":
    main()
