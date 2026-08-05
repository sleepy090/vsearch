from __future__ import annotations

from vsearch.movies import is_movie, parse_description, title_year


def test_parse_description():
    desc = (
        "Год выпуска: 1977\nСтрана: США\nЖанр: фантастика, фэнтези, боевик\n"
        "Режиссер: Джордж Лукас / George Lucas\n"
    )
    d = parse_description(desc)
    assert d["year"] == 1977
    assert d["country"] == "США"
    assert d["genres"] == ["фантастика", "фэнтези", "боевик"]
    assert "Лукас" in d["director"]


def test_parse_empty():
    d = parse_description("")
    assert d == {"year": None, "country": None, "genres": None, "director": None}


def test_title_year():
    assert title_year("Звёздные войны (1977)") == 1977
    assert title_year("Без года") is None


def test_is_movie_long_duration():
    item = {
        "duration": 7502,
        "title": "Какой-то фильм",
        "description": "",
        "category": {"name": "Развлечения"},
    }
    assert is_movie(item)


def test_is_movie_trailer_in_films_category_rejected():
    item = {"duration": 120, "title": "Трейлер фильма", "category": {"name": "Фильмы"}}
    assert not is_movie(item)


def test_is_movie_rejects_serial_and_short():
    serial = {"duration": 3000, "title": "Сериал", "is_serial": True}
    assert not is_movie(serial)
    short = {"duration": 30, "title": "Клип", "description": "", "category": {"name": "Музыка"}}
    assert not is_movie(short)


def test_is_movie_description_signal():
    item = {
        "duration": 10,
        "title": "Нарезка",
        "description": "Год выпуска: 2005\nЖанр: драма",
        "category": {"name": "Новости"},
    }
    assert is_movie(item)