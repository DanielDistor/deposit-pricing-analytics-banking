# Deposit Pricing Analytics

> **Tracking how major U.S. banks respond to Federal Reserve rate changes — and which banks pass the most value to savers.**

**Live Dashboard:** [STREAMLIT_DASHBOARD_URL]

---

## Business Question

When the Fed raises or lowers interest rates, how do major banks respond with their deposit pricing? Which banks pass through rate changes fastest, and who is winning deposits?

**Why it matters:** During the 2022–2023 rate hiking cycle, the Fed raised rates from ~0% to 5.25% — the fastest increase in 40 years. Online banks (Marcus, Ally, SoFi) tracked the Fed closely, raising savings APYs by 4–5%. Big traditional banks (Chase, BofA, Wells Fargo) barely moved. A $100,000 deposit at a top online bank earned ~$4,000–$5,000 more per year than the same deposit at a big bank.

---

## Tech Stack

| Layer | Tool |
|-------|------|
| IDE | Cursor + Claude Code |
| Data Warehouse | Snowflake |
| Transformation | dbt |
| Orchestration | GitHub Actions (weekly schedule) |
| Dashboard | Streamlit (Community Cloud) |
| Knowledge Base | Claude Code + Firecrawl |
| Version Control | Git + GitHub |

---

## Data Sources

| Source | Type | Destination |
|--------|------|-------------|
| [FRED API](https://fred.stlouisfed.org/) | REST API | `DEPOSIT_ANALYTICS.RAW.FRED_OBSERVATIONS` |
| [Bankrate](https://www.bankrate.com/) | Firecrawl scrape | `knowledge/raw/` → `DEPOSIT_ANALYTICS.RAW.BANKRATE_RATES` |
| Big Four seeds | CSV | `dbt/seeds/big_four_rates.csv` |

FRED series loaded: Fed Funds Rate (monthly + daily), 3-Month/1-Year/2-Year/5-Year/10-Year Treasury yields, Discount Window Rate.

---

## Pipeline Diagram

```mermaid
flowchart LR
    FRED[FRED API] -->|extract_fred.py\nGitHub Actions| RAW_FRED[(RAW.FRED_OBSERVATIONS\nSnowflake)]
    BANKRATE[Bankrate\nFirecrawl Scrape] -->|extract_bankrate.py\nGitHub Actions| KB[knowledge/raw/\nMarkdown Files]
    KB -->|parse_bankrate.py| RAW_BANK[(RAW.BANKRATE_RATES\nSnowflake)]
    BIG4[Big 4 Seeds\nCSV] -->|dbt seed| STG_BANK
    KB -->|Claude Code| WIKI[knowledge/wiki/\nSynthesis Pages]
    RAW_FRED --> STG_FRED[stg_fred_observations\nStaging View]
    RAW_BANK --> STG_BANK[stg_bankrate_rates\nStaging View]
    STG_FRED --> FACT[fact_deposit_rates\nMart Table]
    STG_BANK --> FACT
    STG_BANK --> DIM_BANK[dim_bank]
    STG_BANK --> DIM_PROD[dim_product]
    STG_FRED --> DIM_DATE[dim_date]
    DIM_BANK --> FACT
    DIM_PROD --> FACT
    DIM_DATE --> FACT
    FACT -->|Streamlit| DASH[Dashboard\nStreamlit Cloud]
```

---

## ERD

```mermaid
erDiagram
    FACT_DEPOSIT_RATES {
        int bank_key FK
        int product_key FK
        date scrape_date
        float apy_pct
        float fed_funds_rate
        float spread_pct
        float passthrough_pct
        string source_name
    }
    DIM_BANK {
        int bank_key PK
        string bank_name
        string bank_type
    }
    DIM_PRODUCT {
        int product_key PK
        string product_name
        int term_months
        string product_display_name
    }
    DIM_DATE {
        date date_day PK
        int year
        int month
        int quarter
        string fed_rate_cycle
    }

    FACT_DEPOSIT_RATES }o--|| DIM_BANK : "bank_key"
    FACT_DEPOSIT_RATES }o--|| DIM_PRODUCT : "product_key"
    FACT_DEPOSIT_RATES }o--|| DIM_DATE : "scrape_date"
```

---

## Key Insights

- **Online banks tracked the Fed:** During the 2022–2023 hiking cycle, online banks like Marcus by Goldman Sachs and Ally raised savings APYs by 4–5%, closely matching the 5.25% Fed funds rate.
- **Big banks kept the spread:** JPMorgan Chase, Bank of America, and Wells Fargo savings accounts stayed near 0.01% APY — capturing 5%+ of margin on every deposited dollar.
- **Pass-through gap is stark:** Top online banks pass through 100%+ of the Fed rate; Chase savings pass-through is under 1%.
- **Client recommendation:** A $100,000 deposit in a top online savings account earns ~$4,000–$5,000 more per year than the same deposit at a big bank.

---

## Dashboard

**Live URL:** [STREAMLIT_DASHBOARD_URL]

Four tabs:
1. **Current Rates** — Ranked table of all bank deposit rates with APY gradient
2. **Rate Timeline** — Fed funds rate history vs. current bank rates
3. **Pass-Through Analysis** — Bar chart ranking banks by how much of the Fed hike they shared with savers
4. **Bank Recommender** — Enter deposit amount → get ranked recommendation with projected annual earnings

---

## Pipeline Setup (Local)

```bash
# Clone and install
git clone https://github.com/DanielDistor/deposit-pricing-analytics-banking.git
cd deposit-pricing-analytics-banking
pip install -r requirements.txt

# Configure credentials (.env file)
# Required: SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, SNOWFLAKE_PASSWORD, FRED_API_KEY, FIRECRAWL_API_KEY

# Run extraction
python pipelines/extract_fred.py
python pipelines/extract_bankrate.py
python pipelines/parse_bankrate.py

# Run dbt
cd dbt
dbt seed
dbt run
dbt test
```

---

## Knowledge Base

Scraped sources and synthesized wiki pages are in `knowledge/`. To query the knowledge base:

Ask Claude Code: *"What does the knowledge base say about how Chase responded to Fed rate hikes?"*

See [`knowledge/index.md`](knowledge/index.md) for all sources and wiki pages.

---

## Project Context

Built for LMU ISBA-4715 (Analytics Engineering), targeting the **JPMorgan Chase Wealth Management Deposit Pricing Analytics Associate** role. The project demonstrates SQL, dimensional modeling, data pipelines, and analytics skills directly required by the posting.
