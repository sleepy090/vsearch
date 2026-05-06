#!/usr/bin/env python3
import json
import sys
import random
import subprocess
import urllib.parse
from pathlib import Path
from datetime import datetime

import requests

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
    args = build_mpv_args(url)

    st = load_settings()
    print(f"\n⚙️ Upscale: {st.get('upscale_mode', 'off')} | Aspect: {st.get('aspect_mode', 'original')}")
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



def shader_path(value):
    if not value:
        return None

    path = Path(str(value)).expanduser()
    return path if path.exists() else None


def build_mpv_args(target):
    st = load_settings()

    args = ["mpv"]

    if st.get("open_fullscreen", True):
        args.append("--fs")

    args.append("--force-window=yes")

    upscale = st.get("upscale_mode", "off")
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
    allowed = ["off", "anime", "film", "status"]

    if mode not in allowed:
        print("❌ Режимы: off / anime / film / status")
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

        print("\n1. Upscale: off")
        print("2. Upscale: anime")
        print("3. Upscale: film")
        print("4. Aspect: original")
        print("5. Aspect: crop")
        print("6. Aspect: stretch")
        print("0. Назад")

        choice = input("\nВыбор: ").strip()

        if choice == "0":
            return
        elif choice == "1":
            set_upscale_mode("off")
        elif choice == "2":
            set_upscale_mode("anime")
        elif choice == "3":
            set_upscale_mode("film")
        elif choice == "4":
            set_aspect_mode("original")
        elif choice == "5":
            set_aspect_mode("crop")
        elif choice == "6":
            set_aspect_mode("stretch")
        else:
            print("❌ Нет такого пункта.")

        input("\nEnter...")


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

    elif cmd in ["-h", "--help", "-help"]:
        help_text()

    else:
        print("❌ Неизвестная команда.")
        help_text()


if __name__ == "__main__":
    main()
