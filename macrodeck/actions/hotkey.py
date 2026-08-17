from __future__ import annotations

import logging

from .registry import register

logger = logging.getLogger(__name__)


@register("hotkey")
def handle_hotkey(params: dict, context, event: str):
    if event != "press":
        return
    keys = params["keys"]
    if not keys:
        logger.warning("hotkey butonuna tus atanmamis, atlandi")
        return
    context.send_hotkey(keys)


@register("hotkey_hold")
def handle_hotkey_hold(params: dict, context, event: str):
    keys = params["keys"]
    if not keys:
        if event == "press":
            logger.warning("hotkey_hold butonuna tus atanmamis, atlandi")
        return
    if event == "press":
        context.hold_key(keys)
    elif event == "release":
        context.release_key(keys)
