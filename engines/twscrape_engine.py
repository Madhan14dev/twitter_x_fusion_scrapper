"""twscrape engine adapter."""
import asyncio
import logging
from typing import Any, AsyncGenerator
from datetime import datetime
from pathlib import Path

import twscrape
from twscrape import API, AccountsPool
from twscrape.login import login as twscrape_login, LoginConfig
from engines.base import BaseEngine, EngineResult, EngineError


logger = logging.getLogger(__name__)


class TwscrapeEngine(BaseEngine):
    """twscrape engine adapter providing unified interface."""

    name = "twscrape"

    def __init__(self, db_path: str, config: dict[str, Any] | None = None):
        super().__init__(config)
        self.db_path = db_path
        self.api: API | None = None
        self._proxy = config.get("proxy") if config else None
        self._ssl = config.get("ssl_verify", True)

    @property
    def pool(self) -> AccountsPool:
        """Get AccountsPool for direct account operations."""
        return AccountsPool(db_file=self.db_path)

    async def _ensure_api(self):
        """Lazy initialization of API."""
        if self.api is None:
            kwargs = {"debug": self.config.get("debug", False)}
            if self._proxy:
                kwargs["proxy"] = self._proxy
            self.api = API(**kwargs)
    
    async def search(
        self,
        query: str,
        limit: int = 100,
        **kwargs
    ) -> AsyncGenerator[EngineResult[dict], None]:
        """Search for tweets using twscrape."""
        try:
            await self._ensure_api()
            tab = kwargs.get("tab", "Latest")
            kv = {"product": tab} if tab != "Latest" else None
            
            async for tweet in self.api.search(query, limit=limit, kv=kv):
                yield EngineResult(
                    data=tweet.dict(),
                    source_engine=self.name,
                    metadata={"query": query, "limit": limit}
                )
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
            await self._ensure_api()
            
            # First get user to verify existence
            user = await self.api.user_by_id(user_id)
            if not user:
                raise EngineError(
                    engine=self.name,
                    operation="user_tweets",
                    error_type="NotFound",
                    message=f"User {user_id} not found",
                    is_transient=False
                )
            
            async for tweet in self.api.user_tweets(user_id, limit=limit):
                yield EngineResult(
                    data=tweet.dict(),
                    source_engine=self.name,
                    metadata={"user_id": str(user_id), "limit": limit}
                )
        except EngineError:
            raise
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
            await self._ensure_api()
            user = await self.api.user_by_login(username)
            if not user:
                return None
            
            return EngineResult(
                data=user.dict(),
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
            await self._ensure_api()
            user = await self.api.user_by_id(user_id)
            if not user:
                return None
            
            return EngineResult(
                data=user.dict(),
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
            await self._ensure_api()
            tweet = await self.api.tweet_details(tweet_id)
            if not tweet:
                return None
            
            return EngineResult(
                data=tweet.dict(),
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
        """Get trends by category."""
        # twscrape trends are currently broken due to Twitter API changes
        # Return empty generator - router will try next engine
        return
        
        # This makes the function an async generator
        yield  # type: ignore
    
    async def followers(
        self,
        user_id: str | int,
        limit: int = 100,
        **kwargs
    ) -> AsyncGenerator[EngineResult[dict], None]:
        """Get followers of a user."""
        try:
            await self._ensure_api()
            
            user_id = int(user_id)
            async for user in self.api.followers(user_id, limit=limit):
                yield EngineResult(
                    data=user.dict(),
                    source_engine=self.name,
                    metadata={"user_id": str(user_id), "limit": limit}
                )
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
            await self._ensure_api()
            
            user_id = int(user_id)
            async for user in self.api.following(user_id, limit=limit):
                yield EngineResult(
                    data=user.dict(),
                    source_engine=self.name,
                    metadata={"user_id": str(user_id), "limit": limit}
                )
        except Exception as e:
            raise EngineError(
                engine=self.name,
                operation="following",
                error_type=type(e).__name__,
                message=str(e),
                is_transient=self._is_transient_error(e)
            )
    
    async def close(self):
        """Clean up resources."""
        # twscrape doesn't require explicit cleanup
        pass
    
    async def login(
        self,
        username: str,
        password: str,
        email: str,
        email_password: str = "",
        user_agent: str | None = None,
        proxy: str | None = None,
        mfa_code: str | None = None,
        cookies: str | None = None,
    ) -> dict:
        """Add account to pool and perform interactive login.

        Uses twscrape's AccountsPool.add_account() + AccountsPool.login() which
        handles the full Twitter auth flow (username -> password -> email check -> 2FA).
        Sessions are automatically persisted to the accounts.db file.
        """
        pool = self.pool

        # Add (or update) account in the pool.  We use a placeholder active=False
        # so twscrape.login() will run the full credential exchange.
        try:
            await pool.add_account(
                username=username,
                password=password,
                email=email,
                email_password=email_password,
                user_agent=user_agent,
                proxy=proxy or self._proxy,
                mfa_code=mfa_code,
                cookies=cookies,
            )
        except Exception:
            # Account may already exist—delete and re-add so credentials refresh
            await pool.delete_accounts([username])
            await pool.add_account(
                username=username,
                password=password,
                email=email,
                email_password=email_password,
                user_agent=user_agent,
                proxy=proxy or self._proxy,
                mfa_code=mfa_code,
                cookies=cookies,
            )

        logger.info("Running twscrape login flow for %s …", username)
        account = await pool.get_account(username)
        result = await twscrape_login(account, LoginConfig(manual=True))
        await pool.save()  # persist to accounts.db

        if result.active:
            logger.info("twscrape: logged in as %s", username)
            return {"success": True}
        return {"success": False, "error": getattr(result, "error_msg", "login returned inactive")}

    async def health_check(self) -> bool:
        """Check if engine is healthy."""
        try:
            await self._ensure_api()
            # Try a simple operation
            async for _ in self.api.search("test", limit=1):
                return True
            return True
        except Exception as e:
            logger.warning(f"twscrape health check failed: {e}")
            return False
    
    def _is_transient_error(self, error: Exception) -> bool:
        """Determine if error is transient (retryable)."""
        error_str = str(error).lower()
        transient_keywords = [
            "timeout", "connection", "rate limit", "429",
            "temporary", "unavailable", "service unavailable"
        ]
        return any(kw in error_str for kw in transient_keywords)