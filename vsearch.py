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


BASE = Path.home() / ".local/share/vsearch"
BASE.mkdir(parents=True, exist_ok=True)

WATCHLIST = BASE / "watchlist.json"
MQUEUE = BASE / "marathons_queue.json"

RUTUBE_SEARCH = "https://rutube.ru/api/search/video/"
MIN_DURATION = 60 * 60

BAD_WORDS = [
    "трейлер", "trailer", "тизер", "teaser", "обзор", "review",
    "реакция", "reaction", "разбор", "пересказ", "нарезка",
    "сцена", "лучшие моменты", "ost", "саундтрек", "клип",
    "clip", "behind the scenes", "интервью"
]

MOVIE_QUOTES = {
    "железный человек": ["🤖 Понял, сэр. Запускаю протокол Mark I."],
    "мстители": ["🛡 Мстители, общий сбор."],
    "матрица": ["🐇 Следуй за белым кроликом.", "💊 Красная таблетка выбрана. Загружаю Матрицу."],
    "звёздные войны": ["🌌 Да пребудет с тобой Сила.", "⚔️ В далёкой-далёкой галактике начинается просмотр."],
    "звездные войны": ["🌌 Да пребудет с тобой Сила.", "⚔️ В далёкой-далёкой галактике начинается просмотр."],
    "терминатор": ["🤖 I'll be back. Но сначала включаю фильм.", "🦾 Hasta la vista, baby."],
    "чужой": ["👽 В космосе никто не услышит твой крик."],
    "хищник": ["🌲 Если оно кровоточит — его можно смотреть."],
    "робокоп": ["🚔 Живым или мёртвым — ты идёшь смотреть."],
    "назад в будущее": ["⚡ Там, куда мы отправляемся, дороги не нужны."],
    "бегущий по лезвию": ["🌧 Все эти моменты исчезнут, как слёзы под дождём."],
    "дюна": ["🏜 Страх убивает разум.", "🪱 Пряность должна течь."],
    "властелин колец": ["💍 Нельзя просто так взять и не посмотреть."],
    "гарри поттер": ["🪄 Accio фильм!"],
    "джон уик": ["✏️ Одним карандашом. Одним фильмом. Одним вечером."],
    "крёстный отец": ["🤌 Сделаю тебе предложение, от которого невозможно отказаться."],
    "бэтмен": ["🦇 Я — месть. Я — ночь. Я запускаю фильм."],
    "таксист": ["🚕 You talkin’ to me?"],
    "бойцовский клуб": ["🧼 Первое правило клуба: никому не рассказывать, что скрипт имба."],
}

GENERIC_QUOTES = [
    "🎬 Проектор включён. Ищу достойную копию.",
    "🍿 Попкорн готов. Начинаю поиск.",
    "📼 Кассета вставлена. Перематываю к началу.",
    "🎞 Свет гаснет. Начинается магия.",
]


CATS_RAW = """
Фантастика и киберпанк => Звёздные войны / Звёздный путь / Чужой / Хищник / Терминатор / Матрица / Бегущий по лезвию / Робокоп / Безумный Макс / Назад в будущее / Трон / Дюна / Планета обезьян / Люди в чёрном / Доктор Кто / Секретные материалы / Чёрное зеркало
Супергероика => Marvel / DC / Человек-паук / Люди Икс / Стражи Галактики / Мстители / Хранители / Пацаны
Фэнтези => Властелин колец / Хоббит / Гарри Поттер / Игра престолов / Ведьмак / Нарния / Пираты Карибского моря / Конан-варвар
Хоррор => Кошмар на улице Вязов / Пятница 13-е / Хэллоуин / Крик / Зловещие мертвецы / Пила / Заклятие / Оно / Восставший из ада / Техасская резня бензопилой / Пункт назначения / Астрал
Боевики и криминал => Джон Уик / Крепкий орешек / Миссия невыполнима / Джеймс Бонд / Форсаж / Рэмбо / Рокки / Смертельное оружие / Убить Билла / Крёстный отец / Лицо со шрамом
Анимация => Шрек / История игрушек / Корпорация монстров / Как приручить дракона / Кунг-фу Панда / Ледниковый период / Гадкий я / Симпсоны / Футурама / Рик и Морти / Южный парк / Гравити Фолз / Время приключений
"""

