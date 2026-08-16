from __future__ import annotations

import secrets
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect

from .config import DeckConfig, load_config, save_config
from .state import generate_pin
from .actions.context import ActionContext
from .actions.registry import dispatch
from .ws import ConnectionManager


def create_app(config_path: Path, pin: str | None = None) -> FastAPI:
    app = FastAPI()
    app.state.config_path = config_path
    app.state.pin = pin or generate_pin()

    def _check_pin(token: str | None) -> None:
        if token is None or not secrets.compare_digest(token, app.state.pin):
            raise HTTPException(status_code=403, detail="invalid pin")

    @app.get("/api/config")
    def get_config(token: str | None = None):
        _check_pin(token)
        return load_config(app.state.config_path).model_dump()

    @app.put("/api/config")
    def put_config(payload: dict, token: str | None = None):
        _check_pin(token)
        config = DeckConfig.model_validate(payload)
        save_config(config, app.state.config_path)
        return {"status": "ok"}

    app.state.manager = ConnectionManager()
    app.state.action_context = ActionContext(
        send_hotkey=lambda keys: None,
        hold_key=lambda keys: None,
        release_key=lambda keys: None,
        launch_uri=lambda uri: None,
        voicemeeter=None,
        screenshare=None,
    )

    def _find_button(config: DeckConfig, page_name: str, button_id: str):
        for page in config.pages:
            if page.name == page_name:
                for button in page.buttons:
                    if button.id == button_id:
                        return button
        return None

    @app.websocket("/ws")
    async def ws_endpoint(websocket: WebSocket, token: str):
        if not secrets.compare_digest(token, app.state.pin):
            await websocket.close(code=4403)
            return
        await app.state.manager.connect(websocket)
        try:
            while True:
                msg = await websocket.receive_json()
                config = load_config(app.state.config_path)
                button = _find_button(config, msg["page"], msg["button_id"])
                if button is None:
                    continue
                params = dict(button.params)
                if "value" in msg:
                    params["value"] = msg["value"]
                dispatch(button.action, params, app.state.action_context, msg.get("event", "press"))
        except WebSocketDisconnect:
            app.state.manager.disconnect(websocket)

    return app
