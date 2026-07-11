from __future__ import annotations
from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional

class ControlKind(Enum):
    BUTTON = auto()
    ENCODER_COUNTERCLOCKWISE = auto()
    ENCODER_PRESS = auto()
    ENCODER_CLOCKWISE = auto()

class ControlPhase(Enum):
    DOWN = auto()
    UP = auto()

@dataclass(frozen=True)
class PhysicalControl:
    control_id: str
    vendor_name: str
    kind: ControlKind
    encoder_index: Optional[int] = None
    button_index: Optional[int] = None

    def __post_init__(self) -> None:
        if not self.control_id or not self.vendor_name:
            raise ValueError("control_id and vendor_name cannot be empty")
        if self.kind == ControlKind.BUTTON:
            if self.button_index is None:
                raise ValueError("BUTTON kind must have a button_index")
            if self.encoder_index is not None:
                raise ValueError("BUTTON kind cannot have an encoder_index")
            if not (1 <= self.button_index <= 12):
                raise ValueError("button_index must be between 1 and 12")
        else:
            if self.encoder_index is None:
                raise ValueError("Encoder kind must have an encoder_index")
            if self.button_index is not None:
                raise ValueError("Encoder kind cannot have a button_index")
            if not (1 <= self.encoder_index <= 4):
                raise ValueError("encoder_index must be between 1 and 4")
