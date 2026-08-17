from __future__ import annotations

import asyncio
import json
import logging
import secrets
from pathlib import Path

from fastapi import WebSocket

logger = logging.getLogger(__name__)


def load_or_create_bridge_token(path: Path) -> str:
    """BetterDiscord plugin'in kullanacagi sabit token; ilk calistirmada uretilir."""
    if path.exists():
        token = path.read_text(encoding="utf-8").strip()
        if token:
            return token
    token = secrets.token_hex(16)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(token, encoding="utf-8")
    return token


class DiscordBridge:
    """MacroDeck backend <-> BetterDiscord plugin arasi tek-baglantili WS kopru.

    `discord_screenshare` action'i icin `ScreenShareAutomation` protokolune
    uyar: `toggle_share` cagrisi plugin'e komut olarak gonderilir. Plugin
    tarafinda gercek "Go Live" tetiklenir; burasi sadece komutu iletir.
    """

    def __init__(self):
        self._websocket: WebSocket | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    @property
    def connected(self) -> bool:
        return self._websocket is not None

    def connect(self, websocket: WebSocket) -> None:
        self._websocket = websocket
        self._loop = asyncio.get_running_loop()

    def disconnect(self, websocket: WebSocket) -> None:
        if self._websocket is websocket:
            self._websocket = None
            self._loop = None

    def toggle_share(self, monitor_index: int) -> None:
        self.send_command({"cmd": "go_live", "monitor_index": monitor_index})

    def toggle_stream_sound(self) -> None:
        self.send_command({"cmd": "toggle_stream_sound"})

    def stop_share(self) -> None:
        self.send_command({"cmd": "stop_share"})

    def join_channel(self, guild_id: str, channel_id: str) -> None:
        self.send_command({"cmd": "join_channel", "guild_id": guild_id, "channel_id": channel_id})

    def leave_channel(self) -> None:
        self.send_command({"cmd": "leave_channel"})

    def toggle_camera(self) -> None:
        self.send_command({"cmd": "toggle_camera"})

    def send_command(self, command: dict) -> None:
        websocket = self._websocket
        loop = self._loop
        if websocket is None or loop is None:
            logger.warning("discord bridge bagli degil, komut atlandi: %s", command)
            return
        asyncio.run_coroutine_threadsafe(self._send(websocket, command), loop)

    async def _send(self, websocket: WebSocket, command: dict) -> None:
        try:
            await websocket.send_text(json.dumps(command))
        except Exception as exc:
            logger.warning("discord bridge komutu gonderilemedi: %s", exc)
