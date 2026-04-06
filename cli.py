"""Pipeline CLI - Redesigned command-line interface."""
import argparse
import asyncio
import logging
import sys
from pathlib import Path
from typing import Optional

# Ensure the twitter directory is in sys.path for imports
_twitter_dir = Path(__file__).parent.resolve()
if str(_twitter_dir) not in sys.path:
    sys.path.insert(0, str(_twitter_dir))
if str(_twitter_dir.parent) not in sys.path:
    sys.path.insert(0, str(_twitter_dir.parent))

from config.settings import settings
from engines import twscrape_engine, twikit_engine
from core import SmartRouter, RateLimiter, ErrorHandler
from output.pipeline import OutputPipeline, ScrapeResult
from datetime import datetime


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)


class PipelineCLI:
    """Main CLI for the scraping pipeline."""
    
    def __init__(self):
        self.router: Optional[SmartRouter] = None
        self.rate_limiter = RateLimiter()
        self.error_handler = ErrorHandler()
        self.output = OutputPipeline(
            settings.output.directory,
            settings.output.db_path
        )
    
    async def initialize(self, engines: list[str] = None):
        """Initialize the pipeline with selected engines."""
        engines = engines or ["twscrape", "twikit"]
        
        engine_instances = {}
        
        if "twscrape" in engines:
            try:
                twscrape = twscrape_engine.TwscrapeEngine(
                    db_path=str(settings.output.db_path.parent / "accounts.db"),
                    config={
                        "proxy": settings.proxy,
                        "ssl_verify": settings.ssl_verify,
                        "circuit_breaker_threshold": settings.twscrape.circuit_breaker_threshold
                    }
                )
                engine_instances["twscrape"] = twscrape
                logger.info("Initialized twscrape engine")
            except Exception as e:
                logger.warning(f"Failed to initialize twscrape: {e}")
        
        if "twikit" in engines:
            try:
                twikit = twikit_engine.TwikitEngine(config={
                    "cookies_path": str(settings.accounts_file.with_suffix(".json")),
                    "circuit_breaker_threshold": settings.twikit.circuit_breaker_threshold
                })
                engine_instances["twikit"] = twikit
                logger.info("Initialized twikit engine")
            except Exception as e:
                # This is expected if twikit isn't available - continue without it
                logger.warning(f"Skipping twikit (not available or no cookies): {e}")
        
        if not engine_instances:
            logger.error("No engines initialized")
            sys.exit(1)
        
        self.router = SmartRouter(
            engine_instances,
            config={
                "circuit_breaker_threshold": 5,
                "circuit_breaker_timeout": 300
            }
        )
    
    async def search(
        self,
        queries: list[str],
        limit: int = 100,
        output: bool = True
    ):
        """Search for tweets."""
        total = 0
        engine_used = "unknown"
        
        for query in queries:
            logger.info(f"Searching: {query}")
            tweets = []
            
            try:
                async for result in self.router.search(query, limit=limit):
                    tweets.append(result.data)
                    engine_used = result.source_engine
                    total += 1
                
                if output and tweets:
                    filename = f"{self._slugify(query)}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                    await self.output.save_tweets(tweets, filename, "search")
                    logger.info(f"Saved {len(tweets)} tweets for '{query}'")
                    
            except Exception as e:
                logger.error(f"Search failed for '{query}': {e}")
                await self.output.log_result(ScrapeResult(
                    operation="search",
                    query=query,
                    count=0,
                    source_engine=engine_used,
                    timestamp=datetime.now(),
                    success=False,
                    error=str(e)
                ))
        
        await self.output.log_result(ScrapeResult(
            operation="search",
            query="all",
            count=total,
            source_engine=engine_used,
            timestamp=datetime.now(),
            success=True
        ))
        
        return total
    
    async def trends(
        self,
        categories: list[str],
        limit: int = 20,
        output: bool = True
    ):
        """Get trends."""
        total = 0
        engine_used = "unknown"
        
        for category in categories:
            logger.info(f"Getting trends: {category}")
            trends = []
            
            try:
                async for result in self.router.trends(category, limit=limit):
                    trends.append(result.data)
                    engine_used = result.source_engine
                    total += 1
                
                if output and trends:
                    filename = f"{category}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                    await self.output.save_trends(trends, filename, "trends")
                    logger.info(f"Saved {len(trends)} trends for '{category}'")
                    
            except Exception as e:
                logger.error(f"Trends failed for '{category}': {e}")
                await self.output.log_result(ScrapeResult(
                    operation="trends",
                    query=category,
                    count=0,
                    source_engine=engine_used,
                    timestamp=datetime.now(),
                    success=False,
                    error=str(e)
                ))
        
        await self.output.log_result(ScrapeResult(
            operation="trends",
            query="all",
            count=total,
            source_engine=engine_used,
            timestamp=datetime.now(),
            success=True
        ))
        
        return total
    
    async def user(
        self,
        username: str,
        tweets: bool = True,
        limit: int = 100,
        output: bool = True
    ):
        """Get user data."""
        logger.info(f"Getting user: {username}")
        
        try:
            user_result = await self.router.user_by_login(username)
            if not user_result:
                logger.error(f"User not found: {username}")
                return 0
            
            user_data = [user_result.data]
            engine_used = user_result.source_engine
            
            if output:
                filename = f"user_{username}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                await self.output.save_users(user_data, filename, "users")
            
            if tweets:
                tweets_list = []
                async for result in self.router.user_tweets(user_result.data.get("id"), limit=limit):
                    tweets_list.append(result.data)
                
                if output and tweets_list:
                    filename = f"user_tweets_{username}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                    await self.output.save_tweets(tweets_list, filename, "users")
            
            await self.output.log_result(ScrapeResult(
                operation="user",
                query=username,
                count=len(user_data),
                source_engine=engine_used,
                timestamp=datetime.now(),
                success=True
            ))
            
            return 1
            
        except Exception as e:
            logger.error(f"User fetch failed: {e}")
            return 0
    
    async def status(self):
        """Show pipeline status."""
        status = await self.router.get_status()
        
        print("\n=== Pipeline Status ===")
        print(f"Engines: {len(status['engines'])}")
        
        for name, info in status["engines"].items():
            status_icon = "✓" if info["available"] and not info["circuit_open"] else "✗"
            print(f"  {status_icon} {name}: available={info['available']}, failures={info['failure_count']}")
        
        print("\nRoutes:")
        for op, engines in status["routes"].items():
            print(f"  {op}: {' → '.join(engines)}")
        
        stats = await self.output.get_stats()
        print(f"\nStats:")
        print(f"  Tweets: {stats['tweets']['total']} ({stats['tweets']['unique']} unique)")
        print(f"  Users: {stats['users']['total']} ({stats['users']['unique']} unique)")
        print(f"  Trends: {stats['trends']['total']}")
        print(f"  Results: {stats['results']['success']} success, {stats['results']['failed']} failed")
    
    async def close(self):
        """Clean up resources."""
        if self.router:
            await self.router.close_all()
    
    @staticmethod
    def _slugify(text: str) -> str:
        """Convert text to filename-friendly slug."""
        import re
        text = text.lower()
        text = re.sub(r'[^\w\s-]', '', text)
        text = re.sub(r'[-\s]+', '_', text)
        return text[:50]


