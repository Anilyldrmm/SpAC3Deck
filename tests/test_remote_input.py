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
    assert r.calls == [("mouse_move", 300, -5), ("mouse_click", "left"), ("type_text", "ğüş")]


def test_ws_input_goes_to_handler_and_bad_input_keeps_socket(tmp_path):
    client, _ = build_client(tmp_path)
    got = []
    client.app.state.input_handler = got.append
    with client.websocket_connect("/ws?token=1234") as ws:
        ws.send_json({"type": "input", "kind": "move", "dx": 1, "dy": 2})
        ws.send_json({"type": "input", "kind": "scroll", "dy": 1})
    assert [m["kind"] for m in got] == ["move", "scroll"]


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
    client.app.state.screen_grab = lambda: b"jpegbytes"
    with client.websocket_connect("/ws/screen?token=1234") as ws:
        assert ws.receive_bytes() == b"jpegbytes"
        assert ws.receive_bytes() == b"jpegbytes"
    import pytest
    from starlette.websockets import WebSocketDisconnect
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws/screen?token=0000"):
            pass


def test_grab_jpeg_real_screen_is_jpeg():
    from macrodeck.screen import grab_jpeg
    data = grab_jpeg()
    assert data[:2] == b"\xff\xd8" and len(data) < 400_000
