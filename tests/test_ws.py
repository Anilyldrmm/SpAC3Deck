from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from macrodeck.config import Button, Page, DeckConfig, save_config
from macrodeck.server import create_app
from macrodeck.actions.context import ActionContext
from macrodeck.ws import ConnectionManager
import macrodeck.actions.hotkey  # noqa: F401
import pytest


def build_client(tmp_path, lan_ip=None, port=8765):
    config_path = tmp_path / "deck.json"
    save_config(
        DeckConfig(pages=[Page(name="Genel", buttons=[
            Button(id="b1", label="Mute", action="hotkey", params={"keys": ["ctrl", "m"]})
        ])]),
        config_path,
    )
    app = create_app(config_path=config_path, pin="1234", lan_ip=lan_ip, port=port)

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
    with pytest.raises(WebSocketDisconnect) as excinfo:
        with client.websocket_connect("/ws?token=0000"):
            pass
    assert excinfo.value.code == 4403


def test_ws_rejects_disallowed_origin(tmp_path):
    """Origin allowlist'te olmayan sayfa dogru PIN ile bile baglanamamali (CSWSH)."""
    client, _ = build_client(tmp_path, lan_ip="192.168.1.10")
    with pytest.raises(WebSocketDisconnect) as excinfo:
        with client.websocket_connect(
            "/ws?token=1234", headers={"Origin": "http://evil.com:8000"}
        ):
            pass
    assert excinfo.value.code == 4403


def test_ws_rejects_origin_matching_host_header(tmp_path):
    """DNS rebinding: Origin ile Host ayni olsa bile allowlist disi ise reddedilir."""
    client, _ = build_client(tmp_path, lan_ip="192.168.1.10")
    with pytest.raises(WebSocketDisconnect) as excinfo:
        with client.websocket_connect(
            "/ws?token=1234",
            headers={"Origin": "http://evil.com", "Host": "evil.com"},
        ):
            pass
    assert excinfo.value.code == 4403


def test_ws_accepts_allowlisted_origin(tmp_path):
    client, recorder = build_client(tmp_path, lan_ip="192.168.1.10", port=8765)
    with client.websocket_connect(
        "/ws?token=1234", headers={"Origin": "http://192.168.1.10:8765"}
    ) as ws:
        ws.send_json({"page": "Genel", "button_id": "b1", "event": "press"})
    assert recorder["send_hotkey"] == [["ctrl", "m"]]


def test_ws_rate_limits_failed_pin_attempts(tmp_path):
    """N hatali PIN denemesinden sonra dogru PIN bile bir sure reddedilmeli."""
    client, _ = build_client(tmp_path)
    app = client.app
    app.state.rate_limiter.threshold = 3

    for _ in range(3):
        with pytest.raises(WebSocketDisconnect) as excinfo:
            with client.websocket_connect("/ws?token=0000"):
                pass
        assert excinfo.value.code == 4403

    with pytest.raises(WebSocketDisconnect) as excinfo:
        with client.websocket_connect("/ws?token=1234"):
            pass
    assert excinfo.value.code == 4429


def test_ws_malformed_message_does_not_crash_connection(tmp_path):
    """Test that malformed messages (missing button_id) don't crash the connection"""
    client, recorder = build_client(tmp_path)
    with client.websocket_connect("/ws?token=1234") as ws:
        # Send malformed message (missing button_id)
        ws.send_json({"page": "Genel"})
        # Send valid message to verify connection still works
        ws.send_json({"page": "Genel", "button_id": "b1", "event": "press"})
        # Send another malformed message (missing page)
        ws.send_json({"button_id": "b1"})
        # Send valid message again
        ws.send_json({"page": "Genel", "button_id": "b1", "event": "press"})

    # Should have dispatched 2 actions (the valid ones)
    assert recorder["send_hotkey"] == [["ctrl", "m"], ["ctrl", "m"]]


def test_put_config_broadcasts_reload_to_connected_clients(tmp_path):
    """Kaydet -> bagli telefonlara WS uzerinden reload sinyali gider."""
    client, _ = build_client(tmp_path)
    with client.websocket_connect("/ws?token=1234") as ws:
        response = client.put(
            "/api/config",
            params={"token": "1234"},
            json={"pages": [{"name": "Yeni", "buttons": []}]},
        )
        assert response.status_code == 200
        assert ws.receive_json() == {"type": "reload"}


@pytest.mark.asyncio
async def test_broadcast_handles_dead_sockets():
    """Test that broadcast() with dead sockets doesn't break delivery to others"""
    from fastapi import WebSocket
    from unittest.mock import AsyncMock, MagicMock

    manager = ConnectionManager()

    # Create mock websockets
    ws1 = MagicMock(spec=WebSocket)
    ws2 = MagicMock(spec=WebSocket)
    ws3 = MagicMock(spec=WebSocket)

    # Set application states - ws2 is CONNECTED but will fail on send
    from starlette.websockets import WebSocketState
    ws1.application_state = WebSocketState.CONNECTED
    ws2.application_state = WebSocketState.CONNECTED  # Dead socket (will fail on send)
    ws3.application_state = WebSocketState.CONNECTED

    ws1.send_json = AsyncMock()
    ws2.send_json = AsyncMock(side_effect=Exception("Socket closed"))
    ws3.send_json = AsyncMock()

    manager.active = [ws1, ws2, ws3]

    # Broadcast should handle the dead socket and still deliver to others
    await manager.broadcast({"type": "test"})

    # ws1 and ws3 should receive the message
    ws1.send_json.assert_called_once_with({"type": "test"})
    ws3.send_json.assert_called_once_with({"type": "test"})

    # ws2 should be removed from active list after failing to send
    assert manager.active == [ws1, ws3]
