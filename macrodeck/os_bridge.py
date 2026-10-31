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
