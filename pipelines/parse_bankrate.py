import os
import re
from datetime import date
from pathlib import Path
from dotenv import load_dotenv
import snowflake.connector

load_dotenv()

RAW_DIR = Path(__file__).parent.parent / "knowledge" / "raw"

BANK_NAME_MAP = {
    "sofi": "SoFi",
    "marcus by goldman sachs": "Marcus by Goldman Sachs",
    "marcus": "Marcus by Goldman Sachs",
    "ally": "Ally Bank",
    "discover": "Discover Bank",
    "american express": "American Express",
    "synchrony": "Synchrony Bank",
    "barclays": "Barclays",
    "capital one": "Capital One",
    "cit bank": "CIT Bank",
    "bread savings": "Bread Savings",
    "western alliance": "Western Alliance Bank",
    "everbank": "EverBank",
    "ufb direct": "UFB Direct",
    "varo": "Varo Bank",
    "lendingclub": "LendingClub Bank",
    "bask bank": "Bask Bank",
    "tab bank": "TAB Bank",
    "sallie mae": "Sallie Mae Bank",
    "cibc": "CIBC Bank USA",
    "my banking direct": "My Banking Direct",
    "nbkc": "NBKC Bank",
}

CD_TERM_MAP = {
    "3-month": 3, "3 month": 3, "3mo": 3,
    "6-month": 6, "6 month": 6, "6mo": 6,
    "1-year": 12, "1 year": 12, "12-month": 12, "12 month": 12,
    "2-year": 24, "2 year": 24, "24-month": 24,
    "3-year": 36, "3 year": 36, "36-month": 36,
    "5-year": 60, "5 year": 60, "60-month": 60,
}

APY_RE = re.compile(r'(\d+\.\d+)\s*%\s*(?:APY|apy)', re.IGNORECASE)
TABLE_ROW_RE = re.compile(r'\|\s*([^|]+?)\s*\|\s*(\d+\.\d+)\s*%', re.IGNORECASE)
DATE_RE = re.compile(r'^\d{2}[/\-]\d{2}[/\-]\d{4}$')


def normalize_bank_name(raw: str) -> str:
    lower = raw.lower().strip()
    for key, canonical in BANK_NAME_MAP.items():
        if key in lower:
            return canonical
    words = raw.strip().split()
    return " ".join(words[:3]) if len(words) >= 3 else raw.strip()


def extract_term_months(text: str) -> int | None:
    lower = text.lower()
    for phrase, months in CD_TERM_MAP.items():
        if phrase in lower:
            return months
    return None


def extract_rates_from_markdown(markdown: str, product_type: str, scrape_date: date) -> list[dict]:
    rows = []
    seen_banks = set()

    # Strategy 1: parse markdown tables
    for line in markdown.splitlines():
        m = TABLE_ROW_RE.match(line.strip())
        if m:
            bank_raw, apy_str = m.group(1), m.group(2)
            if DATE_RE.match(bank_raw.strip()):
                continue  # skip historical date rows
            bank = normalize_bank_name(bank_raw)
            if bank.lower() in ("bank", "institution", "bank name") or not bank:
                continue
            apy = float(apy_str)
            term = extract_term_months(line) if product_type == "cd" else None
            key = (bank, term)
            if key not in seen_banks:
                seen_banks.add(key)
                rows.append({
                    "bank_name": bank,
                    "product_type": product_type,
                    "term_months": term,
                    "apy_pct": apy,
                    "scrape_date": scrape_date,
                })

    if rows:
        return rows

    # Strategy 2: section-based parsing (## Bank Name ... APY%)
    sections = re.split(r'\n#{1,3}\s+', markdown)
    for section in sections:
        lines = section.strip().splitlines()
        if not lines:
            continue
        header = lines[0].strip()
        bank = normalize_bank_name(header)
        if not bank:
            continue

        if any(skip in header.lower() for skip in ["table of contents", "overview", "methodology", "faq", "editorial", "advertiser", "sponsored", "competition", "picks"]):
            continue

        content = "\n".join(lines)
        apy_matches = APY_RE.findall(content)
        if not apy_matches:
            continue

        apy = float(apy_matches[0])
        term = extract_term_months(content) if product_type == "cd" else None
        key = (bank, term)
        if key not in seen_banks:
            seen_banks.add(key)
            rows.append({
                "bank_name": bank,
                "product_type": product_type,
                "term_months": term,
                "apy_pct": apy,
                "scrape_date": scrape_date,
            })

    return rows


def load_to_snowflake(rows: list[dict]) -> None:
    if not rows:
        print("No rows to load.")
        return

    conn = snowflake.connector.connect(
        account=os.getenv("SNOWFLAKE_ACCOUNT"),
        user=os.getenv("SNOWFLAKE_USER"),
        password=os.getenv("SNOWFLAKE_PASSWORD"),
        role="ACCOUNTADMIN",
    )
    cur = conn.cursor()
    try:
        cur.execute("USE WAREHOUSE COMPUTE_WH")
        cur.execute("USE DATABASE DEPOSIT_ANALYTICS")
        cur.execute("USE SCHEMA RAW")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS BANKRATE_RATES (
                bank_name    VARCHAR(100),
                product_type VARCHAR(20),
                term_months  INTEGER,
                apy_pct      FLOAT,
                scrape_date  DATE,
                loaded_at    TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
            )
        """)
        cur.execute("TRUNCATE TABLE IF EXISTS BANKRATE_RATES")
        cur.executemany(
            """INSERT INTO BANKRATE_RATES (bank_name, product_type, term_months, apy_pct, scrape_date)
               VALUES (%s, %s, %s, %s, %s)""",
            [(r["bank_name"], r["product_type"], r["term_months"], r["apy_pct"], r["scrape_date"])
             for r in rows],
        )
        conn.commit()
        cur.execute("SELECT COUNT(*) FROM BANKRATE_RATES")
        count = cur.fetchone()[0]
        print(f"Loaded {count} rows to DEPOSIT_ANALYTICS.RAW.BANKRATE_RATES")
    finally:
        cur.close()
        conn.close()


def main():
    all_rows = []
    for md_file in sorted(RAW_DIR.glob("bankrate_savings_*.md")):
        print(f"Parsing {md_file.name}...")
        scrape_date = date.fromisoformat(md_file.stem.split("_")[-1])
        markdown = md_file.read_text(encoding="utf-8")
        rows = extract_rates_from_markdown(markdown, "savings", scrape_date)
        print(f"  Found {len(rows)} savings rates")
        all_rows.extend(rows)

    for md_file in sorted(RAW_DIR.glob("bankrate_cds_*.md")):
        print(f"Parsing {md_file.name}...")
        scrape_date = date.fromisoformat(md_file.stem.split("_")[-1])
        markdown = md_file.read_text(encoding="utf-8")
        rows = extract_rates_from_markdown(markdown, "cd", scrape_date)
        print(f"  Found {len(rows)} CD rates")
        all_rows.extend(rows)

    print(f"\nTotal: {len(all_rows)} rows across all files")
    load_to_snowflake(all_rows)


if __name__ == "__main__":
    main()
