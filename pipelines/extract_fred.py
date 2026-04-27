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
