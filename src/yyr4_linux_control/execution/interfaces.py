import asyncio
from typing import Tuple, Optional, Protocol
from abc import ABC, abstractmethod

class DesktopInputBackend(ABC):
    @abstractmethod
    def availability(self) -> bool:
        """Returns True if the backend is available in the current environment."""
        pass

    @abstractmethod
    async def send_hotkey(self, keys: Tuple[str, ...]) -> None:
        """Sends a hotkey combination."""
        pass

    @abstractmethod
    async def type_text(self, value: str) -> None:
        """Types the given text literally."""
        pass

class CommandRunner(ABC):
    @abstractmethod
    async def run(self, argv: Tuple[str, ...], timeout_seconds: Optional[int]) -> Tuple[int, bytes, bytes]:
        """
        Runs a command and returns (exit_code, stdout, stderr).
        Raises CommandRejectedError, CommandTimeoutError, or ExecutionCancelledError.
        """
        pass

class DelayBackend(ABC):
    @abstractmethod
    async def delay(self, milliseconds: int) -> None:
        """
        Waits for the specified duration. Can be cancelled by cancelling the current asyncio Task.
        """
        pass

class DebugLogBackend(ABC):
    @abstractmethod
    def emit(self, message: str) -> None:
        """Emits a debug log message."""
        pass

class RuntimeControlBackend(Protocol):
    async def set_layer(self, layer_id: str) -> bool:
        ...

    async def next_layer(self) -> bool:
        ...

    async def previous_layer(self) -> bool:
        ...

    async def set_profile(self, profile_id: str) -> bool:
        ...