ORDERS_RAW = """
Звёздные войны => Звёздные войны: Эпизод IV — Новая надежда / Звёздные войны: Эпизод V — Империя наносит ответный удар / Звёздные войны: Эпизод VI — Возвращение джедая / Звёздные войны: Эпизод I — Скрытая угроза / Звёздные войны: Эпизод II — Атака клонов / Звёздные войны: Эпизод III — Месть ситхов / Звёздные войны: Эпизод VII — Пробуждение силы / Звёздные войны: Эпизод VIII — Последние джедаи / Звёздные войны: Эпизод IX — Скайуокер. Восход / Изгой-один: Звёздные войны. Истории / Хан Соло: Звёздные войны. Истории / Звёздные войны: Войны клонов / Звёздные войны: Повстанцы / Мандалорец / Книга Бобы Фетта / Асока
Звёздный путь => Звёздный путь: Оригинальный сериал / Звёздный путь: Анимационный сериал / Звёздный путь фильм 1 / Звёздный путь 2: Гнев Хана / Звёздный путь 3: В поисках Спока / Звёздный путь 4: Дорога домой / Звёздный путь 5: Последний рубеж / Звёздный путь 6: Неоткрытая страна / Звёздный путь: Следующее поколение / Звёздный путь: Поколения / Звёздный путь: Первый контакт / Звёздный путь: Восстание / Звёздный путь: Возмездие / Звёздный путь: Глубокий космос 9 / Звёздный путь: Вояджер / Звёздный путь: Энтерпрайз / Звёздный путь: Дискавери / Звёздный путь: Странные новые миры / Звёздный путь 2009 / Стартрек: Возмездие / Стартрек: Бесконечность
Чужой => Чужой / Чужие / Чужой 3 / Чужой: Воскрешение / Прометей / Чужой: Завет / Чужой против Хищника / Чужие против Хищника: Реквием
Хищник => Хищник / Хищник 2 / Хищники / Хищник 2018 / Добыча
Терминатор => Терминатор / Терминатор 2: Судный день / Терминатор: Тёмные судьбы / Терминатор 3: Восстание машин / Терминатор: Да придёт спаситель / Терминатор: Генезис
Матрица => Матрица / Аниматрица / Матрица: Перезагрузка / Матрица: Революция / Матрица: Воскрешение
Бегущий по лезвию => Бегущий по лезвию: Последняя версия / Бегущий по лезвию: Блэкаут 2022 / 2036: Восход Nexus / 2048: Некуда бежать / Бегущий по лезвию 2049
Робокоп => Робокоп / Робокоп 2 / Робокоп 3
Безумный Макс => Фуриоса: Хроники Безумного Макса / Безумный Макс / Безумный Макс 2: Воин дороги / Безумный Макс 3: Под куполом грома / Безумный Макс: Дорога ярости
Назад в будущее => Назад в будущее / Назад в будущее 2 / Назад в будущее 3
Трон => Трон / Трон: Восстание / Трон: Наследие
Дюна => Дюна 2021 / Дюна: Часть вторая
Планета обезьян => Восстание планеты обезьян / Планета обезьян: Революция / Планета обезьян: Война / Планета обезьян: Новое царство / Планета обезьян 1968 / Под планетой обезьян / Бегство с планеты обезьян / Завоевание планеты обезьян / Битва за планету обезьян
Люди в чёрном => Люди в чёрном / Люди в чёрном 2 / Люди в чёрном 3 / Люди в чёрном: Интернэшнл
Доктор Кто => Доктор Кто: классика / Доктор Кто: новый сериал
Секретные материалы => Секретные материалы 1 сезон / Секретные материалы 2 сезон / Секретные материалы 3 сезон / Секретные материалы 4 сезон / Секретные материалы 5 сезон / Секретные материалы: Борьба за будущее / Секретные материалы 6 сезон / Секретные материалы 7 сезон / Секретные материалы 8 сезон / Секретные материалы 9 сезон / Секретные материалы: Хочу верить / Секретные материалы 10 сезон / Секретные материалы 11 сезон
Чёрное зеркало => Чёрное зеркало 1 сезон / Чёрное зеркало 2 сезон / Чёрное зеркало 3 сезон / Чёрное зеркало 4 сезон / Чёрное зеркало 5 сезон / Чёрное зеркало 6 сезон
Marvel => Железный человек / Мстители / Мстители: Эра Альтрона / Первый мститель: Противостояние / Мстители: Война бесконечности / Мстители: Финал / Стражи Галактики / Стражи Галактики. Часть 2 / Стражи Галактики. Часть 3 / Человек-паук: Возвращение домой / Человек-паук: Вдали от дома / Человек-паук: Нет пути домой / Доктор Стрэндж / Доктор Стрэндж: В мультивселенной безумия / Чёрная вдова / Вечные / Тор: Любовь и гром
DC => Человек из стали / Бэтмен против Супермена / Отряд самоубийц / Чудо-женщина / Лига справедливости Зака Снайдера / Аквамен / Шазам / Хищные птицы / Отряд самоубийц: Миссия навылет / Чёрный Адам / Флэш / Аквамен и потерянное царство / Синий Жук
Человек-паук => Человек-паук / Человек-паук 2 / Человек-паук 3 / Новый Человек-паук / Новый Человек-паук: Высокое напряжение / Человек-паук: Возвращение домой / Человек-паук: Вдали от дома / Человек-паук: Нет пути домой / Человек-паук: Через вселенные / Человек-паук: Паутина вселенных
Люди Икс => Люди Икс: Первый класс / Люди Икс: Дни минувшего будущего / Люди Икс: Апокалипсис / Люди Икс: Тёмный Феникс / Люди Икс / Люди Икс 2 / Люди Икс: Последняя битва / Люди Икс: Начало. Росомаха / Логан
Стражи Галактики => Стражи Галактики / Стражи Галактики. Часть 2 / Стражи Галактики: Праздничный спецвыпуск / Стражи Галактики. Часть 3
Мстители => Мстители / Мстители: Эра Альтрона / Мстители: Война бесконечности / Мстители: Финал
Хранители => Хранители 2009 / Хранители сериал 2019
Пацаны => Пацаны 1 сезон / Пацаны 2 сезон / Пацаны 3 сезон / Поколение Ви / Пацаны 4 сезон
Властелин колец => Властелин колец: Братство кольца / Властелин колец: Две крепости / Властелин колец: Возвращение короля / Хоббит: Нежданное путешествие / Хоббит: Пустошь Смауга / Хоббит: Битва пяти воинств
Хоббит => Хоббит: Нежданное путешествие / Хоббит: Пустошь Смауга / Хоббит: Битва пяти воинств / Властелин колец: Братство кольца / Властелин колец: Две крепости / Властелин колец: Возвращение короля
Гарри Поттер => Гарри Поттер и философский камень / Гарри Поттер и Тайная комната / Гарри Поттер и узник Азкабана / Гарри Поттер и Кубок огня / Гарри Поттер и Орден Феникса / Гарри Поттер и Принц-полукровка / Гарри Поттер и Дары Смерти: Часть 1 / Гарри Поттер и Дары Смерти: Часть 2 / Фантастические твари и где они обитают / Фантастические твари: Преступления Грин-де-Вальда / Фантастические твари: Тайны Дамблдора
Игра престолов => Игра престолов 1 сезон / Игра престолов 2 сезон / Игра престолов 3 сезон / Игра престолов 4 сезон / Игра престолов 5 сезон / Игра престолов 6 сезон / Игра престолов 7 сезон / Игра престолов 8 сезон / Дом Дракона
Ведьмак => Ведьмак: Кошмар волка / Ведьмак 1 сезон / Ведьмак 2 сезон / Ведьмак 3 сезон
Нарния => Хроники Нарнии: Лев, колдунья и волшебный шкаф / Хроники Нарнии: Принц Каспиан / Хроники Нарнии: Покоритель зари
Пираты Карибского моря => Пираты Карибского моря: Проклятие Чёрной жемчужины / Пираты Карибского моря: Сундук мертвеца / Пираты Карибского моря: На краю света / Пираты Карибского моря: На странных берегах / Пираты Карибского моря: Мертвецы не рассказывают сказки
Конан-варвар => Конан-варвар 1982 / Конан-разрушитель
Кошмар на улице Вязов => Кошмар на улице Вязов 1 / Кошмар на улице Вязов 2 / Кошмар на улице Вязов 3 / Кошмар на улице Вязов 4 / Кошмар на улице Вязов 5 / Фредди мёртв: Последний кошмар / Новый кошмар Уэса Крэйвена
Пятница 13-е => Пятница 13-е 1 / Пятница 13-е 2 / Пятница 13-е 3 / Пятница 13-е 4 / Пятница 13-е 5 / Пятница 13-е 6 / Пятница 13-е 7 / Пятница 13-е 8 / Джейсон отправляется в ад / Джейсон X / Фредди против Джейсона
Хэллоуин => Хэллоуин 1978 / Хэллоуин 2018 / Хэллоуин убивает / Хэллоуин заканчивается
Крик => Крик / Крик 2 / Крик 3 / Крик 4 / Крик 2022 / Крик 6
Зловещие мертвецы => Зловещие мертвецы / Зловещие мертвецы 2 / Армия тьмы / Эш против зловещих мертвецов / Зловещие мертвецы: Чёрная книга / Восстание зловещих мертвецов
Пила => Пила / Пила 2 / Пила 3 / Пила 4 / Пила 5 / Пила 6 / Пила 3D / Пила 8 / Спираль: Наследие Пилы / Пила 10
Заклятие => Заклятие / Заклятие 2 / Заклятие 3 / Проклятие монахини / Проклятие монахини 2 / Проклятие Аннабель / Проклятие Аннабель: Зарождение зла / Проклятие Аннабель 3
Оно => Оно 2017 / Оно 2
Восставший из ада => Восставший из ада / Восставший из ада 2 / Восставший из ада 3 / Восставший из ада 4
Техасская резня бензопилой => Техасская резня бензопилой 1974 / Техасская резня бензопилой 2022
Пункт назначения => Пункт назначения 5 / Пункт назначения / Пункт назначения 2 / Пункт назначения 3 / Пункт назначения 4
Астрал => Астрал 3 / Астрал 4: Последний ключ / Астрал / Астрал: Глава 2 / Астрал 5: Красная дверь
Джон Уик => Джон Уик / Джон Уик 2 / Джон Уик 3 / Джон Уик 4
Крепкий орешек => Крепкий орешек / Крепкий орешек 2 / Крепкий орешек 3 / Крепкий орешек 4.0 / Крепкий орешек: Хороший день, чтобы умереть
Миссия невыполнима => Миссия невыполнима / Миссия невыполнима 2 / Миссия невыполнима 3 / Миссия невыполнима: Протокол Фантом / Миссия невыполнима: Племя изгоев / Миссия невыполнима: Последствия / Миссия невыполнима: Смертельная расплата
Джеймс Бонд => Казино Рояль / Квант милосердия / 007: Координаты Скайфолл / 007: Спектр / Не время умирать
Форсаж => Форсаж / Двойной форсаж / Форсаж 4 / Форсаж 5 / Форсаж 6 / Тройной форсаж: Токийский дрифт / Форсаж 7 / Форсаж 8 / Форсаж: Хоббс и Шоу / Форсаж 9 / Форсаж 10
Рэмбо => Рэмбо: Первая кровь / Рэмбо: Первая кровь 2 / Рэмбо 3 / Рэмбо 4 / Рэмбо: Последняя кровь
Рокки => Рокки / Рокки 2 / Рокки 3 / Рокки 4 / Рокки 5 / Рокки Бальбоа / Крид: Наследие Рокки / Крид 2 / Крид 3
Смертельное оружие => Смертельное оружие / Смертельное оружие 2 / Смертельное оружие 3 / Смертельное оружие 4
Убить Билла => Убить Билла. Фильм 1 / Убить Билла. Фильм 2
Крёстный отец => Крёстный отец / Крёстный отец 2 / Крёстный отец 3
Лицо со шрамом => Лицо со шрамом
Шрек => Шрек / Шрек 2 / Шрек Третий / Шрек навсегда / Кот в сапогах / Кот в сапогах 2: Последнее желание
История игрушек => История игрушек / История игрушек 2 / История игрушек 3 / История игрушек 4
Корпорация монстров => Университет монстров / Корпорация монстров
Как приручить дракона => Как приручить дракона / Как приручить дракона 2 / Как приручить дракона 3
Кунг-фу Панда => Кунг-фу Панда / Кунг-фу Панда 2 / Кунг-фу Панда 3 / Кунг-фу Панда 4
Ледниковый период => Ледниковый период / Ледниковый период 2 / Ледниковый период 3 / Ледниковый период 4 / Ледниковый период 5
Гадкий я => Миньоны / Миньоны: Грювитация / Гадкий я / Гадкий я 2 / Гадкий я 3 / Гадкий я 4
Симпсоны => Симпсоны по сезонам / Симпсоны в кино
Футурама => Футурама по сезонам
Рик и Морти => Рик и Морти по сезонам
Южный парк => Южный парк по сезонам / Южный парк: Большой, длинный и необрезанный
Гравити Фолз => Гравити Фолз 1 сезон / Гравити Фолз 2 сезон
Время приключений => Время приключений по сезонам / Время приключений: Далёкие земли / Фионна и Кейк
"""


