from __future__ import annotations

import secrets
from pathlib import Path

from fastapi import FastAPI, HTTPException

from .config import DeckConfig, load_config, save_config
from .state import generate_pin


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

    return app
