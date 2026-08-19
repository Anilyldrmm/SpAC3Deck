from fastapi.testclient import TestClient
from macrodeck.config import Button, Page, DeckConfig, save_config
from macrodeck.server import create_app, compute_strip_indices, compute_bus_indices, configure_runtime


def build_client(tmp_path, pin="1234", lan_ip=None, port=8765):
    config_path = tmp_path / "deck.json"
    save_config(
        DeckConfig(pages=[Page(name="Genel", buttons=[
            Button(id="b1", label="Mute", action="hotkey", params={"keys": ["ctrl", "m"]})
        ])]),
        config_path,
    )
    app = create_app(config_path=config_path, pin=pin, lan_ip=lan_ip, port=port)
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


def test_put_config_invalid_payload_returns_422(tmp_path):
    """Gecersiz config 500 degil, anlamli 422 donmeli."""
    client = build_client(tmp_path)
    response = client.put(
        "/api/config",
        params={"token": "1234"},
        json={"pages": [{"buttons": [{"id": "b1"}]}]},  # name ve label/action eksik
    )
    assert response.status_code == 422
    assert response.json()["detail"]


def test_put_config_recomputes_voicemeeter_strip_indices(tmp_path):
    """Configurator'dan eklenen yeni strip restart beklemeden poll edilmeli."""
    client = build_client(tmp_path)
    app = client.app
    assert app.state.voicemeeter_strip_indices == []

    response = client.put(
        "/api/config",
        params={"token": "1234"},
        json={
            "pages": [
                {
                    "name": "Ses",
                    "buttons": [
                        {"id": "m3", "label": "Mic", "action": "voicemeeter_mute",
                         "params": {"strip_index": 3}},
                        {"id": "g5", "label": "Gain", "action": "voicemeeter_gain",
                         "params": {"strip_index": 5}},
                    ],
                }
            ]
        },
    )
    assert response.status_code == 200
    assert app.state.voicemeeter_strip_indices == [3, 5]


class _FakeKeyboardForMediaKeys:
    def __init__(self):
        self.registered = {}
        self._next_id = 0

    def add_hotkey(self, key, callback, suppress=False):
        self._next_id += 1
        self.registered[self._next_id] = key
        return self._next_id

    def remove_hotkey(self, hook_id):
        del self.registered[hook_id]


def test_put_config_toggles_media_key_listener_live(tmp_path):
    """enabled ayari degisince restart beklemeden hook'lar kurulup kaldirilmali."""
    client = build_client(tmp_path)
    app = client.app
    fake_keyboard = _FakeKeyboardForMediaKeys()
    configure_runtime(app, media_key_keyboard_module=fake_keyboard)
    assert fake_keyboard.registered == {}  # varsayilan enabled=False

    enable_response = client.put(
        "/api/config",
        params={"token": "1234"},
        json={
            "pages": [],
            "media_keys": {"enabled": True, "target_type": "strip", "target_index": 0, "step_db": 3.0},
        },
    )
    assert enable_response.status_code == 200
    assert set(fake_keyboard.registered.values()) == {"volume up", "volume down", "volume mute"}

    disable_response = client.put(
        "/api/config",
        params={"token": "1234"},
        json={
            "pages": [],
            "media_keys": {"enabled": False, "target_type": "strip", "target_index": 0, "step_db": 3.0},
        },
    )
    assert disable_response.status_code == 200
    assert fake_keyboard.registered == {}


def test_rest_rate_limits_failed_pin_attempts(tmp_path):
    """REST tarafi da brute-force'a karsi kilitlenmeli (WS limiti ile ayni sayac)."""
    client = build_client(tmp_path)
    app = client.app
    app.state.rate_limiter.threshold = 5

    for _ in range(5):
        assert client.get("/api/config", params={"token": "0000"}).status_code == 403

    blocked = client.get("/api/config", params={"token": "0000"})
    assert blocked.status_code == 429
    assert blocked.headers.get("Retry-After")

    # dogru PIN bile kilit suresince reddedilir
    assert client.get("/api/config", params={"token": "1234"}).status_code == 429
    assert client.put(
        "/api/config", params={"token": "1234"}, json={"pages": []}
    ).status_code == 429


