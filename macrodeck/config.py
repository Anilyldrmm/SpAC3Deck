from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class Button(BaseModel):
    id: str
    label: str
    icon: str = ""
    action: str
    params: dict = Field(default_factory=dict)


class Page(BaseModel):
    name: str
    buttons: list[Button] = Field(default_factory=list)


class MediaKeysConfig(BaseModel):
    enabled: bool = False
    target_type: Literal["strip", "bus"] = "strip"
    target_index: int = 0
    step_db: float = 3.0


class DeckConfig(BaseModel):
    pages: list[Page] = Field(default_factory=list)
    grid_columns: int = 5
    grid_rows: int = 3
    media_keys: MediaKeysConfig = Field(default_factory=MediaKeysConfig)


def load_config(path: Path) -> DeckConfig:
    if not path.exists():
        return DeckConfig(pages=[])
    data = json.loads(path.read_text(encoding="utf-8"))
    return DeckConfig.model_validate(data)


def save_config(config: DeckConfig, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(config.model_dump(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
