from __future__ import annotations

import builtins

import pytest


def _patch_input(monkeypatch, values: list[str]):
    it = iter(values)

    def fake(prompt=""):
        return next(it, "q")

    monkeypatch.setattr(builtins, "input", fake)


def test_select_pipe_enter_picks_first(monkeypatch):
    from vsearch.selector import select

    _patch_input(monkeypatch, [""])
    item, action = select(
        ["a", "b"],
        line=lambda s: s,
        title="t",
        enter_help="выбрать",
    )
    assert item == "a"
    assert action == "enter"


def test_select_pipe_number(monkeypatch):
    from vsearch.selector import select

    _patch_input(monkeypatch, ["2"])
    item, action = select(["a", "b"], line=lambda s: s)
    assert item == "b"


def test_select_pipe_key_prefix(monkeypatch):
    from vsearch.selector import select

    _patch_input(monkeypatch, ["x2"])
    item, action = select(
        ["a", "b"], line=lambda s: s, keys={"x": "действие"}
    )
    assert item == "b"
    assert action == "x"


def test_select_pipe_back(monkeypatch):
    from vsearch.selector import select

    _patch_input(monkeypatch, ["q"])
    item, action = select(["a", "b"], line=lambda s: s)
    assert item is None
    assert action == "q"


def test_select_empty():
    from vsearch.selector import select

    item, action = select([], line=lambda s: s)
    assert item is None
    assert action == "q"
