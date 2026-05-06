#!/usr/bin/env python3
import json
import sys
import random
import subprocess
import urllib.parse
from pathlib import Path
from datetime import datetime

import requests

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
    "железный человек": [
        "🤖 Понял, сэр. Запускаю протокол Mark I.",
        "🤖 Реактор запущен. Костюм готов к просмотру.",
        "🤖 Сэр, я бы рекомендовал устроиться поудобнее."
    ],
    "мстители": [
        "🛡 Мстители, общий сбор.",
        "⚡ Угроза уровня Таноса. Запускаю просмотр."
    ],
    "матрица": [
        "🐇 Следуй за белым кроликом.",
        "💊 Красная таблетка выбрана. Загружаю Матрицу.",
        "🕶 Добро пожаловать в реальный мир."
    ],
    "звёздные войны": [
        "🌌 Да пребудет с тобой Сила.",
        "⚔️ В далёкой-далёкой галактике начинается просмотр.",
        "🛸 Это не те дроиды, которых вы ищете. Но фильм сейчас найдём."
    ],
    "звездные войны": [
        "🌌 Да пребудет с тобой Сила.",
        "⚔️ В далёкой-далёкой галактике начинается просмотр.",
        "🛸 Это не те дроиды, которых вы ищете. Но фильм сейчас найдём."
    ],
    "терминатор": [
        "🤖 I'll be back. Но сначала включаю фильм.",
        "🦾 Hasta la vista, baby.",
        "🔴 Цель обнаружена. Запускаю Skynet-поиск."
    ],
    "чужой": [
        "👽 В космосе никто не услышит твой крик.",
        "🚨 Датчики движения что-то засекли. Запускаю фильм."
    ],
    "хищник": [
        "🌲 Если оно кровоточит — его можно смотреть.",
        "👁 Тепловизор включён. Цель найдём."
    ],
    "робокоп": [
        "🚔 Живым или мёртвым — ты идёшь смотреть.",
        "🤖 Служить обществу, защищать невиновных, запускать фильм."
    ],
    "назад в будущее": [
        "⚡ Там, куда мы отправляемся, дороги не нужны.",
        "🚗 Флюкс-конденсатор заряжен. Поехали."
    ],
    "бегущий по лезвию": [
        "🌧 Все эти моменты исчезнут, как слёзы под дождём.",
        "🦉 Репликант обнаружен. Запускаю тест Войта-Кампфа."
    ],
    "дюна": [
        "🏜 Страх убивает разум.",
        "🪱 Пряность должна течь."
    ],
    "властелин колец": [
        "💍 Нельзя просто так взять и не посмотреть.",
        "🧙 Ты не пройдёшь... мимо этого фильма."
    ],
    "гарри поттер": [
        "🪄 Accio фильм!",
        "⚡ Торжественно клянусь, что замышляю только просмотр."
    ],
    "джон уик": [
        "✏️ Одним карандашом. Одним фильмом. Одним вечером.",
        "🐶 Баба Яга выходит на охоту."
    ],
    "крёстный отец": [
        "🤌 Сделаю тебе предложение, от которого невозможно отказаться.",
        "🍷 Семья собирается. Фильм запускается."
    ],
    "бэтмен": [
        "🦇 Я — месть. Я — ночь. Я запускаю фильм.",
        "🦇 Бэт-сигнал принят. Открываю досье."
    ],
    "таксист": [
        "🚕 You talkin’ to me?",
        "🌃 Ночной город уже ждёт."
    ],
    "бойцовский клуб": [
        "🧼 Первое правило клуба: никому не рассказывать, что скрипт имба.",
        "🥊 Ты встретил меня в очень странный период моей жизни."
    ],
}

GENERIC_QUOTES = [
    "🎬 Проектор включён. Ищу достойную копию.",
    "🍿 Попкорн готов. Начинаю поиск.",
    "📼 Кассета вставлена. Перематываю к началу.",
    "🎞 Свет гаснет. Начинается магия.",
    "📡 Сканирую Rutube в поисках артефакта.",
]

