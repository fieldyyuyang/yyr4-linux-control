import unittest
from yyr4_linux_control.execution.models import ExecutionStatus, StepExecutionResult, ActionExecutionResult
from yyr4_linux_control.control.models import OfficialControl
from yyr4_linux_control.control.actions import ResolutionStatus

class TestExecutionModels(unittest.TestCase):
    def test_step_execution_result_to_dict(self):
        res = StepExecutionResult(
            step_index=0,
            action_type="HotkeyAction",
            status=ExecutionStatus.SUCCESS,
            started_at=10.0,
            finished_at=11.5,
            duration_seconds=1.5,
            exit_code=0,
            message=None,
            stdout=b"hello",
            stderr=b"world",
            output_truncated=False
        )
        d = res.to_dict()
        self.assertEqual(d["step_index"], 0)
        self.assertEqual(d["action_type"], "HotkeyAction")
        self.assertEqual(d["status"], "SUCCESS")
        self.assertEqual(d["duration_seconds"], 1.5)
        self.assertEqual(d["exit_code"], 0)
        self.assertEqual(d["stdout"], "hello")
        self.assertEqual(d["stderr"], "world")

    def test_action_execution_result_to_dict(self):
        res = ActionExecutionResult(
            control=OfficialControl.A1,
            plan_resolution_status=ResolutionStatus.CONFIGURED,
            execution_status=ExecutionStatus.FAILED,
            started_at=10.0,
            finished_at=11.5,
            duration_seconds=1.5,
            total_steps=1,
            completed_steps=0,
            step_results=()
        )
        d = res.to_dict()
        self.assertEqual(d["control"], "A1")
        self.assertEqual(d["plan_resolution_status"], "CONFIGURED")
        self.assertEqual(d["execution_status"], "FAILED")
        self.assertEqual(d["total_steps"], 1)
        self.assertEqual(d["completed_steps"], 0)
        self.assertEqual(d["step_results"], [])
