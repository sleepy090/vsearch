from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from . import config
from .scoring import key, year_extract, year_from_hints

LOG = "/tmp/vsearch-player.log"

_ANIMATION_WORDS = [
    "мультфильм", "аниме", "animation", "animated",
    "шрек", "shrek", "история игрушек", "toy story",
    "корпорация монстров", "monsters inc", "университет монстров",
    "как приручить дракона", "кунг-фу панда", "ледниковый период",
    "гадкий я", "миньоны", "мадагаскар", "тачки", "суперсемейка",
    "монстры на каникулах", "в поисках немо", "в поисках дори",
    "ральф", "зверополис", "призрак в доспехах", "акира", "паприка",
    "аниматрица", "ковбой бибоп", "евангелион", "навсикая",
]

_OLD_FILM_WORDS = [
    "тарковский", "кубри", "линч", "карпентер", "кроненберг",
    "скорсезе", "балабанов", "солярис", "сталкер", "робокоп",
    "чужой", "чужие", "терминатор", "видеодром", "таксист",
    "бегущий по лезвию", "назад в будущее", "безумный макс",
    "кин-дза-дза", "брат",
]


def _spawn(cmd):
    try:
        with open(LOG, "a", encoding="utf-8") as lf:
            return subprocess.Popen(
                cmd, stdout=subprocess.DEVNULL, stderr=lf,
                stdin=subprocess.DEVNULL,
            )
    except OSError:
        return None


def have_mpv() -> bool:
    return shutil.which("mpv") is not None


def have_browser() -> bool:
    return shutil.which("xdg-open") is not None or shutil.which("open") is not None


def open_browser(url: str):
    for opener in ("xdg-open", "open"):
        if shutil.which(opener):
            return _spawn([opener, url])
    return None


def detect_auto_upscale_mode(title: str) -> str:
    q = key(title)
    if any(w in q for w in _ANIMATION_WORDS):
        return "anime"
    year = year_from_hints(title) or year_extract(title)
    if year and year <= 2005:
        return "film"
    if any(w in q for w in _OLD_FILM_WORDS):
        return "film"
    return "off"


def effective_upscale_mode(title: str) -> str:
    settings = config.load_settings()
    mode = settings.get("upscale_mode", "auto")
    if mode == "auto":
        return detect_auto_upscale_mode(title)
    return mode


def _shader_path(value) -> Path | None:
    if not value:
        return None
    path = Path(str(value)).expanduser()
    return path if path.exists() else None


def build_mpv_args(url: str, title: str | None = None):
    settings = config.load_settings()
    args = ["mpv"]
    if settings.get("open_fullscreen", True):
        args.append("--fs")
    args.append("--force-window=yes")

    target = title or url
    upscale = effective_upscale_mode(target)
    aspect = settings.get("aspect_mode", "original")

    if upscale == "anime":
        restore = _shader_path(settings.get("anime4k_restore_shader"))
        upscale_shader = _shader_path(settings.get("anime4k_upscale_shader"))
        if restore:
            args.append(f"--glsl-shader={restore}")
        if upscale_shader:
            args.append(f"--glsl-shader={upscale_shader}")
        args.extend([
            "--scale=ewa_lanczossharp",
            "--cscale=ewa_lanczossharp",
            "--dscale=mitchell",
            "--correct-downscaling=yes",
            "--sigmoid-upscaling=yes",
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
            "--vf-add=lavfi=[unsharp=5:5:0.6:3:3:0.3]",
        ])

    if aspect == "crop":
        args.append("--panscan=1.0")
    elif aspect == "stretch":
        args.append("--video-aspect-override=16:9")

    args.append(url)
    return args


def play(urls, audio_only: bool = False):
    urls = [u for u in urls if u]
    if not urls:
        return None
    if have_mpv():
        args = build_mpv_args(urls[0], title=None)
        if audio_only:
            args.append("--no-video")
        if len(urls) > 1:
            args = ["mpv", "--fs", "--force-window=yes"] + urls
        return _spawn(args)
    if len(urls) == 1 and open_browser(urls[0]):
        return "browser"
    return None


def player_hint() -> str:
    if have_mpv():
        return "mpv"
    if have_browser():
        return "browser"
    return "нет плеера"
