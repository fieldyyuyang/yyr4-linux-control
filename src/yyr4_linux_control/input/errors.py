from __future__ import annotations

class InputAdapterError(Exception):
    """Base exception for input adapter errors."""
    pass

class InputOpenError(InputAdapterError):
    """Raised when failing to open an input device."""
    pass

class InputReadError(InputAdapterError):
    """Raised when an error occurs during reading from an input device."""
    pass

class InputClosedError(InputAdapterError):
    """Raised when attempting to interact with a closed input device."""
    pass
