import Scrapper.twscrape.twscrape as twscrape
from Scrapper.twscrape.twscrape import gather

from config import settings
from scrapers.base import BaseScraper


class TweetScraper(BaseScraper):
    def __init__(self, db_path: str | None = None, proxy: str | None = None, ssl_verify: bool = True):
        super().__init__(db_path, proxy, ssl_verify)

    async def scrape_tweet(self, tweet_id: int, include_replies: bool = True, 
                          include_retweeters: bool = False, limit: int = 100) -> dict:
        twscrape.logger.info(f"Scraping tweet ID: {tweet_id}")

        results = {}

        tweet = await self.api.tweet_details(tweet_id)
        if not tweet:
            twscrape.logger.error(f"Tweet not found: {tweet_id}")
            return results

        results["tweet"] = tweet.dict()

        if include_replies:
            output_path = self._get_output_path("tweets", f"replies_{tweet_id}.json")
            replies = await self.gather_and_save(
                self.api.tweet_replies(tweet_id, limit=limit),
                output_path,
                limit=limit
            )
            results["replies"] = replies
            twscrape.logger.info(f"Scraped {len(replies)} replies for tweet {tweet_id}")

        if include_retweeters:
            output_path = self._get_output_path("tweets", f"retweeters_{tweet_id}.json")
            retweeters = await self.gather_and_save(
                self.api.retweeters(tweet_id, limit=limit),
                output_path,
                limit=limit
            )
            results["retweeters"] = retweeters
            twscrape.logger.info(f"Scraped {len(retweeters)} retweeters for tweet {tweet_id}")

        return results

    async def scrape_tweets(self, tweet_ids: list[int], include_replies: bool = True,
                           include_retweeters: bool = False, limit: int = 100) -> dict[int, dict]:
        results = {}
        for tweet_id in tweet_ids:
            try:
                data = await self.scrape_tweet(tweet_id, include_replies, include_retweeters, limit)
                results[tweet_id] = data
            except Exception as e:
                twscrape.logger.error(f"Error scraping tweet {tweet_id}: {type(e).__name__}: {e}")
                results[tweet_id] = {}

        return results

    async def run(self, tweet_ids: list[int] | None = None, include_replies: bool = True,
                 include_retweeters: bool = False, limit: int = 100) -> dict[int, dict]:
        if tweet_ids is None:
            tweet_ids = []

        return await self.scrape_tweets(tweet_ids, include_replies, include_retweeters, limit)
