"""On-disk cache for research artifacts, so reruns and --from-step cost no research tokens.

Layout (per company):  outputs/<slug>/cache/{search,pages,facts}/<sha1(key)>.json
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


class DiskCache:
    def __init__(self, root: Path, enabled: bool = True):
        self.root = root
        self.enabled = enabled
        self.hits = 0
        self.misses = 0

    @staticmethod
    def key(*parts: str) -> str:
        return hashlib.sha1("\x1f".join(parts).encode("utf-8")).hexdigest()

    def _path(self, bucket: str, key: str) -> Path:
        return self.root / bucket / f"{self.key(key)}.json"

    def get(self, bucket: str, key: str) -> Any | None:
        if not self.enabled:
            return None
        path = self._path(bucket, key)
        if not path.exists():
            self.misses += 1
            return None
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.misses += 1
            return None
        self.hits += 1
        return value

    def set(self, bucket: str, key: str, value: Any) -> None:
        path = self._path(bucket, key)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)
