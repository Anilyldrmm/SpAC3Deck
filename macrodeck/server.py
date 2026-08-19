from __future__ import annotations

import asyncio
import hashlib
import json
import re
import secrets
import logging
import urllib.request
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Response, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

logger = logging.getLogger(__name__)

from . import __version__ as APP_VERSION
from . import autostart
from . import backups as backups_module
from .config import DeckConfig, load_config, save_config
from .discord_bridge import DiscordBridge, load_or_create_bridge_token
from .paths import web_root as get_web_root
from .qr import generate_deck_url, generate_qr_png
from .security import AttemptLimiter, build_allowed_origins, origin_allowed
from .sources import list_monitors, list_steam_games
from .state import generate_pin, compute_diff
from .actions.context import ActionContext
from .actions.registry import dispatch
from .ws import ConnectionManager

DEFAULT_PORT = 8765

AUTH_OK = "ok"
AUTH_BAD_ORIGIN = "bad_origin"
AUTH_RATE_LIMITED = "rate_limited"
AUTH_BAD_PIN = "bad_pin"


_STRIP_ACTIONS = {"voicemeeter_mute", "voicemeeter_gain", "voicemeeter_route"}
_BUS_ACTIONS = {"voicemeeter_bus_mute", "voicemeeter_bus_gain"}


def compute_strip_indices(config: DeckConfig) -> list[int]:
    """Config'deki voicemeeter butonlarindan poll edilecek strip listesini cikarir."""
    strip_indices = set()
    for page in config.pages:
        for button in page.buttons:
            if button.action in _STRIP_ACTIONS:
                strip_indices.add(button.params.get("strip_index", 0))
    return sorted(strip_indices)


