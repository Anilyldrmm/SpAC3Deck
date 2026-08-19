from __future__ import annotations

import logging
from typing import Callable

import keyboard as _default_keyboard_module

from .config import DeckConfig

logger = logging.getLogger(__name__)

_DEFAULT_KEYS = {
    "up": "volume up",
    "down": "volume down",
    "mute": "volume mute",
}
_HANDLER_NAMES = {
    "up": "_on_volume_up",
    "down": "_on_volume_down",
    "mute": "_on_mute",
}


def _resolve_bindings(media_keys) -> dict[str, set[str]]:
    """Her aksiyon icin gereken tus kumesini dondurur: config'de ozel tus
    kombinasyonu (up_keys/down_keys/mute_keys) tanimliysa onu, yoksa
    varsayilan "volume up/down/mute" medya tusunu kullanir."""
    overrides = {
        "up": media_keys.up_keys,
        "down": media_keys.down_keys,
        "mute": media_keys.mute_keys,
    }
    return {
        action: set(keys) if keys else {_DEFAULT_KEYS[action]}
        for action, keys in overrides.items()
    }


class MediaKeyListener:
    """Klavye medya tuslarini (volume up/down/mute, ya da ozel bir tus
    kombinasyonu) Voicemeeter gain/mute'a yonlendirir.

    NOT: `keyboard.add_hotkey(..., suppress=True)` (ve cipiak
    `keyboard.hook(cb, suppress=True)`) bu ortamda (Python 3.14 +
    keyboard 0.13.5) hicbir olayi yakalamiyor - dogrulanmis (standalone
    prob'larla): suppress=True verildigi an kutuphane hicbir key event'i
    callback'e iletmiyor. Bu yuzden suppress=False `hook()` ile ham
    olaylari izleyip eslesmeyi kendimiz yapiyoruz. Bunun bedeli: config'de
    varsayilan "volume up/down/mute" kullanilirsa Windows'un kendi ses
    OSD'si de ayni anda tetiklenir (bastirilamiyor) - ozel bir tusa (F13
    vb.) remap edilirse bu sorun olmaz cunku o tusun zaten OS'ta bir
    islevi yok.

    Her tus basisinda config + voicemeeter client'i taze okur; boylece
    ayarlar degisince (configurator'dan) dinleyiciyi yeniden baslatmaya
    gerek kalmaz.
    """

    def __init__(
        self,
        get_client: Callable[[], object | None],
        get_config: Callable[[], DeckConfig],
        keyboard_module=_default_keyboard_module,
    ):
        self._get_client = get_client
        self._get_config = get_config
        self._keyboard = keyboard_module
        self._hooks: list[object] = []
        self._pressed: set[str] = set()

    def start(self) -> None:
        if not self._get_config().media_keys.enabled:
            return
        try:
            hook = self._keyboard.hook(self._handle_event)
            self._hooks.append(hook)
        except Exception as exc:
            logger.warning("medya tusu dinleyicisi baslatilamadi: %s", exc)

    def stop(self) -> None:
        for hook in self._hooks:
            try:
                self._keyboard.unhook(hook)
            except (KeyError, ValueError) as exc:
                logger.debug("hook kaldirilamadi: %s", exc)
        self._hooks.clear()
        self._pressed.clear()

    def _handle_event(self, event) -> None:
        name = getattr(event, "name", None)
        if name is None:
            return
        name = name.lower()
        if event.event_type == "up":
            self._pressed.discard(name)
            return
        if event.event_type != "down":
            return
        self._pressed.add(name)

        bindings = _resolve_bindings(self._get_config().media_keys)
        for action, required in bindings.items():
            if required <= self._pressed:
                getattr(self, _HANDLER_NAMES[action])()

    def _on_volume_up(self) -> None:
        self._apply_step(1)

    def _on_volume_down(self) -> None:
        self._apply_step(-1)

    def _apply_step(self, direction: int) -> None:
        media_keys = self._get_config().media_keys
        if not media_keys.enabled:
            return
        client = self._get_client()
        if client is None:
            return
        delta = direction * media_keys.step_db
        try:
            if media_keys.target_type == "bus":
                client.step_bus_gain(media_keys.target_index, delta)
            else:
                client.step_gain(media_keys.target_index, delta)
        except Exception as exc:
            logger.warning("voicemeeter gain ayarlanamadi: %s", exc)

    def _on_mute(self) -> None:
        media_keys = self._get_config().media_keys
        if not media_keys.enabled:
            return
        client = self._get_client()
        if client is None:
            return
        try:
            if media_keys.target_type == "bus":
                client.toggle_bus_mute(media_keys.target_index)
            else:
                client.toggle_mute(media_keys.target_index)
        except Exception as exc:
            logger.warning("voicemeeter mute ayarlanamadi: %s", exc)
