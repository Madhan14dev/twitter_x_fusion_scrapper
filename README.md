# Twitter Scraping Pipeline

<p align="center">
  <a href="https://github.com/yourusername/twitter-scraper-pipeline/actions/workflows/ci.yml">
    <img src="https://img.shields.io/github/actions/status/yourusername/twitter-scraper-pipeline/ci?style=flat-square" alt="CI">
  </a>
</p>

A production-ready Twitter/X scraping pipeline that combines **twscrape** and **twikit** engines with automatic fallback, smart routing, circuit breakers, and adaptive rate limiting.

## ✨ Features

- **🔄 Automatic Fallback**: Switches between twscrape and twikit seamlessly when one fails
- **🛡️ Circuit Breaker**: Temporarily disables failing engines to prevent cascade failures
- **⚡ Adaptive Rate Limiting**: Smart throttling with exponential backoff and jitter
- **📊 Unified Data Models**: Standardized output format (Twitter API v2 structure)
- **💾 Dual Output**: JSON files + SQLite database for persistence
- **🔐 Programmatic Login**: No more manual cookie extraction — log in directly from the CLI
- **🧑‍💼 Account Pooling**: Manage multiple Twitter accounts with automatic rotation and health tracking
- **🐳 Production Ready**: Comprehensive logging, error handling, and status monitoring

## 📋 Prerequisites

| Requirement | Version |
|-------------|---------|
| Python | 3.11+ |
| pip | 22.0+ |
| OS | Windows, macOS, Linux |

### Required for twscrape (Basic)
- At least one Twitter/X account (username + password + email) for login
- Network access to x.com and api.x.com

### Required for twikit (Advanced/Trends)
- twikit library installed
- Valid Twitter/X authentication cookies or programmatic login

## 🚀 Quick Start

### 1. Clone and Install

```bash
# Clone repository
git clone https://github.com/yourusername/twitter-scraper-pipeline.git
cd twitter-scraper-pipeline

# Create virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# or
.venv\Scripts\activate   # Windows

# Install core dependencies
pip install -r requirements.txt

# Install twikit for extended features
pip install twikit
```

### 2. Log In

No need to manually extract cookies from your browser. Log in directly:

```bash
# Interactive login (prompts for password and email)
python cli.py login your_username

# Fully non-interactive
python cli.py login your_username --password "your_password" --email "your_email@example.com"

# With MFA / TOTP (if the account has 2FA)
python cli.py login your_username --password "pwd" --email "email@example.com" --mfa "ABC123"
```

The login command authenticates against one or both engines and persists sessions:
- **twscrape**: sessions saved to `accounts.db` (automatic account pool)
- **twikit**: per-account cookie files saved to `output/cookies_<username>.json`

When you run scraping commands afterwards, accounts are automatically rotated from the pool.

### 3. Run Your First Scraping

```bash
# Search for tweets
python cli.py search "artificial intelligence" --limit 50

# Get trends (requires twikit)
python cli.py trends --categories trending news

# Get user data
python cli.py user elonmusk --tweets

# Check pipeline status
python cli.py status
```

## 📖 CLI Commands

### Login

```bash
# Interactive login (will prompt for missing credentials)
python cli.py login <username>

# Non-interactive login
python cli.py login <username> --password "..." --email "..."

# Authenticate against both engines
python cli.py login <username> --engines twscrape twikit

# Authenticate against twscrape only
python cli.py login <username> --engines twscrape
```

| Option | Description | Default |
|--------|-------------|---------|
| `--password` | Account password | prompted |
| `--email` | Account email | prompted |
| `--mfa` | MFA / TOTP secret | none |
| `--engines` | Engines to authenticate with | twscrape twikit |

### Search

```bash
# Single query
python cli.py search "python programming" --limit 100

# Multiple queries
python cli.py search "AI" "machine learning" "data science" --limit 50

# Latest tab (default)
python cli.py search "test" --limit 20
```

### Trends

```bash
# All categories
python cli.py trends

# Specific categories
python cli.py trends --categories trending news sport entertainment --limit 20
```

### User

```bash
# Get user profile
python cli.py user elonmusk

# Get user profile + tweets
python cli.py user elonmusk --tweets --limit 100
```

### Options

| Option | Description | Default |
|--------|-------------|---------|
| `--engines` | Engines to use (twscrape twikit) | both |
| `--log-level` | Logging level (DEBUG, INFO, WARNING, ERROR) | INFO |
| `--limit` | Items to fetch per query | 100 |
| `--no-output` | Don't save to file | false |
| `--proxy` | HTTP proxy URL | none |

## ⚙️ Configuration

### Environment Variables

Create a `.env` file in the project root (see `.env.example`):

