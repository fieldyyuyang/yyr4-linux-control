"""Deterministic schema-v2 TOML serialization for YYR4 configurations.

Produces byte-identical output for semantically identical input.
Uses sort keys everywhere and a fixed control ordering.
"""

import io
from typing import Dict, Any, Tuple, List

from yyr4_linux_control.control.actions import (
    Action, HotkeyAction, TextAction, CommandAction,
    DelayAction, MacroAction, NoOpAction, DebugLogAction,
    SetLayerAction, NextLayerAction, PreviousLayerAction, SetProfileAction,
)
from yyr4_linux_control.control.models import (
    OfficialControl, LayerId, ProfileId, LayeredControlConfig,
)


# ── Action field ordering ────────────────────────────────────────

def _emit_action(indent: int, action: Action) -> str:
    """Return a deterministic TOML representation of *action*."""
    parts: List[str] = []

    if isinstance(action, HotkeyAction):
        parts.append(f'{{ type = "hotkey", keys = {_toml_strs(action.keys)} }}')

    elif isinstance(action, TextAction):
        parts.append(f'{{ type = "text", value = {_toml_str(action.value)} }}')

    elif isinstance(action, CommandAction):
        to = f', timeout_seconds = {action.timeout_seconds}' if action.timeout_seconds else ""
        parts.append(
            f'{{ type = "command", argv = {_toml_strs(action.argv)}{to} }}'
        )

    elif isinstance(action, DelayAction):
        parts.append(f'{{ type = "delay", milliseconds = {action.milliseconds} }}')

    elif isinstance(action, MacroAction):
        steps = "\n" + ",\n".join(
            f'{"    " * (indent + 2)}{_emit_action(indent + 2, s)}'
            for s in action.steps
        ) + f"\n{'    ' * (indent + 1)}"
        parts.append(f"{{ type = \"macro\", steps = [{steps}] }}")

    elif isinstance(action, NoOpAction):
        parts.append('{ type = "noop" }')

    elif isinstance(action, DebugLogAction):
        parts.append(f'{{ type = "debug_log", message = {_toml_str(action.message)} }}')

    elif isinstance(action, SetLayerAction):
        parts.append(f'{{ type = "set_layer", layer = {_toml_str(action.layer)} }}')

    elif isinstance(action, NextLayerAction):
        parts.append('{ type = "next_layer" }')

    elif isinstance(action, PreviousLayerAction):
        parts.append('{ type = "previous_layer" }')

    elif isinstance(action, SetProfileAction):
        parts.append(f'{{ type = "set_profile", profile = {_toml_str(action.profile)} }}')

    else:
        raise ValueError(f"Unknown action type: {type(action).__name__}")

    return "".join(parts)


# ── TOML string escaping ──────────────────────────────────────────

def _toml_str(s: str) -> str:
    """Return a TOML basic-string literal for *s*.

    Handles all required TOML basic-string escapes: \\\", \\\\, \\b, \\t,
    \\n, \\f, \\r, and \\uXXXX for other control characters.
    """
    parts = []
    for ch in s:
        cp = ord(ch)
        if ch == '"':
            parts.append('\\"')
        elif ch == "\\":
            parts.append("\\\\")
        elif ch == "\b":
            parts.append("\\b")
        elif ch == "\t":
            parts.append("\\t")
        elif ch == "\n":
            parts.append("\\n")
        elif ch == "\f":
            parts.append("\\f")
        elif ch == "\r":
            parts.append("\\r")
        elif cp < 0x20 or cp == 0x7f:
            parts.append(f"\\u{cp:04x}")
        else:
            parts.append(ch)
    return f'"{''.join(parts)}"'


def _toml_strs(strings: Tuple[str, ...]) -> str:
    return "[" + ", ".join(_toml_str(s) for s in strings) + "]"


# ── Canonical control order ───────────────────────────────────────

_CANONICAL_CONTROLS: Tuple[OfficialControl, ...] = (
    OfficialControl.A1, OfficialControl.A2, OfficialControl.A3,
    OfficialControl.A4, OfficialControl.A5, OfficialControl.A6,
    OfficialControl.A7, OfficialControl.A8, OfficialControl.A9,
    OfficialControl.A10, OfficialControl.A11, OfficialControl.A12,
    OfficialControl.AL, OfficialControl.AP, OfficialControl.AR,
    OfficialControl.BL, OfficialControl.BP, OfficialControl.BR,
    OfficialControl.CL, OfficialControl.CP, OfficialControl.CR,
    OfficialControl.DL, OfficialControl.DP, OfficialControl.DR,
)


def serialize(config: LayeredControlConfig) -> str:
    """Return a deterministic schema-v2 TOML string.

    The output is stable: calling this function twice with the same
    semantic configuration produces byte-identical strings.
    """
    buf = io.StringIO()

    # ── Top-level keys in fixed order ──
    buf.write(f'schema_version = {config.schema_version}\n')
    buf.write(f'default_profile = {_toml_str(config.default_profile.value)}\n')
    buf.write(f'initial_layer = {_toml_str(config.initial_layer.value)}\n')
    buf.write("\n")

    # ── Profiles in sorted order ──
    for pid in sorted(config.profiles.keys(), key=lambda p: p.value):
        profile = config.profiles[pid]
        buf.write(f"\n")

        for lid in sorted(profile.layers.keys(), key=lambda l: l.value):
            layer = profile.layers[lid]

            for oc in _CANONICAL_CONTROLS:
                action = layer.controls.get(oc)
                if action is None:
                    continue
                key = f"profiles.{pid.value}.layers.{lid.value}.controls.{oc.value}.action"
                buf.write(f"{key} = {_emit_action(0, action)}\n")

    return buf.getvalue()
