from __future__ import annotations

import json
import os
from pathlib import Path

from . import cache as cache_module

CONFIG_HOME = Path(os.environ.get("XDG_CONFIG_HOME", "~/.config")).expanduser() / "vsearch"
DATA_HOME = Path(os.environ.get("XDG_DATA_HOME", "~/.local/share")).expanduser() / "vsearch"

WATCHLIST_FILE = DATA_HOME / "watchlist.json"
SERIES_FILE = DATA_HOME / "series.json"
MQUEUE_FILE = DATA_HOME / "mqueue.json"
NOTES_FILE = DATA_HOME / "notes.json"

SETTINGS_FILE = CONFIG_HOME / "settings.json"
TITLES_FILE = CONFIG_HOME / "titles.json"

DATA_DIR = Path(__file__).parent / "data"

DEFAULT_SETTINGS = {
    "min_duration_minutes": 40,
    "results_limit": 20,
    "page_size": 20,
    "open_fullscreen": True,
    "allow_unknown_duration": True,
    "upscale_mode": "auto",
    "aspect_mode": "original",
    "anime4k_restore_shader": "",
    "anime4k_upscale_shader": "",
    "auto_select": True,
    "auto_select_threshold": 90,
}


def _user_file(name: str) -> Path:
    return CONFIG_HOME / name


def load_settings() -> dict:
    data = dict(DEFAULT_SETTINGS)
    try:
        user = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        if isinstance(user, dict):
            data.update(user)
    except (OSError, ValueError):
        pass
    return data


def save_settings(data: dict) -> None:
    CONFIG_HOME.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def load_json(path: Path, fallback):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return fallback


def save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _lines_from(path: Path) -> list[str]:
    try:
        return path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []


def load_bad_words() -> list[str]:
    words: list[str] = []
    for source in (DATA_DIR / "bad_words.txt", _user_file("bad_words.txt")):
        words.extend(
            line.strip().lower()
            for line in _lines_from(source)
            if line.strip() and not line.strip().startswith("#")
        )
    return list(dict.fromkeys(words))


def load_movie_hints() -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for source in (DATA_DIR / "movie_hints.txt", _user_file("movie_hints.txt")):
        for line in _lines_from(source):
            line = line.strip()
            if not line or line.startswith("#") or "=>" not in line:
                continue
            title, hints = line.split("=>", 1)
            key = _key(title)
            values = [h.strip() for h in hints.split("/") if h.strip()]
            result.setdefault(key, []).extend(values)
    return result


def load_quotes() -> dict[str, list[str]]:
    quotes = load_json(DATA_DIR / "quotes.json", {"_generic": ["🎬 Ищу фильм."]})
    user = load_json(_user_file("quotes.json"), {})
    if isinstance(quotes, dict) and isinstance(user, dict):
        for k, v in user.items():
            quotes[k] = v
    return quotes if isinstance(quotes, dict) else {"_generic": ["🎬 Ищу фильм."]}


def load_titles() -> dict:
    return load_json(TITLES_FILE, {}) if isinstance(load_json(TITLES_FILE, {}), dict) else {}


def norm(text) -> str:
    return " ".join(str(text).strip().split())


def _key(text: str) -> str:
    return norm(text).lower().replace("ё", "е")


def reset_cache() -> None:
    cache_module.Cache().clear()
