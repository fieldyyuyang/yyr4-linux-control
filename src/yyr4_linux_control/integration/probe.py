"""Probe models and runner for safe, bounded device validation."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from enum import Enum, auto
from typing import Tuple, Optional, Any

from yyr4_linux_control.domain.controls import ControlPhase
from yyr4_linux_control.observation.pipeline import ObservationPipeline
from yyr4_linux_control.observation.diagnostics import ObservationDiagnostics
from yyr4_linux_control.observation.errors import ObservationError
from yyr4_linux_control.integration.errors import IntegrationConfigurationError, IntegrationSafetyError
import re

def _redact_error_message(msg: str) -> str:
    """Redact sensitive paths, serials, and control characters from error messages."""
    if not isinstance(msg, str):
        msg = str(msg)
    
    # Remove control characters (keep printable + space)
    msg = "".join(ch for ch in msg if ch.isprintable() or ch == ' ')
    
    # Redact common sensitive patterns
    patterns = [
        r"/home/[^/\s]+",
        r"/dev/input/[^\s]+",
        r"(?i)[0-9a-f]{4,}-[0-9a-f]{4,}-[0-9a-f]{4,}",  # Fake serial patterns
        r"(?i)[0-9a-f]{8,}" # Long hex strings
    ]
    for p in patterns:
        msg = re.sub(p, "<redacted>", msg)
        
    return msg


@dataclass(frozen=True)
class ProbeAuthorization:
    """Explicit authorization to run a real device probe."""
    acknowledge_read_only_device_access: bool
    acknowledge_current_profile_is_transport_profile: bool
    acknowledge_no_actions_will_run: bool


def validate_probe_authorization(auth: ProbeAuthorization) -> None:
    """Validates that all authorizations have been explicitly granted."""
    if not auth.acknowledge_read_only_device_access:
        raise IntegrationSafetyError("Missing acknowledgment for read-only device access")
    if not auth.acknowledge_current_profile_is_transport_profile:
        raise IntegrationSafetyError("Missing acknowledgment that transport profile is active")
    if not auth.acknowledge_no_actions_will_run:
        raise IntegrationSafetyError("Missing acknowledgment that no actions will run")


@dataclass(frozen=True)
class ProbeConfig:
    """Configuration for a bounded probe run."""
    max_control_events: int = 32
    timeout_seconds: float = 30.0
    include_synthetic: bool = True
    display_timestamps: bool = False
    redact_runtime_identity: bool = True

    def __post_init__(self):
        if type(self.max_control_events) is bool or not isinstance(self.max_control_events, int):
            raise IntegrationConfigurationError("max_control_events must be an integer")
        if not (1 <= self.max_control_events <= 256):
            raise IntegrationConfigurationError("max_control_events must be between 1 and 256")
        if type(self.timeout_seconds) is bool or not (isinstance(self.timeout_seconds, int) or isinstance(self.timeout_seconds, float)):
            raise IntegrationConfigurationError("timeout_seconds must be a number")
        if not (0 < self.timeout_seconds <= 300):
            raise IntegrationConfigurationError("timeout_seconds must be > 0 and <= 300")
        if type(self.include_synthetic) is not bool:
            raise IntegrationConfigurationError("include_synthetic must be a bool")
        if type(self.display_timestamps) is not bool:
            raise IntegrationConfigurationError("display_timestamps must be a bool")
        if type(self.redact_runtime_identity) is not bool:
            raise IntegrationConfigurationError("redact_runtime_identity must be a bool")


class ProbeTermination(Enum):
    """Reason for a probe run terminating."""
    NORMAL_EOF = auto()
    EVENT_LIMIT = auto()
    TIMEOUT = auto()
    CANCELLED = auto()
    OBSERVATION_ERROR = auto()
    EXTERNAL_CLOSE = auto()


@dataclass(frozen=True)
class ProbeEvent:
    """Safe, redacted event emitted by the probe."""
    sequence: int
    control_id: str
    vendor_name: str
    phase: ControlPhase
    synthetic: bool
    reason: Optional[str]
    timestamp_ns: Optional[int] = None


@dataclass(frozen=True)
class ProbeResult:
    """Result of a probe run."""
    termination: ProbeTermination
    events: Tuple[ProbeEvent, ...]
    elapsed_seconds: float
    diagnostics: ObservationDiagnostics
    error_type: Optional[str] = None
    error_message: Optional[str] = None


class ProbeRunner:
    """Executes a bounded, safe probe against an ObservationPipeline."""
    
    def __init__(
        self,
        pipeline: ObservationPipeline,
        config: ProbeConfig,
        monotonic_clock: Any,  # e.g., time.monotonic
        sleeper: Any = asyncio.sleep  # unused directly, but can be for timeouts
    ) -> None:
        self._pipeline = pipeline
        self._config = config
        self._clock = monotonic_clock
        self._sleeper = sleeper

    async def run(self) -> ProbeResult:
        """Run the probe until a limit, timeout, EOF, or error occurs."""
        start_time = self._clock()
        events = []
        sequence = 1
        termination = ProbeTermination.NORMAL_EOF
        error_type = None
        error_message = None

        try:
            async with asyncio.timeout(self._config.timeout_seconds):
                async for control_event in self._pipeline.observe():
                    if not self._config.include_synthetic and control_event.synthetic:
                        continue
                    
                    probe_event = ProbeEvent(
                        sequence=sequence,
                        control_id=control_event.control.control_id,
                        vendor_name=control_event.control.vendor_name,
                        phase=control_event.phase,
                        synthetic=control_event.synthetic,
                        reason=control_event.reason,
                        timestamp_ns=control_event.timestamp_ns if self._config.display_timestamps else None,
                    )
                    events.append(probe_event)
                    sequence += 1
                    
                    if len(events) >= self._config.max_control_events:
                        termination = ProbeTermination.EVENT_LIMIT
                        await self._pipeline.close()
                        break
        except asyncio.TimeoutError:
            termination = ProbeTermination.TIMEOUT
            await self._pipeline.close()
        except asyncio.CancelledError:
            termination = ProbeTermination.CANCELLED
            await self._pipeline.close()
            raise
        except ObservationError as e:
            termination = ProbeTermination.OBSERVATION_ERROR
            error_type = type(e).__name__
            error_message = _redact_error_message(str(e))
            await self._pipeline.close()
        except Exception as e:
            # We don't swallow programming errors, but we close the pipeline safely
            await self._pipeline.close()
            raise

        elapsed = self._clock() - start_time
        
        return ProbeResult(
            termination=termination,
            events=tuple(events),
            elapsed_seconds=elapsed,
            diagnostics=self._pipeline.snapshot_diagnostics(),
            error_type=error_type,
            error_message=error_message,
        )
