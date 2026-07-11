from __future__ import annotations
from typing import List, Dict, Set, Optional
from ..domain.events import RawKeyEvent, ControlEvent
from ..domain.controls import PhysicalControl, ControlPhase
from .codebook import Codebook, DEFAULT_CODEBOOK, TransportCode

class TransportParser:
    def __init__(self, source_id: str, modifier_timeout_ms: int = 100, codebook: Optional[Codebook] = None):
        if modifier_timeout_ms <= 0:
            raise ValueError("modifier_timeout_ms must be positive")
        self.source_id = source_id
        self.modifier_timeout_ms = modifier_timeout_ms
        self.codebook = codebook or DEFAULT_CODEBOOK

        # State
        self._shift_active: bool = False
        self._shift_timestamp_ns: int = 0

        # Currently active F keys and what physical control they resolved to
        self._active_f_keys: Dict[str, PhysicalControl] = {}

        # Tracking metrics
        self.error_count: int = 0
        self.repeat_count: int = 0
        self.orphan_releases: int = 0
        self.modifier_timeouts: int = 0
        self.duplicate_downs: int = 0
        self.timestamp_regressions: int = 0
        self._last_timestamp_ns: int = 0

    def feed(self, event: RawKeyEvent) -> List[ControlEvent]:
        if event.source_id != self.source_id:
            return []

        if event.timestamp_ns < self._last_timestamp_ns:
            self.timestamp_regressions += 1
            self.error_count += 1
            # Optionally we could reject it, but let's just log and process it
            # or we can reject. I'll reject time regressions to maintain invariants.
            return []

        self._last_timestamp_ns = event.timestamp_ns
        self.advance_time(event.timestamp_ns)

        if event.value == 2:
            self.repeat_count += 1
            return []

        if event.code == "KEY_LEFTSHIFT":
            if event.value == 1:
                self._shift_active = True
                self._shift_timestamp_ns = event.timestamp_ns
            elif event.value == 0:
                self._shift_active = False
            return []

        if event.code.startswith("KEY_F"):
            if event.value == 1:
                if event.code in self._active_f_keys:
                    self.duplicate_downs += 1
                    self.error_count += 1
                    return []

                modifiers = ("KEY_LEFTSHIFT",) if self._shift_active else ()
                ctrl = self.codebook.get_by_primary_key_and_modifiers(event.code, modifiers)

                if ctrl:
                    self._active_f_keys[event.code] = ctrl
                    return [ControlEvent(
                        source_id=self.source_id,
                        timestamp_ns=event.timestamp_ns,
                        control=ctrl,
                        phase=ControlPhase.DOWN,
                        transport_code=TransportCode(event.code, modifiers)
                    )]
                else:
                    self.error_count += 1

            elif event.value == 0:
                if event.code in self._active_f_keys:
                    ctrl = self._active_f_keys.pop(event.code)
                    code = self.codebook.get_code_for_control_id(ctrl.control_id)
                    if code is None:
                        code = TransportCode(event.code)
                    return [ControlEvent(
                        source_id=self.source_id,
                        timestamp_ns=event.timestamp_ns,
                        control=ctrl,
                        phase=ControlPhase.UP,
                        transport_code=code
                    )]
                else:
                    self.orphan_releases += 1
                    self.error_count += 1

        return []

    def advance_time(self, timestamp_ns: int) -> None:
        if self._shift_active and not self._active_f_keys:
            elapsed_ms = (timestamp_ns - self._shift_timestamp_ns) / 1_000_000
            if elapsed_ms > self.modifier_timeout_ms:
                self._shift_active = False
                self.modifier_timeouts += 1
                self.error_count += 1

    def reset(self, timestamp_ns: int = 0) -> List[ControlEvent]:
        if timestamp_ns != 0 and timestamp_ns > self._last_timestamp_ns:
            self._last_timestamp_ns = timestamp_ns
        self._shift_active = False
        self._shift_timestamp_ns = 0

        events = []
        for f_key, ctrl in self._active_f_keys.items():
            code = self.codebook.get_code_for_control_id(ctrl.control_id)
            if code is None:
                code = TransportCode("UNKNOWN")
            events.append(ControlEvent(
                source_id=self.source_id,
                timestamp_ns=timestamp_ns,
                control=ctrl,
                phase=ControlPhase.UP,
                transport_code=code,
                synthetic=True,
                reason="reset"
            ))
        self._active_f_keys.clear()
        return events
