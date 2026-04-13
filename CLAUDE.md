# Project Context

## Job Posting
- **Role:** Wealth Management Solutions Deposit Pricing Analytics – Associate
- **Company:** JPMorganChase
- **Location:** New York, NY
- **SQL requirement:** "Strong proficiency with SQL, Python, SAS, Tableau"

## Project Summary
This is an analytics engineering portfolio project for LMU ISBA-4715. The project tracks
deposit pricing trends across major U.S. banks relative to Federal Reserve rate changes,
built to demonstrate the skills required by the target job posting.

## Business Question
When the Fed raises or lowers interest rates, how do major banks respond with their deposit
pricing? Which banks pass through rate changes fastest? Who is winning deposits?

## Tech Stack
- **Data Warehouse:** Snowflake (AWS US East 1)
- **Transformation:** dbt (raw → staging → mart)
- **Orchestration:** GitHub Actions (scheduled)
- **Dashboard:** Streamlit (deployed to Streamlit Community Cloud)
- **IDE:** Cursor + Claude Code + Superpowers

## Data Sources
- **Source 1 (API):** FRED API — Federal Reserve rate data, Treasury yields, macro indicators
- **Source 2 (Scrape):** Bank deposit rates from Bankrate or individual bank websites

## Star Schema
- **Fact table:** deposit rates over time (bank, product type, rate, date)
- **Dimensions:** banks, product types (savings/CD/money market), Fed rate cycles

## Dashboard Analytics
- **Descriptive:** How have deposit rates changed across major banks over the last 2 years?
- **Diagnostic:** Which banks lagged the Fed the most during rate hikes? Who passed through the most?

## Knowledge Base
- Raw scraped sources stored in `knowledge/raw/` (15+ sources from 3+ sites/authors)
- Claude Code-generated wiki pages in `knowledge/wiki/` (overview, key entities, themes)
- Index at `knowledge/index.md`

### How to Query the Knowledge Base
To answer questions about deposit pricing trends, bank strategies, or Fed rate policy:
1. Read all relevant wiki pages in `knowledge/wiki/`
2. Cross-reference with raw sources in `knowledge/raw/` when more detail is needed
3. Synthesize across sources — do not summarize individual files in isolation
4. Ground answers in specific banks, dates, and rate figures where available

## Directory Structure
```
deposit-pricing-analytics-banking/
├── docs/
│   ├── job-posting.pdf
│   ├── proposal.md
│   └── resume.pdf          # added at final submission
├── knowledge/
│   ├── raw/                # scraped sources
│   ├── wiki/               # Claude Code-generated synthesis pages
│   └── index.md
├── dbt/                    # dbt project
├── pipelines/              # GitHub Actions workflows
├── dashboard/              # Streamlit app
├── CLAUDE.md
├── README.md
└── .gitignore
```

## Credentials
All credentials (Snowflake, FRED API key) are stored in `.env` and never committed to git.
