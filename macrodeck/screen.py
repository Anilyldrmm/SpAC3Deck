# macrodeck/screen.py
"""PC ekranini kucultulmus JPEG olarak yakalar (telefonda izlemek icin)."""
from __future__ import annotations

import ctypes
from ctypes import wintypes
from io import BytesIO

from PIL import ImageDraw, ImageGrab

DEFAULT_WIDTH = 1000
MIN_WIDTH, MAX_WIDTH = 640, 1920
QUALITY = 55

_user32 = ctypes.windll.user32
_ENUM_PROC = ctypes.WINFUNCTYPE(
    wintypes.BOOL, wintypes.HANDLE, wintypes.HDC, ctypes.POINTER(wintypes.RECT), wintypes.LPARAM
)


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


def grab_jpeg(monitor: int = 0, width: int = DEFAULT_WIDTH) -> bytes:
    rects = monitors()
    left, top, right, bottom = rects[monitor] if 0 <= monitor < len(rects) else rects[0]
    # Pillow Windows'ta tum sanal ekrani alip kirpar; bbox sanal ekran kosesine goredir
    vx, vy = _user32.GetSystemMetrics(76), _user32.GetSystemMetrics(77)
    img = ImageGrab.grab(all_screens=True).crop((left - vx, top - vy, right - vx, bottom - vy)).convert("RGB")
    full_w = img.width
    width = max(MIN_WIDTH, min(MAX_WIDTH, width))
    if img.width > width:
        img = img.resize((width, round(img.height * width / img.width)))
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
