"""
Comprehensive Firebase / Google Analytics (GA4) to Gemini AI Pipeline
Extracts multi-dimensional iOS app analytics (New vs Returning cohorts, 7-day trends,
full event funnels, versions, geo, devices) and generates executive PDF & notifications.
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
    OrderBy,
    RunReportRequest,
)
from google.oauth2 import service_account
from google import genai
from notifier import dispatch_all_notifications

# ==========================================
# Configuration & Environment Variables
# ==========================================
SERVICE_ACCOUNT_KEY = os.getenv("FIREBASE_KEY_PATH", str(BASE_DIR / "serviceAccountKey.json"))
GA4_PROPERTY_ID = os.getenv("GA4_PROPERTY_ID")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
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


def fetch_comprehensive_ga4_data(client):
    """
    Queries Google Analytics 4 across 6 comprehensive analytical dimensions:
    1. Daily Overview (Yesterday)
    2. New vs. Returning User Cohort Breakdown (Old vs New behavior)
    3. 7-Day Daily Trend (Trajectory & growth)
    4. Complete Event Telemetry & Funnel (Top 30 events)
    5. App Version Adoption (Current, Staged, Legacy)
    6. Geographic & Top Device Distribution
    """
    if not GA4_PROPERTY_ID or GA4_PROPERTY_ID.strip() == "":
        raise ValueError("GA4_PROPERTY_ID is missing in .env.")

    property_path = f"properties/{GA4_PROPERTY_ID.strip()}"
    print(f"[{datetime.now().isoformat()}] Querying GA4 Multi-Dimensional Data: {property_path}...")

    yesterday_range = [DateRange(start_date="yesterday", end_date="yesterday")]
    seven_day_range = [DateRange(start_date="7daysAgo", end_date="yesterday")]

    # 1. Yesterday Overview Metrics
    overview_req = RunReportRequest(
        property=property_path,
        date_ranges=yesterday_range,
        metrics=[
            Metric(name="activeUsers"),
            Metric(name="newUsers"),
            Metric(name="sessions"),
            Metric(name="screenPageViews"),
            Metric(name="engagementRate"),
            Metric(name="averageSessionDuration"),
            Metric(name="userEngagementDuration"),
            Metric(name="eventsPerSession"),
        ],
    )
    overview_res = client.run_report(overview_req)
    overview_data = {}
    if overview_res.rows:
        row = overview_res.rows[0]
        for header, val in zip(overview_res.metric_headers, row.metric_values):
            overview_data[header.name] = val.value

    # 2. New vs. Returning Cohort Breakdown (Old vs New)
    cohort_req = RunReportRequest(
        property=property_path,
        date_ranges=yesterday_range,
        dimensions=[Dimension(name="newVsReturning")],
        metrics=[
            Metric(name="activeUsers"),
            Metric(name="sessions"),
            Metric(name="averageSessionDuration"),
            Metric(name="engagementRate"),
            Metric(name="screenPageViews"),
        ],
    )
    cohort_res = client.run_report(cohort_req)
    cohort_data = []
    for row in cohort_res.rows:
        cohort_data.append({
            "user_type": row.dimension_values[0].value,
            "activeUsers": int(row.metric_values[0].value),
            "sessions": int(row.metric_values[1].value),
            "avgSessionDuration_sec": round(float(row.metric_values[2].value), 1),
            "engagementRate": f"{round(float(row.metric_values[3].value) * 100, 1)}%",
            "screenPageViews": int(row.metric_values[4].value),
        })

    # 3. 7-Day Trend (Daily trajectory)
    trend_req = RunReportRequest(
        property=property_path,
        date_ranges=seven_day_range,
        dimensions=[Dimension(name="date")],
        metrics=[
            Metric(name="activeUsers"),
            Metric(name="newUsers"),
            Metric(name="sessions"),
            Metric(name="engagementRate"),
        ],
        order_bys=[OrderBy(dimension=OrderBy.DimensionOrderBy(dimension_name="date"))],
    )
    trend_res = client.run_report(trend_req)
    trend_data = []
    for row in trend_res.rows:
        date_str = row.dimension_values[0].value
        formatted_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}" if len(date_str) == 8 else date_str
        trend_data.append({
            "date": formatted_date,
            "activeUsers": int(row.metric_values[0].value),
            "newUsers": int(row.metric_values[1].value),
            "sessions": int(row.metric_values[2].value),
            "engagementRate": f"{round(float(row.metric_values[3].value) * 100, 1)}%",
        })

    # 4. Detailed Event Telemetry (Top 30 events)
    events_req = RunReportRequest(
        property=property_path,
        date_ranges=yesterday_range,
        dimensions=[Dimension(name="eventName")],
        metrics=[
            Metric(name="eventCount"),
            Metric(name="totalUsers"),
            Metric(name="eventCountPerUser"),
        ],
        order_bys=[OrderBy(metric=OrderBy.MetricOrderBy(metric_name="eventCount"), desc=True)],
        limit=30,
    )
    events_res = client.run_report(events_req)
    events_data = []
    for row in events_res.rows:
        events_data.append({
            "eventName": row.dimension_values[0].value,
            "eventCount": int(row.metric_values[0].value),
            "totalUsers": int(row.metric_values[1].value),
            "eventsPerUser": round(float(row.metric_values[2].value), 1),
        })

    # 5. App Versions Breakdown
    versions_req = RunReportRequest(
        property=property_path,
        date_ranges=yesterday_range,
        dimensions=[Dimension(name="appVersion")],
        metrics=[
            Metric(name="activeUsers"),
            Metric(name="sessions"),
            Metric(name="engagementRate"),
        ],
        order_bys=[OrderBy(metric=OrderBy.MetricOrderBy(metric_name="activeUsers"), desc=True)],
        limit=10,
    )
    versions_res = client.run_report(versions_req)
    versions_data = []
    for row in versions_res.rows:
        versions_data.append({
            "appVersion": row.dimension_values[0].value,
            "activeUsers": int(row.metric_values[0].value),
            "sessions": int(row.metric_values[1].value),
            "engagementRate": f"{round(float(row.metric_values[2].value) * 100, 1)}%",
        })

    # 6. Geographic Breakdown (Top 10 Countries)
    geo_req = RunReportRequest(
        property=property_path,
        date_ranges=yesterday_range,
        dimensions=[Dimension(name="country")],
        metrics=[Metric(name="activeUsers"), Metric(name="sessions")],
        order_bys=[OrderBy(metric=OrderBy.MetricOrderBy(metric_name="activeUsers"), desc=True)],
        limit=10,
    )
    geo_res = client.run_report(geo_req)
    geo_data = []
    for row in geo_res.rows:
        geo_data.append({
            "country": row.dimension_values[0].value,
            "activeUsers": int(row.metric_values[0].value),
            "sessions": int(row.metric_values[1].value),
        })

    return {
        "report_generated_at": datetime.now().isoformat(),
        "yesterday_overview": overview_data,
        "new_vs_returning_cohorts": cohort_data,
        "past_7_days_trend": trend_data,
        "top_events_telemetry": events_data,
        "app_versions": versions_data,
        "geographic_distribution": geo_data,
    }


def analyze_with_gemini(analytics_payload):
    """
    Sends multi-dimensional GA4 data to Gemini to produce an in-depth,
    diagram-rich, structured executive analysis.
    """
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    if not gemini_api_key:
        raise ValueError("GEMINI_API_KEY is not set.")

    client = genai.Client(api_key=gemini_api_key)
    print(f"Sending rich analytics payload to Gemini ({GEMINI_MODEL})...")

    data_json = json.dumps(analytics_payload, indent=2)

    prompt = f"""
