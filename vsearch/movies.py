from __future__ import annotations

import re

MIN_MOVIE_SECONDS = 2400

_SKIP_FIELDS = ("is_serial", "is_audio", "is_livestream", "is_paid", "is_deleted")

_RE_TITLE_YEAR = re.compile(r"\(?\s*(1[89]\d\d|20\d\d)\s*\)?")
_RE_GOD = re.compile(r"Год\s*выпуска\s*:?\s*(\d{4})")
_RE_COUNTRY = re.compile(r"Страна\s*:?\s*([^\n]+)")
_RE_GENRES = re.compile(r"Жанр\s*:?\s*([^\n]+)")
_RE_DIRECTOR = re.compile(r"Режисс(?:ер|ёр)\s*:?\s*([^\n]+)")


def _skip_check(item: dict) -> bool:
    return any(item.get(f) for f in _SKIP_FIELDS)


def parse_description(desc: str | None) -> dict:
    parsed = {"year": None, "country": None, "genres": None, "director": None}
    if not desc:
        return parsed
    m = _RE_GOD.search(desc)
    if m:
        parsed["year"] = int(m.group(1))
    m = _RE_COUNTRY.search(desc)
    if m:
        parsed["country"] = m.group(1).strip()
    m = _RE_GENRES.search(desc)
    if m:
        parsed["genres"] = [g.strip() for g in m.group(1).split(",") if g.strip()]
    m = _RE_DIRECTOR.search(desc)
    if m:
        parsed["director"] = m.group(1).strip()
    return parsed


def title_year(title: str | None) -> int | None:
    if not title:
        return None
    m = _RE_TITLE_YEAR.search(title)
    return int(m.group(1)) if m else None


def is_movie(item: dict) -> bool:
    if _skip_check(item):
        return False
    duration = item.get("duration") or 0
    desc = item.get("description") or ""
    if duration >= MIN_MOVIE_SECONDS:
        return True
    if _RE_GOD.search(desc) and _RE_GENRES.search(desc):
        return True
    return False