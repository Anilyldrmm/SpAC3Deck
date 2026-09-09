# macrodeck/osd.py
"""Ekran ustu ses gostergesi (OSD).

Voicemeeter gain/mute degisince ekranin uzerinde kisa sureli bir kart
gosterir. Kart odak calmaz: pencereye WS_EX_NOACTIVATE + WS_EX_TOOLWINDOW +
WS_EX_TRANSPARENT ex-style'lari verilir - boylece hicbir zaman aktif pencere
olmaz (oyun minimize olmaz), alt-tab listesinde gorunmez ve fare olaylarini
altindaki pencereye gecirir.

Tkinter arayuzu kendi thread'inde kurulur ve sadece o thread'den elleniyor;
disaridan gelen istekler `queue` uzerinden aktarilir (tkinter thread-safe
degil). `surface_factory` enjekte edilebilir, testler gercek pencere acmadan
mantigi dogrular.
"""
from __future__ import annotations

import logging
import queue
import threading
import time
from dataclasses import dataclass
from typing import Callable, Protocol

logger = logging.getLogger(__name__)

CARD_WIDTH = 300
CARD_HEIGHT = 78
SCREEN_MARGIN = 56  # varsayilan konumda alt kenardan bosluk
GAIN_MIN_DB = -60.0
GAIN_MAX_DB = 12.0
HIDE_AFTER_SECONDS = 1.4
TICK_SECONDS = 0.04
IDLE_TICK_SECONDS = 0.12  # kart gizliyken dongu daha seyrek uyanir
# configurator penceresi yerlestirme modunda kapatilirsa kart ekranda fare
# olayi alan halde kalmasin diye guvenlik agi
PLACEMENT_TIMEOUT_SECONDS = 180.0
CONFIG_CACHE_SECONDS = 0.25
MONITOR_CACHE_SECONDS = 5.0
QUEUE_MAX_ITEMS = 32
MAX_CONSECUTIVE_TICK_ERRORS = 5

# renkler configurator'un paletinden (web/configure/style.css) - OSD masaustu
# uygulamasinin bir parcasi, deck'in (telefon) yesil temasi degil
COLOR_CARD = "#1e1f24"
COLOR_BORDER = "#2a2b31"
COLOR_TEXT = "#e6e6e6"
COLOR_TEXT_DIM = "#999999"
COLOR_TRACK = "#26272e"
COLOR_FILL = "#6266ff"
COLOR_MUTED = "#ee6666"
COLOR_MUTED_FILL = "#553a42"  # susturuldu: cubuk sonuk kalsin, "acik" gibi durmasin
COLOR_TRANSPARENT_KEY = "#ff00ff"  # -transparentcolor ile kirpilan kose rengi

_GWL_EXSTYLE = -20
_GA_ROOT = 2
_WS_EX_TRANSPARENT = 0x00000020
_WS_EX_TOOLWINDOW = 0x00000080
_WS_EX_NOACTIVATE = 0x08000000
_PASSIVE_EX_STYLES = _WS_EX_NOACTIVATE | _WS_EX_TOOLWINDOW | _WS_EX_TRANSPARENT
_SWP_FLAGS = 0x0001 | 0x0002 | 0x0004 | 0x0010 | 0x0020  # NOSIZE|NOMOVE|NOZORDER|NOACTIVATE|FRAMECHANGED


@dataclass
class OsdFrame:
    """OSD'nin o an cizecegi icerik."""

    label: str
    gain_db: float
    muted: bool
    fraction: float
    placement: bool = False


class OsdSurface(Protocol):
    """Cizim yuzeyi (gercek uygulamasi tkinter, testlerde fake)."""

    def render(self, frame: OsdFrame) -> None: ...
    def move(self, x: int, y: int) -> None: ...
    def set_visible(self, visible: bool) -> None: ...
    def set_interactive(self, interactive: bool) -> None: ...
    def pump(self) -> None: ...
    def destroy(self) -> None: ...


def gain_fraction(gain_db: float) -> float:
    """dB degerini 0..1 arasi cubuk dolulugu yapar."""
    span = GAIN_MAX_DB - GAIN_MIN_DB
    fraction = (gain_db - GAIN_MIN_DB) / span
    return min(1.0, max(0.0, fraction))


def format_gain(gain_db: float) -> str:
    return f"{gain_db:+.1f} dB"


