# vsearch

Поиск и просмотр фильмов на Rutube из терминала.

## Установка

```bash
cd vsearch
python3 -m venv .venv
.venv/bin/pip install -e .
```

После этого доступен `vsearch` (через `.venv/bin/vsearch`) или `python -m vsearch`.

## Использование

```
vsearch                    # интерактивное меню (поиск / новинки / марафоны)
vsearch search <запрос>    # поиск фильмов
vsearch new                # свежие фильмы
vsearch marathon           # список франшиз
vsearch marathon "Звёздные войны"          # эпизоды франшизы
vsearch marathon "Звёздные войны" --watch # проиграть всё подряд
vsearch watch <url>        # проиграть конкретный url
vsearch refresh            # очистить кэш
```

Выбор в списке:
- `N` — детали (описание, год, режиссёр)
- `wN` — смотреть в mpv
- `oN` — открыть в браузере
- `q` — назад

## Как это работает

- Поиск: публичный API Rutube `https://rutube.ru/api/search/video/` — без токена.
- Эвристика «фильм»: длительность ≥ 40 мин или описание с полями «Год/Жанр»; сериалы и короткие трейлеры отсекаются.
- Марафоны: кураторская база франшиз (SW, Marvel, LOTR, Гарри Поттер и т.д.), поиск по каждой + сортировка по номеру эпизода (включая римские).
- Воспроизведение: mpv (сам резолвит rutube через yt-dlp), фолбэк на xdg-open.
- Кэш: JSON в `~/.cache/vsearch/`, поиск ~6ч, марафон ~24ч.

## Свои франшизы

Скопируй и подправь:

```bash
mkdir -p ~/.config/vsearch
cp vsearch/vsearch/data/franchises.yaml ~/.config/vsearch/franchises.yaml
```

Поля: `name`, `query` (поиск на rutube), `include` (какие слова должны быть в названии, ИЛИ), `exclude` (какие слова исключить).

---
