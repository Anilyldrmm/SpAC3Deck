from __future__ import annotations

from typing import Protocol


class VoicemeeterBackend(Protocol):
    def set_mute(self, strip_index: int, muted: bool) -> None: ...
    def get_mute(self, strip_index: int) -> bool: ...
    def set_gain(self, strip_index: int, value: float) -> None: ...
    def get_gain(self, strip_index: int) -> float: ...
    def set_route(self, strip_index: int, bus: str, enabled: bool) -> None: ...
    def get_route(self, strip_index: int, bus: str) -> bool: ...
    def list_strips(self) -> list[dict]: ...
    def set_bus_mute(self, bus_index: int, muted: bool) -> None: ...
    def get_bus_mute(self, bus_index: int) -> bool: ...
    def set_bus_gain(self, bus_index: int, value: float) -> None: ...
    def get_bus_gain(self, bus_index: int) -> float: ...
    def list_buses(self) -> list[dict]: ...


class VoicemeeterClient:
    def __init__(self, backend: VoicemeeterBackend):
        self._backend = backend

    def toggle_mute(self, strip_index: int) -> bool:
        new_state = not self._backend.get_mute(strip_index)
        self._backend.set_mute(strip_index, new_state)
        return new_state

    def set_gain(self, strip_index: int, value: float) -> None:
        self._backend.set_gain(strip_index, value)

    def step_gain(self, strip_index: int, delta: float) -> float:
        new_value = self._backend.get_gain(strip_index) + delta
        self._backend.set_gain(strip_index, new_value)
        return new_value

    def toggle_route(self, strip_index: int, bus: str) -> bool:
        new_state = not self._backend.get_route(strip_index, bus)
        self._backend.set_route(strip_index, bus, new_state)
        return new_state

    def get_mute_state(self, strip_index: int) -> bool:
        return self._backend.get_mute(strip_index)

    def get_gain_state(self, strip_index: int) -> float:
        return self._backend.get_gain(strip_index)

    def list_strips(self) -> list[dict]:
        return self._backend.list_strips()

    def toggle_bus_mute(self, bus_index: int) -> bool:
        new_state = not self._backend.get_bus_mute(bus_index)
        self._backend.set_bus_mute(bus_index, new_state)
        return new_state

    def set_bus_gain(self, bus_index: int, value: float) -> None:
        self._backend.set_bus_gain(bus_index, value)

    def step_bus_gain(self, bus_index: int, delta: float) -> float:
        new_value = self._backend.get_bus_gain(bus_index) + delta
        self._backend.set_bus_gain(bus_index, new_value)
        return new_value

    def get_bus_mute_state(self, bus_index: int) -> bool:
        return self._backend.get_bus_mute(bus_index)

    def get_bus_gain_state(self, bus_index: int) -> float:
        return self._backend.get_bus_gain(bus_index)

    def list_buses(self) -> list[dict]:
        return self._backend.list_buses()
