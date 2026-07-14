import unittest
import asyncio
from unittest.mock import MagicMock
from yyr4_linux_control.daemon.runtime import DaemonRuntime
from yyr4_linux_control.daemon.models import RuntimeSettings, DaemonState
from yyr4_linux_control.control.models import OfficialControl, OfficialControlEvent
from yyr4_linux_control.domain.events import ControlPhase
import tempfile
import os

class TestDaemonLayeredCompatibility(unittest.IsolatedAsyncioTestCase):
    async def test_daemon_uses_default_profile(self):
        fd, temp_path = tempfile.mkstemp(suffix=".toml")
        try:
            with os.fdopen(fd, 'w') as f:
                f.write("""
schema_version = 2
default_profile = "prod"
initial_layer = "layer_1"

[profiles.prod.layers.general.controls.A1]
action = { type = "noop" }

[profiles.prod.layers.layer_1.controls.A1]
action = { type = "text", value = "hello" }
""")

            settings = RuntimeSettings(
                config_path=temp_path,
                execution_mode="DRY_RUN",
                queue_capacity=100
            )
            runtime = DaemonRuntime(
                settings=settings,
                input_session_factory=MagicMock(),
                action_executor=MagicMock()
            )
            resolver = await runtime._try_load_config()
            self.assertEqual(resolver.config.default_profile.value, "prod")
            self.assertEqual(resolver.config.initial_layer.value, "layer_1")
            
            # Simulate an event
            ev = OfficialControlEvent(control=OfficialControl.A1, phase=ControlPhase.DOWN, timestamp_ns=0)
            plan = resolver.resolve(ev, resolver.config.default_profile, resolver.config.initial_layer)
            self.assertEqual(plan.mapping_source, "active_layer")
            self.assertEqual(plan.steps[0].value, "hello")
        finally:
            os.remove(temp_path)
