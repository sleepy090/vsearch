#!/usr/bin/env python3
import json
import sys
import random
import subprocess
import urllib.parse
from pathlib import Path
from datetime import datetime

import requests
import re

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.align import Align
    from rich.text import Text
    RICH = True
    console = Console()
except Exception:
    RICH = False
    console = None


APP = Path.home() / ".local/share/vsearch"
CFG = Path.home() / ".config/vsearch"

APP.mkdir(parents=True, exist_ok=True)
CFG.mkdir(parents=True, exist_ok=True)

WATCHLIST = APP / "watchlist.json"
MQUEUE = APP / "marathons_queue.json"

MARATHONS_FILE = CFG / "marathons.txt"
ORDERS_FILE = CFG / "orders.txt"
BAD_WORDS_FILE = CFG / "bad_words.txt"
QUOTES_FILE = CFG / "quotes.json"
SETTINGS_FILE = CFG / "settings.json"
MOVIE_HINTS_FILE = CFG / "movie_hints.txt"

RUTUBE_SEARCH = "https://rutube.ru/api/search/video/"


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def load_json(path, fallback):
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def save_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_settings():
    return load_json(SETTINGS_FILE, {
        "min_duration_minutes": 60,
        "results_limit": 20,
        "page_size": 20,
        "open_fullscreen": True,
        "allow_unknown_duration": True
    })


def seq(text):
    return [x.strip() for x in text.split("/") if x.strip()]


def parse_map_file(path):
    if not path.exists():
        return {}
    result = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=>" not in line:
            continue
        key, value = line.split("=>", 1)
        result[key.strip()] = seq(value)
    return result


def load_bad_words():
    if not BAD_WORDS_FILE.exists():
        return []
    return [
        line.strip().lower()
        for line in BAD_WORDS_FILE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def load_quotes():
    return load_json(QUOTES_FILE, {"_generic": ["🎬 Ищу фильм."]})


def load_movie_hints():
    result = {}

    if not MOVIE_HINTS_FILE.exists():
        return result

    for line in MOVIE_HINTS_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()

        if not line or line.startswith("#") or "=>" not in line:
            continue

        title, hints = line.split("=>", 1)
        result[key(title)] = [x.strip() for x in hints.split("/") if x.strip()]

    return result


def hints_for(query):
    q = key(query)
    hints = load_movie_hints()

    for title_key, values in hints.items():
        if q == title_key or title_key in q or q in title_key:
            return values

    return []


def is_series_query(query):
    q = key(query)
    markers = [
        "сезон", "series", "сериал", "doctor who", "доктор кто",
        "симпсоны", "футурама", "рик и морти", "южный парк",
        "гравити фолз", "время приключений"
    ]
    return any(x in q for x in markers)


def search_query_for(query, strict=True):
    q = norm(query)
    hints = hints_for(q)

    year = next((h for h in hints if h.isdigit() and len(h) == 4), None)

    if strict and not is_series_query(q):
        if year and year not in q:
            return f"{q} фильм {year}"
        if "фильм" not in key(q):
            return f"{q} фильм"

    return q


def norm(text):
    return " ".join(str(text).strip().split())


def key(text):
    return norm(text).lower().replace("ё", "е")


def banner():
    if RICH:
        title = Text()
        title.append("🎬 vsearch\n", style="bold cyan")
        title.append("CLI-кино-комбайн для Linux", style="dim")
        console.print(Panel(Align.center(title), border_style="cyan"))
    else:
        print("\n🎬 vsearch — CLI-кино-комбайн\n")


def bar(done, total, width=22):
    if total <= 0:
        return "░" * width
    filled = int(width * (done / total))
    return "█" * filled + "░" * (width - filled)


def watchlist():
    return load_json(WATCHLIST, [])


def save_watchlist(data):
    save_json(WATCHLIST, data)


def mqueue():
    return load_json(MQUEUE, [])


def save_mqueue(data):
    save_json(MQUEUE, data)


def unwatched():
    return [x for x in watchlist() if not x.get("watched")]


def watched():
    return [x for x in watchlist() if x.get("watched")]


def marathons():
    return parse_map_file(MARATHONS_FILE)


def orders():
    return parse_map_file(ORDERS_FILE)


def all_franchises():
    result = []
    for cat, titles in marathons().items():
        for title in titles:
            result.append((cat, title))
    return result


def find_franchise(query):
    q = key(query)

    for cat, title in all_franchises():
        t = key(title)
        if q == t or q in t:
            return cat, title

    for title in orders().keys():
        t = key(title)
        if q == t or q in t:
            return "Другое", title

    return None, None


def order_for(title):
    return orders().get(title, [title])


def movie_quote(query):
    q = key(query)
    quotes = load_quotes()

    for k, lines in quotes.items():
        if k == "_generic":
            continue
        kk = key(k)
        if kk in q or q in kk:
            return random.choice(lines)

    return random.choice(quotes.get("_generic", ["🎬 Ищу фильм."]))


def parse_duration(value):
    if value is None:
        return 0

    if isinstance(value, (int, float)):
        return int(value)

    text = str(value).strip()

    if text.isdigit():
        return int(text)

    try:
        parts = [int(x) for x in text.split(":")]
    except Exception:
        return 0

    if len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]

    if len(parts) == 2:
        return parts[0] * 60 + parts[1]

    return 0


def is_bad_result(title, query="", strict=True):
    low = title.lower()
    q = key(query)

    base_bad = load_bad_words()

    strict_bad = [
        "заставка", "интро", "intro", "опенинг", "opening", "эндинг", "ending",
        "прохождение", "полное прохождение", "gameplay", "летсплей", "letsplay",
        "let's play", "стрим", "stream", "игрофильм", "аудиокнига", "аудиокниги",
        "озвучка", "мод", "модификация", "anomaly", "gamma",
        "shadow of chernobyl", "зов припяти", "чистое небо",
        "сердце чернобыля", "heart of chornobyl", "stalker 2", "s.t.a.l.k.e.r",
        "100 дней", "эдит", "edit", "shorts", "short", "нарезка", "фрагмент",
        "отрывок", "сцена", "лучшие сцены", "лучшие моменты", "обзор", "реакция",
        "разбор", "пересказ", "кратко", "объяснение", "ost", "саундтрек", "клип"
    ]

    words = base_bad + strict_bad if strict else base_bad

    # Для игровых названий особенно режем игровые результаты.
    if "сталкер" in q:
        stalker_game_bad = [
            "прохождение", "stalker 2", "s.t.a.l.k.e.r", "сердце чернобыля",
            "heart of chornobyl", "shadow of chernobyl", "зов припяти",
            "чистое небо", "anomaly", "gamma", "мод", "игрофильм"
        ]
        words += stalker_game_bad

    return any(word in low for word in words)