def seq(text):
    return [x.strip() for x in text.split("/") if x.strip()]

MARATHONS = {
    "Фантастика и киберпанк": seq("Звёздные войны / Звёздный путь / Чужой / Хищник / Терминатор / Матрица / Бегущий по лезвию / Робокоп / Безумный Макс / Назад в будущее / Трон / Дюна / Планета обезьян / Люди в чёрном / Доктор Кто / Секретные материалы / Чёрное зеркало"),
    "Супергероика": seq("Marvel / DC / Человек-паук / Люди Икс / Стражи Галактики / Мстители / Хранители / Пацаны"),
    "Фэнтези": seq("Властелин колец / Хоббит / Гарри Поттер / Игра престолов / Ведьмак / Нарния / Пираты Карибского моря / Конан-варвар"),
    "Хоррор": seq("Кошмар на улице Вязов / Пятница 13-е / Хэллоуин / Крик / Зловещие мертвецы / Пила / Заклятие / Оно / Восставший из ада / Техасская резня бензопилой / Пункт назначения / Астрал"),
    "Боевики и криминал": seq("Джон Уик / Крепкий орешек / Миссия невыполнима / Джеймс Бонд / Форсаж / Рэмбо / Рокки / Смертельное оружие / Убить Билла / Крёстный отец / Лицо со шрамом"),
    "Анимация": seq("Шрек / История игрушек / Корпорация монстров / Как приручить дракона / Кунг-фу Панда / Ледниковый период / Гадкий я / Симпсоны / Футурама / Рик и Морти / Южный парк / Гравити Фолз / Время приключений"),
}

