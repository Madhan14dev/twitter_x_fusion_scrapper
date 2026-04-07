"""twikit engine adapter."""
import logging
from typing import Any, AsyncGenerator, TYPE_CHECKING
from datetime import datetime

try:
    from twikit import Client
    from twikit.errors import (
        TooManyRequests,
        ServerError,
        TwitterException
    )
    TWIKIT_AVAILABLE = True
except ImportError as e:
    TWIKIT_AVAILABLE = False
    Client = None  # type: ignore
    TooManyRequests = None  # type: ignore
    AccountSuspended = None  # type: ignore
    ServerError = None  # type: ignore
    TwitterException = None  # type: ignore

from engines.base import BaseEngine, EngineResult, EngineError


logger = logging.getLogger(__name__)


class TwikitEngine(BaseEngine):
    """twikit engine adapter providing extended operations."""
    
    name = "twikit"
    
    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        
        if not TWIKIT_AVAILABLE:
            raise ImportError("twikit is not installed. Install with: pip install twikit")
        
        self._client: Client | None = None
        self._cookies_loaded = False
        self._cookies_path = config.get("cookies_path") if config else None
    
    @property
    def client(self) -> Client:
        """Get or create twikit client."""
        if self._client is None:
            self._client = Client(language='en-US')
        return self._client
    
    async def _ensure_cookies(self):
        """Ensure cookies are loaded."""
        if not self._cookies_loaded and self._cookies_path:
            try:
                cookies_path_str = self._cookies_path
                import json
                with open(cookies_path_str, 'r', encoding='utf-8') as f:
                    raw = json.load(f)

                # Handle accounts wrapper format: {"accounts": [{..., "cookies": {...}}, ...]}
                if isinstance(raw, dict) and "accounts" in raw:
                    accounts = raw["accounts"]
                    cookies = None
                    for acc in accounts:
                        if acc.get("cookies") and isinstance(acc["cookies"], dict):
                            cookies = acc["cookies"]
                            break
                    if not cookies or (not cookies.get("ct0") and not cookies.get("auth_token")):
                        logger.warning(
                            "No valid Twitter cookies found in %s. "
                            "Log in with 'python cli.py login <username>' first.",
                            cookies_path_str,
                        )
                        return
                elif isinstance(raw, dict) and raw.get("ct0"):
                    cookies = raw
                else:
                    logger.warning(
                        "Cookies file %s contains invalid format (expected {ct0, auth_token})",
                        cookies_path_str,
                    )
                    return

                self.client.load_cookies(cookies_path_str) if isinstance(raw, dict) and raw.get("ct0") else self.client.set_cookies(cookies)
                self._cookies_loaded = True
                logger.info("Loaded cookies from %s", cookies_path_str)
            except Exception as e:
                logger.warning("Failed to load cookies: %s", e)
    
    async def search(
        self,
        query: str,
        limit: int = 100,
        **kwargs
    ) -> AsyncGenerator[EngineResult[dict], None]:
        """Search for tweets using twikit."""
        try:
            await self._ensure_cookies()
            
            product = kwargs.get("product", "Latest")
            count = min(limit, 100)
            
            cursor = None
            fetched = 0
            
            while fetched < limit:
                tweets = await self.client.search_tweet(
                    query, 
                    product=product,
                    count=count,
                    cursor=cursor
                )
                
                if not tweets:
                    break
                
                for tweet in tweets:
                    yield EngineResult(
                        data=tweet._to_dict() if hasattr(tweet, '_to_dict') else vars(tweet),
                        source_engine=self.name,
                        metadata={"query": query, "limit": limit}
                    )
                    fetched += 1
                    if fetched >= limit:
                        break
                
                # Get cursor for next page - twikit returns a Result object
                if hasattr(tweets, 'next_cursor'):
                    cursor = tweets.next_cursor
                else:
                    break
                    
        except Exception as e:
            raise EngineError(
                engine=self.name,
                operation="search",
                error_type=type(e).__name__,
                message=str(e),
                is_transient=self._is_transient_error(e)
            )
    
    async def user_tweets(
        self,
        user_id: str | int,
        limit: int = 100,
        **kwargs
    ) -> AsyncGenerator[EngineResult[dict], None]:
        """Get user tweets."""
        try:
            await self._ensure_cookies()
            
            tweet_type = kwargs.get("tweet_type", "Tweets")
            count = min(limit, 100)
            
            cursor = None
            fetched = 0
            
            while fetched < limit:
                tweets = await self.client.get_user_tweets(
                    user_id,
                    tweet_type=tweet_type,
                    count=count,
                    cursor=cursor
                )
                
                if not tweets:
                    break
                
                for tweet in tweets:
                    yield EngineResult(
                        data=tweet._to_dict() if hasattr(tweet, '_to_dict') else vars(tweet),
                        source_engine=self.name,
                        metadata={"user_id": str(user_id), "limit": limit}
                    )
                    fetched += 1
                    if fetched >= limit:
                        break
                
                if hasattr(tweets, 'next_cursor'):
                    cursor = tweets.next_cursor
                else:
                    break
                    
        except Exception as e:
            raise EngineError(
                engine=self.name,
                operation="user_tweets",
                error_type=type(e).__name__,
                message=str(e),
                is_transient=self._is_transient_error(e)
            )
    
    async def user_by_login(
        self,
        username: str,
        **kwargs
    ) -> EngineResult[dict] | None:
        """Get user by username."""
        try:
            await self._ensure_cookies()
            
            user = await self.client.get_user_by_screen_name(username)
            if not user:
                return None
            
            return EngineResult(
                data=user._to_dict() if hasattr(user, '_to_dict') else vars(user),
                source_engine=self.name,
                metadata={"username": username}
            )
        except Exception as e:
            raise EngineError(
                engine=self.name,
                operation="user_by_login",
                error_type=type(e).__name__,
                message=str(e),
                is_transient=self._is_transient_error(e)
            )
    
    async def user_by_id(
        self,
        user_id: str | int,
        **kwargs
    ) -> EngineResult[dict] | None:
        """Get user by numeric ID."""
        try:
            await self._ensure_cookies()
            
            user = await self.client.get_user_by_id(user_id)
            if not user:
                return None
            
            return EngineResult(
                data=user._to_dict() if hasattr(user, '_to_dict') else vars(user),
                source_engine=self.name,
                metadata={"user_id": str(user_id)}
            )
        except Exception as e:
            raise EngineError(
                engine=self.name,
                operation="user_by_id",
                error_type=type(e).__name__,
                message=str(e),
                is_transient=self._is_transient_error(e)
            )
    
    async def tweet_details(
        self,
        tweet_id: int,
        **kwargs
    ) -> EngineResult[dict] | None:
        """Get tweet details."""
        try:
            await self._ensure_cookies()
            
            tweet = await self.client.get_tweet_by_id(tweet_id)
            if not tweet:
                return None
            
            return EngineResult(
                data=tweet._to_dict() if hasattr(tweet, '_to_dict') else vars(tweet),
                source_engine=self.name,
                metadata={"tweet_id": str(tweet_id)}
            )
        except Exception as e:
            raise EngineError(
                engine=self.name,
                operation="tweet_details",
                error_type=type(e).__name__,
                message=str(e),
                is_transient=self._is_transient_error(e)
            )
    
    async def trends(
        self,
        category: str = "trending",
        limit: int = 100,
        **kwargs
    ) -> AsyncGenerator[EngineResult[dict], None]:
        """Get trends by category - this is twikit's strength."""
        try:
            await self._ensure_cookies()
            
            count = min(limit, 20)
            
            # Map category names
            category_map = {
                "trending": "trending",
                "news": "news",
                "sport": "sports",
                "entertainment": "entertainment",
                "for-you": "for-you",
            }
            twikit_category = category_map.get(category, "trending")
            
            trends = await self.client.get_trends(
                twikit_category,
                count=count,
                retry=True,
                additional_request_params=kwargs.get("extra_params")
            )
            
            if not trends:
                return
            
            for trend in trends:
                yield EngineResult(
                    data={
                        "name": trend.name,
                        "tweets_count": trend.tweets_count,
                        "domain_context": trend.domain_context,
                        "url": trend.url if hasattr(trend, 'url') else None,
                        "query": trend.query if hasattr(trend, 'query') else None,
                    },
                    source_engine=self.name,
                    metadata={"category": category, "limit": limit}
                )
                    
        except Exception as e:
            raise EngineError(
                engine=self.name,
                operation="trends",
                error_type=type(e).__name__,
                message=str(e),
                is_transient=self._is_transient_error(e)
            )
    
    async def followers(
        self,
        user_id: str | int,
        limit: int = 100,
        **kwargs
    ) -> AsyncGenerator[EngineResult[dict], None]:
        """Get followers of a user."""
        try:
            await self._ensure_cookies()
            
            count = min(limit, 100)
            cursor = None
            fetched = 0
            
            while fetched < limit:
                users = await self.client.get_user_followers(
                    user_id,
                    count=count,
                    cursor=cursor
                )
                
                if not users:
                    break
                
                for user in users:
                    yield EngineResult(
                        data=user._to_dict() if hasattr(user, '_to_dict') else vars(user),
                        source_engine=self.name,
                        metadata={"user_id": str(user_id), "limit": limit}
                    )
                    fetched += 1
                    if fetched >= limit:
                        break
                
                if hasattr(users, 'next_cursor'):
                    cursor = users.next_cursor
                else:
                    break
                    
        except Exception as e:
            raise EngineError(
                engine=self.name,
                operation="followers",
                error_type=type(e).__name__,
                message=str(e),
                is_transient=self._is_transient_error(e)
            )
    
    async def following(
        self,
        user_id: str | int,
        limit: int = 100,
        **kwargs
    ) -> AsyncGenerator[EngineResult[dict], None]:
        """Get following of a user."""
        try:
            await self._ensure_cookies()
            
            count = min(limit, 100)
            cursor = None
            fetched = 0
            
            while fetched < limit:
                users = await self.client.get_user_following(
                    user_id,
                    count=count,
                    cursor=cursor
                )
                
                if not users:
                    break
                
                for user in users:
                    yield EngineResult(
                        data=user._to_dict() if hasattr(user, '_to_dict') else vars(user),
                        source_engine=self.name,
                        metadata={"user_id": str(user_id), "limit": limit}
                    )
                    fetched += 1
                    if fetched >= limit:
                        break
                
                if hasattr(users, 'next_cursor'):
                    cursor = users.next_cursor
                else:
                    break
                    
        except Exception as e:
            raise EngineError(
                engine=self.name,
                operation="following",
                error_type=type(e).__name__,
                message=str(e),
                is_transient=self._is_transient_error(e)
            )
    
    async def login(
        self,
        username: str,
        password: str,
        email: str | None = None,
        totp_secret: str | None = None,
        cookies_file: str | None = None
    ) -> dict:
        """Login to Twitter and save cookies to a JSON file.

        Uses ``twikit.Client.login`` which persists cookies when
        ``cookies_file`` is given (no separate save step needed).
        """
        try:
            cookies_file = cookies_file or self._cookies_path or "./config/cookies.json"
            await self.client.login(
                auth_info_1=username,
                password=password,
                auth_info_2=email,
                totp_secret=totp_secret,
                cookies_file=cookies_file,
            )
            self._cookies_path = cookies_file
            self._cookies_loaded = True
            logger.info("twikit: logged in as %s, cookies saved to %s", username, cookies_file)
            return {"success": True, "cookies_file": cookies_file}
        except Exception as e:
            logger.warning("twikit login failed for %s: %s", username, e)
            return {"success": False, "error": str(e)}

    async def close(self):
        """Clean up resources."""
        pass

    async def health_check(self) -> bool:
        """Check if engine is healthy."""
        try:
            await self._ensure_cookies()
            user = await self.client.user()
            return user is not None
        except Exception as e:
            logger.warning(f"twikit health check failed: {e}")
            return False
    
    def _is_transient_error(self, error: Exception) -> bool:
        """Determine if error is transient."""
        if isinstance(error, TooManyRequests):
            return True
        error_str = str(error).lower()
        return "timeout" in error_str or "connection" in error_str or "rate" in error_str