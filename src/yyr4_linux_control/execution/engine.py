import asyncio
import time
from typing import List, Optional

from ..control.actions import (
    ActionPlan, Action, HotkeyAction, TextAction, CommandAction,
    DelayAction, NoOpAction, DebugLogAction, ResolutionStatus,
    SetLayerAction, NextLayerAction, PreviousLayerAction, SetProfileAction
)
from .models import ExecutionStatus, StepExecutionResult, ActionExecutionResult
from .interfaces import DesktopInputBackend, CommandRunner, DelayBackend, DebugLogBackend, RuntimeControlBackend
from .errors import (
    BackendUnavailableError, DesktopInputError, CommandRejectedError,
    CommandExecutionError, CommandTimeoutError, ExecutionCancelledError
)

class ActionExecutionEngine:
    def __init__(
        self,
        desktop_backend: DesktopInputBackend,
        command_runner: CommandRunner,
        delay_backend: DelayBackend,
        debug_log_backend: DebugLogBackend,
        runtime_backend: Optional[RuntimeControlBackend] = None
    ):
        self.desktop_backend = desktop_backend
        self.command_runner = command_runner
        self.delay_backend = delay_backend
        self.debug_log_backend = debug_log_backend
        self.runtime_backend = runtime_backend

    async def execute(self, plan: ActionPlan) -> ActionExecutionResult:
        started_at = time.monotonic()
        step_results: List[StepExecutionResult] = []
        
        # Determine initial engine status
        if plan.resolution_status == ResolutionStatus.UNMAPPED:
            overall_status = ExecutionStatus.SKIPPED
        else:
            overall_status = ExecutionStatus.SUCCESS

        total_steps = len(plan.steps)
        completed_steps = 0

        for i, step in enumerate(plan.steps):
            if overall_status not in (ExecutionStatus.SUCCESS,):
                # If a previous step failed or we are skipped, mark remaining as skipped
                step_results.append(StepExecutionResult(
                    step_index=i,
                    action_type=type(step).__name__,
                    status=ExecutionStatus.SKIPPED,
                    started_at=time.monotonic(),
                    finished_at=time.monotonic(),
                    duration_seconds=0.0
                ))
                continue

            step_started_at = time.monotonic()
            step_status = ExecutionStatus.SUCCESS
            exit_code = None
            message = None
            stdout = None
            stderr = None
            output_truncated = False

            try:
                # We check for cancellation at the start of each step
                await asyncio.sleep(0)
                
                if isinstance(step, HotkeyAction):
                    if not self.desktop_backend.availability():
                        raise BackendUnavailableError("Desktop input backend is unavailable")
                    await self.desktop_backend.send_hotkey(step.keys)
                
                elif isinstance(step, TextAction):
                    if not self.desktop_backend.availability():
                        raise BackendUnavailableError("Desktop input backend is unavailable")
                    await self.desktop_backend.type_text(step.value)
                
                elif isinstance(step, CommandAction):
                    code, out, err = await self.command_runner.run(step.argv, step.timeout_seconds)
                    exit_code = code
                    stdout = out
                    stderr = err
                    if b"[TRUNCATED]" in out or b"[TRUNCATED]" in err:
                        output_truncated = True
                    if code != 0:
                        raise CommandExecutionError(f"Command exited with non-zero code {code}")
                        
                elif isinstance(step, DelayAction):
                    await self.delay_backend.delay(step.milliseconds)
                    
                elif isinstance(step, NoOpAction):
                    pass
                    
                elif isinstance(step, DebugLogAction):
                    self.debug_log_backend.emit(step.message)
                    
                elif isinstance(step, SetLayerAction):
                    if not self.runtime_backend:
                        raise BackendUnavailableError("Runtime backend is unavailable")
                    await self.runtime_backend.set_layer(step.layer)
                    
                elif isinstance(step, NextLayerAction):
                    if not self.runtime_backend:
                        raise BackendUnavailableError("Runtime backend is unavailable")
                    await self.runtime_backend.next_layer()
                    
                elif isinstance(step, PreviousLayerAction):
                    if not self.runtime_backend:
                        raise BackendUnavailableError("Runtime backend is unavailable")
                    await self.runtime_backend.previous_layer()
                    
                elif isinstance(step, SetProfileAction):
                    if not self.runtime_backend:
                        raise BackendUnavailableError("Runtime backend is unavailable")
                    await self.runtime_backend.set_profile(step.profile)
                    
            except asyncio.CancelledError:
                step_status = ExecutionStatus.CANCELLED
                message = "Cancelled"
                overall_status = ExecutionStatus.CANCELLED
                raise
            except BackendUnavailableError as e:
                step_status = ExecutionStatus.BACKEND_UNAVAILABLE
                message = str(e)
                overall_status = ExecutionStatus.BACKEND_UNAVAILABLE
            except DesktopInputError as e:
                step_status = ExecutionStatus.FAILED
                message = str(e)
                overall_status = ExecutionStatus.FAILED
            except CommandRejectedError as e:
                step_status = ExecutionStatus.FAILED
                message = str(e)
                overall_status = ExecutionStatus.FAILED
            except CommandTimeoutError as e:
                step_status = ExecutionStatus.TIMED_OUT
                message = str(e)
                overall_status = ExecutionStatus.TIMED_OUT
            except CommandExecutionError as e:
                step_status = ExecutionStatus.FAILED
                message = str(e)
                overall_status = ExecutionStatus.FAILED
            except ExecutionCancelledError as e:
                step_status = ExecutionStatus.CANCELLED
                message = str(e)
                overall_status = ExecutionStatus.CANCELLED
            except Exception as e:
                # Any other unexpected error is a failure
                step_status = ExecutionStatus.FAILED
                message = f"Unexpected error: {type(e).__name__}: {e}"
                overall_status = ExecutionStatus.FAILED
            
            step_finished_at = time.monotonic()
            step_results.append(StepExecutionResult(
                step_index=i,
                action_type=type(step).__name__,
                status=step_status,
                started_at=step_started_at,
                finished_at=step_finished_at,
                duration_seconds=max(0.0, step_finished_at - step_started_at),
                exit_code=exit_code,
                message=message,
                stdout=stdout,
                stderr=stderr,
                output_truncated=output_truncated
            ))

            if step_status == ExecutionStatus.SUCCESS:
                completed_steps += 1

        finished_at = time.monotonic()
        return ActionExecutionResult(
            control=plan.control,
            plan_resolution_status=plan.resolution_status,
            execution_status=overall_status,
            started_at=started_at,
            finished_at=finished_at,
            duration_seconds=max(0.0, finished_at - started_at),
            total_steps=total_steps,
            completed_steps=completed_steps,
            step_results=tuple(step_results)
        )
