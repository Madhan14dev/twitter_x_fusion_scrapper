"""Unified tweet model."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class TweetModel:
    """Standardized tweet data."""
    id: int
    text: str
    created_at: datetime | None = None
    author_id: int | None = None
    author_username: str | None = None
    author_name: str | None = None
    
    # Metrics
    likes: int = 0
    retweets: int = 0
    replies: int = 0
    quotes: int = 0
    views: int = 0
    
    # Additional
    in_reply_to_tweet_id: int | None = None
    in_reply_to_user_id: int | None = None
    is_retweet: bool = False
    is_quote: bool = False
    is_reply: bool = False
    
    # Source tracking
    source_engine: str = ""
    scraped_at: datetime = field(default_factory=datetime.now)
    raw_data: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "text": self.text,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "author_id": self.author_id,
            "author_username": self.author_username,
            "author_name": self.author_name,
            "likes": self.likes,
            "retweets": self.retweets,
            "replies": self.replies,
            "quotes": self.quotes,
            "views": self.views,
            "in_reply_to_tweet_id": self.in_reply_to_tweet_id,
            "in_reply_to_user_id": self.in_reply_to_user_id,
            "is_retweet": self.is_retweet,
            "is_quote": self.is_quote,
            "is_reply": self.is_reply,
            "source_engine": self.source_engine,
            "scraped_at": self.scraped_at.isoformat()
        }
    
    @classmethod
    def from_twscrape(cls, data: dict[str, Any], source: str = "twscrape") -> "TweetModel":
        """Create from twscrape tweet data."""
        user = data.get("user", {})
        
        # Parse engagement metrics from legacy
        legacy = data.get("legacy", {})
        metrics = legacy or data
        
        return cls(
            id=int(data.get("id", 0)),
            text=legacy.get("full_text", data.get("text", "")),
            created_at=datetime.fromisoformat(data.get("created_at", "").replace("Z", "+00:00")) if data.get("created_at") else None,
            author_id=int(user.get("id", 0)) if user else None,
            author_username=user.get("screen_name", "") if user else None,
            author_name=user.get("name", "") if user else None,
            likes=metrics.get("favorite_count", 0),
            retweets=metrics.get("retweet_count", 0),
            replies=metrics.get("reply_count", 0),
            in_reply_to_tweet_id=int(metrics.get("in_reply_to_status_id_str", 0)) or None,
            in_reply_to_user_id=int(metrics.get("in_reply_to_user_id_str", 0)) or None,
            is_retweet=legacy.get("retweeted", False) if legacy else False,
            is_reply=legacy.get("in_reply_to_status_id", False) if legacy else False,
            source_engine=source,
            raw_data=data
        )
    
    @classmethod
    def from_twikit(cls, data: dict[str, Any], source: str = "twikit") -> "TweetModel":
        """Create from twikit tweet data."""
        return cls(
            id=int(data.get("id", 0)),
            text=data.get("text", ""),
            created_at=datetime.fromisoformat(data.get("created_at", "").replace("Z", "+00:00")) if data.get("created_at") else None,
            author_id=int(data.get("user_id", 0)) or None,
            author_username=data.get("user", {}).get("screen_name") if isinstance(data.get("user"), dict) else None,
            author_name=data.get("user", {}).get("name") if isinstance(data.get("user"), dict) else None,
            likes=data.get("favorite_count", 0),
            retweets=data.get("retweet_count", 0),
            replies=data.get("reply_count", 0),
            source_engine=source,
            raw_data=data
        )