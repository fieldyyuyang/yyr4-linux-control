from __future__ import annotations

class DeviceDiscoveryError(Exception):
    """Base exception for device discovery errors."""
    pass

class DeviceNotFoundError(DeviceDiscoveryError):
    """Raised when the expected device cannot be found."""
    pass

class DeviceAmbiguousError(DeviceDiscoveryError):
    """Raised when multiple devices match the criteria but only one is expected."""
    pass

class DeviceIdentityMismatchError(DeviceDiscoveryError):
    """Raised when a device matches some criteria but fails strict identity checks."""
    pass

class DeviceIncompleteError(DeviceDiscoveryError):
    """Raised when a device is found but is missing required interfaces (e.g., keyboard but no mouse)."""
    pass

class DependencyUnavailableError(Exception):
    """Raised when an optional dependency is required but not installed."""
    pass
