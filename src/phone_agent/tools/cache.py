import hashlib
import json
import os
from pathlib import Path
from typing import Optional


class PageCache:
    """Simple on-disk page cache.

    Cache key: sha256(url)[:16]
    Stores {key}.md and {key}.meta.json per URL.
    """

    def __init__(self, cache_dir: str = ".cache/pages") -> None:
        self.base = Path(cache_dir)
        self.base.mkdir(parents=True, exist_ok=True)

    def key(self, url: str) -> str:
        return hashlib.sha256(url.encode("utf-8", errors="replace")).hexdigest()[:16]

    def get(self, url: str) -> Optional[str]:
        k = self.key(url)
        md_path = self.base / f"{k}.md"
        if md_path.exists():
            return md_path.read_text(encoding="utf-8", errors="replace")
        return None

    def put(self, url: str, markdown: str) -> None:
        k = self.key(url)
        md_path = self.base / f"{k}.md"
        meta_path = self.base / f"{k}.meta.json"
        md_path.write_text(markdown, encoding="utf-8")
        meta_path.write_text(
            json.dumps({"url": str(md_path), "chars": len(markdown)}),
            encoding="utf-8",
        )