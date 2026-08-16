import pytest
from macrodeck.actions.registry import register, dispatch, get_registered_actions
from macrodeck.actions.context import ActionContext
import macrodeck.actions.hotkey  # noqa: F401  (register decorator'ları çalıştırır)


def make_context(**overrides):
    recorder = {"send_hotkey": [], "hold_key": [], "release_key": []}
    defaults = dict(
        send_hotkey=lambda keys: recorder["send_hotkey"].append(keys),
        hold_key=lambda keys: recorder["hold_key"].append(keys),
        release_key=lambda keys: recorder["release_key"].append(keys),
        launch_uri=lambda uri: None,
        voicemeeter=None,
        screenshare=None,
    )
    defaults.update(overrides)
    return ActionContext(**defaults), recorder


def test_dispatch_unknown_action_raises():
    context, _ = make_context()
    with pytest.raises(KeyError):
        dispatch("does_not_exist", {}, context, "press")


def test_hotkey_action_registered():
    assert "hotkey" in get_registered_actions()
    assert "hotkey_hold" in get_registered_actions()


def test_hotkey_press_sends_keys():
    context, recorder = make_context()
    dispatch("hotkey", {"keys": ["ctrl", "shift", "m"]}, context, "press")
    assert recorder["send_hotkey"] == [["ctrl", "shift", "m"]]


def test_hotkey_hold_press_and_release():
    context, recorder = make_context()
    dispatch("hotkey_hold", {"keys": ["v"]}, context, "press")
    dispatch("hotkey_hold", {"keys": ["v"]}, context, "release")
    assert recorder["hold_key"] == [["v"]]
    assert recorder["release_key"] == [["v"]]
