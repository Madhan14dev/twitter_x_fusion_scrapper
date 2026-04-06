import json
from pathlib import Path
from typing import Any

import Scrapper.twscrape.twscrape as twscrape

from config import settings
from scrapers.base import BaseScraper


class SearchScraper(BaseScraper):
    def __init__(self, db_path: str | None = None, proxy: str | None = None, ssl_verify: bool = True):
        super().__init__(db_path, proxy, ssl_verify)

    async def scrape_query(self, query: str, limit: int = 100, tab: str = "Latest") -> list[dict]:
        twscrape.logger.info(f"Scraping query: {query} (limit={limit}, tab={tab})")

        kv = {"product": tab} if tab != "Latest" else None
        output_path = self._get_output_path(
            "search",
            f"{self._slugify(query)}_{self._timestamp()}.json"
        )

        tweets = await self.gather_and_save(
            self.api.search(query, limit=limit, kv=kv),
            output_path,
            limit=limit
        )

        twscrape.logger.info(f"Scraped {len(tweets)} tweets for query: {query}")
        return tweets

    async def run(self, queries: list[dict] | None = None) -> dict[str, list[dict]]:
        if queries is None:
            queries = self._load_queries()

        results = {}
        for q in queries:
            query = q.get("query")
            limit = q.get("limit", settings.DEFAULT_LIMIT)
            tab = q.get("tab", "Latest")

            try:
                tweets = await self.scrape_query(query, limit, tab)
                results[query] = tweets
            except Exception as e:
                twscrape.logger.error(f"Error scraping query '{query}': {type(e).__name__}: {e}")
                results[query] = []

        return results

    def _load_queries(self) -> list[dict]:
        if settings.QUERIES_FILE.exists():
            with open(settings.QUERIES_FILE, encoding="utf-8") as f:
                data = json.load(f)
                return data.get("queries", [])
        return []
