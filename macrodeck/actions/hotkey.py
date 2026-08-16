from __future__ import annotations

from .registry import register


@register("hotkey")
def handle_hotkey(params: dict, context, event: str):
    if event != "press":
        return
    context.send_hotkey(params["keys"])


@register("hotkey_hold")
def handle_hotkey_hold(params: dict, context, event: str):
    keys = params["keys"]
    if event == "press":
        context.hold_key(keys)
    elif event == "release":
        context.release_key(keys)
