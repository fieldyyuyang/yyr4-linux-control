"""Bidirectional JSON ↔ Action conversion for CLI and GUI input."""

from __future__ import annotations
from typing import List

from yyr4_linux_control.control.actions import (
    Action, HotkeyAction, TextAction, CommandAction,
    DelayAction, MacroAction, NoOpAction, DebugLogAction,
    SetLayerAction, NextLayerAction, PreviousLayerAction, SetProfileAction,
)
from yyr4_linux_control.control.models import LayerId


_MAX_SPEC_DEPTH = 10


def parse_spec(value, path="action", *, _depth=0):
    """Parse a JSON-compatible dict into an Action object.

    Raises *ValueError* with a path-qualified message on failure.
    """
    if not isinstance(value, dict):
        raise ValueError(f"{path}: must be a JSON object, got {type(value).__name__}")
    atype = value.get("type")
    if atype is None:
        raise ValueError(f"{path}: missing required field 'type'")
    if not isinstance(atype, str):
        raise ValueError(f"{path}.type: must be a string")

    extra = set(value.keys()) - _ALLOWED_FIELDS.get(atype, set())
    if extra:
        raise ValueError(f"{path}: unknown field(s): {', '.join(sorted(extra))}")

    return _dispatch(atype, value, path, _depth)


def action_to_spec(action: Action) -> dict:
    """Convert an Action to a JSON-serializable dict."""
    if isinstance(action, HotkeyAction):
        return {"type": "hotkey", "keys": list(action.keys)}
    if isinstance(action, TextAction):
        return {"type": "text", "value": action.value}
    if isinstance(action, CommandAction):
        result = {"type": "command", "argv": list(action.argv)}
        if action.timeout_seconds:
            result["timeout_seconds"] = action.timeout_seconds
        return result
    if isinstance(action, DelayAction):
        return {"type": "delay", "milliseconds": action.milliseconds}
    if isinstance(action, MacroAction):
        return {"type": "macro", "steps": [action_to_spec(s) for s in action.steps]}
    if isinstance(action, NoOpAction):
        return {"type": "noop"}
    if isinstance(action, DebugLogAction):
        return {"type": "debug_log", "message": action.message}
    if isinstance(action, SetLayerAction):
        return {"type": "set_layer", "layer": action.layer}
    if isinstance(action, NextLayerAction):
        return {"type": "next_layer"}
    if isinstance(action, PreviousLayerAction):
        return {"type": "previous_layer"}
    if isinstance(action, SetProfileAction):
        return {"type": "set_profile", "profile": action.profile}
    return {"type": "UNKNOWN"}


# ── Internal dispatch ─────────────────────────────────────────────

_ALLOWED_FIELDS = {
    "hotkey": {"type", "keys"},
    "text": {"type", "value"},
    "command": {"type", "argv", "timeout_seconds"},
    "delay": {"type", "milliseconds"},
    "macro": {"type", "steps"},
    "noop": {"type"},
    "debug_log": {"type", "message"},
    "set_layer": {"type", "layer"},
    "next_layer": {"type"},
    "previous_layer": {"type"},
    "set_profile": {"type", "profile"},
}

_STRING_FIELDS = {
    "text": ("value",),
    "debug_log": ("message",),
    "set_layer": ("layer",),
    "set_profile": ("profile",),
}


def _dispatch(atype, value, path, depth):
    if atype == "hotkey":
        return _parse_hotkey(value, path)
    if atype == "text":
        return _parse_text(value, path)
    if atype == "command":
        return _parse_command(value, path)
    if atype == "delay":
        return _parse_delay(value, path)
    if atype == "macro":
        return _parse_macro(value, path, depth)
    if atype == "noop":
        return NoOpAction()
    if atype == "debug_log":
        return _parse_debug_log(value, path)
    if atype == "set_layer":
        return _parse_set_layer(value, path)
    if atype == "next_layer":
        return NextLayerAction()
    if atype == "previous_layer":
        return PreviousLayerAction()
    if atype == "set_profile":
        return _parse_set_profile(value, path)
    raise ValueError(f"{path}: unknown action type: {atype!r}")


def _str_field(value, path, name):
    v = value.get(name)
    if not isinstance(v, str):
        raise ValueError(f"{path}.{name}: must be a string")
    return v


def _parse_hotkey(value, path):
    keys = value.get("keys")
    if not isinstance(keys, list) or len(keys) == 0:
        raise ValueError(f"{path}.keys: must be a non-empty array of strings")
    for i, k in enumerate(keys):
        if not isinstance(k, str) or not k:
            raise ValueError(f"{path}.keys[{i}]: must be a non-empty string")
    return HotkeyAction(tuple(keys))


def _parse_text(value, path):
    v = value.get("value")
    if not isinstance(v, str):
        raise ValueError(f"{path}.value: must be a string")
    return TextAction(v)


def _parse_command(value, path):
    argv = value.get("argv")
    if not isinstance(argv, list) or len(argv) == 0:
        raise ValueError(f"{path}.argv: must be a non-empty array of strings")
    for i, a in enumerate(argv):
        if not isinstance(a, str):
            raise ValueError(f"{path}.argv[{i}]: must be a string")
    timeout = value.get("timeout_seconds")
    if timeout is not None and not isinstance(timeout, (int, float)):
        raise ValueError(f"{path}.timeout_seconds: must be a number")
    return CommandAction(tuple(argv), timeout_seconds=int(timeout) if timeout else None)


def _parse_delay(value, path):
    ms = value.get("milliseconds")
    if not isinstance(ms, (int, float)):
        raise ValueError(f"{path}.milliseconds: must be a number")
    if ms < 0:
        raise ValueError(f"{path}.milliseconds: must be non-negative")
    return DelayAction(int(ms))


def _parse_macro(value, path, depth):
    if depth >= _MAX_SPEC_DEPTH:
        raise ValueError(f"{path}: macro nesting depth exceeded")
    steps = value.get("steps")
    if not isinstance(steps, list):
        raise ValueError(f"{path}.steps: must be an array")
    parsed = []
    for i, step in enumerate(steps):
        parsed.append(parse_spec(step, f"{path}.steps[{i}]", _depth=depth+1))
    return MacroAction(tuple(parsed))


def _parse_debug_log(value, path):
    msg = _str_field(value, path, "message")
    return DebugLogAction(msg)


def _parse_set_layer(value, path):
    name = _str_field(value, path, "layer")
    try:
        LayerId(name)
    except ValueError:
        raise ValueError(f"{path}.layer: invalid LayerId: {name!r}")
    return SetLayerAction(name)


def _parse_set_profile(value, path):
    from yyr4_linux_control.control.models import ProfileId
    name = _str_field(value, path, "profile")
    try:
        ProfileId(name)
    except ValueError:
        raise ValueError(f"{path}.profile: invalid ProfileId: {name!r}")
    return SetProfileAction(name)
