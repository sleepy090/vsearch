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
vsearch                      # интерактивное меню (поиск / новинки / марафоны)
vsearch search <запрос>      # поиск фильмов
vsearch new                  # свежие фильмы
vsearch watch <url>          # проиграть конкретный url
vsearch refresh              # очистить кэш
```

### Марафоны

```
vsearch marathon                       # список франшиз
vsearch marathon "Звёздные войны"       # эпизоды франшизы
vsearch marathon "Звёздные войны" --watch   # проиграть все эпизоды подряд
vsearch marathon-add "Звёздные войны"  # добавить в очередь
vsearch marathon-queue                 # очередь марафонов
vsearch marathon-next                  # следующая часть из очереди
```

### Список фильмов (watchlist)

```
vsearch list list      # список
vsearch list add "Нечто / Матрица / Сталкер"
vsearch list next      # смотреть следующий
vsearch list done 3    # отметить просмотренным
vsearch list rate 3    # оценить из истории
vsearch list history   # история просмотров
vsearch list stats     # статистика
```

### Сериалы

```
vsearch series list                 # список
vsearch series next "Во все тяжкие" # следующая серия
vsearch series add "Во все тяжкие"  # добавить (1 сезон 1 серия)
vsearch series set "Во все тяжкие"  # поставить сезон/серию
vsearch series done "Во все тяжкие" # отметить серию просмотренной
vsearch series del "Во все тяжкие"  # удалить
```

### Проигрыватель

```
vsearch player upscale auto|off|anime|film   # режим апскейла
vsearch player aspect original|crop|stretch  # режим кадра
vsearch player status                        # текущие режимы
```

### Бэкапы

```
vsearch backup     # создать бэкап данных
vsearch restore    # восстановить из последнего
```

## Навигация

Во всех интерактивных списках и меню:

- `↑` / `↓` — перемещение по списку
- `Enter` — выбрать / смотреть
- `i` — детали (в списке фильмов)
- `w` — смотреть в mpv · `o` — открыть в браузере · `a` — добавить в список
- `d` — отметить просмотренным
- `q` / `Esc` — назад

В не-интерактивном режиме (пайпы, скрипты) доступен ввод `N` (номер) или `клавишаN`.

## Как это работает

- Поиск: публичный API Rutube `https://rutube.ru/api/search/video/` — без токена, фолбэк на VK Video.
- Эвристика «фильм»: длительность ≥ 40 мин или описание с полями «Год/Жанр»; сериалы и короткие трейлеры отсекаются.
- Скоринг: точное совпадение названия выше, трейлеры/обзоры/прохождения игр штрафуются.
- Марафоны: кураторская база франшиз (SW, Marvel, LOTR, Гарри Поттер и т.д.), поиск по каждой + сортировка по номеру эпизода (включая римские).
- Воспроизведение: mpv (сам резолвит rutube через yt-dlp) с режимами апскейла и кадра, фолбэк на xdg-open.
- Кэш: JSON в `~/.cache/vsearch/`, поиск ~6ч, марафон ~24ч.

## Данные

- Настройки: `~/.config/vsearch/`
- Данные (список, сериалы, очередь, бэкапы): `~/.local/share/vsearch/`

## Свои франшизы

Скопируй и подправь:

```bash
mkdir -p ~/.config/vsearch
cp vsearch/vsearch/data/franchises.yaml ~/.config/vsearch/franchises.yaml
```

Поля: `name`, `query` (поиск на rutube), `include` (какие слова должны быть в названии, ИЛИ), `exclude` (какие слова исключить).

---
