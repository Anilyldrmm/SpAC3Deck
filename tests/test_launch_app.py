from macrodeck.actions.registry import dispatch
from macrodeck.actions.context import ActionContext
import macrodeck.actions.launch_app  # noqa: F401


def test_launch_app_forwards_path():
    calls = []
    context = ActionContext(
        send_hotkey=lambda keys: None,
        hold_key=lambda keys: None,
        release_key=lambda keys: None,
        launch_uri=lambda uri: calls.append(uri),
        voicemeeter=None,
        screenshare=None,
    )
    dispatch("launch_app", {"path": "C:/Games/game.exe"}, context, "press")
    assert calls == ["C:/Games/game.exe"]


def make_context(open_url):
    return ActionContext(
        send_hotkey=lambda keys: None,
        hold_key=lambda keys: None,
        release_key=lambda keys: None,
        launch_uri=lambda uri: None,
        voicemeeter=None,
        screenshare=None,
        open_url=open_url,
    )


def test_open_url_forwards_url_and_browser():
    calls = []
    context = make_context(lambda url, browser: calls.append((url, browser)))
    dispatch("open_url", {"url": "https://example.com", "browser": "chrome"}, context, "press")
    assert calls == [("https://example.com", "chrome")]


def test_open_url_defaults_browser_when_missing():
    calls = []
    context = make_context(lambda url, browser: calls.append((url, browser)))
    dispatch("open_url", {"url": "https://example.com"}, context, "press")
    assert calls == [("https://example.com", "default")]