def compute_bus_indices(config: DeckConfig) -> list[int]:
    """Config'deki voicemeeter bus butonlarindan poll edilecek bus listesini cikarir."""
    bus_indices = set()
    for page in config.pages:
        for button in page.buttons:
            if button.action in _BUS_ACTIONS:
                bus_indices.add(button.params.get("bus_index", 0))
    return sorted(bus_indices)


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
    app.state.discord_bridge = DiscordBridge()
    app.state.bridge_token = load_or_create_bridge_token(
        config_path.parent / "bridge_token.txt"
    )
    app.state.activate_callback = None  # main.py doldurur (AppLifecycle.open_configurator)

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
        backups_module.create_backup(app.state.config_path)
        save_config(config, app.state.config_path)
        # yeni config'deki strip/bus'lar restart beklemeden poll edilsin
        app.state.voicemeeter_strip_indices = compute_strip_indices(config)
        app.state.voicemeeter_bus_indices = compute_bus_indices(config)
        await app.state.manager.broadcast({"type": "reload"})
        return {"status": "ok"}

    @app.get("/api/backups")
    def get_backups(request: Request, token: str | None = None):
        _require_auth(request, token)
        return backups_module.list_backups(app.state.config_path)

    @app.post("/api/backups/{filename}/restore")
    async def restore_backup_endpoint(filename: str, request: Request, token: str | None = None):
        _require_auth(request, token)
        if not backups_module.restore_backup(app.state.config_path, filename):
            raise HTTPException(status_code=404, detail="backup not found")
        config = load_config(app.state.config_path)
        app.state.voicemeeter_strip_indices = compute_strip_indices(config)
        app.state.voicemeeter_bus_indices = compute_bus_indices(config)
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

    @app.get("/api/version")
    def get_version(request: Request, token: str | None = None):
        _require_auth(request, token)
        return {"version": APP_VERSION}

    @app.get("/api/settings/autostart")
    def get_autostart(request: Request, token: str | None = None):
        _require_auth(request, token)
        supported = autostart.is_supported()
        return {"supported": supported, "enabled": autostart.is_enabled() if supported else False}

    @app.post("/api/settings/autostart")
    def set_autostart(request: Request, payload: dict, token: str | None = None):
        _require_auth(request, token)
        if not autostart.is_supported():
            raise HTTPException(status_code=400, detail="sadece paketlenmis exe'de kullanilabilir")
        autostart.set_enabled(bool(payload.get("enabled")))
        return {"enabled": autostart.is_enabled()}

    @app.get("/api/bridge-token")
    def get_bridge_token(request: Request, token: str | None = None):
        _require_auth(request, token)
        return {"bridge_token": app.state.bridge_token, "bridge_connected": app.state.discord_bridge.connected}

    @app.post("/api/activate")
    def activate(request: Request, token: str | None = None):
        """Ikinci bir process (kisayol/exe tekrar calistirilinca) bu process'e
        'zaten calisiyorsun, pencereni on plana getir' der - Discord tarzi tek
        instance davranisi. main.py'de set edilir (activate_callback)."""
        _require_auth(request, token)
        callback = getattr(app.state, "activate_callback", None)
        if callback is not None:
            callback()
        return {"ok": True}

    @app.get("/api/sources/voicemeeter-strips")
    def get_voicemeeter_strips(request: Request, token: str | None = None):
        _require_auth(request, token)
        client = app.state.voicemeeter_client
        if client is None:
            return []
        return client.list_strips()

    @app.get("/api/sources/voicemeeter-buses")
    def get_voicemeeter_buses(request: Request, token: str | None = None):
        _require_auth(request, token)
        client = app.state.voicemeeter_client
        if client is None:
            return []
        return client.list_buses()

    @app.get("/api/sources/monitors")
    def get_monitors(request: Request, token: str | None = None):
        _require_auth(request, token)
        return list_monitors()

    @app.get("/api/sources/steam-games")
    def get_steam_games(request: Request, token: str | None = None):
        _require_auth(request, token)
        return list_steam_games()

    @app.get("/api/icon/steam/{appid}")
    def get_steam_icon(appid: str, request: Request, token: str | None = None):
        _require_auth(request, token)
        if not appid.isdigit():
            raise HTTPException(status_code=400, detail="invalid appid")

        cache_dir = app.state.config_path.parent / "icon_cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        icon_path = cache_dir / f"steam_{appid}.jpg"

        if not icon_path.exists():
            url = f"https://cdn.cloudflare.steamstatic.com/steam/apps/{appid}/header.jpg"
            try:
                with urllib.request.urlopen(url, timeout=5) as resp:
                    icon_path.write_bytes(resp.read())
            except OSError as exc:
                logger.warning("steam ikon indirilemedi (%s): %s", appid, exc)
                raise HTTPException(status_code=502, detail="icon indirilemedi")

        return Response(
            content=icon_path.read_bytes(),
            media_type="image/jpeg",
            headers={"Cache-Control": "public, max-age=604800"},
        )

    _UPLOAD_EXTENSIONS = {
        "image/png": "png",
        "image/jpeg": "jpg",
        "image/webp": "webp",
        "image/gif": "gif",
    }
    _MAX_UPLOAD_BYTES = 12 * 1024 * 1024  # gif'ler png/jpg'den buyuk olabilir

    @app.post("/api/icon/upload")
    async def upload_icon(request: Request, file: UploadFile, token: str | None = None):
        _require_auth(request, token)
        extension = _UPLOAD_EXTENSIONS.get(file.content_type)
        if extension is None:
            raise HTTPException(status_code=415, detail="desteklenmeyen dosya turu")

        content = await file.read(_MAX_UPLOAD_BYTES + 1)
        if len(content) > _MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="dosya cok buyuk (max 12MB)")

        custom_dir = app.state.config_path.parent / "icon_cache" / "custom"
        custom_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{hashlib.sha256(content).hexdigest()[:16]}.{extension}"
        (custom_dir / filename).write_bytes(content)

        return {"icon": f"/api/icon/custom/{filename}"}

    @app.get("/api/icon/custom/{filename}")
    def get_custom_icon(filename: str, request: Request, token: str | None = None):
        _require_auth(request, token)
        custom_dir = app.state.config_path.parent / "icon_cache" / "custom"
        icon_path = (custom_dir / filename).resolve()
        if custom_dir.resolve() not in icon_path.parents or not icon_path.is_file():
            raise HTTPException(status_code=404, detail="not found")

        media_type = "image/" + (filename.rsplit(".", 1)[-1] if "." in filename else "png")
        return Response(
            content=icon_path.read_bytes(),
            media_type=media_type,
            headers={"Cache-Control": "public, max-age=604800"},
        )

    _SOUND_EXTENSIONS = {"audio/wav": "wav", "audio/x-wav": "wav", "audio/wave": "wav"}
    _MAX_SOUND_BYTES = 10 * 1024 * 1024

    @app.post("/api/sound/upload")
    async def upload_sound(request: Request, file: UploadFile, token: str | None = None):
        _require_auth(request, token)
        extension = _SOUND_EXTENSIONS.get(file.content_type)
        if extension is None:
            raise HTTPException(status_code=415, detail="sadece WAV destekleniyor")

        content = await file.read(_MAX_SOUND_BYTES + 1)
        if len(content) > _MAX_SOUND_BYTES:
            raise HTTPException(status_code=413, detail="dosya cok buyuk (max 10MB)")

        sounds_dir = app.state.config_path.parent / "sounds"
        sounds_dir.mkdir(parents=True, exist_ok=True)
        original_stem = re.sub(r"[^a-zA-Z0-9_-]", "_", Path(file.filename or "ses").stem)[:40] or "ses"
        filename = f"{hashlib.sha256(content).hexdigest()[:12]}_{original_stem}.{extension}"
        (sounds_dir / filename).write_bytes(content)

        return {"file": filename, "label": file.filename or filename}

    @app.get("/api/sources/sounds")
    def get_sounds(request: Request, token: str | None = None):
        _require_auth(request, token)
        sounds_dir = app.state.config_path.parent / "sounds"
        if not sounds_dir.is_dir():
            return []
        return [{"file": p.name, "label": p.name} for p in sorted(sounds_dir.glob("*.wav"))]

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
    app.state.voicemeeter_kind = "banana"  # configure_runtime doldurur
    app.state.voicemeeter_strip_indices: list[int] = []
    app.state.voicemeeter_bus_indices: list[int] = []

    RECONNECT_INTERVAL = 5.0
    _last_reconnect_attempt = 0.0

    def _try_connect_voicemeeter(app):
        backend, client = _connect_voicemeeter(app.state.voicemeeter_kind)
        if client is None:
            return
        app.state.voicemeeter_backend = backend
        app.state.voicemeeter_client = client
        app.state.action_context.voicemeeter = client
        logger.info("voicemeeter'a sonradan baglanildi")

    async def _poll_voicemeeter():
        nonlocal _last_reconnect_attempt
        loop = asyncio.get_running_loop()
        while True:
            await asyncio.sleep(0.5)
            client = app.state.voicemeeter_client
            # Voicemeeter baslangicta kapaliysa client hep None kalirdi; burada
            # periyodik olarak yeniden baglanmayi dene (kullanici Voicemeeter'i
            # MacroDeck'ten sonra actiginda strip/bus listesi bos kalmasin diye).
            if client is None:
                now = loop.time()
                if now - _last_reconnect_attempt >= RECONNECT_INTERVAL:
                    _last_reconnect_attempt = now
                    _try_connect_voicemeeter(app)
                continue
            # bagli telefon yokken COM cagrilarini atla (bos yere CPU/COM overhead)
            if not app.state.manager.active:
                continue
            new_state = {}
            for strip_index in app.state.voicemeeter_strip_indices:
                new_state[f"strip{strip_index}_mute"] = client.get_mute_state(strip_index)
                new_state[f"strip{strip_index}_gain"] = client.get_gain_state(strip_index)
            for bus_index in app.state.voicemeeter_bus_indices:
                new_state[f"bus{bus_index}_mute"] = client.get_bus_mute_state(bus_index)
                new_state[f"bus{bus_index}_gain"] = client.get_bus_gain_state(bus_index)
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

    @app.websocket("/ws/discord-bridge")
    async def discord_bridge_endpoint(websocket: WebSocket, token: str):
        client_host = websocket.client.host if websocket.client else None
        if client_host not in ("127.0.0.1", "::1", "localhost"):
            await websocket.close(code=4403)
            return
        if not secrets.compare_digest(token.encode("utf-8"), app.state.bridge_token.encode("utf-8")):
            await websocket.close(code=4403)
            return

        await websocket.accept()
        app.state.discord_bridge.connect(websocket)
        logger.info("discord bridge (BetterDiscord plugin) baglandi")
        try:
            while True:
                raw = await websocket.receive_text()
                try:
                    message = json.loads(raw)
                except ValueError:
                    continue
                if message.get("type") == "state":
                    data = {k: v for k, v in message.items() if k != "type"}
                    logger.info("discord bridge state: %s", data)
                    await app.state.manager.broadcast({"type": "state", "data": data})
        except WebSocketDisconnect:
            pass
        finally:
            app.state.discord_bridge.disconnect(websocket)
            logger.info("discord bridge baglantisi kesildi")

    web_root = get_web_root()
    app.mount("/deck", StaticFiles(directory=web_root / "deck", html=True), name="deck")
    app.mount("/configure", StaticFiles(directory=web_root / "configure", html=True), name="configure")

    return app


