from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
from enum import Enum, auto

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
