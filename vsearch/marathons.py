from __future__ import annotations

import importlib.resources as resources
import os
import re

import yaml

from .api import Rutube, search_cached
from .cache import Cache
from .movies import is_movie

_EPISODE_RE = re.compile(r"[Ээ]пизод\s*([\dIVXL]+)")
_YEAR_RE = re.compile(r"\((1[89]\d\d|20\d\d)\)")
_DATE_RE = re.compile(r"\d{1,2}[./-]\d{1,2}[./-]\d{2,4}")
_ROMAN = {
    "i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5, "vi": 6,
    "vii": 7, "viii": 8, "ix": 9, "x": 10, "xi": 11, "xii": 12,
}
_ROMAN_DIGITS = {k: str(v) for k, v in _ROMAN.items()}
_GLOBAL_EXCLUDE = (
    "аудио", "аудиокнига", "пересказ", "обзор", "реакция", "вырезанные",
    "киногрехи", "прохождение", "лего", "трейлер", "тизер", "саундтрек",
    "музыка", "подборка", "все части", "серия 1",
    "badcomedian", "перезалив", "сцены", "саундт", "полная история",
    "режиссервия", "режиссерская версия", "адаптированная", "softradio",
    "код бога", "горяев", "гаряев", "10-04", "13-04", "16-09",
    "зубарев", "смотрит", "стрим", "баба яга", "gtav", "гта",
    "обзор", "разбор", "самый", "шедевр", "выпуск", "minecraft",
    "майнкрафт", "бокс", "тайсон", "усик", "дпг", "затянутый",
    "эфир", "летсплей", "мультфильм", "сериал", "стетхэм", "статхэм",
    "стэтхэм", "джет ли", "смотрим", "идём", "потеря крови", "заброш",
    "инакше", "оговука", "обществознание", "учебник", "бивис", "смысл",
    "полный фильм", "калсакен", "разврат", "песн",
    "эстрад", "советск", "майя", "вепрецкий", "цивилизац", "дорама",
    "лестниц", "часов", "хит", "эдельман", "диалог", "теннис", "трен",
    "жукариен", "обсужден", "эндуро", "соревнован", "награжден",
    "расшифрова", "ужастик", "гузбампс", "вестерн", "боевик", "мощнейш",
    "мощнейший", "проект", "stream", "gameplay", "медвед", "пчелы",
    "легенд", "тилида", "нарезка",
    "letsplay", "let's play", "фрагмент", "отрывок", "кратко", "краткий пересказ",
    "gamma", "клип", "clip", "review", "intro", "ending", "stalker 2",
    "s.t.a.l.k.e.r", "сердце чернобыля", "полное прохождение",
    "short", "shorts", "opening", "объяснение", "топ",
    "shadow of chernobyl", "100 дней", "чистое небо", "интро", "киновселенн",
    "марвелы",
    # игровой мусор, симуляторы, доки
    "simulator", "saloon", "wytchwood", "dangerous", "авианосец", "retro",
    "изучаем", "загадки", "vr", "рыбалк", "эмулятор", "игровой",
    "прохожд", "геймплей", "walkthrough", "видеостор", "store sim",
    "солнец", "зонд", "музык", "swgoh",
    "лучшие моменты", "эдит", "behind the scenes", "за кадром", "anomaly",
    "модификация", "эндинг", "зов припяти", "интервью",
    "заставка", "опенинг", "игрофильм", "score", "main theme", "remix",
    "recap", "explained", "making of", "official video",
    "tiktok", "tik tok", "walkthrough", "lets play", "let s play",
)

CONFIG_HOME = os.environ.get(
    "XDG_CONFIG_HOME", os.path.join(os.path.expanduser("~"), ".config")
)
USER_FILE = os.path.join(CONFIG_HOME, "vsearch", "franchises.yaml")


def load_franchises() -> list[dict]:
    path = USER_FILE if os.path.exists(USER_FILE) else _default_data_path()
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("marathons", [])


