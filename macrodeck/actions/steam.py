from __future__ import annotations

from .registry import register


@register("steam_launch")
def handle_steam_launch(params: dict, context, event: str):
    if event != "press":
        return
    context.launch_uri(f"steam://run/{params['appid']}")
