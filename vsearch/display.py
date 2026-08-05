from __future__ import annotations

from rich.markup import escape
from rich.panel import Panel
from rich.table import Table

from .movies import parse_description, title_year

FALLBACK_ART = r"""
██╗   ██╗███████╗██╗     ██╗██╗  ██╗
██║   ██║██╔════╝██║     ██║╚██╗██╔╝
██║   ██║█████╗  ██║     ██║ ╚███╔╝
╚██╗ ██╔╝██╔══╝  ██║     ██║ ██╔██╗
 ╚████╔╝ ██║     ███████╗██║██╔╝ ██╗
  ╚═══╝  ╚═╝     ╚══════╝╚═╝╚═╝  ╚═╝
"""


def banner(console):
    try:
        from pyfiglet import Figlet

        fig = Figlet(font="standard")
        art = fig.renderText("VFLIX")
    except Exception:
        art = FALLBACK_ART
    console.print(art.rstrip("\n"), style="bold cyan", highlight=False)


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


def show_table(console, movies):
    table = Table(title=f"{len(movies)} фильмов", header_style="bold cyan", box=None, pad_edge=False)
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
    console.print(f"\n[bold]{escape(m.get('title', ''))}[/bold]")
    if parsed["year"]:
        console.print(f"[cyan]Год:[/cyan] {parsed['year']}")
    if parsed["country"]:
        console.print(f"[cyan]Страна:[/cyan] {escape(parsed['country'])}")
    if parsed["genres"]:
        console.print(f"[cyan]Жанр:[/cyan] {escape(', '.join(parsed['genres']))}")
    if parsed["director"]:
        console.print(f"[cyan]Режиссёр:[/cyan] {escape(parsed['director'])}")
    author = (m.get("author") or {}).get("name")
    console.print(
        f"[cyan]Длительность:[/cyan] {format_duration(m.get('duration'))} · "
        f"[cyan]Просмотры:[/cyan] {format_views(m.get('hits'))}"
    )
    if author:
        console.print(f"[cyan]Канал:[/cyan] {escape(author)}")
    console.print(f"[dim]{escape(m.get('video_url', ''))}[/dim]")
    desc = m.get("description", "")
    if desc:
        console.print(Panel(escape(desc[:1000]), title="Описание", border_style="dim"))

def show_watchlist_table(console, items, title="Список фильмов"):
    table = Table(title=title, header_style="bold cyan", box=None, pad_edge=False)
    table.add_column("#", justify="right")
    table.add_column("Фильм")
    table.add_column("Оценка", justify="right")
    table.add_column("Добавлен")
    for i, m in enumerate(items, 1):
        rating = f"{m.get('rating')}/10" if m.get("rating") else "—"
        table.add_row(str(i), escape(_truncate(m.get("title", ""), 60)), rating, m.get("added_at", ""))
    console.print(table)


def show_history_table(console, items):
    table = Table(title=f"История · {len(items)} просмотрено", header_style="bold green", box=None, pad_edge=False)
    table.add_column("#", justify="right")
    table.add_column("Фильм")
    table.add_column("Оценка", justify="right")
    table.add_column("Когда", justify="right")
    for i, m in enumerate(items, 1):
        rating = f"{m.get('rating')}/10" if m.get("rating") else "без оценки"
        table.add_row(str(i), escape(_truncate(m.get("title", ""), 60)), rating, m.get("watched_at", "—"))
    console.print(table)


def show_stats_table(console, s):
    table = Table(title="Статистика", header_style="bold cyan", box=None, pad_edge=False)
    table.add_column("Параметр", style="bold")
    table.add_column("Значение")
    table.add_row("Всего фильмов", str(s["total"]))
    table.add_row("Просмотрено", str(s["done"]))
    table.add_row("Осталось", str(s["left"]))
    table.add_row("Прогресс", f"{s['percent']}%")
    table.add_row("Оценок", str(s["rated"]))
    table.add_row("Средняя оценка", str(s["avg"]) if s["avg"] is not None else "—")
    console.print(table)


def show_series_table(console, items):
    table = Table(title="Сериалы", header_style="bold cyan", box=None, pad_edge=False)
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
    table = Table(title="Очередь марафонов", header_style="bold cyan", box=None, pad_edge=False)
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
    lines = [f"[bold]{escape(query)}[/bold]"]
    for key, label in (
        ("ru", "RU"),
        ("year", "Год"),
        ("type", "Тип"),
        ("genre", "Жанр"),
        ("note", "Заметка"),
    ):
        val = meta.get(key)
        if val:
            lines.append(f"[cyan]{label}:[/cyan] {escape(str(val))}")
    console.print(Panel("\n".join(lines), title="Карточка", border_style="cyan"))
