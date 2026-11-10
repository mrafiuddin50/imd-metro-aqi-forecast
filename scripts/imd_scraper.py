"""
IMD Metro Air Quality Forecast Scraper (Hourly + Official Daily AQI)
Council on Energy, Environment and Water (CEEW)

Extracts:
1. Hourly PM2.5 and PM10 forecast time series (~92 continuous hours) from the top plots.
2. Official AQI values and dominating pollutants directly from the IMD gauges below the plots.
3. Clean city-separated CSVs under data/cities/{city}_hourly.csv + master combined dataset.

Target: https://nwp.imd.gov.in/aqfcst1.php -> SILAM Engine
Cities: Delhi, Mumbai, Hyderabad, Bengaluru, Kolkata, Chennai
"""

import os
import re
import csv
import json
import time
import logging
from datetime import datetime, timezone, timedelta
import urllib3
import requests

# Suppress SSL certificate warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Directory configurations
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(BASE_DIR, "data")
CITIES_DIR = os.path.join(DATA_DIR, "cities")
DAILY_SUMMARY_CSV = os.path.join(DATA_DIR, "daily_official_aqi_summary.csv")
MASTER_HOURLY_CSV = os.path.join(DATA_DIR, "master_all_cities_hourly.csv")
LATEST_SNAPSHOT_JSON = os.path.join(DATA_DIR, "latest_snapshot.json")
LOG_PATH = os.path.join(BASE_DIR, "scraper.log")

os.makedirs(CITIES_DIR, exist_ok=True)

