"""Unified tweet model."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class HashtagFields:
    """Hashtag field structure matching Twitter API."""
    tag: str


@dataclass
class TweetModel:
    """Standardized tweet data matching Twitter API v2 structure."""
    id: str
    text: str
    created_at: str | None = None
    author_id: str | None = None
    username: str | None = None

    # Engagement metrics
    public_metrics: dict[str, Any] = field(default_factory=dict)
    non_public_metrics: dict[str, Any] = field(default_factory=dict)
    organic_metrics: dict[str, Any] = field(default_factory=dict)
    promoted_metrics: dict[str, Any] = field(default_factory=dict)

    # Content metadata
    attachments: dict[str, Any] | None = None
    community_id: str | None = None
    context_annotations: list[dict[str, Any]] = field(default_factory=list)
    conversation_id: str | None = None
    display_text_range: list[int] | None = None
    edit_controls: dict[str, Any] | None = None
    edit_history_tweet_ids: list[str] = field(default_factory=list)
    entities: dict[str, Any] | None = None
    geo: dict[str, Any] | None = None
    in_reply_to_user_id: str | None = None
    lang: str | None = None
    note_tweet: dict[str, Any] | None = None
    possibly_sensitive: bool = False
    reply_settings: str | None = None
    scopes: dict[str, Any] | None = None
    source: str | None = None
    suggested_source_links: list[Any] = field(default_factory=list)
    suggested_source_links_with_counts: dict[str, Any] = field(default_factory=dict)
    withheld: dict[str, Any] | None = None

    # Referenced tweets
    referenced_tweets: list[dict[str, Any]] = field(default_factory=list)

    # Source tracking
    source_engine: str = ""
    scraped_at: datetime = field(default_factory=datetime.now)
    raw_data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "text": self.text,
            "created_at": self.created_at,
            "author_id": self.author_id,
            "username": self.username,
            "public_metrics": self.public_metrics,
            "non_public_metrics": self.non_public_metrics,
            "organic_metrics": self.organic_metrics,
            "promoted_metrics": self.promoted_metrics,
            "attachments": self.attachments,
            "community_id": self.community_id,
            "context_annotations": self.context_annotations,
            "conversation_id": self.conversation_id,
            "display_text_range": self.display_text_range,
            "edit_controls": self.edit_controls,
            "edit_history_tweet_ids": self.edit_history_tweet_ids,
            "entities": self.entities,
            "geo": self.geo,
            "in_reply_to_user_id": self.in_reply_to_user_id,
            "lang": self.lang,
            "note_tweet": self.note_tweet,
            "possibly_sensitive": self.possibly_sensitive,
            "reply_settings": self.reply_settings,
            "scopes": self.scopes,
            "source": self.source,
            "suggested_source_links": self.suggested_source_links,
            "suggested_source_links_with_counts": self.suggested_source_links_with_counts,
            "withheld": self.withheld,
            "referenced_tweets": self.referenced_tweets,
            "source_engine": self.source_engine,
            "scraped_at": self.scraped_at.isoformat()
        }

    @classmethod
    def from_twscrape(cls, data: dict[str, Any], source: str = "twscrape") -> "TweetModel":
        """Create from twscrape tweet data."""
        user = data.get("user", {})
        legacy = data.get("legacy", {})

        # Extract public metrics
        public_metrics = {
            "retweet_count": legacy.get("retweet_count", 0),
            "reply_count": legacy.get("reply_count", 0),
            "like_count": legacy.get("favorite_count", 0),
            "quote_count": legacy.get("quote_count", 0),
        }

        # Check for views in metrics
        metrics = data.get("metrics", {})
        if metrics:
            public_metrics["impression_count"] = metrics.get("impression_count", 0)

        # Parse entities
        entities = {}
        if legacy.get("entities"):
            entities = legacy.get("entities", {})

        return cls(
            id=str(data.get("id", "")),
            text=legacy.get("full_text", data.get("text", "")),
            created_at=data.get("created_at"),
            author_id=str(user.get("id", "")) if user else None,
            username=user.get("screen_name", "") if user else None,
            public_metrics=public_metrics,
            non_public_metrics=data.get("non_public_metrics", {}),
            organic_metrics=data.get("organic_metrics", {}),
            promoted_metrics=data.get("promoted_metrics", {}),
            attachments=data.get("attachments"),
            community_id=data.get("community_id"),
            context_annotations=data.get("context_annotations", []),
            conversation_id=data.get("conversation_id"),
            display_text_range=legacy.get("display_text_range"),
            edit_controls=data.get("edit_controls"),
            edit_history_tweet_ids=data.get("edit_history_tweet_ids", []),
            entities=entities if entities else None,
            geo=data.get("geo"),
            in_reply_to_user_id=str(legacy.get("in_reply_to_user_id", "")) if legacy.get("in_reply_to_user_id") else None,
            lang=legacy.get("lang"),
            note_tweet=data.get("note_tweet"),
            possibly_sensitive=legacy.get("possibly_sensitive", False) if legacy else False,
            reply_settings=data.get("reply_settings"),
            scopes=data.get("scopes"),
            source=legacy.get("source", "") if legacy else None,
            suggested_source_links=data.get("suggested_source_links", []),
            suggested_source_links_with_counts=data.get("suggested_source_links_with_counts", {}),
            withheld=data.get("withheld"),
            referenced_tweets=data.get("referenced_tweets", []),
            source_engine=source,
            scraped_at=datetime.now(),
            raw_data=data
        )

    @classmethod
    def from_twikit(cls, data: dict[str, Any], source: str = "twikit") -> "TweetModel":
        """Create from twikit tweet data."""
        user = data.get("user", {})

        # Build public metrics
        public_metrics = {
            "retweet_count": data.get("retweet_count", 0),
            "reply_count": data.get("reply_count", 0),
            "like_count": data.get("favorite_count", 0),
            "quote_count": 0,
        }

        return cls(
            id=str(data.get("id", "")),
            text=data.get("text", ""),
            created_at=data.get("created_at"),
            author_id=str(data.get("user_id", "")) if data.get("user_id") else None,
            username=user.get("screen_name", "") if isinstance(user, dict) else None,
            public_metrics=public_metrics,
            non_public_metrics=data.get("non_public_metrics", {}),
            organic_metrics=data.get("organic_metrics", {}),
            promoted_metrics=data.get("promoted_metrics", {}),
            attachments=data.get("attachments"),
            community_id=data.get("community_id"),
            context_annotations=data.get("context_annotations", []),
            conversation_id=data.get("conversation_id"),
            display_text_range=data.get("display_text_range"),
            edit_controls=data.get("edit_controls"),
            edit_history_tweet_ids=data.get("edit_history_tweet_ids", []),
            entities=data.get("entities"),
            geo=data.get("geo"),
            in_reply_to_user_id=data.get("in_reply_to_user_id"),
            lang=data.get("lang"),
            note_tweet=data.get("note_tweet"),
            possibly_sensitive=data.get("possibly_sensitive", False),
            reply_settings=data.get("reply_settings"),
            scopes=data.get("scopes"),
            source=data.get("source"),
            suggested_source_links=data.get("suggested_source_links", []),
            suggested_source_links_with_counts=data.get("suggested_source_links_with_counts", {}),
            withheld=data.get("withheld"),
            referenced_tweets=data.get("referenced_tweets", []),
            source_engine=source,
            scraped_at=datetime.now(),
            raw_data=data
        )