def _default_data_path():
    return resources.files("vsearch").joinpath("data", "franchises.yaml")


def norm_title(title: str) -> str:
    t = re.split(r"[/|]", title or "")[0]
    t = re.sub(r"\([^)]*\)", "", t)
    t = re.sub(r"[\s\-—_/:]+", " ", t.lower())
    return t.strip()


def _episode_num(m: dict) -> int | None:
    match = _EPISODE_RE.search(m.get("title", "") or "")
    if not match:
        return None
    token = match.group(1)
    if token.isdigit():
        return int(token)
    return _ROMAN.get(token.lower())


def dedupe_movies(movies: list[dict]) -> list[dict]:
    best: dict[str, dict] = {}
    for m in movies:
        num = _episode_num(m)
        key = f"ep:{num}" if num is not None else f"t:{norm_title(m.get('title', ''))}"
        if key not in best or (m.get("hits") or 0) > (best[key].get("hits") or 0):
            best[key] = m
    return list(best.values())


def _sort_key(m):
    num = _episode_num(m)
    title = (m.get("title") or "").lower()
    return (num if num is not None else 9999, title)


def sort_episodes(movies: list[dict]) -> list[dict]:
    return sorted(movies, key=_sort_key)


def _title_keywords(title: str) -> str:
    t = norm_title(title)
    t = t.replace("звёзд", "звезд")
    t = t.replace("ё", "е")
    return t


def _roman_to_digits(text: str) -> str:
    out = []
    for word in text.split():
        out.append(_ROMAN_DIGITS.get(word, word))
    return " ".join(out)


def _match_key(text: str) -> str:
    """Нормализация для сопоставления частей: ё->е, римские->арабские,
    убираем обёртку «(фильм, 1979)» но оставляем год."""
    t = (text or "").lower()
    t = t.replace("ё", "е")
    t = re.sub(r"\(([^)]*)\)", lambda m: m.group(1), t)
    t = re.sub(r"\b(фильм|мультфильм|сериал)\b", " ", t)
    t = re.sub(r"[^а-яёa-z0-9]+", " ", t)
    return _roman_to_digits(" ".join(t.split()))


def _part_tokens(part: str) -> set[str]:
    return set(_match_key(part).split())


def _title_tokens(m: dict) -> set[str]:
    return set(_match_key(m.get("title", "")).split())


def _split_candidates(pool: list[dict], part: str) -> tuple[list[dict], list[dict]]:
    """(полное совпадение токенов, shared-совпадение). shared игнорирует цифры."""
    tokens = _part_tokens(part)
    if not tokens:
        return [], []
    full, shared = [], []
    for m in pool:
        hay = _title_tokens(m)
        if tokens <= hay:
            full.append(m)
            continue
        common = (tokens & hay) - {t for t in tokens & hay if t.isdigit()}
        if any(len(t) >= 3 for t in common):
            shared.append(m)
    return full, shared


def _is_seq_token(t: str) -> bool:
    """Число-номер сиквела (не год), например 2, 3 в «Матрица 2»."""
    if not t.isdigit():
        return False
    return not (1900 <= int(t) <= 2100)


