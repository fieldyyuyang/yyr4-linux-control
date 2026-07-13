class ExecutionError(Exception):
    """Base class for all execution errors."""
    pass

class BackendUnavailableError(ExecutionError):
    """Raised when a required backend is unavailable."""
    pass

class DesktopInputError(ExecutionError):
    """Raised when a desktop input operation fails or is unsupported."""
    pass

class CommandRejectedError(ExecutionError):
    """Raised when a command is rejected by the execution policy."""
    pass

class CommandExecutionError(ExecutionError):
    """Raised when a command fails to execute or returns a non-zero exit code."""
    pass

class CommandTimeoutError(ExecutionError):
    """Raised when a command execution exceeds the allowed timeout."""
    pass

class ExecutionCancelledError(ExecutionError):
    """Raised when the execution is cancelled."""
    pass
