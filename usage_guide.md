# Usage Guide

## 1. Environment Setup

```bash
cd D:\SMA\twitter

# Activate virtual environment
.\.venv\Scripts\activate

# Verify dependencies
python -c "import twscrape, twikit; print('twscrape:', twscrape.__version__); print('twikit: OK')"
```

## 2. Configure Environment (Optional)

```bash
# Copy template
copy .env.example .env

# Optional: edit with your proxy settings
```

| Variable | Purpose | Default |
|----------|---------|---------|
| `TWS_PROXY` | HTTP proxy URL | none |
| `TWS_SSL_VERIFY` | Set `false` for corporate proxies | `true` |
| `LOG_LEVEL` | `DEBUG`, `INFO`, `WARNING`, `ERROR` | `INFO` |

## 3. Log In Twitter Accounts

> **Must be done before scraping.** The pipeline needs at least one authenticated account.

### Interactive Login
```bash
# Prompts for password & email
python cli.py login myusername
```

### Non-Interactive Login
```bash
# All credentials on command line
python cli.py login myusername --password "mypassword" --email "my@email.com"
```

### With MFA / TOTP Secret
```bash
python cli.py login myusername --password "mypassword" --email "my@email.com" --mfa "ABC123"
```

### Against Specific Engine
```bash
# twscrape only
python cli.py login myusername --engines twscrape

# twikit only
python cli.py login myusername --engines twikit

# Both (default)
python cli.py login myusername --engines twscrape twikit
```

### What is Stored Where
- **twscrape** → `accounts.db` (SQLite, auto-managed pool)
- **twikit** → `output/cookies_<username>.json` (per-account cookie files)

To add more accounts, simply repeat the login command. Engine discovery automatically picks up all valid accounts.

## 4. Check Pipeline Status

```bash
python cli.py status
```

Output should show each engine with `available=True` and circuit breakers `open=False`.

## 5. Search Tweets

```bash
# Basic search
python cli.py search "python programming" --limit 50

# Multiple queries
python cli.py search "AI" "machine learning" --limit 30

# Limit to one engine
python cli.py search "test" --limit 20 --engines twscrape

# Don't save to file
python cli.py search "test" --no-output

# Custom tab
python cli.py search "test" --limit 20 --tab Top
```

Output: `output/search/<timestamp>.json` + `pipeline.db`

## 6. Get Trends

```bash
# All categories (trending, news, sport, entertainment)
python cli.py trends

# Specific category
python cli.py trends --categories trending news

# Custom limit
python cli.py trends --categories sport --limit 50
```

Output: `output/trends/<category>_<timestamp>.json` + `pipeline.db`

> **Note:** twikit is the primary engine for trends. If no twikit session exists the pipeline falls back to twscrape (currently limited).

## 7. Get User Data

```bash
# Profile only
python cli.py user elonmusk

# Profile + tweets
python cli.py user elonmusk --tweets --limit 50

# Don't save to file
python cli.py user elonmusk --no-output
```

Output: `output/users/user_<name>_<timestamp>.json` + `pipeline.db`

## 8. View SQLite Data

```bash
python -c "
import sqlite3
conn = sqlite3.connect('pipeline.db')

print('=== Tweets ===')
for row in conn.execute('SELECT id, text FROM tweets LIMIT 5'):
    print(row)

print('\n=== Results ===')
for row in conn.execute('SELECT operation, count, success FROM results LIMIT 5'):
    print(row)

conn.close()
"
```

Common queries:
```sql
-- Distinct tweet count
SELECT COUNT(DISTINCT id) FROM tweets;

-- Results by engine
SELECT source_engine, COUNT(*), SUM(success) FROM results GROUP BY source_engine;

-- Recent failures
SELECT operation, query, error FROM results WHERE success = 0 ORDER BY timestamp DESC LIMIT 10;
```

## 9. Account Pooling

### Add Multiple Accounts
```bash
python cli.py login user1 --password "..." --email "..."
python cli.py login user2 --password "..." --email "..."
python cli.py login user3 --password "..." --email "..."
```

After logging in, both engines automatically discover available accounts.

### Check Account Health
```bash
# twscrape pool status (via status command)
python cli.py status

# SQLite stats
sqlite3 accounts.db "SELECT username, active, failed_requests, total_requests FROM accounts;"
```

Accounts that hit rate limits or auth errors are **automatically locked** for a cooldown period. Locked accounts are skipped during scraping.

## 10. Re-Login When Necessary

Re-authenticate when:
- Logs show `unauthorized`, `401`, `forbidden`, or `Authentication` errors
- `python cli.py status` shows all engines unavailable
- Twitter sessions expire (typically every 2–4 weeks)

```bash
python cli.py login <username>
```

The engine automatically overwrites old session data.

## 11. Output Structure

```
output/
├── pipeline.db                    # SQLite database (tweets, users, trends, results tables)
├── search/
│   └── python_programming_20260407_143000.json
├── trends/
│   └── trending_20260407_143000.json
├── users/
│   └── user_elonmusk_20260407_143000.json
└── cookies_*.json                 # twikit per-account session files
```

### Tweet JSON Structure

Each tweet in the output follows the Twitter API v2 field set:

```json
{
  "id": "1234567890",
  "text": "...",
  "created_at": "...",
  "author_id": "987654321",
  "username": "handle",
  "public_metrics": {
    "retweet_count": 42,
    "reply_count": 10,
    "like_count": 100,
    "quote_count": 5,
    "impression_count": 5000
  },
  "non_public_metrics": {},
  "organic_metrics": {},
  "promoted_metrics": {},
  "attachments": null,
  "community_id": null,
  "context_annotations": [],
  "conversation_id": "1234567890",
  "display_text_range": [0, 80],
  "edit_controls": null,
  "edit_history_tweet_ids": [],
  "entities": { "hashtags": [...] },
  "geo": null,
  "in_reply_to_user_id": null,
  "lang": "en",
  "note_tweet": null,
  "possibly_sensitive": false,
  "reply_settings": "everyone",
  "scopes": null,
  "source": "Twitter Web App",
  "suggested_source_links": [],
  "suggested_source_links_with_counts": {},
  "withheld": null,
  "referenced_tweets": [],
  "source_engine": "twscrape",
  "scraped_at": "2026-04-07T14:30:00"
}
```

## 12. Library Usage (Python API)

```python
import asyncio
from engines import TwscrapeEngine, TwikitEngine
from core import SmartRouter

async def main():
    # Direct engine
    engine = TwscrapeEngine(db_path="accounts.db")
    async for tweet in engine.search("python", limit=10):
        print(tweet.data.get("text"))
    await engine.close()

    # Smart router with fallback
    engines = {
        "twscrape": TwscrapeEngine(db_path="accounts.db"),
        "twikit": TwikitEngine(config={"cookies_path": "config/cookies.json"}),
    }
    router = SmartRouter(engines)
    async for result in router.search("python", limit=10):
        print(result.data.get("text"))
    await router.close_all()

asyncio.run(main())
```

## 13. Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| `No active accounts` | No accounts logged in or all locked | `python cli.py login <username>` |
| `unauthorized` / `401` | Session expired | Re-login |
| `Rate limit` / `429` | Twitter rate-limited the account | Wait 15–60 min, or use proxy |
| `All engines failed` | No valid cookies in any engine | Check `cli.py status`, re-login |
| Trends empty | twikit has no cookie | Log in with `--engines twikit` |
| Connection timeout | Network / proxy issue | Set `TWS_PROXY`, set `TWS_SSL_VERIFY=false` |
