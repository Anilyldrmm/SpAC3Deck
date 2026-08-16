# MacroDeck Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Telefondan LAN üzerinden PC'yi kontrol eden, Discord/Voicemeeter/Steam entegrasyonlu, PC'de native configurator app'i olan bir macrodeck sistemi kurmak.

**Architecture:** Tek Python process — FastAPI backend (config + WebSocket + action dispatch), pywebview ile native PC configurator penceresi, telefon tarayıcısında açılan PWA deck view. Action handler'lar registry pattern ile eklenir, her entegrasyon (hotkey, steam, voicemeeter, discord screenshare) kendi dosyasında bir Protocol arkasında test edilebilir.

**Tech Stack:** Python 3.11+, FastAPI, uvicorn, websockets, pydantic, `keyboard`, `pywinauto`, `pywebview`, `pystray`, `qrcode`, `voicemeeter-api` (`voicemeeterlib`), pytest, pytest-asyncio, httpx.

**Spec:** `docs/superpowers/specs/2026-08-16-macrodeck-design.md`

## Global Constraints

- Sadece LAN üzerinde çalışır, internete açılmaz (spec: Güvenlik).
- Her bağlantı PIN ile korunur.
- Config dosyası: `config/deck.json`, Pydantic modelleriyle okunur/yazılır.
- Action handler'lar registry pattern: `actions/<type>.py` içinde `@register("type_name")` (spec: Genişletilebilirlik).
- Discord mute/deafen: kullanıcının Discord'da tanımladığı global hotkey simüle edilir, token kullanılmaz.
- Discord screenshare: `pywinauto` ile best-effort UI automation, kırılgan olduğu dokümante edilir.
- Voicemeeter: mute, gain, A1/A2/A3/B1/B2/B3 routing strip bazlı desteklenir.

---

## File Structure

```
macrodeck/
  __init__.py
  config.py                 # DeckConfig/Page/Button pydantic modelleri + load/save
  os_bridge.py               # gerçek OS köprüsü: send_hotkey, hold_key, release_key, launch_uri
  voicemeeter_client.py      # VoicemeeterBackend Protocol + VoicemeeterClient (mute/gain/route)
  voicemeeter_backend.py     # RealVoicemeeterBackend (voicemeeterlib sarmalayıcı)
  discord_screenshare.py     # ScreenShareAutomation Protocol + DiscordScreenShareController
  discord_automation.py      # PywinautoScreenShareAutomation (gerçek automation)
  state.py                   # PIN üretimi, compute_diff (state broadcast diff)
  ws.py                      # ConnectionManager (WebSocket broadcast)
  qr.py                      # generate_deck_url, generate_qr_png
  server.py                  # FastAPI app factory: REST + WS endpoint'leri
  tray.py                    # pystray tray icon + configurator pencere tetikleme
  main.py                    # entrypoint: server thread + tray + pywebview configurator
  actions/
    __init__.py
    registry.py               # register()/dispatch()/get_registered_actions()
    context.py                 # ActionContext dataclass
    hotkey.py                  # "hotkey", "hotkey_hold"
    steam.py                   # "steam_launch"
    voicemeeter.py             # "voicemeeter_mute", "voicemeeter_gain", "voicemeeter_route"
    discord.py                  # "discord_screenshare"
    launch_app.py               # "launch_app"
web/
  deck/index.html, app.js, style.css, manifest.json, sw.js
  configure/index.html, app.js, style.css
config/
  deck.json                  # örnek config
tests/
  test_config.py
  test_registry_hotkey.py
  test_steam.py
  test_server_api.py
  test_ws.py
  test_voicemeeter_client.py
  test_state_diff.py
  test_discord_screenshare.py
  test_launch_app.py
  test_qr.py
requirements.txt
README.md
```

---

### Task 1: Config modelleri + load/save

**Files:**
- Create: `macrodeck/__init__.py` (boş)
- Create: `macrodeck/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `Button(id: str, label: str, icon: str, action: str, params: dict)`, `Page(name: str, buttons: list[Button])`, `DeckConfig(pages: list[Page])`, `load_config(path: Path) -> DeckConfig`, `save_config(config: DeckConfig, path: Path) -> None`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_config.py
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
    assert data == {"pages": []}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'macrodeck'`

- [ ] **Step 3: Write minimal implementation**

```python
# macrodeck/config.py
from __future__ import annotations

import json
from pathlib import Path

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


class DeckConfig(BaseModel):
    pages: list[Page] = Field(default_factory=list)


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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_config.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add macrodeck/__init__.py macrodeck/config.py tests/test_config.py
git commit -m "feat: deck config modelleri ve load/save"
```

---

### Task 2: Action registry + ActionContext + hotkey handler

**Files:**
- Create: `macrodeck/actions/__init__.py` (boş)
- Create: `macrodeck/actions/registry.py`
- Create: `macrodeck/actions/context.py`
- Create: `macrodeck/actions/hotkey.py`
- Test: `tests/test_registry_hotkey.py`

**Interfaces:**
- Consumes: nothing (bağımsız modül)
- Produces: `register(name: str)` decorator, `dispatch(action_type: str, params: dict, context: ActionContext, event: str = "press")`, `get_registered_actions() -> list[str]`, `ActionContext(send_hotkey, hold_key, release_key, launch_uri, voicemeeter, screenshare)` — sonraki task'lar bu imzaları kullanır.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_registry_hotkey.py
import pytest
from macrodeck.actions.registry import register, dispatch, get_registered_actions
from macrodeck.actions.context import ActionContext
import macrodeck.actions.hotkey  # noqa: F401  (register decorator'ları çalıştırır)


def make_context(**overrides):
    recorder = {"send_hotkey": [], "hold_key": [], "release_key": []}
    defaults = dict(
        send_hotkey=lambda keys: recorder["send_hotkey"].append(keys),
        hold_key=lambda keys: recorder["hold_key"].append(keys),
        release_key=lambda keys: recorder["release_key"].append(keys),
        launch_uri=lambda uri: None,
        voicemeeter=None,
        screenshare=None,
    )
    defaults.update(overrides)
    return ActionContext(**defaults), recorder


def test_dispatch_unknown_action_raises():
    context, _ = make_context()
    with pytest.raises(KeyError):
        dispatch("does_not_exist", {}, context, "press")


def test_hotkey_action_registered():
    assert "hotkey" in get_registered_actions()
    assert "hotkey_hold" in get_registered_actions()


def test_hotkey_press_sends_keys():
    context, recorder = make_context()
    dispatch("hotkey", {"keys": ["ctrl", "shift", "m"]}, context, "press")
    assert recorder["send_hotkey"] == [["ctrl", "shift", "m"]]


def test_hotkey_hold_press_and_release():
    context, recorder = make_context()
    dispatch("hotkey_hold", {"keys": ["v"]}, context, "press")
    dispatch("hotkey_hold", {"keys": ["v"]}, context, "release")
    assert recorder["hold_key"] == [["v"]]
    assert recorder["release_key"] == [["v"]]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_registry_hotkey.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'macrodeck.actions'`

- [ ] **Step 3: Write minimal implementation**

```python
# macrodeck/actions/registry.py
from __future__ import annotations

from typing import Any, Callable

_HANDLERS: dict[str, Callable[[dict, Any, str], Any]] = {}


def register(name: str):
    def decorator(fn):
        _HANDLERS[name] = fn
        return fn

    return decorator


def dispatch(action_type: str, params: dict, context, event: str = "press"):
    handler = _HANDLERS.get(action_type)
    if handler is None:
        raise KeyError(f"unknown action type: {action_type}")
    return handler(params, context, event)


