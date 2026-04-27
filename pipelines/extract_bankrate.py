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
    # firecrawl-py v4.x uses .scrape(); older versions used .scrape_url()
    if hasattr(app, "scrape"):
        result = app.scrape(url, formats=["markdown"])
    else:
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