logging.basicConfig(
    filename=LOG_PATH,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

METRO_CITIES = [
    "Delhi",
    "Mumbai",
    "Hyderabad",
    "Bengaluru",
    "Kolkata",
    "Chennai"
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://nwp.imd.gov.in/aqfcst1.php"
}

def get_ist_now():
    """Returns the current datetime in Indian Standard Time (UTC+5:30)."""
    ist = timezone(timedelta(hours=5, minutes=30))
    return datetime.now(ist)

def get_cpcb_category(aqi_val):
    """Returns official CPCB AQI categories based on the numeric AQI value."""
    try:
        val = float(aqi_val)
        if val <= 50:
            return "Good"
        elif val <= 100:
            return "Satisfactory"
        elif val <= 200:
            return "Moderate"
        elif val <= 300:
            return "Poor"
        elif val <= 400:
            return "Very Poor"
        else:
            return "Severe"
    except (ValueError, TypeError):
        return "Unknown"

def scrape_city_data(session, city_name):
    """
    Extracts:
    - Hourly PM2.5 and PM10 time series
    - Official daily AQI gauges located below the forecast plots
    """
    url = f"https://nwp.imd.gov.in/silam/{city_name}.html"
    ist_str = get_ist_now().strftime("%Y-%m-%d %H:%M:%S")

    for attempt in range(1, 4):
        try:
            resp = session.get(url, headers=HEADERS, verify=False, timeout=30)
            if resp.status_code == 200:
                html = resp.text
                match = re.search(r'<script type="application/json" data-for="[^"]+">(.*?)</script>', html, re.DOTALL)
                if not match:
                    logging.warning(f"[{city_name}] Could not find Plotly JSON payload.")
                    return [], []

                data = json.loads(match.group(1))
                traces = data.get("x", {}).get("data", [])

                # 1. Extract Official Daily AQI Gauges (located below the plots)
                daily_gauges = []
                daily_aqi_by_date = {} # maps YYYY-MM-DD -> {aqi, dominating, category}

                for t in traces:
                    if t.get("type") == "indicator" and t.get("value") is not None:
                        val = round(float(t.get("value")))
                        title_text = t.get("title", {}).get("text", "")
                        
                        # Match: "AQI <forecast_date>... Dominating: <pollutant>"
                        date_match = re.search(r'AQI\s+([^<]+)', title_text)
                        dom_match = re.search(r'Dominating:\s*([^"]+)', title_text)

                        raw_date = date_match.group(1).replace(" UTC", "").strip() if date_match else "N/A"
                        pollutant = dom_match.group(1).strip() if dom_match else "N/A"
                        cat = get_cpcb_category(val)

                        gauge_record = {
                            "scraped_at_ist": ist_str,
                            "city": city_name,
                            "forecast_date": raw_date,
                            "official_aqi": val,
                            "dominating_pollutant": pollutant,
                            "aqi_category": cat
                        }

                        # Deduplicate across desktop/mobile views
                        day_key = raw_date[:10]
                        if day_key not in daily_aqi_by_date:
                            daily_aqi_by_date[day_key] = gauge_record
                            daily_gauges.append(gauge_record)

                # 2. Extract Hourly PM2.5 and PM10 Traces from the top plots
                pm25_trace = next((t for t in traces if t.get("name") == "PM2_5"), None)
                pm10_trace = next((t for t in traces if t.get("name") == "PM10"), None)

                hourly_records = []
                if pm25_trace and pm10_trace:
                    x_pm25 = pm25_trace.get("x", [])
                    y_pm25 = pm25_trace.get("y", [])
                    x_pm10 = pm10_trace.get("x", [])
                    y_pm10 = pm10_trace.get("y", [])

                    # Map PM10 by clean timestamp string
                    pm10_dict = {}
                    for i, ts in enumerate(x_pm10):
                        clean_ts = ts.split(".")[0].strip()
                        pm10_dict[clean_ts] = y_pm10[i] if i < len(y_pm10) else None

                    for i, ts in enumerate(x_pm25):
                        clean_ts = ts.split(".")[0].strip()
                        p25_val = round(float(y_pm25[i]), 1) if i < len(y_pm25) and y_pm25[i] is not None else "N/A"
                        p10_val = round(float(pm10_dict.get(clean_ts)), 1) if pm10_dict.get(clean_ts) is not None else "N/A"
                        
                        # Match day to the official daily AQI gauge below the plot
                        day_key = clean_ts[:10]
                        gauge_info = daily_aqi_by_date.get(day_key, {})
                        official_aqi = gauge_info.get("official_aqi", "N/A")
                        dom_pollutant = gauge_info.get("dominating_pollutant", "N/A")
                        category = gauge_info.get("aqi_category", "N/A")

                        hourly_records.append({
                            "forecast_timestamp": clean_ts,
                            "city": city_name,
                            "pm25_hourly": p25_val,
                            "pm10_hourly": p10_val,
                            "official_daily_aqi": official_aqi,
                            "dominating_pollutant": dom_pollutant,
                            "aqi_category": category,
                            "scraped_at_ist": ist_str
                        })

                logging.info(f"[{city_name}] Extracted {len(hourly_records)} hourly points & {len(daily_gauges)} AQI gauges.")
                return hourly_records, daily_gauges

            logging.warning(f"[{city_name}] Attempt {attempt} returned HTTP {resp.status_code}")
            time.sleep(attempt * 2)

        except requests.exceptions.RequestException as e:
            logging.warning(f"[{city_name}] Attempt {attempt} failed: {e}")
            time.sleep(attempt * 2)

    logging.error(f"Failed to fetch {city_name} after 3 attempts.")
    return [], []

def save_city_hourly_csv(city_name, records):
    """
    Saves dedicated city hourly CSV under data/cities/{city_lower}_hourly.csv.
    Merges and deduplicates based on forecast_timestamp.
    """
    city_filename = f"{city_name.lower()}_hourly.csv"
    city_filepath = os.path.join(CITIES_DIR, city_filename)

    fieldnames = [
        "forecast_timestamp",
        "city",
        "pm25_hourly",
        "pm10_hourly",
        "official_daily_aqi",
        "dominating_pollutant",
        "aqi_category",
        "scraped_at_ist"
    ]

    existing_rows = {}
    if os.path.exists(city_filepath):
        try:
            with open(city_filepath, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for r in reader:
                    existing_rows[r.get("forecast_timestamp")] = r
        except Exception as e:
            logging.warning(f"Could not read existing file for {city_name}: {e}")

    # Update/append with new forecast records
    for r in records:
        existing_rows[r["forecast_timestamp"]] = r

    # Write sorted chronologically
    sorted_rows = sorted(existing_rows.values(), key=lambda x: x["forecast_timestamp"])
    with open(city_filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(sorted_rows)

    logging.info(f"Saved {len(sorted_rows)} total rows to {city_filepath}")

def save_master_hourly_csv(all_hourly_records):
    """Saves combined panel dataset for all cities into data/master_all_cities_hourly.csv."""
    fieldnames = [
        "forecast_timestamp",
        "city",
        "pm25_hourly",
        "pm10_hourly",
        "official_daily_aqi",
        "dominating_pollutant",
        "aqi_category",
        "scraped_at_ist"
    ]

    existing_rows = {}
    if os.path.exists(MASTER_HOURLY_CSV):
        try:
            with open(MASTER_HOURLY_CSV, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for r in reader:
                    key = (r.get("city"), r.get("forecast_timestamp"))
                    existing_rows[key] = r
        except Exception as e:
            logging.warning(f"Could not read master hourly CSV: {e}")

    for r in all_hourly_records:
        key = (r["city"], r["forecast_timestamp"])
        existing_rows[key] = r

    sorted_rows = sorted(existing_rows.values(), key=lambda x: (x["city"], x["forecast_timestamp"]))
    with open(MASTER_HOURLY_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(sorted_rows)

    logging.info(f"Saved {len(sorted_rows)} rows to master CSV.")

def save_daily_aqi_summary_csv(all_daily_gauges):
    """Saves official daily gauge summary across all 6 cities."""
    fieldnames = [
        "scraped_at_ist",
        "city",
        "forecast_date",
        "official_aqi",
        "dominating_pollutant",
        "aqi_category"
    ]

    existing_rows = {}
    if os.path.exists(DAILY_SUMMARY_CSV):
        try:
            with open(DAILY_SUMMARY_CSV, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for r in reader:
                    key = (r.get("city"), r.get("forecast_date"))
                    existing_rows[key] = r
        except Exception as e:
            logging.warning(f"Could not read daily summary CSV: {e}")

    for r in all_daily_gauges:
        key = (r["city"], r["forecast_date"])
        existing_rows[key] = r

    sorted_rows = sorted(existing_rows.values(), key=lambda x: (x["city"], x["forecast_date"]))
    with open(DAILY_SUMMARY_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(sorted_rows)

    logging.info(f"Saved {len(sorted_rows)} rows to daily AQI summary CSV.")

def main():
    start_time = get_ist_now()
    print(f"[{start_time.strftime('%Y-%m-%d %H:%M:%S IST')}] Scraping IMD Metro Hourly & Official AQI Data...")
    logging.info("Starting scrape run...")

    session = requests.Session()
    all_hourly_records = []
    all_daily_gauges = []

    for city in METRO_CITIES:
        hourly, gauges = scrape_city_data(session, city)
        if hourly:
            save_city_hourly_csv(city, hourly)
            all_hourly_records.extend(hourly)
        if gauges:
            all_daily_gauges.extend(gauges)

        print(f"  ✔ {city.ljust(11)}: {len(hourly)} hourly points | {len(gauges)} official AQI gauges")
        time.sleep(1)

    if all_hourly_records:
        save_master_hourly_csv(all_hourly_records)
    if all_daily_gauges:
        save_daily_aqi_summary_csv(all_daily_gauges)

    # Save latest snapshot JSON
    snapshot = {
        "updated_at_ist": start_time.strftime("%Y-%m-%d %H:%M:%S"),
        "cities": METRO_CITIES,
        "daily_official_gauges": all_daily_gauges,
        "sample_hourly_records": all_hourly_records[:10]
    }
    with open(LATEST_SNAPSHOT_JSON, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, indent=2, ensure_ascii=False)

    print(f"\n[DONE] Extraction completed successfully!")
    print(f"  - Per-City CSVs:          data/cities/<city>_hourly.csv (6 cities)")
    print(f"  - Master Hourly Dataset:  data/master_all_cities_hourly.csv ({len(all_hourly_records)} rows)")
    print(f"  - Daily Official AQI:     data/daily_official_aqi_summary.csv ({len(all_daily_gauges)} rows)")

if __name__ == "__main__":
    main()
