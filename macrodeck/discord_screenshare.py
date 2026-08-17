from __future__ import annotations

from typing import Protocol


class ScreenShareAutomation(Protocol):
    def toggle_share(self, monitor_index: int) -> None: ...
    def toggle_stream_sound(self) -> None: ...
    def stop_share(self) -> None: ...
    def join_channel(self, guild_id: str, channel_id: str) -> None: ...
    def leave_channel(self) -> None: ...
    def toggle_camera(self) -> None: ...


class DiscordScreenShareController:
    def __init__(self, automation: ScreenShareAutomation):
        self._automation = automation

    def share_monitor(self, monitor_index: int) -> None:
        self._automation.toggle_share(monitor_index)

    def toggle_stream_sound(self) -> None:
        self._automation.toggle_stream_sound()

    def stop_share(self) -> None:
        self._automation.stop_share()

    def join_channel(self, guild_id: str, channel_id: str) -> None:
        self._automation.join_channel(guild_id, channel_id)

    def leave_channel(self) -> None:
        self._automation.leave_channel()

    def toggle_camera(self) -> None:
        self._automation.toggle_camera()
