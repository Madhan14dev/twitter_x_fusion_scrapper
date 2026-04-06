"""Unified trend model."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class TrendModel:
    """Standardized trend data."""
    name: str
    url: str | None = None
    query: str | None = None
    
    # Metrics
    tweet_volume: int | None = None
    
    # Context
    domain_context: str | None = None
    meta_description: str | None = None
    
    # Related trends
    grouped_trends: list[str] = field(default_factory=list)
    
    # Source tracking
    source_engine: str = ""
    scraped_at: datetime = field(default_factory=datetime.now)
    raw_data: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "url": self.url,
            "query": self.query,
            "tweet_volume": self.tweet_volume,
            "domain_context": self.domain_context,
            "meta_description": self.meta_description,
            "grouped_trends": self.grouped_trends,
            "source_engine": self.source_engine,
            "scraped_at": self.scraped_at.isoformat()
        }
    
    @classmethod
    def from_twscrape(cls, data: dict[str, Any], source: str = "twscrape") -> "TrendModel":
        """Create from twscrape trend data."""
        trend_metadata = data.get("trend_metadata", {})
        
        return cls(
            name=data.get("name", ""),
            url=data.get("trend_url", {}).get("url") if isinstance(data.get("trend_url"), dict) else None,
            query=trend_metadata.get("metaDescription", ""),
            tweet_volume=int(data.get("rank", 0)) or None,
            domain_context=trend_metadata.get("domainContext", ""),
            grouped_trends=[t.get("name", "") for t in data.get("grouped_trends", [])],
            source_engine=source,
            raw_data=data
        )
    
    @classmethod
    def from_twikit(cls, data: dict[str, Any], source: str = "twikit") -> "TrendModel":
        """Create from twikit trend data."""
        return cls(
            name=data.get("name", ""),
            url=data.get("url"),
            query=data.get("query"),
            tweet_volume=data.get("tweets_count"),
            domain_context=data.get("domain_context"),
            source_engine=source,
            raw_data=data
        )