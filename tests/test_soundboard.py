from macrodeck.actions.registry import dispatch
from macrodeck.actions.context import ActionContext
import macrodeck.actions.soundboard  # noqa: F401


def make_context(play_sound):
    return ActionContext(
        send_hotkey=lambda keys: None,
        hold_key=lambda keys: None,
        release_key=lambda keys: None,
        launch_uri=lambda uri: None,
        voicemeeter=None,
        screenshare=None,
        play_sound=play_sound,
    )


def test_dispatch_play_sound_action():
    played = []
    context = make_context(lambda filename: played.append(filename))
    dispatch("play_sound", {"file": "boom.wav"}, context, "press")
    assert played == ["boom.wav"]


def test_play_sound_ignores_non_press_event():
    played = []
    context = make_context(lambda filename: played.append(filename))
    dispatch("play_sound", {"file": "boom.wav"}, context, "release")
    assert played == []
