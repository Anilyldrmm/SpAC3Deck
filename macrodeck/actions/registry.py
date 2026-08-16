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