def result_score(movie_query, video_title, duration):
    q = key(movie_query)
    t = key(video_title)
    hints = hints_for(movie_query)
    score = 0

    # точность названия
    if q == t:
        score += 100
    elif q in t:
        score += 65

    q_words = [w for w in q.split() if len(w) > 2]
    matched = 0

    for w in q_words:
        if w in t:
            matched += 1
            score += 6

    if q_words and matched == len(q_words):
        score += 25

    # подсказки: год, режиссёр, альтернативное название
    for hint in hints:
        h = key(hint)
        if h and h in t:
            if hint.isdigit() and len(hint) == 4:
                score += 90
            else:
                score += 35

    # признаки настоящего фильма
    good_words = [
        "фильм", "полный фильм", "смотреть онлайн", "реж.", "режиссер",
        "режиссёр", "андрей тарковский", "4к", "4k", "hd", "1080", "720"
    ]

    for w in good_words:
        if key(w) in t:
            score += 8

    # длительность
    if duration >= 60 * 60:
        score += 45
    elif 40 * 60 <= duration < 60 * 60:
        score += 10
    elif 0 < duration < 40 * 60:
        score -= 80
    elif duration == 0:
        score -= 5

    # мусор
    bad_hints = [
        "заставка", "интро", "опенинг", "ending", "эндинг",
        "трейлер", "тизер", "обзор", "реакция", "разбор",
        "пересказ", "нарезка", "сцена", "фрагмент", "отрывок",
        "эдит", "edit", "shorts", "клип", "ost", "саундтрек",
        "прохождение", "gameplay", "летсплей", "стрим", "игрофильм",
        "аудиокнига", "озвучка", "мод", "anomaly", "gamma"
    ]

    for w in bad_hints:
        if w in t:
            score -= 160

    # отдельный жёсткий случай: фильм «Сталкер» vs игры S.T.A.L.K.E.R.
    if "сталкер" in q:
        game_words = [
            "stalker 2", "s.t.a.l.k.e.r", "сердце чернобыля",
            "heart of chornobyl", "shadow of chernobyl", "зов припяти",
            "чистое небо", "anomaly", "gamma", "прохождение", "игрофильм"
        ]

        if any(w in t for w in game_words):
            score -= 250

        if "1979" in t or "тарковский" in t:
            score += 150

    # если ищем базовый фильм без номера, не поднимать сиквелы выше оригинала
    base_shrek_query = q in ["шрек", "shrek"]
    if base_shrek_query:
        if "2001" in t:
            score += 120
        sequel_words = [
            "шрек 2", "shrek 2", "шрек третий", "shrek the third",
            "шрек 3", "шрек навсегда", "shrek forever after",
            "шрек 4", "2010", "2007", "2004"
        ]
        if any(w in t for w in sequel_words):
            score -= 180

    return score


def search_rutube(query, strict=True):
    settings = load_settings()
    min_duration = int(settings.get("min_duration_minutes", 60)) * 60
    limit = int(settings.get("results_limit", 20))
    allow_unknown = bool(settings.get("allow_unknown_duration", True))
    final_query = search_query_for(query, strict=strict)

    try:
        r = requests.get(
            RUTUBE_SEARCH,
            params={"query": final_query, "page": 1, "limit": limit},
            timeout=12,
            headers={"User-Agent": "Mozilla/5.0 vsearch"}
        )
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"❌ Ошибка поиска Rutube: {e}")
        return []

    videos = []

    for item in data.get("results", []):
        title = item.get("title") or "Без названия"

        if is_bad_result(title, query=query, strict=strict):
            continue

        url = item.get("video_url") or item.get("html_url") or item.get("url")

        if not url and item.get("id"):
            url = f"https://rutube.ru/video/{item.get('id')}/"

        duration_raw = item.get("duration") or item.get("duration_string") or item.get("video_duration")
        duration = parse_duration(duration_raw)

        if strict:
            if duration and duration < min_duration:
                continue
            if duration == 0 and not allow_unknown:
                continue

        if url:
            videos.append({
                "title": title,
                "url": url,
                "duration": duration_raw or "??",
                "score": result_score(query, title, duration)
            })

    videos.sort(key=lambda x: x["score"], reverse=True)
    return videos


def choose_video(videos):
    settings = load_settings()

    if settings.get("auto_select_best", True) and videos:
        threshold = int(settings.get("auto_select_threshold", 85))
        gap = int(settings.get("auto_select_gap", 12))
        first = videos[0].get("score", 0)
        second = videos[1].get("score", -999) if len(videos) > 1 else -999

        if first >= threshold and first - second >= gap:
            print(f"✅ Автовыбор: {videos[0]['title']} [{videos[0]['duration']}] score={first}")
            return 0

    if RICH:
        table = Table(title="🔎 Найдено", border_style="cyan")
        table.add_column("№", justify="right", style="bold cyan")
        table.add_column("Название", style="bold white")
        table.add_column("Длительность", style="yellow")
        table.add_column("Score", justify="right", style="dim")

        for i, video in enumerate(videos, 1):
            table.add_row(str(i), video["title"], str(video["duration"]), str(video.get("score", 0)))

        console.print(table)
    else:
        print("Найдено:\n")
        for i, video in enumerate(videos, 1):
            print(f"{i}. {video['title']} [{video['duration']}]")

    choice = input("\nEnter = первый результат | номер = выбрать | 0 = отмена: ").strip()

    if choice == "0":
        return None

    if not choice:
        return 0

    if choice.isdigit() and 1 <= int(choice) <= len(videos):
        return int(choice) - 1

    print("❌ Неверный номер.")
    return None


def play_query(query, strict=True):
    banner()

    if RICH:
        console.print(Panel(movie_quote(query), title="🍿 Реплика", border_style="magenta"))
        console.print(f"[bold cyan]🔎 Ищу на Rutube:[/] {query}\n")
    else:
        print("\n" + movie_quote(query))
        print(f"🔎 Ищу на Rutube: {query}\n")

    videos = search_rutube(query, strict=strict)

    if not videos:
        print("❌ Ничего нормального не нашёл.")
        print("Поиск вручную:")
        print("https://rutube.ru/search/?query=" + urllib.parse.quote(query))
        return False

    idx = choose_video(videos)

    if idx is None:
        return False

    url = videos[idx]["url"]
    args = build_mpv_args(url, title=query)

    st = load_settings()
    real_upscale = effective_upscale_mode(query)
    print(f"\n⚙️ Upscale: {st.get('upscale_mode', 'auto')} → {real_upscale} | Aspect: {st.get('aspect_mode', 'original')}")
    print(f"▶️ Открываю:\n{url}\n")
    subprocess.run(args)

    return True