You are a Principal Mobile Analytics & Growth Architect specializing in iOS audio/utility products.
Analyze the following multi-dimensional Firebase / GA4 daily analytics dataset for **Neural Sound iOS**.

### Mandatory Report Structure & Requirements:

# 📊 Neural Sound iOS — Executive Daily Analytics & Growth Intelligence

### 🎯 Product Overview & Health Score
- **Overall Health Score:** (X / 10 with clear mathematical rationale)
- **Executive Summary:** Bulleted highlights of yesterday's performance, user velocity, and notable anomalies.

---

## 👥 1. Old vs. New User Cohort Deep-Dive (CRITICAL)
- Create a clear markdown comparison table: **New Users** vs **Returning (Old) Users** (Active users, % of DAU, Sessions/user, Avg Session Duration, Engagement Rate, Screenviews).
- Detailed behavioral analysis: How do new users interact differently from returning power users? What is the retention drop-off risk?

---

## 📈 2. 7-Day Performance & Velocity Trajectory
- Include a 7-day trend table showing Date, DAU, New Users, Returning Users, Sessions, and Engagement Rate.
- Add a text/ASCII visual progress bar or trend indicator for daily volume.
- Momentum analysis: Is acquisition accelerating, plateauing, or decaying?

---

## ⚡ 3. End-to-End User Journey & Funnel Diagrams (DIAGRAMS REQUIRED)
- **Provide 2 ASCII/Unicode diagrams:**
  1. **Onboarding & Auth Funnel Diagram** (`first_open` ──► `onboarding_viewed` ──► `login_succeeded` ──► `first_journey_completed`) with explicit conversion percentages.
  2. **Core Audio Creation & Player Funnel Diagram** (`plus_button_tap` ──► `import_files`/`photos` ──► `separation_player_opened` ──► `separation_play_started`) with drop-off bottlenecks highlighted.
- Identify friction points and high-friction drop-offs.

---

## 🎛️ 4. Feature Telemetry & Power-User Lookups
- Table of key feature interactions and in-app event counts.
- Identify telemetry anomalies (e.g. un-debounced slider tracking on pitch/tempo).

---

## 📱 5. App Version Adoption & Global Footprint
- Version distribution table & visual ASCII bar chart (Production vs Staged Rollout vs Legacy versions).
- Top geographic markets table (Top countries by active users and engagement).

---

## 💡 6. Strategic Action Matrix (Prioritized)
Provide a structured table:
| Priority | Category (Eng / Product / Growth) | Issue / Finding | Recommended Action | Expected Impact |

Data Payload:
```json
{data_json}
```
"""

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
    )
    return response.text


def log_results(analysis_result):
    """Outputs analysis to terminal, saves to log file, and dispatches to all channels."""
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
    print(f"=== Starting Comprehensive Firebase Analytics AI Pipeline: {datetime.now()} ===")
    try:
        client = get_analytics_client()
        payload = fetch_comprehensive_ga4_data(client)
        result = analyze_with_gemini(payload)
        log_results(result)
        print("=== Pipeline Execution Finished Successfully ===")
    except Exception as err:
        print(f"Error during pipeline execution: {err}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
