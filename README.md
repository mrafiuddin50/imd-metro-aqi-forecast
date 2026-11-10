# 🌦️ IMD Metro Air Quality Forecast Tracker (Daily Automated Scraper)
*Automated daily air quality forecast monitoring across India's top 6 metropolitan cities.*

**Data Source:** [India Meteorological Department (IMD) NWP Portal](https://nwp.imd.gov.in/aqfcst1.php)  
**Cities Monitored:** Delhi, Mumbai, Hyderabad, Bengaluru, Kolkata, Chennai  
**Run Frequency:** Daily at **08:00 AM IST** (`02:30 UTC`) via GitHub Actions  

---

## 📊 Live Google Sheets Integration (No Coding Required)

Any researcher on your team can view this live dataset directly inside an empty Google Sheet without downloading anything:

1. Open a new Google Sheet.
2. In cell **A1**, paste this formula (replace `<YOUR-USERNAME>` and `<REPO-NAME>`):

```excel
=IMPORTDATA("https://raw.githubusercontent.com/<YOUR-USERNAME>/<REPO-NAME>/main/data/imd_forecast_history.csv")
```

Every morning after 8:00 AM IST when GitHub Actions runs, your Google Sheet will automatically refresh with the latest forecast data.

---

## 📁 Repository Structure

```
.
├── .github/
│   └── workflows/
│       └── daily_scrape.yml       # GitHub Actions schedule (08:00 AM IST)
├── scripts/
│   └── imd_scraper.py             # Multi-city scraping script (requests + bs4)
├── data/
│   ├── imd_forecast_history.csv   # Cumulative historical time series
│   └── latest_snapshot.json       # Today's 6-city snapshot in JSON
├── requirements.txt               # Python package dependencies
├── scraper.log                    # Run audit logs
└── README.md
```

---

## 📋 Data Dictionary (`data/imd_forecast_history.csv`)

| Field | Type | Description |
| :--- | :--- | :--- |
| `scraped_at_ist` | Timestamp | Date and time the scraper ran (IST) |
| `city` | Text | City queried (`Delhi`, `Mumbai`, `Hyderabad`, `Bengaluru`, `Kolkata`, `Chennai`) |
| `forecast_date` | Date/Text | Target date for which the forecast is issued |
| `parameter` | Text | Pollutant or meteorological indicator (e.g. `PM2.5`) |
| `forecast_value` | Number/Text | Forecasted concentration or index value |
| `unit` | Text | Unit of measurement (e.g., `µg/m³`) |
| `status` | Text | `SUCCESS` or error audit status |

---

## ⚙️ Initial 3-Minute GitHub Setup

### 1. Enable Workflow Write Permissions
In order for GitHub Actions to automatically commit the updated CSV back to your repository:
1. In this repo, click **Settings** (top tab).
2. In the left sidebar, click **Actions** $\rightarrow$ **General**.
3. Scroll down to **Workflow permissions**.
4. Select **Read and write permissions**.
5. Click **Save**.

### 2. Manual Test Run
You can trigger the scraper immediately without waiting for 8:00 AM:
1. Click the **Actions** tab at the top.
2. Click **Daily IMD Metro Air Quality Forecast Scraper** in the left menu.
3. Click the **Run workflow** dropdown on the right $\rightarrow$ click the green **Run workflow** button.
4. Refresh after ~30 seconds to see the new data populated under `data/imd_forecast_history.csv`!
