"""
Visual HTML Dashboard Generator
Renders one self-contained HTML file with every section of the PDF report plus
App Store Connect income metrics. Charts are inline SVG and the period tabs are
pure CSS, so the file also works offline and in phone file previews where
scripts do not run.
"""

import html
import math
from pathlib import Path

import markdown

from appstore_income import PERIODS
from charts import funnel_stages

SERIES_COLORS = ["var(--s1)", "var(--s2)", "var(--s3)", "var(--s4)", "var(--s5)", "var(--s6)", "var(--s7)", "var(--s8)"]

CSS = """
:root {
    color-scheme: light;
    --page: #f9f9f7; --surface: #fcfcfb; --ink: #0b0b0b; --ink-2: #52514e; --muted: #6f6d68;
    --grid: #e1e0d9; --axis: #c3c2b7; --border: rgba(11,11,11,0.10); --wash: #f0efec;
    --up: #006300; --down: #b92f2f;
    --s1: #2a78d6; --s2: #eb6834; --s3: #1baf7a; --s4: #eda100;
    --s5: #e87ba4; --s6: #008300; --s7: #6250d6; --s8: #e34948;
}
@media (prefers-color-scheme: dark) {
    :root:where(:not([data-theme="light"])) {
        color-scheme: dark;
        --page: #0d0d0d; --surface: #1a1a19; --ink: #f0efec; --ink-2: #c3c2b7; --muted: #a09e96;
        --grid: #2c2c2a; --axis: #383835; --border: rgba(255,255,255,0.10); --wash: #262624;
        --up: #0ca30c; --down: #e66767;
        --s1: #3987e5; --s2: #d95926; --s3: #199e70; --s4: #c98500;
        --s5: #d55181; --s6: #008300; --s7: #9085e9; --s8: #e66767;
    }
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--page); color: var(--ink); font: 15px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; }
.wrap { max-width: 1120px; margin: 0 auto; padding: 24px 16px 64px; }
header h1 { font-size: 26px; margin: 0 0 4px; letter-spacing: -0.01em; }
.sub, .note { color: var(--ink-2); font-size: 13px; }
nav { display: flex; flex-wrap: wrap; gap: 6px 14px; margin: 14px 0 26px; font-size: 13px; }
a { color: var(--s1); }
section { margin-top: 36px; }
h2 { font-size: 21px; margin: 0 0 12px; padding-top: 10px; border-top: 2px solid var(--ink); }
h3 { font-size: 15px; margin: 0 0 10px; }
.grid { display: grid; gap: 12px; grid-template-columns: repeat(auto-fit, minmax(min(100%, 460px), 1fr)); }
.tiles { display: grid; gap: 10px; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); margin-bottom: 12px; }
.card, .tile { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; }
.card { padding: 16px; min-width: 0; }
.card.wide { grid-column: 1 / -1; }
.tile { padding: 12px 14px; }
.tile .label { color: var(--ink-2); font-size: 13px; }
.tile .value { font-size: 23px; font-weight: 600; margin-top: 2px; }
.delta { font-size: 13px; font-weight: 500; }
.delta.up { color: var(--up); } .delta.down { color: var(--down); } .delta.flat { color: var(--muted); }
.tabs { display: flex; gap: 2px; background: var(--wash); padding: 3px; border-radius: 10px; margin-bottom: 14px; width: fit-content; max-width: 100%; overflow-x: auto; }
.tabs label { padding: 5px 15px; border-radius: 8px; font-size: 13px; cursor: pointer; color: var(--ink-2); white-space: nowrap; }
.period-radio { position: absolute; opacity: 0; pointer-events: none; }
.panel { display: none; }
.bar-row { display: grid; grid-template-columns: minmax(0, 2fr) minmax(0, 2fr) auto; gap: 10px; align-items: center; font-size: 13px; padding: 4px 0; }
.bar-label { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--ink-2); }
.bar-track { height: 12px; }
.bar-fill { height: 100%; min-width: 2px; background: var(--s1); border-radius: 0 4px 4px 0; }
.bar-value { font-variant-numeric: tabular-nums; text-align: right; white-space: nowrap; }
.stack { display: flex; gap: 2px; height: 18px; margin-bottom: 10px; }
.stack div { min-width: 3px; }
.stack div:first-child { border-radius: 4px 0 0 4px; } .stack div:last-child { border-radius: 0 4px 4px 0; }
.legend { display: flex; flex-wrap: wrap; gap: 4px 14px; font-size: 13px; color: var(--ink-2); }
.key { display: inline-block; width: 10px; height: 10px; border-radius: 2px; margin-right: 5px; }
.scroll { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th { text-align: left; font-weight: 600; color: var(--ink-2); border-bottom: 1px solid var(--axis); padding: 6px 8px; white-space: nowrap; }
td { border-bottom: 1px solid var(--grid); padding: 6px 8px; }
td.n, th.n { text-align: right; font-variant-numeric: tabular-nums; }
.chart { overflow-x: auto; }
svg { display: block; width: 100%; min-width: 420px; max-width: 720px; margin: 0 auto; height: auto; }
svg text { font: 12px system-ui, -apple-system, "Segoe UI", sans-serif; fill: var(--muted); }
svg text.end-label { fill: var(--ink); font-weight: 600; }
.notice { background: var(--surface); border: 1px solid var(--border); border-left: 4px solid var(--s4); border-radius: 8px; padding: 12px 14px; }
.empty { color: var(--muted); font-size: 13px; }
details > summary { cursor: pointer; font-size: 13px; color: var(--ink-2); margin-top: 8px; }
.prose { overflow-x: auto; }
.prose table { margin: 10px 0; } .prose pre { background: var(--wash); padding: 10px; overflow-x: auto; border-radius: 6px; font-size: 12px; }
.prose h1 { font-size: 21px; } .prose h2 { font-size: 18px; border-top: 0; } .prose h3 { font-size: 15px; margin-top: 16px; }
@media (max-width: 560px) { .bar-row { grid-template-columns: minmax(0, 1fr) auto; } .bar-track { grid-column: 1 / -1; grid-row: 2; } }
@media print { .tabs { display: none; } nav { display: none; } }
"""


