from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, TypeVar, Generic
from datetime import datetime


T = TypeVar('T')


@dataclass
class EngineResult(Generic[T]):
    """Standardized result from any engine."""
    data: T
    source_engine: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class EngineError(Exception):
    """Base exception for engine errors."""
    engine: str
    operation: str
    error_type: str
    message: str
    is_transient: bool = True
    retry_after: int | None = None
    
    def __str__(self):
        return f"[{self.engine}] {self.operation}: {self.error_type} - {self.message}"


class BaseEngine(ABC):
    """Abstract base class for all engine adapters."""
    
    name: str = "base"
    
    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self._is_available = True
        self._failure_count = 0
        self._last_failure: datetime | None = None
    
    @property
    def is_available(self) -> bool:
        """Check if engine is available for requests."""
        return self._is_available
    
    @property
    def failure_count(self) -> int:
        """Number of consecutive failures."""
        return self._failure_count
    
    def record_success(self):
        """Record a successful request."""
        self._failure_count = 0
        self._is_available = True
    
    def record_failure(self, error: Exception):
        """Record a failed request."""
        self._failure_count += 1
        self._last_failure = datetime.now()
        
        # Circuit breaker: disable after threshold
        threshold = self.config.get("circuit_breaker_threshold", 5)
        if self._failure_count >= threshold:
            self._is_available = False
    
    async def search(
        self, 
        query: str, 
        limit: int = 100,
        **kwargs
    ) -> AsyncGenerator[EngineResult[dict], None]:
        """Search for tweets."""
        raise NotImplementedError
    
    async def user_tweets(
        self,
        user_id: str | int,
        limit: int = 100,
        **kwargs
    ) -> AsyncGenerator[EngineResult[dict], None]:
        """Get tweets from a user."""
        raise NotImplementedError
    
    async def user_by_login(
        self,
        username: str,
        **kwargs
    ) -> EngineResult[dict] | None:
        """Get user by username."""
        raise NotImplementedError
    
    async def tweet_details(
        self,
        tweet_id: int,
        **kwargs
    ) -> EngineResult[dict] | None:
        """Get tweet details."""
        raise NotImplementedError
    
    async def trends(
        self,
        category: str = "trending",
        limit: int = 100,
        **kwargs
    ) -> AsyncGenerator[EngineResult[dict], None]:
        """Get trends by category."""
        raise NotImplementedError
    
    async def followers(
        self,
        user_id: str | int,
        limit: int = 100,
        **kwargs
    ) -> AsyncGenerator[EngineResult[dict], None]:
        """Get followers of a user."""
        raise NotImplementedError
    
    async def following(
        self,
        user_id: str | int,
        limit: int = 100,
        **kwargs
    ) -> AsyncGenerator[EngineResult[dict], None]:
        """Get following of a user."""
        raise NotImplementedError
    
    async def close(self):
        """Clean up resources."""
        pass
    
    async def health_check(self) -> bool:
        """Check if engine is healthy."""
        raise NotImplementedError