from __future__ import annotations

import argparse
import sys

from rich.console import Console

from . import config, marathons, series, watchlist
from .api import (
    Rutube,
    RutubeError,
    search_rutube_scored,
    staged_search,
    to_display_items,
)
from .cache import Cache
from .display import (
    banner,
    format_duration,
    show_detail,
    show_history_table,
    show_info_card,
    show_queue_table,
    show_series_table,
    show_stats_table,
    show_table,
    show_watchlist_table,
)
from .player import open_browser, play, player_hint
from .scoring import movie_quote

SEARCH_TTL = 6 * 3600

console = Console()

MENU = """\
[bold]1[/] Поиск фильма
[bold]2[/] Новинки
[bold]3[/] Марафоны
[bold]4[/] Список фильмов
[bold]5[/] Сериалы
[bold]6[/] Очередь марафонов
[bold]0[/] Выход"""


def _prompt(text: str = "") -> str:
    try:
        return input(text).strip()
    except (EOFError, KeyboardInterrupt):
        console.print("\n[dim]пока![/dim]")
        raise SystemExit(0)


def _collect(query, sort, pages, ttl=SEARCH_TTL):
    """Сбор фильмов по запросу с эвристикой."""
    from .movies import is_movie

    api = Rutube()
    cache = Cache(ttl=ttl)
    seen = {}
    for page in range(1, pages + 1):
        from .api import search_cached

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
    """Интерактивный выбор фильма из списка."""
    while True:
        show_table(console, movies)
        console.print(
            f"[dim]N — детали · wN — смотреть ([cyan]{player_hint()}[/cyan]) · "
            f"oN — браузер · aN — добавить в список · q — назад[/dim]"
        )
        raw = _prompt("> ")
        if raw.lower() in ("q", "0"):
            return
        action, num = "info", raw
        if raw[:1].lower() == "w":
            action, num = "watch", raw[1:]
        elif raw[:1].lower() == "o":
            action, num = "open", raw[1:]
        elif raw[:1].lower() == "a":
            action, num = "add", raw[1:]
        try:
            movie = movies[int(num) - 1]
        except (ValueError, IndexError):
            console.print("[red]нет такого номера[/red]")
            continue
        if action == "watch":
            _do_watch([movie["video_url"]], title=movie.get("title"))
        elif action == "open":
            open_browser(movie["video_url"])
        elif action == "add":
            _add_to_watchlist(movie)
        else:
            show_detail(console, movie)
            again = _prompt("w — смотреть, o — браузер, a — в список, b — назад > ").lower()
            if again == "w":
                _do_watch([movie["video_url"]], title=movie.get("title"))
            elif again == "o":
                open_browser(movie["video_url"])
            elif again == "a":
                _add_to_watchlist(movie)


def _add_to_watchlist(movie):
    title = movie.get("title", "")
    if not title:
        return
    if title.startswith("VK Video"):
        return
    added = watchlist.add_movies(title)
    if added:
        console.print(f"[green]добавлено в список: {title}[/green]")
    else:
        console.print("[yellow]уже в списке[/yellow]")


def _do_watch(urls, title=None):
    method = play(urls)
    if method == "mpv":
        console.print(f"[green]mpv запущен: {title or urls[0]}[/green]")
        return True
    if method == "browser":
        console.print("[green]открыто в браузере[/green]")
        return True
    console.print("[yellow]плеер не найден[/yellow]")
    return False


def _search_and_select(query, strict=True):
    api = Rutube()
    cache = Cache(ttl=SEARCH_TTL)
    meta = config.load_titles().get(query.strip().lower())
    show_info_card(console, query, meta)
    try:
        movies = staged_search(api, cache, query, strict=strict, pages=2)
    except RutubeError as exc:
        console.print(f"[red]{exc}[/red]")
        return
    items = to_display_items(movies)
    if not items:
        console.print(f"[yellow]ничего не нашлось: {query}[/yellow]")
        return
    if config.load_settings().get("auto_select", True) and len(items) == 1:
        console.print(f"[green]автовыбор: {items[0]['title']}[/green]")
        _do_watch([items[0]["video_url"]], title=items[0]["title"])
        return
    _selection_loop(items)


def _list_franchises(franchises):
    console.print("[bold]Марафоны:[/bold]")
    for i, fr in enumerate(franchises, 1):
        console.print(f"{i:>2}. {fr['name']}")
    console.print("[dim]N — выбрать · q — назад[/dim]")


