from __future__ import annotations

from .registry import register


@register("play_sound")
def handle_play_sound(params: dict, context, event: str):
    if event != "press":
        return
    context.play_sound(params["file"])
