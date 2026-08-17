import asyncio
import json

import pytest

from macrodeck.discord_bridge import DiscordBridge


class FakeWebSocket:
    def __init__(self):
        self.sent = []

    async def send_text(self, data: str) -> None:
        self.sent.append(data)


def test_toggle_share_without_connection_does_not_raise():
    bridge = DiscordBridge()
    bridge.toggle_share(0)  # bagli client yok, sessizce atlanmali


@pytest.mark.asyncio
async def test_toggle_share_sends_go_live_command_to_connected_socket():
    bridge = DiscordBridge()
    websocket = FakeWebSocket()
    bridge.connect(websocket)

    bridge.toggle_share(1)
    await asyncio.sleep(0.01)  # run_coroutine_threadsafe callback'inin isleyebilmesi icin

    assert len(websocket.sent) == 1
    assert json.loads(websocket.sent[0]) == {"cmd": "go_live", "monitor_index": 1}


@pytest.mark.asyncio
async def test_disconnect_stops_further_sends():
    bridge = DiscordBridge()
    websocket = FakeWebSocket()
    bridge.connect(websocket)
    bridge.disconnect(websocket)

    bridge.toggle_share(0)
    await asyncio.sleep(0.01)

    assert websocket.sent == []