def test_rest_and_ws_share_the_same_failed_attempt_counter(tmp_path):
    """REST uzerinden yapilan denemeler WS limitini de tuketmeli."""
    from starlette.websockets import WebSocketDisconnect
    import pytest

    client = build_client(tmp_path)
    client.app.state.rate_limiter.threshold = 3

    for _ in range(3):
        assert client.get("/api/config", params={"token": "0000"}).status_code == 403

    with pytest.raises(WebSocketDisconnect) as excinfo:
        with client.websocket_connect("/ws?token=1234"):
            pass
    assert excinfo.value.code == 4429


def test_rest_rejects_disallowed_origin(tmp_path):
    client = build_client(tmp_path, lan_ip="192.168.1.10")
    response = client.get(
        "/api/config",
        params={"token": "1234"},
        headers={"Origin": "http://evil.com", "Host": "evil.com"},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "origin not allowed"


def test_rest_accepts_allowlisted_origin(tmp_path):
    client = build_client(tmp_path, lan_ip="192.168.1.10", port=8765)
    response = client.get(
        "/api/config",
        params={"token": "1234"},
        headers={"Origin": "http://192.168.1.10:8765"},
    )
    assert response.status_code == 200


def test_qr_endpoint_requires_pin(tmp_path):
    client = build_client(tmp_path)
    assert client.get("/api/qr").status_code == 403
    assert client.get("/api/qr", params={"token": "0000"}).status_code == 403


def test_qr_endpoint_returns_png_for_lan_url(tmp_path):
    client = build_client(tmp_path, lan_ip="192.168.1.10", port=8765)
    response = client.get("/api/qr", params={"token": "1234"})
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content[:8] == b"\x89PNG\r\n\x1a\n"


def test_activate_endpoint_requires_pin_and_calls_callback(tmp_path):
    client = build_client(tmp_path)
    calls = []
    client.app.state.activate_callback = lambda: calls.append(1)

    assert client.post("/api/activate").status_code == 403
    assert calls == []

    response = client.post("/api/activate", params={"token": "1234"})
    assert response.status_code == 200
    assert calls == [1]


def test_activate_endpoint_without_callback_still_ok(tmp_path):
    client = build_client(tmp_path)
    response = client.post("/api/activate", params={"token": "1234"})
    assert response.status_code == 200


def test_compute_strip_indices_dedupes_and_sorts():
    config = DeckConfig(pages=[
        Page(name="A", buttons=[
            Button(id="1", label="a", action="voicemeeter_mute", params={"strip_index": 4}),
            Button(id="2", label="b", action="voicemeeter_gain", params={"strip_index": 4}),
            Button(id="3", label="c", action="voicemeeter_route", params={"strip_index": 1}),
            Button(id="4", label="d", action="hotkey", params={"keys": ["a"]}),
            Button(id="5", label="e", action="voicemeeter_mute", params={}),
        ]),
    ])
    assert compute_strip_indices(config) == [0, 1, 4]


def test_compute_bus_indices_dedupes_and_sorts():
    config = DeckConfig(pages=[
        Page(name="A", buttons=[
            Button(id="1", label="a", action="voicemeeter_bus_mute", params={"bus_index": 2}),
            Button(id="2", label="b", action="voicemeeter_bus_gain", params={"bus_index": 0}),
            Button(id="3", label="c", action="voicemeeter_mute", params={"strip_index": 5}),
        ]),
    ])
    assert compute_bus_indices(config) == [0, 2]


def test_get_sounds_empty_when_no_uploads(tmp_path):
    client = build_client(tmp_path)
    response = client.get("/api/sources/sounds", params={"token": "1234"})
    assert response.status_code == 200
    assert response.json() == []


def test_upload_sound_rejects_non_wav(tmp_path):
    client = build_client(tmp_path)
    response = client.post(
        "/api/sound/upload",
        params={"token": "1234"},
        files={"file": ("test.mp3", b"fake", "audio/mpeg")},
    )
    assert response.status_code == 415


def test_upload_and_list_sound(tmp_path):
    client = build_client(tmp_path)
    upload = client.post(
        "/api/sound/upload",
        params={"token": "1234"},
        files={"file": ("boom.wav", b"RIFF....WAVEfmt ", "audio/wav")},
    )
    assert upload.status_code == 200
    assert upload.json()["file"].endswith(".wav")

    listing = client.get("/api/sources/sounds", params={"token": "1234"})
    assert listing.status_code == 200
    assert len(listing.json()) == 1
    assert listing.json()[0]["file"] == upload.json()["file"]
