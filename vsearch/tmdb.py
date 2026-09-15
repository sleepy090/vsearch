from __future__ import annotations

import time

import requests

from . import config

BASE = "https://api.themoviedb.org/3"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64; rv:126.0) "
        "Gecko/20100101 Firefox/126.0"
    )
}

FEEDS = {
    "now": "now_playing",
    "now_playing": "now_playing",
    "popular": "popular",
    "upcoming": "upcoming",
    "top": "top_rated",
    "top_rated": "top_rated",
}

FEED_LABELS = {
    "now_playing": "в кино сейчас",
    "popular": "популярные",
    "upcoming": "скоро",
    "top_rated": "топ рейтинг",
}


class TmdbError(Exception):
    pass


def load_api_key() -> str:
    return str(config.load_settings().get("tmdb_api_key", "")).strip()


class Tmdb:
    def __init__(self, api_key=None, session=None, language="ru-RU", region="RU",
                 timeout=15, retries=2):
        self.api_key = api_key or load_api_key()
        self.session = session or requests.Session()
        self.language = language
        self.region = region
        self.timeout = timeout
        self.retries = retries

    def _get(self, path, params):
        if not self.api_key:
            raise TmdbError(
                "нет API-ключа TMDB. Получи бесплатный ключ на "
                "https://www.themoviedb.org/settings/api и добавь "
                "tmdb_api_key в ~/.config/vsearch/settings.json"
            )
        params = {"api_key": self.api_key, "language": self.language, **params}
        url = f"{BASE}{path}"
        last = None
        for attempt in range(self.retries):
            try:
                resp = self.session.get(
                    url, params=params, headers=HEADERS, timeout=self.timeout
                )
                resp.raise_for_status()
                return resp.json()
            except (requests.RequestException, ValueError) as exc:
                last = exc
                if attempt < self.retries - 1:
                    time.sleep(0.5 * (attempt + 1))
        raise TmdbError(f"TMDB недоступен: {last}")

    def movies(self, feed="now_playing", page=1, limit=20):
        if feed not in FEED_LABELS:
            feed = "now_playing"
        params = {"page": page}
        if feed in ("now_playing", "upcoming", "top_rated"):
            params["region"] = self.region
        data = self._get(f"/movie/{feed}", params)
        results = []
        for m in data.get("results", []):
            results.append(
                {
                    "title": m.get("title") or m.get("original_title") or "",
                    "original_title": m.get("original_title") or "",
                    "year": _year_from_date(m.get("release_date")),
                    "release_date": m.get("release_date") or "",
                    "overview": m.get("overview") or "",
                    "vote_average": float(m.get("vote_average") or 0),
                    "vote_count": int(m.get("vote_count") or 0),
                    "tmdb_id": m.get("id"),
                    "poster": m.get("poster_path") or "",
                }
            )
            if len(results) >= limit:
                break
        return results


def fetch_movies(cache, tmdb, feed="now_playing", page=1, limit=20, ttl=12 * 3600):
    """Кэшированная загрузка списка фильмов TMDB."""
    url = f"tmdb:/movie/{feed}?page={page}&limit={limit}"
    data = cache.get(url)
    if data is None:
        data = tmdb.movies(feed, page=page, limit=limit)
        cache.put(url, data)
    return data


def _year_from_date(date: str) -> int | None:
    try:
        return int(str(date)[:4])
    except (TypeError, ValueError):
        return None
