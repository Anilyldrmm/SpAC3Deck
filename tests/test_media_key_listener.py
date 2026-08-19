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
    def __init__(self):
        self.registered = {}
        self._next_hook_id = 0
        self.removed = []

    def add_hotkey(self, key, callback, suppress=False):
        self._next_hook_id += 1
        hook_id = self._next_hook_id
        self.registered[hook_id] = (key, callback, suppress)
        return hook_id

    def remove_hotkey(self, hook_id):
        self.removed.append(hook_id)
        del self.registered[hook_id]


def make_listener(config, client_or_none=FakeBackend, keyboard_module=None):
    backend = FakeBackend() if client_or_none is FakeBackend else client_or_none
    client = VoicemeeterClient(backend) if backend is not None else None
    listener = MediaKeyListener(
        get_client=lambda: client,
        get_config=lambda: config,
        keyboard_module=keyboard_module or FakeKeyboard(),
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


def test_start_does_not_register_hooks_when_disabled():
    config = DeckConfig(media_keys=MediaKeysConfig(enabled=False))
    fake_keyboard = FakeKeyboard()
    listener, _backend, _client = make_listener(config, keyboard_module=fake_keyboard)

    listener.start()

    assert fake_keyboard.registered == {}


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


def test_start_registers_volume_and_mute_hotkeys_with_suppress():
    config = DeckConfig(media_keys=MediaKeysConfig(enabled=True))
    fake_keyboard = FakeKeyboard()
    listener, _backend, _client = make_listener(config, keyboard_module=fake_keyboard)

    listener.start()

    registered_keys = {key for key, _cb, _suppress in fake_keyboard.registered.values()}
    assert registered_keys == {"volume up", "volume down", "volume mute"}
    assert all(suppress is True for _key, _cb, suppress in fake_keyboard.registered.values())


def test_stop_removes_all_registered_hooks():
    config = DeckConfig(media_keys=MediaKeysConfig(enabled=True))
    fake_keyboard = FakeKeyboard()
    listener, _backend, _client = make_listener(config, keyboard_module=fake_keyboard)
    listener.start()

    listener.stop()

    assert fake_keyboard.registered == {}
