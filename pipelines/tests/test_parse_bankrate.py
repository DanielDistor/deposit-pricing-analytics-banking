import re
import pytest
from datetime import date
from pipelines.parse_bankrate import extract_rates_from_markdown, normalize_bank_name

SAMPLE_SAVINGS_MARKDOWN = """
## SoFi Checking and Savings
**APY:** 3.80% APY
Minimum balance: $0

## Ally High Yield Savings Account
Up to 4.00% APY
No minimum balance required

## Marcus by Goldman Sachs Online Savings Account
4.10% APY
"""

SAMPLE_CD_MARKDOWN = """
## Barclays Online CD
**APY:** 4.20% APY
Term: 1 year (12 months)

## Ally Bank CD
4.00% APY
12-month term
"""

SAMPLE_TABLE_MARKDOWN = """
| Bank | APY | Min. Balance |
|------|-----|-------------|
| SoFi Checking and Savings | 3.80% | $0 |
| Marcus by Goldman Sachs | 4.10% | $0 |
| Ally Bank | 4.00% | $0 |
"""


def test_extract_savings_from_sections():
    rows = extract_rates_from_markdown(SAMPLE_SAVINGS_MARKDOWN, "savings", date(2026, 4, 26))
    assert len(rows) >= 2
    apys = [r["apy_pct"] for r in rows]
    assert 3.80 in apys or any(abs(a - 3.80) < 0.01 for a in apys)


def test_extract_rates_from_table():
    rows = extract_rates_from_markdown(SAMPLE_TABLE_MARKDOWN, "savings", date(2026, 4, 26))
    assert len(rows) >= 2


def test_extract_cd_rates():
    rows = extract_rates_from_markdown(SAMPLE_CD_MARKDOWN, "cd", date(2026, 4, 26))
    assert len(rows) >= 1
    assert all(r["product_type"] == "cd" for r in rows)


def test_row_schema():
    rows = extract_rates_from_markdown(SAMPLE_SAVINGS_MARKDOWN, "savings", date(2026, 4, 26))
    for row in rows:
        assert "bank_name" in row
        assert "product_type" in row
        assert "apy_pct" in row
        assert "scrape_date" in row
        assert isinstance(row["apy_pct"], float)


def test_normalize_bank_name():
    assert normalize_bank_name("Marcus by Goldman Sachs Online Savings Account") == "Marcus by Goldman Sachs"
    assert normalize_bank_name("Ally High Yield Savings Account") == "Ally Bank"
    assert normalize_bank_name("SoFi Checking and Savings") == "SoFi"


SAMPLE_DATE_TABLE_MARKDOWN = """
| Date | National average APY | Top rate APY |
|------|---------------------|-------------|
| 02/13/2026 | 4.03% | 0.60% |
| 01/23/2026 | 4.02% | 0.59% |
| 12/26/2025 | 3.95% | 0.55% |
"""


def test_rejects_date_table_rows():
    rows = extract_rates_from_markdown(SAMPLE_DATE_TABLE_MARKDOWN, "savings", date(2026, 4, 26))
    for row in rows:
        # bank_name should never be a date string
        assert not re.match(r'^\d{2}[/\-]\d{2}[/\-]\d{4}$', row["bank_name"]), \
            f"Date string leaked into bank_name: {row['bank_name']}"