def default_position(monitors: list[dict], size: tuple[int, int] = (CARD_WIDTH, CARD_HEIGHT)) -> tuple[int, int]:
    """Ana ekranin alt ortasi (monitor listesi bossa 0,0)."""
    width, height = size
    primary = next((m for m in monitors if m.get("primary")), None)
    if primary is None:
        primary = monitors[0] if monitors else None
    if primary is None:
        return 0, 0
    left, top, right, bottom = primary["rect"]
    return left + (right - left - width) // 2, bottom - height - SCREEN_MARGIN


def resolve_position(
    x: int | None,
    y: int | None,
    monitors: list[dict],
    size: tuple[int, int] = (CARD_WIDTH, CARD_HEIGHT),
) -> tuple[int, int]:
    """Kayitli konumu dogrular; ekran degistiyse/yoksa varsayilana doner.

    Cok monitorlu kurulumda konum sanal ekran koordinatidir (yan monitorde x
    negatif olabilir), bu yuzden monitor secimi ayri bir alan olarak tutulmuyor.
    Kart tamamen ekranlarin disinda kalmissa (monitor cikarildi, cozunurluk
    degisti) gorunmez bir yerde kalmasin diye varsayilan konuma dusuyoruz.
    """
    if x is None or y is None:
        return default_position(monitors, size)
    width, height = size
    for monitor in monitors:
        left, top, right, bottom = monitor["rect"]
        # kartin en az bir bolumu bu ekranin icinde mi
        if x + width > left and x < right and y + height > top and y < bottom:
            return x, y
    return default_position(monitors, size)


def list_monitor_rects() -> list[dict]:
    """Bagli ekranlari {rect, primary} olarak dondurur, alinamazsa bos liste."""
    try:
        import win32api
    except ImportError:
        logger.warning("win32api bulunamadi, OSD ekran bilgisi alinamiyor")
        return []
    try:
        rects = []
        for entry in win32api.EnumDisplayMonitors():
            info = win32api.GetMonitorInfo(entry[0])
            rects.append(
                {
                    "rect": tuple(info.get("Monitor", (0, 0, 0, 0))),
                    "primary": bool(info.get("Flags", 0) & 1),
                }
            )
        return rects
    except Exception as exc:
        logger.warning("ekran bilgisi alinamadi: %s", exc)
        return []