def seq(text):
    return [x.strip() for x in text.split("/") if x.strip()]


def parse_map(raw):
    data = {}
    for line in raw.strip().splitlines():
        if "=>" not in line:
            continue
        key, value = line.split("=>", 1)
        data[key.strip()] = seq(value)
    return data


MARATHONS = parse_map(CATS_RAW)
ORDERS = parse_map(ORDERS_RAW)


def ts():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def load(path, fallback):
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def banner():
    if RICH:
        text = Text()
        text.append("🎬 vsearch\n", style="bold cyan")
        text.append("CLI-кино-комбайн для Linux", style="dim")
        console.print(Panel(Align.center(text), border_style="cyan"))
    else:
        print("\n🎬 vsearch — CLI-кино-комбайн\n")


def bar(done, total, width=22):
    if total <= 0:
        return "░" * width
    filled = int(width * (done / total))
    return "█" * filled + "░" * (width - filled)


def watchlist():
    return load(WATCHLIST, [])


def save_watchlist(data):
    save(WATCHLIST, data)


def unwatched():
    return [x for x in watchlist() if not x.get("watched")]


def watched():
    return [x for x in watchlist() if x.get("watched")]


def mqueue():
    return load(MQUEUE, [])


def save_mqueue(data):
    save(MQUEUE, data)


