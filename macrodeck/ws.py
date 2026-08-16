from __future__ import annotations

import logging
from fastapi import WebSocket
from starlette.websockets import WebSocketState

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active:
            self.active.remove(websocket)

    async def broadcast(self, message: dict) -> None:
        dead_sockets = []
        for websocket in list(self.active):
            try:
                if websocket.application_state == WebSocketState.CONNECTED:
                    await websocket.send_json(message)
            except Exception as e:
                logger.debug(f"Failed to send to socket: {e}")
                dead_sockets.append(websocket)
        for ws in dead_sockets:
            self.disconnect(ws)
