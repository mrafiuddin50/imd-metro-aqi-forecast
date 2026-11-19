"""
IMD Metro Air Quality Forecast Scraper

What this script does, step by step:
  1. Downloads each city's SILAM forecast page from the IMD NWP portal.
  2. Finds the chart data hidden inside the page. The charts are drawn with
     Plotly, and Plotly keeps the numbers in a block of JSON in the page source.
     Reading that JSON is far more reliable than reading the chart image.
  3. Pulls out hourly PM2.5 and PM10 and the daily AQI gauges.
  4. Checks the forecast is current. IMD sometimes stops updating a city's page,
     and an old page still downloads without any error.
  5. Saves per-city CSVs, a combined CSV, a daily AQI CSV, a raw archive of this
     run and a status file.
  6. Exits with an error if anything broke, so GitHub marks the run as failed
     and emails the repository owner.

Source page: https://nwp.imd.gov.in/aqfcst1.php (SILAM model)
The values are model FORECASTS shown on IMD's site, not observed AQI.
"""

import csv
import json
import logging
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone

import requests
import urllib3

# ---------------------------------------------------------------------------
# Settings: the things you are most likely to change
# ---------------------------------------------------------------------------

CITIES = ["Delhi", "Mumbai", "Hyderabad", "Bengaluru", "Kolkata", "Chennai"]

PAGE_URL = "https://nwp.imd.gov.in/silam/{city}.html"

# The tracker starts on this date. Older rows are dropped from the main files.
# (This also clears out the December 2024 rows from IMD's stale Bengaluru page.)
DATA_START_DATE = "2026-11-08"

# Say honestly who is asking for the page, with a link to find out more.
USER_AGENT = (
    "imd-metro-aqi-forecast research scraper "
    "(+https://github.com/mrafiuddin50/imd-metro-aqi-forecast)"
)

PAUSE_BETWEEN_CITIES_SECONDS = 2
ATTEMPTS_PER_CITY = 3

IST = timezone(timedelta(hours=5, minutes=30))

# ---------------------------------------------------------------------------
# File locations
# ---------------------------------------------------------------------------

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
CITIES_DIR = os.path.join(DATA_DIR, "cities")
ARCHIVE_DIR = os.path.join(DATA_DIR, "archive")
MASTER_HOURLY_CSV = os.path.join(DATA_DIR, "master_all_cities_hourly.csv")
DAILY_SUMMARY_CSV = os.path.join(DATA_DIR, "daily_official_aqi_summary.csv")
STATUS_JSON = os.path.join(DATA_DIR, "latest_snapshot.json")

HOURLY_FIELDS = [
    "forecast_timestamp",
    "city",
    "pm25_hourly",
    "pm10_hourly",
    "daily_imd_silam_forecast_aqi",
    "daily_dominating_pollutant",
    "daily_aqi_category_derived",
    "scraped_at_ist",
]

DAILY_FIELDS = [
    "scraped_at_ist",
    "city",
    "forecast_date_utc",
    "imd_silam_forecast_aqi",
    "dominating_pollutant",
    "aqi_category_derived",
]

# Old column names (before November 2026) -> new names. Used to upgrade
# existing CSVs the first time this version of the script runs.
OLD_HOURLY_NAMES = {
    "official_daily_aqi": "daily_imd_silam_forecast_aqi",
    "dominating_pollutant": "daily_dominating_pollutant",
    "aqi_category": "daily_aqi_category_derived",
}
OLD_DAILY_NAMES = {
    "forecast_date": "forecast_date_utc",
    "official_aqi": "imd_silam_forecast_aqi",
    "aqi_category": "aqi_category_derived",
}

# Log to the screen (GitHub keeps each run's screen output), with UTC labelled.
logging.Formatter.converter = time.gmtime
logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format="%(asctime)s UTC [%(levelname)s] %(message)s",
)
log = logging.getLogger("imd_scraper")


class PageProblem(Exception):
    """The page downloaded, but its contents were not what we expected."""


# ---------------------------------------------------------------------------
# Step 1: download a page
# ---------------------------------------------------------------------------

def fetch_page(session, url):
    """Download a page, retrying a few times. Returns the HTML text, or None."""
    for attempt in range(1, ATTEMPTS_PER_CITY + 1):
        try:
            try:
                resp = session.get(url, timeout=30)
            except requests.exceptions.SSLError:
                # IMD's security certificate does not always pass Python's checks.
                # We only READ public pages, so we fall back to an unchecked
                # connection, but we say so loudly instead of hiding it.
                log.warning("SSL certificate check failed for %s; retrying without it.", url)
                urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
                resp = session.get(url, timeout=30, verify=False)

            if resp.status_code == 200:
                return resp.text
            log.warning("Attempt %d: %s returned HTTP %d", attempt, url, resp.status_code)
        except requests.exceptions.RequestException as e:
            log.warning("Attempt %d: %s failed: %s", attempt, url, e)
        time.sleep(attempt * 2)
    return None


