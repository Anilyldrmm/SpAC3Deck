from __future__ import annotations

from .registry import register


@register("launch_app")
def handle_launch_app(params: dict, context, event: str):
    if event != "press":
        return
    context.launch_uri(params["path"])


@register("open_url")
def handle_open_url(params: dict, context, event: str):
    if event != "press":
        return
    context.open_url(params["url"], params.get("browser", "default"))
