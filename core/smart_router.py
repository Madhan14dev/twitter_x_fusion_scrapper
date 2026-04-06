"""Smart router with fallback chain and circuit breaker."""
import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, TypeVar, Callable
from datetime import datetime, timedelta
from collections import defaultdict

from engines.base import BaseEngine, EngineResult, EngineError


logger = logging.getLogger(__name__)

T = TypeVar('T')


@dataclass
class RouteConfig:
    """Configuration for an operation route."""
    engines: list[str]  # Engine names in fallback order
    timeout: int = 30
    retries: int = 3
    retry_delay: int = 2


class CircuitBreaker:
    """Circuit breaker for individual engines."""
    
    def __init__(self, failure_threshold: int = 5, timeout: int = 300):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failures: dict[str, int] = defaultdict(int)
        self.last_failure: dict[str, datetime] = {}
        self._locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
    
    def record_success(self, engine: str):
        """Record successful request."""
        self.failures[engine] = 0
    
    def record_failure(self, engine: str):
        """Record failed request."""
        self.failures[engine] += 1
        self.last_failure[engine] = datetime.now()
    
    def is_open(self, engine: str) -> bool:
        """Check if circuit is open (blocked)."""
        if self.failures[engine] >= self.failure_threshold:
            # Check if timeout has passed
            if engine in self.last_failure:
                elapsed = (datetime.now() - self.last_failure[engine]).total_seconds()
                if elapsed >= self.timeout:
                    # Reset after timeout
                    self.failures[engine] = 0
                    return False
            return True
        return False
    
    async def get_engine(self, engine: str) -> bool:
        """Get engine with lock."""
        async with self._locks[engine]:
            return not self.is_open(engine)