class VolumeOsd:
    """Ses gostergesinin yasam dongusu ve durum makinesi.

    `show()` her tus basisinda cagrilir (baska thread'den), kart gorunur olur
    ve son gosterimden HIDE_AFTER_SECONDS sonra kendini gizler. Yerlestirme
    modunda (`set_placement(True)`) kart kalici gorunur ve fare olaylarini
    alir, boylece surukle-birak ile konumlandirilabilir.
    """

    def __init__(
        self,
        get_config: Callable[[], object],
        surface_factory: Callable[[Callable[[int, int], None]], OsdSurface] | None = None,
        monitor_lister: Callable[[], list[dict]] = list_monitor_rects,
        clock: Callable[[], float] = time.monotonic,
    ):
        self._get_config = get_config
        self._surface_factory = surface_factory or _create_tk_surface
        self._monitor_lister = monitor_lister
        self._clock = clock
        self._queue: queue.Queue = queue.Queue(maxsize=QUEUE_MAX_ITEMS)
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.RLock()
        self._position: tuple[int, int] | None = None
        self._surface: OsdSurface | None = None
        self._failed = False
        self._visible = False
        self._placement = False
        self._placement_started_at = 0.0
        self._last_shown_at = 0.0
        self._cached_media_keys = None
        self._media_keys_read_at = 0.0
        self._cached_monitors: list[dict] | None = None
        self._monitors_read_at = 0.0

    # --- disaridan cagrilan (thread-safe) arayuz ---

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name="macrodeck-osd", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        thread, self._thread = self._thread, None
        if thread is not None:
            thread.join(timeout=2.0)

    def is_running(self) -> bool:
        """Gosterge gercekten kullanilabilir mi.

        `create_volume_osd` tkinter kurulamasa bile bir nesne dondurur (uygulama
        bu yuzden acilmasin diye); o durumda thread hemen olur. Placement
        endpoint'i bunu kontrol edip anlamli hata dondurur, yoksa configurator
        ekranda olmayan bir karti konumlandirdigini sanir."""
        thread = self._thread
        return bool(
            thread is not None
            and thread.is_alive()
            and not self._failed
            and self._surface is not None
        )

    def show(self, label: str, gain_db: float, muted: bool) -> None:
        """Karti gosterir; config'de kapatilmissa sessizce hicbir sey yapmaz."""
        if not self._osd_enabled():
            return
        frame = OsdFrame(
            label=label,
            gain_db=gain_db,
            muted=muted,
            fraction=gain_fraction(gain_db),
        )
        try:
            self._queue.put_nowait(("frame", frame))
        except queue.Full:
            # OSD thread'i yetismiyor ya da olmus: kuyruk sinirsiz buyumesin
            logger.debug("OSD kuyrugu dolu, kare atlandi")

    def set_placement(self, active: bool) -> tuple[int, int]:
        """Yerlestirme modunu acar/kapatir ve guncel konumu dondurur.

        Kapatilirken donen (x, y) configurator tarafindan config'e yazilir -
        OSD kendisi config dosyasina yazmaz (tek dogruluk kaynagi config).
        Konum kuyruga yazmadan ONCE okunur: OSD thread'i araya girerse
        surukleyerek secilen konumu kaybetmeyelim.
        """
        active = bool(active)
        position = self.position
        if active or position is None:
            position = resolve_position(*self._config_position(), self._monitors())
            with self._lock:
                self._position = position
        try:
            self._queue.put_nowait(("placement", active))
        except queue.Full:
            logger.warning("OSD kuyrugu dolu, yerlestirme modu degistirilemedi")
        return position

    @property
    def position(self) -> tuple[int, int] | None:
        with self._lock:
            return self._position

    # --- OSD thread'i ---

    def open(self) -> None:
        """Cizim yuzeyini olusturur. `_run` bunu OSD thread'inde cagirir;
        testler thread acmadan dogrudan cagirabilir."""
        if self._surface is None:
            self._surface = self._surface_factory(self._on_drag_end)

    def close(self) -> None:
        surface, self._surface = self._surface, None
        if surface is None:
            return
        try:
            surface.destroy()
        except Exception as exc:
            logger.debug("OSD penceresi kapatilamadi: %s", exc)

    def _run(self) -> None:
        try:
            self.open()
        except Exception as exc:
            logger.warning("OSD penceresi olusturulamadi, gosterge devre disi: %s", exc)
            self._failed = True
            return
        errors = 0
        while not self._stop_event.is_set():
            # try dongunun ICINDE: gecici bir Tk hatasi (ekran modu degisimi,
            # RDP oturumu) gostergeyi oturum sonuna kadar oldurmesin
            try:
                self.tick()
                errors = 0
            except Exception as exc:
                errors += 1
                logger.warning(
                    "OSD dongusu hata verdi (%d/%d): %s", errors, MAX_CONSECUTIVE_TICK_ERRORS, exc
                )
                if errors >= MAX_CONSECUTIVE_TICK_ERRORS:
                    logger.warning("OSD ust uste hata verdi, gosterge kapatiliyor")
                    self._failed = True
                    break
            time.sleep(TICK_SECONDS if (self._visible or self._placement) else IDLE_TICK_SECONDS)
        self.close()

    def tick(self) -> None:
        """Dongunun tek adimi: kuyrugu bosalt, otomatik gizle, pencereyi surur."""
        surface = self._surface
        if surface is None:
            return
        while True:
            try:
                kind, payload = self._queue.get_nowait()
            except queue.Empty:
                break
            if kind == "frame":
                self._handle_frame(surface, payload)
            elif kind == "placement":
                self._handle_placement(surface, payload)
        if self._placement:
            if self._clock() - self._placement_started_at >= PLACEMENT_TIMEOUT_SECONDS:
                logger.info("yerlestirme modu zaman asimina ugradi, kapatiliyor")
                self._handle_placement(surface, False)
        elif self._visible and self._clock() - self._last_shown_at >= HIDE_AFTER_SECONDS:
            self._visible = False
            surface.set_visible(False)
        surface.pump()

    def _handle_frame(self, surface: OsdSurface, frame: OsdFrame) -> None:
        if self._placement:
            # yerlestirme modunda surukleme ipucu ekranda kalmali; ses
            # degistirmek karti normal gorunume dondurmesin
            return
        self._last_shown_at = self._clock()
        self._apply_position(surface)
        surface.render(frame)
        if not self._visible:
            self._visible = True
            surface.set_visible(True)

    def _handle_placement(self, surface: OsdSurface, active: bool) -> None:
        if active and not self._osd_enabled():
            logger.info("ses gostergesi kapali, yerlestirme modu acilmadi")
            return
        self._placement = active
        if active:
            self._placement_started_at = self._clock()
            self._apply_position(surface)
            surface.set_interactive(True)
            surface.render(_placement_preview())
            self._visible = True
            surface.set_visible(True)
            return
        # Cikista konum YENIDEN HESAPLANMAZ: surukleyerek secilen deger
        # config'e yazilana kadar bellekte kalmali
        self._visible = False
        surface.set_visible(False)
        surface.set_interactive(False)

    def _apply_position(self, surface: OsdSurface) -> None:
        """Karti config'deki konuma tasir (gecersizse varsayilana duser)."""
        position = resolve_position(*self._config_position(), self._monitors())
        with self._lock:
            self._position = position
        surface.move(*position)

    def _on_drag_end(self, x: int, y: int) -> None:
        """Surface'in surukleme bitince cagirdigi callback."""
        with self._lock:
            self._position = (int(x), int(y))

    # --- config yardimcilari ---

    def _media_keys(self):
        """Config'i kisa sureli onbellekle okur.

        Bir tus basisinda config birden fazla kez gerekiyor (gosterge acik mi,
        konum nerede) ve knob saniyede onlarca event uretebiliyor - her
        seferinde deck.json'i parse etmek gereksiz. Okuma basarisiz olursa
        (configurator dosyayi yeniden yazarken) son bilinen deger kullanilir,
        boylece kart yanlislikla varsayilan konuma sicramaz."""
        with self._lock:
            now = self._clock()
            fresh = now - self._media_keys_read_at < CONFIG_CACHE_SECONDS
            if self._cached_media_keys is not None and fresh:
                return self._cached_media_keys
            try:
                media_keys = self._get_config().media_keys
            except Exception as exc:
                logger.debug("OSD config okunamadi: %s", exc)
                return self._cached_media_keys
            self._cached_media_keys = media_keys
            self._media_keys_read_at = now
            return media_keys

    def _monitors(self) -> list[dict]:
        """Ekran listesini onbellekle dondurur (her karede EnumDisplayMonitors
        cagirmaya gerek yok; monitor takilip cikarilmasi seyrek olay)."""
        with self._lock:
            now = self._clock()
            monitors_fresh = now - self._monitors_read_at < MONITOR_CACHE_SECONDS
            if self._cached_monitors is not None and monitors_fresh:
                return self._cached_monitors
            self._cached_monitors = self._monitor_lister()
            self._monitors_read_at = now
            return self._cached_monitors

    def _osd_enabled(self) -> bool:
        media_keys = self._media_keys()
        return bool(media_keys is not None and getattr(media_keys, "osd_enabled", False))

    def _config_position(self) -> tuple[int | None, int | None]:
        media_keys = self._media_keys()
        if media_keys is None:
            return None, None
        return getattr(media_keys, "osd_x", None), getattr(media_keys, "osd_y", None)


