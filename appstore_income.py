"""
App Store Connect Income Module
Downloads daily Sales & Trends reports through the App Store Connect API and
aggregates them into the metrics shown by the App Store Connect "Trends" screen:
Units, Proceeds, Sales, Updates, In-App Purchases, App Bundles and Pre-Orders,
with per-product and per-territory breakdowns over 1D / 7D / 2W / 5W / 13W / 26W.

Run directly to check one day against the Trends screen:
    ./venv/bin/python appstore_income.py --date 2026-10-29
"""

import argparse
import csv
import gzip
import io
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from pathlib import Path

import jwt
import requests
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

SALES_REPORTS_URL = "https://api.appstoreconnect.apple.com/v1/salesReports"
FX_TIMESERIES_URL = "https://api.frankfurter.dev/v1/{start}..{end}"
FX_LATEST_URL = "https://open.er-api.com/v6/latest/USD"
CACHE_DIR = BASE_DIR / ".income_cache"

PERIODS = [("1D", 1), ("7D", 7), ("2W", 14), ("5W", 35), ("13W", 91), ("26W", 182)]
LATEST_DATE_LOOKBACK_DAYS = 7

# Product Type Identifiers from Apple's Sales & Trends report reference.
APP_TYPES = {"1", "1F", "1T", "F1", "1E", "1EP", "1EU"}
UPDATE_TYPES = {"7", "7F", "7T", "F7"}
REDOWNLOAD_TYPES = {"3", "3F", "3T", "F3"}
IAP_TYPES = {"IA1", "IA9", "IAY", "IAC", "FI1"}
BUNDLE_TYPES = {"1-B", "F1-B", "1E-B", "1EP-B", "1EU-B"}

COUNTRY_NAMES = {
    "AE": "United Arab Emirates", "AR": "Argentina", "AT": "Austria", "AU": "Australia",
    "BD": "Bangladesh", "BE": "Belgium", "BR": "Brazil", "CA": "Canada", "CH": "Switzerland",
    "CL": "Chile", "CN": "China", "CO": "Colombia", "CZ": "Czechia", "DE": "Germany",
    "DK": "Denmark", "EG": "Egypt", "ES": "Spain", "FI": "Finland", "FR": "France",
    "GB": "United Kingdom", "GR": "Greece", "HK": "Hong Kong", "HU": "Hungary", "ID": "Indonesia",
    "IE": "Ireland", "IL": "Israel", "IN": "India", "IT": "Italy", "JP": "Japan",
    "KR": "Korea, Republic of", "KW": "Kuwait", "MX": "Mexico", "MY": "Malaysia", "NG": "Nigeria",
    "NL": "Netherlands", "NO": "Norway", "NZ": "New Zealand", "PE": "Peru", "PH": "Philippines",
    "PK": "Pakistan", "PL": "Poland", "PT": "Portugal", "QA": "Qatar", "RO": "Romania",
    "RU": "Russia", "SA": "Saudi Arabia", "SE": "Sweden", "SG": "Singapore", "TH": "Thailand",
    "TR": "Türkiye", "TW": "Taiwan", "UA": "Ukraine", "US": "United States", "VN": "Vietnam",
    "ZA": "South Africa",
}


def get_credentials():
    """Returns App Store Connect credentials from .env, or None if any are missing."""
    creds = {
        "issuer_id": os.getenv("ASC_ISSUER_ID", "").strip(),
        "key_id": os.getenv("ASC_KEY_ID", "").strip(),
        "key_path": os.getenv("ASC_PRIVATE_KEY_PATH", "").strip(),
        "vendor_number": os.getenv("ASC_VENDOR_NUMBER", "").strip(),
    }
    if not all(creds.values()):
        return None
    if not os.path.isabs(creds["key_path"]):
        creds["key_path"] = str(BASE_DIR / creds["key_path"])
    return creds


