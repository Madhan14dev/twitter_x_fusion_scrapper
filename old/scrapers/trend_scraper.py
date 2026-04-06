import Scrapper.twscrape.twscrape as twscrape
from Scrapper.twscrape.twscrape import gather

from config import settings
from scrapers.base import BaseScraper


class TrendScraper(BaseScraper):
    def __init__(self, db_path: str | None = None, proxy: str | None = None, ssl_verify: bool = True):
        super().__init__(db_path, proxy, ssl_verify)

    CATEGORIES = ["trending", "news", "sport", "entertainment"]

    async def scrape_category(self, category: str, limit: int = 100) -> list[dict]:
        twscrape.logger.info(f"Scraping trends: {category}")

        output_path = self._get_output_path(
            "trends",
            f"{category}_{self._timestamp()}.json"
        )

        try:
            trends = await self.gather_and_save(
                self.api.trends(category, limit=limit),
                output_path,
                limit=limit
            )
            twscrape.logger.info(f"Scraped {len(trends)} trends for category: {category}")
            return trends
        except Exception as e:
            twscrape.logger.warning(f"Trend API for '{category}' may be unavailable (Twitter changed their API). Error: {e}")
            twscrape.logger.info(f"Skipping category '{category}' due to API issues")
            return []

    async def scrape_all(self, limit: int = 100) -> dict[str, list[dict]]:
        results = {}
        for category in self.CATEGORIES:
            try:
                trends = await self.scrape_category(category, limit)
                results[category] = trends
            except Exception as e:
                twscrape.logger.error(
                    f"Error scraping category '{category}': {type(e).__name__}: {e}"
                )
                results[category] = []

        return results

    async def run(self, categories: list[str] | None = None, limit: int = 100) -> dict[str, list[dict]]:
        if categories is None:
            return await self.scrape_all(limit)

        results = {}
        for category in categories:
            if category not in self.CATEGORIES:
                twscrape.logger.warning(f"Unknown category: {category}, skipping")
                continue

            try:
                trends = await self.scrape_category(category, limit)
                results[category] = trends
            except Exception as e:
                twscrape.logger.error(
                    f"Error scraping category '{category}': {type(e).__name__}: {e}"
                )
                results[category] = []

        return results
