# 🌦️ IMD Metro Air Quality Forecast Tracker (Hourly + Official Daily AQI)
*Automated daily air quality forecast monitoring across India's top 6 metropolitan cities.*

**Data Source:** [India Meteorological Department (IMD) NWP Portal](https://nwp.imd.gov.in/aqfcst1.php) -> SILAM Engine  
**Cities Monitored:** Delhi, Mumbai, Hyderabad, Bengaluru, Kolkata, Chennai  
**Run Frequency:** Daily at **08:00 AM IST** (`02:30 UTC`) via GitHub Actions  

---

## 📊 Live Google Sheets Integration (Direct One-Click Links)

Researchers can paste any of the formulas below directly into cell **A1** of a Google Sheet tab:

### 1. Dedicated Per-City Tabs (Clean Separation)
* **Delhi Tab:**
  ```excel
  =IMPORTDATA("https://raw.githubusercontent.com/mrafiuddin50/imd-metro-aqi-forecast/main/data/cities/delhi_hourly.csv")
  ```
* **Mumbai Tab:**
  ```excel
  =IMPORTDATA("https://raw.githubusercontent.com/mrafiuddin50/imd-metro-aqi-forecast/main/data/cities/mumbai_hourly.csv")
  ```
* **Hyderabad Tab:**
  ```excel
  =IMPORTDATA("https://raw.githubusercontent.com/mrafiuddin50/imd-metro-aqi-forecast/main/data/cities/hyderabad_hourly.csv")
  ```
* **Bengaluru Tab:**
  ```excel
  =IMPORTDATA("https://raw.githubusercontent.com/mrafiuddin50/imd-metro-aqi-forecast/main/data/cities/bengaluru_hourly.csv")
  ```
* **Kolkata Tab:**
  ```excel
  =IMPORTDATA("https://raw.githubusercontent.com/mrafiuddin50/imd-metro-aqi-forecast/main/data/cities/kolkata_hourly.csv")
  ```
* **Chennai Tab:**
  ```excel
  =IMPORTDATA("https://raw.githubusercontent.com/mrafiuddin50/imd-metro-aqi-forecast/main/data/cities/chennai_hourly.csv")
  ```

### 2. High-Level Summary Tabs
* **Daily Official AQI Summary (All 6 Cities):**
  ```excel
  =IMPORTDATA("https://raw.githubusercontent.com/mrafiuddin50/imd-metro-aqi-forecast/main/data/daily_official_aqi_summary.csv")
  ```
* **Master Hourly Panel (All 6 Cities Combined):**
  ```excel
  =IMPORTDATA("https://raw.githubusercontent.com/mrafiuddin50/imd-metro-aqi-forecast/main/data/master_all_cities_hourly.csv")
  ```

---

## 📁 Repository Structure

```
.
├── .github/
│   └── workflows/
│       └── daily_scrape.yml           # Runs daily at 08:00 AM IST
├── scripts/
│   └── imd_scraper.py                 # Multi-city hourly & daily AQI engine
├── data/
│   ├── cities/                        # Clean per-city separation
│   │   ├── delhi_hourly.csv           # Hourly PM2.5, PM10 & official daily AQI
│   │   ├── mumbai_hourly.csv
│   │   ├── hyderabad_hourly.csv
│   │   ├── bengaluru_hourly.csv
│   │   ├── kolkata_hourly.csv
│   │   └── chennai_hourly.csv
│   ├── daily_official_aqi_summary.csv # Pure official AQI gauges directly from IMD
│   ├── master_all_cities_hourly.csv   # Combined 6-city hourly dataset for modeling
│   └── latest_snapshot.json           # Lightweight JSON snapshot
├── requirements.txt                   # requests, beautifulsoup4, urllib3
├── scraper.log                        # Execution audit logs
└── README.md
```

---

## 📋 Data Dictionary

### Hourly Datasets (`data/cities/<city>_hourly.csv`)

| Field | Example | Description |
| :--- | :--- | :--- |
| `forecast_timestamp` | `2026-11-10 14:00:00` | Hourly forecast time |
| `city` | `Delhi` | City name |
| `pm25_hourly` | `170.0` | Hourly $\text{PM}_{2.5}$ ($\mu\text{g/m}^3$) directly from plot |
| `pm10_hourly` | `224.5` | Hourly $\text{PM}_{10}$ ($\mu\text{g/m}^3$) directly from plot |
| `official_daily_aqi` | `617` | **Official IMD AQI directly from the gauge below the plot** |
| `dominating_pollutant` | `PM2_5` | Official dominating pollutant reported by IMD |
| `aqi_category` | `Severe` | CPCB rating category for the official AQI |
| `scraped_at_ist` | `2026-11-10 14:42:01` | Execution timestamp in IST |

---

### Daily AQI Summary (`data/daily_official_aqi_summary.csv`)

| Field | Example | Description |
| :--- | :--- | :--- |
| `scraped_at_ist` | `2026-11-10 14:42:01` | Execution timestamp in IST |
| `city` | `Delhi` | City name |
| `forecast_date` | `2026-11-10 11:00:00` | Target forecast date and time |
| `official_aqi` | `617` | **Exact AQI value from the IMD gauge below plot** |
| `dominating_pollutant` | `PM2_5` | Dominating pollutant from IMD gauge |
| `aqi_category` | `Severe` | Official category |
