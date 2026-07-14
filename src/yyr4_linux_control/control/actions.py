from __future__ import annotations
from dataclasses import dataclass
from typing import Tuple, Optional, Any, Dict, List
from enum import Enum, auto

from .models import OfficialControl, OfficialControlEvent, LayerId, ProfileId, LayeredControlConfig
from ..domain.events import ControlPhase
from .errors import ResolutionError, MacroDepthExceededError, MacroStepLimitExceededError

@dataclass(frozen=True)
class Action:
    pass

@dataclass(frozen=True)
class HotkeyAction(Action):
    keys: Tuple[str, ...]

    def __post_init__(self):
        if not self.keys:
            raise ValueError("HotkeyAction must have at least one key")
        for k in self.keys:
            if not k:
                raise ValueError("Hotkey keys cannot be empty")

@dataclass(frozen=True)
class TextAction(Action):
    value: str

@dataclass(frozen=True)
class CommandAction(Action):
    argv: Tuple[str, ...]
    timeout_seconds: Optional[int] = None

    def __post_init__(self):
        if not self.argv:
            raise ValueError("CommandAction must have non-empty argv")
        for arg in self.argv:
            if not isinstance(arg, str) or not arg:
                raise ValueError("CommandAction argv items must be non-empty strings")

@dataclass(frozen=True)
class DelayAction(Action):
    milliseconds: int

    def __post_init__(self):
        if self.milliseconds < 0:
            raise ValueError("DelayAction milliseconds cannot be negative")

@dataclass(frozen=True)
class MacroAction(Action):
    steps: Tuple[Action, ...]


@dataclass(frozen=True)
class SetLayerAction(Action):
    layer: str

@dataclass(frozen=True)
class NextLayerAction(Action):
    pass

@dataclass(frozen=True)
class PreviousLayerAction(Action):
    pass

@dataclass(frozen=True)
class SetProfileAction(Action):
    profile: str

@dataclass(frozen=True)
class NoOpAction(Action):
    pass

@dataclass(frozen=True)
class DebugLogAction(Action):
    message: str


class ResolutionStatus(Enum):
    UNMAPPED = auto()
    CONFIGURED = auto()

@dataclass(frozen=True)
class ActionPlan:
    control: OfficialControl
    resolution_status: ResolutionStatus
    steps: Tuple[Action, ...]
    mapping_source: Optional[str] = None


class ActionResolver:
    """Resolves OfficialControlEvents against a validated configuration into an ActionPlan."""
    
    def __init__(self, config: Dict[OfficialControl, Action], max_macro_depth: int = 10, max_macro_steps: int = 100):
        self.config = config
        self.max_macro_depth = max_macro_depth
        self.max_macro_steps = max_macro_steps

    def resolve(self, event: OfficialControlEvent) -> ActionPlan:
        # Actions are triggered on DOWN phase
        if event.phase != ControlPhase.DOWN:
            return ActionPlan(
                control=event.control,
                resolution_status=ResolutionStatus.UNMAPPED,
                steps=()
            )

        action_def = self.config.get(event.control)
        if not action_def:
            return ActionPlan(
                control=event.control,
                resolution_status=ResolutionStatus.UNMAPPED,
                steps=()
            )

        try:
            steps = self._flatten_action(action_def, depth=0)
            return ActionPlan(
                control=event.control,
                resolution_status=ResolutionStatus.CONFIGURED,
                steps=tuple(steps)
            )
        except (MacroDepthExceededError, MacroStepLimitExceededError) as e:
            raise ResolutionError(str(e)) from e

    def _flatten_action(self, action: Action, depth: int) -> List[Action]:
        if depth > self.max_macro_depth:
            raise MacroDepthExceededError("Maximum macro depth exceeded")
            
        if isinstance(action, MacroAction):
            flat = []
            for step in action.steps:
                flat.extend(self._flatten_action(step, depth + 1))
                if len(flat) > self.max_macro_steps:
                    raise MacroStepLimitExceededError("Maximum macro step limit exceeded")
            return flat
        else:
            return [action]


class LayeredActionResolver:
    """Resolves events against a layered configuration, with profile and layer isolation and fallback."""

    def __init__(self, config: LayeredControlConfig, max_macro_depth: int = 10, max_macro_steps: int = 100):
        self.config = config
        self.max_macro_depth = max_macro_depth
        self.max_macro_steps = max_macro_steps

    def resolve(self, event: OfficialControlEvent, profile_id: ProfileId, layer_id: LayerId) -> ActionPlan:
        # Optimization and correctness: DOWN phase check is already in ActionResolver, 
        # but doing it here prevents unnecessary lookups.
        if event.phase != ControlPhase.DOWN:
            return ActionPlan(
                control=event.control,
                resolution_status=ResolutionStatus.UNMAPPED,
                steps=(),
                mapping_source="unmapped"
            )

        profile = self.config.profiles.get(profile_id)
        if not profile:
            raise ValueError(f"Unknown profile: {profile_id}")

        action = None
        mapping_source = "unmapped"
        
        # 1. Lookup in active layer
        active_layer = profile.layers.get(layer_id)
        if active_layer and event.control in active_layer.controls:
            action = active_layer.controls[event.control]
            mapping_source = "active_layer"

        # 2. Fallback to general layer
        if action is None and layer_id != LayerId.GENERAL:
            general_layer = profile.layers.get(LayerId.GENERAL)
            if general_layer and event.control in general_layer.controls:
                action = general_layer.controls[event.control]
                mapping_source = "general_fallback"

        # Delegate to single-layer ActionResolver logic
        synthetic_config = {event.control: action} if action is not None else {}
        inner_resolver = ActionResolver(
            config=synthetic_config,
            max_macro_depth=self.max_macro_depth,
            max_macro_steps=self.max_macro_steps
        )
        plan = inner_resolver.resolve(event)
        return ActionPlan(
            control=plan.control,
            resolution_status=plan.resolution_status,
            steps=plan.steps,
            mapping_source=mapping_source if plan.resolution_status == ResolutionStatus.CONFIGURED else "unmapped"
        )


@dataclass(frozen=True)
class DryRunExecutionResult:
    control: OfficialControl
    status: str
    step_count: int
    steps: List[Dict[str, Any]]

class DryRunExecutor:
    def execute(self, plan: ActionPlan) -> DryRunExecutionResult:
        step_logs = []
        for step in plan.steps:
            if isinstance(step, HotkeyAction):
                step_logs.append({"type": "hotkey", "keys": step.keys})
            elif isinstance(step, TextAction):
                step_logs.append({"type": "text", "value": step.value})
            elif isinstance(step, CommandAction):
                step_logs.append({"type": "command", "argv": step.argv, "timeout_seconds": step.timeout_seconds})
            elif isinstance(step, DelayAction):
                step_logs.append({"type": "delay", "milliseconds": step.milliseconds})
            elif isinstance(step, NoOpAction):
                step_logs.append({"type": "noop"})
            elif isinstance(step, DebugLogAction):
                step_logs.append({"type": "debug_log", "message": step.message})
            else:
                step_logs.append({"type": "unknown"})

        return DryRunExecutionResult(
            control=plan.control,
            status=plan.resolution_status.name,
            step_count=len(step_logs),
            steps=step_logs
        )
