# Milestone 01: Extract & Load — Design Spec

**Date:** 2026-04-26
**Due:** 2026-04-27 9:55 AM
**Points:** 20 (10 + 10)

---

## Overview

Two independent extraction scripts that land data in their respective destinations. No orchestration, no transformation, no dashboard.

---

## Deliverable 4: Source 1 — FRED API → Snowflake RAW (10 pts)

### Script
`pipelines/extract_fred.py`

### What it pulls
8 FRED series relevant to deposit pricing analytics:

| Series ID | Description |
|-----------|-------------|
| `FEDFUNDS` | Effective Federal Funds Rate (monthly) |
| `DFF` | Federal Funds Effective Rate (daily) |
| `TB3MS` | 3-Month Treasury Bill Secondary Market Rate |
| `GS1` | 1-Year Treasury Constant Maturity Rate |
| `GS2` | 2-Year Treasury Constant Maturity Rate |
| `GS5` | 5-Year Treasury Constant Maturity Rate |
| `GS10` | 10-Year Treasury Constant Maturity Rate |
| `DPCREDIT` | Discount Window Primary Credit Rate |

### Snowflake objects created on first run
- **Database:** `DEPOSIT_ANALYTICS`
- **Schema:** `RAW`
- **Warehouse:** `COMPUTE_WH` (X-Small, auto-suspend 60s)
- **Table:** `RAW.FRED_OBSERVATIONS`

### Table schema
```sql
CREATE TABLE IF NOT EXISTS RAW.FRED_OBSERVATIONS (
    series_id        VARCHAR(20),
    observation_date DATE,
    value            FLOAT,
    loaded_at        TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    PRIMARY KEY (series_id, observation_date)
);
```

### Approach
- `requests` for FRED API calls (no extra library)
- `snowflake-connector-python` for Snowflake writes
- `python-dotenv` for credential loading
- Upsert via `MERGE` so re-runs are idempotent
- Pulls full history (observation_start=2000-01-01)

### Credentials (env vars)
```
FRED_API_KEY=...
SNOWFLAKE_ACCOUNT=...
SNOWFLAKE_USER=...
SNOWFLAKE_PASSWORD=...
SNOWFLAKE_WAREHOUSE=COMPUTE_WH
SNOWFLAKE_DATABASE=DEPOSIT_ANALYTICS
SNOWFLAKE_SCHEMA=RAW
```

---

## Deliverable 5: Source 2 — Firecrawl Web Scrape → knowledge/raw/ (10 pts)

### Script
`pipelines/extract_bankrate.py`

### What it scrapes
Two Bankrate pages listing deposit rates across major U.S. banks:
1. Best high-yield savings account rates
2. Best CD rates

### Output
Two markdown files written to `knowledge/raw/`, timestamped by run date:
- `knowledge/raw/bankrate_savings_YYYY-MM-DD.md`
- `knowledge/raw/bankrate_cds_YYYY-MM-DD.md`

### Approach
- `firecrawl-py` library, `scrape` endpoint (not crawl — just 2 specific pages)
- Returns clean markdown of page content
- Writes raw markdown directly to file — no parsing, no transformation
- `python-dotenv` for credential loading

### Credentials (env vars)
```
FIRECRAWL_API_KEY=...
```

---

## Supporting Files

### `.env` (never committed)
All 5 credentials stored here, loaded at runtime.

### `requirements.txt`
```
requests
snowflake-connector-python
firecrawl-py
python-dotenv
```

---

## Success Criteria
- `python pipelines/extract_fred.py` runs without error and rows appear in `DEPOSIT_ANALYTICS.RAW.FRED_OBSERVATIONS`
- `python pipelines/extract_bankrate.py` runs without error and two `.md` files appear in `knowledge/raw/`
- No credentials committed to git