def esc(value):
    return html.escape(str(value), quote=True)


def _float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def usd(value):
    return f"${_float(value):,.2f}"


def integer(value):
    return f"{int(_float(value)):,}"


def percent_of_one(value):
    return f"{_float(value) * 100:.1f}%"


def delta_html(pct):
    if pct > 0:
        return f'<span class="delta up">↗ {pct:.1f}%</span>'
    if pct < 0:
        return f'<span class="delta down">↘ {abs(pct):.1f}%</span>'
    return '<span class="delta flat">0.0%</span>'


def tile(label, value, delta=""):
    return f'<div class="tile"><div class="label">{esc(label)}</div><div class="value">{esc(value)}</div>{delta}</div>'


def table(headers, rows, numeric=()):
    """Renders a table; columns whose index is in numeric are right-aligned."""
    head = "".join(f'<th class="n">{esc(h)}</th>' if i in numeric else f"<th>{esc(h)}</th>" for i, h in enumerate(headers))
    body = ""
    for row in rows:
        body += "<tr>" + "".join(
            f'<td class="n">{cell}</td>' if i in numeric else f"<td>{cell}</td>" for i, cell in enumerate(row)
        ) + "</tr>"
    return f'<div class="scroll"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def bars(items):
    """Horizontal bars from (label, number, display_value) tuples, on a shared zero baseline."""
    if not items:
        return '<p class="empty">No data for this period.</p>'
    top = max((_float(i[1]) for i in items), default=0) or 1
    rows = ""
    for label, number, display in items:
        width = max(_float(number), 0) / top * 100
        rows += (
            f'<div class="bar-row" title="{esc(label)}: {esc(display)}"><div class="bar-label">{esc(label)}</div>'
            f'<div class="bar-track"><div class="bar-fill" style="width:{width:.1f}%"></div></div>'
            f'<div class="bar-value">{esc(display)}</div></div>'
        )
    return rows


