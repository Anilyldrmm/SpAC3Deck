from macrodeck.actions.registry import dispatch
from macrodeck.actions.context import ActionContext
import macrodeck.actions.steam  # noqa: F401


def make_context():
    calls = []
    context = ActionContext(
        send_hotkey=lambda keys: None,
        hold_key=lambda keys: None,
        release_key=lambda keys: None,
        launch_uri=lambda uri: calls.append(uri),
        voicemeeter=None,
        screenshare=None,
    )
    return context, calls


def test_steam_launch_builds_steam_uri():
    context, calls = make_context()
    dispatch("steam_launch", {"appid": "1234567"}, context, "press")
    assert calls == ["steam://run/1234567"]


def test_steam_launch_ignores_release_event():
    context, calls = make_context()
    dispatch("steam_launch", {"appid": "1234567"}, context, "release")
    assert calls == []