ORDERS = {
    "Звёздные войны": seq("Звёздные войны: Эпизод IV — Новая надежда / Звёздные войны: Эпизод V — Империя наносит ответный удар / Звёздные войны: Эпизод VI — Возвращение джедая / Звёздные войны: Эпизод I — Скрытая угроза / Звёздные войны: Эпизод II — Атака клонов / Звёздные войны: Эпизод III — Месть ситхов / Звёздные войны: Эпизод VII — Пробуждение силы / Звёздные войны: Эпизод VIII — Последние джедаи / Звёздные войны: Эпизод IX — Скайуокер. Восход / Изгой-один: Звёздные войны. Истории / Хан Соло: Звёздные войны. Истории / Звёздные войны: Войны клонов / Звёздные войны: Повстанцы / Мандалорец / Книга Бобы Фетта / Асока"),
    "Звёздный путь": seq("Звёздный путь: Оригинальный сериал / Звёздный путь: Анимационный сериал / Звёздный путь фильм 1 / Звёздный путь 2: Гнев Хана / Звёздный путь 3: В поисках Спока / Звёздный путь 4: Дорога домой / Звёздный путь 5: Последний рубеж / Звёздный путь 6: Неоткрытая страна / Звёздный путь: Следующее поколение / Звёздный путь: Поколения / Звёздный путь: Первый контакт / Звёздный путь: Восстание / Звёздный путь: Возмездие / Звёздный путь: Глубокий космос 9 / Звёздный путь: Вояджер / Звёздный путь: Энтерпрайз / Звёздный путь: Дискавери / Звёздный путь: Странные новые миры / Звёздный путь 2009 / Стартрек: Возмездие / Стартрек: Бесконечность"),
    "Чужой": seq("Чужой / Чужие / Чужой 3 / Чужой: Воскрешение / Прометей / Чужой: Завет / Чужой против Хищника / Чужие против Хищника: Реквием"),
    "Хищник": seq("Хищник / Хищник 2 / Хищники / Хищник 2018 / Добыча"),
    "Терминатор": seq("Терминатор / Терминатор 2: Судный день / Терминатор: Тёмные судьбы / Терминатор 3: Восстание машин / Терминатор: Да придёт спаситель / Терминатор: Генезис"),
    "Матрица": seq("Матрица / Аниматрица / Матрица: Перезагрузка / Матрица: Революция / Матрица: Воскрешение"),
    "Бегущий по лезвию": seq("Бегущий по лезвию: Последняя версия / Бегущий по лезвию: Блэкаут 2022 / 2036: Восход Nexus / 2048: Некуда бежать / Бегущий по лезвию 2049"),
    "Робокоп": seq("Робокоп / Робокоп 2 / Робокоп 3"),
    "Безумный Макс": seq("Фуриоса: Хроники Безумного Макса / Безумный Макс / Безумный Макс 2: Воин дороги / Безумный Макс 3: Под куполом грома / Безумный Макс: Дорога ярости"),
    "Назад в будущее": seq("Назад в будущее / Назад в будущее 2 / Назад в будущее 3"),
    "Трон": seq("Трон / Трон: Восстание / Трон: Наследие"),
    "Дюна": seq("Дюна 2021 / Дюна: Часть вторая"),
    "Планета обезьян": seq("Восстание планеты обезьян / Планета обезьян: Революция / Планета обезьян: Война / Планета обезьян: Новое царство / Планета обезьян 1968 / Под планетой обезьян / Бегство с планеты обезьян / Завоевание планеты обезьян / Битва за планету обезьян"),
    "Люди в чёрном": seq("Люди в чёрном / Люди в чёрном 2 / Люди в чёрном 3 / Люди в чёрном: Интернэшнл"),
    "Доктор Кто": seq("Доктор Кто: классика / Доктор Кто: новый сериал"),
    "Секретные материалы": seq("Секретные материалы 1 сезон / Секретные материалы 2 сезон / Секретные материалы 3 сезон / Секретные материалы 4 сезон / Секретные материалы 5 сезон / Секретные материалы: Борьба за будущее / Секретные материалы 6 сезон / Секретные материалы 7 сезон / Секретные материалы 8 сезон / Секретные материалы 9 сезон / Секретные материалы: Хочу верить / Секретные материалы 10 сезон / Секретные материалы 11 сезон"),
    "Чёрное зеркало": seq("Чёрное зеркало 1 сезон / Чёрное зеркало 2 сезон / Чёрное зеркало 3 сезон / Чёрное зеркало 4 сезон / Чёрное зеркало 5 сезон / Чёрное зеркало 6 сезон"),
    "Marvel": seq("Железный человек / Мстители / Мстители: Эра Альтрона / Первый мститель: Противостояние / Мстители: Война бесконечности / Мстители: Финал / Стражи Галактики / Стражи Галактики. Часть 2 / Стражи Галактики. Часть 3 / Человек-паук: Возвращение домой / Человек-паук: Вдали от дома / Человек-паук: Нет пути домой / Доктор Стрэндж / Доктор Стрэндж: В мультивселенной безумия / Чёрная вдова / Вечные / Тор: Любовь и гром"),
    "DC": seq("Человек из стали / Бэтмен против Супермена / Отряд самоубийц / Чудо-женщина / Лига справедливости Зака Снайдера / Аквамен / Шазам / Хищные птицы / Отряд самоубийц: Миссия навылет / Чёрный Адам / Флэш / Аквамен и потерянное царство / Синий Жук"),
    "Человек-паук": seq("Человек-паук / Человек-паук 2 / Человек-паук 3 / Новый Человек-паук / Новый Человек-паук: Высокое напряжение / Человек-паук: Возвращение домой / Человек-паук: Вдали от дома / Человек-паук: Нет пути домой / Человек-паук: Через вселенные / Человек-паук: Паутина вселенных"),
    "Люди Икс": seq("Люди Икс: Первый класс / Люди Икс: Дни минувшего будущего / Люди Икс: Апокалипсис / Люди Икс: Тёмный Феникс / Люди Икс / Люди Икс 2 / Люди Икс: Последняя битва / Люди Икс: Начало. Росомаха / Логан"),
    "Стражи Галактики": seq("Стражи Галактики / Стражи Галактики. Часть 2 / Стражи Галактики: Праздничный спецвыпуск / Стражи Галактики. Часть 3"),
    "Мстители": seq("Мстители / Мстители: Эра Альтрона / Мстители: Война бесконечности / Мстители: Финал"),
    "Хранители": seq("Хранители 2009 / Хранители сериал 2019"),
    "Пацаны": seq("Пацаны 1 сезон / Пацаны 2 сезон / Пацаны 3 сезон / Поколение Ви / Пацаны 4 сезон"),
    "Властелин колец": seq("Властелин колец: Братство кольца / Властелин колец: Две крепости / Властелин колец: Возвращение короля / Хоббит: Нежданное путешествие / Хоббит: Пустошь Смауга / Хоббит: Битва пяти воинств"),
    "Хоббит": seq("Хоббит: Нежданное путешествие / Хоббит: Пустошь Смауга / Хоббит: Битва пяти воинств / Властелин колец: Братство кольца / Властелин колец: Две крепости / Властелин колец: Возвращение короля"),
    "Гарри Поттер": seq("Гарри Поттер и философский камень / Гарри Поттер и Тайная комната / Гарри Поттер и узник Азкабана / Гарри Поттер и Кубок огня / Гарри Поттер и Орден Феникса / Гарри Поттер и Принц-полукровка / Гарри Поттер и Дары Смерти: Часть 1 / Гарри Поттер и Дары Смерти: Часть 2 / Фантастические твари и где они обитают / Фантастические твари: Преступления Грин-де-Вальда / Фантастические твари: Тайны Дамблдора"),
    "Игра престолов": seq("Игра престолов 1 сезон / Игра престолов 2 сезон / Игра престолов 3 сезон / Игра престолов 4 сезон / Игра престолов 5 сезон / Игра престолов 6 сезон / Игра престолов 7 сезон / Игра престолов 8 сезон / Дом Дракона"),
    "Ведьмак": seq("Ведьмак: Кошмар волка / Ведьмак 1 сезон / Ведьмак 2 сезон / Ведьмак 3 сезон"),
    "Нарния": seq("Хроники Нарнии: Лев, колдунья и волшебный шкаф / Хроники Нарнии: Принц Каспиан / Хроники Нарнии: Покоритель зари"),
    "Пираты Карибского моря": seq("Пираты Карибского моря: Проклятие Чёрной жемчужины / Пираты Карибского моря: Сундук мертвеца / Пираты Карибского моря: На краю света / Пираты Карибского моря: На странных берегах / Пираты Карибского моря: Мертвецы не рассказывают сказки"),
    "Конан-варвар": seq("Конан-варвар 1982 / Конан-разрушитель"),
    "Кошмар на улице Вязов": seq("Кошмар на улице Вязов 1 / Кошмар на улице Вязов 2 / Кошмар на улице Вязов 3 / Кошмар на улице Вязов 4 / Кошмар на улице Вязов 5 / Фредди мёртв: Последний кошмар / Новый кошмар Уэса Крэйвена"),
    "Пятница 13-е": seq("Пятница 13-е 1 / Пятница 13-е 2 / Пятница 13-е 3 / Пятница 13-е 4 / Пятница 13-е 5 / Пятница 13-е 6 / Пятница 13-е 7 / Пятница 13-е 8 / Джейсон отправляется в ад / Джейсон X / Фредди против Джейсона"),
    "Хэллоуин": seq("Хэллоуин 1978 / Хэллоуин 2018 / Хэллоуин убивает / Хэллоуин заканчивается"),
    "Крик": seq("Крик / Крик 2 / Крик 3 / Крик 4 / Крик 2022 / Крик 6"),
    "Зловещие мертвецы": seq("Зловещие мертвецы / Зловещие мертвецы 2 / Армия тьмы / Эш против зловещих мертвецов / Зловещие мертвецы: Чёрная книга / Восстание зловещих мертвецов"),
    "Пила": seq("Пила / Пила 2 / Пила 3 / Пила 4 / Пила 5 / Пила 6 / Пила 3D / Пила 8 / Спираль: Наследие Пилы / Пила 10"),
    "Заклятие": seq("Заклятие / Заклятие 2 / Заклятие 3 / Проклятие монахини / Проклятие монахини 2 / Проклятие Аннабель / Проклятие Аннабель: Зарождение зла / Проклятие Аннабель 3"),
    "Оно": seq("Оно 2017 / Оно 2"),
    "Восставший из ада": seq("Восставший из ада / Восставший из ада 2 / Восставший из ада 3 / Восставший из ада 4"),
    "Техасская резня бензопилой": seq("Техасская резня бензопилой 1974 / Техасская резня бензопилой 2022"),
    "Пункт назначения": seq("Пункт назначения 5 / Пункт назначения / Пункт назначения 2 / Пункт назначения 3 / Пункт назначения 4"),
    "Астрал": seq("Астрал 3 / Астрал 4: Последний ключ / Астрал / Астрал: Глава 2 / Астрал 5: Красная дверь"),
    "Джон Уик": seq("Джон Уик / Джон Уик 2 / Джон Уик 3 / Джон Уик 4"),
    "Крепкий орешек": seq("Крепкий орешек / Крепкий орешек 2 / Крепкий орешек 3 / Крепкий орешек 4.0 / Крепкий орешек: Хороший день, чтобы умереть"),
    "Миссия невыполнима": seq("Миссия невыполнима / Миссия невыполнима 2 / Миссия невыполнима 3 / Миссия невыполнима: Протокол Фантом / Миссия невыполнима: Племя изгоев / Миссия невыполнима: Последствия / Миссия невыполнима: Смертельная расплата"),
    "Джеймс Бонд": seq("Казино Рояль / Квант милосердия / 007: Координаты Скайфолл / 007: Спектр / Не время умирать"),
    "Форсаж": seq("Форсаж / Двойной форсаж / Форсаж 4 / Форсаж 5 / Форсаж 6 / Тройной форсаж: Токийский дрифт / Форсаж 7 / Форсаж 8 / Форсаж: Хоббс и Шоу / Форсаж 9 / Форсаж 10"),
    "Рэмбо": seq("Рэмбо: Первая кровь / Рэмбо: Первая кровь 2 / Рэмбо 3 / Рэмбо 4 / Рэмбо: Последняя кровь"),
    "Рокки": seq("Рокки / Рокки 2 / Рокки 3 / Рокки 4 / Рокки 5 / Рокки Бальбоа / Крид: Наследие Рокки / Крид 2 / Крид 3"),
    "Смертельное оружие": seq("Смертельное оружие / Смертельное оружие 2 / Смертельное оружие 3 / Смертельное оружие 4"),
    "Убить Билла": seq("Убить Билла. Фильм 1 / Убить Билла. Фильм 2"),
    "Крёстный отец": seq("Крёстный отец / Крёстный отец 2 / Крёстный отец 3"),
    "Лицо со шрамом": seq("Лицо со шрамом"),
    "Шрек": seq("Шрек / Шрек 2 / Шрек Третий / Шрек навсегда / Кот в сапогах / Кот в сапогах 2: Последнее желание"),
    "История игрушек": seq("История игрушек / История игрушек 2 / История игрушек 3 / История игрушек 4"),
    "Корпорация монстров": seq("Университет монстров / Корпорация монстров"),
    "Как приручить дракона": seq("Как приручить дракона / Как приручить дракона 2 / Как приручить дракона 3"),
    "Кунг-фу Панда": seq("Кунг-фу Панда / Кунг-фу Панда 2 / Кунг-фу Панда 3 / Кунг-фу Панда 4"),
    "Ледниковый период": seq("Ледниковый период / Ледниковый период 2 / Ледниковый период 3 / Ледниковый период 4 / Ледниковый период 5"),
    "Гадкий я": seq("Миньоны / Миньоны: Грювитация / Гадкий я / Гадкий я 2 / Гадкий я 3 / Гадкий я 4"),
    "Симпсоны": seq("Симпсоны по сезонам / Симпсоны в кино"),
    "Футурама": seq("Футурама по сезонам"),
    "Рик и Морти": seq("Рик и Морти по сезонам"),
    "Южный парк": seq("Южный парк по сезонам / Южный парк: Большой, длинный и необрезанный"),
    "Гравити Фолз": seq("Гравити Фолз 1 сезон / Гравити Фолз 2 сезон"),
    "Время приключений": seq("Время приключений по сезонам / Время приключений: Далёкие земли / Фионна и Кейк"),
}

