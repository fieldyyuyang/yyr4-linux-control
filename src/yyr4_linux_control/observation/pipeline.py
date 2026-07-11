from enum import Enum, auto
from typing import AsyncIterator, Optional, Dict
import asyncio
from dataclasses import replace

from ..domain.events import ControlEvent
from ..device.errors import DeviceDiscoveryError
from ..input.errors import InputAdapterError

from .interfaces import DeviceSelector, RawInputStream, RawInputStreamFactory, TransportParserFactory, DefaultTransportParserFactory
from .errors import ObservationStateError, ObservationDiscoveryError, ObservationInputError, ObservationConfigurationError, ObservationError
from .diagnostics import ObservationDiagnostics

class ObservationState(Enum):
    CREATED = auto()
    RUNNING = auto()
    CLOSING = auto()
    CLOSED = auto()

class ObservationPipeline:
    def __init__(
        self,
        selector: DeviceSelector,
        input_factory: RawInputStreamFactory,
        parser_factory: Optional[TransportParserFactory] = None,
        transport_source_id: str = "yyr4:keyboard"
    ):
        if not transport_source_id:
            raise ValueError("transport_source_id cannot be empty")
        if selector is None or input_factory is None:
            raise ValueError("Dependencies cannot be None")

        self.selector = selector
        self.input_factory = input_factory
        self.parser_factory = parser_factory or DefaultTransportParserFactory()
        self.transport_source_id = transport_source_id
        
        self._state = ObservationState.CREATED
        self._stream: Optional[RawInputStream] = None
        self._state_lock = asyncio.Lock()
        self._counters = {
            "discovery_attempts": 0,
            "identities_selected": 0,
            "streams_created": 0,
            "raw_events_seen": 0,
            "transport_source_events": 0,
            "ignored_source_events": 0,
            "control_events_emitted": 0,
            "synthetic_releases_emitted": 0,
            "normal_completions": 0,
            "discovery_errors": 0,
            "input_errors": 0,
            "parser_errors": 0,
            "cancellation_count": 0,
            "reset_on_cancel_count": 0,
            "dropped_synthetic_releases_on_cancel": 0,
            "close_calls": 0,
        }
        
    @property
    def state(self) -> ObservationState:
        return self._state

    def snapshot_diagnostics(self) -> ObservationDiagnostics:
        return ObservationDiagnostics(**self._counters)

    async def close(self) -> None:
        async with self._state_lock:
            self._counters["close_calls"] += 1
            if self._state == ObservationState.CREATED:
                self._state = ObservationState.CLOSED
                return
            if self._state in (ObservationState.CLOSING, ObservationState.CLOSED):
                return
            
            self._state = ObservationState.CLOSING
            
        if self._stream is not None:
            await self._stream.close()

    async def observe(self) -> AsyncIterator[ControlEvent]:
        async with self._state_lock:
            if self._state != ObservationState.CREATED:
                raise ObservationStateError("observe() can only be called once when CREATED")
            self._state = ObservationState.RUNNING

        self._counters["discovery_attempts"] += 1
        try:
            identity = self.selector.select_single()
        except DeviceDiscoveryError as exc:
            self._counters["discovery_errors"] += 1
            self._state = ObservationState.CLOSED
            raise ObservationDiscoveryError("Failed to discover device") from exc
        
        self._counters["identities_selected"] += 1
        
        try:
            self._stream = self.input_factory.create(identity)
        except Exception as exc:
            self._counters["discovery_errors"] += 1
            self._state = ObservationState.CLOSED
            raise ObservationDiscoveryError("Failed to create input stream") from exc
            
        self._counters["streams_created"] += 1
        
        try:
            parser = self.parser_factory.create(self.transport_source_id)
        except Exception as exc:
            self._state = ObservationState.CLOSED
            raise ObservationConfigurationError("Failed to create parser") from exc

        last_raw_timestamp_ns = 0
        last_parser_timestamp_ns = 0
        
        has_error = False
        try:
            try:
                async for raw_event in self._stream.read_events():
                    self._counters["raw_events_seen"] += 1
                    last_raw_timestamp_ns = raw_event.timestamp_ns
                    
                    if raw_event.source_id != self.transport_source_id:
                        self._counters["ignored_source_events"] += 1
                        continue
                        
                    self._counters["transport_source_events"] += 1
                    
                    try:
                        ctrl_events = parser.feed(raw_event)
                    except Exception as exc:
                        self._counters["parser_errors"] += 1
                        raise ObservationConfigurationError("Parser failed unexpectedly") from exc
                        
                    for ce in ctrl_events:
                        last_parser_timestamp_ns = max(last_parser_timestamp_ns, ce.timestamp_ns)
                        self._counters["control_events_emitted"] += 1
                        yield ce

                # Normal EOF
                reset_ts = max(last_parser_timestamp_ns + 1, last_raw_timestamp_ns + 1)
                try:
                    reset_events = parser.reset(reset_ts)
                except Exception as exc:
                    self._counters["parser_errors"] += 1
                    raise ObservationConfigurationError("Parser reset failed") from exc

                for ce in reset_events:
                    self._counters["control_events_emitted"] += 1
                    self._counters["synthetic_releases_emitted"] += 1
                    yield ce
                    
                self._counters["normal_completions"] += 1
                
            except asyncio.CancelledError:
                has_error = True
                self._counters["cancellation_count"] += 1
                self._counters["reset_on_cancel_count"] += 1
                try:
                    reset_events = parser.reset()
                    self._counters["dropped_synthetic_releases_on_cancel"] += len(reset_events)
                except Exception:
                    self._counters["parser_errors"] += 1
                raise
                
            except GeneratorExit:
                has_error = True
                self._counters["reset_on_cancel_count"] += 1
                try:
                    reset_events = parser.reset()
                    self._counters["dropped_synthetic_releases_on_cancel"] += len(reset_events)
                except Exception:
                    self._counters["parser_errors"] += 1
                raise

            except InputAdapterError as exc:
                has_error = True
                self._counters["input_errors"] += 1
                try:
                    reset_events = parser.reset(max(last_parser_timestamp_ns + 1, last_raw_timestamp_ns + 1))
                    for ce in reset_events:
                        self._counters["control_events_emitted"] += 1
                        self._counters["synthetic_releases_emitted"] += 1
                        yield ce
                except Exception:
                    self._counters["parser_errors"] += 1
                raise ObservationInputError("Input reading failed") from exc
                
            except ObservationError:
                has_error = True
                raise
                
            except Exception as exc:
                has_error = True
                self._counters["parser_errors"] += 1
                raise ObservationConfigurationError("Unexpected pipeline error") from exc
                
        finally:
            if self._stream is not None:
                try:
                    await self._stream.close()
                except Exception as close_exc:
                    if not has_error:
                        self._state = ObservationState.CLOSED
                        raise ObservationError("Stream close failed") from close_exc
            self._state = ObservationState.CLOSED
