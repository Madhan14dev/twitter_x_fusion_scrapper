import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.resolve()))

from loguru import logger

from config import settings
from scrapers.search_scraper import SearchScraper
from scrapers.user_scraper import UserScraper
from scrapers.tweet_scraper import TweetScraper
from scrapers.trend_scraper import TrendScraper
from Scrapper.twscrape.twscrape import set_log_level


def setup_logging():
    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        level=settings.LOG_LEVEL,
    )
    set_log_level(settings.LOG_LEVEL)


async def run_search(scraper: SearchScraper) -> dict:
    logger.info("Running search scraper...")
    start = time.time()
    results = await scraper.run()
    elapsed = time.time() - start
    logger.info(f"Search scraper completed in {elapsed:.2f}s")
    return results


async def run_user(scraper: UserScraper) -> dict:
    logger.info("Running user scraper...")
    start = time.time()
    results = await scraper.run()
    elapsed = time.time() - start
    logger.info(f"User scraper completed in {elapsed:.2f}s")
    return results


async def run_tweet(scraper: TweetScraper, tweet_ids: list[int]) -> dict:
    logger.info("Running tweet scraper...")
    start = time.time()
    results = await scraper.run(tweet_ids=tweet_ids)
    elapsed = time.time() - start
    logger.info(f"Tweet scraper completed in {elapsed:.2f}s")
    return results


async def run_trend(scraper: TrendScraper, categories: list[str] | None) -> dict:
    logger.info("Running trend scraper...")
    start = time.time()
    results = await scraper.run(categories=categories)
    elapsed = time.time() - start
    logger.info(f"Trend scraper completed in {elapsed:.2f}s")
    return results


async def run_all(scrapers: dict) -> dict:
    all_results = {}
    for name, (scraper, func, kwargs) in scrapers.items():
        try:
            result = await func(scraper, **kwargs)
            all_results[name] = result
        except Exception as e:
            logger.error(f"Error in {name}: {type(e).__name__}: {e}")
            all_results[name] = {}
    return all_results


def print_summary(results: dict, scrapers: dict) -> None:
    logger.info("=" * 60)
    logger.info("SCRAPING SUMMARY")
    logger.info("=" * 60)

    total_items = 0

    if "search" in results:
        search_results = results["search"]
        count = sum(len(v) for v in search_results.values()) if search_results else 0
        logger.info(f"Search tweets: {count}")
        total_items += count

    if "user" in results:
        user_results = results["user"]
        users_count = len(user_results)
        tweets_count = sum(len(v.get("tweets", [])) for v in user_results.values())
        logger.info(f"Users scraped: {users_count}, Tweets: {tweets_count}")
        total_items += tweets_count

    if "tweet" in results:
        tweet_results = results["tweet"]
        count = sum(len(v.get("tweet", [])) if isinstance(v.get("tweet"), list) else 1 
                   for v in tweet_results.values())
        logger.info(f"Tweet details: {count}")
        total_items += count

    if "trend" in results:
        trend_results = results["trend"]
        count = sum(len(v) for v in trend_results.values()) if trend_results else 0
        logger.info(f"Trends: {count}")
        total_items += count

    logger.info(f"Total items scraped: {total_items}")
    logger.info("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Twitter Scraper - Main Orchestrator")
    parser.add_argument("--task", action="append", dest="tasks", 
                       help="Tasks to run: search, user, tweet, trend. If omitted, runs all.")
    parser.add_argument("--tweet-ids", nargs="*", type=int, default=[],
                       help="Tweet IDs to scrape (for tweet task)")
    parser.add_argument("--trend-categories", nargs="*",
                       choices=["trending", "news", "sport", "entertainment"],
                       help="Trend categories to scrape")
    parser.add_argument("--output-dir", type=Path, default=settings.OUTPUT_DIR,
                       help="Output directory")
    parser.add_argument("--db", type=Path, default=settings.DB_PATH,
                       help="Accounts database path")
    parser.add_argument("--log-level", default=settings.LOG_LEVEL,
                       choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                       help="Logging level")
    parser.add_argument("--queries-file", type=Path, default=settings.QUERIES_FILE,
                       help="Queries JSON file")
    parser.add_argument("--targets-file", type=Path, default=settings.TARGETS_FILE,
                        help="Targets JSON file")
    parser.add_argument("--proxy", type=str, default=settings.PROXY,
                        help="Proxy URL (e.g., http://127.0.0.1:8080)")
    parser.add_argument("--no-ssl-verify", action="store_true",
                        help="Disable SSL verification (useful for corporate proxies)")

    args = parser.parse_args()

    settings.LOG_LEVEL = args.log_level
    settings.OUTPUT_DIR = args.output_dir
    settings.DB_PATH = args.db
    settings.QUERIES_FILE = args.queries_file
    settings.TARGETS_FILE = args.targets_file
    proxy = args.proxy
    ssl_verify = not args.no_ssl_verify

    if proxy:
        logger.info(f"Using proxy: {proxy}")
    if not ssl_verify:
        logger.warning("SSL verification disabled!")

    setup_logging()

    valid_tasks = {"search", "user", "tweet", "trend"}
    tasks = args.tasks if args.tasks else list(valid_tasks)

    for task in tasks:
        if task not in valid_tasks:
            logger.error(f"Invalid task: {task}")
            return

    logger.info(f"Starting scraper with tasks: {tasks}")

    scrapers_dict = {}
    scrapers_info = {}

    if "search" in tasks:
        search_scraper = SearchScraper(db_path=str(args.db), proxy=proxy, ssl_verify=ssl_verify)
        scrapers_dict["search"] = search_scraper
        scrapers_info["search"] = (search_scraper, run_search, {})

    if "user" in tasks:
        user_scraper = UserScraper(db_path=str(args.db), proxy=proxy, ssl_verify=ssl_verify)
        scrapers_dict["user"] = user_scraper
        scrapers_info["user"] = (user_scraper, run_user, {})

    if "tweet" in tasks:
        tweet_scraper = TweetScraper(db_path=str(args.db), proxy=proxy, ssl_verify=ssl_verify)
        scrapers_dict["tweet"] = tweet_scraper
        scrapers_info["tweet"] = (tweet_scraper, run_tweet, {"tweet_ids": args.tweet_ids})

    if "trend" in tasks:
        trend_scraper = TrendScraper(db_path=str(args.db), proxy=proxy, ssl_verify=ssl_verify)
        scrapers_dict["trend"] = trend_scraper
        scrapers_info["trend"] = (trend_scraper, run_trend, {"categories": args.trend_categories})

    results = asyncio.run(run_all(scrapers_info))

    print_summary(results, scrapers_info)

    for name, scraper in scrapers_dict.items():
        scraper.print_stats()


if __name__ == "__main__":
    main()