def cmd_search(query):
    _search_and_select(query)
    return 0


def cmd_new():
    api = Rutube()
    cache = Cache(ttl=SEARCH_TTL)
    seen = {}
    for q in ("фильм", "кино"):
        try:
            for m in search_rutube_scored(api, cache, q, sort="created", pages=2, strict=True):
                seen[m["id"]] = m
        except RutubeError as exc:
            console.print(f"[red]{exc}[/red]")
    items = sorted(
        seen.values(),
        key=lambda m: (m.get("publication_ts") or "") or (m.get("hits") or 0),
        reverse=True,
    )[:20]
    movies = to_display_items(items)
    if not movies:
        console.print("[yellow]новинок не нашлось[/yellow]")
        return
    _selection_loop(movies)


def cmd_watch(target):
    if target.startswith("http"):
        _do_watch([target])
    else:
        _search_and_select(target)


def _pick_franchise(name):
    franchises = marathons.load_franchises()
    if not name:
        _list_franchises(franchises)
        raw = _prompt("> ")
        if raw.lower() == "q":
            return None
        try:
            return franchises[int(raw) - 1]
        except (ValueError, IndexError):
            console.print("[red]нет такого номера[/red]")
            return None
    fr = next((f for f in franchises if f["name"].lower() == name.lower()), None)
    if fr is None:
        console.print(f"[red]нет франшизы «{name}»[/red]")
        return None
    return fr


def cmd_marathon(name=None, watch=False):
    fr = _pick_franchise(name)
    if fr is None:
        return
    console.print(f"[bold]{fr['name']}[/bold] — ищу на Rutube…")
    try:
        episodes = marathons.build_marathon(fr)
    except RutubeError as exc:
        console.print(f"[red]{exc}[/red]")
        return
    if not episodes:
        console.print("[yellow]ничего не собралось[/yellow]")
        return
    total = sum(int(m.get("duration") or 0) for m in episodes)
    console.print(
        f"[bold]{fr['name']}[/bold] · {len(episodes)} фильмов · "
        f"общий хронометраж [cyan]{format_duration(total)}[/cyan]"
    )
    if fr.get("parts"):
        missing = marathons.unmatched_parts(fr)
        if missing:
            console.print(f"[dim]не нашлось на Rutube: {', '.join(missing)}[/dim]")
    if watch:
        _do_watch([m["video_url"] for m in episodes])
        return
    _selection_loop(episodes)


def cmd_marathon_queue():
    q = marathons.queue_active()
    if not q:
        console.print("[yellow]очередь пуста[/yellow]")
        return
    enriched = []
    for item in q:
        fr = next(
            (f for f in marathons.load_franchises() if f["name"].lower() == item["title"].lower()),
            None,
        )
        enriched.append({**item, "parts": fr.get("parts", []) if fr else []})
    show_queue_table(console, enriched)
    console.print("[dim]N — играть часть · n — следующая · dN — завершить · q — назад[/dim]")
    while True:
        raw = _prompt("> ")
        if raw.lower() in ("q", "0"):
            return
        if raw.lower() == "n":
            cmd_marathon_next()
            return
        if raw[:1].lower() == "d":
            num = raw[1:]
            if num.isdigit() and marathons.queue_finish(int(num)):
                console.print("[green]марафон завершён[/green]")
            continue
        if raw.isdigit():
            _play_queue_item(int(raw))
            return


def _play_queue_item(num):
    active = marathons.queue_active()
    if not 1 <= num <= len(active):
        console.print("[red]нет такого номера[/red]")
        return
    item = active[num - 1]
    fr = next(
        (f for f in marathons.load_franchises() if f["name"].lower() == item["title"].lower()),
        None,
    )
    if fr is None:
        console.print(f"[red]франшиза «{item['title']}» не найдена[/red]")
        return
    parts = fr.get("parts", [])
    idx = int(item.get("current_index", 0))
    if idx >= len(parts):
        console.print("[yellow]марафон уже завершён[/yellow]")
        return
    console.print(f"[bold]{item['title']}[/bold] · часть {idx + 1}/{len(parts)}")
    _search_and_select(parts[idx], strict=not marathons.is_series_query(parts[idx]))
    _ask_advance_queue(item["title"])


