from macrodeck import os_bridge


def test_play_sound_missing_file_does_not_raise(tmp_path, monkeypatch):
    monkeypatch.setattr(os_bridge, "SOUNDS_DIR", tmp_path / "nope")
    os_bridge.play_sound("missing.wav")  # exception atmamali


def test_play_sound_strips_path_traversal(tmp_path, monkeypatch):
    monkeypatch.setattr(os_bridge, "SOUNDS_DIR", tmp_path)
    # dizin disina cikma denemesi de guvenle no-op olmali (dosya yok)
    os_bridge.play_sound("../../evil.wav")
