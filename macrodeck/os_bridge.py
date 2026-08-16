# macrodeck/os_bridge.py
from __future__ import annotations

import os

import keyboard


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