```bash
# Proxy (optional)
TWS_PROXY=http://127.0.0.1:8080

# SSL (disable if using proxy with SSL inspection)
TWS_SSL_VERIFY=true

# Logging
LOG_LEVEL=INFO
```

### Settings File

Edit `config/settings.py` for advanced configuration:

```python
# Engine settings
twscrape:
  timeout: 30
  retries: 3
  circuit_breaker_threshold: 5

twikit:
  timeout: 30
  retries: 3
  circuit_breaker_threshold: 5

# Rate limiting
rate_limit:
  requests_per_minute: 60
  requests_per_hour: 500
  adaptive_enabled: true
  backoff_base: 2.0
  max_backoff: 300
```

## 📁 Project Structure

```
twitter-scraper-pipeline/
├── cli.py                     # Main CLI entry point
├── config/
│   ├── settings.py            # Configuration management
│   ├── queries.json           # Pre-defined queries
│   └── targets.json           # Target users/hashtags
├── engines/
│   ├── base.py                # Abstract engine interface
│   ├── twscrape_engine.py     # twscrape adapter
│   ├── twikit_engine.py       # twikit adapter
│   └── guest_engine.py        # Guest/anonymous access
├── core/
│   ├── smart_router.py       # Fallback routing & circuit breaker
│   ├── account_manager.py    # Account pool management
│   ├── rate_limiter.py       # Adaptive throttling
│   └── error_handler.py       # Error classification & retry
├── models/
│   ├── tweet.py               # Unified tweet model (Twitter API v2)
│   ├── user.py                # Unified user model
│   └── trend.py               # Unified trend model
├── output/
│   └── pipeline.py           # JSON + SQLite output
├── requirements.txt           # Python dependencies
├── README.md                  # This file
└── .gitignore                 # Git ignore rules
```

## 🔌 Engine Priority

| Operation | Primary | Fallback | Notes |
|-----------|---------|----------|-------|
| search | twscrape | twikit | Fast, reliable |
| trends | twikit | - | twscrape API broken |
| user_tweets | twscrape | twikit | Get user timeline |
| user_by_login | twscrape | twikit | Profile lookup |
| tweet_details | twscrape | twikit | Single tweet |
| followers | twscrape | twikit | Follower list |
| following | twscrape | twikit | Following list |

## 🔒 Security

- **Programmatic login**: Accounts authenticate directly via CLI — no browser cookie extraction needed
- **Session persistence**: twscrape uses `accounts.db` (SQLite), twikit uses per-account JSON cookie files
- **Account pooling**: Multiple accounts are automatically rotated and health-tracked
- **Use environment variables**: Store sensitive data in `.env`
- **Rotate credentials regularly**: Twitter sessions expire; re-login when needed
- **Use proxy for large-scale**: Prevents IP blocks

## 🐛 Troubleshooting

### "No active accounts" Error
```bash
# Reset account locks
python -c "import sqlite3; conn = sqlite3.connect('output/accounts.db'); conn.execute('UPDATE accounts SET locks = \"{}\"'); conn.commit()"
```

### Trends returning empty
- Trends API requires twikit with valid cookies
- twscrape trends are currently broken (Twitter API changes)

### Rate Limiting
- Wait for cooldown period (15 min - 1 hour)
- Use proxy: `--proxy http://your-proxy:port`
- Enable adaptive backoff in settings

### Connection Timeout
- Check network access to x.com
- Verify proxy settings if using one
- Disable SSL verification for corporate proxies: `TWS_SSL_VERIFY=false`

## 📊 Output

### JSON Files
```
output/
├── search/
│   └── ai_news_20240406_123456.json
├── users/
│   └── user_elonmusk_20240406_123456.json
└── trends/
    └── trending_20240406_123456.json
```

### SQLite Database
```sql
-- View scraped data
SELECT * FROM tweets LIMIT 10;
SELECT * FROM users LIMIT 10;
SELECT * FROM trends;

-- View operation results
SELECT * FROM results;
```

## 🧩 Using as a Library

```python
import asyncio
from engines import TwscrapeEngine
from core import SmartRouter

async def main():
    # Create engine
    engine = TwscrapeEngine(db_path="output/accounts.db")

    # Use directly
    async for tweet in engine.search("python", limit=10):
        print(tweet.data)

    await engine.close()

asyncio.run(main())
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes and add tests
4. Run linting: `make lint`
5. Submit a pull request

## 📝 License

MIT License - see [LICENSE](LICENSE) for details.

## 🙏 Acknowledgments

- [twscrape](https://github.com/vladkens/twscrape) - Fast Twitter API client
- [twikit](https://github.com/d60/twikit) - Modern Twitter/X client
