import asyncio
import json
import time
from contextlib import aclosing
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator, Any

import Scrapper.twscrape.twscrape as twscrape
from Scrapper.twscrape.twscrape import API, NoAccountError

from config import settings


class BaseScraper:
    def __init__(self, db_path: str | None = None, proxy: str | None = None, ssl_verify: bool = True):
        self.db_path = db_path or str(settings.DB_PATH)
        self.proxy = proxy or settings.PROXY
        self.ssl_verify = ssl_verify and settings.SSL_VERIFY
        self.api = API(pool=self.db_path, proxy=self.proxy, ssl=self.ssl_verify)
        self.stats = {
            "total_items": 0,
            "errors": 0,
            "rate_limit_waits": 0,
        }

    def _get_output_path(self, category: str, filename: str) -> Path:
        output_dir = settings.OUTPUT_SUBDIRS.get(category, settings.OUTPUT_DIR)
        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir / filename

    def _timestamp(self) -> str:
        return datetime.now().strftime("%Y%m%d_%H%M%S")

    def _slugify(self, text: str) -> str:
        import re
        text = text.lower().strip()
        text = re.sub(r"[^\w\s-]", "", text)
        text = re.sub(r"[\s_-]+", "_", text)
        text = text[:50]
        return text

    async def _gather_safe(self, generator: AsyncGenerator, limit: int = -1) -> list:
        items = []
        try:
            async for item in generator:
                items.append(item.dict() if hasattr(item, "dict") else item)
                if limit > 0 and len(items) >= limit:
                    break
        except NoAccountError:
            self.stats["rate_limit_waits"] += 1
            twscrape.logger.warning("No account available, waiting...")
            await asyncio.sleep(5)
        except Exception as e:
            self.stats["errors"] += 1
            twscrape.logger.error(f"Error during gathering: {type(e).__name__}: {e}")
        return items

    async def gather_and_save(
        self,
        generator: AsyncGenerator,
        output_path: Path,
        limit: int = -1,
    ) -> list:
        items = await self._gather_safe(generator, limit)
        if items:
            self._save_json(items, output_path)
            self.stats["total_items"] += len(items)
        return items

    def _save_json(self, data: Any, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        count = len(data) if isinstance(data, (list, dict)) else 1
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        twscrape.logger.info(f"Saved {count} items to {path.name}")

    def _load_json(self, path: Path) -> Any:
        if path.exists():
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        return None

    def get_stats(self) -> dict:
        return self.stats.copy()

    def print_stats(self) -> None:
        twscrape.logger.info(
            f"Scraper stats: items={self.stats['total_items']}, "
            f"errors={self.stats['errors']}, rate_limit_waits={self.stats['rate_limit_waits']}"
        )
