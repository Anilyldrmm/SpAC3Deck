# macrodeck/main.py
from __future__ import annotations

import logging
import os
import socket
import threading
import urllib.error
import urllib.request
from pathlib import Path

import uvicorn
import webview
import win32api
import win32event
import winerror

from . import updater
from .paths import app_data_dir, is_frozen
from .qr import generate_deck_url
from .server import create_app, configure_runtime
from .state import load_or_create_pin
from .tray import start_tray

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

PORT = 8765
CONFIG_PATH = app_data_dir() / "deck.json"
CONFIGURATOR_TITLE = "MacroDeck Configurator"
KEEPALIVE_TITLE = "MacroDeck"
EXIT_GRACE_SECONDS = 5.0
_SINGLE_INSTANCE_MUTEX_NAME = "Global\\MacroDeck_SingleInstance"


def acquire_single_instance_lock(mutex_name: str = _SINGLE_INSTANCE_MUTEX_NAME):
    """Ayni anda tek bir MacroDeck process'i calissin diye isimli mutex tutar.

    Configurator penceresi kapatilsa bile process tray'de arka planda devam
    eder (bilincli tasarim) - kullanici bunu fark etmeyip exe'yi tekrar
    calistirirsa, eski process kapanmadan yeni bir Voicemeeter baglantisi
    (ve bridge/port catismasi) birikmesin diye bu kilit gerekli.

    `mutex_name` testlerin gercek uygulama kilidiyle çakışmadan izole
    calisabilmesi icin parametrik (uretimde varsayilani kullanir).

    Dondurur: (mutex_handle, already_running: bool). mutex_handle process
    boyunca acik tutulmali (referans kaybolursa kilit serbest kalir).
    """
    mutex = win32event.CreateMutex(None, False, mutex_name)
    already_running = win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS
    return mutex, already_running


def _activate_running_instance(pin: str) -> None:
    """Zaten calisan process'e '/api/activate' ile pencereni on plana getir
    sinyali gonderir - kisayoldan/exe'den ikinci kez acilinca Discord gibi
    davranmasi icin (uyari kutusu yok, sessizce mevcut pencereyi gosterir)."""
    url = f"http://127.0.0.1:{PORT}/api/activate?token={pin}"
    try:
        urllib.request.urlopen(urllib.request.Request(url, method="POST"), timeout=3)
    except (urllib.error.URLError, OSError) as exc:
        logger.warning("calisan MacroDeck'e activate sinyali gonderilemedi: %s", exc)


def _get_lan_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    finally:
        s.close()


def _run_server(app):
    # access_log=False: her HTTP/WS istegi icin log satiri basmaz (tray-resident
    # calisirken gereksiz I/O) - bizim kendi logger'larimiz (discord bridge, hata
    # loglari vb.) bundan etkilenmez, ayri logging.basicConfig ile yonetiliyor.
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="warning", access_log=False)


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

    @property
    def quitting_event(self) -> threading.Event:
        return self._quitting

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

            window = self._webview.create_window(
                CONFIGURATOR_TITLE, self._configurator_url, width=1180, height=740, min_size=(960, 600)
            )
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
        """Voicemeeter oturumunu ve medya tusu dinleyicisini kapatir (idempotent)."""
        listener = getattr(self._app.state, "media_key_listener", None)
        if listener is not None:
            listener.stop()
            self._app.state.media_key_listener = None

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

    def check_for_updates(self, icon=None, *_):
        """Tray "Güncellemeleri Kontrol Et": arka plan thread'inde calisir,
        sonucu bir MessageBox ile bildirir (guncelleme bulunup uygulanirsa
        quit tetiklenir, mesaj gostermeye gerek kalmaz - process kapanacak)."""
        def _worker():
            if not is_frozen():
                self._notify("Gelistirme modunda güncelleme kontrolü yapılmaz.")
                return
            info = updater.check_for_update()
            if info is None:
                self._notify("Zaten en güncel sürümdesiniz.")
                return
            if updater.apply_update(info):
                self.quit(icon)
            else:
                self._notify("Güncelleme indirilemedi, daha sonra tekrar deneyin.")

        threading.Thread(target=_worker, daemon=True).start()

    @staticmethod
    def _notify(message: str) -> None:
        try:
            win32api.MessageBox(0, message, "MacroDeck", 0x40)
        except Exception as exc:
            logger.debug("bilgi kutusu gosterilemedi: %s", exc)


def main() -> None:
    _mutex, already_running = acquire_single_instance_lock()
    if already_running:
        # Discord tarzi: uyari kutusu yok, mevcut process'e pencereyi on plana
        # getirmesini soyleyip sessizce cikilir - kisayola tekrar tiklamak da
        # tray ikonuna tiklamak gibi calissin diye.
        logger.info("MacroDeck zaten calisiyor, mevcut pencere on plana getiriliyor")
        pin = load_or_create_pin(app_data_dir() / "pin.txt")
        _activate_running_instance(pin)
        return

    lan_ip = _get_lan_ip()
    pin = load_or_create_pin(app_data_dir() / "pin.txt")
    app = create_app(config_path=CONFIG_PATH, pin=pin, lan_ip=lan_ip, port=PORT)
    configure_runtime(app, voicemeeter_kind="banana")

    server_thread = threading.Thread(target=_run_server, args=(app,), daemon=True)
    server_thread.start()

    deck_url = generate_deck_url(lan_ip, PORT, app.state.pin)
    configurator_url = f"http://localhost:{PORT}/configure?token={app.state.pin}"
    print(f"Deck URL: {deck_url}")
    print(f"Configurator URL: {configurator_url}")
    print(f"Discord bridge token (BetterDiscord plugin ayarlarina yapistir): {app.state.bridge_token}")

    lifecycle = AppLifecycle(app, configurator_url)
    app.state.activate_callback = lifecycle.open_configurator
    start_tray(lifecycle.open_configurator, lifecycle.quit, lifecycle.check_for_updates)

    if is_frozen():
        # gelistirme modunda self-update anlamsiz (kalici bir exe yolu yok) - sadece
        # paketlenmis exe'de calisir. Sessiz/otomatik: yeni surum bulununca indirilir,
        # dogrulanir ve lifecycle.quit() tetiklenir; process kapanınca bat dosyalari
        # degistirip yeniden baslatir.
        threading.Thread(
            target=updater.run_update_loop,
            args=(lifecycle.quitting_event, lifecycle.quit),
            daemon=True,
        ).start()

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
