from __future__ import annotations

import shutil
import tarfile
import tempfile
import time
from pathlib import Path

from . import config

BACKUP_DIR = config.DATA_HOME / "backups"


def _files_under(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(p for p in root.rglob("*") if p.is_file())


def _walk(root: Path):
    if not root.exists():
        return
    for p in sorted(root.rglob("*")):
        if p.is_dir():
            yield p, None
        else:
            yield p, p.relative_to(root).as_posix()


def create() -> Path | None:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    out = BACKUP_DIR / f"vsearch-backup-{stamp}.tar.gz"
    with tarfile.open(out, "w:gz") as tar:
        for root, arcname in ((config.CONFIG_HOME, "config"), (config.DATA_HOME, "data")):
            for p, rel in _walk(root):
                if rel is None:
                    continue
                if root == config.DATA_HOME and rel.startswith("backups/"):
                    continue
                tar.add(p, arcname=f"{arcname}/{rel}")
    return out


def latest() -> Path | None:
    if not BACKUP_DIR.exists():
        return None
    backups = sorted(BACKUP_DIR.glob("vsearch-backup-*.tar.gz"), reverse=True)
    return backups[0] if backups else None


def restore() -> Path | None:
    backup = latest()
    if backup is None:
        return None
    stash = Path(tempfile.mkdtemp(prefix="vsearch-restore-"))
    safe = stash / backup.name
    shutil.copy2(backup, safe)
    with tarfile.open(safe, "r:gz") as tar:
        tar.extractall(stash)
    for name, dst in (("config", config.CONFIG_HOME), ("data", config.DATA_HOME)):
        src = stash / name
        if not src.exists():
            continue
        if dst.exists():
            shutil.rmtree(dst)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(src, dst)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    shutil.rmtree(stash, ignore_errors=True)
    return backup
