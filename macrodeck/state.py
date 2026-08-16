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
