# macrodeck/tray.py
from __future__ import annotations

import threading

import pystray
from PIL import Image, ImageDraw


def _make_icon_image():
    image = Image.new("RGB", (64, 64), "black")
    draw = ImageDraw.Draw(image)
    draw.rectangle((16, 16, 48, 48), fill="white")
    return image


def start_tray(on_open_configurator, on_quit) -> None:
    icon = pystray.Icon(
        "macrodeck",
        _make_icon_image(),
        "MacroDeck",
        menu=pystray.Menu(
            pystray.MenuItem("Configurator Aç", lambda: on_open_configurator()),
            pystray.MenuItem("Çıkış", lambda: on_quit(icon)),
        ),
    )
    threading.Thread(target=icon.run, daemon=True).start()
