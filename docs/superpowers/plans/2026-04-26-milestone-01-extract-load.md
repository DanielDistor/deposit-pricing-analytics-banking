# Milestone 01: Extract & Load Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Write two Python extraction scripts — one pulling FRED API data into Snowflake RAW, one scraping Bankrate pages into knowledge/raw/ as markdown.

**Architecture:** Two independent scripts under `pipelines/`. Each loads credentials from `.env` via `python-dotenv`. Source 1 uses `requests` + `snowflake-connector-python`. Source 2 uses `firecrawl-py`. No shared code between them.

**Tech Stack:** Python 3.11+, requests, snowflake-connector-python, firecrawl-py, python-dotenv

---

## File Map

| File | Action | Purpose |
|------|--------|---------|
| `.env` | Create | All credentials, never committed |
| `requirements.txt` | Create | Python dependencies |
| `pipelines/__init__.py` | Create | Makes pipelines a package |
| `pipelines/extract_fred.py` | Create | FRED API → Snowflake RAW |
| `pipelines/extract_bankrate.py` | Create | Firecrawl → knowledge/raw/ |
| `knowledge/raw/.gitkeep` | Create | Ensures directory tracked in git |

---

## Task 1: Environment Setup

**Files:**
- Create: `.env`
- Create: `requirements.txt`

- [ ] **Step 1: Create `.env` with all credentials**

Create `.env` in the project root — fill in values from your own credentials (stored securely, never committed):

```
FRED_API_KEY=<your_fred_api_key>
SNOWFLAKE_ACCOUNT=<your_account_identifier>
SNOWFLAKE_USER=<your_snowflake_username>
SNOWFLAKE_PASSWORD=<your_snowflake_password>
SNOWFLAKE_WAREHOUSE=COMPUTE_WH
SNOWFLAKE_DATABASE=DEPOSIT_ANALYTICS
SNOWFLAKE_SCHEMA=RAW
FIRECRAWL_API_KEY=<your_firecrawl_api_key>
```

- [ ] **Step 2: Verify `.env` is gitignored**

Run:
```bash
grep -n "\.env" .gitignore
```
Expected output includes a line matching `.env`. If not present, add `.env` to `.gitignore`.

- [ ] **Step 3: Create `requirements.txt`**

```
requests>=2.31.0
snowflake-connector-python>=3.6.0
firecrawl-py>=1.0.0
python-dotenv>=1.0.0
```

- [ ] **Step 4: Install dependencies**

Run:
```bash
pip install -r requirements.txt
```
Expected: All packages install without error. `snowflake-connector-python` installs fast because it uses a binary wheel.

- [ ] **Step 5: Create directory structure**

Run:
```bash
mkdir -p pipelines knowledge/raw
touch pipelines/__init__.py knowledge/raw/.gitkeep
```

- [ ] **Step 6: Commit**

```bash
git add requirements.txt pipelines/__init__.py knowledge/raw/.gitkeep
git commit -m "feat: add requirements and directory structure for pipelines"
```

Note: Do NOT `git add .env` — it must stay untracked.

---

## Task 2: FRED Extraction Script

**Files:**
- Create: `pipelines/extract_fred.py`

- [ ] **Step 1: Write `pipelines/extract_fred.py`**

```python
import os
import sys
import requests
from dotenv import load_dotenv
import snowflake.connector

load_dotenv()

FRED_API_KEY = os.getenv("FRED_API_KEY")
SERIES = ["FEDFUNDS", "DFF", "TB3MS", "GS1", "GS2", "GS5", "GS10", "DPCREDIT"]


def fetch_series(series_id: str) -> list[tuple]:
    url = "https://api.stlouisfed.org/fred/series/observations"
    params = {
        "series_id": series_id,
        "api_key": FRED_API_KEY,
        "file_type": "json",
        "observation_start": "2000-01-01",
    }
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    observations = r.json()["observations"]
    return [
        (series_id, obs["date"], float(obs["value"]))
        for obs in observations
        if obs["value"] != "."
    ]


def setup_snowflake(cur):
    cur.execute("CREATE WAREHOUSE IF NOT EXISTS COMPUTE_WH WITH WAREHOUSE_SIZE='X-SMALL' AUTO_SUSPEND=60 AUTO_RESUME=TRUE")
    cur.execute("USE WAREHOUSE COMPUTE_WH")
    cur.execute("CREATE DATABASE IF NOT EXISTS DEPOSIT_ANALYTICS")
    cur.execute("CREATE SCHEMA IF NOT EXISTS DEPOSIT_ANALYTICS.RAW")
    cur.execute("USE DATABASE DEPOSIT_ANALYTICS")
    cur.execute("USE SCHEMA RAW")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS FRED_OBSERVATIONS (
            series_id        VARCHAR(20),
            observation_date DATE,
            value            FLOAT,
            loaded_at        TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
            PRIMARY KEY (series_id, observation_date)
        )
    """)


def load_rows(cur, rows: list[tuple], batch_size: int = 1000):
    cur.execute("TRUNCATE TABLE IF EXISTS FRED_OBSERVATIONS")
    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]
        cur.executemany(
            "INSERT INTO FRED_OBSERVATIONS (series_id, observation_date, value) VALUES (%s, %s, %s)",
            batch,
        )


def main():
    print("Connecting to Snowflake...")
    conn = snowflake.connector.connect(
        account=os.getenv("SNOWFLAKE_ACCOUNT"),
        user=os.getenv("SNOWFLAKE_USER"),
        password=os.getenv("SNOWFLAKE_PASSWORD"),
        role="ACCOUNTADMIN",
    )
    cur = conn.cursor()

    print("Setting up Snowflake objects...")
    setup_snowflake(cur)

    all_rows: list[tuple] = []
    for series_id in SERIES:
        print(f"  Fetching {series_id}...", end=" ", flush=True)
        rows = fetch_series(series_id)
        all_rows.extend(rows)
        print(f"{len(rows)} observations")

    print(f"\nLoading {len(all_rows)} total rows to Snowflake...")
    load_rows(cur, all_rows)
    conn.commit()

    cur.execute("SELECT COUNT(*) FROM FRED_OBSERVATIONS")
    count = cur.fetchone()[0]
    print(f"Verified: {count} rows in DEPOSIT_ANALYTICS.RAW.FRED_OBSERVATIONS")

    cur.close()
    conn.close()
    print("Done!")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the script**

Run from project root:
```bash
python pipelines/extract_fred.py
```

Expected output (exact numbers may vary slightly):
```
Connecting to Snowflake...
Setting up Snowflake objects...
  Fetching FEDFUNDS... 303 observations
  Fetching DFF... 6800 observations
  Fetching TB3MS... 303 observations
  Fetching GS1... 303 observations
  Fetching GS2... 303 observations
  Fetching GS5... 303 observations
  Fetching GS10... 303 observations
  Fetching DPCREDIT... 303 observations

