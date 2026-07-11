from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol, AsyncIterator
import time

@dataclass(frozen=True)
class KernelInputEvent:
    event_type: int
    code: int
    value: int
    timestamp_ns: int = 0
    
    def __post_init__(self) -> None:
        if self.event_type < 0:
            raise ValueError("event_type must be non-negative")
        if self.code < 0:
            raise ValueError("code must be non-negative")
        if self.timestamp_ns < 0:
            raise ValueError("timestamp_ns must be non-negative")

class EventDeviceHandle(Protocol):
    @property
    def path(self) -> str:
        ...
        
    @property
    def name(self) -> str:
        ...

    def async_read_loop(self) -> AsyncIterator[KernelInputEvent]:
        ...

    def close(self) -> None:
        ...

class EventDeviceFactory(Protocol):
    def open(self, path: str) -> EventDeviceHandle:
        ...

class MonotonicClock(Protocol):
    def now_ns(self) -> int:
        ...

class SystemMonotonicClock(MonotonicClock):
    def now_ns(self) -> int:
        return time.monotonic_ns()