def timestamp():
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

def norm(text):
    return " ".join(text.strip().split())

def all_franchises():
    result = []
    for cat, items in MARATHONS.items():
        for title in items:
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

def quote(query):
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

def is_bad(title):
    low = title.lower()
    return any(w in low for w in BAD_WORDS)

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
        if is_bad(title):
            continue

        url = item.get("video_url") or item.get("html_url") or item.get("url")
        if not url and item.get("id"):
            url = f"https://rutube.ru/video/{item.get('id')}/"

        dur_raw = item.get("duration") or item.get("duration_string") or item.get("video_duration")
        dur = parse_duration(dur_raw)

        if strict and dur and dur < MIN_DURATION:
            continue

        if url:
            videos.append({"title": title, "url": url, "duration": dur_raw or "??"})

    return videos

def choose(videos):
    print("Найдено:\n")
    for i, v in enumerate(videos, 1):
        print(f"{i}. {v['title']} [{v['duration']}]")
    choice = input("\nEnter = первый результат | номер = выбрать: ").strip()
    if not choice:
        return 0
    if choice.isdigit() and 1 <= int(choice) <= len(videos):
        return int(choice) - 1
    print("❌ Неверный номер.")
    return None

def play_query(query, strict=True):
    print("\n" + quote(query))
    print(f"🔎 Ищу на Rutube: {query}\n")

    videos = search_rutube(query, strict)
    if not videos:
        print("❌ Ничего нормального не нашёл.")
        print("Поиск вручную:")
        print("https://rutube.ru/search/?query=" + urllib.parse.quote(query))
        return False

    idx = choose(videos)
    if idx is None:
        return False

    url = videos[idx]["url"]
    print(f"\n▶️ Открываю fullscreen:\n{url}\n")
    subprocess.run(["mpv", "--fs", "--force-window=yes", url])
    return True

