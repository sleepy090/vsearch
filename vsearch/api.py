from __future__ import annotations

import time
from urllib.parse import quote

import requests

BASE = "https://rutube.ru/api"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64; rv:126.0) "
        "Gecko/20100101 Firefox/126.0"
    ),
    "Accept": "application/json",
}


class RutubeError(Exception):
    pass


class Rutube:
    def __init__(self, session=None, retries=3, backoff=1.0, timeout=15):
        self.session = session or requests.Session()
        self.retries = retries
        self.backoff = backoff
        self.timeout = timeout

    def _get(self, path, params):
        params.setdefault("format", "json")
        first_url = f"{BASE}{path}"
        last = None
        for attempt in range(self.retries):
            try:
                resp = self.session.get(
                    first_url, params=params, headers=HEADERS, timeout=self.timeout
                )
                resp.raise_for_status()
                return resp.json()
            except (requests.RequestException, ValueError) as exc:
                last = exc
                if attempt < self.retries - 1:
                    time.sleep(self.backoff * (2**attempt))
        raise RutubeError(f"запрос не удался: {last}")

    def search(self, query, *, sort="rank", page=1, per_page=20, duration=None):
        params = {
            "query": query,
            "sort": sort,
            "page": page,
            "per_page": per_page,
        }
        if duration:
            params["filter"] = f"duration:{duration}"
        return self._get("/search/video/", params)

    def video(self, video_id):
        return self._get(f"/video/{video_id}/", {})


def _cache_url(query, sort, page, per_page, duration):
    url = f"/search/video/?query={quote(query)}&sort={sort}&page={page}&per_page={per_page}&format=json"
    if duration:
        url += f"&filter=duration:{duration}"
    return url


def search_cached(api, cache, query, *, sort="rank", page=1, per_page=30, duration="long"):
    url = _cache_url(query, sort, page, per_page, duration)
    data = cache.get(url)
    if data is None:
        data = api.search(
            query, sort=sort, page=page, per_page=per_page, duration=duration
        )
        cache.put(url, data)
    return data