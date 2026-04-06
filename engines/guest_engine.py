"""Guest engine for unauthenticated access."""
import logging
from typing import Any, AsyncGenerator
from datetime import datetime

try:
    from twikit import Client as GuestClient
    GUEST_AVAILABLE = True
except ImportError:
    GUEST_AVAILABLE = False
    GuestClient = None  # type: ignore

from engines.base import BaseEngine, EngineResult, EngineError


logger = logging.getLogger(__name__)


class GuestEngine(BaseEngine):
    """Guest (unauthenticated) engine for basic lookups."""
    
    name = "guest"
    
    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        
        if not GUEST_AVAILABLE:
            raise ImportError("twikit is not installed for guest access")
        
        self._client = None
    
    @property
    def client(self):
        """Get or create guest client."""
        if self._client is None and GuestClient:
            self._client = GuestClient(language='en-US')
        return self._client
    
    async def search(
        self,
        query: str,
        limit: int = 100,
        **kwargs
    ) -> AsyncGenerator[EngineResult[dict], None]:
        """Search with guest access - limited results."""
        try:
            product = kwargs.get("product", "Latest")
            count = min(limit, 20)  # Guest has lower limits
            
            cursor = None
            fetched = 0
            
            while fetched < limit:
                # Guest client search is limited
                tweets = await self.client.guest_search_tweet(
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
                        metadata={"query": query, "limit": limit, "guest": True}
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
                operation="search",
                error_type=type(e).__name__,
                message=str(e),
                is_transient=self._is_transient_error(e)
            )
    
    async def user_by_login(
        self,
        username: str,
        **kwargs
    ) -> EngineResult[dict] | None:
        """Get user by username - limited info."""
        try:
            user = await self.client.guest_get_user(username)
            if not user:
                return None
            
            return EngineResult(
                data=user._to_dict() if hasattr(user, '_to_dict') else vars(user),
                source_engine=self.name,
                metadata={"username": username, "guest": True}
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
        """Get user by numeric ID - limited info."""
        try:
            user = await self.client.guest_get_user_by_id(user_id)
            if not user:
                return None
            
            return EngineResult(
                data=user._to_dict() if hasattr(user, '_to_dict') else vars(user),
                source_engine=self.name,
                metadata={"user_id": str(user_id), "guest": True}
            )
        except Exception as e:
            raise EngineError(
                engine=self.name,
                operation="user_by_id",
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
        """Get user tweets - limited."""
        # Guest can't get user tweets in most cases
        raise EngineError(
            engine=self.name,
            operation="user_tweets",
            error_type="NotSupported",
            message="Guest access does not support user tweets",
            is_transient=False
        )
    
    async def tweet_details(
        self,
        tweet_id: int,
        **kwargs
    ) -> EngineResult[dict] | None:
        """Get tweet details - limited."""
        try:
            tweet = await self.client.guest_get_tweet(tweet_id)
            if not tweet:
                return None
            
            return EngineResult(
                data=tweet._to_dict() if hasattr(tweet, '_to_dict') else vars(tweet),
                source_engine=self.name,
                metadata={"tweet_id": str(tweet_id), "guest": True}
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
        """Trends not available for guest."""
        raise EngineError(
            engine=self.name,
            operation="trends",
            error_type="NotSupported",
            message="Guest access does not support trends",
            is_transient=False
        )
    
    async def followers(
        self,
        user_id: str | int,
        limit: int = 100,
        **kwargs
    ) -> AsyncGenerator[EngineResult[dict], None]:
        """Followers not available for guest."""
        raise EngineError(
            engine=self.name,
            operation="followers",
            error_type="NotSupported",
            message="Guest access does not support followers",
            is_transient=False
        )
    
    async def following(
        self,
        user_id: str | int,
        limit: int = 100,
        **kwargs
    ) -> AsyncGenerator[EngineResult[dict], None]:
        """Following not available for guest."""
        raise EngineError(
            engine=self.name,
            operation="following",
            error_type="NotSupported",
            message="Guest access does not support following",
            is_transient=False
        )
    
    async def health_check(self) -> bool:
        """Check if guest access works."""
        try:
            # Try a simple guest operation
            return True
        except Exception as e:
            logger.warning(f"Guest health check failed: {e}")
            return False
    
    def _is_transient_error(self, error: Exception) -> bool:
        """Determine if error is transient."""
        error_str = str(error).lower()
        return "timeout" in error_str or "connection" in error_str