class DaemonError(Exception):
    """Base class for all daemon errors."""
    pass

class RecoverableSessionError(DaemonError):
    """Raised when an input session fails but should trigger a reconnect."""
    pass

class FatalRuntimeError(DaemonError):
    """Raised when the runtime encounters a non-recoverable error."""
    pass

class InvalidStateTransitionError(FatalRuntimeError):
    """Raised when an invalid state transition is requested."""
    pass