def _connect_voicemeeter(kind: str):
    """Voicemeeter'a baglanmayi dener; kurulu/acik degilse (None, None) doner."""
    from .voicemeeter_backend import RealVoicemeeterBackend
    from .voicemeeter_client import VoicemeeterClient

    try:
        backend = RealVoicemeeterBackend(kind=kind)
        return backend, VoicemeeterClient(backend)
    except Exception as exc:
        logger.warning(
            "voicemeeter baglanamadi, voicemeeter butonlari devre disi: %s", exc
        )
        return None, None


def configure_runtime(app, voicemeeter_kind: str = "banana") -> None:
    from . import os_bridge
    from .discord_screenshare import DiscordScreenShareController

    # Voicemeeter kurulu/acik olmayabilir; bu durumda diger entegrasyonlar calismaya devam etmeli
    backend, voicemeeter_client = _connect_voicemeeter(voicemeeter_kind)

    screenshare = DiscordScreenShareController(app.state.discord_bridge)

    app.state.action_context = ActionContext(
        send_hotkey=os_bridge.send_hotkey,
        hold_key=os_bridge.hold_key,
        release_key=os_bridge.release_key,
        launch_uri=os_bridge.launch_uri,
        voicemeeter=voicemeeter_client,
        screenshare=screenshare,
        play_sound=os_bridge.play_sound,
        open_url=os_bridge.open_url,
    )
    app.state.voicemeeter_client = voicemeeter_client
    app.state.voicemeeter_backend = backend
    app.state.voicemeeter_kind = voicemeeter_kind

    current_config = load_config(app.state.config_path)
    app.state.voicemeeter_strip_indices = compute_strip_indices(current_config)
    app.state.voicemeeter_bus_indices = compute_bus_indices(current_config)