def build_token(creds):
    """Signs a short-lived ES256 JWT for the App Store Connect API."""
    with open(creds["key_path"], "r", encoding="utf-8") as f:
        private_key = f.read()
    now = int(time.time())
    return jwt.encode(
        {"iss": creds["issuer_id"], "iat": now, "exp": now + 1200, "aud": "appstoreconnect-v1"},
        private_key,
        algorithm="ES256",
        headers={"kid": creds["key_id"], "typ": "JWT"},
    )


def download_daily_report(creds, day):
    """Returns the report TSV for one day, or None if Apple has no report for that day."""
    params = {
        "filter[frequency]": "DAILY",
        "filter[reportType]": "SALES",
        "filter[reportSubType]": "SUMMARY",
        "filter[vendorNumber]": creds["vendor_number"],
        "filter[reportDate]": day.isoformat(),
        "filter[version]": os.getenv("ASC_REPORT_VERSION", "1_0"),
    }
    for attempt in range(4):
        headers = {"Authorization": f"Bearer {build_token(creds)}", "Accept": "application/a-gzip"}
        resp = requests.get(SALES_REPORTS_URL, params=params, headers=headers, timeout=60)
        if resp.status_code == 404:
            return None
        if resp.status_code == 429 or resp.status_code >= 500:
            time.sleep(2 ** attempt)
            continue
        if resp.status_code != 200:
            raise RuntimeError(f"App Store Connect returned HTTP {resp.status_code} for {day}: {resp.text[:300]}")
        return gzip.decompress(resp.content).decode("utf-8")
    raise RuntimeError(f"App Store Connect kept failing for {day} (HTTP {resp.status_code}).")


def parse_report(tsv_text):
    """Parses a Sales report TSV into row dictionaries, read by column name."""
    if not tsv_text:
        return []
    return list(csv.DictReader(io.StringIO(tsv_text), delimiter="\t"))


