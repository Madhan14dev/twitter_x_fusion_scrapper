
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


# ---------------------------------------------------------------------------
# Login helpers
# ---------------------------------------------------------------------------

def _prompt_password(prompt_text: str = "Password: ") -> str:
    try:
        import getpass
        return getpass.getpass(prompt_text)
    except (EOFError, Exception):
        return input(prompt_text)


def _prompt_text(prompt_text: str) -> str:
    try:
        return input(prompt_text).strip()
    except EOFError:
        return ""


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

    async def login(
        self,
        username: str,
        password: str | None = None,
        email: str | None = None,
        mfa_code: str | None = None,
        engines: list[str] | None = None,
    ):
        """Interactive / semi-interactive login for one or both scraping engines.

        This is the entry point intended for freshly-created scraper accounts
        (no 2FA / TOTP).

        Flow
        ----
        1. If *password* or *email* was not supplied on the CLI the user is
           prompted interactively (masked for the password).
        2. The twscrape engine attempts login first (``AccountsPool`` flow).
           If the engine requires an email verification code the CLI will prompt
           for it and retry.
        3. The twikit engine (when requested) then attempts login and saves its
           own per-account cookie file.
        """

        engines = engines or ["twscrape"]
        username = username.strip()

        # --- collect missing credentials interactively -----------------------
        if not password:
            print(f"[login] Enter password for  {username}")
            password = _prompt_password()

        if not email:
            email = _prompt_text("Email address : ")

        # --- run engine-specific logins --------------------------------------
        for eng in engines:
            eng = eng.lower()
            print(f"\n--- Logging in via {eng} ---")

            if eng == "twscrape":
                engine = twscrape_engine.TwscrapeEngine(
                    db_path=str(settings.output.db_path.parent / "accounts.db"),
                    config={
                        "proxy": settings.proxy,
                        "ssl_verify": settings.ssl_verify,
                    },
                )
                await self._do_twscrape_login(engine, username, password, email, mfa_code)

            elif eng == "twikit":
                engine = twikit_engine.TwikitEngine(config={
                    "circuit_breaker_threshold": settings.twikit.circuit_breaker_threshold,
                })
                await self._do_twikit_login(engine, username, password, email, mfa_code)
            else:
                logger.warning("Unknown engine %s — skipping.", eng)

    # -- internal login helpers ----------------------------------------------

    async def _do_twscrape_login(self, engine, username, password, email, mfa_code):
        """Execute twscrape login.

        The twscrape library itself prompts for email verification codes
        when ``LoginConfig(manual=True)`` is used, so no extra handling is
        needed here.  It prints::

            Enter email code for <user> / <email>
            Code:

        and blocks until the user types the code.
        """
        result = await engine.login(
            username=username,
            password=password,
            email=email,
            mfa_code=mfa_code,
        )
        if result.get("success"):
            print(f"  twscrape login succeeded for {username}")
        else:
            print(f"  twscrape login failed: {result.get('error', 'unknown')}")

    async def _do_twikit_login(self, engine, username, password, email, mfa_code):
        """Execute twikit login."""
        cookies_file = str(
            settings.output.db_path.parent / f"cookies_{username}.json"
        )
        result = await engine.login(
            username=username,
            password=password,
            email=email,
            totp_secret=mfa_code,
            cookies_file=cookies_file,
        )
        if result.get("success"):
            print(f"  twikit login succeeded for {username} (cookies: {cookies_file})")
        else:
            print(f"  twikit login failed: {result.get('error', 'unknown')}")
    
    async def _resolve_twikit_cookies(self) -> str | None:
        """Find the best twikit cookies file to use.

        Priority:
        1. Most recent ``output/cookies_*.json`` (created by ``cli.py login``)
        2. ``config/accounts.json`` if it contains actual cookie data
        3. None (twikit will warn and operations will fail)
        """

        # 1. Search for per-account cookie files produced by login
        output_dir = settings.output.directory
        cookie_files = list(output_dir.glob("cookies_*.json"))
        if cookie_files:
            # Pick the most recently modified one
            latest = max(cookie_files, key=lambda p: p.stat().st_mtime)
            logger.info("Found twikit cookie files: %s, using latest: %s",
                        len(cookie_files), latest.name)
            return str(latest)

        # 2. Check if config/accounts.json has real cookies
        acct_file = settings.accounts_file
        if acct_file.exists():
            import json
            try:
                with open(acct_file) as f:
                    raw = json.load(f)
                if isinstance(raw, dict):
                    # Direct cookie format
                    if raw.get("ct0") or raw.get("auth_token"):
                        return str(acct_file)
                    # Wrapper format
                    accounts = raw.get("accounts", [])
                    for acc in accounts:
                        cookies = acc.get("cookies")
                        if cookies and isinstance(cookies, dict) and cookies.get("ct0"):
                            # Found valid cookies – but twikit needs plain dict,
                            # and load_cookies reads the raw file. Need to write
                            # a temporary cookie file or use set_cookies.
                            # For now, create a temporary per-account cookie file.
                            temp_file = output_dir / "cookies_auto.json"
                            with open(temp_file, "w") as fw:
                                json.dump(cookies, fw)
                            logger.info("Extracted cookies from %s to %s", acct_file.name, temp_file.name)
                            return str(temp_file)
            except Exception as e:
                logger.debug("Could not parse %s: %s", acct_file, e)

        return None

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
                cookies_path = await self._resolve_twikit_cookies()
                kw_config = {
                    "circuit_breaker_threshold": settings.twikit.circuit_breaker_threshold
                }
                if cookies_path:
                    kw_config["cookies_path"] = cookies_path

                twikit = twikit_engine.TwikitEngine(config=kw_config)
                engine_instances["twikit"] = twikit
                logger.info("Initialized twikit engine (cookies: %s)", cookies_path or "none")
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

    # Login command
    login_parser = subparsers.add_parser("login", help="Log in a Twitter account")
    login_parser.add_argument("username", help="Twitter username")
    login_parser.add_argument("--password", help="Password (will prompt if omitted)")
    login_parser.add_argument("--email", help="Email address (will prompt if omitted)")
    login_parser.add_argument("--mfa", help="MFA / verification code (optional)")
    login_parser.add_argument("--engines", nargs="+", default=["twscrape", "twikit"],
                              help="Engines to authenticate with")

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
        if args.command == "login":
            await cli.login(
                username=args.username,
                password=args.password,
                email=args.email,
                mfa_code=args.mfa,
                engines=args.engines,
            )

        elif args.command == "search":
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