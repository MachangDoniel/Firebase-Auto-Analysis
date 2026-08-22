"""
Daily Firebase / Google Analytics (GA4) to Gemini AI Pipeline
Fetches iOS App Analytics (events, users, sessions, versions) from Google Analytics 4
and runs automated AI analysis with Gemini.
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    DateRange,
    Dimension,
    Metric,
    RunReportRequest,
)
from google.oauth2 import service_account
from google import genai

# ==========================================
# Configuration & Environment Variables
# ==========================================
SERVICE_ACCOUNT_KEY = os.getenv("FIREBASE_KEY_PATH", str(BASE_DIR / "serviceAccountKey.json"))
GA4_PROPERTY_ID = os.getenv("GA4_PROPERTY_ID")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
LOG_FILE = BASE_DIR / "daily_analysis.log"

if not os.path.isabs(SERVICE_ACCOUNT_KEY):
    SERVICE_ACCOUNT_KEY = str(BASE_DIR / SERVICE_ACCOUNT_KEY)


def get_analytics_client():
    """Initializes Google Analytics Data API client using Service Account credentials."""
    if not os.path.exists(SERVICE_ACCOUNT_KEY):
        raise FileNotFoundError(
            f"Service account key not found at '{SERVICE_ACCOUNT_KEY}'. "
            "Download your serviceAccountKey.json from Firebase Console > Project Settings > Service Accounts."
        )

    credentials = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_KEY)
    return BetaAnalyticsDataClient(credentials=credentials)


def fetch_ga4_daily_report(client):
    """
    Queries Google Analytics 4 for yesterday's app metrics:
    - Overview (Active users, new users, sessions, engagement rate, average session duration)
    - Top Events (Event names and counts)
    - App Versions (Active users per release version)
    """
    if not GA4_PROPERTY_ID or GA4_PROPERTY_ID.strip() == "" or GA4_PROPERTY_ID == "your_ga4_property_id":
        raise ValueError(
            "GA4_PROPERTY_ID is missing or not set in .env. "
            "Find it in Firebase Console > Project Settings > Integrations > Google Analytics."
        )

    property_path = f"properties/{GA4_PROPERTY_ID.strip()}"
    print(f"[{datetime.now().isoformat()}] Querying GA4 Property: {property_path}...")

    date_range = [DateRange(start_date="yesterday", end_date="yesterday")]

    # 1. Daily Core Overview
    overview_request = RunReportRequest(
        property=property_path,
        date_ranges=date_range,
        metrics=[
            Metric(name="activeUsers"),
            Metric(name="newUsers"),
            Metric(name="sessions"),
            Metric(name="screenPageViews"),
            Metric(name="engagementRate"),
            Metric(name="averageSessionDuration"),
            Metric(name="userEngagementDuration"),
        ],
    )
    overview_response = client.run_report(overview_request)
    overview_data = {}
    if overview_response.rows:
        row = overview_response.rows[0]
        for header, value in zip(overview_response.metric_headers, row.metric_values):
            overview_data[header.name] = value.value

    # 2. Daily Top Events Breakdown
    events_request = RunReportRequest(
        property=property_path,
        date_ranges=date_range,
        dimensions=[Dimension(name="eventName")],
        metrics=[Metric(name="eventCount"), Metric(name="totalUsers")],
        limit=25,
    )
    events_response = client.run_report(events_request)
    events_data = []
    for row in events_response.rows:
        events_data.append({
            "eventName": row.dimension_values[0].value,
            "eventCount": int(row.metric_values[0].value),
            "users": int(row.metric_values[1].value),
        })

    # 3. Active App Versions
    versions_request = RunReportRequest(
        property=property_path,
        date_ranges=date_range,
        dimensions=[Dimension(name="appVersion")],
        metrics=[Metric(name="activeUsers"), Metric(name="sessions")],
        limit=10,
    )
    versions_response = client.run_report(versions_request)
    versions_data = []
    for row in versions_response.rows:
        versions_data.append({
            "appVersion": row.dimension_values[0].value,
            "activeUsers": int(row.metric_values[0].value),
            "sessions": int(row.metric_values[1].value),
        })

    report = {
        "date": "yesterday",
        "overview": overview_data,
        "top_events": events_data,
        "app_versions": versions_data,
    }
    return report


def analyze_with_gemini(report):
    """Sends GA4 metrics to Gemini for AI analysis and product insights."""
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    if not gemini_api_key:
        raise ValueError("GEMINI_API_KEY is not set. Please set it in .env or environment.")

    client = genai.Client(api_key=gemini_api_key)
    print(f"Sending Analytics report to Gemini API ({GEMINI_MODEL})...")

    data_str = json.dumps(report, indent=2)

    prompt = f"""
You are an expert Mobile App Product & Analytics Specialist.
Analyze the following daily Firebase / Google Analytics (GA4) report for our iOS application.

Provide a structured, executive-ready briefing with:
1. 📊 Executive Summary (Key performance highlights & health score)
2. 👥 User Activity & Engagement (Active vs new users, session duration, engagement rate)
3. ⚡ Feature & Event Performance (Key in-app events, user workflow trends)
4. 📱 App Version Adoption & Stability Observations
5. 💡 Actionable Insights & Recommendations for Product/Engineering

Analytics Data:
```json
{data_str}
```
"""

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
    )
    return response.text


from notifier import dispatch_all_notifications


def log_results(analysis_result):
    """Outputs analysis to terminal, saves to log file, and dispatches to configured notification channels."""
    timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    divider = "=" * 60
    log_entry = f"\n{divider}\n[FIREBASE ANALYTICS AI REPORT - {timestamp_str}]\n{divider}\n{analysis_result}\n"

    print(log_entry)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(log_entry)
    print(f"Report saved to: {LOG_FILE}")

    # Dispatch to Telegram, Discord, Gmail, macOS banners, and reports/ directory
    dispatch_all_notifications(analysis_result)


def main():
    print(f"=== Starting Firebase Analytics AI Pipeline: {datetime.now()} ===")
    try:
        client = get_analytics_client()
        report = fetch_ga4_daily_report(client)
        result = analyze_with_gemini(report)
        log_results(result)
        print("=== Pipeline Execution Finished Successfully ===")
    except Exception as err:
        print(f"Error during pipeline execution: {err}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
