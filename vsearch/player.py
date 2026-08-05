from __future__ import annotations

import shutil
import subprocess

LOG = "/tmp/vsearch-player.log"


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


def play(urls, audio_only: bool = False, fullscreen: bool = True):
    urls = [u for u in urls if u]
    if not urls:
        return None
    if have_mpv():
        cmd = ["mpv"]
        if fullscreen:
            cmd += ["--fullscreen", "--force-window"]
        if audio_only:
            cmd.append("--no-video")
        cmd += urls
        return _spawn(cmd)
    if len(urls) == 1 and open_browser(urls[0]):
        return "browser"
    return None


def player_hint() -> str:
    if have_mpv():
        return "mpv"
    if have_browser():
        return "browser"
    return "нет плеера"