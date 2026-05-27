import json
import logging
import os
from typing import Any, Dict


class CacheStore:
    def __init__(self, path: str) -> None:
        self.path = path

    def load(self) -> Dict[str, Any]:
        if not os.path.exists(self.path):
            return {}

        try:
            with open(self.path, "r", encoding="utf-8") as cache_file:
                return json.load(cache_file)
        except json.JSONDecodeError:
            logging.warning("Cache is corrupted. Creating a new one.")
            return {}

    def save(self, cache: Dict[str, Any]) -> None:
        with open(self.path, "w", encoding="utf-8") as cache_file:
            json.dump(cache, cache_file, indent=4, ensure_ascii=False)
