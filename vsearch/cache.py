from __future__ import annotations

import hashlib
import json
import os
import time

DEFAULT_ROOT = os.path.join(
    os.environ.get("XDG_CACHE_HOME", os.path.join(os.path.expanduser("~"), ".cache")),
    "vsearch",
)


def _key(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:16]


class Cache:
    def __init__(self, ttl: int = 3600, root: str = DEFAULT_ROOT):
        self.ttl = ttl
        self.root = root
        os.makedirs(root, exist_ok=True)

    def _path(self, url: str) -> str:
        return os.path.join(self.root, _key(url) + ".json")

    def get(self, url: str):
        path = self._path(url)
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            if data["ts"] + self.ttl < time.time():
                return None
            return data["value"]
        except (OSError, KeyError, ValueError):
            return None

    def put(self, url: str, value):
        path = self._path(url)
        tmp = path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"ts": time.time(), "value": value}, f, ensure_ascii=False)
            os.replace(tmp, path)
        except OSError:
            pass

    def clear(self):
        for name in os.listdir(self.root):
            if name.endswith(".json"):
                try:
                    os.remove(os.path.join(self.root, name))
                except OSError:
                    pass