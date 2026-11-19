# Learning web scraping with this repository

This guide is for colleagues who don't write code but do have Claude. You won't need to read the Python. You will learn how to:

1. find the data behind a chart on a website,
2. get Claude to write a scraper for it,
3. **check that the scraper's output is right**, and
4. run it every day on GitHub and pull the results into Google Sheets.

Step 3 matters most. A scraper that runs without errors can still collect wrong or out-of-date data. This repository has a real example of that (see "Case study: Bengaluru").

---

## Ground rules before scraping any site

* **Public pages only.** Never scrape anything behind a login, and never collect personal data.
* **Check the site's rules.** Open `https://<site>/robots.txt` and any terms-of-use page. If they say no automated access, stop and ask.
* **Be polite.** Pause between requests (this scraper waits 2 seconds) and run once a day, not every minute.
* **Be honest about who you are.** Set a User-Agent that names your project and links to it, as `USER_AGENT` does in `scripts/imd_scraper.py`. Don't pretend to be a web browser.
* **Credit the source** and describe the data accurately. The values here are IMD *model forecasts*, not *official observed AQI*.

---

## Session plan (about 2 hours)

### 1. Look at the page (10 min)
Open one city's forecast page from <https://nwp.imd.gov.in/aqfcst1.php>. Note what you can see: two charts (PM2.5 and PM10 by hour) and AQI gauges underneath. Pick one number you can read clearly on the page, such as a gauge value.

### 2. Find the data behind the chart (20 min)
Right-click → **View page source**. Press Ctrl+F and search for the number you picked.

You'll find it inside a long block that starts `<script type="application/json" ...>`. That is the data the chart is drawn from, and it is what the scraper reads. Charts made with Plotly, Highcharts and similar tools often keep their numbers in the page like this. Looking for that data is usually much easier than trying to read numbers off a picture.

If the number isn't in the page source, the site loads it separately. Open **Developer Tools → Network**, reload the page and look for a request that returns JSON. Ask Claude to help you read it.

### 3. Ask Claude to write the scraper (20 min)
Describe what you found. An example prompt:

> I want a Python script that downloads https://nwp.imd.gov.in/silam/Delhi.html, finds the `<script type="application/json">` block that holds the Plotly chart data, and saves the hourly PM2.5 and PM10 values to a CSV with one row per hour. The AQI gauges are traces with type "indicator"; save their value, date and dominating pollutant to a second CSV. Pause between requests, use an honest User-Agent, and stop with a clear error if the JSON block is missing.

Compare what Claude writes with `scripts/imd_scraper.py`. Ask Claude to explain any part you don't follow, in plain words.

### 4. Check the output (20 min): don't skip this
Open the CSV next to the IMD page.

* Pick **three values** (one gauge, two hourly points) and find each one on the page. Do they match?
* Do the dates make sense? Is the newest forecast date today or later?
* Are there gaps? (Here, every day is missing 00:00. Is that the scraper's fault or the source's? Look at the page data to decide.)
* What time zone are the timestamps in? Does the page say?

Write down anything you can't confirm. That list goes into the README's "Known limitations".

### 5. Run it every day on GitHub (20 min)
1. On this repository's GitHub page, click **Use this template** → **Create a new repository**. This gives you your own copy with the schedule included. (If you fork the repository instead, GitHub leaves the copied schedule switched off until you turn it on.)
2. Open the **Actions** tab → *Daily IMD Metro Air Quality Forecast Scraper* → **Run workflow**. Wait for the green tick, then check that the `data/` folder has been updated. If the *Commit and push* step fails with a permission error, go to **Settings → Actions → General → Workflow permissions**, choose **Read and write permissions**, and run it again.
3. The schedule is in `.github/workflows/daily_scrape.yml`. Times are written like `'17 2 * * *'`: minute 17, hour 2, in **UTC**. There are two runs, the second a backup three hours later in case the first fails. Choose minutes that aren't 0, because GitHub is busiest at the top of each hour.

### 6. Pull it into Google Sheets (10 min)
Use the `IMPORTDATA` formulas in the README, replacing `mrafiuddin50/imd-metro-aqi-forecast` with your own repository's name.

---

## Case study: Bengaluru

IMD's Bengaluru page downloads without any error. But its forecasts are for **December 2024**. The first version of this scraper saved those rows every day with that day's download date, so in Google Sheets they looked fresh.

The fix is a simple rule: *if the newest forecast hour is before today, the page is stale, so skip it and raise a warning.* Look for "Step 4" in the script.

**Lesson:** "it ran without errors" is not the same as "the data is right". Every scraper needs at least one check that the data makes sense.

---

## Exercise: add a city

1. Find another city on IMD's SILAM page and note the exact name used in its page address (`.../silam/<Name>.html`).
2. Ask Claude: *"In scripts/imd_scraper.py, add <Name> to CITIES. What else, if anything, needs to change?"*
3. Run the workflow by hand and check the new city's file using step 4 above.

---

## When things go wrong

| What you see | What it usually means | What to do |
| :--- | :--- | :--- |
| Red cross on the Actions tab | A page could not be downloaded or read. IMD may be down, or may have changed the page. | Open the failed run → *Run scraper* step and read the `::error::` line. Paste it into Claude along with the script. |
| Yellow warning, green tick | A city's page is stale. | Nothing to fix in the code. Check the page yourself. |
| `push` rejected, or "merge conflict" | Someone else committed data at the same time (often a run from a laptop). | Let only the GitHub Action commit data. Ask Claude to help you reset your local copy to match GitHub. |
| Sheet shows `#N/A` or old data | Google caches `IMPORTDATA`. | Wait an hour, or retype the formula. |
