from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class ActionContext:
    send_hotkey: Callable[[list[str]], None]
    hold_key: Callable[[list[str]], None]
    release_key: Callable[[list[str]], None]
    launch_uri: Callable[[str], None]
    voicemeeter: Any
    screenshare: Any
