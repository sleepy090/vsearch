from __future__ import annotations

import random
import re

from . import config

_YEAR_RE = re.compile(r"\b(19[0-9]{2}|20[0-2][0-9])\b")

_GOOD_WORDS = [
    "фильм", "полный фильм", "кино", "movie", "full movie", "film",
    "1080p", "720p", "2160p", "4k", "bdrip", "hdrip", "webrip",
    "web-dl", "blu-ray", "bluray", "смотреть онлайн", "реж.",
    "режиссер", "режиссёр", "4к",
]

_BAD_WORDS = [
    "заставка", "интро", "intro", "опенинг", "opening", "эндинг",
    "ending", "трейлер", "trailer", "тизер", "teaser", "обзор",
    "review", "reaction", "реакция", "разбор", "пересказ", "recap",
    "explained", "нарезка", "фрагмент", "отрывок", "scene", "clip",
    "эдит", "edit", "amv", "shorts", "#shorts", "клип", "клипы",
    "ost", "soundtrack", "score", "theme", "main theme", "lyrics",
    "instrumental", "remix", "cover", "music video", "official video",
    "прохождение", "gameplay", "walkthrough", "летсплей", "letsplay",
    "let's play", "стрим", "stream", "игрофильм", "аудиокнига",
    "аудиокниги", "озвучка", "мод", "модификация", "anomaly", "gamma",
    "stalker 2", "s.t.a.l.k.e.r", "сердце чернобыля", "heart of chornobyl",
    "shadow of chernobyl", "зов припяти", "чистое небо", "100 дней",
    "behind the scenes", "making of", "интервью", "tiktok", "tik tok",
    "подборка", "все части", "серия 1", "badcomedian", "киногрехи",
    "стетхэм", "дорама", "мультфильм", "сериал",
]

_STALKER_GAME = [
    "stalker 2", "s.t.a.l.k.e.r", "сердце чернобыля", "heart of chornobyl",
    "shadow of chernobyl", "зов припяти", "чистое небо", "anomaly",
    "gamma", "мод", "игрофильм",
]

_STALKER_MOVIE = ["1979", "тарковский", "1979: "]


def norm(text) -> str:
    return " ".join(str(text).strip().split())


def key(text) -> str:
    return norm(text).lower().replace("ё", "е")


def year_from_title(title: str) -> int | None:
    m = _YEAR_RE.search(str(title or ""))
    return int(m.group(1)) if m else None


def hints_for(query: str) -> list[str]:
    q = key(query)
    hints = config.load_movie_hints()
    for title_key, values in hints.items():
        if q == title_key or title_key in q or q in title_key:
            return values
    return []


def year_from_hints(query: str) -> int | None:
    for hint in hints_for(query):
        if str(hint).isdigit() and len(str(hint)) == 4:
            return int(hint)
    return None


def enrich_query(query: str, strict: bool = True) -> str:
    """Добавить к запросу год/фильм из подсказок, чтобы Rutube нашёл лучше."""
    q = norm(query)
    if not q:
        return q
    hints = hints_for(q)
    year = next((h for h in hints if h.isdigit() and len(h) == 4), None)
    if strict and "фильм" not in key(q) and not _is_series_query(q):
        if year and year not in q:
            return f"{q} фильм {year}"
        return f"{q} фильм"
    return q


def is_bad_result(title: str, query: str = "", strict: bool = True) -> bool:
    low = str(title or "").lower()
    q = key(query)
    words = list(config.load_bad_words())
    if strict:
        words += _BAD_WORDS
    if "сталкер" in q:
        words += _STALKER_GAME
    return any(w in low for w in words)


def result_score(movie_query: str, video_title: str, duration: int | None) -> int:
    q = key(movie_query)
    t = key(video_title)
    hints = hints_for(movie_query)
    score = 0

    if q == t:
        score += 100
    elif q in t:
        score += 65

    q_words = [w for w in q.split() if len(w) > 2]
    matched = sum(1 for w in q_words if w in t)
    score += matched * 6
    if q_words and matched == len(q_words):
        score += 25

    for hint in hints:
        h = key(hint)
        if h and h in t:
            score += 90 if hint.isdigit() and len(hint) == 4 else 35

    for w in _GOOD_WORDS:
        if key(w) in t:
            score += 8

    if duration:
        if duration >= 60 * 60:
            score += 45
        elif duration >= 40 * 60:
            score += 10
        elif duration > 0:
            score -= 80
    else:
        score -= 5

    for w in _BAD_WORDS:
        if w in t:
            score -= 160

    if "сталкер" in q:
        if any(w in t for w in _STALKER_GAME):
            score -= 250
        if any(w in t for w in _STALKER_MOVIE):
            score += 150

    return score


def movie_quote(query: str) -> str:
    q = key(query)
    quotes = config.load_quotes()
    for k, lines in quotes.items():
        if k == "_generic":
            continue
        kk = key(k)
        if kk and (kk in q or q in kk) and lines:
            return random.choice(lines)
    return random.choice(quotes.get("_generic", ["🎬 Ищу фильм."]))


def _is_series_query(query: str) -> bool:
    q = key(query)
    markers = [
        "сезон", "серия", "series", "сериал", "doctor who", "доктор кто",
        "симпсоны", "футурама", "рик и морти", "южный парк",
        "гравити фолз", "время приключений", "s01", "e01", "эпизод",
    ]
    return any(x in q for x in markers)


def is_series_query(query: str) -> bool:
    return _is_series_query(query)


def year_extract(text) -> int | None:
    m = re.search(r"\b(19[0-9]{2}|20[0-2][0-9])\b", str(text))
    return int(m.group(1)) if m else None
