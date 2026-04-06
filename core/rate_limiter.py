"""Rate limiter with adaptive backoff."""
import asyncio
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any


logger = logging.getLogger(__name__)


@dataclass
class RateLimitState:
    """Rate limit state for an account/engine."""
    requests: list[float] = field(default_factory=list)
    total_requests: int = 0
    total_success: int = 0
    total_failures: int = 0


class RateLimiter:
    """Adaptive rate limiter with per-account and global limits."""
    
    def __init__(
        self,
        requests_per_minute: int = 60,
        requests_per_hour: int = 500,
        adaptive: bool = True,
        backoff_base: float = 2.0,
        max_backoff: int = 300
    ):
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
        self.adaptive = adaptive
        self.backoff_base = backoff_base
        self.max_backoff = max_backoff
        
        self._states: dict[str, RateLimitState] = defaultdict(RateLimitState)
        self._locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._global_lock = asyncio.Lock()
        self._waiting: dict[str, asyncio.Event] = {}
    
    def _cleanup_old_requests(self, state: RateLimitState, window_seconds: int):
        """Remove requests outside the time window."""
        now = time.time()
        state.requests = [t for t in state.requests if now - t < window_seconds]
    
    async def acquire(
        self,
        key: str = "default",
        check_global: bool = True
    ) -> bool:
        """Acquire a rate limit slot. Returns True if allowed."""
        async with self._locks[key]:
            state = self._states[key]
            
            # Clean up old requests
            self._cleanup_old_requests(state, 60)  # 1 minute window
            self._cleanup_old_requests(state, 3600)  # 1 hour window
            
            # Check per-minute limit
            if len(state.requests) >= self.requests_per_minute:
                wait_time = 60 - (time.time() - state.requests[0])
                if wait_time > 0:
                    logger.warning(f"Rate limit (min) for {key}, waiting {wait_time:.1f}s")
                    await asyncio.sleep(wait_time)
                    return await self.acquire(key, check_global)
            
            # Check per-hour limit
            if len(state.requests) >= self.requests_per_hour:
                wait_time = 3600 - (time.time() - state.requests[0])
                if wait_time > 0:
                    logger.warning(f"Rate limit (hour) for {key}, waiting {wait_time:.1f}s")
                    await asyncio.sleep(wait_time)
                    return await self.acquire(key, check_global)
            
            # Add current request timestamp
            state.requests.append(time.time())
            state.total_requests += 1
            
            return True
    
    async def release(self, key: str, success: bool):
        """Release after a request."""
        state = self._states[key]
        if success:
            state.total_success += 1
        else:
            state.total_failures += 1
    
    async def wait_if_needed(self, key: str) -> float:
        """Calculate and return wait time if rate limited."""
        state = self._states[key]
        self._cleanup_old_requests(state, 60)
        
        if len(state.requests) >= self.requests_per_minute:
            wait_time = 60 - (time.time() - state.requests[0])
            return max(0, wait_time)
        
        return 0
    
    def get_backoff_time(self, key: str, failure_count: int) -> float:
        """Calculate exponential backoff time."""
        if not self.adaptive:
            return 0
        
        if failure_count == 0:
            return 0
        
        backoff = min(
            self.backoff_base ** failure_count,
            self.max_backoff
        )
        
        # Add jitter (0.5 to 1.5 of backoff time)
        import random
        jitter = random.uniform(0.5, 1.5)
        
        return backoff * jitter
    
    async def record_and_wait(
        self,
        key: str,
        success: bool,
        failure_count: int = 0
    ) -> float:
        """Record result and return backoff time if needed."""
        await self.release(key, success)
        
        if not success:
            backoff = self.get_backoff_time(key, failure_count)
            if backoff > 0:
                logger.info(f"Backing off {key} for {backoff:.1f}s after failure")
                await asyncio.sleep(backoff)
                return backoff
        
        return 0
    
    async def get_stats(self, key: str = "default") -> dict[str, Any]:
        """Get rate limiter stats."""
        state = self._states.get(key, RateLimitState())
        
        self._cleanup_old_requests(state, 60)
        self._cleanup_old_requests(state, 3600)
        
        return {
            "requests_last_minute": len(state.requests),
            "total_requests": state.total_requests,
            "total_success": state.total_success,
            "total_failures": state.total_failures,
            "success_rate": (
                state.total_success / state.total_requests 
                if state.total_requests > 0 else 0
            )
        }
    
    def reset(self, key: str = "default"):
        """Reset rate limiter state for a key."""
        if key in self._states:
            self._states[key] = RateLimitState()
        logger.info(f"Reset rate limiter for {key}")
    
    def reset_all(self):
        """Reset all rate limiter states."""
        self._states.clear()
        logger.info("Reset all rate limiters")