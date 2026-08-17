from __future__ import annotations

from .registry import register


@register("discord_screenshare")
def handle_discord_screenshare(params: dict, context, event: str):
    if event != "press":
        return
    context.screenshare.share_monitor(params["monitor_index"])


@register("discord_stream_sound")
def handle_discord_stream_sound(params: dict, context, event: str):
    if event != "press":
        return
    context.screenshare.toggle_stream_sound()


@register("discord_stop_share")
def handle_discord_stop_share(params: dict, context, event: str):
    if event != "press":
        return
    context.screenshare.stop_share()


@register("discord_join_channel")
def handle_discord_join_channel(params: dict, context, event: str):
    if event != "press":
        return
    context.screenshare.join_channel(params["guild_id"], params["channel_id"])


@register("discord_leave_channel")
def handle_discord_leave_channel(params: dict, context, event: str):
    if event != "press":
        return
    context.screenshare.leave_channel()


@register("discord_camera_toggle")
def handle_discord_camera_toggle(params: dict, context, event: str):
    if event != "press":
        return
    context.screenshare.toggle_camera()
