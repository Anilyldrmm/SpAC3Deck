from __future__ import annotations

import json
import os
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
    # bos ise varsayilan "volume up"/"volume down"/"volume mute" kullanilir -
    # bazi klavye/knob donanimlari bu medya tuslarini WH_KEYBOARD_LL hook'unun
    # goremeyecegi bir kanaldan (APPCOMMAND/HID consumer-page) gonderdigi icin,
    # knob'u duz bir tus kombinasyonuna (F13 vb.) remap edip burada override
    # etmek gerekebiliyor.
    up_keys: list[str] = Field(default_factory=list)
    down_keys: list[str] = Field(default_factory=list)
    mute_keys: list[str] = Field(default_factory=list)
    # ekran ustu ses gostergesi (OSD). osd_x/osd_y sanal ekran koordinatidir -
    # yan monitorde x negatif olabilir, bu yuzden ayri bir "monitor sec" alani
    # yok. None ise ana ekranin alt ortasi kullanilir.
    osd_enabled: bool = True
    osd_x: int | None = None
    osd_y: int | None = None


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
    """Config'i atomik yazar (gecici dosya + os.replace).

    Dogrudan write_text dosyayi once bosaltip sonra doldurur; medya tusu
    dinleyicisi ve ses gostergesi config'i her tus basisinda okudugu icin bu
    araligda yarim dosya okunup parse hatasi alinabiliyordu."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(config.model_dump(), indent=2, ensure_ascii=False)
    tmp_path = path.with_name(path.name + ".tmp")
    tmp_path.write_text(payload, encoding="utf-8")
    os.replace(tmp_path, path)
