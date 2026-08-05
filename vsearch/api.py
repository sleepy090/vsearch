from __future__ import annotations

import html
import re
import time
from urllib.parse import quote

import requests

from . import config
from .scoring import enrich_query, is_bad_result, result_score, year_from_title

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


def _item_title(item):
    return str(
        item.get("title")
        or item.get("name")
        or item.get("fulltitle")
        or item.get("webpage_url")
        or item
    )


def _item_duration(item):
    try:
        d = item.get("duration")
        if d is None:
            return None
        return int(float(d))
    except (TypeError, ValueError):
        return None


def _item_url(item):
    url = item.get("video_url") or item.get("html_url") or item.get("url")
    if not url and item.get("id"):
        url = f"https://rutube.ru/video/{item.get('id')}/"
    return url


def filter_results(query, items, *, strict=True, min_seconds=None):
    """score-фильтрация и сортировка результатов."""
    if not isinstance(items, list):
        return items
    min_seconds = min_seconds or int(config.load_settings().get("min_duration_minutes", 40)) * 60
    scored = []
    for item in items:
        title = _item_title(item)
        if is_bad_result(title, query=query, strict=strict):
            continue
        duration = _item_duration(item)
        if strict and duration is not None and duration < min_seconds:
            continue
        if not _item_url(item):
            continue
        scored.append((result_score(query, title, duration), item))
    if not scored:
        return []
    scored.sort(key=lambda x: x[0], reverse=True)
    return [item for _, item in scored]


def search_rutube_scored(api, cache, query, *, sort="rank", pages=1, per_page=30, strict=True):
    """Поиск по Rutube с оценкой и фильтрацией."""
    final = enrich_query(query, strict=strict)
    seen = {}
    for page in range(1, pages + 1):
        data = search_cached(
            api, cache, final, sort=sort, page=page, per_page=per_page, duration="long"
        )
        for item in data.get("results", []):
            seen[item["id"]] = item
        if not data.get("has_next"):
            break
    return filter_results(query, list(seen.values()), strict=strict)


def _is_seriesish(query):
    q = query.lower()
    return any(x in q for x in ("сезон", "серия", "season", "episode", "s0", "e0"))


def search_vk_video(query, limit=10):
    """Best-effort VK Video поиск через m.vkvideo.ru."""
    q = str(query).strip()
    if not q:
        return []
    url = "https://m.vkvideo.ru/?action=search&q=" + quote(q)
    try:
        resp = requests.get(
            url,
            timeout=12,
            headers={
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) vsearch",
                "Accept-Language": "ru,en;q=0.8",
            },
        )
        resp.raise_for_status()
        text = resp.text
    except requests.RequestException:
        return []

    found = []
    seen = set()
    patterns = [
        r'href=["\'](?P<href>(?:https?://(?:m\.)?vkvideo\.ru)?/video[^"\']+)["\']',
        r'href=["\'](?P<href>(?:https?://(?:m\.)?vk\.com)?/video[^"\']+)["\']',
    ]
    for pat in patterns:
        for m in re.finditer(pat, text, flags=re.I):
            href = html.unescape(m.group("href"))
            href = href.split("&amp;")[0]
            if href.startswith("/"):
                href = "https://vkvideo.ru" + href
            elif "m.vkvideo.ru" in href:
                href = href.replace("https://m.vkvideo.ru", "https://vkvideo.ru")
            href = href.split("?")[0] if "/video" in href else href
            if href in seen:
                continue
            seen.add(href)

            start = max(0, m.start() - 600)
            end = min(len(text), m.end() + 1200)
            chunk = text[start:end]
            title = None
            for tpat in (
                r'title=["\']([^"\']{3,180})["\']',
                r'aria-label=["\']([^"\']{3,180})["\']',
                r'alt=["\']([^"\']{3,180})["\']',
                r'<span[^>]*>([^<]{3,180})</span>',
            ):
                tm = re.search(tpat, chunk, flags=re.I | re.S)
                if tm:
                    title = re.sub(r"\s+", " ", html.unescape(tm.group(1))).strip()
                    break
            if not title:
                title = f"VK Video результат {len(found) + 1}"
            found.append({
                "title": title,
                "video_url": href,
                "duration": None,
                "source": "vk",
            })
            if len(found) >= limit:
                break
        if len(found) >= limit:
            break
    return found


def staged_search(api, cache, query, *, strict=True, pages=1):
    """Rutube (strict) -> VK -> Rutube (loose). Возвращает отфильтрованный список."""
    if _is_seriesish(query):
        return search_rutube_scored(api, cache, query, pages=pages, strict=False)

    movies = search_rutube_scored(api, cache, query, pages=pages, strict=strict)
    if movies:
        return movies
    if not strict:
        return []

    vk = search_vk_video(query)
    if vk:
        return vk

    return search_rutube_scored(api, cache, query, pages=pages, strict=False)


def to_display_items(movies: list[dict]) -> list[dict]:
    """Привести список к единому виду для отображения."""
    out = []
    for m in movies:
        if m.get("source") == "vk":
            out.append(m)
            continue
        title = _item_title(m)
        out.append({
            "id": m.get("id"),
            "title": title,
            "video_url": _item_url(m),
            "duration": _item_duration(m),
            "hits": m.get("hits"),
            "year": year_from_title(title),
            "description": m.get("description") or "",
            "author": (m.get("author") or {}).get("name") or "",
        })
    return out
