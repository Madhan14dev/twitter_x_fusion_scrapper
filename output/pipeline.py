"""Output pipeline for saving scraped data."""
import asyncio
import json
import logging
import sqlite3
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any


logger = logging.getLogger(__name__)


@dataclass
class ScrapeResult:
    """Result from a scraping operation."""
    operation: str
    query: str
    count: int
    source_engine: str
    timestamp: datetime
    success: bool
    error: str | None = None


class OutputPipeline:
    """Handles output to JSON files and SQLite database."""
    
    def __init__(self, output_dir: Path, db_path: Path):
        self.output_dir = Path(output_dir)
        self.db_path = Path(db_path)
        
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self._init_db()
    
    def _init_db(self):
        """Initialize results database."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                operation TEXT NOT NULL,
                query TEXT NOT NULL,
                count INTEGER,
                source_engine TEXT,
                timestamp TEXT NOT NULL,
                success INTEGER,
                error TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tweets (
                id INTEGER PRIMARY KEY,
                text TEXT,
                author_id INTEGER,
                author_username TEXT,
                created_at TEXT,
                likes INTEGER,
                retweets INTEGER,
                source_engine TEXT,
                scraped_at TEXT,
                UNIQUE(id, source_engine)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT,
                name TEXT,
                followers_count INTEGER,
                following_count INTEGER,
                source_engine TEXT,
                scraped_at TEXT,
                UNIQUE(id, source_engine)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS trends (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                url TEXT,
                query TEXT,
                tweet_volume INTEGER,
                domain_context TEXT,
                source_engine TEXT,
                scraped_at TEXT,
                UNIQUE(name, source_engine)
            )
        """)
        conn.commit()
        conn.close()
    
    async def save_tweets(
        self,
        tweets: list[dict[str, Any]],
        filename: str,
        output_subdir: str = "search"
    ) -> Path:
        """Save tweets to JSON file."""
        output_path = self.output_dir / output_subdir / filename
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(tweets, f, indent=2, default=str, ensure_ascii=False)
        
        logger.info(f"Saved {len(tweets)} tweets to {output_path}")
        
        # Also save to DB
        await self._save_tweets_to_db(tweets)
        
        return output_path
    
    async def _save_tweets_to_db(self, tweets: list[dict[str, Any]]):
        """Save tweets to database."""
        conn = sqlite3.connect(self.db_path)
        for tweet in tweets:
            try:
                conn.execute("""
                    INSERT OR REPLACE INTO tweets 
                    (id, text, author_id, author_username, created_at, likes, retweets, source_engine, scraped_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    tweet.get("id"),
                    tweet.get("text", ""),
                    tweet.get("author_id"),
                    tweet.get("author_username"),
                    tweet.get("created_at"),
                    tweet.get("likes", 0),
                    tweet.get("retweets", 0),
                    tweet.get("source_engine", ""),
                    datetime.now().isoformat()
                ))
            except Exception as e:
                logger.debug(f"Failed to save tweet {tweet.get('id')}: {e}")
        conn.commit()
        conn.close()
    
    async def save_users(
        self,
        users: list[dict[str, Any]],
        filename: str,
        output_subdir: str = "users"
    ) -> Path:
        """Save users to JSON file."""
        output_path = self.output_dir / output_subdir / filename
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(users, f, indent=2, default=str, ensure_ascii=False)
        
        logger.info(f"Saved {len(users)} users to {output_path}")
        
        # Also save to DB
        await self._save_users_to_db(users)
        
        return output_path
    
    async def _save_users_to_db(self, users: list[dict[str, Any]]):
        """Save users to database."""
        conn = sqlite3.connect(self.db_path)
        for user in users:
            try:
                conn.execute("""
                    INSERT OR REPLACE INTO users
                    (id, username, name, followers_count, following_count, source_engine, scraped_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    user.get("id"),
                    user.get("username", ""),
                    user.get("name", ""),
                    user.get("followers_count", 0),
                    user.get("following_count", 0),
                    user.get("source_engine", ""),
                    datetime.now().isoformat()
                ))
            except Exception as e:
                logger.debug(f"Failed to save user {user.get('id')}: {e}")
        conn.commit()
        conn.close()
    
    async def save_trends(
        self,
        trends: list[dict[str, Any]],
        filename: str,
        output_subdir: str = "trends"
    ) -> Path:
        """Save trends to JSON file."""
        output_path = self.output_dir / output_subdir / filename
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(trends, f, indent=2, default=str, ensure_ascii=False)
        
        logger.info(f"Saved {len(trends)} trends to {output_path}")
        
        # Also save to DB
        await self._save_trends_to_db(trends)
        
        return output_path
    
    async def _save_trends_to_db(self, trends: list[dict[str, Any]]):
        """Save trends to database."""
        conn = sqlite3.connect(self.db_path)
        for trend in trends:
            try:
                conn.execute("""
                    INSERT OR REPLACE INTO trends
                    (name, url, query, tweet_volume, domain_context, source_engine, scraped_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    trend.get("name", ""),
                    trend.get("url"),
                    trend.get("query"),
                    trend.get("tweet_volume"),
                    trend.get("domain_context"),
                    trend.get("source_engine", ""),
                    datetime.now().isoformat()
                ))
            except Exception as e:
                logger.debug(f"Failed to save trend: {e}")
        conn.commit()
        conn.close()
    
    async def log_result(self, result: ScrapeResult):
        """Log scraping result to database."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            INSERT INTO results (operation, query, count, source_engine, timestamp, success, error)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            result.operation,
            result.query,
            result.count,
            result.source_engine,
            result.timestamp.isoformat(),
            1 if result.success else 0,
            result.error
        ))
        conn.commit()
        conn.close()
    
    async def get_stats(self) -> dict[str, Any]:
        """Get pipeline statistics."""
        conn = sqlite3.connect(self.db_path)
        
        # Tweet stats
        tweet_stats = conn.execute("SELECT COUNT(*), COUNT(DISTINCT id) FROM tweets").fetchone()
        
        # User stats
        user_stats = conn.execute("SELECT COUNT(*), COUNT(DISTINCT id) FROM users").fetchone()
        
        # Trend stats
        trend_stats = conn.execute("SELECT COUNT(*) FROM trends").fetchone()
        
        # Result stats
        result_stats = conn.execute("""
            SELECT 
                SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END),
                SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END),
                SUM(count)
            FROM results
        """).fetchone()
        
        conn.close()
        
        return {
            "tweets": {"total": tweet_stats[0], "unique": tweet_stats[1]},
            "users": {"total": user_stats[0], "unique": user_stats[1]},
            "trends": {"total": trend_stats[0]},
            "results": {
                "success": result_stats[0] or 0,
                "failed": result_stats[1] or 0,
                "total_items": result_stats[2] or 0
            }
        }