from __future__ import annotations

import secrets
from pathlib import Path


def generate_pin() -> str:
    return f"{secrets.randbelow(10000):04d}"


def load_or_create_pin(path: Path) -> str:
    """PIN'i kalici tutar - her baslatmada rastgele degismesin diye.

    Telefon PIN'i localStorage'da sakliyor (bir kere gir, hatirla); PIN her
    baslatmada degisirse bu hatirlama isliyor gorunmez, kullanici tekrar tekrar
    PIN girmek zorunda kalir.
    """
    if path.exists():
        pin = path.read_text(encoding="utf-8").strip()
        if pin:
            return pin
    pin = generate_pin()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(pin, encoding="utf-8")
    return pin


def compute_diff(old_state: dict, new_state: dict) -> dict:
    return {
        key: value
        for key, value in new_state.items()
        if key not in old_state or old_state[key] != value
    }