Loading 9121 total rows to Snowflake...
Verified: 9121 rows in DEPOSIT_ANALYTICS.RAW.FRED_OBSERVATIONS
Done!
```

- [ ] **Step 3: Verify in Snowflake UI**

Log into app.snowflake.com → Worksheets → run:
```sql
SELECT series_id, COUNT(*) as obs, MIN(observation_date) as first, MAX(observation_date) as last
FROM DEPOSIT_ANALYTICS.RAW.FRED_OBSERVATIONS
GROUP BY series_id
ORDER BY series_id;
```
Expected: 8 rows, one per series, all with `first` date around 2000-01-01.

- [ ] **Step 4: Commit**

```bash
git add pipelines/extract_fred.py
git commit -m "feat: FRED API extraction script loads 8 series to Snowflake RAW"
```

---

## Task 3: Bankrate Scrape Script

**Files:**
- Create: `pipelines/extract_bankrate.py`

- [ ] **Step 1: Write `pipelines/extract_bankrate.py`**

```python
import os
from datetime import date
from pathlib import Path
from dotenv import load_dotenv
from firecrawl import FirecrawlApp

load_dotenv()

OUTPUT_DIR = Path("knowledge/raw")

TARGETS = [
    {
        "url": "https://www.bankrate.com/banking/savings/best-high-yield-interests-savings-accounts/",
        "slug": "bankrate_savings",
    },
    {
        "url": "https://www.bankrate.com/banking/cds/best-cd-rates/",
        "slug": "bankrate_cds",
    },
]


def scrape_page(app: FirecrawlApp, url: str) -> str:
    result = app.scrape_url(url, formats=["markdown"])
    if isinstance(result, dict):
        return result.get("markdown") or result.get("content", "")
    return result.markdown


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    app = FirecrawlApp(api_key=os.getenv("FIRECRAWL_API_KEY"))
    today = date.today().isoformat()

    for target in TARGETS:
        print(f"Scraping {target['url']}...", flush=True)
        markdown = scrape_page(app, target["url"])
        out_path = OUTPUT_DIR / f"{target['slug']}_{today}.md"
        out_path.write_text(markdown, encoding="utf-8")
        print(f"  Saved: {out_path} ({len(markdown):,} chars)")

    print("Done!")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the script**

Run from project root:
```bash
python pipelines/extract_bankrate.py
```

Expected output:
```
Scraping https://www.bankrate.com/banking/savings/best-high-yield-interests-savings-accounts/...
  Saved: knowledge/raw/bankrate_savings_2026-04-26.md (45,000+ chars)
Scraping https://www.bankrate.com/banking/cds/best-cd-rates/...
  Saved: knowledge/raw/bankrate_cds_2026-04-26.md (30,000+ chars)
Done!
```

- [ ] **Step 3: Verify output files exist and contain rate data**

Run:
```bash
ls -lh knowledge/raw/
head -100 knowledge/raw/bankrate_savings_2026-04-26.md
```

Expected: Two `.md` files, both non-empty, the savings file should contain bank names and APY percentages.

- [ ] **Step 4: Commit**

```bash
git add pipelines/extract_bankrate.py knowledge/raw/.gitkeep
git commit -m "feat: Firecrawl scrape script writes Bankrate deposit rates to knowledge/raw/"
```

Note: Do NOT add the `.md` scrape outputs to git — they are data files, not code. The `.gitkeep` is already committed from Task 1.

---

## Task 4: Final Verification & Submission Commit

- [ ] **Step 1: Run both scripts end-to-end one final time**

```bash
python pipelines/extract_fred.py && python pipelines/extract_bankrate.py
```

Both should exit cleanly with no errors.

- [ ] **Step 2: Confirm no credentials in git history**

```bash
git log --all --full-history -p | grep -E "418d0f|Snowflake0456|fc-26dba|DGODISTOR" | head -5
```

Expected: No output. If credentials appear, stop and ask for help before pushing.

- [ ] **Step 3: Final commit**

```bash
git status
```

Expected: `.env` is NOT listed (it's gitignored). Only committed files are visible. If `git status` is clean, no commit needed. If there are any uncommitted changes, commit them now.

- [ ] **Step 4: Push to GitHub**

```bash
git push origin main
```

Then submit the repo URL to Brightspace.
