"""Build View Models from validated YYR4 configuration objects.

This module depends only on the control domain (`control.config`,
`control.actions`, `control.models`) and the Configurator view
models — no TOML parsing, no daemon, no hardware.
"""

from __future__ import annotations
from pathlib import Path
from typing import List, Optional

from yyr4_linux_control.control.config import load_control_config_from_file
from yyr4_linux_control.control.models import (
    OfficialControl, LayerId, ProfileId, LayeredControlConfig,
)
from yyr4_linux_control.control.actions import (
    Action, HotkeyAction, TextAction, CommandAction,
    DelayAction, MacroAction, NoOpAction, DebugLogAction,
    SetLayerAction, NextLayerAction, PreviousLayerAction, SetProfileAction,
)

from .models import (
    ConfiguratorDocument, ProfileView, LayerView, ControlView,
    ActionView, ValidationDiagnostic,
)

# ── Official Control ordering ────────────────────────────────────

_BUTTON_ORDER = tuple(OfficialControl(f"A{i}") for i in range(1, 13))
_ENCODER_ORDER = (
    OfficialControl.AL, OfficialControl.AP, OfficialControl.AR,
    OfficialControl.BL, OfficialControl.BP, OfficialControl.BR,
    OfficialControl.CL, OfficialControl.CP, OfficialControl.CR,
    OfficialControl.DL, OfficialControl.DP, OfficialControl.DR,
)
_OFFICIAL_ORDER = _BUTTON_ORDER + _ENCODER_ORDER

_ENCODER_KINDS = {
    "encoder.e01.counterclockwise": "encoder_counterclockwise",
    "encoder.e01.press":             "encoder_press",
    "encoder.e01.clockwise":         "encoder_clockwise",
    "encoder.e02.counterclockwise": "encoder_counterclockwise",
    "encoder.e02.press":             "encoder_press",
    "encoder.e02.clockwise":         "encoder_clockwise",
    "encoder.e03.counterclockwise": "encoder_counterclockwise",
    "encoder.e03.press":             "encoder_press",
    "encoder.e03.clockwise":         "encoder_clockwise",
    "encoder.e04.counterclockwise": "encoder_counterclockwise",
    "encoder.e04.press":             "encoder_press",
    "encoder.e04.clockwise":         "encoder_clockwise",
}

_ENCODER_GROUP = {
    "encoder.e01": "A",
    "encoder.e02": "B",
    "encoder.e03": "C",
    "encoder.e04": "D",
}

_MAX_MACRO_DEPTH = 4


# ── Builder ──────────────────────────────────────────────────────

def build_document(config_path: Path) -> ConfiguratorDocument:
    """Load a validated config and convert it to a read-only View Model."""
    config = load_control_config_from_file(config_path)
    return _build_from_config(config, str(config_path))


def _build_from_config(
    config: LayeredControlConfig, source_path: str,
) -> ConfiguratorDocument:
    profiles: List[ProfileView] = []
    total_layers = 0
    total_controls = 0
    diagnostics: List[ValidationDiagnostic] = []

    for profile_id in sorted(config.profiles.keys(), key=lambda p: p.value):
        pc = config.profiles[profile_id]
        layers: List[LayerView] = []
        profile_controls = 0

        for layer_id in sorted(pc.layers.keys(), key=lambda lid: lid.value):
            lc = pc.layers[layer_id]
            controls = _build_controls(lc.controls, layer_id.value)
            configured = sum(1 for c in controls if c.configured)
            profile_controls += configured
            layers.append(LayerView(
                layer_id=layer_id.value,
                is_initial=(layer_id == config.initial_layer),
                configured_control_count=configured,
                controls=tuple(controls),
            ))
            total_controls += configured

        total_layers += len(layers)
        profiles.append(ProfileView(
            profile_id=profile_id.value,
            is_default=(profile_id == config.default_profile),
            layer_count=len(layers),
            configured_control_count=profile_controls,
            layers=tuple(layers),
        ))

    return ConfiguratorDocument(
        schema_version=config.schema_version,
        source_path=source_path,
        default_profile=config.default_profile.value,
        initial_layer=config.initial_layer.value,
        profile_count=len(profiles),
        total_layer_count=total_layers,
        total_configured_controls=total_controls,
        validation_status="VALID",
        diagnostics=tuple(diagnostics),
        profiles=tuple(profiles),
    )


