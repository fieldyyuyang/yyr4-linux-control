import asyncio
from abc import ABC, abstractmethod
from typing import AsyncIterator

from yyr4_linux_control.control.models import OfficialControlEvent
from yyr4_linux_control.control.actions import ActionPlan
from yyr4_linux_control.execution.models import ActionExecutionResult

class InputSession(ABC):
    @abstractmethod
    async def observe(self) -> AsyncIterator[OfficialControlEvent]:
        """
        Yields official control events.
        May raise RecoverableSessionError or FatalRuntimeError.
        """
        yield # type: ignore

    @abstractmethod
    async def close(self) -> None:
        """Closes the session."""
        pass

class InputSessionFactory(ABC):
    @abstractmethod
    def create_session(self) -> InputSession:
        """Creates a new input session."""
        pass

class ActionPlanExecutor(ABC):
    @abstractmethod
    async def execute(self, plan: ActionPlan) -> ActionExecutionResult:
        """Executes the action plan."""
        pass

class Clock(ABC):
    @abstractmethod
    def monotonic(self) -> float:
        pass

    @abstractmethod
    async def sleep(self, seconds: float) -> None:
        pass

class SignalController(ABC):
    @abstractmethod
    def setup(self, loop: asyncio.AbstractEventLoop, on_stop, on_reload) -> None:
        """Sets up signal handlers."""
        pass
