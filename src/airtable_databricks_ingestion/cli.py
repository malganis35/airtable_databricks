import asyncio
from .scraper import scrape_airtable_csv

def main() -> None:
    """CLI entrypoint to run the Airtable to Databricks ingestion."""
    asyncio.run(scrape_airtable_csv())
