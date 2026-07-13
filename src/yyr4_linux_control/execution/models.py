from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Tuple, Optional, Dict, Any

from ..control.models import OfficialControl
from ..control.actions import ResolutionStatus

class ExecutionStatus(Enum):
    SUCCESS = auto()
    FAILED = auto()
    TIMED_OUT = auto()
    CANCELLED = auto()
    SKIPPED = auto()
    BACKEND_UNAVAILABLE = auto()

@dataclass(frozen=True)
class StepExecutionResult:
    step_index: int
    action_type: str
    status: ExecutionStatus
    started_at: float
    finished_at: float
    duration_seconds: float
    exit_code: Optional[int] = None
    message: Optional[str] = None
    stdout: Optional[bytes] = None
    stderr: Optional[bytes] = None
    output_truncated: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_index": self.step_index,
            "action_type": self.action_type,
            "status": self.status.name,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_seconds": self.duration_seconds,
            "exit_code": self.exit_code,
            "message": self.message,
            "stdout": self.stdout.decode('utf-8', errors='replace') if self.stdout is not None else None,
            "stderr": self.stderr.decode('utf-8', errors='replace') if self.stderr is not None else None,
            "output_truncated": self.output_truncated,
        }

@dataclass(frozen=True)
class ActionExecutionResult:
    control: OfficialControl
    plan_resolution_status: ResolutionStatus
    execution_status: ExecutionStatus
    started_at: float
    finished_at: float
    duration_seconds: float
    total_steps: int
    completed_steps: int
    step_results: Tuple[StepExecutionResult, ...] = field(default_factory=tuple)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "control": self.control.value,
            "plan_resolution_status": self.plan_resolution_status.name,
            "execution_status": self.execution_status.name,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_seconds": self.duration_seconds,
            "total_steps": self.total_steps,
            "completed_steps": self.completed_steps,
            "step_results": [r.to_dict() for r in self.step_results],
        }
