"""Production composition for Linux read-only observation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from yyr4_linux_control.device.discovery import YYR4Identity
from yyr4_linux_control.observation.interfaces import DeviceSelector, RawInputStreamFactory, TransportParserFactory
from yyr4_linux_control.observation.pipeline import ObservationPipeline
from yyr4_linux_control.observation.interfaces import RawInputStream
from yyr4_linux_control.integration.errors import IntegrationDependencyError


class LinuxRawInputStreamFactory(RawInputStreamFactory):
    """Adapter to create EvdevInputAdapters safely."""
    
    def __init__(
        self,
        event_device_factory,  # EventDeviceFactory from yyr4_linux_control.input.evdev
        clock,                 # MonotonicClock
        include_mouse: bool = True
    ) -> None:
        self._event_device_factory = event_device_factory
        self._clock = clock
        self._include_mouse = include_mouse

    def create(self, identity: YYR4Identity) -> RawInputStream:
        from yyr4_linux_control.input.evdev_adapter import EvdevInputAdapter
        return EvdevInputAdapter(
            identity=identity,
            factory=self._event_device_factory,
            clock=self._clock,
            include_mouse=self._include_mouse,
        )


@dataclass(frozen=True)
class LinuxObservationComposition:
    """Read-only container for Linux production components."""
    selector: DeviceSelector
    input_factory: RawInputStreamFactory
    parser_factory: TransportParserFactory
    pipeline: ObservationPipeline


def build_linux_observation_pipeline(
    include_mouse: bool = True,
    transport_source_id: str = "yyr4:keyboard"
) -> LinuxObservationComposition:
    """Builds the Linux observation pipeline and its dependencies.
    
    This factory is the only place where Linux-specific optional dependencies 
    (pyudev, evdev) are explicitly imported. Calling this when dependencies 
    are missing will raise an IntegrationDependencyError.
    """
    try:
        import pyudev
        from yyr4_linux_control.device.linux_udev import LinuxUdevDiscoveryBackend
        from yyr4_linux_control.device.discovery import YYR4DeviceDiscovery
        from yyr4_linux_control.input.evdev_adapter import LinuxEvdevDeviceFactory
        from yyr4_linux_control.input.interfaces import SystemMonotonicClock
        from yyr4_linux_control.observation.interfaces import DefaultTransportParserFactory
    except ImportError as e:
        raise IntegrationDependencyError(f"Missing required Linux dependencies: {e}") from e

    backend = LinuxUdevDiscoveryBackend()
    selector = YYR4DeviceDiscovery(backend)

    try:
        event_device_factory = LinuxEvdevDeviceFactory()
    except Exception as e:
        # Catch DependencyUnavailableError or similar from lazy load
        raise IntegrationDependencyError(f"Missing required Linux dependencies: {e}") from e

    clock = SystemMonotonicClock()
    input_factory = LinuxRawInputStreamFactory(
        event_device_factory=event_device_factory,
        clock=clock,
        include_mouse=include_mouse
    )

    parser_factory = DefaultTransportParserFactory()

    pipeline = ObservationPipeline(
        selector=selector,
        input_factory=input_factory,
        parser_factory=parser_factory,
        transport_source_id=transport_source_id,
    )

    return LinuxObservationComposition(
        selector=selector,
        input_factory=input_factory,
        parser_factory=parser_factory,
        pipeline=pipeline,
    )
