from __future__ import annotations

import asyncio
import secrets
import time
import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles

logger = logging.getLogger(__name__)

from .config import DeckConfig, load_config, save_config
from .state import generate_pin, compute_diff
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

    app.state.last_voicemeeter_state = {}
    app.state.voicemeeter_client = None  # Task 12'de RealVoicemeeterBackend ile doldurulur
    app.state.voicemeeter_strip_indices: list[int] = []  # poll edilecek strip'ler, config'den Task 12'de doldurulur
    app.state.ws_failed_attempts: dict[str, tuple[int, float]] = {}  # {ip: (count, first_timestamp)}
    app.state.ws_rate_limit_threshold = 10
    app.state.ws_rate_limit_window = 60
    app.state.ws_rate_limit_lockout = 30

    async def _poll_voicemeeter():
        while True:
            await asyncio.sleep(0.5)
            client = app.state.voicemeeter_client
            if client is None:
                continue
            new_state = {}
            for strip_index in app.state.voicemeeter_strip_indices:
                new_state[f"strip{strip_index}_mute"] = client.get_mute_state(strip_index)
                new_state[f"strip{strip_index}_gain"] = client.get_gain_state(strip_index)
            diff = compute_diff(app.state.last_voicemeeter_state, new_state)
            if diff:
                app.state.last_voicemeeter_state.update(diff)
                await app.state.manager.broadcast({"type": "state", "data": diff})

    @app.on_event("startup")
    async def _start_poller():
        asyncio.create_task(_poll_voicemeeter())

    @app.websocket("/ws")
    async def ws_endpoint(websocket: WebSocket, token: str):
        client_ip = websocket.client.host if websocket.client else "unknown"

        # Check origin header for CSWSH protection
        origin_header = websocket.headers.get("origin", "")
        if origin_header:
            host_header = websocket.headers.get("host", "")
            origin_host = origin_header.split("://", 1)[-1].split("/")[0]
            if origin_host != host_header:
                logger.warning(f"WebSocket origin mismatch: {origin_header} vs {host_header}")
                await websocket.close(code=4403)
                return

        # Check rate limiting on failed PIN attempts
        now = time.monotonic()
        if client_ip in app.state.ws_failed_attempts:
            fail_count, first_fail = app.state.ws_failed_attempts[client_ip]
            if now - first_fail < app.state.ws_rate_limit_window:
                if fail_count >= app.state.ws_rate_limit_threshold:
                    logger.warning(f"Rate limit exceeded for {client_ip}: {fail_count} failed attempts")
                    await websocket.close(code=4429)
                    return
            else:
                del app.state.ws_failed_attempts[client_ip]

        # Validate PIN
        if not secrets.compare_digest(token, app.state.pin):
            if client_ip not in app.state.ws_failed_attempts:
                app.state.ws_failed_attempts[client_ip] = (1, now)
            else:
                count, first_fail = app.state.ws_failed_attempts[client_ip]
                if now - first_fail < app.state.ws_rate_limit_window:
                    app.state.ws_failed_attempts[client_ip] = (count + 1, first_fail)
                else:
                    app.state.ws_failed_attempts[client_ip] = (1, now)

            await websocket.close(code=4403)
            return

        # Clear failed attempts on successful auth
        if client_ip in app.state.ws_failed_attempts:
            del app.state.ws_failed_attempts[client_ip]

        await app.state.manager.connect(websocket)
        try:
            while True:
                msg = await websocket.receive_json()

                # Validate message shape
                if not isinstance(msg, dict) or "page" not in msg or "button_id" not in msg:
                    logger.debug(f"Malformed message from {client_ip}: {msg}")
                    continue

                try:
                    config = load_config(app.state.config_path)
                    button = _find_button(config, msg["page"], msg["button_id"])
                    if button is None:
                        continue
                    params = dict(button.params)
                    if "value" in msg:
                        params["value"] = msg["value"]
                    dispatch(button.action, params, app.state.action_context, msg.get("event", "press"))
                except Exception as e:
                    logger.error(f"Error dispatching action: {e}")
                    continue
        except WebSocketDisconnect:
            pass
        finally:
            app.state.manager.disconnect(websocket)

    web_root = Path(__file__).resolve().parent.parent / "web"
    app.mount("/deck", StaticFiles(directory=web_root / "deck", html=True), name="deck")
    app.mount("/configure", StaticFiles(directory=web_root / "configure", html=True), name="configure")

    return app
