class ObservationError(Exception):
    """Base class for observation errors."""
    pass

class ObservationStateError(ObservationError):
    """Raised when the pipeline state is invalid for the requested operation."""
    pass

class ObservationDiscoveryError(ObservationError):
    """Raised when device discovery fails."""
    pass

class ObservationInputError(ObservationError):
    """Raised when an error occurs reading input events."""
    pass

class ObservationConfigurationError(ObservationError):
    """Raised when parser configuration or feeding fails unexpectedly."""
    pass
