# macrodeck/main.py
from __future__ import annotations

import logging
import os
import socket
import threading
from pathlib import Path

import uvicorn
import webview

from .qr import generate_deck_url
from .server import create_app, configure_runtime
from .tray import start_tray

logger = logging.getLogger(__name__)

PORT = 8765
CONFIG_PATH = Path("config/deck.json")
CONFIGURATOR_TITLE = "MacroDeck Configurator"
KEEPALIVE_TITLE = "MacroDeck"
EXIT_GRACE_SECONDS = 5.0


def _get_lan_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    finally:
        s.close()


def _run_server(app):
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")


class AppLifecycle:
    """Tray + pywebview yasam dongusu.

    `webview.start()` main thread'de **bir kez** calisir ve tum pencereler yok
    edilene kadar doner. Gizli bir "keep-alive" penceresi acik kaldigi icin
    configurator penceresi kapatilinca GUI dongusu (ve dolayisiyla process,
    uvicorn thread'i, tray icon) yasamaya devam eder. Tray'den "Configurator Aç"
    sadece `create_window` cagirir; ikinci bir `webview.start()` cagrilmaz.
    """

    def __init__(
        self,
        app,
        configurator_url: str,
        webview_module=webview,
        exit_grace: float | None = EXIT_GRACE_SECONDS,
        force_exit=os._exit,
    ):
        self._app = app
        self._configurator_url = configurator_url
        self._webview = webview_module
        self._exit_grace = exit_grace
        self._force_exit = force_exit
        self._lock = threading.RLock()
        self._configurator_window = None
        self._quitting = threading.Event()

    @property
    def is_quitting(self) -> bool:
        return self._quitting.is_set()

    def create_keepalive_window(self):
        """GUI dongusunu ayakta tutan gizli pencere (ilk/master pencere olmali)."""
        return self._webview.create_window(
            KEEPALIVE_TITLE,
            html="<html><body></body></html>",
            hidden=True,
            width=1,
            height=1,
        )

    def open_configurator(self, *_):
        """Tray callback'i: sadece pencere olusturur, GUI dongusu baslatmaz."""
        with self._lock:
            if self._quitting.is_set():
                return None
            if self._configurator_window is not None:
                try:
                    self._configurator_window.show()
                except Exception as exc:  # pencere zaten yok edilmis olabilir
                    logger.debug("mevcut configurator penceresi gosterilemedi: %s", exc)
                return self._configurator_window

            window = self._webview.create_window(CONFIGURATOR_TITLE, self._configurator_url)
            self._configurator_window = window
            try:
                window.events.closed += self._on_configurator_closed
            except Exception as exc:
                logger.debug("closed event baglanamadi: %s", exc)
            return window

    def _on_configurator_closed(self, *_):
        with self._lock:
            self._configurator_window = None

    def quit(self, icon=None, *_):
        """Tray "Çıkış": tray'i durdur, voicemeeter oturumunu kapat, pencereleri yok et."""
        if self._quitting.is_set():
            return
        self._quitting.set()

        if icon is not None:
            try:
                icon.stop()
            except Exception as exc:
                logger.debug("tray icon durdurulamadi: %s", exc)

        self.shutdown()
        self._destroy_windows()

        # Temiz cikis: tum pencereler yok olunca webview.start() doner, main()
        # biter ve daemon thread'ler (uvicorn/pystray) ile process kapanir.
        # Herhangi bir backend takilirsa asagidaki watchdog garantiler.
        if self._exit_grace is not None:
            watchdog = threading.Timer(self._exit_grace, lambda: self._force_exit(0))
            watchdog.daemon = True
            watchdog.start()

    def _destroy_windows(self):
        for window in list(getattr(self._webview, "windows", [])):
            try:
                window.destroy()
            except Exception as exc:
                logger.debug("pencere kapatilamadi: %s", exc)
        with self._lock:
            self._configurator_window = None

    def shutdown(self):
        """Voicemeeter oturumunu kapatir (idempotent)."""
        backend = getattr(self._app.state, "voicemeeter_backend", None)
        if backend is None:
            return
        logout = getattr(backend, "logout", None)
        if callable(logout):
            try:
                logout()
            except Exception as exc:
                logger.warning("voicemeeter logout basarisiz: %s", exc)
        self._app.state.voicemeeter_backend = None
        self._app.state.voicemeeter_client = None

    def wait_for_quit(self):
        self._quitting.wait()


def main() -> None:
    lan_ip = _get_lan_ip()
    app = create_app(config_path=CONFIG_PATH, lan_ip=lan_ip, port=PORT)
    configure_runtime(app, voicemeeter_kind="banana")

    server_thread = threading.Thread(target=_run_server, args=(app,), daemon=True)
    server_thread.start()

    deck_url = generate_deck_url(lan_ip, PORT, app.state.pin)
    configurator_url = f"http://localhost:{PORT}/configure?token={app.state.pin}"
    print(f"Deck URL: {deck_url}")
    print(f"Configurator URL: {configurator_url}")

    lifecycle = AppLifecycle(app, configurator_url)
    start_tray(lifecycle.open_configurator, lifecycle.quit)

    lifecycle.create_keepalive_window()
    lifecycle.open_configurator()
    webview.start()  # tek GUI dongusu, main thread

    if not lifecycle.is_quitting:
        # Beklenmedik durum: GUI dongusu cikis istenmeden bitti. Sunucuyu
        # oldurmek yerine tray'den cikis gelene kadar main thread'i canli tut.
        logger.warning("GUI dongusu beklenmedik sekilde sonlandi; sunucu calismaya devam ediyor")
        lifecycle.wait_for_quit()

    lifecycle.shutdown()


if __name__ == "__main__":
    main()