def all_franchises():
    result = []
    for cat, titles in MARATHONS.items():
        for title in titles:
            result.append((cat, title))
    return result


def find_franchise(query):
    q = query.lower().replace("ё", "е").strip()

    for cat, title in all_franchises():
        t = title.lower().replace("ё", "е")
        if q == t or q in t:
            return cat, title

    for title in ORDERS:
        t = title.lower().replace("ё", "е")
        if q == t or q in t:
            return "Другое", title

    return None, None


def order_for(title):
    return ORDERS.get(title, [title])


def movie_quote(query):
    q = query.lower().replace("ё", "е")

    for key, lines in MOVIE_QUOTES.items():
        k = key.lower().replace("ё", "е")
        if k in q or q in k:
            return random.choice(lines)

    return random.choice(GENERIC_QUOTES)


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


def bad_video(title):
    low = title.lower()
    return any(word in low for word in BAD_WORDS)


def search_rutube(query, strict=True):
    try:
        r = requests.get(
            RUTUBE_SEARCH,
            params={"query": query, "page": 1, "limit": 15},
            timeout=10,
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

        if bad_video(title):
            continue

        url = item.get("video_url") or item.get("html_url") or item.get("url")

        if not url and item.get("id"):
            url = f"https://rutube.ru/video/{item.get('id')}/"

        duration_raw = item.get("duration") or item.get("duration_string") or item.get("video_duration")
        duration = parse_duration(duration_raw)

        if strict and duration and duration < MIN_DURATION:
            continue

        if url:
            videos.append({
                "title": title,
                "url": url,
                "duration": duration_raw or "??"
            })

    return videos


def choose_video(videos):
    if RICH:
        table = Table(title="🔎 Найдено", border_style="cyan")
        table.add_column("№", style="bold cyan", justify="right")
        table.add_column("Название", style="bold white")
        table.add_column("Длительность", style="yellow")

        for i, video in enumerate(videos, 1):
            table.add_row(str(i), video["title"], str(video["duration"]))

        console.print(table)
    else:
        print("Найдено:\n")
        for i, video in enumerate(videos, 1):
            print(f"{i}. {video['title']} [{video['duration']}]")

    choice = input("\nEnter = первый результат | номер = выбрать: ").strip()

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

    print(f"\n▶️ Открываю fullscreen:\n{url}\n")
    subprocess.run(["mpv", "--fs", "--force-window=yes", url])

    return True


def show_watchlist():
    items = unwatched()
    db = watchlist()
    done = len([x for x in db if x.get("watched")])
    total = len(db)

    banner()

    if RICH:
        console.print(Panel(
            f"[bold]Всего:[/] {total}   [green]Просмотрено:[/] {done}   "
            f"[yellow]Осталось:[/] {len(items)}   [cyan]{bar(done, total)}[/]",
            title="📊 Прогресс",
            border_style="blue"
        ))

        if not items:
            console.print(Panel(
                '[yellow]Список пуст.[/]\n\nДобавить:\n[bold cyan]vsearch -add "Нечто / Матрица / Акира"[/]',
                title="🎬 Watchlist",
                border_style="yellow"
            ))
            return

        table = Table(title="🎬 Твой список на просмотр", border_style="cyan")
        table.add_column("№", justify="right", style="bold cyan", width=4)
        table.add_column("Фильм", style="bold white")
        table.add_column("Статус", justify="center")

        for i, item in enumerate(items, 1):
            table.add_row(str(i), item["title"], "⬜ ждёт")

        console.print(table)

        console.print(Panel(
            "[bold cyan]vsearch -list[/] — открыть первый фильм\n"
            "[bold cyan]vsearch -list 10[/] — открыть фильм №10\n"
            "[bold cyan]vsearch -marathons[/] — меню марафонов\n"
            "[bold cyan]vsearch -stats[/] — статистика",
            title="⚡ Быстрые команды",
            border_style="magenta"
        ))
    else:
        print("\n🎬 ТВОЙ СПИСОК НА ПРОСМОТР\n")
        if not items:
            print('Пусто. Добавить: vsearch -add "Нечто / Матрица"')
            return
        for i, item in enumerate(items, 1):
            print(f"{i}. {item['title']}")


def add_movies(raw):
    db = watchlist()
    existing = {x["title"].lower() for x in db}
    movies = [" ".join(x.strip().split()) for x in raw.replace("\n", "/").split("/") if x.strip()]
    added = 0

    for movie in movies:
        if movie.lower() in existing:
            continue

        db.append({
            "title": movie,
            "watched": False,
            "added_at": ts(),
            "watched_at": None,
            "rating": None
        })

        existing.add(movie.lower())
        added += 1

    save_watchlist(db)
    print(f"✅ Добавлено: {added}")
    show_watchlist()


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
    item["watched_at"] = ts()

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
        print(f"\n🎞 ПОРЯДОК МАРАФОНА: {title}\n")
        for i, part in enumerate(order, 1):
            print(f"{i}. {part}")


def menu_marathons():
    cats = list(MARATHONS.keys())

    while True:
        banner()

        if RICH:
            table = Table(title="🏁 Марафоны", border_style="cyan")
            table.add_column("№", justify="right", style="bold cyan")
            table.add_column("Категория", style="bold white")
            table.add_column("Франшиз", justify="right", style="yellow")

            for i, cat in enumerate(cats, 1):
                table.add_row(str(i), cat, str(len(MARATHONS[cat])))

            table.add_row("0", "Выход", "")
            console.print(table)
        else:
            for i, cat in enumerate(cats, 1):
                print(f"{i}. {cat} ({len(MARATHONS[cat])})")
            print("0. Выход")

        choice = input("\nКатегория: ").strip()

        if choice == "0":
            return

        if not choice.isdigit() or not (1 <= int(choice) <= len(cats)):
            print("❌ Неверный номер.")
            continue

        cat = cats[int(choice) - 1]
        franchises = MARATHONS[cat]

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
                    print(f"\n🎬 {title}\n")
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
    cats = list(MARATHONS.keys())
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

    for i, title in enumerate(MARATHONS[cat], 1):
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
        "added_at": ts(),
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

    play_query(episode, strict=False)


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

    if play_query(episode, strict=False):
        answer = input("\nОтметить эту часть просмотренной? [y/N]: ").strip().lower()

        if answer in ["y", "yes", "д", "да"]:
            item["current_index"] = idx + 1

            if item["current_index"] >= len(order):
                item["done"] = True
                item["done_at"] = ts()

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
    item["done_at"] = ts()
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
                ("2", "🎬 Показать список фильмов"),
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
            print("2. Показать список фильмов")
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
            input("\nEnter чтобы вернуться...")
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

    elif cmd in ["-h", "--help", "-help"]:
        help_text()

    else:
        print("❌ Неизвестная команда.")
        help_text()


if __name__ == "__main__":
    main()
