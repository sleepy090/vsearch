# vsearch

Поиск и просмотр фильмов на Rutube из терминала.

## Установка

### Linux (рекомендуемый способ)

Сначала установи Python и `mpv` — `mpv` нужен для просмотра фильмов в отдельном окне.

Arch Linux / CachyOS:

```bash
sudo pacman -S --needed git python python-pip mpv
```

Ubuntu / Debian:

```bash
sudo apt update
sudo apt install -y git python3 python3-venv mpv
```

Затем скачай проект и установи его в виртуальное окружение:

```bash
git clone https://github.com/sleepy090/vsearch.git
cd vsearch
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install .
```

После установки запускай программу из каталога проекта:

```bash
source .venv/bin/activate
vsearch
```

Если не хочешь активировать окружение, используй полный путь:

```bash
./.venv/bin/vsearch
```

Проверить установку можно так:

```bash
vsearch --help
```

### Обновление

```bash
cd vsearch
git pull
source .venv/bin/activate
python -m pip install .
```

### Без `mpv`

Искать фильмы можно и без `mpv`, но для просмотра приложение откроет ссылку в браузере.
На Linux для этого обычно нужен `xdg-open` (он входит в стандартное графическое окружение).

## Использование

```
vsearch                      # интерактивное меню (поиск / новинки / марафоны)
vsearch search <запрос>      # поиск фильмов
vsearch new                  # свежие фильмы (курируемые «Новинки» Rutube)
vsearch new 2025             # фильмы 2025 года · new/2026/2025/2024
vsearch new боевики          # по жанру: боевики/комедии/драмы/фантастика…
vsearch new popular          # TMDB: popular · upcoming · top_rated (если задан ключ)
vsearch watch <url>          # проиграть конкретный url
vsearch refresh              # очистить кэш
```

### Новинки

По умолчанию `vsearch new` показывает курируемый раздел Rutube «Новинки»
(«Новые фильмы и сериалы») — реальные свежие релизы без всяких ключей.
Доступны теги-источники: `new`, `2026`, `2025`, `2024` и жанры
(`боевики`, `комедии`, `драмы`, `фантастика`, `триллеры`, …).
Серии и кликбейт отсекаются.

Если задан TMDB-ключ, `vsearch new popular/upcoming/top_rated/now`
берёт списки с TMDB и ищет каждый фильм на Rutube.

TMDB нужен бесплатный API-ключ. Получи его на
<https://www.themoviedb.org/settings/api> и добавь в настройки:

```bash
# ~/.config/vsearch/settings.json
{
  "tmdb_api_key": "твой_ключ"
}
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
