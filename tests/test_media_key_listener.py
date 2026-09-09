from macrodeck.media_key_listener import MediaKeyListener
from macrodeck.voicemeeter_client import VoicemeeterClient
from macrodeck.config import DeckConfig, MediaKeysConfig


class FakeBackend:
    def __init__(self):
        self.mute = {}
        self.gain = {}
        self.bus_mute = {}
        self.bus_gain = {}

    def get_mute(self, strip_index):
        return self.mute.get(strip_index, False)

    def set_mute(self, strip_index, muted):
        self.mute[strip_index] = muted

    def get_gain(self, strip_index):
        return self.gain.get(strip_index, 0.0)

    def set_gain(self, strip_index, value):
        self.gain[strip_index] = value

    def get_bus_mute(self, bus_index):
        return self.bus_mute.get(bus_index, False)

    def set_bus_mute(self, bus_index, muted):
        self.bus_mute[bus_index] = muted

    def get_bus_gain(self, bus_index):
        return self.bus_gain.get(bus_index, 0.0)

    def set_bus_gain(self, bus_index, value):
        self.bus_gain[bus_index] = value


class FakeKeyboard:
    """add_hotkey(..., suppress=True) bu ortamda (Python 3.14 + keyboard 0.13.5)
    hicbir olayi yakalamiyor - dogrulanmis (bkz. media_key_listener.py'deki
    kok neden notu). MediaKeyListener bunun yerine hook()/unhook() kullaniyor,
    bu yuzden test double'i da onu taklit ediyor."""

    def __init__(self):
        self.hooked = {}
        self._next_hook_id = 0

    def hook(self, callback):
        self._next_hook_id += 1
        hook_id = self._next_hook_id
        self.hooked[hook_id] = callback
        return hook_id

    def unhook(self, hook_id):
        del self.hooked[hook_id]

    def fire(self, name, event_type):
        event = FakeEvent(name, event_type)
        for callback in list(self.hooked.values()):
            callback(event)


class FakeEvent:
    def __init__(self, name, event_type):
        self.name = name
        self.event_type = event_type


class FakeOsd:
    def __init__(self):
        self.shown = []

    def show(self, label, gain_db, muted):
        self.shown.append((label, gain_db, muted))


def make_listener(config, client_or_none=FakeBackend, keyboard_module=None, osd=None):
    backend = FakeBackend() if client_or_none is FakeBackend else client_or_none
    client = VoicemeeterClient(backend) if backend is not None else None
    listener = MediaKeyListener(
        get_client=lambda: client,
        get_config=lambda: config,
        keyboard_module=keyboard_module or FakeKeyboard(),
        osd=osd,
    )
    return listener, backend, client


def test_volume_up_increases_gain_on_strip_target():
    config = DeckConfig(media_keys=MediaKeysConfig(enabled=True, target_type="strip", target_index=0, step_db=3.0))
    listener, backend, _ = make_listener(config)
    backend.gain[0] = -6.0

    listener._on_volume_up()

    assert backend.gain[0] == -3.0


def test_volume_down_decreases_gain_on_bus_target():
    config = DeckConfig(media_keys=MediaKeysConfig(enabled=True, target_type="bus", target_index=1, step_db=2.0))
    listener, backend, _ = make_listener(config)
    backend.bus_gain[1] = -6.0

    listener._on_volume_down()

    assert backend.bus_gain[1] == -8.0


def test_mute_key_toggles_strip_mute():
    config = DeckConfig(media_keys=MediaKeysConfig(enabled=True, target_type="strip", target_index=0))
    listener, backend, _ = make_listener(config)

    listener._on_mute()

    assert backend.mute[0] is True


def test_mute_key_toggles_bus_mute():
    config = DeckConfig(media_keys=MediaKeysConfig(enabled=True, target_type="bus", target_index=0))
    listener, backend, _ = make_listener(config)

    listener._on_mute()

    assert backend.bus_mute[0] is True


def test_disabled_config_ignores_volume_up():
    config = DeckConfig(media_keys=MediaKeysConfig(enabled=False))
    listener, backend, _ = make_listener(config)
    backend.gain[0] = -6.0

    listener._on_volume_up()

    assert backend.gain[0] == -6.0


def test_no_voicemeeter_client_does_not_raise():
    config = DeckConfig(media_keys=MediaKeysConfig(enabled=True))
    listener, _backend, _client = make_listener(config, client_or_none=None)

    listener._on_volume_up()  # raise etmemeli


def test_start_does_not_hook_when_disabled():
    config = DeckConfig(media_keys=MediaKeysConfig(enabled=False))
    fake_keyboard = FakeKeyboard()
    listener, _backend, _client = make_listener(config, keyboard_module=fake_keyboard)

    listener.start()

    assert fake_keyboard.hooked == {}


