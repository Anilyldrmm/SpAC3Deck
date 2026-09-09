from __future__ import annotations

import logging
import threading
import time
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
# etiket alinamadiginda (Voicemeeter baglantisi yok, kanal adi bos) ne kadar
# sure sonra tekrar sorulacagi - her tus basisinda list_strips cagirmadan
LABEL_RETRY_SECONDS = 30.0


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
        osd=None,
    ):
        self._get_client = get_client
        self._get_config = get_config
        self._keyboard = keyboard_module
        self._osd = osd
        self._hooks: list[object] = []
        self._pressed: set[str] = set()
        # (target_type, index) -> (etiket, tekrar sorulabilecegi an | None)
        self._label_cache: dict[tuple[str, int], tuple[str, float | None]] = {}
        # mute durumu yalnizca kendi toggle'larimizdan izlenir; ekran ustu
        # gosterge icin Voicemeeter'a fazladan sorgu atmiyoruz
        self._mute_state: dict[tuple[str, int], bool] = {}
        # mute tusuna basildiginda kartta gosterilecek son bilinen dB
        self._last_gain: dict[tuple[str, int], float] = {}
        self._label_lock = threading.Lock()
        self._label_lookups: set[tuple[str, int]] = set()

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
        # yeniden baglanmada Voicemeeter etiketleri degismis olabilir
        self._label_cache.clear()

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
                new_gain = client.step_bus_gain(media_keys.target_index, delta)
            else:
                new_gain = client.step_gain(media_keys.target_index, delta)
        except Exception as exc:
            logger.warning("voicemeeter gain ayarlanamadi: %s", exc)
            return
        key = (media_keys.target_type, media_keys.target_index)
        self._notify_osd(media_keys, client, new_gain, self._mute_state.get(key, False))

    def _on_mute(self) -> None:
        media_keys = self._get_config().media_keys
        if not media_keys.enabled:
            return
        client = self._get_client()
        if client is None:
            return
        try:
            if media_keys.target_type == "bus":
                muted = client.toggle_bus_mute(media_keys.target_index)
            else:
                muted = client.toggle_mute(media_keys.target_index)
        except Exception as exc:
            logger.warning("voicemeeter mute ayarlanamadi: %s", exc)
            return
        key = (media_keys.target_type, media_keys.target_index)
        self._mute_state[key] = bool(muted)
        self._notify_osd(media_keys, client, self._last_gain.get(key, 0.0), bool(muted))

    def _notify_osd(self, media_keys, client, gain_db: float, muted: bool) -> None:
        """Ekran ustu gostergeyi tetikler; gosterge yoksa hicbir sey yapmaz.

        Degerler zaten elimizde olanlardan gelir (step/toggle cagrisinin
        dondurdugu deger): tus basma yolunda Voicemeeter'a FAZLADAN sorgu
        atilmaz. Yazdiktan sonra geri okumak, timeout ile kurulmus bir
        baglantida klavye hook thread'ini bloklayip knob'u tamamen olu
        gosterebiliyor - dogrulanmis regresyon. Ham toplami OSD kirpar
        (`clamp_gain`), mute durumu kendi toggle'larimizdan izlenir."""
        if self._osd is None:
            return
        key = (media_keys.target_type, media_keys.target_index)
        self._last_gain[key] = gain_db
        try:
            self._osd.show(self._target_label(media_keys, client), gain_db, muted)
        except Exception as exc:
            logger.debug("ses gostergesi gosterilemedi: %s", exc)

    def _target_label(self, media_keys, client) -> str:
        """Hedef kanalin etiketini onbellekten dondurur; yoksa hemen bir
        yer tutucu ("Strip 0") verip gercek etiketi arka planda cozer.

        Tus basma yolu Voicemeeter API'sine HIC dokunmamali: bu cagri
        klavye hook thread'inde calisiyor ve orada yapilan bir Voicemeeter
        sorgusu (baglanti timeout'una takilirsa) knob'u tamamen olu
        gosterebiliyor - dogrulanmis regresyon. Bu yuzden `list_strips`
        yalnizca ayri bir thread'de cagrilir; sonuc bir sonraki tus basisinda
        kullanilir."""
        key = (media_keys.target_type, media_keys.target_index)
        cached = self._label_cache.get(key)
        kind = "Bus" if media_keys.target_type == "bus" else "Strip"
        fallback = f"{kind} {media_keys.target_index}"
        if cached is not None:
            label, retry_at = cached
            if retry_at is None or time.monotonic() < retry_at:
                return label
        self._start_label_lookup(key, client, fallback)
        return cached[0] if cached is not None else fallback

    def _start_label_lookup(self, key, client, fallback: str) -> None:
        """Etiket cozumlemesini arka plan thread'inde baslatir (ayni hedef icin
        bir tane calisir)."""
        with self._label_lock:
            if key in self._label_lookups:
                return
            self._label_lookups.add(key)
        thread = threading.Thread(
            target=self._resolve_label,
            args=(key, client, fallback),
            name="macrodeck-osd-label",
            daemon=True,
        )
        thread.start()

    def _resolve_label(self, key, client, fallback: str) -> None:
        target_type, target_index = key
        try:
            channels = client.list_buses() if target_type == "bus" else client.list_strips()
        except Exception as exc:
            logger.debug("voicemeeter kanal etiketi alinamadi: %s", exc)
            self._label_cache[key] = (fallback, time.monotonic() + LABEL_RETRY_SECONDS)
            return
        finally:
            with self._label_lock:
                self._label_lookups.discard(key)
        for channel in channels:
            if channel.get("index") == target_index:
                label = channel.get("label")
                if label:
                    self._label_cache[key] = (label, None)
                    return
                break
        self._label_cache[key] = (fallback, time.monotonic() + LABEL_RETRY_SECONDS)
