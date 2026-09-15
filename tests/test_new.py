from __future__ import annotations

from vsearch.api import tag_feed_cached
from vsearch.cli import _filter_new_items, _is_series_title


def _item(iid, title, duration, desc="", ts="2026-08-01", serial=False):
    item = {
        "id": iid,
        "title": title,
        "duration": duration,
        "description": desc,
        "publication_ts": ts,
    }
    if serial:
        item["is_serial"] = True
    return item


def test_filter_drops_short_serial_and_dupe_by_id():
    items = [
        _item("a", "Мумия (фильм, 2026)", 6000, ts="2026-08-08"),
        _item("a", "Мумия (фильм, 2026)", 6000, ts="2026-08-07"),
        _item("b", "Моана (фильм, 2026)", 5900, ts="2026-08-06"),
        _item("c", "Сериал какой-то", 3000, serial=True),
        _item("d", "Трейлер фильма", 120),
    ]
    out = _filter_new_items(items)
    assert [m["title"] for m in out] == ["Мумия (фильм, 2026)", "Моана (фильм, 2026)"]


def test_filter_drops_concert_and_uzbek():
    items = [
        _item("a", "Группа Кино — Концерт в ЦСКА", 7200, ts="2026-08-08"),
        _item("b", "HECH KIMGA AYTMA (o'zbek kino)", 5000, ts="2026-08-07"),
        _item("c", "Кормилец (фильм, 2025)", 5957, ts="2026-08-06"),
    ]
    out = _filter_new_items(items)
    assert [m["title"] for m in out] == ["Кормилец (фильм, 2025)"]


def test_filter_dedupes_by_title():
    items = [
        _item("a", "Одиссея (2026) | The Odyssey", 9900, ts="2026-08-08"),
        _item("b", "Одиссея (2026) | The Odyssey", 9900, ts="2026-08-07"),
        _item("c", "Одиссея (2026) / The Odyssey", 9900, ts="2026-08-06"),
    ]
    out = _filter_new_items(items)
    assert len(out) == 1


def test_filter_keeps_recent_first():
    items = [
        _item("a", "Старый фильм (фильм, 2005)", 6000, ts="2025-01-01"),
        _item("b", "Новый фильм (фильм, 2026)", 6000, ts="2026-08-08"),
    ]
    out = _filter_new_items(items)
    assert out[0]["title"] == "Новый фильм (фильм, 2026)"


def test_is_series_title_detects_episodes():
    assert _is_series_title("Нам кранты | 1 серия | Дмитрий Журавлев")
    assert _is_series_title("Вторая жизнь Сергеича, 1 сезон, 1 серия")
    assert _is_series_title("Сериал какой-то")
    assert not _is_series_title("Река крови | Rio de Sangue (2026)")


def test_filter_drops_series_episodes_from_curated():
    items = [
        _item("a", "Река крови | Rio de Sangue (2026)", 6363, ts="2026-08-03"),
        _item("b", "Нам кранты | 1 серия | Дмитрий Журавлев", 2646, ts="2026-08-03"),
        _item("c", "Вторая жизнь Сергеича, 1 сезон, 1 серия", 2903, ts="2026-07-28"),
    ]
    cleaned = [m for m in items if not _is_series_title(m["title"])]
    out = _filter_new_items(cleaned, require_year=False)
    assert [m["title"] for m in out] == ["Река крови | Rio de Sangue (2026)"]


def test_filter_require_year_flag():
    items = [_item("a", "Без года в названии", 6000, ts="2026-08-03")]
    assert _filter_new_items(items, require_year=False) == items
    assert _filter_new_items(items, require_year=True) == []


class _FakeApi:
    def __init__(self, pages):
        self.pages = pages
        self.calls = []

    def tag_feed(self, tag_id, *, sort="tagged_d", page=1, per_page=50):
        self.calls.append((tag_id, page))
        return {
            "results": self.pages.get(page, []),
            "has_next": page < len(self.pages),
        }


class _FakeCache:
    def __init__(self):
        self.store = {}

    def get(self, url):
        return self.store.get(url)

    def put(self, url, value):
        self.store[url] = value


def test_tag_feed_cached_merges_pages_and_stops():
    api = _FakeApi({
        1: [{"id": "a", "title": "Фильм 1 (2026)", "duration": 6000}],
        2: [{"id": "b", "title": "Фильм 2 (2026)", "duration": 6000}],
    })
    cache = _FakeCache()
    out = tag_feed_cached(api, cache, 8151, pages=3)
    assert [m["id"] for m in out] == ["a", "b"]
    assert api.calls == [(8151, 1), (8151, 2)]


def test_tag_feed_cached_uses_cache():
    api = _FakeApi({1: [{"id": "a", "title": "Фильм 1 (2026)", "duration": 6000}]})
    cache = _FakeCache()
    tag_feed_cached(api, cache, 8151, pages=1)
    tag_feed_cached(api, cache, 8151, pages=1)
    assert api.calls == [(8151, 1)]


def test_selection_loop_enter_plays(monkeypatch):
    from vsearch import cli

    played = []
    monkeypatch.setattr(cli, "_do_watch", lambda urls, title=None: played.append(urls))
    calls = {"n": 0}

    def fake_select(items, **kw):
        calls["n"] += 1
        if calls["n"] == 1:
            return {"video_url": "https://rutube.ru/video/x/", "title": "Фильм X"}, "enter"
        return None, "back"

    monkeypatch.setattr(cli, "select", fake_select)
    cli._selection_loop([{"video_url": "u", "title": "T"}])
    assert played == [["https://rutube.ru/video/x/"]]