def _build_controls(
    configured: dict, _layer_name: str,
) -> List[ControlView]:
    result: List[ControlView] = []
    for oc in _OFFICIAL_ORDER:
        action = configured.get(oc)
        if action is None:
            result.append(ControlView(
                official_name=oc.value,
                control_kind=_kind_for(oc),
                encoder_group=_group_for(oc),
                configured=False,
                action=None,
                action_summary="UNMAPPED",
            ))
        else:
            av = _build_action(action, depth=0)
            result.append(ControlView(
                official_name=oc.value,
                control_kind=_kind_for(oc),
                encoder_group=_group_for(oc),
                configured=True,
                action=av,
                action_summary=av.concise_summary,
            ))
    return result


def _kind_for(oc: OfficialControl) -> str:
    if oc.value in frozenset({f"A{i}" for i in range(1, 13)}):
        return "button"
    # Derive from the canonical encoder mapping
    idx = _ENCODER_ORDER.index(oc)
    suffix = ("counterclockwise", "press", "clockwise")[idx % 3]
    enc_num = (idx // 3) + 1
    cid = f"encoder.e{enc_num:02d}.{suffix}"
    return _ENCODER_KINDS.get(cid, "button")


def _group_for(oc: OfficialControl) -> Optional[str]:
    if oc.value in frozenset({f"A{i}" for i in range(1, 13)}):
        return None
    idx = _ENCODER_ORDER.index(oc)
    enc_num = (idx // 3) + 1
    return _ENCODER_GROUP.get(f"encoder.e{enc_num:02d}")


# ── Action → ActionView ──────────────────────────────────────────

def _build_action(action: Action, depth: int) -> ActionView:
    if depth > _MAX_MACRO_DEPTH:
        return ActionView(
            action_type="UNKNOWN",
            concise_summary="[recursion limit exceeded]",
            warning_flags=("recursion_depth",),
            side_effect_class="unknown",
        )

    if isinstance(action, HotkeyAction):
        keys_str = "+".join(action.keys)
        return ActionView(
            action_type="Hotkey",
            concise_summary=keys_str,
            structured_details=(("keys", keys_str),),
            side_effect_class="desktop_input",
        )

    if isinstance(action, TextAction):
        preview = action.value[:60] + "…" if len(action.value) > 60 else action.value
        return ActionView(
            action_type="Text",
            concise_summary=preview,
            structured_details=(("value", action.value),),
            side_effect_class="desktop_input",
        )

    if isinstance(action, CommandAction):
        exe = action.argv[0] if action.argv else "?"
        return ActionView(
            action_type="Command",
            concise_summary=exe,
            structured_details=(
                ("executable", exe),
                ("argv", " ".join(action.argv)),
                ("timeout_seconds", str(action.timeout_seconds or "default")),
            ),
            side_effect_class="command_execution",
        )

    if isinstance(action, DelayAction):
        return ActionView(
            action_type="Delay",
            concise_summary=f"{action.milliseconds} ms",
            structured_details=(("milliseconds", str(action.milliseconds)),),
            side_effect_class="none",
        )

    if isinstance(action, MacroAction):
        steps = [_build_action(s, depth + 1) for s in action.steps]
        return ActionView(
            action_type="Macro",
            concise_summary=f"{len(steps)} steps",
            structured_details=(("step_count", str(len(steps))),),
            child_steps=tuple(steps),
            side_effect_class="composite",
        )

    if isinstance(action, NoOpAction):
        return ActionView(
            action_type="NoOp",
            concise_summary="(no operation)",
            side_effect_class="none",
        )

    if isinstance(action, DebugLogAction):
        return ActionView(
            action_type="DebugLog",
            concise_summary=action.message[:60],
            structured_details=(("message", action.message),),
            side_effect_class="diagnostic",
        )

    if isinstance(action, SetLayerAction):
        return ActionView(
            action_type="SetLayer",
            concise_summary=f"→ {action.layer}",
            structured_details=(("target_layer", action.layer),),
            side_effect_class="runtime_context_change",
        )

    if isinstance(action, NextLayerAction):
        return ActionView(
            action_type="NextLayer",
            concise_summary="→ next layer",
            side_effect_class="runtime_context_change",
        )

    if isinstance(action, PreviousLayerAction):
        return ActionView(
            action_type="PreviousLayer",
            concise_summary="→ previous layer",
            side_effect_class="runtime_context_change",
        )

    if isinstance(action, SetProfileAction):
        return ActionView(
            action_type="SetProfile",
            concise_summary=f"→ {action.profile}",
            structured_details=(("target_profile", action.profile),),
            side_effect_class="runtime_context_change",
        )

    return ActionView(
        action_type=f"UNKNOWN:{type(action).__name__}",
        concise_summary="[unsupported action type]",
        warning_flags=("unknown_action_type",),
        side_effect_class="unknown",
    )
