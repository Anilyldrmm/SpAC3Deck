# macrodeck/tray.py
from __future__ import annotations

import threading

import pystray
from PIL import Image, ImageDraw


def _make_icon_image():
    # uygulama logosu: yesil kare + 2x2 beyaz izgara (iOS/configurator ile ayni)
    image = Image.new("RGB", (64, 64), (60, 154, 68))
    draw = ImageDraw.Draw(image)
    for x in (16, 35):
        for y in (16, 35):
            draw.rounded_rectangle((x, y, x + 13, y + 13), radius=3, fill="white")
    return image


def start_tray(on_open_configurator, on_quit, on_check_updates) -> pystray.Icon:
    """Tray icon'u kendi thread'inde baslatir ve icon nesnesini doner.

    `on_open_configurator` sadece pencere olusturmali; GUI dongusu (webview.start)
    main thread'de bir kez calisir. `on_quit(icon)` tum kapatma islerinden sorumlu.
    `on_check_updates()` manuel guncelleme kontrolunu tetikler.

    "Configurator Aç" `default=True` ile isaretli: pystray'in Windows backend'i
    tray ikonuna sol tiklandiginda (sag tikla acilan menu degil) varsayilan
    ogeyi calistirir - boylece ikona tiklamak da Configurator'u acar.
    """
    icon = pystray.Icon(
        "macrodeck",
        _make_icon_image(),
        "MacroDeck",
        menu=pystray.Menu(
            pystray.MenuItem("Configurator Aç", lambda: on_open_configurator(), default=True),
            pystray.MenuItem("Güncellemeleri Kontrol Et", lambda: on_check_updates()),
            pystray.MenuItem("Çıkış", lambda: on_quit(icon)),
        ),
    )
    threading.Thread(target=icon.run, daemon=True).start()
    return icon
