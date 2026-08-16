from __future__ import annotations

from typing import Protocol


class ScreenShareAutomation(Protocol):
    def toggle_share(self, monitor_index: int) -> None: ...


class DiscordScreenShareController:
    def __init__(self, automation: ScreenShareAutomation):
        self._automation = automation

    def share_monitor(self, monitor_index: int) -> None:
        self._automation.toggle_share(monitor_index)