def load_report(creds, day, latest_day):
    """
    Returns parsed rows for a day using the local cache. A 404 before the latest
    available day means there were no sales, so it is cached as an empty report.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = CACHE_DIR / f"sales_{day.isoformat()}.tsv"
    if cache_file.exists():
        return parse_report(cache_file.read_text(encoding="utf-8"))
    tsv_text = download_daily_report(creds, day)
    if tsv_text is not None or day < latest_day:
        cache_file.write_text(tsv_text or "", encoding="utf-8")
    return parse_report(tsv_text)


def find_latest_report_day(creds, today=None):
    """Walks back from yesterday to the newest day Apple has published."""
    today = today or date.today()
    for offset in range(1, LATEST_DATE_LOOKBACK_DAYS + 1):
        day = today - timedelta(days=offset)
        if (CACHE_DIR / f"sales_{day.isoformat()}.tsv").exists():
            return day
        if load_report(creds, day, latest_day=date.min) or (CACHE_DIR / f"sales_{day.isoformat()}.tsv").exists():
            return day
    return None


def load_fx_rates(start, end, currencies):
    """
    Returns {date: {currency: units per USD}} using ECB daily rates, with a
    latest-rate fallback for currencies the ECB does not publish.
    """
    resp = requests.get(
        FX_TIMESERIES_URL.format(start=(start - timedelta(days=7)).isoformat(), end=end.isoformat()),
        params={"base": "USD"},
        timeout=30,
    )
    resp.raise_for_status()
    rates_by_date = resp.json().get("rates", {})

    known = {c for rates in rates_by_date.values() for c in rates} | {"USD"}
    fallback = {}
    if set(currencies) - known:
        fallback_resp = requests.get(FX_LATEST_URL, timeout=30)
        fallback_resp.raise_for_status()
        fallback = fallback_resp.json().get("rates", {})
    return rates_by_date, fallback


def to_usd(amount, currency, day, rates_by_date, fallback, missing):
    """Converts an amount to USD using the rate on or just before the given day."""
    if not amount or currency == "USD":
        return amount
    for offset in range(8):
        rates = rates_by_date.get((day - timedelta(days=offset)).isoformat())
        if rates and currency in rates:
            return amount / rates[currency]
    if currency in fallback:
        return amount / fallback[currency]
    missing.add(currency)
    return 0.0


def _number(value):
    try:
        return float(value or 0)
    except ValueError:
        return 0.0


def normalize_rows(reports_by_day, rates_by_date, fallback, missing):
    """Flattens raw report rows into USD-valued records, one per report row."""
    # IAP rows point at their app through Parent Identifier, so map app SKUs to titles first.
    app_titles = {}
    for rows in reports_by_day.values():
        for row in rows:
            if row.get("Product Type Identifier", "").strip() in APP_TYPES | UPDATE_TYPES | REDOWNLOAD_TYPES:
                app_titles[row.get("SKU", "").strip()] = row.get("Title", "").strip()

    records = []
    for day, rows in reports_by_day.items():
        for row in rows:
            units = _number(row.get("Units"))
            # Refund rows can carry negative prices as well as negative units, so the sign comes from units only.
            proceeds = units * abs(_number(row.get("Developer Proceeds")))
            sales = units * abs(_number(row.get("Customer Price")))
            sku = row.get("SKU", "").strip()
            parent = row.get("Parent Identifier", "").strip()
            records.append({
                "day": day,
                "type": row.get("Product Type Identifier", "").strip(),
                "sku": sku,
                "title": row.get("Title", "").strip(),
                "app": app_titles.get(parent) or app_titles.get(sku) or parent or row.get("Title", "").strip(),
                "country": row.get("Country Code", "").strip(),
                "units": units,
                "proceeds": to_usd(proceeds, row.get("Currency of Proceeds", "").strip(), day, rates_by_date, fallback, missing),
                "sales": to_usd(sales, row.get("Customer Currency", "").strip(), day, rates_by_date, fallback, missing),
                "subscription": row.get("Subscription", "").strip(),
                "preorder": "pre" in row.get("Order Type", "").strip().lower(),
            })
    return records


def change_pct(current, previous):
    """Period-over-period change, matching App Store Connect: rising from zero reads as 100%."""
    if previous == 0:
        return 0.0 if current == 0 else (100.0 if current > 0 else -100.0)
    return round((current - previous) / abs(previous) * 100, 1)


def _metric(current, previous, digits=0):
    return {
        "value": round(current, digits) if digits else int(round(current)),
        "previous": round(previous, digits) if digits else int(round(previous)),
        "change_pct": change_pct(round(current, 2), round(previous, 2)),
    }


def _totals(records):
    def units_of(types):
        return sum(r["units"] for r in records if r["type"] in types)
    return {
        "units": units_of(APP_TYPES),
        "proceeds": sum(r["proceeds"] for r in records),
        "sales": sum(r["sales"] for r in records),
        "updates": units_of(UPDATE_TYPES),
        "iap": units_of(IAP_TYPES),
        "bundles": units_of(BUNDLE_TYPES),
        "preorders": sum(r["units"] for r in records if r["preorder"]),
        "redownloads": units_of(REDOWNLOAD_TYPES),
        "refunds": -sum(r["units"] for r in records if r["units"] < 0),
    }


def _group(current, previous, key_fn, describe_fn):
    """Groups records by key, totals them, and adds proceeds change against the previous window."""
    groups = {}
    for r in current:
        g = groups.setdefault(key_fn(r), {"units": 0.0, "proceeds": 0.0, "sales": 0.0, "previous_proceeds": 0.0, **describe_fn(r)})
        g["units"] += r["units"]
        g["proceeds"] += r["proceeds"]
        g["sales"] += r["sales"]
    for r in previous:
        if key_fn(r) in groups:
            groups[key_fn(r)]["previous_proceeds"] += r["proceeds"]
    result = []
    for g in groups.values():
        g["change_pct"] = change_pct(round(g["proceeds"], 2), round(g["previous_proceeds"], 2))
        g["units"] = int(round(g["units"]))
        g["proceeds"] = round(g["proceeds"], 2)
        g["sales"] = round(g["sales"], 2)
        del g["previous_proceeds"]
        result.append(g)
    return sorted(result, key=lambda g: (-g["proceeds"], -g["units"]))


def build_period(records, latest_day, days):
    """Builds every metric and breakdown for one trailing window against the window before it."""
    start = latest_day - timedelta(days=days - 1)
    prev_end = start - timedelta(days=1)
    prev_start = prev_end - timedelta(days=days - 1)
    current = [r for r in records if start <= r["day"] <= latest_day]
    previous = [r for r in records if prev_start <= r["day"] <= prev_end]
    cur, prev = _totals(current), _totals(previous)

    money = [r for r in current if r["type"] in IAP_TYPES or r["proceeds"] or r["sales"]]
    money_prev = [r for r in previous if r["type"] in IAP_TYPES or r["proceeds"] or r["sales"]]

    daily = []
    for offset in range(days):
        day = start + timedelta(days=offset)
        totals = _totals([r for r in current if r["day"] == day])
        daily.append({
            "date": day.isoformat(),
            "units": int(round(totals["units"])),
            "proceeds": round(totals["proceeds"], 2),
            "sales": round(totals["sales"], 2),
            "iap": int(round(totals["iap"])),
        })

    subscriptions = {"new": {"units": 0, "proceeds": 0.0}, "renewal": {"units": 0, "proceeds": 0.0}}
    for r in current:
        if r["subscription"]:
            bucket = subscriptions["renewal" if r["subscription"].lower().startswith("renew") else "new"]
            bucket["units"] += int(r["units"])
            bucket["proceeds"] = round(bucket["proceeds"] + r["proceeds"], 2)

    return {
        "start": start.isoformat(),
        "end": latest_day.isoformat(),
        "days": days,
        "metrics": {
            "units": _metric(cur["units"], prev["units"]),
            "proceeds": _metric(cur["proceeds"], prev["proceeds"], 2),
            "sales": _metric(cur["sales"], prev["sales"], 2),
            "updates": _metric(cur["updates"], prev["updates"]),
            "iap": _metric(cur["iap"], prev["iap"]),
            "bundles": _metric(cur["bundles"], prev["bundles"]),
            "preorders": _metric(cur["preorders"], prev["preorders"]),
            "redownloads": _metric(cur["redownloads"], prev["redownloads"]),
            "refunds": _metric(cur["refunds"], prev["refunds"]),
        },
        "products": _group(money, money_prev, lambda r: r["sku"], lambda r: {"sku": r["sku"], "title": r["title"], "app": r["app"]}),
        "territories": _group(money, money_prev, lambda r: r["country"], lambda r: {"code": r["country"], "name": COUNTRY_NAMES.get(r["country"], r["country"])}),
        "apps": _group(current, previous, lambda r: r["app"], lambda r: {"name": r["app"]}),
        "subscriptions": subscriptions,
        "daily": daily,
    }


def build_income(reports_by_day, latest_day, rates_by_date, fallback):
    """Turns raw daily reports into the income payload used by the reports."""
    missing = set()
    records = normalize_rows(reports_by_day, rates_by_date, fallback, missing)
    income = {
        "status": "ok",
        "as_of": latest_day.isoformat(),
        "currency": "USD",
        "source": "App Store Connect Sales & Trends",
        "note": "USD values are converted with daily ECB rates, so they can differ slightly from Apple's own figures.",
        "periods": {label: build_period(records, latest_day, days) for label, days in PERIODS},
        "warnings": [],
    }
    if missing:
        income["warnings"].append(f"No exchange rate for {', '.join(sorted(missing))}; those amounts count as $0.")
    return income


def fetch_income(today=None):
    """
    Fetches the income payload. Never raises: a missing setup or an API failure
    comes back as a status so the rest of the daily report still goes out.
    """
    creds = get_credentials()
    if not creds:
        return {"status": "not_configured", "message": "App Store Connect credentials are not set in .env."}
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        latest_day = find_latest_report_day(creds, today)
        if not latest_day:
            return {"status": "error", "message": f"No App Store Connect report in the last {LATEST_DATE_LOOKBACK_DAYS} days."}

        longest = max(days for _, days in PERIODS)
        all_days = [latest_day - timedelta(days=offset) for offset in range(longest * 2)]
        with ThreadPoolExecutor(max_workers=6) as pool:
            reports = list(pool.map(lambda d: load_report(creds, d, latest_day), all_days))
        reports_by_day = dict(zip(all_days, reports))

        currencies = {
            row.get(column, "").strip()
            for rows in reports for row in rows
            for column in ("Currency of Proceeds", "Customer Currency")
        } - {""}
        rates_by_date, fallback = load_fx_rates(all_days[-1], latest_day, currencies)
        return build_income(reports_by_day, latest_day, rates_by_date, fallback)
    except Exception as e:
        print(f"⚠️ App Store Connect income fetch failed: {e}", file=sys.stderr)
        return {"status": "error", "message": str(e)}


def income_to_markdown(income):
    """Verified income section for the PDF and Markdown reports, independent of the AI text."""
    if income.get("status") != "ok":
        return f"## 💵 App Store Income\n\n> ⚠️ Income data unavailable: {income.get('message', 'unknown error')}\n\n"

    def delta(metric):
        return f"{metric['change_pct']:+.1f}%"

    md = f"## 💵 App Store Income (newest report: {income['as_of']})\n\n"
    md += f"*{income['source']}. {income['note']}*\n\n"
    labels = [label for label, _ in PERIODS]
    md += "| Metric | " + " | ".join(labels) + " |\n| :--- |" + " :--- |" * len(labels) + "\n"
    rows = [
        ("Units", "units", "{:,.0f}"), ("Proceeds", "proceeds", "${:,.2f}"), ("Sales", "sales", "${:,.2f}"),
        ("Updates", "updates", "{:,.0f}"), ("In-App Purchases", "iap", "{:,.0f}"),
        ("App Bundles", "bundles", "{:,.0f}"), ("Pre-Orders", "preorders", "{:,.0f}"),
    ]
    for name, key, fmt in rows:
        cells = [income["periods"][label]["metrics"][key] for label in labels]
        md += f"| **{name}** | " + " | ".join(f"{fmt.format(c['value'])} ({delta(c)})" for c in cells) + " |\n"

    period = income["periods"]["1D"]
    md += f"\n### Products, {period['end']}\n\n| Product | App | Units | Proceeds | Change |\n| :--- | :--- | :--- | :--- | :--- |\n"
    for p in period["products"]:
        md += f"| {p['title']} | {p['app']} | {p['units']} | ${p['proceeds']:,.2f} | {p['change_pct']:+.1f}% |\n"
    md += f"\n### Territories, {period['end']}\n\n| Territory | Units | Proceeds | Change |\n| :--- | :--- | :--- | :--- |\n"
    for t in period["territories"]:
        md += f"| {t['name']} | {t['units']} | ${t['proceeds']:,.2f} | {t['change_pct']:+.1f}% |\n"
    for warning in income.get("warnings", []):
        md += f"\n> ⚠️ {warning}\n"
    return md + "\n---\n\n"


def main():
    parser = argparse.ArgumentParser(description="Print App Store Connect income for the newest report on or before a date.")
    parser.add_argument("--date", help="YYYY-MM-DD report day to check against the Trends screen")
    args = parser.parse_args()
    today = datetime.strptime(args.date, "%Y-%m-%d").date() + timedelta(days=1) if args.date else None
    income = fetch_income(today)
    if income["status"] != "ok":
        print(json.dumps(income, indent=2))
        sys.exit(1)
    period = income["periods"]["1D"]
    print(f"Report day: {income['as_of']}")
    print(json.dumps(period["metrics"], indent=2))
    print(json.dumps({"products": period["products"], "territories": period["territories"]}, indent=2))


if __name__ == "__main__":
    main()