def watchlist():
    return load(WATCHLIST, [])

def save_watchlist(data):
    save(WATCHLIST, data)

def unwatched():
    return [x for x in watchlist() if not x.get("watched")]

def watched():
    return [x for x in watchlist() if x.get("watched")]

def show_watchlist():
    items = unwatched()
    print("\n🎬 ТВОЙ СПИСОК НА ПРОСМОТР\n")
    if not items:
        print('Пусто. Добавить: vsearch -add "Нечто / Матрица"')
        return
    for i, item in enumerate(items, 1):
        print(f"{i}. {item['title']}")
    print("\nГлавное:")
    print("vsearch -list        открыть первый фильм")
    print("vsearch -list 10     открыть фильм №10")
    print("vsearch -marathons   интерактивные марафоны")

def add_movies(raw):
    db = watchlist()
    existing = {x["title"].lower() for x in db}
    movies = [norm(x) for x in raw.replace("\n", "/").split("/") if norm(x)]
    added = 0
    for m in movies:
        if m.lower() in existing:
            continue
        db.append({"title": m, "watched": False, "added_at": timestamp(), "watched_at": None, "rating": None})
        existing.add(m.lower())
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
        ans = input("\nОтметить просмотренным? [y/N]: ").strip().lower()
        if ans in ["y", "yes", "д", "да"]:
            mark_done(num)

