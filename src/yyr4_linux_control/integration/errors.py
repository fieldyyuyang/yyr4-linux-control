"""Integration error classes."""

from __future__ import annotations

class IntegrationError(Exception):
    """Base exception for integration and preflight errors."""
    pass

class IntegrationConfigurationError(IntegrationError):
    """Raised when integration configuration is invalid."""
    pass

class IntegrationDependencyError(IntegrationError):
    """Raised when an optional dependency is missing."""
    pass

class IntegrationPermissionError(IntegrationError):
    """Raised when device permission checks fail."""
    pass

class IntegrationSafetyError(IntegrationError):
    """Raised when safety preconditions or explicit authorizations fail."""
    pass

class ProbeError(IntegrationError):
    """Base exception for probe runtime errors."""
    pass

class ProbeTimeoutError(ProbeError):
    """Raised when a probe operation times out. Used internally."""
    pass

class ProbeLimitReached(ProbeError):
    """Raised when a probe operation hits its event limit. Used internally."""
    pass
