from __future__ import annotations

from datetime import datetime

from . import config


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def load() -> list[dict]:
    data = config.load_json(config.WATCHLIST_FILE, [])
    return data if isinstance(data, list) else []


def save(data: list[dict]) -> None:
    config.save_json(config.WATCHLIST_FILE, data)


def unwatched() -> list[dict]:
    return [x for x in load() if not x.get("watched")]


def watched() -> list[dict]:
    return [x for x in load() if x.get("watched")]


def add_movies(raw: str) -> int:
    db = load()
    existing = {x["title"].lower() for x in db}
    movies = [config.norm(x) for x in raw.replace("\n", "/").split("/") if config.norm(x)]
    added = 0
    for movie in movies:
        if movie.lower() in existing:
            continue
        db.append({
            "title": movie,
            "watched": False,
            "added_at": _now(),
            "watched_at": None,
            "rating": None,
        })
        existing.add(movie.lower())
        added += 1
    save(db)
    return added


def mark_done(num: int, rating: int | None = None) -> str | None:
    items = unwatched()
    if not 1 <= num <= len(items):
        return None
    item = items[num - 1]
    item["watched"] = True
    item["watched_at"] = _now()
    if rating is not None:
        item["rating"] = rating
    save(load())
    return item["title"]


def rate(num: int, rating: int) -> str | None:
    items = watched()
    if not 1 <= num <= len(items):
        return None
    item = items[num - 1]
    item["rating"] = rating
    save(load())
    return item["title"]


def stats() -> dict:
    db = load()
    done = len(watched())
    rated = [x for x in db if x.get("rating")]
    avg = round(sum(int(x["rating"]) for x in rated) / len(rated), 2) if rated else None
    return {
        "total": len(db),
        "done": done,
        "left": len(db) - done,
        "rated": len(rated),
        "avg": avg,
        "percent": round(done / len(db) * 100, 1) if db else 0,
    }


def clear() -> None:
    save([])
