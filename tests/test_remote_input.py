from macrodeck.remote_input import handle
from tests.test_ws import build_client


class Rec:
    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        return lambda *a: self.calls.append((name, *a))


def test_handle_validates_and_clamps():
    r = Rec()
    handle({"kind": "move", "dx": 9999, "dy": -5.7}, r)
    handle({"kind": "click", "button": "evil"}, r)
    handle({"kind": "key", "key": "f4"}, r)
    handle({"kind": "click"}, r)
    handle({"kind": "text", "text": "ğüş"}, r)
    handle({"kind": "button", "button": "left", "down": True}, r)
    handle({"kind": "button", "button": "left", "down": "yes"}, r)
    assert r.calls == [
        ("mouse_move", 300, -5), ("mouse_click", "left"), ("type_text", "ğüş"), ("mouse_button", "left", True),
    ]


def test_ws_input_goes_to_handler_and_bad_input_keeps_socket(tmp_path):
    client, _ = build_client(tmp_path)
    got = []
    client.app.state.input_handler = got.append
    with client.websocket_connect("/ws?token=1234") as ws:
        ws.send_json({"type": "input", "kind": "move", "dx": 1, "dy": 2})
        ws.send_json({"type": "input", "kind": "scroll", "dy": 1})
    # bağlantı kapanırken sunucu basılı fare tuşunu bırakır (son mesaj)
    assert [m["kind"] for m in got] == ["move", "scroll", "button"]


class FakeClip:
    def __init__(self, text=""):
        self.text, self.seq = text, 0

    def clipboard_seq(self):
        return self.seq

    def get_clipboard_text(self):
        return self.text

    def set_clipboard_text(self, text):
        self.text, self.seq = text, self.seq + 1


def test_clipboard_pc_to_phone_on_connect_and_phone_to_pc(tmp_path):
    client, _ = build_client(tmp_path)
    clip = FakeClip("pcden gelen")
    client.app.state.clipboard = clip
    with client.websocket_connect("/ws?token=1234") as ws:
        assert ws.receive_json() == {"type": "clipboard", "text": "pcden gelen"}
        ws.send_json({"type": "clipboard", "text": "telefondan"})
        ws.send_json({"type": "clipboard", "text": 5})  # gecersiz: yok sayilmali
        ws.send_json({"type": "input", "kind": "scroll", "dy": 1})  # soket hala canli
    assert clip.text == "telefondan"


def test_screen_stream_sends_frames_and_rejects_bad_pin(tmp_path):
    client, _ = build_client(tmp_path)
    client.app.state.screen_grab = lambda monitor=0, width=0: b"jpegbytes"
    with client.websocket_connect("/ws/screen?token=1234") as ws:
        assert ws.receive_bytes() == b"jpegbytes"
        assert ws.receive_bytes() == b"jpegbytes"
    import pytest
    from starlette.websockets import WebSocketDisconnect
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws/screen?token=0000"):
            pass


def test_grab_jpeg_real_screen_is_jpeg():
    from macrodeck.screen import grab_jpeg, monitors
    assert len(monitors()) >= 1
    for i in range(len(monitors())):
        data = grab_jpeg(i, 800)
        assert data[:2] == b"\xff\xd8" and len(data) < 400_000
    assert grab_jpeg(99)[:2] == b"\xff\xd8"  # gecersiz indeks ana monitore duser


def test_monitors_endpoint_and_stream_params(tmp_path):
    client, _ = build_client(tmp_path)
    client.app.state.monitors = lambda: [(0, 0, 1920, 1080), (1920, 0, 3840, 1200)]
    got = []
    client.app.state.screen_grab = lambda monitor=0, width=0: got.append((monitor, width)) or b"x"
    assert client.get("/api/monitors?token=1234").json()["monitors"] == [
        {"index": 0, "width": 1920, "height": 1080, "primary": True},
        {"index": 1, "width": 1920, "height": 1200, "primary": False},
    ]
    assert client.get("/api/monitors?token=0000").status_code == 403
    with client.websocket_connect("/ws/screen?token=1234&monitor=1&width=1600") as ws:
        ws.receive_bytes()
    assert got[0] == (1, 1600)


