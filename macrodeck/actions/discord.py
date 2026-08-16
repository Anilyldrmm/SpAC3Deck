from __future__ import annotations

from .registry import register


@register("discord_screenshare")
def handle_discord_screenshare(params: dict, context, event: str):
    if event != "press":
        return
    context.screenshare.share_monitor(params["monitor_index"])
