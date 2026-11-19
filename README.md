# 🌦️ IMD Metro Air Quality Forecast Tracker (Hourly PM + Daily Forecast AQI)
*Automated daily collection of IMD's SILAM air quality forecasts for six Indian metropolitan cities.*

**Data source:** [India Meteorological Department (IMD) NWP Portal](https://nwp.imd.gov.in/aqfcst1.php) → SILAM model city pages
**Cities:** Delhi, Mumbai, Hyderabad, Bengaluru, Kolkata, Chennai
**Schedule:** Daily via GitHub Actions at **07:47 IST** (`02:17 UTC`), with a backup run at **10:47 IST** (`05:17 UTC`) in case the first fails. The backup commits only if it finds new data. GitHub often starts scheduled runs late, so a run can happen hours after these times. Check the commit time for when data actually arrived.

> **What this data is, and is not.** Every value here is a **model forecast** published on IMD's SILAM pages. None of it is observed or monitored air quality. The AQI category is **worked out by this script** from CPCB breakpoints; IMD's page does not give it. Some forecast AQI values go above 500, the top of the CPCB scale. Verify against the IMD page before using any value in an output.

---

## 📊 Google Sheets: live links

Paste any formula into cell **A1** of a Google Sheet tab. Google refreshes the data roughly every hour.

### 1. Per-city tabs
* **Delhi:** `=IMPORTDATA("https://raw.githubusercontent.com/mrafiuddin50/imd-metro-aqi-forecast/main/data/cities/delhi_hourly.csv")`
* **Mumbai:** `=IMPORTDATA("https://raw.githubusercontent.com/mrafiuddin50/imd-metro-aqi-forecast/main/data/cities/mumbai_hourly.csv")`
* **Hyderabad:** `=IMPORTDATA("https://raw.githubusercontent.com/mrafiuddin50/imd-metro-aqi-forecast/main/data/cities/hyderabad_hourly.csv")`
* **Bengaluru:** `=IMPORTDATA("https://raw.githubusercontent.com/mrafiuddin50/imd-metro-aqi-forecast/main/data/cities/bengaluru_hourly.csv")` *(empty for now: see Known limitations)*
* **Kolkata:** `=IMPORTDATA("https://raw.githubusercontent.com/mrafiuddin50/imd-metro-aqi-forecast/main/data/cities/kolkata_hourly.csv")`
* **Chennai:** `=IMPORTDATA("https://raw.githubusercontent.com/mrafiuddin50/imd-metro-aqi-forecast/main/data/cities/chennai_hourly.csv")`

### 2. Summary tabs
* **Daily forecast AQI, all cities:** `=IMPORTDATA("https://raw.githubusercontent.com/mrafiuddin50/imd-metro-aqi-forecast/main/data/daily_official_aqi_summary.csv")`
* **Hourly, all cities combined:** `=IMPORTDATA("https://raw.githubusercontent.com/mrafiuddin50/imd-metro-aqi-forecast/main/data/master_all_cities_hourly.csv")`

> **Column names changed on 19 November 2026** (see the data dictionary). Sheets that refer to columns by name need updating. The file names and links have not changed.

---

## 📁 Repository structure

```
.
├── .github/workflows/daily_scrape.yml   # Daily schedule (02:17 UTC, backup 05:17 UTC) + manual "Run workflow" button
├── scripts/imd_scraper.py               # The scraper
├── data/
│   ├── cities/<city>_hourly.csv         # Hourly PM2.5, PM10 + that day's forecast AQI, one file per city
│   ├── master_all_cities_hourly.csv     # All cities' hourly rows in one file
│   ├── daily_official_aqi_summary.csv   # Daily forecast AQI gauges, all cities
│   ├── archive/YYYY-MM-DD_hourly.csv    # Everything downloaded on that day, kept as-is
│   ├── archive/YYYY-MM-DD_daily.csv
│   └── latest_snapshot.json             # Each city's status (ok / stale / failed) + upcoming daily forecasts
├── requirements.txt                     # requests, urllib3
├── TEACHING.md                          # How to use this repo to learn scraping
└── README.md
```

---

## 📋 Data dictionary

### Hourly files (`data/cities/<city>_hourly.csv`, `data/master_all_cities_hourly.csv`)

| Field | Example | Description |
| :--- | :--- | :--- |
| `forecast_timestamp` | `2026-11-10 14:00:00` | Forecast hour as given in IMD's chart data. **Time zone not yet confirmed** (see Known limitations). |
| `city` | `Delhi` | City name |
| `pm25_hourly` | `170.0` | Forecast PM2.5 (µg/m³) |
| `pm10_hourly` | `224.5` | Forecast PM10 (µg/m³) |
| `daily_imd_silam_forecast_aqi` | `227` | That **day's** forecast AQI from IMD's gauge, repeated on every hour of the day. Not an hourly AQI. |
| `daily_dominating_pollutant` | `PM2_5` | Dominating pollutant shown on that day's gauge |
| `daily_aqi_category_derived` | `Poor` | CPCB category **worked out by this script** from the AQI value |
| `scraped_at_ist` | `2026-11-10 15:00:25` | When this row's values were downloaded (IST) |

Blank cells mean the value was missing on IMD's page.

### Daily file (`data/daily_official_aqi_summary.csv`)

| Field | Example | Description |
| :--- | :--- | :--- |
| `scraped_at_ist` | `2026-11-10 15:00:25` | When this row's values were downloaded (IST) |
| `city` | `Delhi` | City name |
| `forecast_date_utc` | `2026-11-08 11:00:00` | Gauge date and time; IMD's page labels it UTC |
| `imd_silam_forecast_aqi` | `227` | Forecast AQI shown on IMD's gauge |
| `dominating_pollutant` | `PM2_5` | Dominating pollutant shown on the gauge |
| `aqi_category_derived` | `Poor` | CPCB category worked out by this script |

---

## ⚠️ Known limitations

* **Each forecast hour keeps only the latest forecast.** IMD's page covers about four days. Each run replaces earlier forecasts for the same hours, so the main files hold the most recent forecast for each hour. To compare forecasts made 1, 2 or 3 days ahead, use `data/archive/` (one pair of files per day, starting with the first run after 19 November 2026).
* **Bengaluru is stale at source.** IMD's Bengaluru page still shows forecasts for 24–31 December 2024. The scraper skips any city whose newest forecast hour is before today, so Bengaluru's file stays empty until IMD updates the page. Check `latest_snapshot.json` for each city's status.
* **Time zone of hourly timestamps not yet confirmed.** Gauge dates are labelled UTC on IMD's page. The hourly chart times carry no label. Until this is checked against the page, treat day boundaries in the hourly files with care.
* **No 00:00 hour.** Each day has 23 hourly values (01:00–23:00). This matches what IMD's chart data contains.
* **Data starts 8 November 2026.**

---

## 🔧 When something breaks

* A run with a **red cross** on the Actions tab means a city's page could not be downloaded or read (for example, IMD changed the page layout). GitHub emails the repository owner. Data from the cities that worked is still saved.
* A **yellow warning** on a green run means a city's page is stale. Nothing from that city was saved.
* Only the GitHub Action should commit data. To run the scraper on your own computer, do it in a separate copy, not in a clone you push from, or you will hit merge conflicts.

---

## 📄 Credit and use

Forecast data © India Meteorological Department, collected from the public NWP portal for research use. This repository is not affiliated with IMD. Check IMD's terms before republishing the data.
