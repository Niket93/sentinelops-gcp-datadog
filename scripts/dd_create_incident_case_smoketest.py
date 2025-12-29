import os
from dotenv import load_dotenv
from src.obs.dd_api import DatadogAPIv2
from src.obs.dd_incidents import DatadogIncidentClient
from src.obs.dd_cases import DatadogCaseClient

load_dotenv(".env")

api = DatadogAPIv2(
    api_key=os.getenv("DD_API_KEY",""),
    app_key=os.getenv("DD_APP_KEY",""),
    site=os.getenv("DD_SITE","datadoghq.com"),
)

inc = DatadogIncidentClient(api)
case = DatadogCaseClient(api)

print("Creating incident...")
print(inc.create_incident(
    title="SentinelOps SmokeTest Incident",
    summary="This is a smoke test incident created by the hackathon demo.",
    severity="SEV-4",
    tags=["team:hackathon","project:sentinelops","smoketest:true"],
))

print("Creating case...")
try:
    print(case.create_case(
        title="SentinelOps SmokeTest Case",
        description="This is a smoke test case created by the hackathon demo.",
        tags=["team:hackathon","project:sentinelops","smoketest:true"],
    ))
except Exception as e:
    print(f"Failed to create case (known API ambiguity): {e}")

print("Done!")