def test_files_upload_list_download_and_traversal(tmp_path):
    client, _ = build_client(tmp_path)
    client.app.state.files_dir = tmp_path / "dosyalar"
    q = "?token=1234"

    r = client.post("/api/files/upload" + q, params={"token": "1234", "name": "..\\..\\evil:x.txt"}, content=b"merhaba")
    assert r.status_code == 200
    r2 = client.post("/api/files/upload" + q, params={"token": "1234", "name": "evil:x.txt"}, content=b"ikinci")
    inbox = tmp_path / "dosyalar" / "Gelen"
    assert sorted(p.name for p in inbox.iterdir()) == ["evil_x (1).txt", "evil_x.txt"]
    assert (inbox / "evil_x.txt").read_bytes() == b"merhaba"
    assert client.post("/api/files/upload?token=0000&name=a.txt", content=b"x").status_code == 403

    outbox = tmp_path / "dosyalar" / "Giden"
    outbox.mkdir(parents=True, exist_ok=True)
    (outbox / "rapor.pdf").write_bytes(b"pdfdata")
    assert client.get("/api/files" + q).json()["files"] == [{"name": "rapor.pdf", "size": 7}]
    assert client.get("/api/files/rapor.pdf" + q).content == b"pdfdata"
    (tmp_path / "dosyalar" / "gizli.txt").write_text("x")
    assert client.get("/api/files/..%2Fgizli.txt" + q).status_code == 404
    assert client.get("/api/files/rapor.pdf?token=0000").status_code == 403


def test_safe_name_reserved_and_empty():
    from macrodeck.files import safe_name
    assert safe_name("CON.txt") == "_CON.txt"
    assert safe_name("") == "dosya"
    assert safe_name("a/b\\c.png") == "c.png"


def test_upload_rejects_oversize_before_reading_body(tmp_path, monkeypatch):
    import macrodeck.server as srv
    client, _ = build_client(tmp_path)
    client.app.state.files_dir = tmp_path / "dosyalar"
    # sinir cok kucuk app'te degil kodda sabit; Content-Length ile 2GB+ iddia et
    r = client.post("/api/files/upload?token=1234&name=a.bin", content=b"x",
                    headers={"content-length": str(3 * 1024**3)})
    assert r.status_code in (400, 413)
    assert not (tmp_path / "dosyalar" / "Gelen").exists() or not any((tmp_path / "dosyalar" / "Gelen").iterdir())


def test_ws_disconnect_releases_held_mouse_button(tmp_path):
    client, _ = build_client(tmp_path)
    got = []
    client.app.state.input_handler = got.append
    with client.websocket_connect("/ws?token=1234") as ws:
        ws.send_json({"type": "input", "kind": "button", "button": "left", "down": True})
    assert got[0]["down"] is True
    assert got[-1] == {"type": "input", "kind": "button", "button": "left", "down": False}


def test_sources_monitors_not_shadowed(tmp_path):
    # /api/monitors rotasi, sources.list_monitors'u golgelemisti -> 500
    client, _ = build_client(tmp_path)
    assert client.get("/api/sources/monitors?token=1234").status_code == 200


def test_start_menu_apps_endpoint(tmp_path):
    client, _ = build_client(tmp_path)
    r = client.get("/api/sources/apps?token=1234")
    assert r.status_code == 200
    apps = r.json()
    assert apps and all(a["path"].lower().endswith(".lnk") for a in apps)
    assert client.get("/api/sources/apps?token=0000").status_code == 403


def test_outbox_drop_inbox_list_delete(tmp_path):
    client, _ = build_client(tmp_path)
    client.app.state.files_dir = tmp_path / "dosyalar"
    q = "?token=1234"
    assert client.post("/api/outbox/upload?token=1234&name=a.txt", content=b"pc").status_code == 200
    assert [f["name"] for f in client.get("/api/files" + q).json()["files"]] == ["a.txt"]  # telefon listesi
    assert client.post("/api/files/upload?token=1234&name=b.txt", content=b"tel").status_code == 200
    assert [f["name"] for f in client.get("/api/inbox" + q).json()["files"]] == ["b.txt"]
    assert client.get("/api/inbox/b.txt" + q).content == b"tel"
    assert client.get("/api/inbox/..%5Ca.txt" + q).status_code == 404
    assert client.delete("/api/inbox/b.txt" + q).status_code == 200
    assert client.delete("/api/outbox/a.txt" + q).status_code == 200
    assert client.delete("/api/outbox/a.txt?token=0000").status_code == 403
