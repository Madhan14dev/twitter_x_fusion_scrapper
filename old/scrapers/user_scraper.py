import Scrapper.twscrape.twscrape as twscrape
from Scrapper.twscrape.twscrape import gather

from config import settings
from scrapers.base import BaseScraper


class UserScraper(BaseScraper):
    def __init__(self, db_path: str | None = None, proxy: str | None = None, ssl_verify: bool = True):
        super().__init__(db_path, proxy, ssl_verify)

    async def scrape_user(self, username: str, scrape_types: list[str], limit: int = 50) -> dict:
        twscrape.logger.info(f"Scraping user: {username} (types={scrape_types}, limit={limit})")

        results = {}

        user = await self.api.user_by_login(username)
        if not user:
            twscrape.logger.error(f"User not found: {username}")
            return results

        user_id = user.id
        results["profile"] = user.dict()

        if "tweets" in scrape_types:
            output_path = self._get_output_path("users", f"tweets_{username}.json")
            tweets = await self.gather_and_save(
                self.api.user_tweets(user_id, limit=limit),
                output_path,
                limit=limit
            )
            results["tweets"] = tweets
            twscrape.logger.info(f"Scraped {len(tweets)} tweets for {username}")

        if "replies" in scrape_types or "tweets_and_replies" in scrape_types:
            output_path = self._get_output_path("users", f"replies_{username}.json")
            tweets = await self.gather_and_save(
                self.api.user_tweets_and_replies(user_id, limit=limit),
                output_path,
                limit=limit
            )
            results["replies"] = tweets
            twscrape.logger.info(f"Scraped {len(tweets)} replies for {username}")

        if "media" in scrape_types:
            output_path = self._get_output_path("users", f"media_{username}.json")
            media = await self.gather_and_save(
                self.api.user_media(user_id, limit=limit),
                output_path,
                limit=limit
            )
            results["media"] = media
            twscrape.logger.info(f"Scraped {len(media)} media tweets for {username}")

        if "followers" in scrape_types:
            output_path = self._get_output_path("users", f"followers_{username}.json")
            followers = await self.gather_and_save(
                self.api.followers(user_id, limit=limit),
                output_path,
                limit=limit
            )
            results["followers"] = followers
            twscrape.logger.info(f"Scraped {len(followers)} followers for {username}")

        if "following" in scrape_types:
            output_path = self._get_output_path("users", f"following_{username}.json")
            following = await self.gather_and_save(
                self.api.following(user_id, limit=limit),
                output_path,
                limit=limit
            )
            results["following"] = following
            twscrape.logger.info(f"Scraped {len(following)} following for {username}")

        return results

    async def run(self, targets: list[dict] | None = None) -> dict[str, dict]:
        if targets is None:
            targets = self._load_targets()

        results = {}
        for target in targets:
            username = target.get("username")
            scrape_types = target.get("scrape", ["profile"])
            limit = target.get("limit", settings.DEFAULT_LIMIT)

            try:
                data = await self.scrape_user(username, scrape_types, limit)
                results[username] = data
            except Exception as e:
                twscrape.logger.error(f"Error scraping user '{username}': {type(e).__name__}: {e}")
                results[username] = {}

        return results

    def _load_targets(self) -> list[dict]:
        import json
        if settings.TARGETS_FILE.exists():
            with open(settings.TARGETS_FILE, encoding="utf-8") as f:
                data = json.load(f)
                return data.get("users", [])
        return []
