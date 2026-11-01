"""
Visual Charts Generator for Firebase / GA4 Analytics
Generates modern, presentation-grade visual charts (PNGs) for inclusion in
PDF reports, HTML dashboards, and Discord/Telegram messages.
"""

import os
from pathlib import Path
import matplotlib
matplotlib.use("Agg")  # Non-interactive backend
import matplotlib.pyplot as plt
import numpy as np

# Set cohesive modern visual style
plt.rcParams["font.family"] = "sans-serif"
plt.rcParams["font.sans-serif"] = ["Helvetica", "Arial", "DejaVu Sans"]
plt.rcParams["axes.edgecolor"] = "#cbd5e1"
plt.rcParams["axes.linewidth"] = 0.8


def funnel_stages(top_events):
    """Returns (stage, users) pairs for the core conversion funnel, skipping empty stages."""
    events = {e["eventName"]: e["totalUsers"] for e in top_events}
    stages = [
        ("Onboarding", events.get("onboarding_viewed", 0) or events.get("first_open", 0)),
        ("Auth Complete", events.get("login_succeeded", 0)),
        ("Journey Done", events.get("first_journey_login_completed", 0)),
        ("Plus Button", events.get("plus_button_tap", 0)),
        ("Import Action", events.get("import_started", 0) or (events.get("import_files_app_tap", 0) + events.get("import_photos_tap", 0)) // 2),
        ("Player Opened", events.get("separation_player_opened", 0)),
        ("Play Started", events.get("separation_play_started", 0)),
    ]
    return [s for s in stages if s[1] > 0]


def generate_income_charts(income, output_dir):
    """
    Generates App Store income charts for the PDF report:
    1. Proceeds & Sales per day (5 weeks)
    2. Proceeds by product and by territory (5 weeks)
    Returns dictionary of generated chart image paths.
    """
    if income.get("status") != "ok":
        return {}
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    period = income["periods"]["5W"]
    chart_paths = {}

    daily = period["daily"]
    dates = [d["date"][5:] for d in daily]
    fig, ax = plt.subplots(figsize=(7, 3.2), dpi=200)
    ax.plot(dates, [d["sales"] for d in daily], color="#06b6d4", linewidth=2, linestyle="--", label="Sales")
    ax.plot(dates, [d["proceeds"] for d in daily], color="#4f46e5", linewidth=2.5, label="Proceeds")
    ax.set_title("App Store Income — Proceeds & Sales per Day (5 Weeks, USD)", fontsize=11, fontweight="bold", pad=10, color="#0f172a")
    ax.set_xticks(range(0, len(dates), 7))
    ax.grid(True, linestyle=":", alpha=0.6, color="#cbd5e1")
    ax.legend(loc="upper left", frameon=True, fontsize=8.5)
    ax.tick_params(colors="#475569", labelsize=8.5)
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    trend_file = output_dir / "app_store_income_trend.png"
    plt.tight_layout()
    plt.savefig(trend_file)
    plt.close(fig)
    chart_paths["income_trend_chart"] = str(trend_file)

    breakdowns = [
        ("products", "Proceeds by Product", "title", "app_store_income_products.png", "income_products_chart"),
        ("territories", "Proceeds by Territory", "name", "app_store_income_territories.png", "income_territories_chart"),
    ]
    for key, title, label_key, file_name, chart_key in breakdowns:
        items = [i for i in period[key] if i["proceeds"] > 0][:8][::-1]
        if not items:
            continue
        values = [i["proceeds"] for i in items]
        fig, ax = plt.subplots(figsize=(7, 3.2), dpi=200)
        ax.barh([i[label_key] for i in items], values, color="#4f46e5", height=0.55)
        for index, value in enumerate(values):
            ax.text(value + max(values) * 0.02, index, f"${value:,.2f}", va="center", ha="left", fontsize=8, color="#0f172a", fontweight="bold")
        ax.set_title(f"App Store Income — {title} (5 Weeks, USD)", fontsize=11, fontweight="bold", pad=10, color="#0f172a")
        ax.set_xlim(0, max(values) * 1.25)
        ax.grid(axis="x", linestyle=":", alpha=0.6, color="#cbd5e1")
        ax.tick_params(colors="#475569", labelsize=8)
        for spine in ["top", "right"]:
            ax.spines[spine].set_visible(False)
        chart_file = output_dir / file_name
        plt.tight_layout()
        plt.savefig(chart_file)
        plt.close(fig)
        chart_paths[chart_key] = str(chart_file)

    return chart_paths


def generate_all_charts(app_name, analytics_data, output_dir):
    """
    Generates a suite of visual charts for a single app:
    1. 7-Day Velocity Trend Chart
    2. Multi-Horizon Growth Comparison (Yesterday, 7d, 30d, 365d, All-Time)
    3. Product Sales & In-App Purchases Revenue Breakdown
    4. Funnel Conversion Bar Chart
    5. New vs Returning Cohort Comparison
    6. App Version Distribution & New Build Alert
    Returns dictionary of generated chart image paths.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    clean_app_id = "".join(c if c.isalnum() else "_" for c in app_name.lower())
    
    chart_paths = {}
    
    # 1. 7-Day Trend Line & Area Chart
    trend_data = analytics_data.get("past_7_days_trend", [])
    if trend_data and len(trend_data) > 1:
        dates = [d["date"][5:] for d in trend_data]  # MM-DD
        dau = [d["activeUsers"] for d in trend_data]
        new_users = [d["newUsers"] for d in trend_data]
        
        fig, ax = plt.subplots(figsize=(7, 3.2), dpi=200)
        ax.plot(dates, dau, color="#4f46e5", marker="o", linewidth=2.5, label="Active Users (DAU)")
        ax.fill_between(dates, dau, color="#4f46e5", alpha=0.12)
        ax.plot(dates, new_users, color="#06b6d4", marker="s", linewidth=2, linestyle="--", label="New Users")
        
        ax.set_title(f"{app_name} — 7-Day User Velocity & Trajectory", fontsize=11, fontweight="bold", pad=10, color="#0f172a")
        ax.set_ylabel("Daily Users", fontsize=9, color="#475569")
        ax.grid(True, linestyle=":", alpha=0.6, color="#cbd5e1")
        ax.legend(loc="upper left", frameon=True, fontsize=8.5)
        ax.tick_params(colors="#475569", labelsize=8.5)
        for spine in ["top", "right"]:
            ax.spines[spine].set_visible(False)
            
        trend_file = output_dir / f"{clean_app_id}_trend.png"
        plt.tight_layout()
        plt.savefig(trend_file)
        plt.close(fig)
        chart_paths["trend_chart"] = str(trend_file)

    # 2. Product Sales & In-App Purchases Revenue Breakdown
    products = analytics_data.get("product_sales_30d", [])
    if products:
        p_names = [p["item_id"].replace("neuralsound.", "").replace("cleaner.", "") for p in products[:5]][::-1]
        p_revs = [p["revenue_usd"] for p in products[:5]][::-1]
        p_qtys = [p["quantity"] for p in products[:5]][::-1]
        
        fig, ax = plt.subplots(figsize=(7, 3.2), dpi=200)
        colors = plt.cm.viridis(np.linspace(0.4, 0.85, len(p_names)))
        bars = ax.barh(p_names, p_revs, color=colors, height=0.55, edgecolor="#cbd5e1")
        
        for bar, rev, qty in zip(bars, p_revs, p_qtys):
            ax.text(bar.get_width() + (max(p_revs) * 0.02 if max(p_revs) > 0 else 0.5), bar.get_y() + bar.get_height()/2,
                    f"${rev:,.2f} ({qty} sold)", va="center", ha="left", fontsize=8, color="#0f172a", fontweight="bold")
                    
        ax.set_title(f"{app_name} — In-App Purchases & Product Revenue (30D)", fontsize=11, fontweight="bold", pad=10, color="#0f172a")
        ax.set_xlim(0, max(p_revs) * 1.35 if max(p_revs) > 0 else 10)
        ax.grid(axis="x", linestyle=":", alpha=0.6, color="#cbd5e1")
        ax.tick_params(colors="#475569", labelsize=8)
        for spine in ["top", "right"]:
            ax.spines[spine].set_visible(False)
            
        rev_file = output_dir / f"{clean_app_id}_revenue.png"
        plt.tight_layout()
        plt.savefig(rev_file)
        plt.close(fig)
        chart_paths["revenue_chart"] = str(rev_file)

    # 3. Multi-Horizon Growth Comparison Chart (Yesterday, 7d, 30d, 365d, All-Time)
    horizons = analytics_data.get("multi_horizon_benchmarks", [])
    if horizons:
        labels = [h["horizon"] for h in horizons]
        users = [h["activeUsers"] for h in horizons]
        sessions = [h["sessions"] for h in horizons]
        
        fig, ax = plt.subplots(figsize=(7, 3.2), dpi=200)
        x = np.arange(len(labels))
        width = 0.35
        
        rects1 = ax.bar(x - width/2, users, width, label="Active Users", color="#4f46e5")
        rects2 = ax.bar(x + width/2, sessions, width, label="Total Sessions", color="#06b6d4")
        
        ax.set_title(f"{app_name} — Multi-Horizon Scale & Comparison", fontsize=11, fontweight="bold", pad=10, color="#0f172a")
        ax.set_xticks(x)
        ax.set_xticklabels(labels, fontsize=8.5, color="#475569")
        ax.grid(axis="y", linestyle=":", alpha=0.6, color="#cbd5e1")
        ax.legend(loc="upper left", frameon=True, fontsize=8.5)
        ax.tick_params(colors="#475569", labelsize=8.5)
        for spine in ["top", "right"]:
            ax.spines[spine].set_visible(False)
            
        for rect in rects1:
            h = rect.get_height()
            if h > 0:
                ax.annotate(f"{h}", xy=(rect.get_x() + rect.get_width()/2, h),
                            xytext=(0, 3), textcoords="offset points", ha="center", va="bottom", fontsize=7.5, fontweight="bold")
        for rect in rects2:
            h = rect.get_height()
            if h > 0:
                ax.annotate(f"{h}", xy=(rect.get_x() + rect.get_width()/2, h),
                            xytext=(0, 3), textcoords="offset points", ha="center", va="bottom", fontsize=7.5)
                            
        horizon_file = output_dir / f"{clean_app_id}_horizons.png"
        plt.tight_layout()
        plt.savefig(horizon_file)
        plt.close(fig)
        chart_paths["horizon_chart"] = str(horizon_file)

    # 4. Funnel Conversion Horizontal Bar Chart
    funnel_keys = funnel_stages(analytics_data.get("top_events_telemetry", []))

    if len(funnel_keys) >= 3:
        stages = [k[0] for k in funnel_keys][::-1]
        counts = [k[1] for k in funnel_keys][::-1]
        base_count = funnel_keys[0][1]
        percentages = [f"{round((c / base_count) * 100, 1)}%" for c in counts]
        
        fig, ax = plt.subplots(figsize=(7, 3.4), dpi=200)
        colors = plt.cm.Blues(np.linspace(0.4, 0.85, len(stages)))
        bars = ax.barh(stages, counts, color=colors, height=0.55, edgecolor="#cbd5e1")
        
        for bar, pct, count in zip(bars, percentages, counts):
            ax.text(bar.get_width() + (max(counts) * 0.02), bar.get_y() + bar.get_height()/2,
                    f"{count} ({pct})", va="center", ha="left", fontsize=8, color="#0f172a", fontweight="bold")
                    
        ax.set_title(f"{app_name} — Core Conversion Funnel & Bottlenecks", fontsize=11, fontweight="bold", pad=10, color="#0f172a")
        ax.set_xlim(0, max(counts) * 1.25)
        ax.grid(axis="x", linestyle=":", alpha=0.6, color="#cbd5e1")
        ax.tick_params(colors="#475569", labelsize=8.5)
        for spine in ["top", "right"]:
            ax.spines[spine].set_visible(False)
            
        funnel_file = output_dir / f"{clean_app_id}_funnel.png"
        plt.tight_layout()
        plt.savefig(funnel_file)
        plt.close(fig)
        chart_paths["funnel_chart"] = str(funnel_file)

    # 5. New vs Returning Cohort Comparison Bar Chart
    cohorts = analytics_data.get("new_vs_returning_cohorts", [])
    if len(cohorts) >= 2:
        names = ["New Users", "Returning Users"]
        dau_vals = [c.get("activeUsers", 0) for c in cohorts[:2]]
        dur_vals = [c.get("avgSessionDuration_sec", 0) / 60 for c in cohorts[:2]]
        
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7, 2.8), dpi=200)
        
        ax1.bar(names, dau_vals, color=["#06b6d4", "#6366f1"], width=0.45)
        ax1.set_title("User Volume (DAU)", fontsize=9.5, fontweight="bold", color="#0f172a")
        ax1.tick_params(labelsize=8, colors="#475569")
        for i, v in enumerate(dau_vals):
            ax1.text(i, v + (max(dau_vals)*0.03), str(v), ha="center", fontweight="bold", fontsize=8.5)
        ax1.set_ylim(0, max(dau_vals) * 1.2)
        ax1.spines["top"].set_visible(False)
        ax1.spines["right"].set_visible(False)
        
        ax2.bar(names, dur_vals, color=["#38bdf8", "#818cf8"], width=0.45)
        ax2.set_title("Avg Session Duration (Mins)", fontsize=9.5, fontweight="bold", color="#0f172a")
        ax2.tick_params(labelsize=8, colors="#475569")
        for i, v in enumerate(dur_vals):
            ax2.text(i, v + (max(dur_vals)*0.03), f"{round(v, 1)}m", ha="center", fontweight="bold", fontsize=8.5)
        ax2.set_ylim(0, max(dur_vals) * 1.2)
        ax2.spines["top"].set_visible(False)
        ax2.spines["right"].set_visible(False)
        
        cohort_file = output_dir / f"{clean_app_id}_cohort.png"
        plt.tight_layout()
        plt.savefig(cohort_file)
        plt.close(fig)
        chart_paths["cohort_chart"] = str(cohort_file)

    # 6. App Version Distribution Donut Chart
    versions = analytics_data.get("app_versions", [])
    if versions:
        v_labels = [v["appVersion"] for v in versions[:4]]
        v_counts = [v["activeUsers"] for v in versions[:4]]
        
        fig, ax = plt.subplots(figsize=(6, 3), dpi=200)
        colors = ["#4f46e5", "#ec4899", "#f59e0b", "#10b981"][:len(v_labels)]
        
        wedges, texts, autotexts = ax.pie(
            v_counts, labels=v_labels, autopct="%1.1f%%",
            startangle=140, colors=colors, textprops=dict(color="#0f172a", fontsize=8.5),
            wedgeprops=dict(width=0.45, edgecolor="#ffffff", linewidth=2)
        )
        for at in autotexts:
            at.set_color("#ffffff")
            at.set_fontsize(7.5)
            at.set_weight("bold")
            
        ax.set_title(f"{app_name} — App Version Distribution", fontsize=10.5, fontweight="bold", pad=8, color="#0f172a")
        
        version_file = output_dir / f"{clean_app_id}_version.png"
        plt.tight_layout()
        plt.savefig(version_file)
        plt.close(fig)
        chart_paths["version_chart"] = str(version_file)

    return chart_paths
