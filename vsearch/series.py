from __future__ import annotations

from datetime import datetime

from . import config


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def load() -> list[dict]:
    data = config.load_json(config.SERIES_FILE, [])
    return data if isinstance(data, list) else []


def save(data: list[dict]) -> None:
    config.save_json(config.SERIES_FILE, data)


def _find_index(title: str) -> int | None:
    q = config._key(title)
    data = load()
    for i, item in enumerate(data):
        name = config._key(item.get("title", ""))
        if q == name or q in name or name in q:
            return i
    return None


def add(title: str, season: int = 1, episode: int = 1) -> bool:
    data = load()
    if _find_index(title) is not None:
        return False
    data.append({
        "title": title,
        "season": int(season),
        "episode": int(episode),
        "watched": 0,
        "added_at": _now(),
        "last_watched_at": None,
        "template": "{title} {season} сезон {episode} серия",
    })
    save(data)
    return True


def remove(title: str) -> str | None:
    data = load()
    idx = _find_index(title)
    if idx is None:
        return None
    item = data.pop(idx)
    save(data)
    return item["title"]


def set_progress(title: str, season: int, episode: int) -> str | None:
    data = load()
    idx = _find_index(title)
    if idx is None:
        return None
    data[idx]["season"] = int(season)
    data[idx]["episode"] = int(episode)
    save(data)
    return data[idx]["title"]


def mark_done(title: str) -> str | None:
    data = load()
    idx = _find_index(title)
    if idx is None:
        return None
    item = data[idx]
    item["watched"] = int(item.get("watched", 0)) + 1
    item["last_watched_at"] = _now()
    item["episode"] = int(item.get("episode", 1)) + 1
    save(data)
    return data[idx]["title"]


def episode_query(title: str) -> str:
    item = load()[_find_index(title)]
    season = int(item.get("season", 1))
    episode = int(item.get("episode", 1))
    template = item.get("template", "{title} {season} сезон {episode} серия")
    return template.format(
        title=item["title"], season=season, episode=episode, s=season, e=episode
    )


def next_query() -> tuple[str, str] | None:
    """Вернуть (title, query) следующей серии первого сериала."""
    data = load()
    if not data:
        return None
    return data[0]["title"], episode_query(data[0]["title"])


def query_for_index(num: int) -> tuple[str, str] | None:
    data = load()
    if not 1 <= num <= len(data):
        return None
    return data[num - 1]["title"], episode_query(data[num - 1]["title"])
