from macrodeck.state import compute_diff, generate_pin, load_or_create_pin


def test_generate_pin_is_four_digits():
    pin = generate_pin()
    assert len(pin) == 4
    assert pin.isdigit()


def test_load_or_create_pin_persists_across_calls(tmp_path):
    path = tmp_path / "pin.txt"
    first = load_or_create_pin(path)
    second = load_or_create_pin(path)
    assert first == second
    assert path.read_text(encoding="utf-8").strip() == first


def test_load_or_create_pin_creates_valid_pin(tmp_path):
    pin = load_or_create_pin(tmp_path / "pin.txt")
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