def mark_done(num):
    db = watchlist()
    items = [x for x in db if not x.get("watched")]
    if num < 1 or num > len(items):
        print("❌ Нет такого номера.")
        return
    item = items[num - 1]
    item["watched"] = True
    item["watched_at"] = timestamp()
    rating = input("Оценка 1–10, Enter чтобы пропустить: ").strip()
    if rating.isdigit() and 1 <= int(rating) <= 10:
        item["rating"] = int(rating)
    save_watchlist(db)
    print(f"✅ Просмотрено: {item['title']}")
    if len(watched()) and len(watched()) % 10 == 0:
        print(f"\n🔥 Уже {len(watched())} фильмов. Не забудь занести оценки в Letterboxd.\n")
        show_history()

def show_history():
    items = watched()
    print("\n✅ ПРОСМОТРЕННОЕ\n")
    if not items:
        print("Пока пусто.")
        return
    for i, item in enumerate(items, 1):
        rating = f"{item.get('rating')}/10" if item.get("rating") else "без оценки"
        print(f"{i}. {item['title']} — {rating}")

def show_stats():
    db = watchlist()
    total = len(db)
    done = len([x for x in db if x.get("watched")])
    rated = [x for x in db if x.get("rating")]
    avg = round(sum(int(x["rating"]) for x in rated) / len(rated), 2) if rated else "нет"
    queue = load(MQUEUE, [])
    print("\n📊 СТАТИСТИКА\n")
    print(f"Фильмов всего: {total}")
    print(f"Просмотрено: {done}")
    print(f"Осталось: {total - done}")
    print(f"Прогресс: {round(done / total * 100, 1) if total else 0}%")
    print(f"Средняя оценка: {avg}")
    print(f"Марафонов в очереди: {len(queue)}")

