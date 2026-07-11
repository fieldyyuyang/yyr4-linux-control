from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING
from .controls import PhysicalControl, ControlPhase

if TYPE_CHECKING:
    from ..transport.codebook import TransportCode

@dataclass(frozen=True)
class RawKeyEvent:
    source_id: str
    timestamp_ns: int
    code: str
    value: int

    def __post_init__(self) -> None:
        if not self.source_id:
            raise ValueError("source_id cannot be empty")
        if self.timestamp_ns < 0:
            raise ValueError("timestamp_ns cannot be negative")
        if not self.code:
            raise ValueError("code cannot be empty")
        if self.value not in (0, 1, 2):
            raise ValueError("value must be 0, 1, or 2")

@dataclass(frozen=True)
class ControlEvent:
    source_id: str
    timestamp_ns: int
    control: PhysicalControl
    phase: ControlPhase
    transport_code: 'TransportCode'
    synthetic: bool = False
    reason: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.source_id:
            raise ValueError("source_id cannot be empty")
        if self.timestamp_ns < 0:
            raise ValueError("timestamp_ns cannot be negative")
        if self.synthetic and not self.reason:
            raise ValueError("synthetic events must have a reason")
        if not self.synthetic and self.reason:
            raise ValueError("non-synthetic events should not have a reason")
        if not hasattr(self.transport_code, "primary_key"):
            raise ValueError("transport_code must be structured")