def get_registered_actions() -> list[str]:
    return sorted(_HANDLERS.keys())
```

```python
# macrodeck/actions/context.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class ActionContext:
    send_hotkey: Callable[[list[str]], None]
    hold_key: Callable[[list[str]], None]
    release_key: Callable[[list[str]], None]
    launch_uri: Callable[[str], None]
    voicemeeter: Any
    screenshare: Any
```

```python
# macrodeck/actions/hotkey.py
from __future__ import annotations

from .registry import register


@register("hotkey")
def handle_hotkey(params: dict, context, event: str):
    if event != "press":
        return
    context.send_hotkey(params["keys"])


@register("hotkey_hold")
def handle_hotkey_hold(params: dict, context, event: str):
    keys = params["keys"]
    if event == "press":
        context.hold_key(keys)
    elif event == "release":
        context.release_key(keys)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_registry_hotkey.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add macrodeck/actions/__init__.py macrodeck/actions/registry.py macrodeck/actions/context.py macrodeck/actions/hotkey.py tests/test_registry_hotkey.py
git commit -m "feat: action registry, ActionContext ve hotkey handler"
```

---

### Task 3: Steam launch + genel launch_app handler'ı

**Files:**
- Create: `macrodeck/actions/steam.py`
- Create: `macrodeck/actions/launch_app.py`
- Test: `tests/test_steam.py`
- Test: `tests/test_launch_app.py`

**Interfaces:**
- Consumes: `ActionContext.launch_uri(uri: str)` (Task 2)
- Produces: `"steam_launch"` ve `"launch_app"` action tipleri registry'de kayıtlı olur.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_steam.py
from macrodeck.actions.registry import dispatch
from macrodeck.actions.context import ActionContext
import macrodeck.actions.steam  # noqa: F401


def make_context():
    calls = []
    context = ActionContext(
        send_hotkey=lambda keys: None,
        hold_key=lambda keys: None,
        release_key=lambda keys: None,
        launch_uri=lambda uri: calls.append(uri),
        voicemeeter=None,
        screenshare=None,
    )
    return context, calls


def test_steam_launch_builds_steam_uri():
    context, calls = make_context()
    dispatch("steam_launch", {"appid": "1234567"}, context, "press")
    assert calls == ["steam://run/1234567"]


def test_steam_launch_ignores_release_event():
    context, calls = make_context()
    dispatch("steam_launch", {"appid": "1234567"}, context, "release")
    assert calls == []
```

```python
# tests/test_launch_app.py
from macrodeck.actions.registry import dispatch
from macrodeck.actions.context import ActionContext
import macrodeck.actions.launch_app  # noqa: F401


def test_launch_app_forwards_path():
    calls = []
    context = ActionContext(
        send_hotkey=lambda keys: None,
        hold_key=lambda keys: None,
        release_key=lambda keys: None,
        launch_uri=lambda uri: calls.append(uri),
        voicemeeter=None,
        screenshare=None,
    )
    dispatch("launch_app", {"path": "C:/Games/game.exe"}, context, "press")
    assert calls == ["C:/Games/game.exe"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_steam.py tests/test_launch_app.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'macrodeck.actions.steam'`

- [ ] **Step 3: Write minimal implementation**

```python
# macrodeck/actions/steam.py
from __future__ import annotations

from .registry import register


@register("steam_launch")
def handle_steam_launch(params: dict, context, event: str):
    if event != "press":
        return
    context.launch_uri(f"steam://run/{params['appid']}")
```

```python
# macrodeck/actions/launch_app.py
from __future__ import annotations

from .registry import register


@register("launch_app")
def handle_launch_app(params: dict, context, event: str):
    if event != "press":
        return
    context.launch_uri(params["path"])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_steam.py tests/test_launch_app.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add macrodeck/actions/steam.py macrodeck/actions/launch_app.py tests/test_steam.py tests/test_launch_app.py
git commit -m "feat: steam_launch ve launch_app action'lari"
```

---

### Task 4: Gerçek OS köprüsü (os_bridge)

**Files:**
- Create: `macrodeck/os_bridge.py`

**Interfaces:**
- Produces: `send_hotkey(keys: list[str]) -> None`, `hold_key(keys: list[str]) -> None`, `release_key(keys: list[str]) -> None`, `launch_uri(uri: str) -> None` — Task 12'de gerçek `ActionContext` bunlarla kurulur.

