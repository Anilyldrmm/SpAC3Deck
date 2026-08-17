"""configure_runtime'in eksik entegrasyonlara dayanikliligi."""

import macrodeck.voicemeeter_backend as voicemeeter_backend
from macrodeck.config import Button, DeckConfig, Page, save_config
from macrodeck.server import configure_runtime, create_app


def _build_app(tmp_path):
    config_path = tmp_path / "deck.json"
    save_config(
        DeckConfig(pages=[Page(name="Ses", buttons=[
            Button(id="m", label="Mic", action="voicemeeter_mute", params={"strip_index": 2}),
            Button(id="h", label="Hot", action="hotkey", params={"keys": ["ctrl", "m"]}),
        ])]),
        config_path,
    )
    return create_app(config_path=config_path, pin="1234")


class _FakeBackend:
    def __init__(self, kind="banana"):
        self.kind = kind
        self.logged_out = False

    def logout(self):
        self.logged_out = True


def test_configure_runtime_survives_missing_voicemeeter(tmp_path, monkeypatch):
    """Voicemeeter kurulu degilse uygulama yine de ayaga kalkmali."""
    def _boom(kind="banana"):
        raise RuntimeError("voicemeeter kurulu degil")

    monkeypatch.setattr(voicemeeter_backend, "RealVoicemeeterBackend", _boom)

    app = _build_app(tmp_path)
    configure_runtime(app)  # exception atmamali

    assert app.state.voicemeeter_client is None
    assert app.state.voicemeeter_backend is None
    assert app.state.action_context.voicemeeter is None
    # voicemeeter disi entegrasyonlar calisir durumda
    assert callable(app.state.action_context.send_hotkey)
    assert app.state.action_context.screenshare is not None


def test_configure_runtime_wires_voicemeeter_and_strip_indices(tmp_path, monkeypatch):
    monkeypatch.setattr(voicemeeter_backend, "RealVoicemeeterBackend", _FakeBackend)

    app = _build_app(tmp_path)
    configure_runtime(app)

    assert app.state.voicemeeter_client is not None
    assert isinstance(app.state.voicemeeter_backend, _FakeBackend)
    assert app.state.voicemeeter_strip_indices == [2]