def _ask_advance_queue(title):
    ans = _prompt("Отметить часть просмотренной? [y/N]: ").lower()
    if ans in ("y", "yes", "д", "да"):
        entry, done = marathons.queue_advance()
        if done:
            console.print(f"[green]марафон завершён: {entry['title']}[/green]")
            rating = _prompt("Оценка 1-10, Enter пропустить: ")
            if rating.isdigit() and 1 <= int(rating) <= 10:
                entry["rating"] = int(rating)
                marathons.queue_save(marathons.queue_load())
        else:
            console.print("[green]следующая часть в очереди[/green]")


def cmd_marathon_next():
    cur = marathons.queue_next_part()
    if cur is None:
        console.print("[yellow]очередь пуста или завершена[/yellow]")
        return
    item, fr, part, idx = cur["item"], cur["franchise"], cur["part"], cur["index"]
    parts = fr.get("parts", [])
    console.print(f"[bold]{item['title']}[/bold] · часть {idx + 1}/{len(parts)}: {part}")
    _search_and_select(part, strict=not marathons.is_series_query(part))
    _ask_advance_queue(item["title"])


def cmd_marathon_add(name):
    fr = _pick_franchise(name)
    if fr is None:
        return
    if marathons.queue_add(fr["name"], fr.get("category", "Другое")):
        console.print(f"[green]марафон в очереди: {fr['name']}[/green]")
    else:
        console.print("[yellow]уже в очереди[/yellow]")


def cmd_watchlist_list():
    items = watchlist.unwatched()
    if not items:
        console.print("[yellow]список пуст. vsearch list add «Фильм»[/yellow]")
        return
    show_watchlist_table(console, items)
    console.print("[dim]N — смотреть · dN — просмотрено · q — назад[/dim]")
    while True:
        raw = _prompt("> ")
        if raw.lower() in ("q", "0"):
            return
        if raw[:1].lower() == "d":
            num = raw[1:]
            if num.isdigit():
                title = watchlist.mark_done(int(num))
                if title:
                    console.print(f"[green]просмотрено: {title}[/green]")
                    rating = _prompt("Оценка 1-10, Enter пропустить: ")
                    if rating.isdigit() and 1 <= int(rating) <= 10:
                        watchlist.save(watchlist.load())
            continue
        if raw.isdigit():
            _play_watchlist_item(int(raw))
            return


def _play_watchlist_item(num):
    items = watchlist.unwatched()
    if not 1 <= num <= len(items):
        console.print("[red]нет такого номера[/red]")
        return
    title = items[num - 1]["title"]
    console.print(f"[bold]{title}[/bold]")
    _search_and_select(title)
    ans = _prompt("Отметить просмотренным? [y/N]: ").lower()
    if ans in ("y", "yes", "д", "да"):
        title2 = watchlist.mark_done(num)
        if title2:
            console.print(f"[green]просмотрено: {title2}[/green]")


def cmd_watchlist_next():
    items = watchlist.unwatched()
    if not items:
        console.print("[yellow]список пуст[/yellow]")
        return
    _play_watchlist_item(1)


def cmd_watchlist_add(raw):
    if not raw:
        console.print('[red]пример: vsearch list add "Нечто / Матрица"[/red]')
        return
    added = watchlist.add_movies(raw)
    console.print(f"[green]добавлено: {added}[/green]")


def cmd_watchlist_done(num):
    title = watchlist.mark_done(num)
    if title:
        console.print(f"[green]просмотрено: {title}[/green]")
    else:
        console.print("[red]нет такого номера[/red]")


def cmd_watchlist_rate(num, rating):
    if not 1 <= int(rating) <= 10:
        console.print("[red]оценка 1-10[/red]")
        return
    title = watchlist.rate(num, int(rating))
    if title:
        console.print(f"[green]{title} — {rating}/10[/green]")
    else:
        console.print("[red]нет такого номера в истории[/red]")


def cmd_watchlist_history():
    items = watchlist.watched()
    if not items:
        console.print("[yellow]пока пусто[/yellow]")
        return
    show_history_table(console, items)
    console.print("[dim]N — изменить оценку · q — назад[/dim]")
    while True:
        raw = _prompt("> ")
        if raw.lower() in ("q", "0"):
            return
        if raw.isdigit():
            num = int(raw)
            rating = _prompt(f"Оценка для {items[num - 1]['title']} (1-10): ")
            if rating.isdigit():
                cmd_watchlist_rate(num, rating)
            return