def show_order(title):
    print(f"\n🎞 ПОРЯДОК МАРАФОНА: {title}\n")
    for i, part in enumerate(order_for(title), 1):
        print(f"{i}. {part}")

def menu_marathons():
    cats = list(MARATHONS.keys())
    while True:
        print("\n🏁 МАРАФОНЫ\n")
        for i, cat in enumerate(cats, 1):
            print(f"{i}. {cat} ({len(MARATHONS[cat])})")
        print("0. Выход")
        c = input("\nКатегория: ").strip()
        if c == "0":
            return
        if not c.isdigit() or not (1 <= int(c) <= len(cats)):
            print("❌ Неверный номер.")
            continue
        cat = cats[int(c) - 1]
        items = MARATHONS[cat]
        while True:
            print(f"\n🏁 {cat}\n")
            for i, title in enumerate(items, 1):
                print(f"{i}. {title}")
            print("0. Назад")
            f = input("\nФраншиза: ").strip()
            if f == "0":
                break
            if not f.isdigit() or not (1 <= int(f) <= len(items)):
                print("❌ Неверный номер.")
                continue
            title = items[int(f) - 1]
            while True:
                print(f"\n🎬 {title}\n")
                print("1. Показать порядок")
                print("2. Включить первую часть")
                print("3. Добавить в очередь")
                print("4. Включить следующую часть из очереди")
                print("0. Назад")
                a = input("\nДействие: ").strip()
                if a == "0":
                    break
                if a == "1":
                    show_order(title)
                elif a == "2":
                    play_marathon_direct(title)
                elif a == "3":
                    add_marathon(title)
                elif a == "4":
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
    print(f"\n🏁 {cat}\n")
    for i, title in enumerate(MARATHONS[cat], 1):
        print(f"{i}. {title}")

def mqueue():
    return load(MQUEUE, [])

def save_mqueue(q):
    save(MQUEUE, q)

