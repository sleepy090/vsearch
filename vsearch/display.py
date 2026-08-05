from __future__ import annotations

from rich.markup import escape
from rich.panel import Panel
from rich.table import Table

from .movies import parse_description, title_year

MAUVE = "#B48EAD"
LAVENDER = "#C5C2EA"
PINK = "#EFB8C9"
CYAN = "#88C0D0"
GREEN = "#A3BE8C"
DIM = "#616E88"

_TABLE_STYLE = {
    "header": f"bold {CYAN}",
    "title": f"bold {LAVENDER}",
    "box": None,
    "pad_edge": False,
}

FALLBACK_ART = r"""
███████╗███████╗███████╗ █████╗ ██████╗  ██████╗██╗  ██╗
██╔════╝██╔════╝██╔════╝██╔══██╗██╔══██╗██╔════╝██║  ██║
███████╗█████╗  ███████╗███████║██████╔╝██║     ███████║
╚════██║██╔══╝  ╚════██║██╔══██║██╔══██╗██║     ██╔══██║
███████║███████╗███████║██║  ██║██║  ██║╚██████╗██║  ██║
╚══════╝╚══════╝╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝
"""


def banner(console):
    from rich.text import Text

    try:
        from pyfiglet import Figlet

        fig = Figlet(font="standard")
        art = fig.renderText("VSEARCH")
    except Exception:
        art = FALLBACK_ART
    lines = [line for line in art.rstrip("\n").splitlines() if line.strip()]
    for line in lines:
        console.print(
            Text.from_markup(f"[gradient({MAUVE},{LAVENDER},{PINK})]{escape(line)}[/]"),
            highlight=False,
        )


def _truncate(value, limit):
    text = str(value or "")
    return text if len(text) <= limit else text[: limit - 1] + "…"


def format_duration(sec):
    try:
        sec = int(sec or 0)
    except (TypeError, ValueError):
        sec = 0
    if sec >= 3600:
        return f"{sec // 3600}ч {(sec % 3600) // 60:02d}м"
    if sec >= 60:
        return f"{sec // 60}м"
    return f"{sec}с"


def format_views(n):
    try:
        n = int(n or 0)
    except (TypeError, ValueError):
        return "—"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.0f}K"
    return str(n)


def _table(title: str, header: str | None = None) -> Table:
    table = Table(
        title=title,
        header_style=header or f"bold {CYAN}",
        box=None,
        pad_edge=False,
        title_style=f"bold {LAVENDER}",
        border_style=DIM,
    )
    return table


def show_table(console, movies):
    table = _table(f"{len(movies)} фильмов")
    table.add_column("#", justify="right")
    table.add_column("Название")
    table.add_column("Год", justify="right")
    table.add_column("Длит", justify="right")
    table.add_column("Просмотры", justify="right")
    table.add_column("Канал")
    for i, m in enumerate(movies, 1):
        parsed = parse_description(m.get("description", ""))
        year = parsed["year"] or title_year(m.get("title")) or "—"
        author = (m.get("author") or {}).get("name") or "—"
        table.add_row(
            str(i),
            escape(_truncate(m.get("title", ""), 60)),
            str(year),
            format_duration(m.get("duration")),
            format_views(m.get("hits")),
            escape(_truncate(author, 26)),
        )
    console.print(table)


def show_detail(console, m):
    parsed = parse_description(m.get("description", ""))
    title = escape(m.get("title", ""))
    console.print(f"\n[bold {LAVENDER}]{title}[/bold {LAVENDER}]")
    if parsed["year"]:
        console.print(f"[{CYAN}]Год:[/{CYAN}] {parsed['year']}")
    if parsed["country"]:
        console.print(f"[{CYAN}]Страна:[/{CYAN}] {escape(parsed['country'])}")
    if parsed["genres"]:
        console.print(f"[{CYAN}]Жанр:[/{CYAN}] {escape(', '.join(parsed['genres']))}")
    if parsed["director"]:
        console.print(f"[{CYAN}]Режиссёр:[/{CYAN}] {escape(parsed['director'])}")
    author = (m.get("author") or {}).get("name")
    console.print(
        f"[{CYAN}]Длительность:[/{CYAN}] {format_duration(m.get('duration'))} · "
        f"[{CYAN}]Просмотры:[/{CYAN}] {format_views(m.get('hits'))}"
    )
    if author:
        console.print(f"[{CYAN}]Канал:[/{CYAN}] {escape(author)}")
    console.print(f"[{DIM}]{escape(m.get('video_url', ''))}[/{DIM}]")
    desc = m.get("description", "")
    if desc:
        console.print(Panel(escape(desc[:1000]), title="Описание", border_style=DIM))