def _placement_preview() -> OsdFrame:
    return OsdFrame(
        label="Konumu sürükleyip bırak",
        gain_db=-12.0,
        muted=False,
        fraction=gain_fraction(-12.0),
        placement=True,
    )


# --- tkinter uygulamasi ---

def passive_ex_style(current: int) -> int:
    """Pasif (normal) haldeki ex-style: odak calmaz, alt-tab'da yok, tiklama gecirir."""
    return current | _PASSIVE_EX_STYLES


def interactive_ex_style(current: int) -> int:
    """Yerlestirme modundaki ex-style: fare olayi alir ama alt-tab'da yine gorunmez."""
    return (current & ~(_WS_EX_NOACTIVATE | _WS_EX_TRANSPARENT)) | _WS_EX_TOOLWINDOW


def _current_foreground():
    """O anki on plan penceresinin handle'i (alinamazsa None)."""
    try:
        import win32gui

        return win32gui.GetForegroundWindow()
    except Exception as exc:
        logger.debug("on plan penceresi okunamadi: %s", exc)
        return None


def _restore_foreground(hwnd) -> None:
    """OSD penceresi olusurken odagi kaptiysa eski pencereye geri verir."""
    if not hwnd:
        return
    try:
        import win32gui

        if win32gui.GetForegroundWindow() == hwnd:
            return
        win32gui.SetForegroundWindow(hwnd)
    except Exception as exc:
        # SetForegroundWindow Windows kisitlamalari yuzunden reddedilebilir;
        # OSD'nin acilisi bunun icin durmasin
        logger.debug("on plan penceresi geri verilemedi: %s", exc)