class SmartRouter:
    """Smart routing with fallback chain across multiple engines."""
    
    def __init__(self, engines: dict[str, BaseEngine], config: dict[str, Any] | None = None):
        self.engines = engines
        self.config = config or {}
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=config.get("circuit_breaker_threshold", 5),
            timeout=config.get("circuit_breaker_timeout", 300)
        )
        
        # Default routes - can be customized
        self.routes: dict[str, RouteConfig] = {
            "search": RouteConfig(
                engines=["twscrape", "twikit"],
                timeout=30,
                retries=3
            ),
            "user_tweets": RouteConfig(
                engines=["twscrape", "twikit"],
                timeout=30,
                retries=3
            ),
            "user_by_login": RouteConfig(
                engines=["twscrape", "twikit"],
                timeout=20,
                retries=2
            ),
            "user_by_id": RouteConfig(
                engines=["twscrape", "twikit"],
                timeout=20,
                retries=2
            ),
            "tweet_details": RouteConfig(
                engines=["twscrape", "twikit"],
                timeout=20,
                retries=2
            ),
            "trends": RouteConfig(
                engines=["twikit", "twscrape"],  # twikit primary for trends
                timeout=30,
                retries=3
            ),
            "followers": RouteConfig(
                engines=["twscrape", "twikit"],
                timeout=30,
                retries=3
            ),
            "following": RouteConfig(
                engines=["twscrape", "twikit"],
                timeout=30,
                retries=3
            ),
        }
    
    def set_route(self, operation: str, engines: list[str]):
        """Set custom engine order for an operation."""
        if operation in self.routes:
            self.routes[operation].engines = engines
        else:
            self.routes[operation] = RouteConfig(engines=engines)
    
    async def route(
        self,
        operation: str,
        generator_func: Callable[..., AsyncGenerator[EngineResult[T], None]],
        *args,
        **kwargs
    ) -> AsyncGenerator[EngineResult[T], None]:
        """Route an operation with fallback chain."""
        route_config = self.routes.get(operation, RouteConfig(engines=list(self.engines.keys())))
        
        last_error: EngineError | None = None
        
        for engine_name in route_config.engines:
            # Check circuit breaker
            if self.circuit_breaker.is_open(engine_name):
                logger.debug(f"Circuit breaker open for {engine_name}, skipping")
                continue
            
            engine = self.engines.get(engine_name)
            if not engine or not engine.is_available:
                continue
            
            logger.info(f"Attempting {operation} with {engine_name}")
            
            try:
                async for result in generator_func(engine, *args, **kwargs):
                    self.circuit_breaker.record_success(engine_name)
                    engine.record_success()
                    yield result
                
                # If we got here without exception, operation succeeded
                logger.info(f"{operation} completed with {engine_name}")
                return
                
            except EngineError as e:
                last_error = e
                self.circuit_breaker.record_failure(engine_name)
                engine.record_failure(e)
                
                logger.warning(f"{engine_name} failed for {operation}: {e}")
                
                if not e.is_transient:
                    # Non-transient error - skip to next engine immediately
                    continue
                
                # Transient error - wait and retry
                await asyncio.sleep(route_config.retry_delay)
                continue
                
            except Exception as e:
                last_error = e
                self.circuit_breaker.record_failure(engine_name)
                logger.warning(f"{engine_name} exception for {operation}: {e}")
                continue
        
        # All engines failed
        if last_error:
            raise last_error
        raise EngineError(
            engine="router",
            operation=operation,
            error_type="NoEnginesAvailable",
            message="All engines failed or unavailable",
            is_transient=True
        )
    
    # Convenience methods for common operations
    
    async def search(
        self,
        query: str,
        limit: int = 100,
        **kwargs
    ) -> AsyncGenerator[EngineResult[dict], None]:
        """Search with automatic fallback."""
        async def _search(engine, query, limit, **kw):
            async for result in engine.search(query, limit, **kw):
                yield result
        
        async for result in self.route("search", _search, query, limit, **kwargs):
            yield result
    
    async def user_tweets(
        self,
        user_id: str | int,
        limit: int = 100,
        **kwargs
    ) -> AsyncGenerator[EngineResult[dict], None]:
        """User tweets with automatic fallback."""
        async def _user_tweets(engine, user_id, limit, **kw):
            async for result in engine.user_tweets(user_id, limit, **kw):
                yield result
        
        async for result in self.route("user_tweets", _user_tweets, user_id, limit, **kwargs):
            yield result
    
    async def user_by_login(
        self,
        username: str,
        **kwargs
    ) -> EngineResult[dict] | None:
        """Get user by login with fallback."""
        for engine_name in self.routes.get("user_by_login", RouteConfig(engines=list(self.engines.keys()))).engines:
            if self.circuit_breaker.is_open(engine_name):
                continue
            
            engine = self.engines.get(engine_name)
            if not engine or not engine.is_available:
                continue
            
            try:
                result = await engine.user_by_login(username, **kwargs)
                if result:
                    self.circuit_breaker.record_success(engine_name)
                    engine.record_success()
                    return result
            except EngineError as e:
                self.circuit_breaker.record_failure(engine_name)
                engine.record_failure(e)
                logger.warning(f"{engine_name} failed for user_by_login: {e}")
                continue
            except Exception as e:
                logger.warning(f"{engine_name} exception for user_by_login: {e}")
                continue
        
        return None
    
    async def tweet_details(
        self,
        tweet_id: int,
        **kwargs
    ) -> EngineResult[dict] | None:
        """Tweet details with fallback."""
        for engine_name in self.routes.get("tweet_details", RouteConfig(engines=list(self.engines.keys()))).engines:
            if self.circuit_breaker.is_open(engine_name):
                continue
            
            engine = self.engines.get(engine_name)
            if not engine or not engine.is_available:
                continue
            
            try:
                result = await engine.tweet_details(tweet_id, **kwargs)
                if result:
                    self.circuit_breaker.record_success(engine_name)
                    engine.record_success()
                    return result
            except EngineError as e:
                self.circuit_breaker.record_failure(engine_name)
                engine.record_failure(e)
                logger.warning(f"{engine_name} failed for tweet_details: {e}")
                continue
        
        return None
    
    async def trends(
        self,
        category: str = "trending",
        limit: int = 100,
        **kwargs
    ) -> AsyncGenerator[EngineResult[dict], None]:
        """Trends with fallback (primary: twikit)."""
        async def _trends(engine, category, limit, **kw):
            async for result in engine.trends(category, limit, **kw):
                yield result
        
        async for result in self.route("trends", _trends, category, limit, **kwargs):
            yield result
    
    async def get_status(self) -> dict[str, Any]:
        """Get router status."""
        return {
            "engines": {
                name: {
                    "available": eng.is_available,
                    "failure_count": eng.failure_count,
                    "circuit_open": self.circuit_breaker.is_open(name)
                }
                for name, eng in self.engines.items()
            },
            "routes": {
                op: cfg.engines for op, cfg in self.routes.items()
            }
        }
    
    async def close_all(self):
        """Close all engines."""
        for engine in self.engines.values():
            await engine.close()