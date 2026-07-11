from typing import Protocol, AsyncIterator
from ..device.identity import YYR4Identity
from ..domain.events import RawKeyEvent
from ..transport.parser import TransportParser

class DeviceSelector(Protocol):
    def select_single(self) -> YYR4Identity:
        ...

class RawInputStream(Protocol):
    def read_events(self) -> AsyncIterator[RawKeyEvent]:
        ...
        
    async def close(self) -> None:
        ...

class RawInputStreamFactory(Protocol):
    def create(self, identity: YYR4Identity) -> RawInputStream:
        ...

class TransportParserFactory(Protocol):
    def create(self, source_id: str) -> TransportParser:
        ...

class DefaultTransportParserFactory(TransportParserFactory):
    def create(self, source_id: str) -> TransportParser:
        return TransportParser(source_id=source_id)