# ---------------------------------------------------------------------------
# Step 2 and 3: find the chart data and pull out the numbers
# ---------------------------------------------------------------------------

def aqi_category(aqi):
    """CPCB category for an AQI number. Worked out here; IMD's page does not give it."""
    if aqi <= 50:
        return "Good"
    if aqi <= 100:
        return "Satisfactory"
    if aqi <= 200:
        return "Moderate"
    if aqi <= 300:
        return "Poor"
    if aqi <= 400:
        return "Very Poor"
    return "Severe"


def number_or_blank(value):
    """Round to one decimal place; blank if the value is missing."""
    if value is None:
        return ""
    return str(round(float(value), 1))


def parse_page(html, city, scraped_at):
    """Return (hourly_rows, daily_rows) from one city's page."""
    match = re.search(
        r'<script type="application/json" data-for="[^"]+">(.*?)</script>', html, re.DOTALL
    )
    if not match:
        raise PageProblem("chart data (Plotly JSON) not found; IMD may have changed the page")

    traces = json.loads(match.group(1)).get("x", {}).get("data", [])

    # Daily AQI gauges. The page shows each gauge twice (desktop and mobile
    # layouts), so keep only the first gauge for each date.
    daily_by_date = {}
    for t in traces:
        if t.get("type") != "indicator" or t.get("value") is None:
            continue
        title = t.get("title", {}).get("text", "")
        date_match = re.search(r"AQI\s+([^<]+)", title)
        pollutant_match = re.search(r'Dominating:\s*([^"<]+)', title)
        if not date_match:
            continue
        forecast_date = date_match.group(1).replace(" UTC", "").strip()
        aqi = round(float(t["value"]))
        day = forecast_date[:10]
        if day not in daily_by_date:
            daily_by_date[day] = {
                "scraped_at_ist": scraped_at,
                "city": city,
                "forecast_date_utc": forecast_date,
                "imd_silam_forecast_aqi": str(aqi),
                "dominating_pollutant": pollutant_match.group(1).strip() if pollutant_match else "",
                "aqi_category_derived": aqi_category(aqi),
            }

    # Hourly PM2.5 and PM10 lines from the charts.
    pm25 = next((t for t in traces if t.get("name") == "PM2_5"), None)
    pm10 = next((t for t in traces if t.get("name") == "PM10"), None)
    if not pm25 or not pm10:
        raise PageProblem("PM2_5 or PM10 chart line not found")

    def clean(ts):
        return ts.split(".")[0].strip()

    pm10_by_time = {clean(ts): y for ts, y in zip(pm10.get("x", []), pm10.get("y", []))}

    hourly = []
    for ts, y in zip(pm25.get("x", []), pm25.get("y", [])):
        ts = clean(ts)
        gauge = daily_by_date.get(ts[:10], {})
        hourly.append({
            "forecast_timestamp": ts,
            "city": city,
            "pm25_hourly": number_or_blank(y),
            "pm10_hourly": number_or_blank(pm10_by_time.get(ts)),
            "daily_imd_silam_forecast_aqi": gauge.get("imd_silam_forecast_aqi", ""),
            "daily_dominating_pollutant": gauge.get("dominating_pollutant", ""),
            "daily_aqi_category_derived": gauge.get("aqi_category_derived", ""),
            "scraped_at_ist": scraped_at,
        })

    if not hourly:
        raise PageProblem("chart lines were found but contained no hourly values")

    return hourly, list(daily_by_date.values())


# ---------------------------------------------------------------------------
# Step 5: save, merging with what is already there
# ---------------------------------------------------------------------------