class RaisingBackend(FakeBackend):
    def get_gain(self, strip_index):
        raise RuntimeError("voicemeeter baglantisi koptu")

    def get_mute(self, strip_index):
        raise RuntimeError("voicemeeter baglantisi koptu")


def test_apply_step_does_not_raise_when_voicemeeter_call_fails():
    config = DeckConfig(media_keys=MediaKeysConfig(enabled=True, target_type="strip", target_index=0))
    listener, _backend, _client = make_listener(config, client_or_none=RaisingBackend())

    listener._on_volume_up()  # raise etmemeli


def test_mute_does_not_raise_when_voicemeeter_call_fails():
    config = DeckConfig(media_keys=MediaKeysConfig(enabled=True, target_type="strip", target_index=0))
    listener, _backend, _client = make_listener(config, client_or_none=RaisingBackend())

    listener._on_mute()  # raise etmemeli


def test_start_installs_single_raw_hook_when_enabled():
    config = DeckConfig(media_keys=MediaKeysConfig(enabled=True))
    fake_keyboard = FakeKeyboard()
    listener, _backend, _client = make_listener(config, keyboard_module=fake_keyboard)

    listener.start()

    assert len(fake_keyboard.hooked) == 1


def test_stop_removes_the_hook():
    config = DeckConfig(media_keys=MediaKeysConfig(enabled=True))
    fake_keyboard = FakeKeyboard()
    listener, _backend, _client = make_listener(config, keyboard_module=fake_keyboard)
    listener.start()

    listener.stop()

    assert fake_keyboard.hooked == {}


def test_default_volume_up_key_press_triggers_gain_step():
    config = DeckConfig(media_keys=MediaKeysConfig(enabled=True, target_type="strip", target_index=0, step_db=3.0))
    fake_keyboard = FakeKeyboard()
    listener, backend, _client = make_listener(config, keyboard_module=fake_keyboard)
    backend.gain[0] = -6.0
    listener.start()

    fake_keyboard.fire("volume up", "down")

    assert backend.gain[0] == -3.0


def test_key_release_does_not_trigger():
    config = DeckConfig(media_keys=MediaKeysConfig(enabled=True, target_type="strip", target_index=0, step_db=3.0))
    fake_keyboard = FakeKeyboard()
    listener, backend, _client = make_listener(config, keyboard_module=fake_keyboard)
    backend.gain[0] = -6.0
    listener.start()

    fake_keyboard.fire("volume up", "up")

    assert backend.gain[0] == -6.0


def test_custom_single_key_binding_triggers_matching_action():
    config = DeckConfig(media_keys=MediaKeysConfig(
        enabled=True, target_type="strip", target_index=0, step_db=1.0,
        up_keys=["f13"], down_keys=["f14"], mute_keys=[],
    ))
    fake_keyboard = FakeKeyboard()
    listener, backend, _client = make_listener(config, keyboard_module=fake_keyboard)
    backend.gain[0] = 0.0
    listener.start()

    fake_keyboard.fire("f14", "down")

    assert backend.gain[0] == -1.0


def test_custom_key_binding_does_not_respond_to_old_default_key():
    """up_keys ozel atanmisken artik 'volume up' tetiklememeli."""
    config = DeckConfig(media_keys=MediaKeysConfig(
        enabled=True, target_type="strip", target_index=0, step_db=1.0,
        up_keys=["f13"],
    ))
    fake_keyboard = FakeKeyboard()
    listener, backend, _client = make_listener(config, keyboard_module=fake_keyboard)
    backend.gain[0] = 0.0
    listener.start()

    fake_keyboard.fire("volume up", "down")

    assert backend.gain[0] == 0.0


def test_multi_key_combo_requires_all_keys_held_before_triggering():
    config = DeckConfig(media_keys=MediaKeysConfig(
        enabled=True, target_type="strip", target_index=0, step_db=1.0,
        up_keys=["ctrl", "alt", "f19"],
    ))
    fake_keyboard = FakeKeyboard()
    listener, backend, _client = make_listener(config, keyboard_module=fake_keyboard)
    backend.gain[0] = 0.0
    listener.start()

    fake_keyboard.fire("ctrl", "down")
    fake_keyboard.fire("alt", "down")
    assert backend.gain[0] == 0.0  # henuz f19 basilmadi

    fake_keyboard.fire("f19", "down")
    assert backend.gain[0] == 1.0


# --- ekran ustu ses gostergesi (OSD) bildirimleri ---

