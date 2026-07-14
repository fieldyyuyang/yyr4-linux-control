import asyncio
import json
import unittest
from pathlib import Path
from yyr4_linux_control.daemon.runtime import DaemonRuntime
from yyr4_linux_control.management.server import ManagementServer
from yyr4_linux_control.management.client import ManagementClient
from yyr4_linux_control.control.config import LayeredControlConfig
from yyr4_linux_control.control.models import ProfileId, LayerId, ProfileConfig, LayerConfig
from yyr4_linux_control.daemon.models import RuntimeSettings, ExecutionMode, DaemonState
from yyr4_linux_control.daemon.context import ContextChangeSource
from yyr4_linux_control.input.interfaces import MonotonicClock

class FakeClock(MonotonicClock):
    def now(self): return 0.0
    def monotonic(self): return 0.0
    async def sleep(self, seconds: float): pass

class FakeActionExecutor:
    def execute(self, plan): pass

class FakeSessionFactory:
    def __init__(self): pass

class TestManagementContext(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.socket_path = Path("/tmp/yyr4_test_mgmt_context.sock")
        if self.socket_path.exists():
            self.socket_path.unlink()
            
        settings = RuntimeSettings(
            config_path="/tmp/fake.toml",
            execution_mode=ExecutionMode.DRY_RUN,
            queue_capacity=10,
        )
        
        self.runtime = DaemonRuntime(settings, FakeSessionFactory(), FakeActionExecutor(), FakeClock())
        # Manually init enough for test
        self.runtime._state = DaemonState.RUNNING
        
        config = LayeredControlConfig(
            schema_version=2,
            default_profile=ProfileId("default"),
            initial_layer=LayerId("general"),
            profiles={
                ProfileId("default"): ProfileConfig(profile_id=ProfileId("default"), layers={
                    LayerId("general"): LayerConfig(layer_id=LayerId("general"), controls={}),
                    LayerId("layer_1"): LayerConfig(layer_id=LayerId("layer_1"), controls={}),
                }),
                ProfileId("gaming"): ProfileConfig(profile_id=ProfileId("gaming"), layers={
                    LayerId("general"): LayerConfig(layer_id=LayerId("general"), controls={})
                })
            }
        )
        
        from yyr4_linux_control.control.actions import LayeredActionResolver
        self.runtime._action_resolver = LayeredActionResolver(config)
        from yyr4_linux_control.daemon.context import RuntimeContextManager
        self.runtime._context = RuntimeContextManager(ProfileId("default"), LayerId("general"), FakeClock())
        self.runtime._context.set_config(config)
        
        self.server = ManagementServer(self.runtime, self.socket_path)
        # Monkey patch check_peer_uid for test
        import yyr4_linux_control.management.server as server_mod
        server_mod.check_peer_uid = lambda sock: True
        
        await self.server.start()
        self.client = ManagementClient(self.socket_path)

    async def asyncTearDown(self):
        await self.server.stop()

    async def test_get_context(self):
        resp = await self.client.send_request("get-context")
        self.assertTrue(resp.ok)
        self.assertEqual(resp.result["selected_profile"], "default")
        self.assertEqual(resp.result["active_layer"], "general")

    async def test_set_layer(self):
        resp = await self.client.send_request("set-layer", {"layer": "layer_1"})
        self.assertTrue(resp.ok)
        self.assertTrue(resp.result["changed"])
        self.assertEqual(resp.result["active_layer"], "layer_1")
        
        # Verify get-context reflects it
        resp2 = await self.client.send_request("get-context")
        self.assertEqual(resp2.result["active_layer"], "layer_1")
        self.assertEqual(resp2.result["last_change_source"], "management_cli")

    async def test_next_layer(self):
        resp = await self.client.send_request("next-layer")
        self.assertTrue(resp.ok)
        self.assertEqual(resp.result["active_layer"], "layer_1")

    async def test_previous_layer(self):
        resp = await self.client.send_request("previous-layer")
        self.assertTrue(resp.ok)
        self.assertEqual(resp.result["active_layer"], "layer_1")

    async def test_set_profile(self):
        resp = await self.client.send_request("set-profile", {"profile": "gaming"})
        self.assertTrue(resp.ok)
        self.assertTrue(resp.result["changed"])
        self.assertEqual(resp.result["selected_profile"], "gaming")

    async def test_set_invalid_profile(self):
        resp = await self.client.send_request("set-profile", {"profile": "unknown"})
        self.assertFalse(resp.ok)
        self.assertEqual(resp.error["code"], "INVALID_PARAM")

if __name__ == '__main__':
    unittest.main()
