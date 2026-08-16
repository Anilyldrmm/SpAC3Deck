from __future__ import annotations

from typing import Protocol


class VoicemeeterBackend(Protocol):
    def set_mute(self, strip_index: int, muted: bool) -> None: ...
    def get_mute(self, strip_index: int) -> bool: ...
    def set_gain(self, strip_index: int, value: float) -> None: ...
    def get_gain(self, strip_index: int) -> float: ...
    def set_route(self, strip_index: int, bus: str, enabled: bool) -> None: ...
    def get_route(self, strip_index: int, bus: str) -> bool: ...


class VoicemeeterClient:
    def __init__(self, backend: VoicemeeterBackend):
        self._backend = backend

    def toggle_mute(self, strip_index: int) -> bool:
        new_state = not self._backend.get_mute(strip_index)
        self._backend.set_mute(strip_index, new_state)
        return new_state

    def set_gain(self, strip_index: int, value: float) -> None:
        self._backend.set_gain(strip_index, value)

    def toggle_route(self, strip_index: int, bus: str) -> bool:
        new_state = not self._backend.get_route(strip_index, bus)
        self._backend.set_route(strip_index, bus, new_state)
        return new_state

    def get_mute_state(self, strip_index: int) -> bool:
        return self._backend.get_mute(strip_index)

    def get_gain_state(self, strip_index: int) -> float:
        return self._backend.get_gain(strip_index)
