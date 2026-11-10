"""
IMD Metro Air Quality Forecast Scraper
Council on Energy, Environment and Water (CEEW)

Target: https://nwp.imd.gov.in/aqfcst1.php -> SILAM Forecast Engine
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

# Suppress insecure SSL warnings for government endpoints
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Directory configurations
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(BASE_DIR, "data")
CSV_PATH = os.path.join(DATA_DIR, "imd_forecast_history.csv")
JSON_PATH = os.path.join(DATA_DIR, "latest_snapshot.json")
LOG_PATH = os.path.join(BASE_DIR, "scraper.log")

os.makedirs(DATA_DIR, exist_ok=True)

logging.basicConfig(
    filename=LOG_PATH,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# 6 Target metropolitan cities on the IMD portal
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

def get_aqi_category(aqi_val):
    """Returns official CPCB AQI categories based on AQI index value."""
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

def scrape_city_silam(session, city_name):
    """
    Extracts multi-day air quality forecast values from IMD's SILAM engine.
    """
    url = f"https://nwp.imd.gov.in/silam/{city_name}.html"
    ist_str = get_ist_now().strftime("%Y-%m-%d %H:%M:%S")
    records = []

    for attempt in range(1, 4):
        try:
            resp = session.get(url, headers=HEADERS, verify=False, timeout=25)
            if resp.status_code == 200:
                html = resp.text
                
                # Match plotly gauge indicators:
                # "value": <num>, "title": {"text": "AQI <forecast_date>... Dominating: <pollutant>"
                matches = re.findall(
                    r'"value":\s*([0-9.]+),\s*"title":\s*\{\s*"text":\s*"AQI\s+([^<]+)<br>Dominating:\s*([^"]+)"',
                    html
                )

                seen_dates = set()
                for val_str, forecast_dt, dominating in matches:
                    forecast_dt_clean = forecast_dt.replace(" UTC", "").strip()
                    # Deduplicate between mobile and desktop plotly trace views
                    if forecast_dt_clean in seen_dates:
                        continue
                    seen_dates.add(forecast_dt_clean)

                    aqi_int = round(float(val_str))
                    records.append({
                        "scraped_at_ist": ist_str,
                        "city": city_name,
                        "forecast_date": forecast_dt_clean,
                        "forecast_aqi": aqi_int,
                        "dominating_pollutant": dominating.strip(),
                        "aqi_category": get_aqi_category(aqi_int),
                        "status": "SUCCESS"
                    })
                
                if records:
                    logging.info(f"[{city_name}] Successfully extracted {len(records)} forecast day(s).")
                    return records

            logging.warning(f"[{city_name}] Attempt {attempt} returned status {resp.status_code}")
            time.sleep(attempt * 2)

        except requests.exceptions.RequestException as e:
            logging.warning(f"[{city_name}] Attempt {attempt} failed: {e}")
            time.sleep(attempt * 2)

    # Fallback if connection fails
    logging.error(f"Failed to fetch data for {city_name}.")
    records.append({
        "scraped_at_ist": ist_str,
        "city": city_name,
        "forecast_date": get_ist_now().strftime("%Y-%m-%d"),
        "forecast_aqi": "N/A",
        "dominating_pollutant": "N/A",
        "aqi_category": "Error",
        "status": "CONNECTION_FAILED"
    })
    return records

def load_existing_records():
    """Reads existing CSV to enable deduplication."""
    if not os.path.exists(CSV_PATH):
        return set()
    
    existing = set()
    try:
        with open(CSV_PATH, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                existing.add((row.get("city"), row.get("forecast_date")))
    except Exception as e:
        logging.warning(f"Could not read existing CSV for deduplication: {e}")
    return existing

def save_records(records):
    """Appends records to the cumulative CSV and updates latest JSON snapshot."""
    existing_keys = load_existing_records()
    new_to_csv = [
        r for r in records 
        if (r["city"], r["forecast_date"]) not in existing_keys
    ]

    fieldnames = [
        "scraped_at_ist",
        "city",
        "forecast_date",
        "forecast_aqi",
        "dominating_pollutant",
        "aqi_category",
        "status"
    ]

    # Write to CSV
    file_exists = os.path.exists(CSV_PATH)
    with open(CSV_PATH, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerows(new_to_csv)

    # Write latest snapshot JSON
    with open(JSON_PATH, mode="w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)

    logging.info(f"Appended {len(new_to_csv)} new rows to CSV; JSON snapshot updated.")

def main():
    start_time = get_ist_now()
    print(f"[{start_time.strftime('%Y-%m-%d %H:%M:%S IST')}] Scraping IMD Metro Air Quality Forecasts...")
    logging.info("Starting scrape run...")

    session = requests.Session()
    all_city_records = []

    for city in METRO_CITIES:
        city_records = scrape_city_silam(session, city)
        all_city_records.extend(city_records)
        print(f"  ✔ {city.ljust(11)}: {len(city_records)} forecast record(s) extracted")
        time.sleep(1) # Polite pause

    save_records(all_city_records)
    print(f"\n[DONE] Finished scraping {len(all_city_records)} total records.")
    print(f"  - CSV:  {CSV_PATH}")
    print(f"  - JSON: {JSON_PATH}")

if __name__ == "__main__":
    main()