def _seek(
    pool: list[dict], part: str, used: set[str], fr: dict, *, allow_shared: bool = True
) -> dict | None:
    """Найти фильм под часть: full-совпадение > shared.
    shared: требуем include-фразу и >=2 значимых токена (или имя, если часть короткая)."""
    tokens = _part_tokens(part)
    if not tokens:
        return None
    part_seq = any(_is_seq_token(t) for t in tokens)
    full = [
        m
        for m in pool
        if tokens <= _title_tokens(m)
        and m["id"] not in used
        and not _bad_words(m.get("title", ""), _GLOBAL_EXCLUDE)
        and (
            part_seq
            or not any(_is_seq_token(t) for t in _title_tokens(m))
        )
    ]
    if full:
        full.sort(
            key=lambda m: (
                1 if _passes_filters(m, fr) else 0,
                -(len(_title_tokens(m)) - len(tokens)),
                m.get("hits") or 0,
            ),
            reverse=True,
        )
        return full[0]
    if not allow_shared:
        return None
    words = [t for t in tokens if not t.isdigit()]
    shared = []
    for m in pool:
        if m["id"] in used:
            continue
        if not _passes_filters(m, fr):
            continue
        common = (tokens & _title_tokens(m)) - {t for t in tokens & _title_tokens(m) if t.isdigit()}
        sig = [t for t in common if len(t) >= 3]
        ok = len(sig) >= 2 if len(words) >= 3 else bool(sig)
        if ok:
            shared.append(m)
    if shared:
        return max(shared, key=lambda m: m.get("hits") or 0)
    return None


def _bad_words(title: str, words) -> bool:
    raw = (title or "").lower()
    key = _title_keywords(title)
    if _DATE_RE.search(raw):
        return True
    return any(w in raw or w in key for w in words)


def _loose_filter(m: dict, fr: dict) -> bool:
    """Для точечного поиска части: exclude и стоп-слова, без include-фразы."""
    if not is_movie(m):
        return False
    title = m.get("title", "") or ""
    exclude = [w.replace("ё", "е") for w in fr.get("exclude", [])]
    if exclude and _bad_words(title, exclude):
        return False
    if _bad_words(title, _GLOBAL_EXCLUDE):
        return False
    return True


def _search_part(api: Rutube, cache: Cache, fr: dict, part: str) -> list[dict]:
    seen = {}
    for page in (1, 2):
        data = search_cached(api, cache, part, sort="rank", page=page, per_page=30)
        for item in data.get("results", []):
            if _loose_filter(item, fr):
                seen[item["id"]] = item
        if not data.get("has_next"):
            break
    return list(seen.values())


def _order_by_parts(
    api: Rutube, cache: Cache, movies: list[dict], fr: dict
) -> list[dict]:
    pool = list(movies)
    used: set[str] = set()
    ordered: list[dict] = []
    for part in fr.get("parts", []):
        best = _seek(pool, part, used, fr, allow_shared=False)
        if best is None:
            for m in _search_part(api, cache, fr, part):
                if m["id"] not in pool_ids(pool):
                    pool.append(m)
            best = _seek(pool, part, used, fr, allow_shared=True)
        if best:
            used.add(best["id"])
            ordered.append(best)
    return ordered


def pool_ids(pool: list[dict]) -> set[str]:
    return {m["id"] for m in pool}


def _passes_filters(m: dict, fr: dict) -> bool:
    title = m.get("title", "") or ""
    key = _title_keywords(title)
    include = [w.replace("ё", "е") for w in fr.get("include", [])]
    if include:
        if not any(w in key for w in include):
            return False
    else:
        phrase = _title_keywords(fr.get("query", ""))
        if phrase and phrase not in key:
            return False
    exclude = [w.replace("ё", "е") for w in fr.get("exclude", [])]
    if exclude and _bad_words(title, exclude):
        return False
    if _bad_words(title, _GLOBAL_EXCLUDE):
        return False
    return True


def _marathon_pool(franchise: dict, cache_ttl: int = 24 * 3600) -> list[dict]:
    api = Rutube()
    cache = Cache(ttl=cache_ttl)
    seen = {}
    for page in range(1, 4):
        data = search_cached(
            api, cache, franchise["query"], sort="rank", page=page, per_page=30
        )
        for item in data.get("results", []):
            if is_movie(item) and _passes_filters(item, franchise):
                seen[item["id"]] = item
        if not data.get("has_next"):
            break
    return dedupe_movies(list(seen.values()))


