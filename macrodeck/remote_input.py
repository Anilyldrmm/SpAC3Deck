# macrodeck/remote_input.py
"""Telefondan gelen fare/klavye mesajlarini dogrular ve os_bridge'e iletir."""
from __future__ import annotations

from . import os_bridge, screen

MOUSE_BUTTONS = {"left", "right", "middle"}
KEYS = {"enter", "backspace", "tab", "esc", "delete", "left", "right", "up", "down", "space"}
MAX_MOVE = 300
MAX_SCROLL = 30
MAX_TEXT = 200


def _num(value, limit: int) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("sayi bekleniyordu")
    return max(-limit, min(limit, int(value)))


def _unit(value) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("sayi bekleniyordu")
    return max(0.0, min(1.0, float(value)))


def handle(msg: dict, bridge=os_bridge, monitors=screen.monitors) -> None:
    kind = msg.get("kind")
    if kind == "abs":
        # secili monitorun icinde 0..1 oranli mutlak konum (dogrudan dokunma modu)
        rects = monitors()
        index = msg.get("monitor")
        if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < len(rects):
            raise ValueError("gecersiz monitor")
        left, top, right, bottom = rects[index]
        bridge.mouse_abs(left + round(_unit(msg.get("x")) * (right - left - 1)),
                         top + round(_unit(msg.get("y")) * (bottom - top - 1)))
        return
    if kind == "move":
        bridge.mouse_move(_num(msg.get("dx"), MAX_MOVE), _num(msg.get("dy"), MAX_MOVE))
    elif kind == "click" and msg.get("button", "left") in MOUSE_BUTTONS:
        bridge.mouse_click(msg.get("button", "left"))
    elif kind == "button" and msg.get("button", "left") in MOUSE_BUTTONS and isinstance(msg.get("down"), bool):
        bridge.mouse_button(msg.get("button", "left"), msg["down"])
    elif kind == "scroll":
        bridge.mouse_scroll(_num(msg.get("dy"), MAX_SCROLL))
    elif kind == "text" and isinstance(msg.get("text"), str):
        bridge.type_text(msg["text"][:MAX_TEXT])
    elif kind == "key" and msg.get("key") in KEYS:
        bridge.press_key(msg["key"])
