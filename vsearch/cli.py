from __future__ import annotations

import argparse
import sys

from rich.console import Console

from .api import Rutube, RutubeError, search_cached
from .cache import Cache
from .display import banner, format_duration, show_detail, show_table
from .movies import is_movie
from .player import open_browser, play, player_hint

SEARCH_TTL = 6 * 3600
NEW_TTL = 6 * 3600

console = Console()

MENU = """\
[bold]1[/] Поиск фильма
[bold]2[/] Новинки
[bold]3[/] Марафоны
[bold]0[/] Выход"""


def _prompt(text: str = "") -> str:
    try:
        return input(text).strip()
    except (EOFError, KeyboardInterrupt):
        console.print("\n[dim]пока![/dim]")
        raise SystemExit(0)


def _collect(query, sort, pages, ttl=SEARCH_TTL):
    api = Rutube()
    cache = Cache(ttl=ttl)
    seen = {}
    for page in range(1, pages + 1):
        data = search_cached(
            api, cache, query, sort=sort, page=page, per_page=30, duration="long"
        )
        for item in data.get("results", []):
            if is_movie(item):
                seen[item["id"]] = item
        if not data.get("has_next"):
            break
    return list(seen.values())


def _selection_loop(movies):
    while True:
        show_table(console, movies)
        console.print(
            f"[dim]N — детали · wN — смотреть ([cyan]{player_hint()}[/cyan]) · "
            f"oN — браузер · q — назад[/dim]"
        )
        raw = _prompt("> ")
        if raw.lower() in ("q", "0"):
            return
        action, num = "info", raw
        if raw[:1].lower() == "w":
            action, num = "watch", raw[1:]
        elif raw[:1].lower() == "o":
            action, num = "open", raw[1:]
        try:
            movie = movies[int(num) - 1]
        except (ValueError, IndexError):
            console.print("[red]нет такого номера[/red]")
            continue
        if action == "watch":
            _do_watch([movie["video_url"]])
        elif action == "open":
            open_browser(movie["video_url"])
        else:
            show_detail(console, movie)
            again = _prompt("w — смотреть, o — браузер, b — назад > ").lower()
            if again == "w":
                _do_watch([movie["video_url"]])
            elif again == "o":
                open_browser(movie["video_url"])


def _do_watch(urls):
    method = play(urls)
    if method == "mpv":
        console.print("[green]mpv запущен[/green]")
    elif method == "browser":
        console.print("[green]открыто в браузере[/green]")
    else:
        console.print("[yellow]плеер не найден[/yellow]")


def _list_franchises(franchises):
    console.print("[bold]Марафоны:[/bold]")
    for i, fr in enumerate(franchises, 1):
        console.print(f"{i:>2}. {fr['name']}")
    console.print("[dim]N — выбрать · q — назад[/dim]")


def cmd_search(query):
    try:
        movies = _collect(query, "rank", 3)
    except RutubeError as exc:
        console.print(f"[red]{exc}[/red]")
        return 1
    if not movies:
        console.print("[yellow]фильмов не нашлось[/yellow]")
        return 0
    _selection_loop(movies)
    return 0


def cmd_new():
    api = Rutube()
    cache = Cache(ttl=NEW_TTL)
    seen = {}
    for query in ("фильм", "кино"):
        try:
            for page in (1, 2):
                data = search_cached(
                    api, cache, query, sort="created", page=page, per_page=30, duration="long"
                )
                for item in data.get("results", []):
                    if is_movie(item):
                        seen[item["id"]] = item
                if not data.get("has_next"):
                    break
        except RutubeError as exc:
            console.print(f"[red]{exc}[/red]")
    movies = sorted(
        seen.values(), key=lambda m: m.get("publication_ts", "") or "", reverse=True
    )[:20]
    if not movies:
        console.print("[yellow]новинок не нашлось[/yellow]")
        return
    _selection_loop(movies)


def cmd_marathon(name=None, watch=False):
    from .marathons import build_marathon, load_franchises, unmatched_parts

    franchises = load_franchises()
    if not name:
        _list_franchises(franchises)
        raw = _prompt("> ")
        if raw.lower() == "q":
            return
        try:
            fr = franchises[int(raw) - 1]
        except (ValueError, IndexError):
            console.print("[red]нет такого номера[/red]")
            return
    else:
        fr = next((f for f in franchises if f["name"].lower() == name.lower()), None)
        if fr is None:
            console.print(f"[red]нет франшизы «{name}»[/red]")
            return
    console.print(f"[bold]{fr['name']}[/bold] — ищу на Rutube…")
    episodes = build_marathon(fr)
    if not episodes:
        console.print("[yellow]ничего не собралось[/yellow]")
        return
    total = sum(int(m.get("duration") or 0) for m in episodes)
    console.print(
        f"[bold]{fr['name']}[/bold] · {len(episodes)} фильмов · "
        f"общий хронометраж [cyan]{format_duration(total)}[/cyan]"
    )
    if fr.get("parts"):
        missing = unmatched_parts(fr)
        if missing:
            console.print(
                f"[dim]не нашлось на Rutube: {', '.join(missing)}[/dim]"
            )
    if watch:
        _do_watch([m["video_url"] for m in episodes])
        return
    _selection_loop(episodes)


def cmd_watch(target):
    if target.startswith("http"):
        _do_watch([target])
    else:
        console.print(
            "[yellow]watch принимает url: vsearch watch https://rutube.ru/video/xxx[/yellow]"
        )


def cmd_refresh():
    Cache().clear()
    console.print("[green]кэш очищен[/green]")


def menu():
    banner(console)
    console.print("[dim]vsearch — фильмы с Rutube в терминале[/dim]\n")
    while True:
        console.print(MENU)
        raw = _prompt("vsearch> ")
        if raw == "1":
            query = _prompt("Что ищем? ")
            if query:
                cmd_search(query)
        elif raw == "2":
            cmd_new()
        elif raw == "3":
            cmd_marathon()
        elif raw.lower() in ("0", "q"):
            console.print("[dim]пока![/dim]")
            break
        else:
            console.print("[red]?[/red]")


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="vsearch", description="Поиск и просмотр фильмов на Rutube из терминала"
    )
    sub = parser.add_subparsers(dest="cmd")
    p = sub.add_parser("search", help="поиск фильмов")
    p.add_argument("query", nargs="+")
    sub.add_parser("new", help="свежие фильмы")
    p = sub.add_parser("marathon", help="марафоны по франшизам")
    p.add_argument("name", nargs="?")
    p.add_argument("--watch", action="store_true", help="проиграть всё подряд")
    p = sub.add_parser("watch", help="проиграть url в mpv")
    p.add_argument("target")
    sub.add_parser("refresh", help="очистить кэш")
    args = parser.parse_args(argv)

    try:
        if args.cmd is None:
            menu()
        elif args.cmd == "search":
            return cmd_search(" ".join(args.query))
        elif args.cmd == "new":
            cmd_new()
        elif args.cmd == "marathon":
            cmd_marathon(args.name, args.watch)
        elif args.cmd == "watch":
            cmd_watch(args.target)
        elif args.cmd == "refresh":
            cmd_refresh()
    except KeyboardInterrupt:
        console.print("\n[dim]пока![/dim]")
    except RutubeError as exc:
        console.print(f"[red]{exc}[/red]")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())