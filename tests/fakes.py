from typing import AsyncIterator, List, Optional
import asyncio
from yyr4_linux_control.input.interfaces import EventDeviceFactory, EventDeviceHandle, KernelInputEvent, MonotonicClock
from yyr4_linux_control.device.discovery import DiscoveryBackend, UdevInputRecord

class FakeEventDeviceHandle(EventDeviceHandle):
    def __init__(self, path: str, events: List[KernelInputEvent], name: str = "Fake Device", auto_eof: bool = True):
        self._path = path
        self._name = name
        self._events = events
        self.closed = False
        self.grabbed = False
        self._queue = asyncio.Queue()
        for e in events:
            self._queue.put_nowait(e)
        if auto_eof:
            self._queue.put_nowait(None)

    @property
    def path(self) -> str:
        return self._path

    @property
    def name(self) -> str:
        return self._name

    async def async_read_loop(self) -> AsyncIterator[KernelInputEvent]:
        while not self.closed:
            try:
                evt = await self._queue.get()
                if evt is None:
                    break
                if isinstance(evt, Exception):
                    raise evt
                yield evt
            except asyncio.CancelledError:
                break

    def close(self) -> None:
        self.closed = True
        
    def inject_error(self, err: Exception):
        self._queue.put_nowait(err)
        
    def inject_eof(self):
        self._queue.put_nowait(None)

class FakeEventDeviceFactory(EventDeviceFactory):
    def __init__(self):
        self.handles = {}
        self.should_fail_open = False
        self.auto_eof = True

    def open(self, path: str) -> EventDeviceHandle:
        if self.should_fail_open:
            raise OSError("Fake open failure")
        if path not in self.handles:
            self.handles[path] = FakeEventDeviceHandle(path, [], auto_eof=self.auto_eof)
        return self.handles[path]

class FakeClock(MonotonicClock):
    def __init__(self):
        self._time = 1000

    def now_ns(self) -> int:
        self._time += 1000
        return self._time
        
    def set_time(self, t: int):
        self._time = t