def cmd_watchlist_stats():
    show_stats_table(console, watchlist.stats())


def cmd_series_list():
    items = series.load()
    if not items:
        console.print('[yellow]сериалов нет. vsearch series add «Название»[/yellow]')
        return
    show_series_table(console, items)
    console.print("[dim]N — следующая серия · q — назад[/dim]")
    while True:
        raw = _prompt("> ")
        if raw.lower() in ("q", "0"):
            return
        if raw.isdigit():
            _play_series_num(int(raw))
            return


def _play_series_num(num):
    res = series.query_for_index(num)
    if res is None:
        console.print("[red]нет такого номера[/red]")
        return
    title, query = res
    console.print(f"[bold]{title}[/bold] — ищу: {query}")
    _search_and_select(query, strict=False)
    ans = _prompt("Отметить серию просмотренной? [Y/n]: ").lower()
    if ans not in ("n", "no", "н", "нет"):
        series.mark_done(title)
        console.print("[green]прогресс обновлён[/green]")


def cmd_series_next():
    res = series.next_query()
    if res is None:
        console.print("[yellow]сериалов нет[/yellow]")
        return
    _play_series_num(1)


def cmd_series_add(raw, season=1, episode=1):
    if not raw:
        console.print('[red]пример: vsearch series add «Во все тяжкие» [сезон] [серия][/red]')
        return
    if series.add(raw, season, episode):
        console.print(f"[green]добавлен: {raw} — {season} сезон {episode} серия[/green]")
    else:
        console.print("[yellow]уже есть[/yellow]")


def cmd_series_set(raw, season, episode):
    title = series.set_progress(raw, season, episode)
    if title:
        console.print(f"[green]{title} — {season} сезон {episode} серия[/green]")
    else:
        console.print("[red]сериал не найден[/red]")


def cmd_series_done(raw):
    title = series.mark_done(raw)
    if title:
        console.print(f"[green]отмечено: {title}[/green]")
    else:
        console.print("[red]сериал не найден[/red]")


def cmd_series_del(raw):
    title = series.remove(raw)
    if title:
        console.print(f"[green]удалён: {title}[/green]")
    else:
        console.print("[red]сериал не найден[/red]")


def cmd_player_status():
    s = config.load_settings()
    console.print(
        f"[bold]Upscale:[/bold] {s.get('upscale_mode', 'auto')} · "
        f"[bold]Aspect:[/bold] {s.get('aspect_mode', 'original')}"
    )
    console.print("режимы: vsearch player upscale auto|off|anime|film · aspect original|crop|stretch")


def cmd_player_upscale(mode):
    allowed = ("auto", "off", "anime", "film")
    if mode not in allowed:
        console.print(f"[red]режимы: {', '.join(allowed)}[/red]")
        return
    s = config.load_settings()
    s["upscale_mode"] = mode
    config.save_settings(s)
    console.print(f"[green]upscale: {mode}[/green]")


def cmd_player_aspect(mode):
    allowed = ("original", "crop", "stretch")
    if mode not in allowed:
        console.print(f"[red]режимы: {', '.join(allowed)}[/red]")
        return
    s = config.load_settings()
    s["aspect_mode"] = mode
    config.save_settings(s)
    console.print(f"[green]aspect: {mode}[/green]")


def cmd_refresh():
    config.reset_cache()
    console.print("[green]кэш очищен[/green]")


def cmd_backup():
    from . import backup

    out = backup.create()
    if out:
        console.print(f"[green]бэкап: {out}[/green]")
    else:
        console.print("[red]бэкап не создался[/red]")


