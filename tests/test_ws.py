from fastapi.testclient import TestClient
from macrodeck.config import Button, Page, DeckConfig, save_config
from macrodeck.server import create_app
from macrodeck.actions.context import ActionContext
import macrodeck.actions.hotkey  # noqa: F401


def build_client(tmp_path):
    config_path = tmp_path / "deck.json"
    save_config(
        DeckConfig(pages=[Page(name="Genel", buttons=[
            Button(id="b1", label="Mute", action="hotkey", params={"keys": ["ctrl", "m"]})
        ])]),
        config_path,
    )
    app = create_app(config_path=config_path, pin="1234")

    recorder = {"send_hotkey": []}
    app.state.action_context = ActionContext(
        send_hotkey=lambda keys: recorder["send_hotkey"].append(keys),
        hold_key=lambda keys: None,
        release_key=lambda keys: None,
        launch_uri=lambda uri: None,
        voicemeeter=None,
        screenshare=None,
    )
    return TestClient(app), recorder


def test_ws_press_dispatches_configured_action(tmp_path):
    client, recorder = build_client(tmp_path)
    with client.websocket_connect("/ws?token=1234") as ws:
        ws.send_json({"page": "Genel", "button_id": "b1", "event": "press"})
        ws.send_json({"page": "Genel", "button_id": "unknown", "event": "press"})

    assert recorder["send_hotkey"] == [["ctrl", "m"]]


def test_ws_rejects_wrong_pin(tmp_path):
    client, _ = build_client(tmp_path)
    try:
        with client.websocket_connect("/ws?token=0000"):
            pass
        assert False, "baglanti kabul edilmemeliydi"
    except Exception:
        pass
