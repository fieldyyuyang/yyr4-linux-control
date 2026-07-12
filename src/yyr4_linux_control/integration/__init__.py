"""Integration subsystem for real device observation and validation."""

from __future__ import annotations

from yyr4_linux_control.integration.preflight import (
    RuntimePreflight,
    DependencyStatus,
    PermissionCheck,
    IdentityPermissionChecker,
    FilesystemIdentityPermissionChecker,
    check_runtime_preflight,
)

from yyr4_linux_control.integration.errors import (
    IntegrationError,
    IntegrationConfigurationError,
    IntegrationDependencyError,
    IntegrationPermissionError,
    IntegrationSafetyError,
    ProbeError,
    ProbeTimeoutError,
    ProbeLimitReached,
)

from yyr4_linux_control.integration.composition import (
    LinuxRawInputStreamFactory,
    LinuxObservationComposition,
    build_linux_observation_pipeline,
)

from yyr4_linux_control.integration.probe import (
    ProbeAuthorization,
    ProbeConfig,
    ProbeEvent,
    ProbeResult,
    ProbeTermination,
    ProbeRunner,
    validate_probe_authorization,
)

__all__ = [
    "RuntimePreflight",
    "DependencyStatus",
    "PermissionCheck",
    "IdentityPermissionChecker",
    "FilesystemIdentityPermissionChecker",
    "check_runtime_preflight",
    
    "IntegrationError",
    "IntegrationConfigurationError",
    "IntegrationDependencyError",
    "IntegrationPermissionError",
    "IntegrationSafetyError",
    "ProbeError",
    "ProbeTimeoutError",
    "ProbeLimitReached",
    
    "LinuxRawInputStreamFactory",
    "LinuxObservationComposition",
    "build_linux_observation_pipeline",
    
    "ProbeAuthorization",
    "ProbeConfig",
    "ProbeEvent",
    "ProbeResult",
    "ProbeTermination",
    "ProbeRunner",
    "validate_probe_authorization",
]
