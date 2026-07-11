from __future__ import annotations
import asyncio
from typing import Optional, AsyncIterator, Dict, Any, Tuple
from dataclasses import dataclass

from ..device.identity import YYR4Identity
from ..device.errors import DependencyUnavailableError
from ..domain.events import RawKeyEvent
from .interfaces import EventDeviceFactory, MonotonicClock, EventDeviceHandle, KernelInputEvent
from .errors import InputReadError, InputOpenError

def _resolve_key_name(code: int, ecodes_module: Any) -> Optional[str]:
    if not ecodes_module:
        return None
    try:
        keys = getattr(ecodes_module, "keys", None)
        if isinstance(keys, dict):
            name = keys.get(code)
            if isinstance(name, str):
                return name
            if isinstance(name, list):
                for n in name:
                    if n.startswith("KEY_"):
                        return n
                return name[0] if name else None
        KEY_dict = getattr(ecodes_module, "KEY", None)
        if isinstance(KEY_dict, dict):
            name = KEY_dict.get(code)
            if isinstance(name, str):
                return name
            if isinstance(name, list):
                for n in name:
                    if n.startswith("KEY_"):
                        return n
                return name[0] if name else None
    except Exception:
        pass
    return None

@dataclass(frozen=True)
class InputDiagnostics:
    opened_devices: int
    emitted_key_events: int
    ignored_non_key_events: int
    ignored_unknown_codes: int
    read_errors: int
    close_count: int
    timestamp_adjustments: int

class EvdevInputAdapter:
    def __init__(self, identity: YYR4Identity, factory: EventDeviceFactory, clock: MonotonicClock, include_mouse: bool = True):
        self._identity = identity
        self._factory = factory
        self._clock = clock
        self._include_mouse = include_mouse
        
        self._handles: Dict[str, EventDeviceHandle] = {}
        self._tasks: list[asyncio.Task] = []
        self._queue: asyncio.Queue[Tuple[str, KernelInputEvent]] = asyncio.Queue()
        self._closed = False
        self._last_timestamp_ns = 0
        
        self._diags = {
            "opened_devices": 0,
            "emitted_key_events": 0,
            "ignored_non_key_events": 0,
            "ignored_unknown_codes": 0,
            "read_errors": 0,
            "close_count": 0,
            "timestamp_adjustments": 0
        }

    async def _reader_task(self, source_id: str, handle: EventDeviceHandle) -> None:
        try:
            async for evt in handle.async_read_loop():
                await self._queue.put((source_id, evt))
        except asyncio.CancelledError:
            pass
        except Exception as e:
            self._diags["read_errors"] += 1
            await self._queue.put((source_id, e))
        finally:
            await self._queue.put((source_id, None))

    async def start(self) -> None:
        if self._closed:
            raise RuntimeError("Cannot start a closed adapter")
            
        kb_path = self._identity.keyboard.device_node
        try:
            kb_handle = self._factory.open(kb_path)
            self._handles["yyr4:keyboard"] = kb_handle
            self._diags["opened_devices"] += 1
        except Exception as e:
            raise InputOpenError(f"Failed to open keyboard at {kb_path}") from e

        if self._include_mouse:
            ms_path = self._identity.mouse.device_node
            try:
                ms_handle = self._factory.open(ms_path)
                self._handles["yyr4:mouse"] = ms_handle
                self._diags["opened_devices"] += 1
            except Exception as e:
                self.close()
                raise InputOpenError(f"Failed to open mouse at {ms_path}") from e

        for source_id, handle in self._handles.items():
            self._tasks.append(asyncio.create_task(self._reader_task(source_id, handle)))

    async def read_events(self) -> AsyncIterator[RawKeyEvent]:
        if not self._handles:
            # Need to start first
            await self.start()
            
        try:
            # We must map raw codes to string codes. E.g. 183 -> KEY_F13.
            # However, we don't have evdev ecodes imported here unless we conditionally import or inject it.
            # But the spec says: "代码中可以引用evdev.ecodes.EV_KEY及键码名称，但必须保持第三方依赖可选。"
            try:
                import evdev
                from evdev import ecodes
                EV_KEY = ecodes.EV_KEY
                keys = ecodes.keys
            except ImportError:
                # If evdev is not installed, fallback to empty or rely on injection.
                # Since factory might be mock, we can just define EV_KEY = 1
                EV_KEY = 1
                keys = {}
                
            active_readers = len(self._handles)
            while not self._closed and active_readers > 0:
                item = await self._queue.get()
                source_id, evt = item
                
                if evt is None:
                    active_readers -= 1
                    continue
                    
                if isinstance(evt, Exception):
                    self.close()
                    raise InputReadError(f"Underlying device read failed on {source_id}") from evt
                    
                if evt.event_type != EV_KEY:
                    self._diags["ignored_non_key_events"] += 1
                    continue
                    
                try:
                    import evdev
                    ecodes_mod = evdev.ecodes
                except ImportError:
                    ecodes_mod = None
                code_name = _resolve_key_name(evt.code, ecodes_mod)

                if not code_name:
                    self._diags["ignored_unknown_codes"] += 1
                    continue
                    
                now = self._clock.now_ns()
                if now <= self._last_timestamp_ns:
                    now = self._last_timestamp_ns + 1
                    self._diags["timestamp_adjustments"] += 1
                self._last_timestamp_ns = now
                
                self._diags["emitted_key_events"] += 1
                
                yield RawKeyEvent(
                    source_id=source_id,
                    timestamp_ns=now,
                    code=code_name,
                    value=evt.value
                )
                
        except asyncio.CancelledError:
            self.close()
            raise

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._diags["close_count"] += 1
        
        for task in self._tasks:
            task.cancel()
            
        for handle in list(self._handles.values()):
            try:
                handle.close()
            except Exception:
                pass
        self._handles.clear()

    def snapshot_diagnostics(self) -> InputDiagnostics:
        return InputDiagnostics(**self._diags)


class LinuxEvdevDeviceFactory(EventDeviceFactory):
    def __init__(self) -> None:
        try:
            import evdev
            self._evdev = evdev
        except ImportError as e:
            raise DependencyUnavailableError("evdev is not installed") from e
            
    def open(self, path: str) -> EventDeviceHandle:
        device = self._evdev.InputDevice(path)
        return _LinuxEvdevHandle(device)


class _LinuxEvdevHandle(EventDeviceHandle):
    def __init__(self, device: Any):
        self._device = device
        
    @property
    def path(self) -> str:
        return self._device.path
        
    @property
    def name(self) -> str:
        return self._device.name
        
    async def async_read_loop(self) -> AsyncIterator[KernelInputEvent]:
        async for event in self._device.async_read_loop():
            yield KernelInputEvent(
                event_type=event.type,
                code=event.code,
                value=event.value,
                timestamp_ns=0 # Adapter provides timestamp
            )
            
    def close(self) -> None:
        self._device.close()
