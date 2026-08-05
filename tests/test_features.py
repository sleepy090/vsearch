from __future__ import annotations

import pytest

from vsearch.scoring import (
    enrich_query,
    is_bad_result,
    result_score,
    year_from_hints,
    year_from_title,
)
from vsearch.series import add, load, mark_done, remove, save, set_progress


@pytest.fixture(autouse=True)
def _clean_series(tmp_path, monkeypatch):
    from vsearch import config as cfg

    monkeypatch.setattr(cfg, "SERIES_FILE", tmp_path / "series.json")
    save([])
    yield


def test_year_from_title():
    assert year_from_title("Blade Runner 1982") == 1982
    assert year_from_title("Без года") is None


def test_hints_year():
    assert year_from_hints("Шрек") is None or isinstance(year_from_hints("Шрек"), int)


def test_enrich_query_movie():
    q = enrich_query("Матрица", strict=True)
    assert "фильм" in q


def test_bad_result_trailer():
    assert is_bad_result("Матрица трейлер", "Матрица")


def test_bad_result_clean():
    assert not is_bad_result("Матрица (1999)", "Матрица")


def test_score_prefers_exact():
    a = result_score("Матрица", "Матрица (1999)", 8200)
    b = result_score("Матрица", "Матрица трейлер", 120)
    assert a > b


def test_score_stalker_game_penalized():
    game = result_score("Сталкер", "S.T.A.L.K.E.R. прохождение", 3600)
    movie = result_score("Сталкер", "Сталкер (1979) Тарковский", 9600)
    assert movie > game


def test_series_add_and_advance():
    assert add("Во все тяжкие", 1, 1)
    assert not add("Во все тяжкие", 1, 1)
    mark_done("Во все тяжкие")
    data = load()
    assert data[0]["episode"] == 2
    assert data[0]["watched"] == 1


def test_series_set_and_remove():
    add("Друзья", 1, 1)
    set_progress("Друзья", 3, 5)
    assert load()[0]["season"] == 3
    assert remove("Друзья") == "Друзья"
    assert load() == []


def test_backup_roundtrip(tmp_path, monkeypatch):
    from vsearch import backup as bk
    from vsearch import config as cfg

    data_dir = tmp_path / "share"
    monkeypatch.setattr(cfg, "DATA_HOME", data_dir)
    monkeypatch.setattr(cfg, "CONFIG_HOME", tmp_path / "config")
    bk.BACKUP_DIR = data_dir / "backups"
    data_dir.mkdir(parents=True)
    (data_dir / "series.json").write_text('[{"name":"x"}]')

    f = bk.create()
    assert f is not None and f.exists()
    (data_dir / "series.json").unlink()
    bk.restore()
    assert (data_dir / "series.json").read_text() == '[{"name":"x"}]'
    assert bk.BACKUP_DIR.exists()


def test_backup_skips_own_dir(tmp_path, monkeypatch):
    import tarfile

    from vsearch import backup as bk
    from vsearch import config as cfg

    data_dir = tmp_path / "share"
    monkeypatch.setattr(cfg, "DATA_HOME", data_dir)
    monkeypatch.setattr(cfg, "CONFIG_HOME", tmp_path / "config")
    bk.BACKUP_DIR = data_dir / "backups"
    data_dir.mkdir(parents=True)
    (data_dir / "series.json").write_text('[{"name":"x"}]')

    f = bk.create()
    with tarfile.open(f, "r:gz") as tar:
        names = tar.getnames()
    assert not any("backups/" in n for n in names)


def test_marathon_queue(tmp_path, monkeypatch):
    from vsearch import config as cfg
    from vsearch import marathons as mm

    fr_dir = tmp_path / "frs"
    fr_dir.mkdir()
    fr_file = fr_dir / "franchises.yaml"
    fr_file.write_text(
        "marathons:\n"
        "- name: Тест\n"
        "  query: тест\n"
        "  include: [тест]\n"
        "  parts: [часть 1, часть 2, часть 3]\n"
    )
    monkeypatch.setattr(mm, "USER_FILE", fr_file)
    monkeypatch.setattr(cfg, "MQUEUE_FILE", tmp_path / "queue.json")

    assert mm.queue_add("Тест")
    assert not mm.queue_add("Тест")
    cur = mm.queue_next_part()
    assert cur is not None and cur["part"] == "часть 1"
    entry, done = mm.queue_advance()
    assert not done
    assert mm.queue_next_part()["part"] == "часть 2"
    mm.queue_advance()
    mm.queue_advance()
    assert mm.queue_load()[0]["done"] is True