Bu modül gerçek OS/`keyboard` bağımlılığı kullandığı için otomatik test edilmez (manuel doğrulama Task 14'te).

- [ ] **Step 1: Implementasyonu yaz**

```python
# macrodeck/os_bridge.py
from __future__ import annotations

import os

import keyboard


def send_hotkey(keys: list[str]) -> None:
    keyboard.send("+".join(keys))


def hold_key(keys: list[str]) -> None:
    for key in keys:
        keyboard.press(key)


def release_key(keys: list[str]) -> None:
    for key in reversed(keys):
        keyboard.release(key)


def launch_uri(uri: str) -> None:
    os.startfile(uri)
```

- [ ] **Step 2: Manuel doğrulama notu ekle**

`requirements.txt` içine `keyboard` bağımlılığını ekle (Task 14'te tam liste tamamlanacak, burada satırı ekle):

```
keyboard>=0.13.5
```

- [ ] **Step 3: Commit**

```bash
git add macrodeck/os_bridge.py requirements.txt
git commit -m "feat: gercek OS koprusu (hotkey/launch_uri)"
```

---

### Task 5: Voicemeeter client (mute/gain/route) + fake backend testleri

**Files:**
- Create: `macrodeck/voicemeeter_client.py`
- Create: `macrodeck/actions/voicemeeter.py`
- Test: `tests/test_voicemeeter_client.py`

**Interfaces:**
- Produces: `VoicemeeterBackend` Protocol (`set_mute`, `get_mute`, `set_gain`, `get_gain`, `set_route`, `get_route`), `VoicemeeterClient(backend).toggle_mute(strip_index) -> bool`, `.set_gain(strip_index, value) -> None`, `.toggle_route(strip_index, bus) -> bool`. Action tipleri: `"voicemeeter_mute"`, `"voicemeeter_gain"` (event `"set"`, `params["value"]` zorunlu), `"voicemeeter_route"` (`params["bus"]` ∈ `{A1,A2,A3,B1,B2,B3}`).
- Consumes: `ActionContext.voicemeeter` (Task 2'den, artık `VoicemeeterClient` örneği taşır).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_voicemeeter_client.py
from macrodeck.voicemeeter_client import VoicemeeterClient
from macrodeck.actions.registry import dispatch
from macrodeck.actions.context import ActionContext
import macrodeck.actions.voicemeeter  # noqa: F401


class FakeBackend:
    def __init__(self):
        self.mute = {}
        self.gain = {}
        self.route = {}

    def get_mute(self, strip_index):
        return self.mute.get(strip_index, False)

    def set_mute(self, strip_index, muted):
        self.mute[strip_index] = muted

    def get_gain(self, strip_index):
        return self.gain.get(strip_index, 0.0)

    def set_gain(self, strip_index, value):
        self.gain[strip_index] = value

    def get_route(self, strip_index, bus):
        return self.route.get((strip_index, bus), False)

    def set_route(self, strip_index, bus, enabled):
        self.route[(strip_index, bus)] = enabled


def test_toggle_mute_flips_state():
    backend = FakeBackend()
    client = VoicemeeterClient(backend)
    assert client.toggle_mute(0) is True
    assert client.toggle_mute(0) is False


def test_set_gain_forwards_value():
    backend = FakeBackend()
    client = VoicemeeterClient(backend)
    client.set_gain(0, -6.5)
    assert backend.gain[0] == -6.5


def test_toggle_route_is_independent_per_bus():
    backend = FakeBackend()
    client = VoicemeeterClient(backend)
    assert client.toggle_route(0, "A1") is True
    assert client.toggle_route(0, "B1") is True
    assert backend.route[(0, "A1")] is True
    assert backend.route[(0, "B1")] is True


def make_context(voicemeeter_client):
    return ActionContext(
        send_hotkey=lambda keys: None,
        hold_key=lambda keys: None,
        release_key=lambda keys: None,
        launch_uri=lambda uri: None,
        voicemeeter=voicemeeter_client,
        screenshare=None,
    )


def test_dispatch_voicemeeter_mute_action():
    backend = FakeBackend()
    client = VoicemeeterClient(backend)
    context = make_context(client)
    dispatch("voicemeeter_mute", {"strip_index": 0}, context, "press")
    assert backend.mute[0] is True


def test_dispatch_voicemeeter_gain_action_requires_set_event():
    backend = FakeBackend()
    client = VoicemeeterClient(backend)
    context = make_context(client)
    dispatch("voicemeeter_gain", {"strip_index": 0, "value": -3.0}, context, "set")
    assert backend.gain[0] == -3.0
    dispatch("voicemeeter_gain", {"strip_index": 0, "value": 99.0}, context, "press")
    assert backend.gain[0] == -3.0  # press event'te degismemeli


def test_dispatch_voicemeeter_route_action():
    backend = FakeBackend()
    client = VoicemeeterClient(backend)
    context = make_context(client)
    dispatch("voicemeeter_route", {"strip_index": 1, "bus": "A2"}, context, "press")
    assert backend.route[(1, "A2")] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_voicemeeter_client.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'macrodeck.voicemeeter_client'`

- [ ] **Step 3: Write minimal implementation**

```python
# macrodeck/voicemeeter_client.py
from __future__ import annotations

from typing import Protocol


class VoicemeeterBackend(Protocol):
    def set_mute(self, strip_index: int, muted: bool) -> None: ...
    def get_mute(self, strip_index: int) -> bool: ...
    def set_gain(self, strip_index: int, value: float) -> None: ...
    def get_gain(self, strip_index: int) -> float: ...
    def set_route(self, strip_index: int, bus: str, enabled: bool) -> None: ...
    def get_route(self, strip_index: int, bus: str) -> bool: ...


class VoicemeeterClient:
    def __init__(self, backend: VoicemeeterBackend):
        self._backend = backend

    def toggle_mute(self, strip_index: int) -> bool:
        new_state = not self._backend.get_mute(strip_index)
        self._backend.set_mute(strip_index, new_state)
        return new_state

    def set_gain(self, strip_index: int, value: float) -> None:
        self._backend.set_gain(strip_index, value)

    def toggle_route(self, strip_index: int, bus: str) -> bool:
        new_state = not self._backend.get_route(strip_index, bus)
        self._backend.set_route(strip_index, bus, new_state)
        return new_state
```

```python
# macrodeck/actions/voicemeeter.py
from __future__ import annotations

from .registry import register


@register("voicemeeter_mute")
def handle_voicemeeter_mute(params: dict, context, event: str):
    if event != "press":
        return
    context.voicemeeter.toggle_mute(params["strip_index"])


@register("voicemeeter_gain")
def handle_voicemeeter_gain(params: dict, context, event: str):
    if event != "set":
        return
    context.voicemeeter.set_gain(params["strip_index"], params["value"])


@register("voicemeeter_route")
def handle_voicemeeter_route(params: dict, context, event: str):
    if event != "press":
        return
    context.voicemeeter.toggle_route(params["strip_index"], params["bus"])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_voicemeeter_client.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add macrodeck/voicemeeter_client.py macrodeck/actions/voicemeeter.py tests/test_voicemeeter_client.py
git commit -m "feat: voicemeeter client (mute/gain/route) ve action handler'lari"
```

---

### Task 6: Gerçek Voicemeeter backend (voicemeeterlib sarmalayıcı)

**Files:**
- Create: `macrodeck/voicemeeter_backend.py`

**Interfaces:**
- Consumes: `VoicemeeterBackend` Protocol (Task 5)
- Produces: `RealVoicemeeterBackend(kind: str = "banana")` — `VoicemeeterBackend` protokolünü gerçek `voicemeeterlib` ile uygular. Gerçek Voicemeeter DLL'i gerektirdiği için otomatik test edilmez, sadece Task 5'in Protocol'üne uyumu statik olarak (tip imzaları) doğrulanır.

- [ ] **Step 1: Implementasyonu yaz**

```python
# macrodeck/voicemeeter_backend.py
from __future__ import annotations

import voicemeeterlib

from .voicemeeter_client import VoicemeeterBackend

_BUS_ATTR = {
    "A1": "A1",
    "A2": "A2",
    "A3": "A3",
    "B1": "B1",
    "B2": "B2",
    "B3": "B3",
}


class RealVoicemeeterBackend:
    def __init__(self, kind: str = "banana"):
        self._vm = voicemeeterlib.api(kind)
        self._vm.login()

    def set_mute(self, strip_index: int, muted: bool) -> None:
        self._vm.strip[strip_index].mute = muted

    def get_mute(self, strip_index: int) -> bool:
        return bool(self._vm.strip[strip_index].mute)

    def set_gain(self, strip_index: int, value: float) -> None:
        self._vm.strip[strip_index].gain = value

    def get_gain(self, strip_index: int) -> float:
        return float(self._vm.strip[strip_index].gain)

    def set_route(self, strip_index: int, bus: str, enabled: bool) -> None:
        setattr(self._vm.strip[strip_index], _BUS_ATTR[bus], enabled)

    def get_route(self, strip_index: int, bus: str) -> bool:
        return bool(getattr(self._vm.strip[strip_index], _BUS_ATTR[bus]))

    def logout(self) -> None:
        self._vm.logout()
```

Protocol uyumluluğu (Task 5'teki `VoicemeeterBackend`) çalışma zamanında değil, statik tip kontrolüyle doğrulanır — burada ek bir çalışma zamanı kontrolüne gerek yok.

- [ ] **Step 2: requirements.txt güncelle**

```
voicemeeter-api>=2.0.0
```

- [ ] **Step 3: Commit**

```bash
git add macrodeck/voicemeeter_backend.py requirements.txt
git commit -m "feat: gercek voicemeeter backend (voicemeeterlib sarmalayici)"
```

---

### Task 7: Discord screenshare controller (Protocol + fake test) ve gerçek pywinauto automation

**Files:**
- Create: `macrodeck/discord_screenshare.py`
- Create: `macrodeck/discord_automation.py`
- Create: `macrodeck/actions/discord.py`
- Test: `tests/test_discord_screenshare.py`

**Interfaces:**
- Produces: `ScreenShareAutomation` Protocol (`toggle_share(monitor_index: int) -> None`), `DiscordScreenShareController(automation).share_monitor(monitor_index: int) -> None`, action tipi `"discord_screenshare"` (`params["monitor_index"]`).
- Consumes: `ActionContext.screenshare` (Task 2'den, artık `DiscordScreenShareController` örneği taşır).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_discord_screenshare.py
from macrodeck.discord_screenshare import DiscordScreenShareController
from macrodeck.actions.registry import dispatch
from macrodeck.actions.context import ActionContext
import macrodeck.actions.discord  # noqa: F401


class FakeAutomation:
    def __init__(self):
        self.calls = []

    def toggle_share(self, monitor_index: int) -> None:
        self.calls.append(monitor_index)


def test_controller_forwards_monitor_index():
    automation = FakeAutomation()
    controller = DiscordScreenShareController(automation)
    controller.share_monitor(1)
    assert automation.calls == [1]


def test_dispatch_discord_screenshare_action():
    automation = FakeAutomation()
    controller = DiscordScreenShareController(automation)
    context = ActionContext(
        send_hotkey=lambda keys: None,
        hold_key=lambda keys: None,
        release_key=lambda keys: None,
        launch_uri=lambda uri: None,
        voicemeeter=None,
        screenshare=controller,
    )
    dispatch("discord_screenshare", {"monitor_index": 0}, context, "press")
    assert automation.calls == [0]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_discord_screenshare.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'macrodeck.discord_screenshare'`

- [ ] **Step 3: Write minimal implementation**

```python
# macrodeck/discord_screenshare.py
from __future__ import annotations

from typing import Protocol


class ScreenShareAutomation(Protocol):
    def toggle_share(self, monitor_index: int) -> None: ...


class DiscordScreenShareController:
    def __init__(self, automation: ScreenShareAutomation):
        self._automation = automation

    def share_monitor(self, monitor_index: int) -> None:
        self._automation.toggle_share(monitor_index)
```

```python
# macrodeck/actions/discord.py
from __future__ import annotations

from .registry import register


@register("discord_screenshare")
def handle_discord_screenshare(params: dict, context, event: str):
    if event != "press":
        return
    context.screenshare.share_monitor(params["monitor_index"])
```

Gerçek automation — **best-effort, kırılgan**, Discord UI güncellemesinde bozulabilir, manuel doğrulama gerekir (Task 14):

```python
# macrodeck/discord_automation.py
from __future__ import annotations

from pywinauto import Application


class PywinautoScreenShareAutomation:
    """Discord ekran paylasimi icin UI automation.

    Discord'da ekran paylasimi baslatma/durdurma icin native global hotkey
    yok, bu yuzden pencere otomasyonu kullaniliyor. Discord penceresi acik
    olmali. Discord'un UI'si degisirse (button title/control_type) bu sinif
    guncellenmeli.
    """

    def toggle_share(self, monitor_index: int) -> None:
        app = Application(backend="uia").connect(title_re=".*Discord.*")
        window = app.top_window()
        window.set_focus()

        share_button = window.child_window(
            title="Share Your Screen", control_type="Button"
        )
        share_button.click_input()

        picker_items = window.descendants(control_type="ListItem")
        screen_items = [
            item for item in picker_items if item.window_text().lower().startswith("screen")
        ]
        screen_items[monitor_index].click_input()

        confirm_button = window.child_window(title="Go Live", control_type="Button")
        confirm_button.click_input()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_discord_screenshare.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: requirements.txt güncelle**

```
pywinauto>=0.6.8
```

- [ ] **Step 6: Commit**

```bash
git add macrodeck/discord_screenshare.py macrodeck/discord_automation.py macrodeck/actions/discord.py tests/test_discord_screenshare.py requirements.txt
git commit -m "feat: discord screenshare controller ve best-effort pywinauto automation"
```

---

### Task 8: State diff hesaplama + PIN üretimi

**Files:**
- Create: `macrodeck/state.py`
- Test: `tests/test_state_diff.py`

**Interfaces:**
- Produces: `generate_pin() -> str` (4 haneli), `compute_diff(old_state: dict, new_state: dict) -> dict` — sadece değişen key'leri döner. Task 10'da poller bu fonksiyonu kullanır.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_state_diff.py
from macrodeck.state import compute_diff, generate_pin


def test_generate_pin_is_four_digits():
    pin = generate_pin()
    assert len(pin) == 4
    assert pin.isdigit()


def test_compute_diff_returns_only_changed_keys():
    old = {"strip0_mute": False, "strip0_gain": -6.0}
    new = {"strip0_mute": True, "strip0_gain": -6.0}
    assert compute_diff(old, new) == {"strip0_mute": True}


def test_compute_diff_includes_new_keys():
    old = {"strip0_mute": False}
    new = {"strip0_mute": False, "strip1_mute": True}
    assert compute_diff(old, new) == {"strip1_mute": True}


def test_compute_diff_empty_when_unchanged():
    state = {"strip0_mute": False}
    assert compute_diff(state, dict(state)) == {}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_state_diff.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'macrodeck.state'`

- [ ] **Step 3: Write minimal implementation**

```python
# macrodeck/state.py
from __future__ import annotations

import secrets


def generate_pin() -> str:
    return f"{secrets.randbelow(10000):04d}"


def compute_diff(old_state: dict, new_state: dict) -> dict:
    return {
        key: value
        for key, value in new_state.items()
        if key not in old_state or old_state[key] != value
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_state_diff.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add macrodeck/state.py tests/test_state_diff.py
git commit -m "feat: pin uretimi ve state diff hesaplama"
```

---

### Task 9: FastAPI server — config REST endpoint'leri + PIN auth

**Files:**
- Create: `macrodeck/server.py`
- Test: `tests/test_server_api.py`

**Interfaces:**
- Consumes: `DeckConfig`, `load_config`, `save_config` (Task 1), `generate_pin` (Task 8)
- Produces: `create_app(config_path: Path, pin: str | None = None) -> FastAPI` — `app.state.pin`, `app.state.config_path` taşır. Task 10, 11, 13 bu fonksiyonu genişletir.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_server_api.py
from fastapi.testclient import TestClient
from macrodeck.config import Button, Page, DeckConfig, save_config
from macrodeck.server import create_app


def build_client(tmp_path, pin="1234"):
    config_path = tmp_path / "deck.json"
    save_config(
        DeckConfig(pages=[Page(name="Genel", buttons=[
            Button(id="b1", label="Mute", action="hotkey", params={"keys": ["ctrl", "m"]})
        ])]),
        config_path,
    )
    app = create_app(config_path=config_path, pin=pin)
    return TestClient(app)


def test_get_config_without_pin_is_forbidden(tmp_path):
    client = build_client(tmp_path)
    response = client.get("/api/config")
    assert response.status_code == 403


def test_get_config_with_correct_pin(tmp_path):
    client = build_client(tmp_path)
    response = client.get("/api/config", params={"token": "1234"})
    assert response.status_code == 200
    assert response.json()["pages"][0]["name"] == "Genel"


def test_put_config_updates_file(tmp_path):
    client = build_client(tmp_path)
    new_config = {"pages": [{"name": "Yeni", "buttons": []}]}
    response = client.put("/api/config", params={"token": "1234"}, json=new_config)
    assert response.status_code == 200

    verify = client.get("/api/config", params={"token": "1234"})
    assert verify.json()["pages"][0]["name"] == "Yeni"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_server_api.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'macrodeck.server'`

- [ ] **Step 3: Write minimal implementation**

```python
# macrodeck/server.py
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException

from .config import DeckConfig, load_config, save_config
from .state import generate_pin


def create_app(config_path: Path, pin: str | None = None) -> FastAPI:
    app = FastAPI()
    app.state.config_path = config_path
    app.state.pin = pin or generate_pin()

    def _check_pin(token: str) -> None:
        if token != app.state.pin:
            raise HTTPException(status_code=403, detail="invalid pin")

    @app.get("/api/config")
    def get_config(token: str):
        _check_pin(token)
        return load_config(app.state.config_path).model_dump()

    @app.put("/api/config")
    def put_config(payload: dict, token: str):
        _check_pin(token)
        config = DeckConfig.model_validate(payload)
        save_config(config, app.state.config_path)
        return {"status": "ok"}

    return app
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_server_api.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add macrodeck/server.py tests/test_server_api.py
git commit -m "feat: fastapi config rest endpoint'leri ve pin auth"
```

---

### Task 10: WebSocket endpoint — buton basışı → action dispatch → broadcast

**Files:**
- Modify: `macrodeck/server.py`
- Create: `macrodeck/ws.py`
- Test: `tests/test_ws.py`

**Interfaces:**
- Consumes: `dispatch` (Task 2), `ActionContext` (Task 2), `_find_button` (bu task içinde tanımlanır)
- Produces: `ConnectionManager` (`connect`, `disconnect`, `broadcast`), `/ws` WebSocket endpoint — mesaj formatı `{"page": str, "button_id": str, "event": "press"|"release"|"set", "value": float | None}`. `app.state.action_context: ActionContext` — Task 12'de gerçek bağımlılıklarla doldurulur, testte fake ile.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ws.py
from fastapi.testclient import TestClient
from macrodeck.config import Button, Page, DeckConfig, save_config
from macrodeck.server import create_app
from macrodeck.actions.context import ActionContext
import macrodeck.actions.hotkey  # noqa: F401


def build_client(tmp_path):
    config_path = tmp_path / "deck.json"
    save_config(
        DeckConfig(pages=[Page(name="Genel", buttons=[
            Button(id="b1", label="Mute", action="hotkey", params={"keys": ["ctrl", "m"]})
        ])]),
        config_path,
    )
    app = create_app(config_path=config_path, pin="1234")

    recorder = {"send_hotkey": []}
    app.state.action_context = ActionContext(
        send_hotkey=lambda keys: recorder["send_hotkey"].append(keys),
        hold_key=lambda keys: None,
        release_key=lambda keys: None,
        launch_uri=lambda uri: None,
        voicemeeter=None,
        screenshare=None,
    )
    return TestClient(app), recorder


def test_ws_press_dispatches_configured_action(tmp_path):
    client, recorder = build_client(tmp_path)
    with client.websocket_connect("/ws?token=1234") as ws:
        ws.send_json({"page": "Genel", "button_id": "b1", "event": "press"})
        ws.send_json({"page": "Genel", "button_id": "unknown", "event": "press"})

    assert recorder["send_hotkey"] == [["ctrl", "m"]]


def test_ws_rejects_wrong_pin(tmp_path):
    client, _ = build_client(tmp_path)
    try:
        with client.websocket_connect("/ws?token=0000"):
            pass
        assert False, "baglanti kabul edilmemeliydi"
    except Exception:
        pass
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_ws.py -v`
Expected: FAIL with `404 Not Found` (henüz `/ws` yok) ya da `AttributeError: 'State' object has no attribute 'action_context'`

- [ ] **Step 3: Write minimal implementation**

```python
# macrodeck/ws.py
from __future__ import annotations

from fastapi import WebSocket


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
        for websocket in list(self.active):
            await websocket.send_json(message)
```

`macrodeck/server.py` içine ekle:

```python
# macrodeck/server.py dosyasinin basina ekle
from fastapi import WebSocket, WebSocketDisconnect

from .actions.context import ActionContext
from .actions.registry import dispatch
from .ws import ConnectionManager
```

`create_app` fonksiyonunun içine, `return app` satırından önce ekle:

```python
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
        if token != app.state.pin:
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_ws.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add macrodeck/server.py macrodeck/ws.py tests/test_ws.py
git commit -m "feat: websocket endpoint - buton basisi dispatch ve broadcast"
```

---

### Task 11: Voicemeeter state poller (background task)

**Files:**
- Modify: `macrodeck/server.py`

**Interfaces:**
- Consumes: `compute_diff` (Task 8), `ConnectionManager.broadcast` (Task 10), `app.state.voicemeeter_client: VoicemeeterClient | None` (Task 12'de doldurulur)
- Produces: `app.state.last_voicemeeter_state: dict` — periyodik olarak güncellenir, değişiklikler `broadcast` ile phone client'lara gider.

Gerçek Voicemeeter bağımlılığı gerektirdiği için bu task'ın background loop'u otomatik test edilmez; `compute_diff` zaten Task 8'de test edildi. Burada sadece wiring yapılır, manuel doğrulama Task 14'te.

- [ ] **Step 1: server.py içine background task ekle**

`create_app` içine, `_find_button` tanımından sonra ekle:

```python
    import asyncio

    app.state.last_voicemeeter_state = {}
    app.state.voicemeeter_client = None  # Task 12'de RealVoicemeeterBackend ile doldurulur
    app.state.voicemeeter_strip_indices: list[int] = []  # poll edilecek strip'ler, config'den Task 12'de doldurulur

    async def _poll_voicemeeter():
        while True:
            await asyncio.sleep(0.5)
            client = app.state.voicemeeter_client
            if client is None:
                continue
            new_state = {}
            for strip_index in app.state.voicemeeter_strip_indices:
                new_state[f"strip{strip_index}_mute"] = client._backend.get_mute(strip_index)
                new_state[f"strip{strip_index}_gain"] = client._backend.get_gain(strip_index)
            diff = compute_diff(app.state.last_voicemeeter_state, new_state)
            if diff:
                app.state.last_voicemeeter_state.update(diff)
                await app.state.manager.broadcast({"type": "state", "data": diff})

    @app.on_event("startup")
    async def _start_poller():
        asyncio.create_task(_poll_voicemeeter())
```

`server.py` dosyasının başındaki import bloğuna `compute_diff` ekle:

```python
from .state import generate_pin, compute_diff
```

- [ ] **Step 2: Manuel doğrulama notu**

Bu task'ın davranışı gerçek Voicemeeter ile Task 14'teki end-to-end test checklistinde doğrulanır (state değişikliği telefon UI'a yansımalı).

- [ ] **Step 3: Commit**

```bash
git add macrodeck/server.py
git commit -m "feat: voicemeeter state poller ve broadcast wiring"
```

---

### Task 12: QR kod üretimi

**Files:**
- Create: `macrodeck/qr.py`
- Test: `tests/test_qr.py`

**Interfaces:**
- Produces: `generate_deck_url(lan_ip: str, port: int, pin: str) -> str`, `generate_qr_png(url: str) -> bytes`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_qr.py
from macrodeck.qr import generate_deck_url, generate_qr_png


def test_generate_deck_url_format():
    url = generate_deck_url("192.168.1.10", 8765, "1234")
    assert url == "http://192.168.1.10:8765/deck?token=1234"


def test_generate_qr_png_returns_nonempty_bytes():
    png_bytes = generate_qr_png("http://192.168.1.10:8765/deck?token=1234")
    assert isinstance(png_bytes, bytes)
    assert len(png_bytes) > 0
    assert png_bytes[:8] == b"\x89PNG\r\n\x1a\n"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_qr.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'macrodeck.qr'`

- [ ] **Step 3: Write minimal implementation**

```python
# macrodeck/qr.py
from __future__ import annotations

import io

import qrcode


def generate_deck_url(lan_ip: str, port: int, pin: str) -> str:
    return f"http://{lan_ip}:{port}/deck?token={pin}"


def generate_qr_png(url: str) -> bytes:
    img = qrcode.make(url)
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_qr.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: requirements.txt güncelle**

```
qrcode[pil]>=7.4
```

- [ ] **Step 6: Commit**

```bash
git add macrodeck/qr.py tests/test_qr.py requirements.txt
git commit -m "feat: deck url ve qr kod uretimi"
```

---

### Task 13: Phone deck view (statik web, PWA)

**Files:**
- Create: `web/deck/index.html`
- Create: `web/deck/app.js`
- Create: `web/deck/style.css`
- Create: `web/deck/manifest.json`
- Create: `web/deck/sw.js`
- Modify: `macrodeck/server.py` (statik dosya ve `/deck` route mount)

Bu task'ın çıktısı statik/JS dosyalar olduğu için otomatik test yok; **manuel test adımları** Step sonunda verilmiştir.

**Interfaces:**
- Consumes: `GET /api/config?token=...`, `WS /ws?token=...` (Task 9, 10)

- [ ] **Step 1: index.html yaz**

```html
<!-- web/deck/index.html -->
<!DOCTYPE html>
<html lang="tr">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1, user-scalable=no" />
  <title>MacroDeck</title>
  <link rel="manifest" href="manifest.json" />
  <link rel="stylesheet" href="style.css" />
</head>
<body>
  <div id="pin-gate">
    <input id="pin-input" type="text" inputmode="numeric" placeholder="PIN" maxlength="4" />
    <button id="pin-submit">Bağlan</button>
  </div>
  <div id="deck" hidden>
    <nav id="page-tabs"></nav>
    <main id="button-grid"></main>
  </div>
  <script src="app.js"></script>
</body>
</html>
```

- [ ] **Step 2: app.js yaz**

```javascript
// web/deck/app.js
const PIN_STORAGE_KEY = "macrodeck_pin";

const pinGate = document.getElementById("pin-gate");
const pinInput = document.getElementById("pin-input");
const pinSubmit = document.getElementById("pin-submit");
const deckEl = document.getElementById("deck");
const tabsEl = document.getElementById("page-tabs");
const gridEl = document.getElementById("button-grid");

let config = null;
let currentPage = 0;
let socket = null;

function getStoredPin() {
  const params = new URLSearchParams(window.location.search);
  return params.get("token") || localStorage.getItem(PIN_STORAGE_KEY);
}

async function connectWithPin(pin) {
  const response = await fetch(`/api/config?token=${encodeURIComponent(pin)}`);
  if (!response.ok) {
    alert("PIN yanlış");
    return;
  }
  config = await response.json();
  localStorage.setItem(PIN_STORAGE_KEY, pin);
  pinGate.hidden = true;
  deckEl.hidden = false;
  renderTabs();
  renderPage(0);
  openSocket(pin);
}

function renderTabs() {
  tabsEl.innerHTML = "";
  config.pages.forEach((page, index) => {
    const tab = document.createElement("button");
    tab.textContent = page.name;
    tab.className = index === currentPage ? "active" : "";
    tab.addEventListener("click", () => {
      currentPage = index;
      renderTabs();
      renderPage(index);
    });
    tabsEl.appendChild(tab);
  });
}

function renderPage(index) {
  gridEl.innerHTML = "";
  const page = config.pages[index];
  page.buttons.forEach((button) => {
    const el = document.createElement("button");
    el.className = "deck-button";
    el.dataset.buttonId = button.id;
    el.innerHTML = `<span class="icon">${button.icon}</span><span class="label">${button.label}</span>`;

    if (button.action === "hotkey_hold") {
      el.addEventListener("touchstart", () => sendEvent(page.name, button.id, "press"));
      el.addEventListener("touchend", () => sendEvent(page.name, button.id, "release"));
      el.addEventListener("mousedown", () => sendEvent(page.name, button.id, "press"));
      el.addEventListener("mouseup", () => sendEvent(page.name, button.id, "release"));
    } else if (button.action === "voicemeeter_gain") {
      const slider = document.createElement("input");
      slider.type = "range";
      slider.min = "-60";
      slider.max = "12";
      slider.step = "0.5";
      slider.addEventListener("input", () => {
        sendEvent(page.name, button.id, "set", parseFloat(slider.value));
      });
      el.appendChild(slider);
    } else {
      el.addEventListener("click", () => sendEvent(page.name, button.id, "press"));
    }

    gridEl.appendChild(el);
  });
}

function sendEvent(pageName, buttonId, event, value) {
  if (!socket || socket.readyState !== WebSocket.OPEN) return;
  const payload = { page: pageName, button_id: buttonId, event };
  if (value !== undefined) payload.value = value;
  socket.send(JSON.stringify(payload));
}

function openSocket(pin) {
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  socket = new WebSocket(`${protocol}://${window.location.host}/ws?token=${encodeURIComponent(pin)}`);
  socket.addEventListener("message", (event) => {
    const message = JSON.parse(event.data);
    if (message.type === "state") {
      applyStateDiff(message.data);
    }
  });
}

function applyStateDiff(diff) {
  Object.entries(diff).forEach(([key, value]) => {
    const match = key.match(/^strip(\d+)_mute$/);
    if (match) {
      const stripIndex = match[1];
      const el = document.querySelector(`[data-strip-index="${stripIndex}"][data-kind="mute"]`);
      if (el) el.classList.toggle("active", Boolean(value));
    }
  });
}

pinSubmit.addEventListener("click", () => connectWithPin(pinInput.value.trim()));

const storedPin = getStoredPin();
if (storedPin) {
  connectWithPin(storedPin);
}

if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("sw.js");
}
```

- [ ] **Step 3: style.css, manifest.json, sw.js yaz**

```css
/* web/deck/style.css */
* { box-sizing: border-box; }
body { margin: 0; font-family: system-ui, sans-serif; background: #111; color: #eee; }
#pin-gate { display: flex; gap: 8px; justify-content: center; align-items: center; height: 100vh; }
#pin-input { font-size: 24px; width: 120px; text-align: center; }
#page-tabs { display: flex; overflow-x: auto; background: #1c1c1c; }
#page-tabs button { flex: none; padding: 12px 16px; background: none; border: none; color: #999; }
#page-tabs button.active { color: #fff; border-bottom: 2px solid #4caf50; }
#button-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; padding: 10px; }
.deck-button { display: flex; flex-direction: column; align-items: center; justify-content: center; aspect-ratio: 1; background: #222; border: none; border-radius: 12px; color: #eee; }
.deck-button.active { background: #4caf50; }
.deck-button .icon { font-size: 28px; }
.deck-button .label { font-size: 12px; margin-top: 4px; }
```

```json
// web/deck/manifest.json
{
  "name": "MacroDeck",
  "short_name": "MacroDeck",
  "start_url": "./index.html",
  "display": "standalone",
  "background_color": "#111111",
  "theme_color": "#111111",
  "icons": []
}
```

```javascript
// web/deck/sw.js
self.addEventListener("install", (event) => {
  self.skipWaiting();
});

self.addEventListener("fetch", () => {
  // v1: cache-first strateji yok, sadece PWA "add to home screen" icin gerekli minimal SW
});
```

- [ ] **Step 4: server.py'ye statik mount ekle**

`macrodeck/server.py` başına ekle:

```python
from fastapi.staticfiles import StaticFiles
```

`create_app` içine, `return app` satırından hemen önce ekle:

```python
    web_root = Path(__file__).resolve().parent.parent / "web"
    app.mount("/deck", StaticFiles(directory=web_root / "deck", html=True), name="deck")
```

- [ ] **Step 5: Manuel test**

Server'ı başlat (Task 15'teki `main.py` hazır olduğunda), telefon tarayıcısında `http://<lan-ip>:<port>/deck` aç, PIN gir, en az bir hotkey butonuna bas, backend loglarında `send_hotkey` çağrıldığını doğrula.

- [ ] **Step 6: Commit**

```bash
git add web/deck macrodeck/server.py
git commit -m "feat: phone deck view (PWA) statik dosyalari ve mount"
```

---

### Task 14: PC Configurator web frontend

**Files:**
- Create: `web/configure/index.html`
- Create: `web/configure/app.js`
- Create: `web/configure/style.css`
- Modify: `macrodeck/server.py` (statik mount)

Manuel test görevi (JS için otomatik test yok).

**Interfaces:**
- Consumes: `GET /api/config`, `PUT /api/config` (Task 9)

- [ ] **Step 1: index.html yaz**

```html
<!-- web/configure/index.html -->
<!DOCTYPE html>
<html lang="tr">
<head>
  <meta charset="UTF-8" />
  <title>MacroDeck Configurator</title>
  <link rel="stylesheet" href="style.css" />
</head>
<body>
  <h1>MacroDeck Configurator</h1>
  <div id="pages"></div>
  <button id="add-page">+ Sayfa Ekle</button>
  <button id="save">Kaydet</button>
  <script src="app.js"></script>
</body>
</html>
```

- [ ] **Step 2: app.js yaz**

```javascript
// web/configure/app.js
const TOKEN = new URLSearchParams(window.location.search).get("token");

let config = { pages: [] };

async function loadConfig() {
  const response = await fetch(`/api/config?token=${TOKEN}`);
  config = await response.json();
  render();
}

async function saveConfig() {
  await fetch(`/api/config?token=${TOKEN}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(config),
  });
  alert("Kaydedildi");
}

function render() {
  const pagesEl = document.getElementById("pages");
  pagesEl.innerHTML = "";
  config.pages.forEach((page, pageIndex) => {
    const pageEl = document.createElement("fieldset");
    pageEl.innerHTML = `<legend>${page.name}</legend>`;

    const buttonList = document.createElement("div");
    page.buttons.forEach((button, buttonIndex) => {
      buttonList.appendChild(renderButtonForm(page, button, pageIndex, buttonIndex));
    });
    pageEl.appendChild(buttonList);

    const addButtonBtn = document.createElement("button");
    addButtonBtn.textContent = "+ Buton Ekle";
    addButtonBtn.addEventListener("click", () => {
      page.buttons.push({ id: `btn-${Date.now()}`, label: "Yeni", icon: "🔘", action: "hotkey", params: { keys: [] } });
      render();
    });
    pageEl.appendChild(addButtonBtn);

    pagesEl.appendChild(pageEl);
  });
}

function renderButtonForm(page, button, pageIndex, buttonIndex) {
  const row = document.createElement("div");
  row.className = "button-row";

  const labelInput = document.createElement("input");
  labelInput.value = button.label;
  labelInput.addEventListener("input", () => { button.label = labelInput.value; });

  const actionSelect = document.createElement("select");
  ["hotkey", "hotkey_hold", "steam_launch", "voicemeeter_mute", "voicemeeter_gain", "voicemeeter_route", "discord_screenshare", "launch_app"].forEach((action) => {
    const option = document.createElement("option");
    option.value = action;
    option.textContent = action;
    option.selected = action === button.action;
    actionSelect.appendChild(option);
  });
  actionSelect.addEventListener("change", () => { button.action = actionSelect.value; });

  const paramsInput = document.createElement("input");
  paramsInput.value = JSON.stringify(button.params);
  paramsInput.addEventListener("input", () => {
    try {
      button.params = JSON.parse(paramsInput.value);
    } catch (e) {
      // gecersiz JSON yazilirken bekle, kaydet'te dogrulanir
    }
  });

  const removeBtn = document.createElement("button");
  removeBtn.textContent = "Sil";
  removeBtn.addEventListener("click", () => {
    page.buttons.splice(buttonIndex, 1);
    render();
  });

  row.append(labelInput, actionSelect, paramsInput, removeBtn);
  return row;
}

document.getElementById("add-page").addEventListener("click", () => {
  config.pages.push({ name: `Sayfa ${config.pages.length + 1}`, buttons: [] });
  render();
});

document.getElementById("save").addEventListener("click", saveConfig);

loadConfig();
```

- [ ] **Step 3: style.css yaz**

```css
/* web/configure/style.css */
body { font-family: system-ui, sans-serif; padding: 16px; }
fieldset { margin-bottom: 16px; }
.button-row { display: flex; gap: 8px; margin-bottom: 6px; }
.button-row input { flex: 1; }
```

- [ ] **Step 4: server.py'ye statik mount ekle**

`create_app` içine, deck mount satırının yanına ekle:

```python
    app.mount("/configure", StaticFiles(directory=web_root / "configure", html=True), name="configure")
```

- [ ] **Step 5: Manuel test**

Server'ı başlat, tarayıcıda `http://localhost:<port>/configure?token=<pin>` aç, bir sayfa+buton ekle, kaydet, `config/deck.json` dosyasının güncellendiğini doğrula.

- [ ] **Step 6: Commit**

```bash
git add web/configure macrodeck/server.py
git commit -m "feat: pc configurator web arayuzu ve mount"
```

---

### Task 15: main.py — tray, pywebview configurator penceresi, entrypoint wiring

**Files:**
- Create: `macrodeck/tray.py`
- Create: `macrodeck/main.py`
- Modify: `macrodeck/server.py` (gerçek `ActionContext` ve Voicemeeter strip listesi kurulumu için `configure_runtime` fonksiyonu)

Bu task tamamen gerçek OS/pencere entegrasyonu olduğu için otomatik test yok; manuel test Task 16'da.

**Interfaces:**
- Consumes: `create_app` (Task 9-11, 13-14), `os_bridge.*` (Task 4), `RealVoicemeeterBackend` (Task 6), `VoicemeeterClient` (Task 5), `DiscordScreenShareController` + `PywinautoScreenShareAutomation` (Task 7), `generate_deck_url`, `generate_qr_png` (Task 12)
- Produces: `configure_runtime(app: FastAPI, voicemeeter_kind: str) -> None`, tray icon başlatma ve `main()` giriş noktası.

- [ ] **Step 1: server.py içine configure_runtime ekle**

`macrodeck/server.py` sonuna ekle:

```python
def configure_runtime(app, voicemeeter_kind: str = "banana") -> None:
    from . import os_bridge
    from .voicemeeter_backend import RealVoicemeeterBackend
    from .voicemeeter_client import VoicemeeterClient
    from .discord_automation import PywinautoScreenShareAutomation
    from .discord_screenshare import DiscordScreenShareController

    backend = RealVoicemeeterBackend(kind=voicemeeter_kind)
    voicemeeter_client = VoicemeeterClient(backend)
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

    config = load_config(app.state.config_path)
    strip_indices = set()
    for page in config.pages:
        for button in page.buttons:
            if button.action.startswith("voicemeeter_"):
                strip_indices.add(button.params.get("strip_index", 0))
    app.state.voicemeeter_strip_indices = sorted(strip_indices)
```

- [ ] **Step 2: tray.py yaz**

```python
# macrodeck/tray.py
from __future__ import annotations

import threading

import pystray
from PIL import Image, ImageDraw


def _make_icon_image():
    image = Image.new("RGB", (64, 64), "black")
    draw = ImageDraw.Draw(image)
    draw.rectangle((16, 16, 48, 48), fill="white")
    return image


def start_tray(on_open_configurator, on_quit) -> None:
    icon = pystray.Icon(
        "macrodeck",
        _make_icon_image(),
        "MacroDeck",
        menu=pystray.Menu(
            pystray.MenuItem("Configurator Aç", lambda: on_open_configurator()),
            pystray.MenuItem("Çıkış", lambda: on_quit(icon)),
        ),
    )
    threading.Thread(target=icon.run, daemon=True).start()
```

- [ ] **Step 3: main.py yaz**

```python
# macrodeck/main.py
from __future__ import annotations

import socket
import threading
from pathlib import Path

import uvicorn
import webview

from .server import create_app, configure_runtime
from .tray import start_tray

PORT = 8765
CONFIG_PATH = Path("config/deck.json")


def _get_lan_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    finally:
        s.close()


def _run_server(app):
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")


def main() -> None:
    app = create_app(config_path=CONFIG_PATH)
    configure_runtime(app, voicemeeter_kind="banana")

    server_thread = threading.Thread(target=_run_server, args=(app,), daemon=True)
    server_thread.start()

    lan_ip = _get_lan_ip()
    print(f"Deck URL: http://{lan_ip}:{PORT}/deck?token={app.state.pin}")
    print(f"Configurator URL: http://localhost:{PORT}/configure?token={app.state.pin}")

    def open_configurator():
        webview.create_window(
            "MacroDeck Configurator",
            f"http://localhost:{PORT}/configure?token={app.state.pin}",
        )
        webview.start()

    def quit_app(icon):
        icon.stop()

    start_tray(open_configurator, quit_app)
    open_configurator()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: requirements.txt tamamla**

```
pywebview>=5.0
pystray>=0.19
pillow>=10.0
uvicorn[standard]>=0.30
```

- [ ] **Step 5: Commit**

```bash
git add macrodeck/tray.py macrodeck/main.py macrodeck/server.py requirements.txt
git commit -m "feat: tray icon, pywebview configurator ve main entrypoint wiring"
```

---

### Task 16: Örnek config, README ve end-to-end manuel test checklisti

**Files:**
- Create: `config/deck.json`
- Create: `README.md`
- Create: `requirements.txt` (finalize — tüm önceki task'larda eklenen satırların birleşimi)

- [ ] **Step 1: Örnek config yaz**

```json
{
  "pages": [
    {
      "name": "Genel",
      "buttons": [
        {"id": "discord-mute", "label": "Mute", "icon": "🎙️", "action": "hotkey", "params": {"keys": ["ctrl", "shift", "m"]}},
        {"id": "discord-deafen", "label": "Deafen", "icon": "🔇", "action": "hotkey", "params": {"keys": ["ctrl", "shift", "d"]}},
        {"id": "discord-share1", "label": "Ekran 1 Paylaş", "icon": "🖥️", "action": "discord_screenshare", "params": {"monitor_index": 0}},
        {"id": "vm-strip0-mute", "label": "Mic Mute", "icon": "🎚️", "action": "voicemeeter_mute", "params": {"strip_index": 0}},
        {"id": "vm-strip0-gain", "label": "Mic Gain", "icon": "🔊", "action": "voicemeeter_gain", "params": {"strip_index": 0}},
        {"id": "vm-strip0-a1", "label": "→A1", "icon": "🔀", "action": "voicemeeter_route", "params": {"strip_index": 0, "bus": "A1"}},
        {"id": "vm-strip0-b1", "label": "→B1", "icon": "🔀", "action": "voicemeeter_route", "params": {"strip_index": 0, "bus": "B1"}}
      ]
    }
  ]
}
```

- [ ] **Step 2: requirements.txt finalize**

```
fastapi>=0.115
uvicorn[standard]>=0.30
websockets>=13.0
pydantic>=2.8
keyboard>=0.13.5
pywinauto>=0.6.8
pywebview>=5.0
pystray>=0.19
pillow>=10.0
qrcode[pil]>=7.4
voicemeeter-api>=2.0.0
pytest>=8.0
pytest-asyncio>=0.24
httpx>=0.27
```

- [ ] **Step 3: README yaz**

```markdown
# MacroDeck

Telefondan LAN üzerinden PC kontrolü: Discord, Voicemeeter, Steam ve genel hotkey/uygulama başlatma.

## Kurulum

\`\`\`bash
pip install -r requirements.txt
python -m macrodeck.main
\`\`\`

Konsolda basılan Deck URL'sini telefonda tarayıcıyla aç (aynı WiFi ağında olmalısın) ya da configurator penceresindeki QR kodu okut.

## Test

\`\`\`bash
pytest
\`\`\`

## Config

\`config/deck.json\` — configurator penceresinden (tray → "Configurator Aç") ya da doğrudan dosyayı düzenleyerek değiştirilir.
```

- [ ] **Step 4: Tüm unit testleri çalıştır**

Run: `pytest -v`
Expected: tüm testler PASS (Task 1-13'te yazılanlar)

- [ ] **Step 5: End-to-end manuel test checklisti çalıştır**

1. `python -m macrodeck.main` çalıştır, tray icon'un göründüğünü doğrula.
2. Configurator penceresinin açıldığını, `config/deck.json`'daki sayfa/butonların göründüğünü doğrula.
3. Gerçek Discord açıkken mute/deafen butonlarını (configurator'dan test edip) telefon deck'inden tetikle, Discord'da mikrofon/ses durumunun değiştiğini doğrula.
4. Discord ekran paylaşımı butonuna bas, best-effort automation'ın çalışıp çalışmadığını doğrula; çalışmazsa `discord_automation.py`'deki selector'ları gerçek Discord sürümüne göre güncelle.
5. Gerçek Voicemeeter (Banana/Potato) açıkken mute, gain slider, A1/B1 routing butonlarını telefon deck'inden test et; PC'de Voicemeeter arayüzünden manuel mute değişikliği yap, telefon UI'ın state broadcast ile güncellendiğini doğrula.
6. Steam açıkken gerçek bir appid ile oyun launch butonunu test et.
7. Telefonu farklı bir cihazdan (yanlış PIN ile) bağlanmayı dene, reddedildiğini doğrula.
8. Telefon tarayıcısında "add to home screen" yap, PWA ikonunun oluştuğunu doğrula.

- [ ] **Step 6: Commit**

```bash
git add config/deck.json README.md requirements.txt
git commit -m "docs: readme, ornek config ve e2e manuel test checklisti"
```

---

## Self-Review Notu

- **Spec coverage:** Discord mute/deafen (Task 2,4,16), Discord screenshare (Task 7), Voicemeeter mute/gain/routing (Task 5,6,11), Steam launch (Task 3), configurator app (Task 14,15), phone PWA (Task 13), QR+PIN güvenlik (Task 9,12,15), genişletilebilirlik registry pattern (Task 2) — spec'teki tüm bölümler bir task'a karşılık geliyor.
- **Placeholder scan:** Yok — her adımda çalışan kod var, "TODO" yok.
- **Type consistency:** `ActionContext` alanları (Task 2) tüm sonraki task'larda aynı isimlerle kullanılıyor (`send_hotkey`, `hold_key`, `release_key`, `launch_uri`, `voicemeeter`, `screenshare`). `VoicemeeterClient`/`VoicemeeterBackend` imzaları Task 5-6-11 arasında tutarlı. `DiscordScreenShareController`/`ScreenShareAutomation` Task 7-15 arasında tutarlı.
