from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, Any, Optional

class ExecutionMode(str, Enum):
    DRY_RUN = "DRY_RUN"
    EXECUTE = "EXECUTE"

class DaemonState(str, Enum):
    CREATED = "CREATED"
    STARTING = "STARTING"
    CONNECTING = "CONNECTING"
    RUNNING = "RUNNING"
    RECONNECTING = "RECONNECTING"
    RELOADING = "RELOADING"
    STOPPING = "STOPPING"
    STOPPED = "STOPPED"
    FAILED = "FAILED"

@dataclass(frozen=True)
class RuntimeSettings:
    config_path: str
    execution_mode: ExecutionMode = ExecutionMode.DRY_RUN
    queue_capacity: int = 128
    reconnect_initial_seconds: float = 1.0
    reconnect_max_seconds: float = 60.0
    reconnect_multiplier: float = 2.0
    shutdown_grace_seconds: float = 5.0
    log_level: str = "INFO"

    def __post_init__(self):
        if self.queue_capacity < 1 or self.queue_capacity > 10000:
            raise ValueError("queue_capacity must be between 1 and 10000")
        if self.reconnect_initial_seconds <= 0:
            raise ValueError("reconnect_initial_seconds must be positive")
        if self.reconnect_max_seconds < self.reconnect_initial_seconds:
            raise ValueError("reconnect_max_seconds cannot be less than initial")
        if self.reconnect_multiplier < 1.0:
            raise ValueError("reconnect_multiplier must be >= 1.0")
        if self.shutdown_grace_seconds < 0:
            raise ValueError("shutdown_grace_seconds must be non-negative")

@dataclass(frozen=True)
class RuntimeSnapshot:
    state: DaemonState
    execution_mode: ExecutionMode
    started_at: float
    uptime_seconds: float
    config_revision: int
    
    # New M3.2 Context Fields
    selected_profile: str
    active_layer: str
    context_revision: int
    last_context_change_source: str
    
    current_session_active: bool
    sessions_started: int
    successful_sessions: int
    reconnect_attempts: int
    events_received: int
    plans_resolved: int
    plans_enqueued: int
    plans_executed: int
    executions_succeeded: int
    executions_failed: int
    unmapped_events: int
    queue_dropped: int
    discarded_on_shutdown: int
    config_reload_successes: int
    config_reload_failures: int
    last_error_code: Optional[str]
    queue_size: int
    queue_capacity: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "state": self.state.value,
            "execution_mode": self.execution_mode.value,
            "started_at": self.started_at,
            "uptime_seconds": self.uptime_seconds,
            "config_revision": self.config_revision,
            
            "selected_profile": self.selected_profile,
            "active_layer": self.active_layer,
            "context_revision": self.context_revision,
            "last_context_change_source": self.last_context_change_source,
            
            "current_session_active": self.current_session_active,
            "sessions_started": self.sessions_started,
            "successful_sessions": self.successful_sessions,
            "reconnect_attempts": self.reconnect_attempts,
            "events_received": self.events_received,
            "plans_resolved": self.plans_resolved,
            "plans_enqueued": self.plans_enqueued,
            "plans_executed": self.plans_executed,
            "executions_succeeded": self.executions_succeeded,
            "executions_failed": self.executions_failed,
            "unmapped_events": self.unmapped_events,
            "queue_dropped": self.queue_dropped,
            "discarded_on_shutdown": self.discarded_on_shutdown,
            "config_reload_successes": self.config_reload_successes,
            "config_reload_failures": self.config_reload_failures,
            "last_error_code": self.last_error_code,
            "queue_size": self.queue_size,
            "queue_capacity": self.queue_capacity,
        }
