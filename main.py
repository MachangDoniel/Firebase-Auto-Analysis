"""
Multi-App Firebase Analytics, In-App Purchases & Crash Intelligence Pipeline
Supports multiple apps across separate GA4 properties or stream IDs in the same project.
Tracks In-App Purchases (Subscriptions & Consumable Minutes), Revenue, Multi-Horizon Benchmarks,
Crash Analytics, New Build Comparisons, and Multi-Channel Delivery (PDF + MD + Charts).
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
    FilterExpression,
    FilterExpressionList,
    Filter,
)
from google.oauth2 import service_account
from google import genai
from notifier import dispatch_all_notifications
from charts import generate_all_charts

# ==========================================
# Configuration
# ==========================================
APPS_CONFIG_FILE = BASE_DIR / "apps_config.json"
DEFAULT_SERVICE_KEY = os.getenv("FIREBASE_KEY_PATH", str(BASE_DIR / "serviceAccountKey.json"))
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
LOG_FILE = BASE_DIR / "daily_analysis.log"
CHARTS_DIR = BASE_DIR / "reports" / "charts"


def load_apps_configuration():
    """Loads configured apps from apps_config.json or falls back to .env."""
    apps = []
    if os.path.exists(APPS_CONFIG_FILE):
        try:
            with open(APPS_CONFIG_FILE, "r", encoding="utf-8") as f:
                raw_apps = json.load(f)
                for a in raw_apps:
                    if a.get("ga4_property_id") and a.get("ga4_property_id").strip():
                        apps.append(a)
        except Exception as e:
            print(f"Warning: Failed to load apps_config.json: {e}", file=sys.stderr)

    if not apps:
        ga4_id = os.getenv("GA4_PROPERTY_ID")
        if ga4_id and ga4_id.strip():
            apps.append({
                "app_id": "music-separation-ios",
                "app_name": "Music Separation iOS",
                "bundle_id": "com.neuralsound.mss",
                "ga4_property_id": ga4_id.strip(),
                "stream_id": "14402502632",
                "platform": "iOS",
                "service_account_key": DEFAULT_SERVICE_KEY,
            })

    return apps


def get_analytics_client(key_path):
    """Initializes GA4 client for a given service account key."""
    if not os.path.isabs(key_path):
        key_path = str(BASE_DIR / key_path)
    if not os.path.exists(key_path):
        raise FileNotFoundError(f"Service account key not found at '{key_path}'.")
    credentials = service_account.Credentials.from_service_account_file(key_path)
    return BetaAnalyticsDataClient(credentials=credentials)


def build_production_filter(stream_id, exclude_tester_countries=None):
    """
    Returns a GA4 FilterExpression scoped to a specific stream AND excluding
    known internal-tester countries (e.g. Bangladesh) so only real App Store
    (production) traffic is returned.

    Args:
        stream_id: GA4 stream ID to scope the query.
        exclude_tester_countries: list of country names to exclude (testers).
                                  Defaults to ["Bangladesh"].
    """
    if exclude_tester_countries is None:
        exclude_tester_countries = ["Bangladesh"]

    expressions = []

    # Filter 1: Scope to specific stream
    if stream_id and str(stream_id).strip():
        expressions.append(FilterExpression(
            filter=Filter(
                field_name="streamId",
                string_filter=Filter.StringFilter(value=str(stream_id).strip())
            )
        ))

    # Filter 2: Exclude internal-tester countries (TestFlight testers)
    for country in exclude_tester_countries:
        expressions.append(FilterExpression(
            not_expression=FilterExpression(
                filter=Filter(
                    field_name="country",
                    string_filter=Filter.StringFilter(
                        match_type=Filter.StringFilter.MatchType.EXACT,
                        value=country,
                        case_sensitive=False,
                    )
                )
            )
        ))

    if len(expressions) > 1:
        return FilterExpression(and_group=FilterExpressionList(expressions=expressions))
    elif expressions:
        return expressions[0]
    return None


def build_testflight_filter(stream_id, tester_countries=None):
    """
    Returns a GA4 FilterExpression that captures ONLY the internal-tester
    (TestFlight) traffic — the inverse of build_production_filter.

    Args:
        stream_id: GA4 stream ID to scope the query.
        tester_countries: list of country names that represent testers.
                          Defaults to ["Bangladesh"].
    """
    if tester_countries is None:
        tester_countries = ["Bangladesh"]

    expressions = []

    if stream_id and str(stream_id).strip():
        expressions.append(FilterExpression(
            filter=Filter(
                field_name="streamId",
                string_filter=Filter.StringFilter(value=str(stream_id).strip())
            )
        ))

    # At least one tester country must match (OR logic across countries)
    if len(tester_countries) == 1:
        expressions.append(FilterExpression(
            filter=Filter(
                field_name="country",
                string_filter=Filter.StringFilter(
                    match_type=Filter.StringFilter.MatchType.EXACT,
                    value=tester_countries[0],
                    case_sensitive=False,
                )
            )
        ))
    elif tester_countries:
        country_exprs = [
            FilterExpression(
                filter=Filter(
                    field_name="country",
                    string_filter=Filter.StringFilter(
                        match_type=Filter.StringFilter.MatchType.EXACT,
                        value=c,
                        case_sensitive=False,
                    )
                )
            )
            for c in tester_countries
        ]
        expressions.append(FilterExpression(or_group=FilterExpressionList(expressions=country_exprs)))

    if len(expressions) > 1:
        return FilterExpression(and_group=FilterExpressionList(expressions=expressions))
    elif expressions:
        return expressions[0]
    return None



def fetch_app_analytics_and_crashes(client, ga4_property_id, app_name, stream_id=None, bundle_id="", tester_countries=None):
    """
    Queries GA4 for complete analytics, in-app purchases & product sales, crash metrics,
    new vs returning cohorts, multi-horizon growth, top events, and app versions.

    Uses build_production_filter() to exclude internal-tester countries (e.g. Bangladesh)
    from all queries so only real App Store (production) traffic is reported.
    A small TestFlight/internal-tester summary is appended separately.
    """
    if tester_countries is None:
        tester_countries = ["Bangladesh"]

    property_path = f"properties/{ga4_property_id.strip()}"
    # Production filter: stream-scoped + tester countries excluded
    dim_filter = build_production_filter(stream_id, exclude_tester_countries=tester_countries)
    # Tester filter: stream-scoped + tester countries only (for internal summary)
    tf_filter = build_testflight_filter(stream_id, tester_countries=tester_countries)

    print(f"[{datetime.now().isoformat()}] Querying [{app_name}] | Production only (excluding: {tester_countries}) | Stream: {stream_id or 'All'} | Bundle: {bundle_id}")


    yesterday_range = [DateRange(start_date="yesterday", end_date="yesterday")]
    seven_day_range = [DateRange(start_date="7daysAgo", end_date="yesterday")]
    thirty_day_range = [DateRange(start_date="30daysAgo", end_date="yesterday")]

    # 1. Overview & Stability Metrics (Yesterday)
    overview_req = RunReportRequest(
        property=property_path,
        date_ranges=yesterday_range,
        dimension_filter=dim_filter,
        metrics=[
            Metric(name="activeUsers"),
            Metric(name="newUsers"),
            Metric(name="sessions"),
            Metric(name="screenPageViews"),
            Metric(name="engagementRate"),
            Metric(name="averageSessionDuration"),
            Metric(name="eventsPerSession"),
            Metric(name="bounceRate"),
            Metric(name="crashFreeUsersRate"),
            Metric(name="purchaseRevenue"),
        ],
    )
    overview_res = client.run_report(overview_req)
    overview_data = {}
    if overview_res.rows:
        row = overview_res.rows[0]
        for header, val in zip(overview_res.metric_headers, row.metric_values):
            overview_data[header.name] = val.value

    # 2. In-App Purchases & Product Revenue (Past 30 Days Breakdown)
    products_req = RunReportRequest(
        property=property_path,
        date_ranges=thirty_day_range,
        dimension_filter=dim_filter,
        dimensions=[Dimension(name="itemId"), Dimension(name="itemName")],
        metrics=[Metric(name="itemsPurchased"), Metric(name="itemRevenue")],
        order_bys=[OrderBy(metric=OrderBy.MetricOrderBy(metric_name="itemsPurchased"), desc=True)],
    )
    products_res = client.run_report(products_req)
    products_data = []
    for row in products_res.rows:
        products_data.append({
            "item_id": row.dimension_values[0].value,
            "item_name": row.dimension_values[1].value,
            "quantity": int(row.metric_values[0].value),
            "revenue_usd": round(float(row.metric_values[1].value), 2),
        })

    # 3. Recent Transaction Log (When, Who, Product, Build/Version, Country, Amount)
    transactions_req = RunReportRequest(
        property=property_path,
        date_ranges=thirty_day_range,
        dimension_filter=dim_filter,
        dimensions=[
            Dimension(name="date"),
            Dimension(name="appVersion"),
            Dimension(name="itemId"),
            Dimension(name="itemName"),
            Dimension(name="country")
        ],
        metrics=[Metric(name="itemsPurchased"), Metric(name="itemRevenue")],
        order_bys=[OrderBy(dimension=OrderBy.DimensionOrderBy(dimension_name="date"), desc=True)],
        limit=25,
    )
    transactions_res = client.run_report(transactions_req)
    transactions_data = []
    for row in transactions_res.rows:
        date_str = row.dimension_values[0].value
        formatted_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}" if len(date_str) == 8 else date_str
        version_str = row.dimension_values[1].value
        transactions_data.append({
            "date": formatted_date,
            "app_version": version_str,
            "product_id": row.dimension_values[2].value,
            "product_name": row.dimension_values[3].value,
            "country": row.dimension_values[4].value,
            "quantity": int(row.metric_values[0].value),
            "revenue_usd": round(float(row.metric_values[1].value), 2),
        })

    # 4. Multi-Horizon Growth Benchmarks (Yesterday, 7 Days, 30 Days, 365 Days, Lifetime)
    horizon_defs = [
        ("Yesterday", "yesterday", "yesterday"),
        ("Past 7 Days", "7daysAgo", "yesterday"),
        ("Past 30 Days", "30daysAgo", "yesterday"),
        ("Past Year (365d)", "365daysAgo", "yesterday"),
        ("All-Time", "2020-01-01", "yesterday"),
    ]
    horizon_data = []
    for h_label, start_d, end_d in horizon_defs:
        h_req = RunReportRequest(
            property=property_path,
            date_ranges=[DateRange(start_date=start_d, end_date=end_d)],
            dimension_filter=dim_filter,
            metrics=[
                Metric(name="activeUsers"),
                Metric(name="newUsers"),
                Metric(name="sessions"),
                Metric(name="engagementRate"),
                Metric(name="purchaseRevenue"),
            ]
        )
        h_res = client.run_report(h_req)
        if h_res.rows:
            r = h_res.rows[0]
            horizon_data.append({
                "horizon": h_label,
                "activeUsers": int(r.metric_values[0].value),
                "newUsers": int(r.metric_values[1].value),
                "sessions": int(r.metric_values[2].value),
                "engagementRate": f"{round(float(r.metric_values[3].value)*100, 1)}%",
                "revenue_usd": round(float(r.metric_values[4].value), 2),
            })

    # 5. New vs Returning Cohorts (Yesterday)
    cohort_req = RunReportRequest(
        property=property_path,
        date_ranges=yesterday_range,
        dimension_filter=dim_filter,
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

    # 6. 7-Day Velocity
    trend_req = RunReportRequest(
        property=property_path,
        date_ranges=seven_day_range,
        dimension_filter=dim_filter,
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

    # 7. Top Events Telemetry
    events_req = RunReportRequest(
        property=property_path,
        date_ranges=yesterday_range,
        dimension_filter=dim_filter,
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

    # 8. App Versions & Build Comparison
    versions_req = RunReportRequest(
        property=property_path,
        date_ranges=yesterday_range,
        dimension_filter=dim_filter,
        dimensions=[Dimension(name="appVersion")],
        metrics=[
            Metric(name="activeUsers"),
            Metric(name="sessions"),
            Metric(name="engagementRate"),
            Metric(name="crashFreeUsersRate"),
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
            "crashFreeUsersRate": f"{round(float(row.metric_values[3].value) * 100, 2)}%" if float(row.metric_values[3].value) > 0 else "100.0%",
        })

    # 9. Geographic Distribution
    geo_req = RunReportRequest(
        property=property_path,
        date_ranges=yesterday_range,
        dimension_filter=dim_filter,
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

    # 10. Internal Tester (TestFlight) Summary — separate query, NOT mixed into production metrics
    print(f"  → Fetching internal-tester (TestFlight) summary for [{app_name}]...")
    tf_overview_req = RunReportRequest(
        property=property_path,
        date_ranges=yesterday_range,
        dimension_filter=tf_filter,
        metrics=[
            Metric(name="activeUsers"),
            Metric(name="newUsers"),
            Metric(name="sessions"),
            Metric(name="purchaseRevenue"),
        ],
    )
    tf_overview_res = client.run_report(tf_overview_req)
    tf_summary = {"note": f"Internal testers only ({', '.join(tester_countries)}). NOT included in production metrics above."}
    if tf_overview_res.rows:
        tf_row = tf_overview_res.rows[0]
        for header, val in zip(tf_overview_res.metric_headers, tf_row.metric_values):
            tf_summary[header.name] = val.value

    app_payload = {
        "app_name": app_name,
        "bundle_id": bundle_id,
        "ga4_property_id": ga4_property_id,
        "stream_id": stream_id,
        "data_scope": f"Production only — internal testers ({', '.join(tester_countries)}) excluded from all metrics",
        "yesterday_overview": overview_data,
        "product_sales_30d": products_data,
        "recent_transactions": transactions_data,
        "multi_horizon_benchmarks": horizon_data,
        "new_vs_returning_cohorts": cohort_data,
        "past_7_days_trend": trend_data,
        "top_events_telemetry": events_data,
        "app_versions": versions_data,
        "geographic_distribution": geo_data,
        "internal_tester_summary": tf_summary,
    }

    # Generate visual PNG charts for this app (includes Revenue Chart) — production data only
    chart_paths = generate_all_charts(app_name, app_payload, CHARTS_DIR)
    app_payload["chart_paths"] = chart_paths

    return app_payload



def analyze_all_apps_with_gemini(all_apps_data):
    """
    Sends all apps data to Gemini for analysis.
    Implements multi-model automatic fallback (gemini-3.6-flash -> gemini-3.5-flash -> gemini-flash-latest).
    If all models or the API key fails, automatically generates a clean deterministic fallback report.
    """
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    data_json = json.dumps(all_apps_data, indent=2)

    prompt = f"""
