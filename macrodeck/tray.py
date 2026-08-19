# macrodeck/tray.py
from __future__ import annotations

import threading

import pystray
from PIL import Image, ImageDraw


def _make_icon_image():
    image = Image.new("RGB", (64, 64), "black")
    draw = ImageDraw.Draw(image)
    # basit "S" harfi: ust, orta, alt yatay cubuklari birbirine baglayan
    # kivrimli zigzag - tek dikdortgen tek cubuk gibi gorunup "I" ile
    # karisiyordu (kullanici raporu), bu S'nin karakteristik siluetini korur.
    draw.rectangle((14, 12, 50, 22), fill="white")   # ust yatay
    draw.rectangle((14, 12, 24, 32), fill="white")   # sol-ust dikey bacak
    draw.rectangle((14, 27, 50, 37), fill="white")   # orta yatay
    draw.rectangle((40, 32, 50, 52), fill="white")   # sag-alt dikey bacak
    draw.rectangle((14, 42, 50, 52), fill="white")   # alt yatay
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
