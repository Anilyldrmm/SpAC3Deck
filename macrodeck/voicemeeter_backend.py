from __future__ import annotations

import voicemeeterlib

from .voicemeeter_client import VoicemeeterBackend

_BANANA_BUS_NAMES = ["A1", "A2", "A3", "B1", "B2"]

_BUS_ATTR = {
    "A1": "A1",
    "A2": "A2",
    "A3": "A3",
    "B1": "B1",
    "B2": "B2",
    "B3": "B3",
}


class RealVoicemeeterBackend:
    def __init__(self, kind: str = "banana", timeout: float = 10.0):
        # varsayilan kutuphane timeout'u 2sn: MacroDeck Voicemeeter'dan once
        # acilirsa login(), Voicemeeter GUI'sini kendi baslatir (VBVMR_RunVoicemeeter)
        # ve GUI'nin ilk acilisi 2sn'den uzun surebilir - bu durumda hazir-olma
        # kontrolu timeout'la patlar, oysa VBVMR_Login zaten basarili olmustur.
        vm = voicemeeterlib.api(kind, timeout=timeout)
        try:
            vm.login()
        except Exception:
            # login() Voicemeeter'i henuz acikken (ornegin GUI daha yeni
            # baslatildiginda) VBVMR_Login'i basariyla cagirip R isigini
            # yakabilir, sonra hazir-olma kontrolu timeout'la patlayabilir.
            # Logout cagrilmazsa DLL surec-genelinde "login" durumunda kalir:
            # Voicemeeter'da R isigi sonsuza dek yanik kalir ve sonraki
            # yeniden-baglanma denemeleri de bu yuzden basarisiz olur.
            try:
                vm.logout()
            except Exception:
                pass
            raise
        self._vm = vm

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

    def list_strips(self) -> list[dict]:
        return [
            {"index": i, "label": self._vm.strip[i].label or f"Strip {i}"}
            for i in range(self._vm.kind.num_strip)
        ]

    def set_bus_mute(self, bus_index: int, muted: bool) -> None:
        self._vm.bus[bus_index].mute = muted

    def get_bus_mute(self, bus_index: int) -> bool:
        return bool(self._vm.bus[bus_index].mute)

    def set_bus_gain(self, bus_index: int, value: float) -> None:
        self._vm.bus[bus_index].gain = value

    def get_bus_gain(self, bus_index: int) -> float:
        return float(self._vm.bus[bus_index].gain)

    def list_buses(self) -> list[dict]:
        return [
            {
                "index": i,
                "label": self._vm.bus[i].label
                or (_BANANA_BUS_NAMES[i] if i < len(_BANANA_BUS_NAMES) else f"Bus {i}"),
            }
            for i in range(self._vm.kind.num_bus)
        ]