def add_marathon(query):
    cat, title = find_franchise(query)
    if not title:
        title = query.strip()
        cat = "Другое"
    q = mqueue()
    if any(x["title"].lower() == title.lower() and not x.get("done") for x in q):
        print(f"⚠️ Уже в очереди: {title}")
        return
    q.append({"title": title, "category": cat, "current_index": 0, "done": False, "added_at": timestamp(), "done_at": None, "rating": None})
    save_mqueue(q)
    print(f"✅ Марафон добавлен: {title}")
    show_mqueue()

def show_mqueue():
    q = mqueue()
    print("\n🏁 ОЧЕРЕДЬ МАРАФОНОВ\n")
    active = [x for x in q if not x.get("done")]
    done = [x for x in q if x.get("done")]
    if not active and not done:
        print('Пусто. Добавить: vsearch -madd "Звёздные войны"')
        return
    if active:
        print("Активные:\n")
        for i, item in enumerate(active, 1):
            order = order_for(item["title"])
            idx = int(item.get("current_index", 0))
            cur = order[idx] if idx < len(order) else "завершён"
            print(f"{i}. {item['title']} — {idx + 1}/{len(order)}: {cur}")
    if done:
        print("\nПройденные:\n")
        for item in done:
            rating = f" — {item.get('rating')}/10" if item.get("rating") else ""
            print(f"✅ {item['title']}{rating}")

def play_marathon_direct(query):
    cat, title = find_franchise(query)
    if not title:
        title = query.strip()
    episode = order_for(title)[0]
    print(f"\n🏁 {title}")
    print(f"▶️ Часть 1/{len(order_for(title))}: {episode}")
    play_query(episode, strict=False)

def play_next_marathon():
    q = mqueue()
    active = [x for x in q if not x.get("done")]
    if not active:
        print("❌ Очередь марафонов пустая.")
        return
    item = active[0]
    title = item["title"]
    idx = int(item.get("current_index", 0))
    order = order_for(title)
    if idx >= len(order):
        item["done"] = True
        save_mqueue(q)
        print("✅ Марафон уже завершён.")
        return
    episode = order[idx]
    print(f"\n🏁 {title}")
    print(f"▶️ Часть {idx + 1}/{len(order)}: {episode}")
    if play_query(episode, strict=False):
        ans = input("\nОтметить эту часть просмотренной? [y/N]: ").strip().lower()
        if ans in ["y", "yes", "д", "да"]:
            item["current_index"] = idx + 1
            if item["current_index"] >= len(order):
                item["done"] = True
                item["done_at"] = timestamp()
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
    item["done_at"] = timestamp()
    item["current_index"] = len(order_for(item["title"]))
    save_mqueue(q)
    print(f"✅ Марафон пройден: {item['title']}")

def help_text():
    print("""
vsearch — кино-комбайн

Фильмы:
  vsearch
  vsearch -list
  vsearch -list 10
  vsearch -add "Фильм 1 / Фильм 2"
  vsearch -done 1
  vsearch -history
  vsearch -stats
  vsearch "Железный человек"   сразу найти и включить фильм

Марафоны:
  vsearch -marathons        интерактивное меню цифрами
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
        show_watchlist()
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
        add_movies(" ".join(args[1:]))

    elif cmd == "-done":
        if len(args) < 2 or not args[1].isdigit():
            print("❌ Пример: vsearch -done 1")
        else:
            mark_done(int(args[1]))

    elif cmd == "-history":
        show_history()

    elif cmd == "-stats":
        show_stats()

    elif cmd == "-all":
        for i, item in enumerate(watchlist(), 1):
            mark = "✅" if item.get("watched") else "⬜"
            print(f"{i}. {mark} {item['title']}")

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
        # Если команда не начинается с "-", считаем это названием фильма
        query = " ".join(args).strip()
        if query:
            play_query(query, strict=True)
        else:
            print("❌ Неизвестная команда.")
            help_text()

if __name__ == "__main__":
    main()
