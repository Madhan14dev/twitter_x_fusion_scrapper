"""Error handler with classification and retry logic."""
import asyncio
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, TypeVar


logger = logging.getLogger(__name__)


class ErrorType(Enum):
    """Error classification types."""
    TRANSIENT = "transient"      # Retryable - timeout, connection, rate limit
    AUTH = "auth"               # Auth issues - needs re-login
    RATE_LIMIT = "rate_limit"   # Rate limited - wait and retry
    PERMANENT = "permanent"     # Not retryable - invalid data, etc
    UNKNOWN = "unknown"         # Need investigation


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True


class ErrorHandler:
    """Handles errors with classification and retry logic."""
    
    def __init__(self, config: RetryConfig | None = None):
        self.config = config or RetryConfig()
        self._error_counts: dict[str, int] = {}
    
    def classify_error(self, error: Exception, context: str = "") -> ErrorType:
        """Classify an error type based on exception and context."""
        error_str = str(error).lower()
        error_type = type(error).__name__.lower()
        
        # Rate limit errors
        if any(x in error_str for x in ["429", "rate limit", "too many requests"]):
            return ErrorType.RATE_LIMIT
        
        # Auth errors
        if any(x in error_str for x in [
            "unauthorized", "401", "forbidden", "403",
            "authentication", "invalid credentials", "session expired",
            "account locked", "account suspended"
        ]):
            return ErrorType.AUTH
        
        # Transient errors
        if any(x in error_str for x in [
            "timeout", "timed out", "connection",
            "temporary", "unavailable", "503", "502",
            "internal server error"  # Sometimes transient
        ]):
            return ErrorType.TRANSIENT
        
        # Permanent errors
        if any(x in error_str for x in [
            "not found", "404", "invalid",
            "cannot find", "does not exist"
        ]):
            return ErrorType.PERMANENT
        
        return ErrorType.UNKNOWN
    
    def get_retry_delay(self, error_type: ErrorType, attempt: int) -> float:
        """Calculate retry delay based on error type and attempt."""
        if error_type == ErrorType.RATE_LIMIT:
            # Longer delays for rate limits
            delay = self.config.base_delay * (self.config.exponential_base ** (attempt + 1)) * 3
        elif error_type == ErrorType.TRANSIENT:
            delay = self.config.base_delay * (self.config.exponential_base ** attempt)
        else:
            delay = self.config.base_delay * (self.config.exponential_base ** (attempt - 1))
        
        # Add jitter
        if self.config.jitter:
            import random
            delay *= random.uniform(0.5, 1.5)
        
        return min(delay, self.config.max_delay)
    
    async def retry_with_backoff(
        self,
        func: Callable,
        *args,
        context: str = "",
        **kwargs
    ) -> Any:
        """Execute a function with retry logic."""
        last_error = None
        
        for attempt in range(self.config.max_retries):
            try:
                result = await func(*args, **kwargs)
                # Reset error count on success
                if context:
                    self._error_counts[context] = 0
                return result
                
            except Exception as e:
                last_error = e
                error_type = self.classify_error(e, context)
                
                logger.warning(
                    f"Attempt {attempt + 1}/{self.config.max_retries} failed "
                    f"for {context}: {error_type.value} - {type(e).__name__}: {e}"
                )
                
                # Don't retry permanent errors
                if error_type == ErrorType.PERMANENT:
                    logger.error(f"Permanent error in {context}, not retrying")
                    raise
                
                # Check if we have retries left
                if attempt < self.config.max_retries - 1:
                    delay = self.get_retry_delay(error_type, attempt)
                    logger.info(f"Retrying {context} in {delay:.1f}s...")
                    await asyncio.sleep(delay)
                    
                    # Track error for circuit breaker
                    if context:
                        self._error_counts[context] = self._error_counts.get(context, 0) + 1
                else:
                    logger.error(f"All retries exhausted for {context}")
        
        raise last_error
    
    def should_quarantine(self, context: str, threshold: int = 5) -> bool:
        """Check if a component should be quarantined."""
        return self._error_counts.get(context, 0) >= threshold
    
    def get_error_stats(self) -> dict[str, int]:
        """Get error count statistics."""
        return dict(self._error_counts)
    
    def reset_errors(self, context: str = ""):
        """Reset error counts."""
        if context:
            self._error_counts[context] = 0
        else:
            self._error_counts.clear()