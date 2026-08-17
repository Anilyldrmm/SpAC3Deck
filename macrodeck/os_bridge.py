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
