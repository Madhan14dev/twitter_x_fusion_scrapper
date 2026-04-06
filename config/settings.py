import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).parent.parent.resolve()

# Load environment variables from .env if exists
_env_file = BASE_DIR / ".env"
if _env_file.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(_env_file)
    except ImportError:
        pass  # python-dotenv not installed, continue without it


@dataclass
class EngineConfig:
    enabled: bool = True
    max_accounts: int = 10
    timeout: int = 30
    retries: int = 3
    retry_delay: int = 5
    circuit_breaker_threshold: int = 5
    circuit_breaker_timeout: int = 300


@dataclass
class RateLimitConfig:
    requests_per_minute: int = 60
    requests_per_hour: int = 500
    adaptive_enabled: bool = True
    backoff_base: float = 2.0
    max_backoff: int = 300


@dataclass
class OutputConfig:
    format: str = "json"
    directory: Path = BASE_DIR / "output"
    db_path: Path = BASE_DIR / "pipeline.db"
    compress: bool = False
    pretty_print: bool = True


@dataclass
class Settings:
    base_dir: Path = field(default=BASE_DIR)
    log_level: str = "INFO"
    
    # Output
    output: OutputConfig = field(default_factory=OutputConfig)
    
    # Engine configurations
    twscrape: EngineConfig = field(default_factory=EngineConfig)
    twikit: EngineConfig = field(default_factory=EngineConfig)
    guest: EngineConfig = field(default_factory=EngineConfig)
    
    # Rate limiting
    rate_limit: RateLimitConfig = field(default_factory=RateLimitConfig)
    
    # Proxy settings
    proxy: str | None = field(default_factory=lambda: os.getenv("TWS_PROXY"))
    ssl_verify: bool = field(default_factory=lambda: os.getenv("TWS_SSL_VERIFY", "true").lower() != "false")
    
    # Default scraping parameters
    default_limit: int = 100
    batch_size: int = 100
    
    # Config files
    config_dir: Path = field(default=BASE_DIR / "config")
    queries_file: Path = field(default=BASE_DIR / "config" / "queries.json")
    targets_file: Path = field(default=BASE_DIR / "config" / "targets.json")
    accounts_file: Path = field(default=BASE_DIR / "config" / "accounts.json")
    
    # Output subdirectories
    output_subdirs: dict = field(default_factory=lambda: {
        "search": BASE_DIR / "output" / "search",
        "users": BASE_DIR / "output" / "users",
        "tweets": BASE_DIR / "output" / "tweets",
        "trends": BASE_DIR / "output" / "trends",
    })
    
    def __post_init__(self):
        self.output.directory.mkdir(parents=True, exist_ok=True)
        self.output.db_path.parent.mkdir(parents=True, exist_ok=True)
        for subdir in self.output_subdirs.values():
            subdir.mkdir(parents=True, exist_ok=True)
    
    def to_dict(self) -> dict[str, Any]:
        result = {}
        for key, value in self.__dict__.items():
            if isinstance(value, (EngineConfig, RateLimitConfig, OutputConfig)):
                result[key] = vars(value)
            elif isinstance(value, Path):
                result[key] = str(value)
            else:
                result[key] = value
        return result


settings = Settings()