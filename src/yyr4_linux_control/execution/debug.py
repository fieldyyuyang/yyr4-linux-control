import logging
from .interfaces import DebugLogBackend

logger = logging.getLogger("yyr4_linux_control.execution")

class PythonLoggingDebugLogBackend(DebugLogBackend):
    def emit(self, message: str) -> None:
        # Message may contain user configuration strings
        logger.debug(f"[User Debug Action] {message}")