def share_bar(items):
    """100% stacked bar with a legend, from (label, number) tuples. Folds past seven parts into Other."""
    items = [(label, _float(number)) for label, number in items if _float(number) > 0]
    if not items:
        return '<p class="empty">No data for this period.</p>'
    if len(items) > 8:
        items = items[:7] + [("Other", sum(n for _, n in items[7:]))]
    total = sum(n for _, n in items)
    segments, legend = "", ""
    for index, (label, number) in enumerate(items):
        color = SERIES_COLORS[index]
        share = number / total * 100
        segments += f'<div style="flex:{number} 1 0;background:{color}" title="{esc(label)}: {number:,.0f} ({share:.1f}%)"></div>'
        legend += f'<span><i class="key" style="background:{color}"></i>{esc(label)} · {number:,.0f} ({share:.1f}%)</span>'
    return f'<div class="stack">{segments}</div><div class="legend">{legend}</div>'


def nice_step(raw_step, whole=False):
    """Rounds an axis step up to 1, 2, 2.5 or 5 times a power of ten, so ticks land on readable values."""
    if raw_step <= 0:
        return 1
    magnitude = 10 ** math.floor(math.log10(raw_step))
    step = next(m * magnitude for m in (1, 2, 2.5, 5, 10) if m * magnitude >= raw_step - 1e-9)
    return max(1, math.ceil(step)) if whole else step


