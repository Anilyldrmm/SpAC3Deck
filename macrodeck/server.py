from __future__ import annotations

import asyncio
import secrets
import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

logger = logging.getLogger(__name__)

from .config import DeckConfig, load_config, save_config
from .qr import generate_deck_url, generate_qr_png
from .security import AttemptLimiter, build_allowed_origins, origin_allowed
from .state import generate_pin, compute_diff
from .actions.context import ActionContext
from .actions.registry import dispatch
from .ws import ConnectionManager

DEFAULT_PORT = 8765

AUTH_OK = "ok"
AUTH_BAD_ORIGIN = "bad_origin"
AUTH_RATE_LIMITED = "rate_limited"
AUTH_BAD_PIN = "bad_pin"


def compute_strip_indices(config: DeckConfig) -> list[int]:
    """Config'deki voicemeeter butonlarindan poll edilecek strip listesini cikarir."""
    strip_indices = set()
    for page in config.pages:
        for button in page.buttons:
            if button.action.startswith("voicemeeter_"):
                strip_indices.add(button.params.get("strip_index", 0))
    return sorted(strip_indices)


def create_app(
    config_path: Path,
    pin: str | None = None,
    lan_ip: str | None = None,
    port: int = DEFAULT_PORT,
) -> FastAPI:
    app = FastAPI()
    app.state.config_path = config_path
    app.state.pin = pin or generate_pin()
    app.state.lan_ip = lan_ip
    app.state.port = port
    app.state.rate_limiter = AttemptLimiter()
    app.state.allowed_origins = build_allowed_origins(
        ["localhost", "127.0.0.1", lan_ip], port
    )

    def _pin_matches(token: str | None) -> bool:
        if token is None:
            return False
        # compare_digest ASCII disi str ile TypeError atar; bytes ile karsilastir
        return secrets.compare_digest(token.encode("utf-8"), app.state.pin.encode("utf-8"))

    def _authorize(client_ip: str, origin: str | None, token: str | None) -> str:
        """REST ve WS icin ortak: origin allowlist -> rate limit -> PIN."""
        if not origin_allowed(origin, app.state.allowed_origins):
            logger.warning("origin reddedildi: %s (%s)", origin, client_ip)
            return AUTH_BAD_ORIGIN

        limiter: AttemptLimiter = app.state.rate_limiter
        if limiter.is_locked(client_ip):
            logger.warning("rate limit: %s kilitli", client_ip)
            return AUTH_RATE_LIMITED

        if not _pin_matches(token):
            locked = limiter.record_failure(client_ip)
            logger.warning("hatali pin: %s%s", client_ip, " (kilitlendi)" if locked else "")
            return AUTH_BAD_PIN

        limiter.reset(client_ip)
        return AUTH_OK

    def _require_auth(request: Request, token: str | None) -> None:
        client_ip = request.client.host if request.client else "unknown"
        result = _authorize(client_ip, request.headers.get("origin"), token)
        if result == AUTH_RATE_LIMITED:
            retry_after = app.state.rate_limiter.retry_after(client_ip)
            raise HTTPException(
                status_code=429,
                detail="too many failed attempts",
                headers={"Retry-After": str(retry_after or 1)},
            )
        if result == AUTH_BAD_ORIGIN:
            raise HTTPException(status_code=403, detail="origin not allowed")
        if result != AUTH_OK:
            raise HTTPException(status_code=403, detail="invalid pin")

    @app.get("/api/config")
    def get_config(request: Request, token: str | None = None):
        _require_auth(request, token)
        return load_config(app.state.config_path).model_dump()

    @app.put("/api/config")
    async def put_config(request: Request, payload: dict, token: str | None = None):
        _require_auth(request, token)
        try:
            config = DeckConfig.model_validate(payload)
        except ValidationError as exc:
            raise HTTPException(
                status_code=422,
                detail=exc.errors(include_url=False, include_context=False),
            )
        save_config(config, app.state.config_path)
        # yeni config'deki strip'ler restart beklemeden poll edilsin
        app.state.voicemeeter_strip_indices = compute_strip_indices(config)
        await app.state.manager.broadcast({"type": "reload"})
        return {"status": "ok"}

    @app.get("/api/qr")
    def get_qr(request: Request, token: str | None = None):
        _require_auth(request, token)
        host = app.state.lan_ip or request.url.hostname or "127.0.0.1"
        png = generate_qr_png(generate_deck_url(host, app.state.port, app.state.pin))
        return Response(
            content=png,
            media_type="image/png",
            headers={"Cache-Control": "no-store"},
        )

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
    app.state.voicemeeter_client = None  # configure_runtime doldurur
    app.state.voicemeeter_backend = None
    app.state.voicemeeter_strip_indices: list[int] = []

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
        result = _authorize(client_ip, websocket.headers.get("origin"), token)
        if result == AUTH_RATE_LIMITED:
            await websocket.close(code=4429)
            return
        if result != AUTH_OK:
            await websocket.close(code=4403)
            return

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


def configure_runtime(app, voicemeeter_kind: str = "banana") -> None:
    from . import os_bridge
    from .voicemeeter_backend import RealVoicemeeterBackend
    from .voicemeeter_client import VoicemeeterClient
    from .discord_automation import PywinautoScreenShareAutomation
    from .discord_screenshare import DiscordScreenShareController

    # Voicemeeter kurulu/acik olmayabilir; bu durumda diger entegrasyonlar calismaya devam etmeli
    backend = None
    voicemeeter_client = None
    try:
        backend = RealVoicemeeterBackend(kind=voicemeeter_kind)
        voicemeeter_client = VoicemeeterClient(backend)
    except Exception as exc:
        logger.warning(
            "voicemeeter baglanamadi, voicemeeter butonlari devre disi: %s", exc
        )
        backend = None
        voicemeeter_client = None

    screenshare = DiscordScreenShareController(PywinautoScreenShareAutomation())

    app.state.action_context = ActionContext(
        send_hotkey=os_bridge.send_hotkey,
        hold_key=os_bridge.hold_key,
        release_key=os_bridge.release_key,
        launch_uri=os_bridge.launch_uri,
        voicemeeter=voicemeeter_client,
        screenshare=screenshare,
    )
    app.state.voicemeeter_client = voicemeeter_client
    app.state.voicemeeter_backend = backend

    app.state.voicemeeter_strip_indices = compute_strip_indices(
        load_config(app.state.config_path)
    )
