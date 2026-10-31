# macrodeck/screen.py
"""PC ekranini kucultulmus JPEG olarak yakalar (telefonda izlemek icin)."""
from __future__ import annotations

import ctypes
from ctypes import wintypes
from io import BytesIO

from PIL import ImageDraw, ImageGrab

MAX_WIDTH = 1000
QUALITY = 55


def _cursor_pos() -> tuple[int, int]:
    pt = wintypes.POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y


def grab_jpeg() -> bytes:
    # shortcut: sadece ana monitor, ikinci monitor gerekirse all_screens=True + imlec ofseti
    img = ImageGrab.grab().convert("RGB")
    full_w = img.width
    cx, cy = _cursor_pos()
    if img.width > MAX_WIDTH:
        img = img.resize((MAX_WIDTH, round(img.height * MAX_WIDTH / img.width)))
    k = img.width / full_w
    x, y = cx * k, cy * k
    # yakalama imleci icermiyor; trackpad icin gorunmesi sart, elle ok ciz
    ImageDraw.Draw(img).polygon(
        [(x, y), (x, y + 18), (x + 5, y + 13), (x + 11, y + 13)], fill="white", outline="black"
    )
    buf = BytesIO()
    img.save(buf, "JPEG", quality=QUALITY)
    return buf.getvalue()