def line_chart(dates, series, money=False):
    """
    Line chart on one y-axis. series is a list of (name, values). Each date column
    has a hover target listing every series value; line ends are labelled directly.
    """
    if len(dates) < 2:
        return '<p class="empty">Not enough days to draw a trend.</p>'
    width, height = 520, 220
    left, right, top, bottom = 46, 62, 12, 24
    plot_w, plot_h = width - left - right, height - top - bottom
    peak = max((max(values) for _, values in series), default=0)
    low = min(0, min((min(values) for _, values in series), default=0))
    step_size = nice_step((peak - low) / 4, whole=not money)
    low = math.floor(low / step_size) * step_size
    tick_steps = max(1, math.ceil((peak - low) / step_size))
    span = step_size * tick_steps

    def fmt(value):
        return f"${value:,.2f}" if money else f"{value:,.0f}"

    def x(i):
        return left + plot_w * i / (len(dates) - 1)

    def y(value):
        return top + plot_h * (1 - (value - low) / span)

    parts = [f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="{esc(", ".join(s[0] for s in series))} by day">']
    for step in range(tick_steps + 1):
        value = low + step_size * step
        parts.append(f'<line x1="{left}" x2="{width - right}" y1="{y(value):.1f}" y2="{y(value):.1f}" stroke="var(--{"axis" if step == 0 else "grid"})"/>')
        label = (f"${value:,.0f}" if float(value).is_integer() else f"${value:,.2f}") if money else f"{value:,.0f}"
        parts.append(f'<text x="{left - 6}" y="{y(value) + 4:.1f}" text-anchor="end">{label}</text>')
    tick_count = len(dates) if len(dates) <= 8 else 5
    for tick in range(tick_count):
        i = round(tick * (len(dates) - 1) / (tick_count - 1))
        anchor = "start" if i == 0 else "end" if i == len(dates) - 1 else "middle"
        parts.append(f'<text x="{x(i):.1f}" y="{height - 8}" text-anchor="{anchor}">{esc(dates[i][5:])}</text>')

    end_positions = []
    for index, (name, values) in enumerate(series):
        color = SERIES_COLORS[index]
        points = " ".join(f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(values))
        parts.append(f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>')
        parts.append(f'<circle cx="{x(len(values) - 1):.1f}" cy="{y(values[-1]):.1f}" r="4" fill="{color}" stroke="var(--surface)" stroke-width="2"/>')
        end_positions.append([y(values[-1]) + 4, fmt(values[-1])])
    # Keep end labels from colliding when series finish close together.
    end_positions.sort(key=lambda p: p[0])
    for i in range(1, len(end_positions)):
        end_positions[i][0] = max(end_positions[i][0], end_positions[i - 1][0] + 13)
    for label_y, text in end_positions:
        parts.append(f'<text class="end-label" x="{width - right + 8}" y="{label_y:.1f}">{esc(text)}</text>')

    column = plot_w / (len(dates) - 1)
    for i, day in enumerate(dates):
        detail = " · ".join(f"{name}: {fmt(values[i])}" for name, values in series)
        parts.append(f'<rect x="{x(i) - column / 2:.1f}" y="{top}" width="{column:.1f}" height="{plot_h}" fill="transparent"><title>{esc(day)} — {esc(detail)}</title></rect>')
    parts.append("</svg>")

    legend = ""
    if len(series) > 1:
        keys = "".join(f'<span><i class="key" style="background:{SERIES_COLORS[i]}"></i>{esc(name)}</span>' for i, (name, _) in enumerate(series))
        legend = f'<div class="legend" style="margin-bottom:6px">{keys}</div>'
    return f'{legend}<div class="chart">{"".join(parts)}</div>'


def income_panel(label, period, context_daily):
    metrics = period["metrics"]
    tiles = [
        ("Units", integer(metrics["units"]["value"]), metrics["units"]),
        ("Proceeds", usd(metrics["proceeds"]["value"]), metrics["proceeds"]),
        ("Sales", usd(metrics["sales"]["value"]), metrics["sales"]),
        ("Updates", integer(metrics["updates"]["value"]), metrics["updates"]),
        ("In-App Purchases", integer(metrics["iap"]["value"]), metrics["iap"]),
        ("App Bundles", integer(metrics["bundles"]["value"]), metrics["bundles"]),
        ("Pre-Orders", integer(metrics["preorders"]["value"]), metrics["preorders"]),
        ("Redownloads", integer(metrics["redownloads"]["value"]), metrics["redownloads"]),
        ("Refunds", integer(metrics["refunds"]["value"]), None),
    ]
    tiles_html = "".join(tile(name, value, delta_html(m["change_pct"]) if m else "") for name, value, m in tiles)

    range_text = period["end"] if period["days"] == 1 else f'{period["start"]} to {period["end"]}'
    daily = period["daily"] if period["days"] > 1 else context_daily
    caption = "last 7 days for context" if period["days"] == 1 else range_text
    dates = [d["date"] for d in daily]

    subs = period["subscriptions"]
    product_rows = [
        [esc(p["title"]), esc(p["app"]), integer(p["units"]), usd(p["proceeds"]), usd(p["sales"]), delta_html(p["change_pct"])]
        for p in period["products"]
    ]
    territory_rows = [
        [esc(t["name"]), integer(t["units"]), usd(t["proceeds"]), usd(t["sales"]), delta_html(t["change_pct"])]
        for t in period["territories"]
    ]
    return f"""
    <div class="panel panel-{label}">
        <p class="sub">{esc(range_text)}, compared with the {"day" if period["days"] == 1 else str(period["days"]) + " days"} before it.</p>
        <div class="tiles">{tiles_html}</div>
        <div class="grid">
            <div class="card wide"><h3>Proceeds and sales per day, USD ({esc(caption)})</h3>
                {line_chart(dates, [("Sales", [d["sales"] for d in daily]), ("Proceeds", [d["proceeds"] for d in daily])], money=True)}</div>
            <div class="card"><h3>Units per day ({esc(caption)})</h3>{line_chart(dates, [("Units", [d["units"] for d in daily])])}</div>
            <div class="card"><h3>In-app purchases per day ({esc(caption)})</h3>{line_chart(dates, [("In-app purchases", [d["iap"] for d in daily])])}</div>
            <div class="card"><h3>Proceeds by product</h3>{bars([(p["title"], p["proceeds"], usd(p["proceeds"])) for p in period["products"][:10]])}</div>
            <div class="card"><h3>Proceeds by territory</h3>{bars([(t["name"], t["proceeds"], usd(t["proceeds"])) for t in period["territories"][:10]])}</div>
            <div class="card"><h3>Proceeds by app</h3>{bars([(a["name"], a["proceeds"], usd(a["proceeds"])) for a in period["apps"]])}</div>
            <div class="card"><h3>Subscription proceeds, new and renewal</h3>
                {bars([("New", subs["new"]["proceeds"], f'{usd(subs["new"]["proceeds"])} · {subs["new"]["units"]} units'), ("Renewal", subs["renewal"]["proceeds"], f'{usd(subs["renewal"]["proceeds"])} · {subs["renewal"]["units"]} units')])}</div>
            <div class="card wide"><h3>Products</h3>{table(["Product", "App", "Units", "Proceeds", "Sales", "Change"], product_rows, numeric=(2, 3, 4, 5)) if product_rows else '<p class="empty">No purchases in this period.</p>'}</div>
            <div class="card wide"><h3>Territories</h3>{table(["Territory", "Units", "Proceeds", "Sales", "Change"], territory_rows, numeric=(1, 2, 3, 4)) if territory_rows else '<p class="empty">No purchases in this period.</p>'}</div>
        </div>
    </div>"""


def income_section(income):
    status = income.get("status")
    if status != "ok":
        reason = "App Store Connect is not connected yet." if status == "not_configured" else "App Store Connect data could not be loaded for this report."
        return f"""<section id="income"><h2>Income</h2>
        <div class="notice"><strong>{esc(reason)}</strong> <span class="note">{esc(income.get("message", ""))}</span><br>
        <span class="note">The per-app revenue figures further down come from GA4 purchase events, not from Apple.</span></div></section>"""

    labels = [label for label, _ in PERIODS]
    context_daily = income["periods"]["7D"]["daily"]
    radios = "".join(
        f'<input class="period-radio" type="radio" name="period" id="period-{label}" aria-label="{label}"{" checked" if i == 0 else ""}>'
        for i, label in enumerate(labels)
    )
    tabs = "".join(f'<label for="period-{label}">{label}</label>' for label in labels)
    panels = "".join(income_panel(label, income["periods"][label], context_daily) for label in labels)
    rules = "".join(
        f"#period-{label}:checked ~ .panels .panel-{label} {{ display: block; }}"
        f"#period-{label}:checked ~ .tabs label[for=period-{label}] {{ background: var(--surface); color: var(--ink); font-weight: 600; }}"
        for label in labels
    )
    warnings = "".join(f'<div class="notice note">{esc(w)}</div>' for w in income.get("warnings", []))
    return f"""<section id="income"><h2>Income</h2>
    <style>{rules}</style>
    <p class="note">{esc(income["source"])}, newest report {esc(income["as_of"])}. {esc(income["note"])}</p>
    {warnings}
    {radios}<div class="tabs">{tabs}</div><div class="panels">{panels}</div></section>"""


def app_section(app, index):
    name = app.get("app_name", "App")
    overview = app.get("yesterday_overview", {})
    horizons = app.get("multi_horizon_benchmarks", [])
    trend = app.get("past_7_days_trend", [])
    products = app.get("product_sales_30d", [])
    transactions = app.get("recent_transactions", [])
    cohorts = app.get("new_vs_returning_cohorts", [])
    events = app.get("top_events_telemetry", [])
    versions = app.get("app_versions", [])
    geo = app.get("geographic_distribution", [])
    testers = app.get("internal_tester_summary", {})
    funnel = funnel_stages(events)

    tiles = "".join([
        tile("Active users", integer(overview.get("activeUsers"))),
        tile("New users", integer(overview.get("newUsers"))),
        tile("Sessions", integer(overview.get("sessions"))),
        tile("Screen views", integer(overview.get("screenPageViews"))),
        tile("Engagement rate", percent_of_one(overview.get("engagementRate"))),
        tile("Avg session", f'{_float(overview.get("averageSessionDuration")) / 60:.1f} min'),
        tile("Events per session", f'{_float(overview.get("eventsPerSession")):.1f}'),
        tile("Bounce rate", percent_of_one(overview.get("bounceRate"))),
        tile("Crash-free users", f'{_float(overview.get("crashFreeUsersRate")) * 100:.2f}%'),
        tile("GA4 revenue", usd(overview.get("purchaseRevenue"))),
    ])

    total_revenue = sum(p["revenue_usd"] for p in products) or 1
    # GA4 splits one product across its localized names, so the chart groups by product ID.
    by_product = {}
    for p in products:
        entry = by_product.setdefault(p["item_id"], {"revenue": 0.0, "quantity": 0})
        entry["revenue"] += p["revenue_usd"]
        entry["quantity"] += p["quantity"]
    product_bars = sorted(by_product.items(), key=lambda item: -item[1]["revenue"])
    product_rows = [
        [f'<code>{esc(p["item_id"])}</code>', esc(p["item_name"]), integer(p["quantity"]), usd(p["revenue_usd"]), f'{p["revenue_usd"] / total_revenue * 100:.1f}%']
        for p in products
    ]
    transaction_rows = [
        [esc(t["date"]), esc(t["app_version"]), esc(t["product_name"] or t["product_id"]), esc(t["country"]), integer(t["quantity"]), usd(t["revenue_usd"])]
        for t in transactions
    ]
    horizon_rows = [
        [esc(h["horizon"]), integer(h["activeUsers"]), integer(h["newUsers"]), integer(h["sessions"]), esc(h["engagementRate"]), usd(h["revenue_usd"])]
        for h in horizons
    ]
    cohort_rows = [
        [esc(c["user_type"]), integer(c["activeUsers"]), integer(c["sessions"]), f'{c["avgSessionDuration_sec"] / 60:.1f} min', esc(c["engagementRate"]), integer(c["screenPageViews"])]
        for c in cohorts
    ]
    version_rows = [
        [esc(v["appVersion"]), integer(v["activeUsers"]), integer(v["sessions"]), esc(v["engagementRate"]), esc(v["crashFreeUsersRate"])]
        for v in versions
    ]
    event_rows = [
        [esc(e["eventName"]), integer(e["eventCount"]), integer(e["totalUsers"]), f'{e["eventsPerUser"]:.1f}']
        for e in events
    ]
    base = funnel[0][1] if funnel else 1
    trend_dates = [d["date"] for d in trend]

    return f"""<section id="app-{index}"><h2>{esc(name)}</h2>
    <p class="note">{esc(app.get("data_scope", ""))}. Tiles show yesterday.</p>
    <div class="tiles">{tiles}</div>
    <div class="grid">
        <div class="card wide"><h3>Users per day, last 7 days</h3>{line_chart(trend_dates, [("Active users", [d["activeUsers"] for d in trend]), ("New users", [d["newUsers"] for d in trend])])}</div>
        <div class="card wide"><h3>Growth across time horizons</h3>{table(["Horizon", "Active users", "New users", "Sessions", "Engagement", "GA4 revenue"], horizon_rows, numeric=(1, 2, 3, 4, 5))}</div>
        <div class="card"><h3>Conversion funnel, yesterday</h3>{bars([(stage, count, f"{count:,} ({count / base * 100:.1f}%)") for stage, count in funnel])}</div>
        <div class="card"><h3>GA4 product revenue, last 30 days</h3>{bars([(item_id, v["revenue"], f'{usd(v["revenue"])} · {v["quantity"]} sold') for item_id, v in product_bars[:8]])}</div>
        <div class="card"><h3>New and returning users</h3>{share_bar([(c["user_type"], c["activeUsers"]) for c in cohorts])}<div style="margin-top:10px">{table(["Type", "Users", "Sessions", "Avg session", "Engaged", "Views"], cohort_rows, numeric=(1, 2, 3, 4, 5))}</div></div>
        <div class="card"><h3>App versions</h3>{share_bar([(v["appVersion"], v["activeUsers"]) for v in versions])}<div style="margin-top:10px">{table(["Version", "Users", "Sessions", "Engaged", "Crash-free"], version_rows, numeric=(1, 2, 3, 4))}</div></div>
        <div class="card"><h3>Top countries, yesterday</h3>{bars([(g["country"], g["activeUsers"], f'{g["activeUsers"]:,} users') for g in geo])}</div>
        <div class="card"><h3>Top events, yesterday</h3>{bars([(e["eventName"], e["eventCount"], f'{e["eventCount"]:,}') for e in events[:10]])}
            <details><summary>All {len(events)} events</summary>{table(["Event", "Count", "Users", "Per user"], event_rows, numeric=(1, 2, 3))}</details></div>
        <div class="card wide"><h3>GA4 products, last 30 days</h3>{table(["Product ID", "Name", "Units", "Revenue", "Share"], product_rows, numeric=(2, 3, 4)) if product_rows else '<p class="empty">No purchases recorded.</p>'}</div>
        <div class="card wide"><h3>Recent transactions</h3>{table(["Date", "Version", "Product", "Country", "Units", "Revenue"], transaction_rows, numeric=(4, 5)) if transaction_rows else '<p class="empty">No transactions recorded.</p>'}</div>
        <div class="card wide"><h3>Internal testers</h3>
            <p class="note">{esc(testers.get("note", ""))}</p>
            <div class="tiles" style="margin:0">{tile("Active users", integer(testers.get("activeUsers")))}{tile("New users", integer(testers.get("newUsers")))}{tile("Sessions", integer(testers.get("sessions")))}{tile("GA4 revenue", usd(testers.get("purchaseRevenue")))}</div></div>
    </div></section>"""


def portfolio_section(all_apps_data):
    rows = []
    for app in all_apps_data:
        overview = app.get("yesterday_overview", {})
        revenue_30d = next((h["revenue_usd"] for h in app.get("multi_horizon_benchmarks", []) if h["horizon"] == "Past 30 Days"), 0)
        rows.append([
            esc(app.get("app_name", "App")), integer(overview.get("activeUsers")), integer(overview.get("newUsers")),
            integer(overview.get("sessions")), percent_of_one(overview.get("engagementRate")),
            f'{_float(overview.get("crashFreeUsersRate")) * 100:.2f}%', usd(revenue_30d),
        ])
    return f"""<section id="portfolio"><h2>Portfolio, yesterday</h2><div class="card">
    {table(["App", "Active users", "New users", "Sessions", "Engagement", "Crash-free", "GA4 revenue, 30d"], rows, numeric=(1, 2, 3, 4, 5, 6))}</div></section>"""


def render_dashboard(all_apps_data, income, ai_markdown, target_date, output_path):
    """Writes the dashboard to output_path and returns that path."""
    nav_links = ['<a href="#income">Income</a>', '<a href="#portfolio">Portfolio</a>']
    nav_links += [f'<a href="#app-{i}">{esc(a.get("app_name", "App"))}</a>' for i, a in enumerate(all_apps_data)]
    nav_links.append('<a href="#analysis">AI analysis</a>')
    apps_html = "".join(app_section(app, i) for i, app in enumerate(all_apps_data))
    analysis = markdown.markdown(ai_markdown, extensions=["tables", "fenced_code", "nl2br"])

    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Neural Sound Dashboard {esc(target_date)}</title>
<style>{CSS}</style>
</head>
<body>
<div class="wrap">
    <header><h1>Neural Sound daily report</h1><div class="sub">{esc(target_date)}</div></header>
    <nav>{"".join(nav_links)}</nav>
    {income_section(income)}
    {portfolio_section(all_apps_data)}
    {apps_html}
    <section id="analysis"><h2>AI analysis</h2><div class="card prose">{analysis}</div></section>
</div>
</body>
</html>"""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(page, encoding="utf-8")
    print(f"✅ Generated Visual Dashboard: {output_path}")
    return output_path
