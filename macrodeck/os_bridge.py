# macrodeck/os_bridge.py
from __future__ import annotations

import os
import subprocess
import winsound
from pathlib import Path

import keyboard

from .paths import app_data_dir
from .sources import find_browser_path

SOUNDS_DIR = app_data_dir() / "sounds"


def send_hotkey(keys: list[str]) -> None:
    keyboard.send("+".join(keys))


def hold_key(keys: list[str]) -> None:
    for key in keys:
        keyboard.press(key)


def release_key(keys: list[str]) -> None:
    for key in reversed(keys):
        keyboard.release(key)


def launch_uri(uri: str) -> None:
    uri = uri.strip().strip('"')
    os.startfile(uri)


def open_url(url: str, browser: str = "default") -> None:
    browser_path = find_browser_path(browser)
    if browser_path is None:
        os.startfile(url)  # varsayilan tarayici, ya da secilen tarayici bulunamadi
        return
    subprocess.Popen([browser_path, url])


def play_sound(filename: str) -> None:
    # Path(filename).name path traversal parcalarini (.. vb) atar
    path = SOUNDS_DIR / Path(filename).name
    if not path.is_file():
        return
    winsound.PlaySound(str(path), winsound.SND_FILENAME | winsound.SND_ASYNC)


# --- uzaktan fare/klavye (telefon trackpad'i): ctypes SendInput, ek bagimlilik yok ---
import ctypes
from ctypes import wintypes

_MOUSE_FLAGS = {
    "left": (0x0002, 0x0004),    # LEFTDOWN, LEFTUP
    "right": (0x0008, 0x0010),   # RIGHTDOWN, RIGHTUP
    "middle": (0x0020, 0x0040),  # MIDDLEDOWN, MIDDLEUP
}
_MOVE, _WHEEL = 0x0001, 0x0800
_KEYEVENTF_KEYUP, _KEYEVENTF_UNICODE = 0x0002, 0x0004


class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


class _INPUT(ctypes.Structure):
    class _U(ctypes.Union):
        _fields_ = [("mi", _MOUSEINPUT), ("ki", _KEYBDINPUT)]

    _anonymous_ = ("u",)
    _fields_ = [("type", wintypes.DWORD), ("u", _U)]


def _send(*inputs: _INPUT) -> None:
    arr = (_INPUT * len(inputs))(*inputs)
    ctypes.windll.user32.SendInput(len(inputs), arr, ctypes.sizeof(_INPUT))


def _mouse(flags: int, dx: int = 0, dy: int = 0, data: int = 0) -> _INPUT:
    return _INPUT(type=0, mi=_MOUSEINPUT(dx, dy, data & 0xFFFFFFFF, flags, 0, 0))


def mouse_move(dx: int, dy: int) -> None:
    _send(_mouse(_MOVE, dx, dy))


def mouse_click(button: str) -> None:
    down, up = _MOUSE_FLAGS[button]
    _send(_mouse(down), _mouse(up))


def mouse_button(button: str, down: bool) -> None:
    flags = _MOUSE_FLAGS[button]
    _send(_mouse(flags[0] if down else flags[1]))


def mouse_scroll(steps: int) -> None:
    # pozitif = yukari; 1 adim = 120 (WHEEL_DELTA)
    _send(_mouse(_WHEEL, data=steps * 120))


def type_text(text: str) -> None:
    for ch in text:
        if ch == "\n":
            keyboard.send("enter")
            continue
        units = ch.encode("utf-16-le")
        for i in range(0, len(units), 2):
            code = int.from_bytes(units[i:i + 2], "little")
            down = _INPUT(type=1, ki=_KEYBDINPUT(0, code, _KEYEVENTF_UNICODE, 0, 0))
            up = _INPUT(type=1, ki=_KEYBDINPUT(0, code, _KEYEVENTF_UNICODE | _KEYEVENTF_KEYUP, 0, 0))
            _send(down, up)


def press_key(name: str) -> None:
    keyboard.send(name)


# --- pano (telefon <-> PC senkronu): ctypes, yalnizca metin ---
import time

_CF_UNICODETEXT = 13
_u32 = ctypes.WinDLL("user32")
_k32 = ctypes.WinDLL("kernel32")
_u32.OpenClipboard.argtypes = [ctypes.c_void_p]
_u32.GetClipboardData.argtypes = [wintypes.UINT]
_u32.GetClipboardData.restype = ctypes.c_void_p
_u32.SetClipboardData.argtypes = [wintypes.UINT, ctypes.c_void_p]
_u32.SetClipboardData.restype = ctypes.c_void_p
_u32.GetClipboardSequenceNumber.restype = wintypes.DWORD
_k32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
_k32.GlobalAlloc.restype = ctypes.c_void_p
_k32.GlobalLock.argtypes = [ctypes.c_void_p]
_k32.GlobalLock.restype = ctypes.c_void_p
_k32.GlobalUnlock.argtypes = [ctypes.c_void_p]
_k32.GlobalFree.argtypes = [ctypes.c_void_p]


def _open_clipboard() -> bool:
    for _ in range(5):  # baska uygulama panoyu tutuyor olabilir
        if _u32.OpenClipboard(None):
            return True
        time.sleep(0.01)
    return False


# sifre yoneticileri kopyaladiklari sifreyi bu formatla isaretler; telefona yayilmamali
_u32.RegisterClipboardFormatW.argtypes = [wintypes.LPCWSTR]
_u32.IsClipboardFormatAvailable.argtypes = [wintypes.UINT]
_EXCLUDE_FORMAT = _u32.RegisterClipboardFormatW("ExcludeClipboardContentFromMonitorProcessing")


def clipboard_seq() -> int:
    return _u32.GetClipboardSequenceNumber()


def get_clipboard_text() -> str | None:
    """Pano metni; metin yoksa veya gizli isaretliyse "", pano mesgulse None."""
    if _u32.IsClipboardFormatAvailable(_EXCLUDE_FORMAT):
        return ""
    if not _open_clipboard():
        return None
    try:
        handle = _u32.GetClipboardData(_CF_UNICODETEXT)
        if not handle:
            return ""
        ptr = _k32.GlobalLock(handle)
        if not ptr:
            return ""
        try:
            return ctypes.wstring_at(ptr)
        finally:
            _k32.GlobalUnlock(handle)
    finally:
        _u32.CloseClipboard()


def set_clipboard_text(text: str) -> None:
    data = (text + "\0").encode("utf-16-le")
    handle = _k32.GlobalAlloc(0x0002, len(data))  # GMEM_MOVEABLE
    ptr = _k32.GlobalLock(handle)
    ctypes.memmove(ptr, data, len(data))
    _k32.GlobalUnlock(handle)
    if not _open_clipboard():
        _k32.GlobalFree(handle)
        raise OSError("pano acilamadi")
    try:
        _u32.EmptyClipboard()
        if not _u32.SetClipboardData(_CF_UNICODETEXT, handle):
            _k32.GlobalFree(handle)
            raise OSError("pano yazilamadi")
    finally:
        _u32.CloseClipboard()
