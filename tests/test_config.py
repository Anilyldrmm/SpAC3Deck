import json
from pathlib import Path
from macrodeck.config import Button, Page, DeckConfig, load_config, save_config

def test_load_config_missing_file_returns_empty(tmp_path):
    config = load_config(tmp_path / "deck.json")
    assert config.pages == []

def test_save_then_load_roundtrip(tmp_path):
    path = tmp_path / "deck.json"
    button = Button(id="b1", label="Mute", icon="🎙️", action="hotkey", params={"keys": ["ctrl", "m"]})
    page = Page(name="Genel", buttons=[button])
    config = DeckConfig(pages=[page])

    save_config(config, path)
    loaded = load_config(path)

    assert loaded.pages[0].name == "Genel"
    assert loaded.pages[0].buttons[0].id == "b1"
    assert loaded.pages[0].buttons[0].params == {"keys": ["ctrl", "m"]}

def test_save_writes_valid_json(tmp_path):
    path = tmp_path / "deck.json"
    save_config(DeckConfig(pages=[]), path)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data == {"pages": [], "grid_columns": 5, "grid_rows": 3}
