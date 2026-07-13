from typing import AsyncIterator
import logging

from yyr4_linux_control.control.models import OfficialControlEvent
from yyr4_linux_control.integration.composition import build_linux_observation_pipeline
from yyr4_linux_control.integration.errors import IntegrationDependencyError
from yyr4_linux_control.observation.errors import ObservationDiscoveryError, ObservationInputError, ObservationConfigurationError
from yyr4_linux_control.device.errors import DeviceDiscoveryError

from .interfaces import InputSession, InputSessionFactory
from .errors import RecoverableSessionError, FatalRuntimeError

logger = logging.getLogger("yyr4_linux_control.daemon")

class ProductionInputSession(InputSession):
    def __init__(self, include_mouse: bool = True):
        self._include_mouse = include_mouse
        self._pipeline = None

    async def observe(self) -> AsyncIterator[OfficialControlEvent]:
        try:
            # Build new pipeline per session
            comp = build_linux_observation_pipeline(include_mouse=self._include_mouse)
            self._pipeline = comp.pipeline
        except IntegrationDependencyError as e:
            raise FatalRuntimeError(f"Missing system dependencies: {e}") from e

        try:
            async for ctrl_event in self._pipeline.observe():
                yield OfficialControlEvent.from_control_event(ctrl_event)
        except (ObservationDiscoveryError, ObservationInputError) as e:
            raise RecoverableSessionError(f"Recoverable session error: {e}") from e
        except ObservationConfigurationError as e:
            raise FatalRuntimeError(f"Fatal observation configuration error: {e}") from e
        except Exception as e:
            raise FatalRuntimeError(f"Unexpected observation error: {e}") from e

    async def close(self) -> None:
        if self._pipeline:
            await self._pipeline.close()

class ProductionInputSessionFactory(InputSessionFactory):
    def __init__(self, include_mouse: bool = True):
        self._include_mouse = include_mouse

    def create_session(self) -> InputSession:
        return ProductionInputSession(include_mouse=self._include_mouse)