def show_watchlist_once(items=None, page=0, filter_text=""):
    source = items if items is not None else unwatched()
    page_size = int(load_settings().get("page_size", 20))

    if filter_text:
        filtered = [
            (idx, item)
            for idx, item in enumerate(unwatched(), 1)
            if key(filter_text) in key(item["title"])
        ]
    else:
        filtered = list(enumerate(unwatched(), 1))

    total_pages = max(1, (len(filtered) + page_size - 1) // page_size)
    page = max(0, min(page, total_pages - 1))
    visible = filtered[page * page_size:(page + 1) * page_size]

    banner()

    if RICH:
        subtitle = f"Страница {page + 1}/{total_pages}"
        if filter_text:
            subtitle += f" | фильтр: {filter_text}"

        table = Table(title=f"🎬 Список фильмов — {subtitle}", border_style="cyan")
        table.add_column("№", justify="right", style="bold cyan", width=5)
        table.add_column("Фильм", style="bold white")
        table.add_column("Статус", justify="center")

        for real_num, item in visible:
            table.add_row(str(real_num), item["title"], "⬜ ждёт")

        console.print(table)
        console.print(Panel(
            "[bold cyan]номер[/] — включить фильм по номеру\n"
            "[bold cyan]/текст[/] — фильтр по названию\n"
            "[bold cyan]n[/] — следующая страница | [bold cyan]p[/] — прошлая\n"
            "[bold cyan]done 132[/] — отметить просмотренным\n"
            "[bold cyan]clear[/] — убрать фильтр | [bold cyan]b[/] — назад",
            title="Управление",
            border_style="magenta"
        ))
    else:
        print(f"\n🎬 Список фильмов — страница {page + 1}/{total_pages}\n")
        for real_num, item in visible:
            print(f"{real_num}. {item['title']}")
        print("\nномер = включить | /текст = фильтр | n/p = страницы | b = назад")

    return page, total_pages, filtered


def browse_watchlist():
    page = 0
    filter_text = ""

    while True:
        page, total_pages, filtered = show_watchlist_once(page=page, filter_text=filter_text)
        cmd = input("\nВыбор: ").strip()

        if not cmd:
            continue

        low = cmd.lower()

        if low in ["b", "back", "q", "quit", "0"]:
            return

        if low == "n":
            page = min(page + 1, total_pages - 1)
            continue

        if low == "p":
            page = max(page - 1, 0)
            continue

        if low == "clear":
            filter_text = ""
            page = 0
            continue

        if cmd.startswith("/"):
            filter_text = cmd[1:].strip()
            page = 0
            continue

        if low.startswith("done "):
            n = low.split(maxsplit=1)[1]
            if n.isdigit():
                mark_done(int(n))
            continue

        if cmd.isdigit():
            play_movie(int(cmd))
            continue

        print("❌ Не понял команду.")


def show_watchlist():
    db = watchlist()
    done = len([x for x in db if x.get("watched")])
    total = len(db)
    items = unwatched()

    banner()

    if RICH:
        console.print(Panel(
            f"[bold]Всего:[/] {total}   [green]Просмотрено:[/] {done}   "
            f"[yellow]Осталось:[/] {len(items)}   [cyan]{bar(done, total)}[/]",
            title="📊 Прогресс",
            border_style="blue"
        ))

    browse_watchlist()


def add_movies(raw):
    db = watchlist()
    existing = {x["title"].lower() for x in db}
    movies = [norm(x) for x in raw.replace("\n", "/").split("/") if norm(x)]
    added = 0

    for movie in movies:
        if movie.lower() in existing:
            continue

        db.append({
            "title": movie,
            "watched": False,
            "added_at": now(),
            "watched_at": None,
            "rating": None
        })

        existing.add(movie.lower())
        added += 1

    save_watchlist(db)
    print(f"✅ Добавлено: {added}")


def play_movie(num=1):
    items = unwatched()

    if num < 1 or num > len(items):
        print("❌ Нет такого номера.")
        return

    title = items[num - 1]["title"]

    if play_query(title, strict=True):
        answer = input("\nОтметить просмотренным? [y/N]: ").strip().lower()
        if answer in ["y", "yes", "д", "да"]:
            mark_done(num)


def mark_done(num):
    db = watchlist()
    items = [x for x in db if not x.get("watched")]

    if num < 1 or num > len(items):
        print("❌ Нет такого номера.")
        return

    item = items[num - 1]
    item["watched"] = True
    item["watched_at"] = now()

    rating = input("Оценка 1–10, Enter чтобы пропустить: ").strip()
    if rating.isdigit() and 1 <= int(rating) <= 10:
        item["rating"] = int(rating)

    save_watchlist(db)
    print(f"✅ Просмотрено: {item['title']}")

    if len(watched()) and len(watched()) % 10 == 0:
        print(f"\n🔥 Уже {len(watched())} фильмов. Не забудь занести оценки в Letterboxd.\n")
        show_history()


def rate_movie(num, rating):
    db = watchlist()
    items = [x for x in db if x.get("watched")]

    if num < 1 or num > len(items):
        print("❌ Нет такого номера в истории.")
        return

    if rating < 1 or rating > 10:
        print("❌ Оценка должна быть от 1 до 10.")
        return

    items[num - 1]["rating"] = rating
    save_watchlist(db)
    print(f"⭐ {items[num - 1]['title']} — {rating}/10")


def show_history():
    items = watched()
    banner()

    if not items:
        print("Пока пусто.")
        return

    if RICH:
        table = Table(title="✅ История просмотров", border_style="green")
        table.add_column("№", justify="right", style="bold cyan")
        table.add_column("Фильм", style="bold white")
        table.add_column("Оценка", style="yellow")
        table.add_column("Дата", style="dim")

        for i, item in enumerate(items, 1):
            rating = f"{item.get('rating')}/10" if item.get("rating") else "без оценки"
            table.add_row(str(i), item["title"], rating, item.get("watched_at") or "—")

        console.print(table)
    else:
        for i, item in enumerate(items, 1):
            rating = f"{item.get('rating')}/10" if item.get("rating") else "без оценки"
            print(f"{i}. {item['title']} — {rating}")


def show_stats():
    db = watchlist()
    total = len(db)
    done = len([x for x in db if x.get("watched")])
    left = total - done
    rated = [x for x in db if x.get("rating")]
    avg = round(sum(int(x["rating"]) for x in rated) / len(rated), 2) if rated else "нет"
    queue = mqueue()
    percent = round(done / total * 100, 1) if total else 0

    banner()

    if RICH:
        table = Table(title="📊 Статистика vsearch", border_style="green")
        table.add_column("Параметр", style="bold cyan")
        table.add_column("Значение", style="bold white")

        table.add_row("Фильмов всего", str(total))
        table.add_row("Просмотрено", str(done))
        table.add_row("Осталось", str(left))
        table.add_row("Прогресс", f"{percent}%  {bar(done, total)}")
        table.add_row("Оценок поставлено", str(len(rated)))
        table.add_row("Средняя оценка", str(avg))
        table.add_row("Марафонов в очереди", str(len(queue)))

        console.print(table)
    else:
        print(f"Фильмов всего: {total}")
        print(f"Просмотрено: {done}")
        print(f"Осталось: {left}")
        print(f"Прогресс: {percent}%")
        print(f"Средняя оценка: {avg}")
        print(f"Марафонов в очереди: {len(queue)}")


def show_all():
    db = watchlist()
    banner()

    if not db:
        print("Список пуст.")
        return

    for i, item in enumerate(db, 1):
        mark = "✅" if item.get("watched") else "⬜"
        rating = f" — {item.get('rating')}/10" if item.get("rating") else ""
        print(f"{i}. {mark} {item['title']}{rating}")


def show_order(title):
    order = order_for(title)
    banner()

    if RICH:
        table = Table(title=f"🎞 Порядок марафона: {title}", border_style="cyan")
        table.add_column("№", justify="right", style="bold cyan")
        table.add_column("Часть", style="bold white")

        for i, part in enumerate(order, 1):
            table.add_row(str(i), part)

        console.print(table)
    else:
        for i, part in enumerate(order, 1):
            print(f"{i}. {part}")


def menu_marathons():
    cats = list(marathons().keys())

    while True:
        banner()

        if RICH:
            table = Table(title="🏁 Марафоны", border_style="cyan")
            table.add_column("№", justify="right", style="bold cyan")
            table.add_column("Категория", style="bold white")
            table.add_column("Франшиз", justify="right", style="yellow")

            for i, cat in enumerate(cats, 1):
                table.add_row(str(i), cat, str(len(marathons()[cat])))

            table.add_row("0", "Выход", "")
            console.print(table)
        else:
            for i, cat in enumerate(cats, 1):
                print(f"{i}. {cat} ({len(marathons()[cat])})")
            print("0. Выход")

        choice = input("\nКатегория: ").strip()

        if choice == "0":
            return

        if not choice.isdigit() or not (1 <= int(choice) <= len(cats)):
            print("❌ Неверный номер.")
            continue

        cat = cats[int(choice) - 1]
        franchises = marathons()[cat]

        while True:
            banner()

            if RICH:
                table = Table(title=f"🏁 {cat}", border_style="magenta")
                table.add_column("№", justify="right", style="bold cyan")
                table.add_column("Франшиза", style="bold white")

                for i, title in enumerate(franchises, 1):
                    table.add_row(str(i), title)

                table.add_row("0", "Назад")
                console.print(table)
            else:
                for i, title in enumerate(franchises, 1):
                    print(f"{i}. {title}")
                print("0. Назад")

            f = input("\nФраншиза: ").strip()

            if f == "0":
                break

            if not f.isdigit() or not (1 <= int(f) <= len(franchises)):
                print("❌ Неверный номер.")
                continue

            title = franchises[int(f) - 1]

            while True:
                banner()

                if RICH:
                    console.print(Panel(
                        "1. Показать порядок просмотра\n"
                        "2. Включить первую часть\n"
                        "3. Добавить марафон в очередь\n"
                        "4. Включить следующую часть из очереди\n"
                        "0. Назад",
                        title=f"🎬 {title}",
                        border_style="green"
                    ))
                else:
                    print("1. Показать порядок")
                    print("2. Включить первую часть")
                    print("3. Добавить в очередь")
                    print("4. Включить следующую часть из очереди")
                    print("0. Назад")

                action = input("\nДействие: ").strip()

                if action == "0":
                    break
                elif action == "1":
                    show_order(title)
                    input("\nEnter...")
                elif action == "2":
                    play_marathon_direct(title)
                elif action == "3":
                    add_marathon(title)
                    input("\nEnter...")
                elif action == "4":
                    play_next_marathon()
                else:
                    print("❌ Нет такого действия.")


def show_category(query):
    cats = list(marathons().keys())
    cat = None

    if query.isdigit() and 1 <= int(query) <= len(cats):
        cat = cats[int(query) - 1]
    else:
        q = query.lower()
        for c in cats:
            if q in c.lower():
                cat = c
                break

    if not cat:
        print("❌ Категория не найдена.")
        return

    for i, title in enumerate(marathons()[cat], 1):
        print(f"{i}. {title}")


def add_marathon(query):
    cat, title = find_franchise(query)

    if not title:
        title = query.strip()
        cat = "Другое"

    q = mqueue()

    if any(x["title"].lower() == title.lower() and not x.get("done") for x in q):
        print(f"⚠️ Уже в очереди: {title}")
        return

    q.append({
        "title": title,
        "category": cat,
        "current_index": 0,
        "done": False,
        "added_at": now(),
        "done_at": None,
        "rating": None
    })

    save_mqueue(q)
    print(f"✅ Марафон добавлен: {title}")


def show_mqueue():
    q = mqueue()
    banner()

    active = [x for x in q if not x.get("done")]
    done = [x for x in q if x.get("done")]

    if not active and not done:
        print('Пусто. Добавить: vsearch -madd "Звёздные войны"')
        return

    if RICH:
        table = Table(title="🏁 Очередь марафонов", border_style="cyan")
        table.add_column("№", justify="right", style="bold cyan")
        table.add_column("Марафон", style="bold white")
        table.add_column("Прогресс", style="yellow")
        table.add_column("Сейчас", style="green")

        for i, item in enumerate(active, 1):
            order = order_for(item["title"])
            idx = int(item.get("current_index", 0))
            current = order[idx] if idx < len(order) else "завершён"
            table.add_row(str(i), item["title"], f"{idx + 1}/{len(order)}", current)

        console.print(table)
    else:
        for i, item in enumerate(active, 1):
            order = order_for(item["title"])
            idx = int(item.get("current_index", 0))
            current = order[idx] if idx < len(order) else "завершён"
            print(f"{i}. {item['title']} — {idx + 1}/{len(order)}: {current}")

    if done:
        print("\nПройденные:")
        for item in done:
            rating = f" — {item.get('rating')}/10" if item.get("rating") else ""
            print(f"✅ {item['title']}{rating}")


def play_marathon_direct(query):
    _, title = find_franchise(query)

    if not title:
        title = query.strip()

    order = order_for(title)
    episode = order[0]

    print(f"\n🏁 {title}")
    print(f"▶️ Часть 1/{len(order)}: {episode}")

    play_query(episode, strict=not is_series_query(episode))


def play_next_marathon():
    q = mqueue()
    active = [x for x in q if not x.get("done")]

    if not active:
        print("❌ Очередь марафонов пустая.")
        return

    item = active[0]
    title = item["title"]
    order = order_for(title)
    idx = int(item.get("current_index", 0))

    if idx >= len(order):
        item["done"] = True
        save_mqueue(q)
        print("✅ Марафон уже завершён.")
        return

    episode = order[idx]

    print(f"\n🏁 {title}")
    print(f"▶️ Часть {idx + 1}/{len(order)}: {episode}")

    if play_query(episode, strict=not is_series_query(episode)):
        answer = input("\nОтметить эту часть просмотренной? [y/N]: ").strip().lower()

        if answer in ["y", "yes", "д", "да"]:
            item["current_index"] = idx + 1

            if item["current_index"] >= len(order):
                item["done"] = True
                item["done_at"] = now()

                rating = input("Марафон завершён. Оценка 1–10, Enter чтобы пропустить: ").strip()
                if rating.isdigit() and 1 <= int(rating) <= 10:
                    item["rating"] = int(rating)

                print(f"🏆 Марафон завершён: {title}")
            else:
                print(f"✅ Следующая часть: {order[item['current_index']]}")

            save_mqueue(q)


def mark_marathon_done(num):
    q = mqueue()
    active = [x for x in q if not x.get("done")]

    if num < 1 or num > len(active):
        print("❌ Нет такого марафона.")
        return

    item = active[num - 1]
    item["done"] = True
    item["done_at"] = now()
    item["current_index"] = len(order_for(item["title"]))

    save_mqueue(q)
    print(f"✅ Марафон пройден: {item['title']}")


def main_menu():
    while True:
        db = watchlist()
        total = len(db)
        done = len([x for x in db if x.get("watched")])
        left = total - done

        banner()

        if RICH:
            console.print(Panel(
                f"[bold]Фильмов всего:[/] {total}\n"
                f"[green]Просмотрено:[/] {done}\n"
                f"[yellow]Осталось:[/] {left}\n"
                f"[cyan]Прогресс:[/] {bar(done, total)}",
                title="📊 Краткая статистика",
                border_style="green"
            ))

            table = Table(title="Главное меню", border_style="cyan")
            table.add_column("№", justify="right", style="bold cyan", width=4)
            table.add_column("Действие", style="bold white")

            rows = [
                ("1", "▶️ Смотреть следующий фильм"),
                ("2", "🎬 Список фильмов с выбором номера"),
                ("3", "➕ Добавить фильмы"),
                ("4", "🏁 Марафоны"),
                ("5", "📜 История просмотров"),
                ("6", "📊 Статистика"),
                ("7", "🏁 Очередь марафонов"),
                ("0", "🚪 Выход"),
            ]

            for number, text in rows:
                table.add_row(number, text)

            console.print(table)
        else:
            print("1. Смотреть следующий фильм")
            print("2. Список фильмов с выбором номера")
            print("3. Добавить фильмы")
            print("4. Марафоны")
            print("5. История просмотров")
            print("6. Статистика")
            print("7. Очередь марафонов")
            print("0. Выход")

        choice = input("\nВыбери действие: ").strip()

        if choice == "0":
            return
        elif choice == "1":
            play_movie(1)
        elif choice == "2":
            show_watchlist()
        elif choice == "3":
            raw = input('Фильмы через "/": ').strip()
            if raw:
                add_movies(raw)
        elif choice == "4":
            menu_marathons()
        elif choice == "5":
            show_history()
            input("\nEnter чтобы вернуться...")
        elif choice == "6":
            show_stats()
            input("\nEnter чтобы вернуться...")
        elif choice == "7":
            show_mqueue()
            input("\nEnter чтобы вернуться...")
        else:
            print("❌ Нет такого пункта.")




def extract_year_from_text(text):
    m = re.search(r'\b(19[0-9]{2}|20[0-2][0-9])\b', str(text))
    if not m:
        return None
    try:
        return int(m.group(1))
    except Exception:
        return None


def year_from_hints(query):
    for hint in hints_for(query):
        if str(hint).isdigit() and len(str(hint)) == 4:
            return int(hint)
    return None


def detect_auto_upscale_mode(title):
    q = key(title)

    animation_words = [
        "мультфильм", "аниме", "animation", "animated",
        "шрек", "shrek",
        "история игрушек", "toy story",
        "корпорация монстров", "monsters inc", "университет монстров",
        "как приручить дракона",
        "кунг-фу панда",
        "ледниковый период",
        "гадкий я", "миньоны",
        "мадагаскар",
        "тачки",
        "суперсемейка",
        "монстры на каникулах",
        "в поисках немо", "в поисках дори",
        "ральф",
        "зверополис",
        "призрак в доспехах",
        "акира",
        "паприка",
        "идеальная грусть",
        "метрополис",
        "аниматрица",
        "ковбой бибоп",
        "ангельское яйцо",
        "навсикая",
        "евангелион"
    ]

    if any(w in q for w in animation_words):
        return "anime"

    year = year_from_hints(title) or extract_year_from_text(title)

    if year and year <= 2005:
        return "film"

    old_film_words = [
        "тарковский", "кубри",
        "линч", "карпентер", "кроненберг",
        "скорсезе", "балабанов",
        "солярис", "сталкер", "робокоп", "чужой", "чужие",
        "терминатор", "видеодром", "таксист",
        "бегущий по лезвию", "назад в будущее",
        "безумный макс", "кин-дза-дза", "брат"
    ]

    if any(w in q for w in old_film_words):
        return "film"

    return "off"


def effective_upscale_mode(title):
    st = load_settings()
    mode = st.get("upscale_mode", "auto")

    if mode == "auto":
        return detect_auto_upscale_mode(title)

    return mode


def shader_path(value):
    if not value:
        return None

    path = Path(str(value)).expanduser()
    return path if path.exists() else None


def build_mpv_args(target, title=None):
    st = load_settings()

    args = ["mpv"]

    if st.get("open_fullscreen", True):
        args.append("--fs")

    args.append("--force-window=yes")

    title_for_detect = title or target

    upscale = effective_upscale_mode(title_for_detect)
    aspect = st.get("aspect_mode", "original")

    if upscale == "anime":
        restore = shader_path(st.get("anime4k_restore_shader"))
        upscale_shader = shader_path(st.get("anime4k_upscale_shader"))

        if restore:
            args.append(f"--glsl-shader={restore}")

        if upscale_shader:
            args.append(f"--glsl-shader={upscale_shader}")

        args.extend([
            "--scale=ewa_lanczossharp",
            "--cscale=ewa_lanczossharp",
            "--dscale=mitchell",
            "--correct-downscaling=yes",
            "--sigmoid-upscaling=yes"
        ])

    elif upscale == "film":
        args.extend([
            "--scale=ewa_lanczossharp",
            "--cscale=ewa_lanczossoft",
            "--dscale=mitchell",
            "--correct-downscaling=yes",
            "--sigmoid-upscaling=yes",
            "--deband=yes",
            "--deband-iterations=2",
            "--deband-threshold=48",
            "--deband-range=16",
            "--deband-grain=24",
            "--vf-add=lavfi=[unsharp=5:5:0.6:3:3:0.3]"
        ])

    if aspect == "crop":
        args.append("--panscan=1.0")

    elif aspect == "stretch":
        args.append("--video-aspect-override=16:9")

    args.append(str(target))
    return args



def show_video_modes():
    st = load_settings()

    upscale = st.get("upscale_mode", "off")
    aspect = st.get("aspect_mode", "original")

    banner()

    if RICH:
        table = Table(title="⚙️ Видео-режимы", border_style="cyan")
        table.add_column("Режим", style="bold cyan")
        table.add_column("Значение", style="bold white")
        table.add_row("Upscale", upscale)
        table.add_row("Aspect", aspect)
        console.print(table)

        console.print(Panel(
            "[bold cyan]vsearch -upscale off[/] — без апскейла\n"
            "[bold cyan]vsearch -upscale anime[/] — Anime4K для аниме\n"
            "[bold cyan]vsearch -upscale film[/] — мягкий режим для старых фильмов\n\n"
            "[bold cyan]vsearch -aspect original[/] — оригинальный кадр\n"
            "[bold cyan]vsearch -aspect crop[/] — заполнить экран без растяга\n"
            "[bold cyan]vsearch -aspect stretch[/] — растянуть до 16:9",
            title="Команды",
            border_style="magenta"
        ))
    else:
        print(f"Upscale: {upscale}")
        print(f"Aspect: {aspect}")


def set_upscale_mode(mode):
    allowed = ["auto", "off", "anime", "film", "status"]

    if mode not in allowed:
        print("❌ Режимы: auto / off / anime / film / status")
        return

    if mode == "status":
        show_video_modes()
        return

    st = load_settings()
    st["upscale_mode"] = mode
    save_json(SETTINGS_FILE, st)

    print(f"✅ Upscale режим: {mode}")


def set_aspect_mode(mode):
    allowed = ["original", "crop", "stretch", "status"]

    if mode not in allowed:
        print("❌ Режимы: original / crop / stretch / status")
        return

    if mode == "status":
        show_video_modes()
        return

    st = load_settings()
    st["aspect_mode"] = mode
    save_json(SETTINGS_FILE, st)

    print(f"✅ Aspect режим: {mode}")


def video_modes_menu():
    while True:
        show_video_modes()

        print("\n1. Upscale: auto")
        print("2. Upscale: off")
        print("3. Upscale: anime")
        print("4. Upscale: film")
        print("5. Aspect: original")
        print("6. Aspect: crop")
        print("7. Aspect: stretch")
        print("0. Назад")

        choice = input("\nВыбор: ").strip()

        if choice == "0":
            return
        elif choice == "1":
            set_upscale_mode("auto")
        elif choice == "2":
            set_upscale_mode("off")
        elif choice == "3":
            set_upscale_mode("anime")
        elif choice == "4":
            set_upscale_mode("film")
        elif choice == "5":
            set_aspect_mode("original")
        elif choice == "6":
            set_aspect_mode("crop")
        elif choice == "7":
            set_aspect_mode("stretch")
        else:
            print("❌ Нет такого пункта.")

        input("\nEnter...")



SERIES_DB = Path.home() / ".local/share/vsearch/series.json"


def load_series():
    if not SERIES_DB.exists():
        return []

    try:
        return json.loads(SERIES_DB.read_text(encoding="utf-8"))
    except Exception:
        return []


def save_series(data):
    SERIES_DB.parent.mkdir(parents=True, exist_ok=True)
    SERIES_DB.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def series_key(text):
    return " ".join(str(text).lower().replace("ё", "е").split())


def find_series_index(title):
    q = series_key(title)
    data = load_series()

    for i, item in enumerate(data):
        name = series_key(item.get("title", ""))

        if q == name or q in name or name in q:
            return i

    return None


def episode_query(item):
    title = item.get("title", "")
    season = int(item.get("season", 1))
    episode = int(item.get("episode", 1))
    template = item.get("template", "{title} {season} сезон {episode} серия")

    return template.format(
        title=title,
        season=season,
        episode=episode,
        s=season,
        e=episode
    )


def show_series():
    data = load_series()
    banner()

    if not data:
        print('Сериалов пока нет. Добавить: vsearch -sadd "Во все тяжкие"')
        return

    if RICH:
        table = Table(title="📺 Сериалы", border_style="cyan")
        table.add_column("№", justify="right", style="bold cyan")
        table.add_column("Название", style="bold white")
        table.add_column("Следующая серия", style="yellow")
        table.add_column("Просмотрено", justify="right", style="green")

        for i, item in enumerate(data, 1):
            table.add_row(
                str(i),
                item.get("title", "Без названия"),
                f'{item.get("season", 1)} сезон {item.get("episode", 1)} серия',
                str(item.get("watched", 0))
            )

        console.print(table)
    else:
        for i, item in enumerate(data, 1):
            print(f'{i}. {item.get("title")} — {item.get("season", 1)} сезон {item.get("episode", 1)} серия')


def add_series(title, season=1, episode=1):
    data = load_series()

    if find_series_index(title) is not None:
        print("⚠️ Такой сериал уже есть.")
        return

    data.append({
        "title": title,
        "season": int(season),
        "episode": int(episode),
        "watched": 0,
        "added_at": now(),
        "last_watched_at": None,
        "template": "{title} {season} сезон {episode} серия"
    })

    save_series(data)
    print(f"✅ Сериал добавлен: {title} — {season} сезон {episode} серия")


def set_series_progress(title, season, episode):
    data = load_series()
    idx = find_series_index(title)

    if idx is None:
        print("❌ Сериал не найден.")
        return

    data[idx]["season"] = int(season)
    data[idx]["episode"] = int(episode)

    save_series(data)
    print(f'✅ Прогресс обновлён: {data[idx]["title"]} — {season} сезон {episode} серия')


def mark_series_done(title):
    data = load_series()
    idx = find_series_index(title)

    if idx is None:
        print("❌ Сериал не найден.")
        return

    item = data[idx]

    item["watched"] = int(item.get("watched", 0)) + 1
    item["last_watched_at"] = now()

    # простая логика: после серии +1
    item["episode"] = int(item.get("episode", 1)) + 1

    save_series(data)

    print(f'✅ Отмечено просмотренным: {item["title"]}')
    print(f'Следующая: {item["season"]} сезон {item["episode"]} серия')


def play_next_series(title=None):
    data = load_series()

    if not data:
        print('Сериалов нет. Добавить: vsearch -sadd "Название"')
        return

    if title:
        idx = find_series_index(title)
    else:
        show_series()
        raw = input("\nНомер сериала | Enter = первый | 0 = отмена: ").strip()

        if raw == "0":
            return

        if not raw:
            idx = 0
        elif raw.isdigit() and 1 <= int(raw) <= len(data):
            idx = int(raw) - 1
        else:
            print("❌ Неверный номер.")
            return

    if idx is None:
        print("❌ Сериал не найден.")
        return

    item = data[idx]
    query = episode_query(item)

    print(f'\n📺 {item["title"]}')
    print(f'▶️ Ищу: {query}')

    # Для сериалов strict=False, потому что серия может быть короче фильма.
    if play_query(query, strict=False):
        ans = input("\nОтметить серию просмотренной? [Y/n]: ").strip().lower()

        if ans not in ["n", "no", "н", "нет"]:
            mark_series_done(item["title"])


def delete_series(title):
    data = load_series()
    idx = find_series_index(title)

    if idx is None:
        print("❌ Сериал не найден.")
        return

    item = data.pop(idx)
    save_series(data)

    print(f'🗑 Удалено: {item["title"]}')


def series_menu():
    while True:
        banner()

        if RICH:
            console.print(Panel(
                "1. 📺 Показать сериалы\n"
                "2. ▶️ Включить следующую серию\n"
                "3. ➕ Добавить сериал\n"
                "4. ✅ Отметить серию просмотренной\n"
                "5. 🎯 Поставить сезон/серию вручную\n"
                "6. 🗑 Удалить сериал\n"
                "0. Назад",
                title="📺 Режим сериалов",
                border_style="cyan"
            ))
        else:
            print("1. Показать сериалы")
            print("2. Включить следующую серию")
            print("3. Добавить сериал")
            print("4. Отметить серию просмотренной")
            print("5. Поставить сезон/серию")
            print("6. Удалить сериал")
            print("0. Назад")

        choice = input("\nВыбор: ").strip()

        if choice == "0":
            return

        elif choice == "1":
            show_series()
            input("\nEnter...")

        elif choice == "2":
            play_next_series()

        elif choice == "3":
            title = input("Название сериала: ").strip()
            season = input("Сезон [1]: ").strip() or "1"
            episode = input("Серия [1]: ").strip() or "1"

            if title and season.isdigit() and episode.isdigit():
                add_series(title, int(season), int(episode))
            else:
                print("❌ Неверные данные.")

            input("\nEnter...")

        elif choice == "4":
            title = input("Название сериала: ").strip()
            if title:
                mark_series_done(title)
            input("\nEnter...")

        elif choice == "5":
            title = input("Название сериала: ").strip()
            season = input("Сезон: ").strip()
            episode = input("Серия: ").strip()

            if title and season.isdigit() and episode.isdigit():
                set_series_progress(title, int(season), int(episode))
            else:
                print("❌ Неверные данные.")

            input("\nEnter...")

        elif choice == "6":
            title = input("Название сериала: ").strip()
            if title:
                delete_series(title)
            input("\nEnter...")

        else:
            print("❌ Нет такого пункта.")


def help_text():
    print("""
vsearch — кино-комбайн

Фильмы:
  vsearch
  vsearch -list
  vsearch -list 10
  vsearch -add "Фильм 1 / Фильм 2"
  vsearch -done 1
  vsearch -rate 1 9
  vsearch -history
  vsearch -stats
  vsearch -all
  vsearch -clear

Сериалы:
  vsearch -series
  vsearch -slist
  vsearch -sadd "Во все тяжкие"
  vsearch -sadd "Во все тяжкие" 2 5
  vsearch -snext "Во все тяжкие"
  vsearch -sdone "Во все тяжкие"
  vsearch -sset "Во все тяжкие" 2 5
  vsearch -sdel "Во все тяжкие"

Сериалы:
  vsearch -series
  vsearch -slist
  vsearch -sadd "Во все тяжкие"
  vsearch -sadd "Во все тяжкие" 2 5
  vsearch -snext "Во все тяжкие"
  vsearch -sdone "Во все тяжкие"
  vsearch -sset "Во все тяжкие" 2 5
  vsearch -sdel "Во все тяжкие"

Сериалы:
  vsearch -series
  vsearch -slist
  vsearch -sadd "Во все тяжкие"
  vsearch -sadd "Во все тяжкие" 2 5
  vsearch -snext "Во все тяжкие"
  vsearch -sdone "Во все тяжкие"
  vsearch -sset "Во все тяжкие" 2 5
  vsearch -sdel "Во все тяжкие"

Марафоны:
  vsearch -marathons
  vsearch -marathon "Хоррор"
  vsearch -mshow "Звёздные войны"
  vsearch -mplay "Звёздные войны"
  vsearch -madd "Звёздные войны"
  vsearch -mqueue
  vsearch -mnext
  vsearch -mclear

Конфиги:
  ~/.config/vsearch/marathons.txt
  ~/.config/vsearch/orders.txt
  ~/.config/vsearch/bad_words.txt
  ~/.config/vsearch/quotes.json
  ~/.config/vsearch/settings.json
""")


def main():
    args = sys.argv[1:]

    if not args:
        main_menu()
        return

    cmd = args[0]

    if cmd == "-list":
        if len(args) == 1:
            play_movie(1)
        elif args[1].isdigit():
            play_movie(int(args[1]))
        else:
            add_movies(" ".join(args[1:]))

    elif cmd == "-next":
        play_movie(1)

    elif cmd == "-add":
        if len(args) < 2:
            print('❌ Пример: vsearch -add "Нечто / Матрица"')
        else:
            add_movies(" ".join(args[1:]))

    elif cmd == "-done":
        if len(args) < 2 or not args[1].isdigit():
            print("❌ Пример: vsearch -done 1")
        else:
            mark_done(int(args[1]))

    elif cmd == "-rate":
        if len(args) < 3 or not args[1].isdigit() or not args[2].isdigit():
            print("❌ Пример: vsearch -rate 1 9")
        else:
            rate_movie(int(args[1]), int(args[2]))

    elif cmd == "-history":
        show_history()

    elif cmd == "-stats":
        show_stats()

    elif cmd == "-all":
        show_all()

    elif cmd == "-clear":
        save_watchlist([])
        print("🧹 Список фильмов очищен.")

    elif cmd == "-marathons":
        menu_marathons()

    elif cmd == "-marathon":
        if len(args) < 2:
            menu_marathons()
        else:
            show_category(" ".join(args[1:]))

    elif cmd == "-mshow":
        if len(args) < 2:
            print('❌ Пример: vsearch -mshow "Звёздные войны"')
        else:
            _, title = find_franchise(" ".join(args[1:]))
            show_order(title or " ".join(args[1:]))

    elif cmd == "-mplay":
        if len(args) < 2:
            print('❌ Пример: vsearch -mplay "Звёздные войны"')
        else:
            play_marathon_direct(" ".join(args[1:]))

    elif cmd == "-madd":
        if len(args) < 2:
            print('❌ Пример: vsearch -madd "Звёздные войны"')
        else:
            add_marathon(" ".join(args[1:]))

    elif cmd == "-mqueue":
        show_mqueue()

    elif cmd == "-mnext":
        play_next_marathon()

    elif cmd == "-mdone":
        if len(args) < 2 or not args[1].isdigit():
            print("❌ Пример: vsearch -mdone 1")
        else:
            mark_marathon_done(int(args[1]))

    elif cmd == "-mclear":
        save_mqueue([])
        print("🧹 Очередь марафонов очищена.")

    elif cmd == "-upscale":
        if len(args) < 2:
            show_video_modes()
        else:
            set_upscale_mode(args[1].lower())

    elif cmd == "-aspect":
        if len(args) < 2:
            show_video_modes()
        else:
            set_aspect_mode(args[1].lower())

    elif cmd == "-video":
        show_video_modes()

    elif cmd == "-series":
        series_menu()

    elif cmd == "-slist":
        show_series()

    elif cmd == "-sadd":
        if len(args) < 2:
            print('❌ Пример: vsearch -sadd "Во все тяжкие"')
        else:
            # можно: vsearch -sadd "Сериал" 2 5
            if len(args) >= 4 and args[-1].isdigit() and args[-2].isdigit():
                title = " ".join(args[1:-2])
                season = int(args[-2])
                episode = int(args[-1])
            else:
                title = " ".join(args[1:])
                season = 1
                episode = 1
            add_series(title, season, episode)

    elif cmd == "-snext":
        if len(args) < 2:
            play_next_series()
        else:
            play_next_series(" ".join(args[1:]))

    elif cmd == "-sdone":
        if len(args) < 2:
            print('❌ Пример: vsearch -sdone "Во все тяжкие"')
        else:
            mark_series_done(" ".join(args[1:]))

    elif cmd == "-sset":
        if len(args) < 4 or not args[-1].isdigit() or not args[-2].isdigit():
            print('❌ Пример: vsearch -sset "Во все тяжкие" 2 5')
        else:
            title = " ".join(args[1:-2])
            season = int(args[-2])
            episode = int(args[-1])
            set_series_progress(title, season, episode)

    elif cmd == "-sdel":
        if len(args) < 2:
            print('❌ Пример: vsearch -sdel "Во все тяжкие"')
        else:
            delete_series(" ".join(args[1:]))

    elif cmd in ["-h", "--help", "-help"]:
        help_text()

    else:
        print("❌ Неизвестная команда.")
        help_text()



# === VSEARCH_MOVIE_FILTER_PATCH_V1 START ===
# Фильтр качества поиска: оставляет фильмы выше, выкидывает клипы/OST/трейлеры/обзоры.
import re as _vsearch_re

_VSEARCH_BAD_MEDIA_WORDS = [
    "trailer", "teaser", "тизер", "трейлер",
    "ost", "soundtrack", "score", "theme", "main theme",
    "music video", "official video", "клип", "песня", "трек",
    "lyrics", "lyric", "instrumental", "remix", "cover",
    "reaction", "реакция", "review", "обзор", "recap", "пересказ",
    "explained", "разбор", "ending explained",
    "behind the scenes", "making of", "интервью",
    "scene", "clip", "фрагмент", "отрывок",
    "gameplay", "walkthrough", "прохождение",
]

_VSEARCH_GOOD_MEDIA_WORDS = [
    "фильм", "полный фильм", "кино",
    "movie", "full movie", "film",
    "1080p", "720p", "2160p", "4k",
    "bdrip", "hdrip", "webrip", "web-dl", "blu-ray", "bluray",
]

def _vsearch_item_title(item):
    if isinstance(item, dict):
        return str(
            item.get("title")
            or item.get("name")
            or item.get("fulltitle")
            or item.get("webpage_url")
            or item
        )
    return str(item)

def _vsearch_item_duration(item):
    if not isinstance(item, dict):
        return None
    d = item.get("duration")
    try:
        if d is None:
            return None
        return int(float(d))
    except Exception:
        return None

def _vsearch_bad_title(title):
    low = str(title).lower()

    for word in _VSEARCH_BAD_MEDIA_WORDS:
        if word in low:
            return True

    # Частые мусорные варианты: "Title OST", "Title - Theme", "Title trailer 4K"
    if _vsearch_re.search(r"\b(ost|theme|trailer|teaser|lyrics|remix|cover)\b", low):
        return True

    # Музыкальные обозначения
    if _vsearch_re.search(r"\b(audio|official audio|visualizer|music)\b", low):
        return True

    return False

def _vsearch_good_title(title):
    low = str(title).lower()

    if any(word in low for word in _VSEARCH_GOOD_MEDIA_WORDS):
        return True

    # Год в названии часто помогает отсеять фильм от мусора
    if _vsearch_re.search(r"\b(19[0-9]{2}|20[0-2][0-9])\b", low):
        return True

    return False

def _vsearch_movie_score(item):
    title = _vsearch_item_title(item)
    low = title.lower()
    duration = _vsearch_item_duration(item)

    score = 0

    if _vsearch_bad_title(title):
        return -999999

    if duration is not None:
        # меньше 40 минут почти всегда не фильм
        if duration < 40 * 60 and not _vsearch_good_title(title):
            return -999998

        # полный метр выше
        if duration >= 70 * 60:
            score += 80
        elif duration >= 40 * 60:
            score += 35

    for word in _VSEARCH_GOOD_MEDIA_WORDS:
        if word in low:
            score += 12

    if _vsearch_re.search(r"\b(19[0-9]{2}|20[0-2][0-9])\b", low):
        score += 10

    # Немного штрафуем очевидно короткий мусор даже без duration
    weak_bad = ["shorts", "#shorts", "tik tok", "tiktok", "edit", "эдит"]
    if any(x in low for x in weak_bad):
        score -= 50

    return score

def _vsearch_filter_movie_results(result):
    if not isinstance(result, list):
        return result

    if not result:
        return result

    # Фильтруем только списки, похожие на поисковые результаты.
    looks_like_results = False
    for item in result[:8]:
        if isinstance(item, dict) and ("title" in item or "name" in item or "duration" in item or "url" in item or "webpage_url" in item):
            looks_like_results = True
            break

    if not looks_like_results:
        return result

    scored = []
    for item in result:
        score = _vsearch_movie_score(item)
        if score <= -999000:
            continue
        scored.append((score, item))

    # Если фильтр случайно выкинул всё — лучше вернуть старый список, чем сломать поиск.
    if not scored:
        return result

    scored.sort(key=lambda x: x[0], reverse=True)
    return [item for score, item in scored]

def _vsearch_install_movie_filter():
    # Оборачиваем только функции поиска, а не меню/плеер/марафоны.
    keys = list(globals().keys())

    for name in keys:
        low = name.lower()

        if not any(k in low for k in ["search", "ytsearch", "find"]):
            continue

        if name.startswith("_vsearch_"):
            continue

        fn = globals().get(name)

        if not callable(fn):
            continue

        if getattr(fn, "_vsearch_movie_filter_wrapped", False):
            continue

        def make_wrapper(old_fn):
            def wrapper(*args, **kwargs):
                result = old_fn(*args, **kwargs)
                return _vsearch_filter_movie_results(result)
            wrapper.__name__ = getattr(old_fn, "__name__", "wrapped")
            wrapper.__doc__ = getattr(old_fn, "__doc__", None)
            wrapper._vsearch_movie_filter_wrapped = True
            return wrapper

        globals()[name] = make_wrapper(fn)

_vsearch_install_movie_filter()
# === VSEARCH_MOVIE_FILTER_PATCH_V1 END ===



# === VSEARCH_SAFE_UPGRADES_V1 START ===
# 3: умный детект названий через titles.json
# 5: --backup и --restore-latest
# 9: bad_words.txt для чистки мусорных результатов
import sys as _vsearch_sys
import json as _vsearch_json
import tarfile as _vsearch_tarfile
import time as _vsearch_time
import shutil as _vsearch_shutil
import re as _vsearch_re
from pathlib import Path as _VSearchPath

_VSEARCH_HOME = _VSearchPath.home()
_VSEARCH_BIN = _VSEARCH_HOME / ".local/bin/vsearch"
_VSEARCH_CFG = _VSEARCH_HOME / ".config/vsearch"
_VSEARCH_DATA = _VSEARCH_HOME / ".local/share/vsearch"
_VSEARCH_BACKUPS = _VSEARCH_DATA / "backups"
_VSEARCH_TITLES = _VSEARCH_CFG / "titles.json"
_VSEARCH_BAD_WORDS = _VSEARCH_CFG / "bad_words.txt"

def _vsearch_load_json_file(path, fallback):
    try:
        return _vsearch_json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback

def _vsearch_load_bad_words():
    if not _VSEARCH_BAD_WORDS.exists():
        return []
    return [
        x.strip().lower()
        for x in _VSEARCH_BAD_WORDS.read_text(encoding="utf-8", errors="ignore").splitlines()
        if x.strip() and not x.strip().startswith("#")
    ]

def _vsearch_create_backup():
    _VSEARCH_BACKUPS.mkdir(parents=True, exist_ok=True)
    stamp = _vsearch_time.strftime("%Y%m%d_%H%M%S")
    out = _VSEARCH_BACKUPS / f"vsearch-full-backup-{stamp}.tar.gz"

    with _vsearch_tarfile.open(out, "w:gz") as tar:
        if _VSEARCH_BIN.exists():
            tar.add(_VSEARCH_BIN, arcname="vsearch")
        if _VSEARCH_CFG.exists():
            tar.add(_VSEARCH_CFG, arcname="config-vsearch")
        if _VSEARCH_DATA.exists():
            tar.add(_VSEARCH_DATA, arcname="share-vsearch")

    print("✅ Бэкап создан:", out)
    return out

def _vsearch_restore_latest():
    if not _VSEARCH_BACKUPS.exists():
        print("❌ Бэкапов нет:", _VSEARCH_BACKUPS)
        return

    backups = sorted(_VSEARCH_BACKUPS.glob("vsearch-full-backup-*.tar.gz"), reverse=True)
    if not backups:
        print("❌ Бэкапов нет:", _VSEARCH_BACKUPS)
        return

    latest = backups[0]
    temp = _VSEARCH_BACKUPS / "_restore_tmp"

    if temp.exists():
        _vsearch_shutil.rmtree(temp)

    temp.mkdir(parents=True, exist_ok=True)

    with _vsearch_tarfile.open(latest, "r:gz") as tar:
        tar.extractall(temp)

    restored_bin = temp / "vsearch"
    restored_cfg = temp / "config-vsearch"
    restored_data = temp / "share-vsearch"

    if restored_bin.exists():
        _VSEARCH_BIN.write_text(restored_bin.read_text(encoding="utf-8", errors="ignore"), encoding="utf-8")
        _VSEARCH_BIN.chmod(0o755)

    if restored_cfg.exists():
        if _VSEARCH_CFG.exists():
            _vsearch_shutil.rmtree(_VSEARCH_CFG)
        _vsearch_shutil.copytree(restored_cfg, _VSEARCH_CFG)

    if restored_data.exists():
        if _VSEARCH_DATA.exists():
            _vsearch_shutil.rmtree(_VSEARCH_DATA)
        _vsearch_shutil.copytree(restored_data, _VSEARCH_DATA)

    _vsearch_shutil.rmtree(temp, ignore_errors=True)
    print("✅ Восстановлено из:", latest)

def _vsearch_enrich_query(query):
    q = str(query).strip()
    if not q:
        return query

    titles = _vsearch_load_json_file(_VSEARCH_TITLES, {})
    if not isinstance(titles, dict):
        return query

    low = q.lower()

    found_key = None
    found_meta = None

    for key, meta in titles.items():
        ru = ""
        if isinstance(meta, dict):
            ru = str(meta.get("ru", ""))

        if low == str(key).lower() or (ru and low == ru.lower()):
            found_key = key
            found_meta = meta
            break

    if not found_key or not isinstance(found_meta, dict):
        return query

    year = found_meta.get("year")
    ru = found_meta.get("ru")
    typ = found_meta.get("type", "movie")

    extra = []

    if year and str(year) not in q:
        extra.append(str(year))

    if ru and str(ru).lower() not in low:
        extra.append(str(ru))

    if typ == "movie":
        extra.extend(["фильм", "movie"])

    # Не превращаем запрос в кашу, только добавляем подсказки.
    enriched = q + " " + " ".join(extra)
    return enriched.strip()

def _vsearch_item_title(item):
    if isinstance(item, dict):
        return str(
            item.get("title")
            or item.get("name")
            or item.get("fulltitle")
            or item.get("webpage_url")
            or item
        )
    return str(item)

def _vsearch_item_duration(item):
    if not isinstance(item, dict):
        return None
    try:
        d = item.get("duration")
        if d is None:
            return None
        return int(float(d))
    except Exception:
        return None

def _vsearch_bad_result(item):
    title = _vsearch_item_title(item).lower()
    duration = _vsearch_item_duration(item)
    bad_words = _vsearch_load_bad_words()

    for word in bad_words:
        if word in title:
            return True

    if duration is not None:
        # меньше 35 минут почти всегда не фильм, если явно не написано full movie / полный фильм
        if duration < 35 * 60 and "full movie" not in title and "полный фильм" not in title:
            return True

    return False

def _vsearch_result_score(item):
    title = _vsearch_item_title(item).lower()
    duration = _vsearch_item_duration(item)

    if _vsearch_bad_result(item):
        return -999999

    score = 0

    good_words = [
        "full movie",
        "полный фильм",
        "фильм",
        "movie",
        "film",
        "1080p",
        "720p",
        "2160p",
        "4k",
        "bdrip",
        "hdrip",
        "webrip",
        "web-dl",
        "bluray",
        "blu-ray",
    ]

    for word in good_words:
        if word in title:
            score += 15

    if _vsearch_re.search(r"\b(19[0-9]{2}|20[0-2][0-9])\b", title):
        score += 10

    if duration is not None:
        if duration >= 70 * 60:
            score += 90
        elif duration >= 45 * 60:
            score += 45

    return score

def _vsearch_filter_results(result):
    if not isinstance(result, list):
        return result

    if not result:
        return result

    looks_like_search_results = False

    for item in result[:10]:
        if isinstance(item, dict) and (
            "title" in item
            or "name" in item
            or "duration" in item
            or "url" in item
            or "webpage_url" in item
        ):
            looks_like_search_results = True
            break

    if not looks_like_search_results:
        return result

    scored = []

    for item in result:
        score = _vsearch_result_score(item)
        if score <= -999000:
            continue
        scored.append((score, item))

    # Если всё выкинуло — возвращаем обычные результаты, чтобы поиск не умер.
    if not scored:
        return result

    scored.sort(key=lambda x: x[0], reverse=True)
    return [item for score, item in scored]

def _vsearch_install_safe_upgrades():
    # Оборачиваем play_query: добавляем год/русское название/тип из titles.json.
    if "play_query" in globals() and callable(globals()["play_query"]):
        old_play_query = globals()["play_query"]

        if not getattr(old_play_query, "_vsearch_safe_wrapped", False):
            def play_query_wrapper(query, *args, **kwargs):
                return old_play_query(_vsearch_enrich_query(query), *args, **kwargs)

            play_query_wrapper._vsearch_safe_wrapped = True
            play_query_wrapper.__name__ = getattr(old_play_query, "__name__", "play_query")
            globals()["play_query"] = play_query_wrapper

    # Оборачиваем поисковые функции: чистим трейлеры/OST/клипы/обзоры из результатов.
    for name, fn in list(globals().items()):
        low = name.lower()

        if name.startswith("_vsearch_"):
            continue

        if not callable(fn):
            continue

        if getattr(fn, "_vsearch_filter_wrapped", False):
            continue

        if not any(k in low for k in ["search", "find", "ytsearch"]):
            continue

        def make_wrapper(old_fn):
            def wrapper(*args, **kwargs):
                return _vsearch_filter_results(old_fn(*args, **kwargs))
            wrapper._vsearch_filter_wrapped = True
            wrapper.__name__ = getattr(old_fn, "__name__", "wrapped_search")
            return wrapper

        globals()[name] = make_wrapper(fn)

    # Оборачиваем main: добавляем --backup и --restore-latest.
    if "main" in globals() and callable(globals()["main"]):
        old_main = globals()["main"]

        if not getattr(old_main, "_vsearch_main_wrapped", False):
            def main_wrapper(*args, **kwargs):
                if "--backup" in _vsearch_sys.argv:
                    _vsearch_create_backup()
                    raise SystemExit(0)
                if "--restore-latest" in _vsearch_sys.argv:
                    _vsearch_restore_latest()
                    raise SystemExit(0)
                return old_main(*args, **kwargs)

            main_wrapper._vsearch_main_wrapped = True
            main_wrapper.__name__ = getattr(old_main, "__name__", "main")
            globals()["main"] = main_wrapper

_vsearch_install_safe_upgrades()
# === VSEARCH_SAFE_UPGRADES_V1 END ===


if __name__ == "__main__":
    main()
