from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple


class Cache:
    def __init__(self, ttl_seconds: int = 60) -> None:
        self.ttl_seconds = ttl_seconds
        self._cache: Dict[Tuple[str, str, int], Dict[str, Any]] = {}

    def get(self, key: Tuple[str, str, int]) -> Optional[Dict[str, Any]]:
        value = self._cache.get(key)
        if not value:
            return None
        if datetime.utcnow() - value["timestamp"] > timedelta(seconds=self.ttl_seconds):
            self._cache.pop(key, None)
            return None
        return value["payload"]

    def set(self, key: Tuple[str, str, int], payload: Dict[str, Any]) -> None:
        self._cache[key] = {"timestamp": datetime.utcnow(), "payload": payload}
