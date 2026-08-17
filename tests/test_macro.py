import time

from macrodeck.actions.registry import dispatch
from macrodeck.actions.context import ActionContext
import macrodeck.actions.macro  # noqa: F401
import macrodeck.actions.hotkey  # noqa: F401


def make_context():
    recorder = {"send_hotkey": []}
    context = ActionContext(
        send_hotkey=lambda keys: recorder["send_hotkey"].append(keys),
        hold_key=lambda keys: None,
        release_key=lambda keys: None,
        launch_uri=lambda uri: None,
        voicemeeter=None,
        screenshare=None,
    )
    return context, recorder


def test_macro_runs_steps_in_order():
    context, recorder = make_context()
    steps = [
        {"action": "hotkey", "params": {"keys": ["a"]}},
        {"action": "hotkey", "params": {"keys": ["b"]}},
    ]
    dispatch("macro", {"steps": steps}, context, "press")
    time.sleep(0.1)  # arka plan thread'inin bitmesini bekle
    assert recorder["send_hotkey"] == [["a"], ["b"]]


def test_macro_with_empty_steps_does_nothing():
    context, recorder = make_context()
    dispatch("macro", {"steps": []}, context, "press")
    time.sleep(0.02)
    assert recorder["send_hotkey"] == []


def test_macro_continues_after_step_failure():
    context, recorder = make_context()
    steps = [
        {"action": "does_not_exist", "params": {}},
        {"action": "hotkey", "params": {"keys": ["c"]}},
    ]
    dispatch("macro", {"steps": steps}, context, "press")
    time.sleep(0.1)
    assert recorder["send_hotkey"] == [["c"]]


def test_macro_ignores_non_press_event():
    context, recorder = make_context()
    steps = [{"action": "hotkey", "params": {"keys": ["a"]}}]
    dispatch("macro", {"steps": steps}, context, "release")
    time.sleep(0.02)
    assert recorder["send_hotkey"] == []
