from macrodeck.voicemeeter_client import VoicemeeterClient
from macrodeck.actions.registry import dispatch
from macrodeck.actions.context import ActionContext
import macrodeck.actions.voicemeeter  # noqa: F401


class FakeBackend:
    def __init__(self):
        self.mute = {}
        self.gain = {}
        self.route = {}
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

    def get_route(self, strip_index, bus):
        return self.route.get((strip_index, bus), False)

    def set_route(self, strip_index, bus, enabled):
        self.route[(strip_index, bus)] = enabled

    def list_strips(self):
        return [{"index": 0, "label": "Mic"}, {"index": 1, "label": "System"}]

    def get_bus_mute(self, bus_index):
        return self.bus_mute.get(bus_index, False)

    def set_bus_mute(self, bus_index, muted):
        self.bus_mute[bus_index] = muted

    def get_bus_gain(self, bus_index):
        return self.bus_gain.get(bus_index, 0.0)

    def set_bus_gain(self, bus_index, value):
        self.bus_gain[bus_index] = value

    def list_buses(self):
        return [{"index": 0, "label": "A1"}, {"index": 1, "label": "B1"}]


def test_toggle_mute_flips_state():
    backend = FakeBackend()
    client = VoicemeeterClient(backend)
    assert client.toggle_mute(0) is True
    assert client.toggle_mute(0) is False


def test_set_gain_forwards_value():
    backend = FakeBackend()
    client = VoicemeeterClient(backend)
    client.set_gain(0, -6.5)
    assert backend.gain[0] == -6.5


def test_toggle_route_is_independent_per_bus():
    backend = FakeBackend()
    client = VoicemeeterClient(backend)
    assert client.toggle_route(0, "A1") is True
    assert client.toggle_route(0, "B1") is True
    assert backend.route[(0, "A1")] is True
    assert backend.route[(0, "B1")] is True


def test_get_mute_state_reads_through_backend():
    backend = FakeBackend()
    backend.mute[0] = True
    client = VoicemeeterClient(backend)
    assert client.get_mute_state(0) is True


def test_get_gain_state_reads_through_backend():
    backend = FakeBackend()
    backend.gain[0] = -12.0
    client = VoicemeeterClient(backend)
    assert client.get_gain_state(0) == -12.0


def test_step_gain_adds_delta_to_current_value():
    backend = FakeBackend()
    backend.gain[0] = -6.0
    client = VoicemeeterClient(backend)
    client.step_gain(0, 3.0)
    assert backend.gain[0] == -3.0


def test_step_bus_gain_adds_delta_to_current_value():
    backend = FakeBackend()
    backend.bus_gain[0] = -6.0
    client = VoicemeeterClient(backend)
    client.step_bus_gain(0, -3.0)
    assert backend.bus_gain[0] == -9.0


def test_list_strips_reads_through_backend():
    backend = FakeBackend()
    client = VoicemeeterClient(backend)
    assert client.list_strips() == [{"index": 0, "label": "Mic"}, {"index": 1, "label": "System"}]


def make_context(voicemeeter_client):
    return ActionContext(
        send_hotkey=lambda keys: None,
        hold_key=lambda keys: None,
        release_key=lambda keys: None,
        launch_uri=lambda uri: None,
        voicemeeter=voicemeeter_client,
        screenshare=None,
    )


def test_dispatch_voicemeeter_mute_action():
    backend = FakeBackend()
    client = VoicemeeterClient(backend)
    context = make_context(client)
    dispatch("voicemeeter_mute", {"strip_index": 0}, context, "press")
    assert backend.mute[0] is True


def test_dispatch_voicemeeter_gain_action_requires_set_event():
    backend = FakeBackend()
    client = VoicemeeterClient(backend)
    context = make_context(client)
    dispatch("voicemeeter_gain", {"strip_index": 0, "value": -3.0}, context, "set")
    assert backend.gain[0] == -3.0
    dispatch("voicemeeter_gain", {"strip_index": 0, "value": 99.0}, context, "press")
    assert backend.gain[0] == -3.0  # press event'te degismemeli


def test_dispatch_voicemeeter_route_action():
    backend = FakeBackend()
    client = VoicemeeterClient(backend)
    context = make_context(client)
    dispatch("voicemeeter_route", {"strip_index": 1, "bus": "A2"}, context, "press")
    assert backend.route[(1, "A2")] is True


def test_toggle_bus_mute_flips_state():
    backend = FakeBackend()
    client = VoicemeeterClient(backend)
    assert client.toggle_bus_mute(0) is True
    assert client.toggle_bus_mute(0) is False


def test_set_bus_gain_forwards_value():
    backend = FakeBackend()
    client = VoicemeeterClient(backend)
    client.set_bus_gain(0, -6.5)
    assert backend.bus_gain[0] == -6.5


def test_list_buses_reads_through_backend():
    backend = FakeBackend()
    client = VoicemeeterClient(backend)
    assert client.list_buses() == [{"index": 0, "label": "A1"}, {"index": 1, "label": "B1"}]


def test_dispatch_voicemeeter_bus_mute_action():
    backend = FakeBackend()
    client = VoicemeeterClient(backend)
    context = make_context(client)
    dispatch("voicemeeter_bus_mute", {"bus_index": 0}, context, "press")
    assert backend.bus_mute[0] is True


def test_dispatch_voicemeeter_bus_gain_action_requires_set_event():
    backend = FakeBackend()
    client = VoicemeeterClient(backend)
    context = make_context(client)
    dispatch("voicemeeter_bus_gain", {"bus_index": 0, "value": -3.0}, context, "set")
    assert backend.bus_gain[0] == -3.0
    dispatch("voicemeeter_bus_gain", {"bus_index": 0, "value": 99.0}, context, "press")
    assert backend.bus_gain[0] == -3.0
