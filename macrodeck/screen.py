# macrodeck/screen.py
"""PC ekranini kucultulmus JPEG olarak yakalar (telefonda izlemek icin).

Hizli yol: DXGI Desktop Duplication (dxcam), 60 fps. Baslamazsa (uzak masaustu, eski surucu)
yavas ama her yerde calisan GDI yakalamaya (Pillow) duser.
"""
from __future__ import annotations

import ctypes
import logging
import threading
from ctypes import wintypes
from io import BytesIO

from PIL import Image, ImageDraw, ImageGrab

logger = logging.getLogger(__name__)

DEFAULT_WIDTH = 1000
MIN_WIDTH, MAX_WIDTH = 640, 1920
QUALITY = 55
TARGET_FPS = 60

_user32 = ctypes.windll.user32
_ENUM_PROC = ctypes.WINFUNCTYPE(
    wintypes.BOOL, wintypes.HANDLE, wintypes.HDC, ctypes.POINTER(wintypes.RECT), wintypes.LPARAM
)


class _MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]


def _cursor_pos() -> tuple[int, int]:
    pt = wintypes.POINT()
    _user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y


def monitors() -> list[tuple[int, int, int, int]]:
    """(sol, ust, sag, alt) listesi; ana monitor her zaman 0. indekste."""
    rects: list[tuple[int, int, int, int]] = []

    def _cb(_h, _dc, rect, _lp):
        r = rect.contents
        rects.append((r.left, r.top, r.right, r.bottom))
        return True

    _user32.EnumDisplayMonitors(None, None, _ENUM_PROC(_cb), 0)
    # ana monitorun sol-ust kosesi (0, 0)'dir
    rects.sort(key=lambda r: ((r[0], r[1]) != (0, 0), r[0], r[1]))
    return rects


def monitor_at(rects: list[tuple[int, int, int, int]], x: int, y: int) -> int | None:
    """(x, y) noktasini iceren monitorun indeksi; hicbirinde degilse None."""
    for i, (left, top, right, bottom) in enumerate(rects):
        if left <= x < right and top <= y < bottom:
            return i
    return None


# --- DXGI yakalama ------------------------------------------------------------------------------

_lock = threading.Lock()
_cams: dict[int, tuple[int, object]] = {}  # monitor indeksi -> (dxcam cikis no, calisan kamera)
_dx_broken = False  # bir kez basarisiz olduysa tekrar deneme, GDI'ya dus
_streams = 0  # acik ekran akisi sayisi; 0 olunca kameralar kapanir


def _output_rect(cam) -> tuple[int, int, int, int]:
    info = _MONITORINFO(cbSize=ctypes.sizeof(_MONITORINFO))
    _user32.GetMonitorInfoW(cam._output.hmonitor, ctypes.byref(info))
    r = info.rcMonitor
    return r.left, r.top, r.right, r.bottom


def _camera(monitor: int, rect: tuple[int, int, int, int]):
    """Verilen monitorun dxcam kamerasini dondurur (yoksa baslatir); basarisizsa None."""
    global _dx_broken
    with _lock:
        if monitor in _cams:
            return _cams[monitor][1]
        if _dx_broken:
            return None
        try:
            import dxcam

            taken = {idx for idx, _ in _cams.values()}
            for idx in range(8):
                if idx in taken:  # dxcam ayni cikis icin calisan kamerayi dondurur; release etme
                    continue
                # shortcut: yalnizca ilk ekran karti; dxcam cikis sirasi bizimkinden farkli, rect ile eslestir
                cam = dxcam.create(device_idx=0, output_idx=idx, output_color="BGRA", processor_backend="numpy")
                if cam is None:
                    break
                if _output_rect(cam) == rect:
                    cam.start(target_fps=TARGET_FPS, video_mode=True)
                    _cams[monitor] = (idx, cam)
                    return cam
                cam.release()
        except Exception as e:
            logger.warning("dxgi yakalama baslamadi, GDI'ya dusuluyor: %s", e)
        _dx_broken = True
        return None


def stream_open() -> None:
    global _streams
    with _lock:
        _streams += 1


def stream_close() -> None:
    """Son akis kapaninca GPU kopyalamayi durdur."""
    global _streams
    with _lock:
        _streams = max(0, _streams - 1)
        if _streams:
            return
        cams = [cam for _, cam in _cams.values()]
        _cams.clear()
    for cam in cams:
        try:
            cam.stop()
            cam.release()
        except Exception as e:
            logger.debug("kamera kapatilamadi: %s", e)


def _grab_dx(monitor: int, rect) -> Image.Image | None:
    cam = _camera(monitor, rect)
    if cam is None:
        return None
    frame = cam.get_latest_frame()  # video_mode: ekran durgunken de son kareyi verir
    if frame is None:
        return None
    h, w = frame.shape[:2]
    return Image.frombuffer("RGB", (w, h), frame, "raw", "BGRX", 0, 1)


def _grab_gdi(rect) -> Image.Image:
    # Pillow Windows'ta tum sanal ekrani alip kirpar; bbox sanal ekran kosesine goredir
    vx, vy = _user32.GetSystemMetrics(76), _user32.GetSystemMetrics(77)
    left, top, right, bottom = rect
    return ImageGrab.grab(all_screens=True).crop((left - vx, top - vy, right - vx, bottom - vy)).convert("RGB")


def grab_jpeg(monitor: int = 0, width: int = DEFAULT_WIDTH) -> bytes:
    rects = monitors()
    if not 0 <= monitor < len(rects):
        monitor = 0
    rect = rects[monitor]
    left, top, right, bottom = rect
    try:
        img = _grab_dx(monitor, rect)
    except Exception as e:
        logger.debug("dxgi kare alinamadi: %s", e)
        img = None
    if img is None:
        img = _grab_gdi(rect)
    full_w = img.width
    # tamsayi katiyla kucult (reduce hizli; serbest resize 1080p'de ~10 ms, 60 fps'i oldurur)
    factor = max(1, round(full_w / max(MIN_WIDTH, min(MAX_WIDTH, width))))
    if factor > 1:
        img = img.reduce(factor)
    k = img.width / full_w
    cx, cy = _cursor_pos()
    if left <= cx < right and top <= cy < bottom:
        x, y = (cx - left) * k, (cy - top) * k
        # yakalama imleci icermiyor; trackpad icin gorunmesi sart, elle ok ciz
        ImageDraw.Draw(img).polygon(
            [(x, y), (x, y + 18), (x + 5, y + 13), (x + 11, y + 13)], fill="white", outline="black"
        )
    buf = BytesIO()
    img.save(buf, "JPEG", quality=QUALITY)
    return buf.getvalue()
