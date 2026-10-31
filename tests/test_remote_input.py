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
