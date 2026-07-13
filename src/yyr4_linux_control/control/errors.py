class ControlError(Exception):
    """Base class for all control errors."""
    pass

class UnsupportedSchemaVersionError(ControlError):
    pass

class ConfigSyntaxError(ControlError):
    pass

class ConfigValidationError(ControlError):
    def __init__(self, message: str, path: str = ""):
        prefix = f"At {path}: " if path else ""
        super().__init__(f"{prefix}{message}")
        self.path = path

class UnknownControlError(ConfigValidationError):
    pass

class UnknownActionTypeError(ConfigValidationError):
    pass

class InvalidActionError(ConfigValidationError):
    pass

class MacroDepthExceededError(ControlError):
    pass

class MacroStepLimitExceededError(ControlError):
    pass

class ResolutionError(ControlError):
    pass
