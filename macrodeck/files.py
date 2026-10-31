# macrodeck/files.py
"""Telefon<->PC dosya aktarimi icin guvenli dosya adi yardimcilari."""
from __future__ import annotations

import re
from pathlib import Path

_BAD_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}


def safe_name(name: str | None) -> str:
    """Yol parcalarini atar, Windows'ta gecersiz karakterleri ve ayrilmis adlari duzeltir."""
    base = re.split(r"[\\/]", name or "")[-1]
    base = _BAD_CHARS.sub("_", base).strip(" .")[:150] or "dosya"
    if base.split(".")[0].upper() in _RESERVED:
        base = "_" + base
    return base


def unique_path(directory: Path, name: str) -> Path:
    """Ayni adli dosya varsa uzerine yazmaz: 'ad (1).uzanti' dener."""
    path = directory / name
    n = 1
    while path.exists():
        path = directory / f"{Path(name).stem} ({n}){Path(name).suffix}"
        n += 1
    return path
