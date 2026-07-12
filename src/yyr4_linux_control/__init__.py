__version__ = "0.1.0.dev0"

from .domain.controls import PhysicalControl, ControlKind, ControlPhase
from .domain.events import RawKeyEvent, ControlEvent
from .transport.codebook import DEFAULT_CODEBOOK, TransportCode, Codebook
from .transport.parser import TransportParser

from .device import (
    YYR4Identity,
    InputInterface,
    InterfaceRole,
    UdevInputRecord,
    YYR4DeviceDiscovery,
    DiscoveryBackend,
    LinuxUdevDiscoveryBackend,
)
from .input import (
    KernelInputEvent,
    EventDeviceHandle,
    EventDeviceFactory,
    EvdevInputAdapter,
    LinuxEvdevDeviceFactory,
    SystemMonotonicClock,
)
from .observation import (
    ObservationPipeline,
    ObservationState,
    ObservationDiagnostics,
    DeviceSelector,
    RawInputStream,
    RawInputStreamFactory,
    TransportParserFactory,
    DefaultTransportParserFactory,
    ObservationError,
    ObservationStateError,
    ObservationDiscoveryError,
    ObservationInputError,
    ObservationConfigurationError,
)

from .integration import (
    RuntimePreflight,
    ProbeConfig,
    ProbeResult,
    ProbeRunner,
)

__all__ = [
    "PhysicalControl",
    "ControlKind",
    "ControlPhase",
    "RawKeyEvent",
    "ControlEvent",
    "DEFAULT_CODEBOOK",
    "TransportCode",
    "Codebook",
    "TransportParser",
    "YYR4Identity",
    "InputInterface",
    "InterfaceRole",
    "UdevInputRecord",
    "YYR4DeviceDiscovery",
    "DiscoveryBackend",
    "LinuxUdevDiscoveryBackend",
    "KernelInputEvent",
    "EventDeviceHandle",
    "EventDeviceFactory",
    "EvdevInputAdapter",
    "LinuxEvdevDeviceFactory",
    "SystemMonotonicClock",
    "ObservationPipeline",
    "ObservationState",
    "ObservationDiagnostics",
    "DeviceSelector",
    "RawInputStream",
    "RawInputStreamFactory",
    "TransportParserFactory",
    "DefaultTransportParserFactory",
    "ObservationError",
    "ObservationStateError",
    "ObservationDiscoveryError",
    "ObservationInputError",
    "ObservationConfigurationError",
    "RuntimePreflight",
    "ProbeConfig",
    "ProbeResult",
    "ProbeRunner",
]
