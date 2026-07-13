import unittest
from typing import Dict
from yyr4_linux_control.domain.controls import PhysicalControl, ControlKind
from yyr4_linux_control.domain.events import ControlPhase
from yyr4_linux_control.control.models import OfficialControl, OfficialControlEvent
from yyr4_linux_control.control.actions import (
    Action, HotkeyAction, TextAction, CommandAction, DelayAction, MacroAction, NoOpAction, DebugLogAction,
    ActionResolver, ActionPlan, ResolutionStatus, DryRunExecutor
)
from yyr4_linux_control.control.errors import ResolutionError

class TestControlActions(unittest.TestCase):
    def setUp(self):
        self.a1_event = OfficialControlEvent(
            control=OfficialControl.A1,
            phase=ControlPhase.DOWN,
            timestamp_ns=1000
        )
        self.a1_up_event = OfficialControlEvent(
            control=OfficialControl.A1,
            phase=ControlPhase.UP,
            timestamp_ns=1100
        )
        self.ap_event = OfficialControlEvent(
            control=OfficialControl.AP,
            phase=ControlPhase.DOWN,
            timestamp_ns=1000
        )

    def test_resolver_unmapped(self):
        config: Dict[OfficialControl, Action] = {}
        resolver = ActionResolver(config)
        plan = resolver.resolve(self.a1_event)
        self.assertEqual(plan.resolution_status, ResolutionStatus.UNMAPPED)
        self.assertEqual(plan.steps, ())

    def test_resolver_up_phase(self):
        config = {OfficialControl.A1: HotkeyAction(("A",))}
        resolver = ActionResolver(config)
        plan = resolver.resolve(self.a1_up_event)
        self.assertEqual(plan.resolution_status, ResolutionStatus.UNMAPPED)
        self.assertEqual(plan.steps, ())

    def test_resolver_hotkey(self):
        config = {OfficialControl.A1: HotkeyAction(("CTRL", "C"))}
        resolver = ActionResolver(config)
        plan = resolver.resolve(self.a1_event)
        self.assertEqual(plan.resolution_status, ResolutionStatus.CONFIGURED)
        self.assertEqual(len(plan.steps), 1)
        self.assertEqual(plan.steps[0], HotkeyAction(("CTRL", "C")))

    def test_resolver_noop_differs_from_unmapped(self):
        config = {OfficialControl.A1: NoOpAction()}
        resolver = ActionResolver(config)
        plan = resolver.resolve(self.a1_event)
        self.assertEqual(plan.resolution_status, ResolutionStatus.CONFIGURED)
        self.assertEqual(plan.steps, (NoOpAction(),))

    def test_resolver_macro_flattening(self):
        config = {
            OfficialControl.AP: MacroAction((
                HotkeyAction(("CTRL", "ENTER")),
                TextAction("---"),
                MacroAction((HotkeyAction(("CTRL", "ENTER")),))
            ))
        }
        resolver = ActionResolver(config)
        plan = resolver.resolve(self.ap_event)
        self.assertEqual(plan.resolution_status, ResolutionStatus.CONFIGURED)
        self.assertEqual(len(plan.steps), 3)
        self.assertEqual(plan.steps[0], HotkeyAction(("CTRL", "ENTER")))
        self.assertEqual(plan.steps[1], TextAction("---"))
        self.assertEqual(plan.steps[2], HotkeyAction(("CTRL", "ENTER")))

    def test_resolver_macro_depth_limit(self):
        def make_nested(depth):
            if depth == 0:
                return NoOpAction()
            return MacroAction((make_nested(depth - 1),))

        config = {OfficialControl.A1: make_nested(12)}
        resolver = ActionResolver(config, max_macro_depth=10)
        with self.assertRaisesRegex(ResolutionError, "Maximum macro depth exceeded"):
            resolver.resolve(self.a1_event)

    def test_resolver_macro_step_limit(self):
        config = {OfficialControl.A1: MacroAction(tuple(NoOpAction() for _ in range(101)))}
        resolver = ActionResolver(config, max_macro_steps=100)
        with self.assertRaisesRegex(ResolutionError, "Maximum macro step limit exceeded"):
            resolver.resolve(self.a1_event)

    def test_dry_run_executor(self):
        plan = ActionPlan(
            control=OfficialControl.A1,
            resolution_status=ResolutionStatus.CONFIGURED,
            steps=(
                HotkeyAction(("CTRL", "C")),
                TextAction("hello"),
                CommandAction(("echo", "world"), timeout_seconds=2),
                DelayAction(100),
                NoOpAction(),
                DebugLogAction("test")
            )
        )
        executor = DryRunExecutor()
        res = executor.execute(plan)
        
        self.assertEqual(res.control, OfficialControl.A1)
        self.assertEqual(res.status, "CONFIGURED")
        self.assertEqual(res.step_count, 6)
        self.assertEqual(res.steps[0], {"type": "hotkey", "keys": ("CTRL", "C")})
        self.assertEqual(res.steps[1], {"type": "text", "value": "hello"})
        self.assertEqual(res.steps[2], {"type": "command", "argv": ("echo", "world"), "timeout_seconds": 2})
        self.assertEqual(res.steps[3], {"type": "delay", "milliseconds": 100})
        self.assertEqual(res.steps[4], {"type": "noop"})
        self.assertEqual(res.steps[5], {"type": "debug_log", "message": "test"})

    def test_dry_run_empty(self):
        plan = ActionPlan(
            control=OfficialControl.A1,
            resolution_status=ResolutionStatus.UNMAPPED,
            steps=()
        )
        executor = DryRunExecutor()
        res = executor.execute(plan)
        self.assertEqual(res.step_count, 0)
        self.assertEqual(res.steps, [])