async def main():
    parser = argparse.ArgumentParser(
        description="Twitter Scraping Pipeline CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument("--engines", nargs="+", default=["twscrape", "twikit"],
                        help="Engines to use (twscrape twikit)")
    parser.add_argument("--log-level", default="INFO",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                        help="Logging level")
    
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Search command
    search_parser = subparsers.add_parser("search", help="Search tweets")
    search_parser.add_argument("queries", nargs="+", help="Search queries")
    search_parser.add_argument("--limit", type=int, default=100, help="Tweet limit per query")
    search_parser.add_argument("--no-output", action="store_true", help="Don't save to file")
    
    # Trends command
    trends_parser = subparsers.add_parser("trends", help="Get trends")
    trends_parser.add_argument("--categories", nargs="+",
                               default=["trending", "news", "sport", "entertainment"],
                               help="Trend categories")
    trends_parser.add_argument("--limit", type=int, default=20, help="Trend limit per category")
    trends_parser.add_argument("--no-output", action="store_true", help="Don't save to file")
    
    # User command
    user_parser = subparsers.add_parser("user", help="Get user data")
    user_parser.add_argument("username", help="Username to fetch")
    user_parser.add_argument("--tweets", action="store_true", help="Also fetch user tweets")
    user_parser.add_argument("--limit", type=int, default=100, help="Tweet limit")
    user_parser.add_argument("--no-output", action="store_true", help="Don't save to file")
    
    # Status command
    subparsers.add_parser("status", help="Show pipeline status")
    
    args = parser.parse_args()
    
    # Set log level
    logging.getLogger().setLevel(getattr(logging, args.log_level))
    
    # Initialize CLI
    cli = PipelineCLI()
    await cli.initialize(args.engines)
    
    try:
        if args.command == "search":
            count = await cli.search(
                args.queries,
                limit=args.limit,
                output=not args.no_output
            )
            print(f"\nTotal tweets: {count}")
            
        elif args.command == "trends":
            count = await cli.trends(
                args.categories,
                limit=args.limit,
                output=not args.no_output
            )
            print(f"\nTotal trends: {count}")
            
        elif args.command == "user":
            count = await cli.user(
                args.username,
                tweets=args.tweets,
                limit=args.limit,
                output=not args.no_output
            )
            print(f"\nUser fetched: {count}")
            
        elif args.command == "status":
            await cli.status()
            
        else:
            parser.print_help()
            
    finally:
        await cli.close()


if __name__ == "__main__":
    asyncio.run(main())