You are a Principal Mobile Analytics & Monetization Growth Architect.
Analyze the following multi-app daily Firebase / GA4 analytics dataset covering all active mobile applications.

### Mandatory Structure for Multi-App Report:
1. Provide an overarching **Portfolio Executive Summary & Health Dashboard** comparing all apps side-by-side (Total Users, Total Revenue, Top Selling Products, Engagement, and Crash-Free Rates).
2. For **EACH APPLICATION (e.g. Music Separation iOS and Vocal Cleaner)**, provide a dedicated deep-dive section containing:
   - **App Header & Health Score** (X / 10 with rationale)
   - **💰 In-App Purchases, Subscriptions & Consumable Minutes Breakdown**:
     * **Product Sales Summary Table**: Item/Product ID, Product Name, Plan Type (Monthly / Weekly / Consumable Minutes), Units Sold (30D), Total Revenue ($ USD), and % Share.
     * **Transaction Timeline Log Table**: Date/Timestamp, App Build / Version, Product Purchased, Units, Revenue ($ USD), and Country of Purchase.
     * **Build Environment & Monetization Analysis**: Identify if transactions or purchase errors occurred in **Production Builds** vs **TestFlight/Staged Builds** (e.g. TestFlight sandbox retry loops). Compare Subscriptions vs Consumable Minute packs (60 min vs 300 min).
   - **📅 Multi-Horizon Growth & Historical Scale Comparison**: Table comparing Yesterday, Past 7d, Past 30d, Past Year (365d), and Lifetime.
   - **Old vs. New User Cohort Deep-Dive** (Table comparing New Users vs Returning Users with duration and engagement).
   - **7-Day Velocity & Trajectory** (Table & daily trend commentary).
   - **User Funnel Diagrams** (ASCII/Unicode diagrams for onboarding, paywall conversion, and core feature execution).
   - **Crash & Stability Health by App Version** (Crash-free user rates and exceptions isolated by version).
   - **🚨 New Build / TestFlight / Staged Rollout Alert Section**: Explicitly detect and compare new builds against the production baseline.
   - **Top In-App Events & Feature Lookups** (Including slider debouncing or telemetry bugs).
   - **Geographic Distribution**.
   - **Prioritized Strategic Action Matrix** (P0, P1, P2 with Engineering/Product/Growth fixes).

