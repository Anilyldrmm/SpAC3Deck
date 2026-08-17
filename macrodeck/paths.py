from __future__ import annotations

import os
import sys
from pathlib import Path


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def app_data_dir() -> Path:
    """config/token/cache dosyalarinin yazildigi kalici dizin.

    Paketlenmis (PyInstaller) modda %APPDATA%\\MacroDeck\\ kullanilir - Program
    Files gibi salt-okunur bir konuma kurulsa bile yazma sorunu olmaz. Gelistirme
    modunda repo kokundeki config/ klasoru kullanilir (mevcut davranis, ornek
    config dahil, git'e commitli).
    """
    if is_frozen():
        base = Path(os.environ.get("APPDATA", str(Path.home())))
        data_dir = base / "MacroDeck"
        data_dir.mkdir(parents=True, exist_ok=True)
        return data_dir
    return Path("config")


def web_root() -> Path:
    """web/ statik dosyalarinin (configurator + deck HTML/CSS/JS) koku."""
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS")) / "web"
    return Path(__file__).resolve().parent.parent / "web"
