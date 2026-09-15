from __future__ import annotations

import pytest

from vsearch.tmdb import Tmdb, TmdbError, _year_from_date, fetch_movies


class _Resp:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self.payload


class _Session:
    def __init__(self, payload):
        self.payload = payload

    def get(self, url, params=None, headers=None, timeout=None):
        return _Resp(self.payload)


def _payload():
    return {
        "results": [
            {
                "id": 1,
                "title": "Мумия",
                "original_title": "The Mummy",
                "release_date": "2026-05-20",
                "overview": "Описание",
                "vote_average": 7.5,
                "vote_count": 100,
                "poster_path": "/x.jpg",
            },
            {
                "id": 2,
                "title": "Одиссея",
                "original_title": "The Odyssey",
                "release_date": "",
                "overview": "",
                "vote_average": 0,
                "vote_count": 0,
                "poster_path": None,
            },
        ]
    }


def test_movies_parse():
    c = Tmdb(api_key="K", session=_Session(_payload()))
    ms = c.movies("now_playing")
    assert ms[0]["title"] == "Мумия"
    assert ms[0]["year"] == 2026
    assert ms[0]["vote_average"] == 7.5
    assert ms[1]["year"] is None


def test_limit():
    c = Tmdb(api_key="K", session=_Session(_payload()))
    assert len(c.movies("now_playing", limit=1)) == 1


def test_requires_key():
    c = Tmdb(api_key="", session=_Session(_payload()))
    with pytest.raises(TmdbError):
        c.movies("now_playing")


def test_fetch_cached():
    class Cache:
        def __init__(self):
            self.d = {}

        def get(self, u):
            return self.d.get(u)

        def put(self, u, val):
            self.d[u] = val

    c = Tmdb(api_key="K", session=_Session(_payload()))
    out = fetch_movies(Cache(), c, "popular", limit=12)
    assert len(out) == 2
    assert out[0]["tmdb_id"] == 1


def test_year_from_date():
    assert _year_from_date("2026-05-20") == 2026
    assert _year_from_date("") is None
    assert _year_from_date(None) is None
