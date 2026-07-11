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
                raise

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

from yyr4_linux_control.device.identity import YYR4Identity, InputInterface, InterfaceRole
from yyr4_linux_control.domain.events import RawKeyEvent
from yyr4_linux_control.observation.interfaces import DeviceSelector, RawInputStream, RawInputStreamFactory, TransportParserFactory
from yyr4_linux_control.transport.parser import TransportParser
from yyr4_linux_control.device.errors import DeviceDiscoveryError
from yyr4_linux_control.input.errors import InputAdapterError

class FakeDeviceSelector(DeviceSelector):
    def __init__(self, identity: YYR4Identity = None, error: Exception = None):
        self.identity = identity
        self.error = error
        self.call_count = 0

    def select_single(self) -> YYR4Identity:
        self.call_count += 1
        if self.error:
            raise self.error
        return self.identity

class FakeRawInputStream(RawInputStream):
    def __init__(self, events: List[RawKeyEvent], auto_eof: bool = True):
        self._queue = asyncio.Queue()
        self.closed = False
        self.close_count = 0
        for e in events:
            self._queue.put_nowait(e)
        if auto_eof:
            self._queue.put_nowait(None)

    async def read_events(self) -> AsyncIterator[RawKeyEvent]:
        while not self.closed:
            try:
                evt = await self._queue.get()
                if evt is None:
                    break
                if isinstance(evt, Exception):
                    raise evt
                yield evt
            except asyncio.CancelledError:
                raise

    async def close(self) -> None:
        self.closed = True
        self.close_count += 1
        self._queue.put_nowait(None)

    def inject_error(self, err: Exception):
        self._queue.put_nowait(err)

    def inject_eof(self):
        self._queue.put_nowait(None)

class FakeRawInputStreamFactory(RawInputStreamFactory):
    def __init__(self, stream: FakeRawInputStream = None, error: Exception = None):
        self.stream = stream
        self.error = error
        self.call_count = 0

    def create(self, identity: YYR4Identity) -> RawInputStream:
        self.call_count += 1
        if self.error:
            raise self.error
        return self.stream

class FaultingTransportParserFactory(TransportParserFactory):
    def __init__(self, parser: TransportParser = None, error: Exception = None):
        self.parser = parser
        self.error = error

    def create(self, source_id: str) -> TransportParser:
        if self.error:
            raise self.error
        return self.parser

class FaultingTransportParser(TransportParser):
    def __init__(self, *args, feed_error=None, reset_error=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.feed_error = feed_error
        self.reset_error = reset_error
        self.reset_call_count = 0

    def feed(self, event):
        if self.feed_error:
            raise self.feed_error
        return super().feed(event)

    def reset(self, timestamp_ns: int = 0):
        self.reset_call_count += 1
        if self.reset_error:
            raise self.reset_error
        return super().reset(timestamp_ns)

def get_dummy_identity() -> YYR4Identity:
    return YYR4Identity(
        vendor_id="1234",
        product_id="5678",
        manufacturer="YOUYOU TEC.",
        product="YOUYOU Keyb_V2",
        usb_parent_syspath="/sys/dummy",
        keyboard=InputInterface(InterfaceRole.KEYBOARD, "/dev/dummy1", "kbd", "02", True, "/sys/dummy/1", "/sys/dummy"),
        mouse=InputInterface(InterfaceRole.MOUSE, "/dev/dummy2", "mouse", "02", True, "/sys/dummy/2", "/sys/dummy"),
        serial_present=False
    )