def merge_and_save(path, new_rows, key_fields, fieldnames, old_names, date_field):
    """
    Merge new rows into a CSV and write it back.

    - Rows are matched on key_fields (e.g. city + forecast hour). A newer
      forecast for the same hour replaces the older one.
    - If a row's values have not changed, the old row (and its scraped_at_ist)
      is kept, so a run with no new data leaves the file byte-for-byte the same
      and there is nothing to commit.
    - Rows dated before DATA_START_DATE are dropped.
    """
    def key(row):
        return tuple(row[k] for k in key_fields)

    rows = {}
    if os.path.exists(path):
        with open(path, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                r = {old_names.get(k, k): v for k, v in r.items()}
                r = {k: ("" if r.get(k) in (None, "N/A") else r[k]) for k in fieldnames}
                rows[key(r)] = r

    for r in new_rows:
        old = rows.get(key(r))
        unchanged = old is not None and all(
            old[k] == r[k] for k in fieldnames if k != "scraped_at_ist"
        )
        if not unchanged:
            rows[key(r)] = r

    kept = [r for r in rows.values() if r[date_field][:10] >= DATA_START_DATE]
    kept.sort(key=key)

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(kept)
    return len(kept)


# ---------------------------------------------------------------------------
# Main run
# ---------------------------------------------------------------------------

def main():
    now = datetime.now(IST)
    scraped_at = now.strftime("%Y-%m-%d %H:%M:%S")
    today = now.strftime("%Y-%m-%d")
    log.info("Starting run (IST %s)", scraped_at)

    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    status = {}
    fresh_hourly, fresh_daily = [], []

    for city in CITIES:
        html = fetch_page(session, PAGE_URL.format(city=city))
        if html is None:
            status[city] = {"status": "failed", "message": "page could not be downloaded"}
        else:
            try:
                hourly, daily = parse_page(html, city, scraped_at)
                newest = max(r["forecast_timestamp"] for r in hourly)
                # Step 4: a forecast whose last hour is before today is stale.
                if newest[:10] < today:
                    status[city] = {
                        "status": "stale",
                        "newest_forecast_hour": newest,
                        "message": "IMD's page has not been updated; data not saved",
                    }
                else:
                    status[city] = {"status": "ok", "newest_forecast_hour": newest}
                    fresh_hourly.extend(hourly)
                    fresh_daily.extend(daily)
            except (PageProblem, ValueError, KeyError) as e:
                status[city] = {"status": "failed", "message": str(e)}

        city_status = status[city]
        log.info("%-10s %s %s", city, city_status["status"].upper(),
                 city_status.get("newest_forecast_hour", city_status.get("message", "")))
        time.sleep(PAUSE_BETWEEN_CITIES_SECONDS)

    # Per-city files. Stale and failed cities are still rewritten, which only
    # applies the DATA_START_DATE filter to rows already there.
    for city in CITIES:
        rows = [r for r in fresh_hourly if r["city"] == city]
        merge_and_save(os.path.join(CITIES_DIR, f"{city.lower()}_hourly.csv"), rows,
                       ["forecast_timestamp"], HOURLY_FIELDS, OLD_HOURLY_NAMES,
                       "forecast_timestamp")

    n_master = merge_and_save(MASTER_HOURLY_CSV, fresh_hourly, ["city", "forecast_timestamp"],
                              HOURLY_FIELDS, OLD_HOURLY_NAMES, "forecast_timestamp")
    n_daily = merge_and_save(DAILY_SUMMARY_CSV, fresh_daily, ["city", "forecast_date_utc"],
                             DAILY_FIELDS, OLD_DAILY_NAMES, "forecast_date_utc")

    # Raw archive: one pair of files per day, never touched by later days.
    # This keeps forecasts made 1, 2 and 3 days ahead, which the main files
    # overwrite. (A second run on the same day updates that day's files.)
    if fresh_hourly:
        merge_and_save(os.path.join(ARCHIVE_DIR, f"{today}_hourly.csv"), fresh_hourly,
                       ["city", "forecast_timestamp"], HOURLY_FIELDS, {}, "forecast_timestamp")
        merge_and_save(os.path.join(ARCHIVE_DIR, f"{today}_daily.csv"), fresh_daily,
                       ["city", "forecast_date_utc"], DAILY_FIELDS, {}, "forecast_date_utc")

    # Status file. No run timestamp in here on purpose: if nothing changed,
    # this file does not change either.
    with open(DAILY_SUMMARY_CSV, newline="", encoding="utf-8") as f:
        upcoming = [r for r in csv.DictReader(f) if r["forecast_date_utc"][:10] >= today]
    with open(STATUS_JSON, "w", encoding="utf-8") as f:
        json.dump({
            "note": "IMD SILAM model forecasts, not observed AQI. Categories are derived "
                    "by this script from CPCB breakpoints.",
            "cities": status,
            "upcoming_daily_forecasts": upcoming,
        }, f, indent=2, ensure_ascii=False)
        f.write("\n")

    log.info("Saved: master hourly %d rows, daily summary %d rows", n_master, n_daily)

    # Step 6: report problems so GitHub shows them. Lines starting with
    # ::warning:: or ::error:: become notes on the GitHub Actions run page.
    failed = [c for c, s in status.items() if s["status"] == "failed"]
    stale = [c for c, s in status.items() if s["status"] == "stale"]
    for c in stale:
        print(f"::warning::{c}: IMD page is stale (newest forecast hour "
              f"{status[c]['newest_forecast_hour']}). Data not saved.")
    for c in failed:
        print(f"::error::{c}: {status[c]['message']}")

    if failed or not fresh_hourly:
        log.error("Run finished with problems: failed=%s stale=%s", failed, stale)
        sys.exit(1)
    log.info("Run finished. Stale cities (skipped): %s", stale or "none")


if __name__ == "__main__":
    main()
