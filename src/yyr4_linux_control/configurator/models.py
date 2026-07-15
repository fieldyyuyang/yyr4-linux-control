"""Read-only View Models for the YYR4 configuration preview.

These dataclasses are pure data — no TOML parsing, no hardware access,
no daemon communication.  They are constructed by `builder.py` from
validated `LayeredControlConfig` objects.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Tuple, Optional, List


@dataclass(frozen=True)
class ActionView:
    """Stable, read-only representation of a single Action."""
    action_type: str
    concise_summary: str
    structured_details: Tuple[Tuple[str, str], ...] = ()
    child_steps: Tuple[ActionView, ...] = ()
    warning_flags: Tuple[str, ...] = ()
    side_effect_class: str = "none"


@dataclass(frozen=True)
class ControlView:
    """A single OfficialControl within a Layer."""
    official_name: str
    control_kind: str               # button, encoder_counterclockwise, encoder_press, encoder_clockwise
    encoder_group: Optional[str]     # A, B, C, D, or None
    configured: bool
    action: Optional[ActionView]     # None = UNMAPPED
    action_summary: str              # human-readable one-line summary


@dataclass(frozen=True)
class LayerView:
    """A read-only view of one Layer within a Profile."""
    layer_id: str
    is_initial: bool
    configured_control_count: int
    controls: Tuple[ControlView, ...]


@dataclass(frozen=True)
class ProfileView:
    """A read-only view of one Profile."""
    profile_id: str
    is_default: bool
    layer_count: int
    configured_control_count: int
    layers: Tuple[LayerView, ...]


@dataclass(frozen=True)
class ValidationDiagnostic:
    """A single configuration validation notice."""
    level: str      # info, warning, error
    message: str


_CONFIGURATOR_MACRO_MAX_DEPTH = 4


@dataclass(frozen=True)
class ConfiguratorDocument:
    """Top-level read-only document representing a full configuration."""
    schema_version: int
    source_path: str
    default_profile: str
    initial_layer: str
    profile_count: int
    total_layer_count: int
    total_configured_controls: int
    validation_status: str           # VALID, INVALID, etc.
    diagnostics: Tuple[ValidationDiagnostic, ...]
    profiles: Tuple[ProfileView, ...]
