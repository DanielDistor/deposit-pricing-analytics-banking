# Milestone 02: Transform, Present & Polish — Design Spec

**Date:** 2026-05-02
**Due:** 2026-05-04 9:55 AM
**Points:** 65

---

## Business Question

When the Fed raises or lowers interest rates, how do major U.S. banks respond with their deposit pricing? Which banks pass through rate changes to savers, and which keep the spread as margin?

The client goal: find the bank paying the highest rate so their money grows the most. The analyst goal: explain *why* some banks are better than others and back it up with data.

---

## Overview

Milestone 02 transforms the raw data from Milestone 01 into a full analytics stack: structured Snowflake mart, Streamlit dashboard, automated pipelines, expanded knowledge base, and polished documentation.

---

## Deliverable 6: dbt Project (15 pts)

### New pipeline step (pre-dbt)

**`pipelines/parse_bankrate.py`**
- Reads existing markdown files from `knowledge/raw/bankrate_savings_*.md` and `knowledge/raw/bankrate_cds_*.md`
- Extracts bank name, product type (savings/CD), APY, term (for CDs), and scrape date via regex
- Loads structured rows to `DEPOSIT_ANALYTICS.RAW.BANKRATE_RATES` in Snowflake

**Table schema:**
```sql
CREATE TABLE IF NOT EXISTS RAW.BANKRATE_RATES (
    bank_name      VARCHAR(100),
    product_type   VARCHAR(20),   -- 'savings' or 'cd'
    term_months    INTEGER,       -- NULL for savings, 3/6/12/36/60 for CDs
    apy_pct        FLOAT,
    scrape_date    DATE,
    loaded_at      TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
)
```

**`seeds/big_four_rates.csv`**
- Manually curated current savings + CD rates for Chase, Bank of America, Wells Fargo, Citibank
- ~16 rows, same schema as BANKRATE_RATES
- Provides the traditional bank low-pass-through contrast

### dbt project structure

```
dbt/
├── dbt_project.yml
├── profiles.yml          # Snowflake connection (uses env vars)
├── seeds/
│   └── big_four_rates.csv
├── models/
│   ├── staging/
│   │   ├── stg_fred_observations.sql    # clean FRED data, rename cols, cast types
│   │   ├── stg_bankrate_rates.sql       # clean bankrate + seeds union, standardize names
│   │   └── schema.yml                   # source definitions + tests
│   └── mart/
│       ├── dim_bank.sql                 # bank_id, bank_name, bank_type (online/traditional)
│       ├── dim_product.sql              # product_id, product_name, term_months
│       ├── dim_date.sql                 # date_key, year, month, quarter, fed_rate_cycle
│       ├── fact_deposit_rates.sql       # one row per bank/product/date, joins all dims
│       └── schema.yml                   # mart tests
```

### Data scope note

Bankrate provides a **point-in-time snapshot** of current bank rates (one scrape date). FRED provides full historical rate data back to 2000. The star schema reflects this: FRED data enables historical timeline charts; bank rates show where each bank stands today relative to the Fed. The pass-through calculation compares current bank APY to the current Fed rate. The big_four_rates seed can include a pre-hike rate (e.g., Jan 2022) alongside the current rate to calculate actual pass-through delta for the big 4.

### Star schema

**`fact_deposit_rates`**
- `date_key` (FK → dim_date)
- `bank_key` (FK → dim_bank)
- `product_key` (FK → dim_product)
- `apy_pct` — bank's deposit rate
- `fed_funds_rate` — Fed rate on that date (from FRED, denormalized for query simplicity)
- `spread_bps` — (fed_funds_rate − apy_pct) × 100, how much the bank kept

**`dim_bank`**
- `bank_key`, `bank_name`, `bank_type` (online / traditional), `parent_company`

**`dim_product`**
- `product_key`, `product_name` (savings / cd), `term_months`

**`dim_date`**
- `date_key`, `date`, `year`, `month`, `quarter`, `fed_rate_cycle` (hiking / cutting / hold)

### dbt tests
- `not_null` and `unique` on all primary keys
- `accepted_values` on `bank_type` and `product_name`
- `relationships` between fact and dimension tables

---

## Deliverable 7: Streamlit Dashboard (15 pts)

**File:** `dashboard/app.py`
**Connection:** Snowflake mart tables via `snowflake-connector-python` + `st.secrets`
**Deployment:** Streamlit Community Cloud (public URL)

### Four tabs

**Tab 1 — Current Rates**
*"A snapshot of today's deposit rates across all banks, ranked by APY. See at a glance who is paying the most."*
- Sortable table: Bank | Type | Product | Current APY | vs. Fed Rate | Spread
- Color-coded: green for high pass-through banks, red for low

**Tab 2 — Rate Timeline**
*"How have deposit rates changed over the last 2+ years relative to the Federal Reserve's benchmark rate? This view shows who tracked the Fed and who didn't."*
- Line chart: Fed funds rate + one line per bank over time
- Interactive: multi-select bank filter, product type toggle (savings / CD)

**Tab 3 — Pass-Through Analysis**
*"When the Fed raised rates by 5.25% between 2022–2023, how much of that increase did each bank pass on to savers? Higher is better for the client."*
- Horizontal bar chart: bank ranked by pass-through % (rate increase ÷ Fed increase)
- Interactive: product type filter

