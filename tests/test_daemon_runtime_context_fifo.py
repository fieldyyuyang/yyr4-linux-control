import unittest
import asyncio
from typing import Dict, Any

from yyr4_linux_control.domain.controls import PhysicalControl, ControlKind
from yyr4_linux_control.domain.events import ControlPhase
from yyr4_linux_control.control.models import OfficialControlEvent, OfficialControl
from yyr4_linux_control.control.models import LayeredControlConfig, ProfileConfig, LayerConfig, LayerId, ProfileId
from yyr4_linux_control.control.actions import HotkeyAction, MacroAction, TextAction, SetLayerAction, SetProfileAction, LayeredActionResolver
from yyr4_linux_control.control.config import load_control_config_from_string
from yyr4_linux_control.daemon.queue import DropNewestEventQueue
from yyr4_linux_control.daemon.context import RuntimeContextManager
from yyr4_linux_control.daemon.runtime import LayeredActionResolver
from yyr4_linux_control.execution.engine import ActionExecutionEngine
from yyr4_linux_control.execution.interfaces import DesktopInputBackend

class MockBackend(DesktopInputBackend):
    def __init__(self):
        self.executed = []

    def availability(self):
        return True

    async def send_hotkey(self, keys):
        self.executed.append(("hotkey", keys))

    async def type_text(self, text):
        self.executed.append(("text", text))

class MockRuntimeBackend:
    def __init__(self, ctx_manager: RuntimeContextManager):
        self.ctx = ctx_manager

    async def set_layer(self, layer: str):
        await self.ctx.set_layer(layer, "control_action")

    async def next_layer(self):
        await self.ctx.next_layer("control_action")

    async def previous_layer(self):
        await self.ctx.previous_layer("control_action")

    async def set_profile(self, profile: str):
        await self.ctx.set_profile(profile, "control_action")

class MockCommandRunner:
    async def run(self, argv, timeout_seconds): return (0, b"", b"")

class MockDelayBackend:
    async def delay(self, milliseconds): pass

class MockDebugLogBackend:
    def emit(self, message): pass

class TestDaemonRuntimeContextFifo(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        toml_content = """
schema_version = 2
default_profile = "default"
initial_layer = "general"

[profiles.default.layers.general.controls.A1.action]
type = "set_layer"
layer = "layer_1"

[profiles.default.layers.general.controls.A2.action]
type = "hotkey"
keys = ["G"]

[profiles.default.layers.general.controls.A3.action]
type = "set_profile"
profile = "media"

[profiles.default.layers.layer_1.controls.A2.action]
type = "hotkey"
keys = ["L1_G"]

[profiles.media.layers.general.controls.A2.action]
type = "hotkey"
keys = ["M_G"]
        """
        self.config = load_control_config_from_string(toml_content)
        self.ctx_manager = RuntimeContextManager(self.config.default_profile, self.config.initial_layer)
        self.ctx_manager.set_config(self.config)
        self.desktop_backend = MockBackend()
        self.runtime_backend = MockRuntimeBackend(self.ctx_manager)
        self.engine = ActionExecutionEngine(
            desktop_backend=self.desktop_backend,
            runtime_backend=self.runtime_backend,
            command_runner=MockCommandRunner(),
            delay_backend=MockDelayBackend(),
            debug_log_backend=MockDebugLogBackend()
        )

    async def test_fifo_layer_switch(self):
        # Enqueue A1 (set_layer layer_1) and A2 (which should resolve differently in general vs layer_1)
        queue = DropNewestEventQueue(capacity=10)
        queue.enqueue(OfficialControlEvent(
            control=OfficialControl.A1,
            phase=ControlPhase.DOWN,
            timestamp_ns=1
        ))
        queue.enqueue(OfficialControlEvent(
            control=OfficialControl.A2,
            phase=ControlPhase.DOWN,
            timestamp_ns=2
        ))

        # Consumer loop simulation
        for _ in range(2):
            event = await queue.dequeue()
            ctx_snap = await self.ctx_manager.snapshot()
            resolver = LayeredActionResolver(self.config)
            plan = resolver.resolve(event, ctx_snap.selected_profile, ctx_snap.active_layer)
            await self.engine.execute(plan)

        # First event changes layer. Second event must have executed L1_G instead of G
        self.assertEqual(self.desktop_backend.executed[0][1][0], "L1_G")
        snap = await self.ctx_manager.snapshot()
        self.assertEqual(snap.active_layer, LayerId("layer_1"))

    async def test_fifo_profile_switch(self):
        queue = DropNewestEventQueue(capacity=10)
        queue.enqueue(OfficialControlEvent(
            control=OfficialControl.A3,
            phase=ControlPhase.DOWN,
            timestamp_ns=1
        ))
        queue.enqueue(OfficialControlEvent(
            control=OfficialControl.A2,
            phase=ControlPhase.DOWN,
            timestamp_ns=2
        ))

        for _ in range(2):
            event = await queue.dequeue()
            ctx_snap = await self.ctx_manager.snapshot()
            resolver = LayeredActionResolver(self.config)
            plan = resolver.resolve(event, ctx_snap.selected_profile, ctx_snap.active_layer)
            await self.engine.execute(plan)

        self.assertEqual(self.desktop_backend.executed[0][1][0], "M_G")
        snap = await self.ctx_manager.snapshot()
        self.assertEqual(snap.selected_profile, ProfileId("media"))

if __name__ == "__main__":
    unittest.main()
