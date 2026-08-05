from __future__ import annotations

import os
import select as _select_mod
import sys
import termios
import tty
from typing import Callable

from rich.console import Console, Group
from rich.live import Live
from rich.markup import escape
from rich.text import Text

# Nord + акценты системы (hypr borders)
BG = "#2E3440"
FG = "#D8DEE9"
DARK = "#3B4252"
COMMENT = "#616E88"
CYAN = "#88C0D0"
BLUE = "#81A1C1"
GREEN = "#A3BE8C"
YELLOW = "#EBCB8B"
RED = "#BF616A"
MAUVE = "#B48EAD"
LAVENDER = "#C5C2EA"
PINK = "#EFB8C9"

console = Console()

_KEY_UP = "up"
_KEY_DOWN = "down"
_KEY_ENTER = "enter"
_KEY_ESC = "esc"
_KEY_BACK = "q"


def _read_seq(fd: int, buf: bytes) -> str:
    if buf.startswith(b"\x1b"):
        extra = _read_more(fd)
        seq = buf + extra
        if seq in (b"\x1b[A", b"\x1bOA"):
            return _KEY_UP
        if seq in (b"\x1b[B", b"\x1bOB"):
            return _KEY_DOWN
        if seq in (b"\x1b[C", b"\x1bOC"):
            return "right"
        if seq in (b"\x1b[D", b"\x1bOD"):
            return "left"
        return _KEY_ESC
    if buf in (b"\r", b"\n"):
        return _KEY_ENTER
    return buf.decode("utf-8", errors="ignore").lower()


def _read_more(fd: int, timeout: float = 0.05) -> bytes:
    out = b""
    while True:
        ready, _, _ = _select_mod.select([fd], [], [], timeout)
        if not ready:
            return out
        try:
            chunk = os.read(fd, 4)
        except OSError:
            return out
        if not chunk:
            return out
        out += chunk


def read_key() -> str:
    """Прочитать одно нажатие. В не-TTY (пайпы/тесты) читает строку input()."""
    if not sys.stdin.isatty():
        try:
            line = input("").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return _KEY_BACK
        if not line:
            return _KEY_ENTER
        return line
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        buf = os.read(fd, 1)
    except (OSError, ValueError):
        return _KEY_BACK
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
    if not buf:
        return _KEY_BACK
    return _read_seq(fd, buf)


def _marker(selected: bool) -> str:
    return "❯" if selected else " "


def _row_style(selected: bool) -> str:
    return f"on {DARK} bold" if selected else ""


def select(
    items: list,
    *,
    line: Callable[[object], str],
    subline: Callable[[object], str] | None = None,
    title: str = "",
    footer: str = "",
    enter_help: str = "выбрать",
    keys: dict[str, str] | None = None,
) -> tuple[object | None, str]:
    """Стрелочный выбор из списка. Возвращает (item, action).
    action: enter | буква горячей клавиши | q (назад). item=None при q/пусто."""
    keys = keys or {}
    if not items:
        return None, _KEY_BACK
    index = 0
    total = len(items)

    def render() -> Table:
        from rich.table import Table

        table = Table(
            title=title,
            box=None,
            pad_edge=False,
            show_header=False,
            expand=False,
            title_style=f"bold {LAVENDER}",
        )
        table.add_column("", justify="right", width=2)
        table.add_column("", no_wrap=False)
        for i, item in enumerate(items):
            selected = i == index
            main = line(item)
            table.add_row(
                Text(_marker(selected), style=_row_style(selected)),
                Text(escape(main), style=_row_style(selected)),
                style=_row_style(selected),
            )
            if subline is not None:
                sub = subline(item)
                if sub:
                    table.add_row(
                        "",
                        Text(escape(sub), style=f"dim on {DARK}" if selected else "dim"),
                        style=f"on {DARK}" if selected else "",
                    )
        return table

    def help_bar() -> Text:
        parts = []
        parts.append(f"[{CYAN}]↑/↓[/] навигация · [bold {YELLOW}]Enter[/] {enter_help}")
        for k, desc in keys.items():
            parts.append(f"[bold {YELLOW}]{k}[/] {desc}")
        if not keys:
            parts.append(f"[bold {YELLOW}]q[/] назад")
        if footer:
            parts.append(f"[dim]{footer}[/dim]")
        return Text.from_markup("  ".join(parts))

    if not sys.stdin.isatty():
        return _select_pipe(
            items, line=line, subline=subline, title=title, keys=keys, enter_help=enter_help
        )

    with Live(
        console=console,
        screen=False,
        transient=True,
        auto_refresh=False,
    ) as live:
        live.update(Group(render(), help_bar()))
        while True:
            key = read_key()
            if key == _KEY_UP:
                index = (index - 1) % total
                live.update(Group(render(), help_bar()))
            elif key == _KEY_DOWN:
                index = (index + 1) % total
                live.update(Group(render(), help_bar()))
            elif key == _KEY_ENTER:
                return items[index], _KEY_ENTER
            elif key in keys:
                return items[index], key
            elif key in (_KEY_BACK, _KEY_ESC):
                return None, _KEY_BACK


def _select_pipe(
    items: list,
    *,
    line: Callable[[object], str],
    subline: Callable[[object], str] | None = None,
    title: str = "",
    keys: dict[str, str] | None = None,
    enter_help: str = "выбрать",
) -> tuple[object | None, str]:
    """Fallback без TTY: нумерованный список + ввод «число» или «клавишаN»."""
    keys = keys or {}
    console.print(f"[bold {LAVENDER}]{title}[/bold {LAVENDER}]")
    for i, item in enumerate(items, 1):
        console.print(f"[dim]{i:>2}.[/dim] {escape(line(item))}")
        if subline is not None:
            sub = subline(item)
            if sub:
                console.print(f"      [dim]{escape(sub)}[/dim]")
    hint = f"[dim]номер | Enter=1 | q — назад"
    for k in keys:
        hint += f" | {k}N"
    hint += "[/dim]"
    console.print(hint)
    while True:
        key = read_key()
        if key in (_KEY_BACK, _KEY_ESC):
            return None, _KEY_BACK
        if key == _KEY_ENTER:
            return items[0], _KEY_ENTER
        action, num = "enter", key
        for k in keys:
            if key.startswith(k) and len(key) > len(k):
                action, num = k, key[len(k):]
                break
        if action != "enter" and not num:
            return items[0], action
        if num.isdigit():
            n = int(num)
            if 1 <= n <= len(items):
                return items[n - 1], action
        if action != "enter":
            return items[0], action
        console.print(f"[{RED}]нет номера {num}[/{RED}]")


def confirm(prompt: str, default: bool = False) -> bool:
    """Стрелочный Да/Нет."""
    choices = [("yes", "Да"), ("no", "Нет")]
    if not sys.stdin.isatty():
        return default
    item, action = select(
        choices,
        line=lambda c: c[1],
        title=prompt,
        enter_help="подтвердить",
        keys={"y": "да", "n": "нет"},
    )
    if item is None:
        return default
    return item[0] == "yes"


def prompt_rating(prompt: str) -> int | None:
    if not sys.stdin.isatty():
        try:
            line = input(f"{prompt} ").strip()
        except (EOFError, KeyboardInterrupt):
            return None
    else:
        try:
            line = input(f"{prompt} ").strip()
        except (EOFError, KeyboardInterrupt):
            return None
    if line.isdigit() and 1 <= int(line) <= 10:
        return int(line)
    return None