class LabeledBackend(FakeBackend):
    def list_strips(self):
        return [{"index": 0, "label": "Mikrofon"}]

    def list_buses(self):
        return [{"index": 1, "label": "Kulaklık"}]


def test_volume_step_notifies_osd_with_new_gain_and_channel_label():
    config = DeckConfig(media_keys=MediaKeysConfig(enabled=True, target_type="strip", target_index=0, step_db=3.0))
    osd = FakeOsd()
    listener, backend, _client = make_listener(config, client_or_none=LabeledBackend(), osd=osd)
    backend.gain[0] = -6.0

    listener._on_volume_up()

    assert osd.shown == [("Mikrofon", -3.0, False)]


def test_mute_toggle_notifies_osd_with_mute_state():
    config = DeckConfig(media_keys=MediaKeysConfig(enabled=True, target_type="bus", target_index=1))
    osd = FakeOsd()
    listener, backend, _client = make_listener(config, client_or_none=LabeledBackend(), osd=osd)
    backend.bus_gain[1] = -4.0

    listener._on_mute()

    assert osd.shown == [("Kulaklık", -4.0, True)]


def test_osd_label_falls_back_when_channel_list_unavailable():
    config = DeckConfig(media_keys=MediaKeysConfig(enabled=True, target_type="strip", target_index=2, step_db=1.0))
    osd = FakeOsd()
    listener, _backend, _client = make_listener(config, osd=osd)  # FakeBackend'de list_strips yok

    listener._on_volume_up()

    assert osd.shown == [("Strip 2", 1.0, False)]


def test_osd_channel_label_is_cached_after_first_lookup():
    class CountingBackend(LabeledBackend):
        def __init__(self):
            super().__init__()
            self.list_calls = 0

        def list_strips(self):
            self.list_calls += 1
            return super().list_strips()

    config = DeckConfig(media_keys=MediaKeysConfig(enabled=True, target_type="strip", target_index=0, step_db=1.0))
    backend = CountingBackend()
    listener, _backend, _client = make_listener(config, client_or_none=backend, osd=FakeOsd())

    listener._on_volume_up()
    listener._on_volume_up()

    assert backend.list_calls == 1


def test_failed_voicemeeter_call_does_not_notify_osd():
    config = DeckConfig(media_keys=MediaKeysConfig(enabled=True, target_type="strip", target_index=0))
    osd = FakeOsd()
    listener, _backend, _client = make_listener(config, client_or_none=RaisingBackend(), osd=osd)

    listener._on_volume_up()

    assert osd.shown == []


def test_osd_label_fallback_is_not_cached_so_it_recovers_after_reconnect():
    """Kanal listesi henuz hazir olmadiginda "Strip 0" oturum sonuna kadar
    yapismamali."""
    class LateBackend(FakeBackend):
        def __init__(self):
            super().__init__()
            self.ready = False

        def list_strips(self):
            if not self.ready:
                raise RuntimeError("voicemeeter hazir degil")
            return [{"index": 0, "label": "Mikrofon"}]

    config = DeckConfig(media_keys=MediaKeysConfig(enabled=True, target_type="strip", target_index=0, step_db=1.0))
    backend = LateBackend()
    osd = FakeOsd()
    listener, _backend, _client = make_listener(config, client_or_none=backend, osd=osd)

    listener._on_volume_up()
    backend.ready = True
    listener._on_volume_up()

    assert [entry[0] for entry in osd.shown] == ["Strip 0", "Mikrofon"]


def test_stop_clears_the_label_cache():
    config = DeckConfig(media_keys=MediaKeysConfig(enabled=True, target_type="strip", target_index=0, step_db=1.0))
    listener, _backend, _client = make_listener(config, client_or_none=LabeledBackend(), osd=FakeOsd())
    listener._on_volume_up()

    listener.stop()

    assert listener._label_cache == {}


def test_osd_shows_the_value_read_back_from_voicemeeter_not_the_raw_sum():
    """Voicemeeter +12 dB'de kirpiyor; kart gerceklesmeyen bir deger yazmamali."""
    class ClampingBackend(LabeledBackend):
        def set_gain(self, strip_index, value):
            self.gain[strip_index] = min(12.0, max(-60.0, value))

    config = DeckConfig(media_keys=MediaKeysConfig(enabled=True, target_type="strip", target_index=0, step_db=3.0))
    backend = ClampingBackend()
    backend.gain[0] = 11.0
    osd = FakeOsd()
    listener, _backend, _client = make_listener(config, client_or_none=backend, osd=osd)

    listener._on_volume_up()

    assert osd.shown == [("Mikrofon", 12.0, False)]
