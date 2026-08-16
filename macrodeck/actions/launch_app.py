from __future__ import annotations

from .registry import register


@register("launch_app")
def handle_launch_app(params: dict, context, event: str):
    if event != "press":
        return
    context.launch_uri(params["path"])
