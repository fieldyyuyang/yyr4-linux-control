import asyncio
import unittest
from typing import Tuple, Optional

from yyr4_linux_control.control.actions import (
    ActionPlan, ResolutionStatus, HotkeyAction, TextAction,
    CommandAction, DelayAction, NoOpAction, DebugLogAction
)
from yyr4_linux_control.control.models import OfficialControl
from yyr4_linux_control.execution.engine import ActionExecutionEngine
from yyr4_linux_control.execution.models import ExecutionStatus
from yyr4_linux_control.execution.errors import BackendUnavailableError, CommandExecutionError
from yyr4_linux_control.execution.interfaces import DesktopInputBackend, CommandRunner, DelayBackend, DebugLogBackend

class FakeDesktopInputBackend(DesktopInputBackend):
    def __init__(self, available=True, fail_on=None):
        self._available = available
        self.fail_on = fail_on

    def availability(self) -> bool:
        return self._available

    async def send_hotkey(self, keys: Tuple[str, ...]) -> None:
        if self.fail_on == "hotkey":
            raise BackendUnavailableError("simulated failure")

    async def type_text(self, value: str) -> None:
        if self.fail_on == "text":
            raise BackendUnavailableError("simulated failure")

class FakeCommandRunner(CommandRunner):
    def __init__(self, exit_code=0):
        self.exit_code = exit_code

    async def run(self, argv: Tuple[str, ...], timeout_seconds: Optional[int]) -> Tuple[int, bytes, bytes]:
        if argv[0] == "sleep":
            await asyncio.sleep(0.1)
        return self.exit_code, b"", b""

class FakeDelayBackend(DelayBackend):
    async def delay(self, milliseconds: int) -> None:
        await asyncio.sleep(0.01)

class FakeDebugLogBackend(DebugLogBackend):
    def __init__(self):
        self.messages = []

    def emit(self, message: str) -> None:
        self.messages.append(message)

class TestExecutionEngine(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.desktop = FakeDesktopInputBackend()
        self.command = FakeCommandRunner()
        self.delay = FakeDelayBackend()
        self.debug = FakeDebugLogBackend()
        self.engine = ActionExecutionEngine(self.desktop, self.command, self.delay, self.debug)

    async def test_unmapped_plan_is_skipped(self):
        plan = ActionPlan(OfficialControl.A1, ResolutionStatus.UNMAPPED, (HotkeyAction(("A",)),))
        res = await self.engine.execute(plan)
        self.assertEqual(res.execution_status, ExecutionStatus.SKIPPED)
        self.assertEqual(len(res.step_results), 1)
        self.assertEqual(res.step_results[0].status, ExecutionStatus.SKIPPED)

    async def test_successful_execution(self):
        plan = ActionPlan(
            control=OfficialControl.A1,
            resolution_status=ResolutionStatus.CONFIGURED,
            steps=(
                HotkeyAction(("A",)),
                TextAction("hello"),
                CommandAction(("echo",)),
                DelayAction(10),
                NoOpAction(),
                DebugLogAction("test log")
            )
        )
        res = await self.engine.execute(plan)
        self.assertEqual(res.execution_status, ExecutionStatus.SUCCESS)
        self.assertEqual(res.completed_steps, 6)
        self.assertEqual(len(self.debug.messages), 1)
        self.assertTrue(res.duration_seconds >= 0)

    async def test_stop_on_failure(self):
        self.command.exit_code = 1
        plan = ActionPlan(
            control=OfficialControl.A1,
            resolution_status=ResolutionStatus.CONFIGURED,
            steps=(
                CommandAction(("fail",)),
                NoOpAction()
            )
        )
        res = await self.engine.execute(plan)
        self.assertEqual(res.execution_status, ExecutionStatus.FAILED)
        self.assertEqual(res.completed_steps, 0)
        self.assertEqual(res.step_results[0].status, ExecutionStatus.FAILED)
        self.assertEqual(res.step_results[1].status, ExecutionStatus.SKIPPED)

    async def test_cancellation(self):
        plan = ActionPlan(
            control=OfficialControl.A1,
            resolution_status=ResolutionStatus.CONFIGURED,
            steps=(
                CommandAction(("sleep",)),
                NoOpAction()
            )
        )
        task = asyncio.create_task(self.engine.execute(plan))
        await asyncio.sleep(0.05)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
