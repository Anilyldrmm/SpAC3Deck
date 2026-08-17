from __future__ import annotations

from .registry import register


@register("voicemeeter_mute")
def handle_voicemeeter_mute(params: dict, context, event: str):
    if event != "press":
        return
    context.voicemeeter.toggle_mute(params["strip_index"])


@register("voicemeeter_gain")
def handle_voicemeeter_gain(params: dict, context, event: str):
    if event != "set":
        return
    context.voicemeeter.set_gain(params["strip_index"], params["value"])


@register("voicemeeter_route")
def handle_voicemeeter_route(params: dict, context, event: str):
    if event != "press":
        return
    context.voicemeeter.toggle_route(params["strip_index"], params["bus"])


@register("voicemeeter_bus_mute")
def handle_voicemeeter_bus_mute(params: dict, context, event: str):
    if event != "press":
        return
    context.voicemeeter.toggle_bus_mute(params["bus_index"])


@register("voicemeeter_bus_gain")
def handle_voicemeeter_bus_gain(params: dict, context, event: str):
    if event != "set":
        return
    context.voicemeeter.set_bus_gain(params["bus_index"], params["value"])