def _dedupe_ordered(ordered: list[dict]) -> list[dict]:
    def key(m: dict) -> str:
        return " ".join(
            t
            for t in _match_key(m.get("title", "")).split()
            if not re.fullmatch(r"[a-z]+", t)
        )

    seen: set[str] = set()
    out: list[dict] = []
    for m in ordered:
        k = key(m)
        if k and k in seen:
            continue
        seen.add(k)
        out.append(m)
    return out


def build_marathon(franchise: dict, cache_ttl: int = 24 * 3600) -> list[dict]:
    api = Rutube()
    cache = Cache(ttl=cache_ttl)
    movies = _marathon_pool(franchise, cache_ttl)
    if franchise.get("parts"):
        return _dedupe_ordered(_order_by_parts(api, cache, movies, franchise))
    return sort_episodes(movies)


def unmatched_parts(franchise: dict, cache_ttl: int = 24 * 3600) -> list[str]:
    """Части, которым не нашлось ролика даже точечным поиском."""
    api = Rutube()
    cache = Cache(ttl=cache_ttl)
    pool = _marathon_pool(franchise, cache_ttl)
    used: set[str] = set()
    missing = []
    for part in franchise.get("parts", []):
        best = _seek(pool, part, used, franchise, allow_shared=False)
        if best is None:
            for m in _search_part(api, cache, franchise, part):
                if m["id"] not in pool_ids(pool):
                    pool.append(m)
            best = _seek(pool, part, used, franchise, allow_shared=True)
        if best:
            used.add(best["id"])
        else:
            missing.append(part)
    return missing

def queue_load() -> list[dict]:
    from . import config
    data = config.load_json(config.MQUEUE_FILE, [])
    return data if isinstance(data, list) else []


def queue_save(q: list[dict]) -> None:
    from . import config
    config.save_json(config.MQUEUE_FILE, q)


def queue_add(name: str, category: str = "Другое") -> bool:
    q = queue_load()
    if any(x["title"].lower() == name.lower() and not x.get("done") for x in q):
        return False
    q.append({
        "title": name,
        "category": category,
        "current_index": 0,
        "done": False,
        "added_at": _ts(),
        "done_at": None,
        "rating": None,
    })
    queue_save(q)
    return True


def queue_next_part() -> dict | None:
    """Вернуть следующий активный марафон и его текущую часть."""
    q = queue_load()
    active = [x for x in q if not x.get("done")]
    if not active:
        return None
    item = active[0]
    fr = next((f for f in load_franchises() if f["name"].lower() == item["title"].lower()), None)
    if fr is None:
        return None
    parts = fr.get("parts", [])
    idx = int(item.get("current_index", 0))
    if idx >= len(parts):
        return None
    return {"item": item, "franchise": fr, "part": parts[idx], "index": idx}


def queue_advance() -> tuple[dict | None, bool]:
    """Пометить текущую часть просмотренной; True если марафон завершён."""
    cur = queue_next_part()
    if cur is None:
        return None, False
    item = cur["item"]
    q = queue_load()
    entry = next((x for x in q if x["title"] == item["title"] and not x.get("done")), None)
    if entry is None:
        return None, False
    parts = cur["franchise"].get("parts", [])
    idx = int(entry.get("current_index", 0)) + 1
    if idx >= len(parts):
        entry["done"] = True
        entry["done_at"] = _ts()
        queue_save(q)
        return entry, True
    entry["current_index"] = idx
    queue_save(q)
    return entry, False


def queue_active() -> list[dict]:
    return [x for x in queue_load() if not x.get("done")]


def queue_finish(num: int) -> bool:
    active = queue_active()
    if not 1 <= num <= len(active):
        return False
    entry = active[num - 1]
    q = queue_load()
    e = next((x for x in q if x["title"] == entry["title"] and not x.get("done")), None)
    if e is None:
        return False
    e["done"] = True
    e["done_at"] = _ts()
    queue_save(q)
    return True


def _ts() -> str:
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def is_series_query(query: str) -> bool:
    from .scoring import is_series_query as _isq
    return _isq(query)
