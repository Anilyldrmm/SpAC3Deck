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
