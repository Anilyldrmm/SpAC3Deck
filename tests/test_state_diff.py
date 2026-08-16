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