def _rounded_rect(canvas, x1: int, y1: int, x2: int, y2: int, radius: int, **kwargs):
    """Canvas'ta yuvarlak koseli dikdortgen (tkinter'da hazir yok)."""
    points = [
        x1 + radius, y1,
        x2 - radius, y1,
        x2, y1,
        x2, y1 + radius,
        x2, y2 - radius,
        x2, y2,
        x2 - radius, y2,
        x1 + radius, y2,
        x1, y2,
        x1, y2 - radius,
        x1, y1 + radius,
        x1, y1,
    ]
    return canvas.create_polygon(points, smooth=True, **kwargs)


class TkOsdSurface:
    """Tkinter tabanli OSD penceresi. Sadece OSD thread'inden kullanilmali."""

    def __init__(self, on_drag_end: Callable[[int, int], None] | None = None):
        import tkinter as tk

        self._tk = tk
        self._on_drag_end = on_drag_end
        self._drag_origin: tuple[int, int] | None = None
        self._interactive = False
        self._foreground_before_interactive = None

        # Tk penceresi olusurken bir an on plana gelip odagi kapabiliyor
        # (dogrulandi: GetForegroundWindow tk penceresini gosteriyordu).
        # Bu yuzden odagi olcup sonunda geri veriyoruz ve ex-style'lari
        # pencere hic haritalanmadan once yaziyoruz.
        previous_foreground = _current_foreground()

        root = tk.Tk()
        root.withdraw()
        root.overrideredirect(True)
        root.attributes("-topmost", True)
        root.attributes("-alpha", 0.94)
        root.attributes("-transparentcolor", COLOR_TRANSPARENT_KEY)
        root.configure(bg=COLOR_TRANSPARENT_KEY)
        root.geometry(f"{CARD_WIDTH}x{CARD_HEIGHT}+0+0")
        self._root = root
        self._hwnd = self._resolve_hwnd()
        self.set_interactive(False)

        self._canvas = tk.Canvas(
            root,
            width=CARD_WIDTH,
            height=CARD_HEIGHT,
            bg=COLOR_TRANSPARENT_KEY,
            highlightthickness=0,
            bd=0,
        )
        self._canvas.pack(fill="both", expand=True)
        self._canvas.bind("<Button-1>", self._on_press)
        self._canvas.bind("<B1-Motion>", self._on_motion)
        self._canvas.bind("<ButtonRelease-1>", self._on_release)

        root.update_idletasks()
        _restore_foreground(previous_foreground)

    # --- OsdSurface arayuzu ---

    def render(self, frame: OsdFrame) -> None:
        canvas = self._canvas
        canvas.delete("all")
        accent = COLOR_MUTED if frame.muted else COLOR_FILL
        _rounded_rect(
            canvas, 1, 1, CARD_WIDTH - 1, CARD_HEIGHT - 1, 16,
            fill=COLOR_CARD,
            outline=accent if frame.placement else COLOR_BORDER,
            width=2 if frame.placement else 1,
        )
        canvas.create_text(
            18, 24, anchor="w", text=frame.label,
            fill=COLOR_TEXT_DIM, font=("Segoe UI", 9),
        )
        value_text = "MUTE" if frame.muted else format_gain(frame.gain_db)
        canvas.create_text(
            CARD_WIDTH - 18, 24, anchor="e", text=value_text,
            fill=accent if frame.muted else COLOR_TEXT,
            font=("Segoe UI Semibold", 12),
        )
        track_left, track_right = 18, CARD_WIDTH - 18
        track_top, track_bottom = 48, 56
        _rounded_rect(
            canvas, track_left, track_top, track_right, track_bottom, 4,
            fill=COLOR_TRACK, outline="",
        )
        fill_width = int((track_right - track_left) * frame.fraction)
        if fill_width >= 8:
            _rounded_rect(
                canvas, track_left, track_top, track_left + fill_width, track_bottom, 4,
                fill=COLOR_MUTED_FILL if frame.muted else accent, outline="",
            )

    def move(self, x: int, y: int) -> None:
        self._root.geometry(f"{CARD_WIDTH}x{CARD_HEIGHT}+{int(x)}+{int(y)}")

    def set_visible(self, visible: bool) -> None:
        if visible:
            self._root.deiconify()
            # baska bir topmost pencere araya girmis olabilir
            self._root.attributes("-topmost", True)
            self._root.lift()
            # Tk bazi wm attributes degisikliklerinde sarmalayici pencereyi
            # yeniden kurar; bu olursa hwnd bayatlar ve ex-style bitleri
            # duser. Her gosterimde ikisini de tazeliyoruz (deger degismediyse
            # SetWindowLong cagrilmaz, yani bedava).
            self._hwnd = self._resolve_hwnd()
            self._apply_ex_styles(self._interactive)
        else:
            self._root.withdraw()

    def set_interactive(self, interactive: bool) -> None:
        """Yerlestirme modunda ex-style'lari kaldirir (fare olayi alsin diye),
        normal modda geri koyar (odak calmaz + tiklama gecirir).

        Yerlestirme modu odak alabildigi icin, moda girerken o anki on plan
        penceresi saklanir ve moddan cikarken geri verilir - kullanici
        yerlestirmeyi bitirdiginde odak oyununa/penceresine donsun."""
        if interactive and not self._interactive:
            self._foreground_before_interactive = _current_foreground()
        self._interactive = interactive
        self._apply_ex_styles(interactive)
        if not interactive and self._foreground_before_interactive is not None:
            _restore_foreground(self._foreground_before_interactive)
            self._foreground_before_interactive = None

    def _apply_ex_styles(self, interactive: bool) -> None:
        if self._hwnd is None:
            return
        try:
            import win32gui

            current = win32gui.GetWindowLong(self._hwnd, _GWL_EXSTYLE)
            updated = interactive_ex_style(current) if interactive else passive_ex_style(current)
            if updated != current:
                win32gui.SetWindowLong(self._hwnd, _GWL_EXSTYLE, updated)
                win32gui.SetWindowPos(self._hwnd, 0, 0, 0, 0, 0, _SWP_FLAGS)
        except Exception as exc:
            logger.warning("OSD pencere stili ayarlanamadi: %s", exc)

    def pump(self) -> None:
        self._root.update()

    def destroy(self) -> None:
        self._root.destroy()

    # --- ic yardimcilar ---

    def _resolve_hwnd(self):
        """Tk'nin ic pencere handle'indan ust seviye (kok) pencereyi bulur.

        GetAncestor(GA_ROOT) dogru olan: GetParent bir popup pencerede
        owner'i dondurebilir ve ex-style'lar yanlis pencereye yazilir."""
        try:
            import win32gui

            hwnd = self._root.winfo_id()
            try:
                root = win32gui.GetAncestor(hwnd, _GA_ROOT)
            except Exception:
                root = win32gui.GetParent(hwnd)
            return root or hwnd
        except Exception as exc:
            logger.warning("OSD pencere handle'i bulunamadi: %s", exc)
            return None

    def _on_press(self, event) -> None:
        self._drag_origin = (event.x, event.y)

    def _on_motion(self, event) -> None:
        if self._drag_origin is None:
            return
        offset_x, offset_y = self._drag_origin
        self.move(event.x_root - offset_x, event.y_root - offset_y)

    def _on_release(self, event) -> None:
        if self._drag_origin is None:
            return
        offset_x, offset_y = self._drag_origin
        self._drag_origin = None
        if self._on_drag_end is not None:
            self._on_drag_end(event.x_root - offset_x, event.y_root - offset_y)


def _create_tk_surface(on_drag_end: Callable[[int, int], None]) -> OsdSurface:
    return TkOsdSurface(on_drag_end=on_drag_end)


def create_volume_osd(get_config: Callable[[], object]) -> VolumeOsd:
    """Tkinter yuzeyi ile hazir bir VolumeOsd kurar ve baslatir."""
    osd = VolumeOsd(get_config)
    osd.start()
    return osd
