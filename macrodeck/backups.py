from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

MAX_BACKUPS = 10


def backups_dir(config_path: Path) -> Path:
    return config_path.parent / "backups"


def create_backup(config_path: Path) -> None:
    """save_config'den ONCE cagirilir - mevcut dosyanin bir kopyasini atar."""
    if not config_path.exists():
        return
    backup_dir = backups_dir(config_path)
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    backup_path = backup_dir / f"deck_{timestamp}.json"
    shutil.copy2(config_path, backup_path)
    _prune_old_backups(backup_dir)


def _prune_old_backups(backup_dir: Path) -> None:
    backups = sorted(backup_dir.glob("deck_*.json"))
    excess = len(backups) - MAX_BACKUPS
    if excess <= 0:
        return
    for old in backups[:excess]:
        old.unlink(missing_ok=True)


def list_backups(config_path: Path) -> list[dict]:
    backup_dir = backups_dir(config_path)
    if not backup_dir.is_dir():
        return []
    backups = sorted(backup_dir.glob("deck_*.json"), reverse=True)
    return [{"filename": p.name, "modified": p.stat().st_mtime} for p in backups]


def restore_backup(config_path: Path, filename: str) -> bool:
    """Verilen backup dosyasini mevcut config olarak geri yukler.

    filename sadece basename olarak kullanilir (path traversal korumasi).
    Geri yuklemeden once mevcut hali de yedeklenir - geri yukleme de geri alinabilir.
    """
    backup_dir = backups_dir(config_path)
    source = backup_dir / Path(filename).name
    if not source.is_file():
        return False
    create_backup(config_path)
    shutil.copy2(source, config_path)
    return True
