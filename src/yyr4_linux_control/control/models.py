from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Mapping, Tuple, Any, Dict
from enum import Enum, auto
import re

from ..domain.controls import PhysicalControl
from ..domain.events import ControlPhase, ControlEvent

# Official controls definition
_OFFICIAL_CONTROL_NAMES = frozenset({
    "A1", "A2", "A3", "A4", "A5", "A6", "A7", "A8", "A9", "A10", "A11", "A12",
    "AL", "AP", "AR",
    "BL", "BP", "BR",
    "CL", "CP", "CR",
    "DL", "DP", "DR",
})

class OfficialControl(str, Enum):
    A1 = "A1"
    A2 = "A2"
    A3 = "A3"
    A4 = "A4"
    A5 = "A5"
    A6 = "A6"
    A7 = "A7"
    A8 = "A8"
    A9 = "A9"
    A10 = "A10"
    A11 = "A11"
    A12 = "A12"
    AL = "AL"
    AP = "AP"
    AR = "AR"
    BL = "BL"
    BP = "BP"
    BR = "BR"
    CL = "CL"
    CP = "CP"
    CR = "CR"
    DL = "DL"
    DP = "DP"
    DR = "DR"

    @classmethod
    def from_physical_control(cls, ctrl: PhysicalControl) -> OfficialControl:
        # PhysicalControl uses vendor_name equal to our OfficialControl names.
        try:
            return cls(ctrl.vendor_name)
        except ValueError:
            raise ValueError(f"Unknown physical control vendor_name: {ctrl.vendor_name}")

@dataclass(frozen=True)
class OfficialControlEvent:
    control: OfficialControl
    phase: ControlPhase
    timestamp_ns: int

    @classmethod
    def from_control_event(cls, event: ControlEvent) -> OfficialControlEvent:
        return cls(
            control=OfficialControl.from_physical_control(event.control),
            phase=event.phase,
            timestamp_ns=event.timestamp_ns
        )

class LayerId(str, Enum):
    GENERAL = "general"
    LAYER_1 = "layer_1"
    LAYER_2 = "layer_2"
    LAYER_3 = "layer_3"
    LAYER_4 = "layer_4"
    LAYER_5 = "layer_5"
    LAYER_6 = "layer_6"
    LAYER_7 = "layer_7"
    LAYER_8 = "layer_8"

_PROFILE_ID_PATTERN = re.compile(r'^[a-z][a-z0-9_-]{0,63}$')

@dataclass(frozen=True)
class ProfileId:
    value: str

    def __post_init__(self):
        if not isinstance(self.value, str):
            raise ValueError(f"ProfileId must be a string, got {type(self.value)}")
        if not _PROFILE_ID_PATTERN.match(self.value):
            raise ValueError(f"Invalid ProfileId: {self.value}")
    
    def __str__(self) -> str:
        return self.value

@dataclass(frozen=True)
class LayerConfig:
    layer_id: LayerId
    controls: Mapping[OfficialControl, Any]  # Value is Action, typed Any to avoid circular import

@dataclass(frozen=True)
class ProfileConfig:
    profile_id: ProfileId
    layers: Mapping[LayerId, LayerConfig]

@dataclass(frozen=True)
class LayeredControlConfig:
    schema_version: int
    default_profile: ProfileId
    initial_layer: LayerId
    profiles: Mapping[ProfileId, ProfileConfig]
