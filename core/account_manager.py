"""Account manager for managing multiple accounts."""
import asyncio
import json
import logging
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


logger = logging.getLogger(__name__)


@dataclass
class Account:
    """Account data."""
    username: str
    cookies: dict[str, str] = field(default_factory=dict)
    headers: dict[str, str] = field(default_factory=dict)
    active: bool = True
    locked: bool = False
    locked_until: datetime | None = None
    failed_requests: int = 0
    total_requests: int = 0
    proxy: str | None = None


class AccountManager:
    """Manages a pool of accounts with health tracking."""
    
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None
        self._lock = asyncio.Lock()
        self._init_db()
    
    def _init_db(self):
        """Initialize database schema."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                username TEXT PRIMARY KEY,
                cookies TEXT,
                headers TEXT,
                active INTEGER DEFAULT 1,
                locked INTEGER DEFAULT 0,
                locked_until TEXT,
                failed_requests INTEGER DEFAULT 0,
                total_requests INTEGER DEFAULT 0,
                proxy TEXT
            )
        """)
        conn.commit()
        conn.close()
    
    @property
    def conn(self) -> sqlite3.Connection:
        """Get database connection."""
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path)
        return self._conn
    
    async def add_account(
        self,
        username: str,
        cookies: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
        proxy: str | None = None
    ):
        """Add an account to the pool."""
        async with self._lock:
            conn = self.conn
            conn.execute("""
                INSERT OR REPLACE INTO accounts (username, cookies, headers, proxy)
                VALUES (?, ?, ?, ?)
            """, (
                username,
                json.dumps(cookies or {}),
                json.dumps(headers or {}),
                proxy
            ))
            conn.commit()
            logger.info(f"Added account: {username}")
    
    async def get_active_accounts(self) -> list[Account]:
        """Get all active (not locked) accounts."""
        conn = self.conn
        cursor = conn.execute("""
            SELECT username, cookies, headers, active, locked, locked_until,
                   failed_requests, total_requests, proxy
            FROM accounts
            WHERE active = 1 AND locked = 0
        """)
        
        accounts = []
        for row in cursor.fetchall():
            locked_until = None
            if row[4] and row[5]:
                locked_until = datetime.fromisoformat(row[5])
                if locked_until < datetime.now():
                    continue
            
            accounts.append(Account(
                username=row[0],
                cookies=json.loads(row[1]) if row[1] else {},
                headers=json.loads(row[2]) if row[2] else {},
                active=bool(row[3]),
                locked=bool(row[4]),
                locked_until=locked_until,
                failed_requests=row[6],
                total_requests=row[7],
                proxy=row[8]
            ))
        
        return accounts
    
    async def get_account_by_username(self, username: str) -> Account | None:
        """Get account by username."""
        conn = self.conn
        cursor = conn.execute("""
            SELECT username, cookies, headers, active, locked, locked_until,
                   failed_requests, total_requests, proxy
            FROM accounts
            WHERE username = ?
        """, (username,))
        
        row = cursor.fetchone()
        if not row:
            return None
        
        return Account(
            username=row[0],
            cookies=json.loads(row[1]) if row[1] else {},
            headers=json.loads(row[2]) if row[2] else {},
            active=bool(row[3]),
            locked=bool(row[4]),
            locked_until=datetime.fromisoformat(row[5]) if row[5] else None,
            failed_requests=row[6],
            total_requests=row[7],
            proxy=row[8]
        )
    
    async def lock_account(self, username: str, duration_minutes: int = 15):
        """Lock an account for a duration."""
        async with self._lock:
            locked_until = datetime.now().timestamp() + (duration_minutes * 60)
            conn = self.conn
            conn.execute("""
                UPDATE accounts
                SET locked = 1, locked_until = ?
                WHERE username = ?
            """, (datetime.fromtimestamp(locked_until).isoformat(), username))
            conn.commit()
            logger.info(f"Locked account {username} for {duration_minutes} minutes")
    
    async def unlock_account(self, username: str):
        """Unlock an account."""
        async with self._lock:
            conn = self.conn
            conn.execute("""
                UPDATE accounts
                SET locked = 0, locked_until = NULL
                WHERE username = ?
            """, (username,))
            conn.commit()
            logger.info(f"Unlocked account {username}")
    
    async def record_request(self, username: str, success: bool):
        """Record a request for an account."""
        async with self._lock:
            conn = self.conn
            if success:
                conn.execute("""
                    UPDATE accounts
                    SET total_requests = total_requests + 1, failed_requests = 0
                    WHERE username = ?
                """, (username,))
            else:
                conn.execute("""
                    UPDATE accounts
                    SET total_requests = total_requests + 1,
                        failed_requests = failed_requests + 1
                    WHERE username = ?
                """, (username,))
            conn.commit()
    
    async def deactivate_account(self, username: str, reason: str = ""):
        """Deactivate an account (e.g., banned)."""
        async with self._lock:
            conn = self.conn
            conn.execute("""
                UPDATE accounts
                SET active = 0
                WHERE username = ?
            """, (username,))
            conn.commit()
            logger.warning(f"Deactivated account {username}: {reason}")
    
    async def load_cookies_from_file(self, username: str, filepath: str):
        """Load cookies from a JSON file."""
        with open(filepath, 'r') as f:
            cookies = json.load(f)
        
        await self.add_account(username, cookies=cookies)
    
    async def get_stats(self) -> dict[str, Any]:
        """Get account pool statistics."""
        conn = self.conn
        cursor = conn.execute("""
            SELECT
                COUNT(*) as total,
                SUM(active) as active,
                SUM(CASE WHEN locked = 1 THEN 1 ELSE 0 END) as locked,
                SUM(total_requests) as total_requests,
                SUM(failed_requests) as failed_requests
            FROM accounts
        """)
        row = cursor.fetchone()
        
        return {
            "total": row[0] or 0,
            "active": row[1] or 0,
            "locked": row[2] or 0,
            "total_requests": row[3] or 0,
            "failed_requests": row[4] or 0
        }
    
    def close(self):
        """Close database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None