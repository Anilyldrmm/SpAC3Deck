from __future__ import annotations

import logging
import threading
import time

from .registry import register, dispatch

logger = logging.getLogger(__name__)


@register("macro")
def handle_macro(params: dict, context, event: str):
    if event != "press":
        return
    steps = params.get("steps", [])
    if not steps:
        return

    def run():
        for step in steps:
            try:
                dispatch(step["action"], step.get("params", {}), context, "press")
            except Exception:
                logger.exception("macro adimi basarisiz: %s", step)
            delay_ms = step.get("delay_ms", 0)
            if delay_ms:
                time.sleep(delay_ms / 1000)

    threading.Thread(target=run, daemon=True).start()