def cmd_restore():
    from . import backup

    out = backup.restore()
    if out:
        console.print(f"[green]восстановлено из: {out}[/green]")
    else:
        console.print("[red]бэкапов нет[/red]")


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
        elif raw == "4":
            cmd_watchlist_list()
        elif raw == "5":
            cmd_series_list()
        elif raw == "6":
            cmd_marathon_queue()
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
    sub.add_parser("marathon-queue", help="очередь марафонов")
    sub.add_parser("marathon-next", help="следующая часть из очереди")
    p = sub.add_parser("marathon-add", help="добавить марафон в очередь")
    p.add_argument("name", nargs="+")

    p = sub.add_parser("watch", help="проиграть url или искать фильм")
    p.add_argument("target")

    p = sub.add_parser("list", help="список фильмов")
    sub2 = p.add_subparsers(dest="list_cmd")
    sub2.add_parser("list", help="показать список")
    sub2.add_parser("next", help="смотреть следующий")
    p2 = sub2.add_parser("add", help="добавить фильмы через /")
    p2.add_argument("raw", nargs="+")
    p2 = sub2.add_parser("done", help="отметить просмотренным")
    p2.add_argument("num", type=int)
    p2 = sub2.add_parser("rate", help="оценить из истории")
    p2.add_argument("num", type=int)
    p2.add_argument("rating", type=int)
    sub2.add_parser("history", help="история просмотров")
    sub2.add_parser("stats", help="статистика")

    p = sub.add_parser("series", help="сериалы")
    sub3 = p.add_subparsers(dest="series_cmd")
    sub3.add_parser("list", help="показать сериалы")
    sub3.add_parser("next", help="следующая серия")
    p2 = sub3.add_parser("add", help="добавить сериал")
    p2.add_argument("title", nargs="+")
    p2.add_argument("-s", "--season", type=int, default=1)
    p2.add_argument("-e", "--episode", type=int, default=1)
    p2 = sub3.add_parser("set", help="поставить сезон/серию")
    p2.add_argument("title", nargs="+")
    p2.add_argument("-s", "--season", type=int, default=1)
    p2.add_argument("-e", "--episode", type=int, default=1)
    p2 = sub3.add_parser("done", help="отметить серию просмотренной")
    p2.add_argument("title", nargs="+")
    p2 = sub3.add_parser("del", help="удалить сериал")
    p2.add_argument("title", nargs="+")

    p = sub.add_parser("player", help="режимы проигрывателя")
    sub4 = p.add_subparsers(dest="player_cmd")
    p2 = sub4.add_parser("upscale", help="auto|off|anime|film")
    p2.add_argument("mode")
    p2 = sub4.add_parser("aspect", help="original|crop|stretch")
    p2.add_argument("mode")
    sub4.add_parser("status", help="текущие режимы")

    sub.add_parser("refresh", help="очистить кэш")
    sub.add_parser("backup", help="создать бэкап данных")
    sub.add_parser("restore", help="восстановить из последнего бэкапа")

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
        elif args.cmd == "marathon-queue":
            cmd_marathon_queue()
        elif args.cmd == "marathon-next":
            cmd_marathon_next()
        elif args.cmd == "marathon-add":
            cmd_marathon_add(" ".join(args.name))
        elif args.cmd == "watch":
            cmd_watch(args.target)
        elif args.cmd == "list":
            lc = args.list_cmd or "list"
            if lc == "next":
                cmd_watchlist_next()
            elif lc == "add":
                cmd_watchlist_add(" ".join(args.raw))
            elif lc == "done":
                cmd_watchlist_done(args.num)
            elif lc == "rate":
                cmd_watchlist_rate(args.num, args.rating)
            elif lc == "history":
                cmd_watchlist_history()
            elif lc == "stats":
                cmd_watchlist_stats()
            else:
                cmd_watchlist_list()
        elif args.cmd == "series":
            sc = args.series_cmd or "list"
            if sc == "next":
                cmd_series_next()
            elif sc == "add":
                cmd_series_add(" ".join(args.title), args.season, args.episode)
            elif sc == "set":
                cmd_series_set(" ".join(args.title), args.season, args.episode)
            elif sc == "done":
                cmd_series_done(" ".join(args.title))
            elif sc == "del":
                cmd_series_del(" ".join(args.title))
            else:
                cmd_series_list()
        elif args.cmd == "player":
            pc = args.player_cmd or "status"
            if pc == "upscale":
                cmd_player_upscale(args.mode)
            elif pc == "aspect":
                cmd_player_aspect(args.mode)
            else:
                cmd_player_status()
        elif args.cmd == "refresh":
            cmd_refresh()
        elif args.cmd == "backup":
            cmd_backup()
        elif args.cmd == "restore":
            cmd_restore()
    except KeyboardInterrupt:
        console.print("\n[dim]пока![/dim]")
    except RutubeError as exc:
        console.print(f"[red]{exc}[/red]")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