Multi-App Dataset:
```json
{data_json}
```
"""

    candidate_models = [
        os.getenv("GEMINI_MODEL", "gemini-3.6-flash"),
        "gemini-3.5-flash",
        "gemini-flash-latest",
        "gemini-3.7-flash",
    ]

    if gemini_api_key:
        client = genai.Client(api_key=gemini_api_key)
        for model_name in candidate_models:
            try:
                print(f"Attempting Gemini generation using model: '{model_name}'...")
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                )
                if response and response.text:
                    print(f"✅ Successfully generated analysis with '{model_name}'.")
                    return response.text
            except Exception as e:
                print(f"⚠️ Model '{model_name}' failed: {e}. Trying next candidate model...", file=sys.stderr)

    # Deterministic Fallback: Generate structured metrics report directly without AI
    print("⚠️ All Gemini models / API keys unavailable. Generating deterministic metrics report...", file=sys.stderr)
    fallback_report = f"# 📊 Daily Mobile Analytics & Monetization Report (Automated Data Mode)\n\n"
    fallback_report += f"> ⚠️ *Gemini AI synthesis was temporarily bypassed. Below is your raw verified multi-app telemetry, product sales, and performance data.*\n\n"
    
    for app in all_apps_data:
        app_name = app.get("app_name", "App")
        yesterday = app.get("yesterday_overview", {})
        fallback_report += f"## 📱 {app_name}\n\n"
        fallback_report += f"| Metric | Value |\n| :--- | :--- |\n"
        fallback_report += f"| **Active Users (DAU)** | {yesterday.get('activeUsers', 'N/A')} |\n"
        fallback_report += f"| **New Users** | {yesterday.get('newUsers', 'N/A')} |\n"
        fallback_report += f"| **Total Sessions** | {yesterday.get('sessions', 'N/A')} |\n"
        fallback_report += f"| **Engagement Rate** | {round(float(yesterday.get('engagementRate', 0))*100, 1)}% |\n"
        fallback_report += f"| **Crash-Free User Rate** | {round(float(yesterday.get('crashFreeUsersRate', 1))*100, 2)}% |\n\n"
        
        fallback_report += f"### 💰 Product Sales & Subscriptions (30 Days)\n\n"
        fallback_report += f"| Product ID | Product Name | Units Sold | Total Revenue ($ USD) |\n| :--- | :--- | :--- | :--- |\n"
        for p in app.get("product_sales_30d", []):
            fallback_report += f"| `{p['item_id']}` | {p['item_name']} | {p['quantity']} | ${p['revenue_usd']:.2f} |\n"
        fallback_report += "\n---\n\n"

    return fallback_report


def log_results(analysis_result, all_apps_data):
    """Outputs analysis, saves logs, and dispatches across all channels with charts."""
    timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    divider = "=" * 60
    log_entry = f"\n{divider}\n[MULTI-APP FIREBASE ANALYTICS & MONETIZATION AI REPORT - {timestamp_str}]\n{divider}\n{analysis_result}\n"

    print(log_entry)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(log_entry)
    print(f"Report saved to: {LOG_FILE}")

    # Gather all generated chart images across all apps
    all_charts = []
    for app in all_apps_data:
        for chart_path in app.get("chart_paths", {}).values():
            if os.path.exists(chart_path):
                all_charts.append(chart_path)

    # Dispatch to Telegram, Discord, Gmail, macOS banners, and reports/ directory
    dispatch_all_notifications(analysis_result, chart_images=all_charts)


def main():
    print(f"=== Starting Multi-App Firebase Analytics & Monetization AI Pipeline: {datetime.now()} ===")
    try:
        apps = load_apps_configuration()
        print(f"Loaded {len(apps)} configured application(s): {[a['app_name'] for a in apps]}")

        all_apps_data = []
        for app in apps:
            client = get_analytics_client(app.get("service_account_key", DEFAULT_SERVICE_KEY))
            # Per-app tester country list; falls back to global default ["Bangladesh"]
            tester_countries = app.get("tester_countries", ["Bangladesh"])
            app_data = fetch_app_analytics_and_crashes(
                client=client,
                ga4_property_id=app["ga4_property_id"],
                app_name=app["app_name"],
                stream_id=app.get("stream_id"),
                bundle_id=app.get("bundle_id", ""),
                tester_countries=tester_countries,
            )
            all_apps_data.append(app_data)

        ai_analysis = analyze_all_apps_with_gemini(all_apps_data)
        log_results(ai_analysis, all_apps_data)
        print("=== Multi-App Pipeline Execution Finished Successfully ===")
    except Exception as err:
        print(f"Error during multi-app pipeline execution: {err}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