**Tab 4 — Bank Recommender**
*"Based on current rates and historical fairness, which bank should your client choose — and how much will they earn on their deposit?"*
- Inputs: deposit amount (slider), product type (savings / CD), term (if CD)
- Output: ranked table of top 5 banks with current APY + projected annual earnings in dollars
- One-line rationale per bank (e.g. "Marcus has consistently tracked Fed rate increases")

---

## Deliverable 8: GitHub Actions Pipelines (5 pts)

**`.github/workflows/extract-fred.yml`**
- Schedule: weekly on Sunday at 6 AM UTC
- Manual trigger: `workflow_dispatch`
- Runs: `pipelines/extract_fred.py`
- Secrets: `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`, `SNOWFLAKE_PASSWORD`, `FRED_API_KEY`

**`.github/workflows/extract-bankrate.yml`**
- Schedule: weekly on Sunday at 6 AM UTC
- Manual trigger: `workflow_dispatch`
- Runs: `pipelines/extract_bankrate.py` then `pipelines/parse_bankrate.py`
- Secrets: `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`, `SNOWFLAKE_PASSWORD`, `FIRECRAWL_API_KEY`

Both workflows install dependencies from `requirements.txt` and use `ubuntu-latest`.

---

## Deliverable 9: Pipeline Diagram (5 pts)

Mermaid diagram embedded in `README.md`:

```
FRED API → RAW.FRED_OBSERVATIONS → stg_fred_observations → fact_deposit_rates → Streamlit Dashboard
Bankrate (Firecrawl) → knowledge/raw/ → RAW.BANKRATE_RATES → stg_bankrate_rates → fact_deposit_rates
                      ↘ knowledge/wiki/ (Claude Code synthesis) ← knowledge/raw/
Big 4 Seeds (CSV) → dbt seeds → stg_bankrate_rates
```

All layers labeled: source → raw → staging → mart → presentation.

---

## Deliverable 10: Presentation Slides (7 pts)

**Format:** Google Slides exported as PDF, saved to `docs/slides.pdf`

**Structure:**
1. Title slide: "Deposit Pricing Analytics: Who Passes Through Fed Rate Hikes to Savers?"
2. Descriptive insight: Rate Timeline chart — *"Online banks tracked the Fed; big banks didn't move"* + callout on the 2022–2023 hike cycle
3. Diagnostic insight: Pass-Through bar chart — *"Marcus passed through 75% of Fed hikes; Chase passed through under 5%"* + callout on the widest spreads
4. Recommendation: *"Clients seeking maximum deposit growth should use [top bank] — projected $X more per year on a $100K deposit vs. Chase"*

---

## Deliverable 11: Knowledge Base (8 pts)

**Target:** 15+ raw files from 4+ sites

| Source | Site | Est. Files |
|--------|------|-----------|
| Savings + CD roundup pages | bankrate.com | 2 (done) |
| Fed rate impact articles | bankrate.com | 3 |
| Best savings + CD articles | nerdwallet.com | 3 |
| Individual bank pages (Chase, Marcus, Ally, SoFi) | bank websites | 4 |
| Fed rate decision press releases | federalreserve.gov | 3 |

**Wiki pages (Claude Code generated):**
- `knowledge/wiki/overview.md` — what deposit pricing is, how the Fed rate cycle works, why spreads matter
- `knowledge/wiki/key-entities.md` — bank profiles, product type definitions, rate terminology
- `knowledge/wiki/fed-rate-cycle-analysis.md` — synthesis: 2022–2023 hiking cycle, who won and lost, pass-through analysis across banks

**`knowledge/index.md`** — lists all wiki pages with one-line summaries

---

## Deliverables 12–14: README, ERD, Repo Polish (10 pts)

**`README.md`** using class template:
- Project overview + business question
- Tech stack table
- Pipeline setup instructions
- Mermaid pipeline diagram
- Mermaid ERD
- Insights summary (2–3 bullet points)
- Streamlit dashboard public URL

**ERD** — Mermaid diagram showing fact + dimension table relationships, generated from dbt model definitions, embedded in README.

**Repo cleanup:**
- Standardize file naming (snake_case throughout)
- Remove `.DS_Store`, test outputs, scratch files from git
- Verify `.gitignore` covers all credentials and temp files

---

## Build Order

1. `pipelines/parse_bankrate.py` — structured bankrate data into Snowflake
2. dbt project — staging → mart, tests passing
3. Knowledge base expansion — scrape 13+ more sources, generate wiki pages
4. Streamlit dashboard — connect to mart, 4 tabs, deploy
5. GitHub Actions — both workflows
6. README + ERD + pipeline diagram
7. Slides

---

## Success Criteria

- `dbt run` and `dbt test` execute without errors, models materialized in Snowflake
- Streamlit app loads with live data from Snowflake mart tables, public URL accessible
- Both GitHub Actions workflows run successfully with secrets (not hardcoded credentials)
- `knowledge/raw/` has 15+ files from 4+ different sites
- `knowledge/wiki/` has 3 synthesized pages + `index.md`
- README includes ERD, pipeline diagram, and public dashboard URL
- No credentials, scratch files, or `.DS_Store` committed to git
