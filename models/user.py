"""Unified user model."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class UserModel:
    """Standardized user data."""
    id: int
    username: str
    name: str
    
    # Profile
    bio: str | None = None
    location: str | None = None
    website: str | None = None
    profile_image_url: str | None = None
    banner_url: str | None = None
    
    # Stats
    followers_count: int = 0
    following_count: int = 0
    tweets_count: int = 0
    likes_count: int = 0
    
    # Meta
    verified: bool = False
    verified_type: str | None = None
    created_at: datetime | None = None
    
    # Source tracking
    source_engine: str = ""
    scraped_at: datetime = field(default_factory=datetime.now)
    raw_data: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "username": self.username,
            "name": self.name,
            "bio": self.bio,
            "location": self.location,
            "website": self.website,
            "profile_image_url": self.profile_image_url,
            "banner_url": self.banner_url,
            "followers_count": self.followers_count,
            "following_count": self.following_count,
            "tweets_count": self.tweets_count,
            "likes_count": self.likes_count,
            "verified": self.verified,
            "verified_type": self.verified_type,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "source_engine": self.source_engine,
            "scraped_at": self.scraped_at.isoformat()
        }
    
    @classmethod
    def from_twscrape(cls, data: dict[str, Any], source: str = "twscrape") -> "UserModel":
        """Create from twscrape user data."""
        legacy = data.get("legacy", {})
        user = data if legacy else data
        
        return cls(
            id=int(data.get("id", 0)),
            username=user.get("screen_name", ""),
            name=user.get("name", ""),
            bio=legacy.get("description", "") if legacy else user.get("description"),
            location=legacy.get("location", "") if legacy else user.get("location"),
            website=legacy.get("entities", {}).get("url", {}).get("urls", [{}])[0].get("expanded_url") if legacy else None,
            profile_image_url=legacy.get("profile_image_url_https", "") if legacy else user.get("profile_image_url"),
            banner_url=legacy.get("profile_banner_url", "") if legacy else user.get("banner_url"),
            followers_count=legacy.get("followers_count", 0) if legacy else user.get("followers_count", 0),
            following_count=legacy.get("friends_count", 0) if legacy else user.get("friends_count", 0),
            tweets_count=legacy.get("statuses_count", 0) if legacy else user.get("statuses_count", 0),
            likes_count=legacy.get("favourites_count", 0) if legacy else user.get("favourites_count", 0),
            verified=legacy.get("verified", False) if legacy else user.get("verified", False),
            created_at=datetime.fromisoformat(legacy.get("created_at", "").replace("Z", "+00:00")) if legacy and legacy.get("created_at") else None,
            source_engine=source,
            raw_data=data
        )
    
    @classmethod
    def from_twikit(cls, data: dict[str, Any], source: str = "twikit") -> "UserModel":
        """Create from twikit user data."""
        return cls(
            id=int(data.get("id", 0)),
            username=data.get("screen_name", ""),
            name=data.get("name", ""),
            bio=data.get("description"),
            location=data.get("location"),
            profile_image_url=data.get("profile_image_url"),
            banner_url=data.get("banner_url"),
            followers_count=data.get("followers_count", 0),
            following_count=data.get("friends_count", 0),
            tweets_count=data.get("statuses_count", 0),
            likes_count=data.get("favourites_count", 0),
            verified=data.get("verified", False),
            created_at=datetime.fromisoformat(data.get("created_at", "").replace("Z", "+00:00")) if data.get("created_at") else None,
            source_engine=source,
            raw_data=data
        )