def show_watchlist_table(console, items, title="Список фильмов"):
    table = _table(title)
    table.add_column("#", justify="right")
    table.add_column("Фильм")
    table.add_column("Оценка", justify="right")
    table.add_column("Добавлен")
    for i, m in enumerate(items, 1):
        rating = f"{m.get('rating')}/10" if m.get("rating") else "—"
        table.add_row(str(i), escape(_truncate(m.get("title", ""), 60)), rating, m.get("added_at", ""))
    console.print(table)


def show_history_table(console, items):
    table = _table(f"История · {len(items)} просмотрено", header=f"bold {GREEN}")
    table.add_column("#", justify="right")
    table.add_column("Фильм")
    table.add_column("Оценка", justify="right")
    table.add_column("Когда", justify="right")
    for i, m in enumerate(items, 1):
        rating = f"{m.get('rating')}/10" if m.get("rating") else "без оценки"
        table.add_row(str(i), escape(_truncate(m.get("title", ""), 60)), rating, m.get("watched_at", "—"))
    console.print(table)


def show_stats_table(console, s):
    table = _table("Статистика")
    table.add_column("Параметр", style=f"bold {LAVENDER}")
    table.add_column("Значение")
    table.add_row("Всего фильмов", str(s["total"]))
    table.add_row("Просмотрено", str(s["done"]))
    table.add_row("Осталось", str(s["left"]))
    table.add_row("Прогресс", f"{s['percent']}%")
    table.add_row("Оценок", str(s["rated"]))
    table.add_row("Средняя оценка", str(s["avg"]) if s["avg"] is not None else "—")
    console.print(table)


def show_series_table(console, items):
    table = _table("Сериалы")
    table.add_column("#", justify="right")
    table.add_column("Название")
    table.add_column("Следующая серия")
    table.add_column("Серий", justify="right")
    for i, m in enumerate(items, 1):
        table.add_row(
            str(i),
            escape(_truncate(m.get("title", ""), 50)),
            f'{m.get("season", 1)} сезон {m.get("episode", 1)} серия',
            str(m.get("watched", 0)),
        )
    console.print(table)


def show_queue_table(console, items):
    table = _table("Очередь марафонов")
    table.add_column("#", justify="right")
    table.add_column("Марафон")
    table.add_column("Часть", justify="right")
    table.add_column("Текущая")
    for i, m in enumerate(items, 1):
        idx = int(m.get("current_index", 0))
        parts = m.get("parts", [])
        total = len(parts)
        current = parts[idx] if idx < total else "завершён"
        table.add_row(
            str(i),
            escape(_truncate(m.get("title", ""), 40)),
            f"{idx + 1}/{total}",
            escape(_truncate(current, 40)),
        )
    console.print(table)


def show_info_card(console, query, meta):
    if not isinstance(meta, dict) or not meta:
        return
    lines = [f"[bold {LAVENDER}]{escape(query)}[/bold {LAVENDER}]"]
    for key, label in (
        ("ru", "RU"),
        ("year", "Год"),
        ("type", "Тип"),
        ("genre", "Жанр"),
        ("note", "Заметка"),
    ):
        val = meta.get(key)
        if val:
            lines.append(f"[{CYAN}]{label}:[/{CYAN}] {escape(str(val))}")
    console.print(Panel("\n".join(lines), title="Карточка", border_style=MAUVE))
