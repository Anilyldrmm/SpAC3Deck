from __future__ import annotations

import voicemeeterlib

from .voicemeeter_client import VoicemeeterBackend

_BUS_ATTR = {
    "A1": "A1",
    "A2": "A2",
    "A3": "A3",
    "B1": "B1",
    "B2": "B2",
    "B3": "B3",
}


class RealVoicemeeterBackend:
    def __init__(self, kind: str = "banana"):
        self._vm = voicemeeterlib.api(kind)
        self._vm.login()

    def set_mute(self, strip_index: int, muted: bool) -> None:
        self._vm.strip[strip_index].mute = muted

    def get_mute(self, strip_index: int) -> bool:
        return bool(self._vm.strip[strip_index].mute)

    def set_gain(self, strip_index: int, value: float) -> None:
        self._vm.strip[strip_index].gain = value

    def get_gain(self, strip_index: int) -> float:
        return float(self._vm.strip[strip_index].gain)

    def set_route(self, strip_index: int, bus: str, enabled: bool) -> None:
        setattr(self._vm.strip[strip_index], _BUS_ATTR[bus], enabled)

    def get_route(self, strip_index: int, bus: str) -> bool:
        return bool(getattr(self._vm.strip[strip_index], _BUS_ATTR[bus]))

    def logout(self) -> None:
        self._vm.logout()
