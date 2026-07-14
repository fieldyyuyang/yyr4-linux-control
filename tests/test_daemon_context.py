import unittest
import asyncio
from yyr4_linux_control.daemon.context import RuntimeContextManager, ContextChangeSource
from yyr4_linux_control.control.config import LayeredControlConfig
from yyr4_linux_control.control.models import ProfileConfig, LayerConfig, ProfileId, LayerId
from yyr4_linux_control.control.actions import ActionPlan
from yyr4_linux_control.input.interfaces import MonotonicClock

class FakeClock(MonotonicClock):
    def __init__(self):
        self.time = 0.0
    def now(self) -> float:
        return self.time
    def monotonic(self) -> float:
        return self.time
    async def sleep(self, seconds: float) -> None:
        self.time += seconds

class TestRuntimeContextManager(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.config = LayeredControlConfig(
            schema_version=2,
            default_profile=ProfileId("default"),
            initial_layer=LayerId("general"),
            profiles={
                ProfileId("default"): ProfileConfig(profile_id=ProfileId("default"), layers={
                    LayerId("general"): LayerConfig(layer_id=LayerId("general"), controls={}),
                    LayerId("layer_1"): LayerConfig(layer_id=LayerId("layer_1"), controls={}),
                    LayerId("layer_2"): LayerConfig(layer_id=LayerId("layer_2"), controls={})
                }),
                ProfileId("gaming"): ProfileConfig(profile_id=ProfileId("gaming"), layers={
                    LayerId("general"): LayerConfig(layer_id=LayerId("general"), controls={}),
                    LayerId("layer_1"): LayerConfig(layer_id=LayerId("layer_1"), controls={})
                })
            }
        )
        self.ctx = RuntimeContextManager(ProfileId("default"), LayerId("general"), self.clock)
        self.ctx.set_config(self.config)

    async def test_startup_defaults(self):
        snap = await self.ctx.snapshot()
        self.assertEqual(snap.selected_profile, ProfileId("default"))
        self.assertEqual(snap.active_layer, LayerId("general"))
        self.assertEqual(snap.revision, 0)

    async def test_set_layer(self):
        changed = await self.ctx.set_layer("layer_1", ContextChangeSource.management_cli)
        self.assertTrue(changed)
        snap = await self.ctx.snapshot()
        self.assertEqual(snap.active_layer, LayerId("layer_1"))
        self.assertEqual(snap.revision, 1)
        
        # idempotent
        changed = await self.ctx.set_layer("layer_1", ContextChangeSource.control_action)
        self.assertFalse(changed)
        snap = await self.ctx.snapshot()
        self.assertEqual(snap.revision, 1)

    async def test_set_invalid_layer_ignored(self):
        with self.assertRaises(ValueError):
            await self.ctx.set_layer("unknown", ContextChangeSource.management_cli)
        snap = await self.ctx.snapshot()
        self.assertEqual(snap.active_layer, LayerId("general"))
        
    async def test_next_layer(self):
        await self.ctx.next_layer(ContextChangeSource.control_action)
        snap = await self.ctx.snapshot()
        self.assertEqual(snap.active_layer, LayerId("layer_1"))
        
        await self.ctx.next_layer(ContextChangeSource.control_action)
        snap = await self.ctx.snapshot()
        self.assertEqual(snap.active_layer, LayerId("layer_2"))
        
        # Wraps around
        await self.ctx.next_layer(ContextChangeSource.control_action)
        snap = await self.ctx.snapshot()
        self.assertEqual(snap.active_layer, LayerId("general"))

    async def test_previous_layer(self):
        await self.ctx.previous_layer(ContextChangeSource.control_action)
        snap = await self.ctx.snapshot()
        self.assertEqual(snap.active_layer, LayerId("layer_2"))
        
        await self.ctx.previous_layer(ContextChangeSource.control_action)
        snap = await self.ctx.snapshot()
        self.assertEqual(snap.active_layer, LayerId("layer_1"))

    async def test_set_profile(self):
        changed = await self.ctx.set_profile("gaming", ContextChangeSource.management_cli)
        self.assertTrue(changed)
        snap = await self.ctx.snapshot()
        self.assertEqual(snap.selected_profile, ProfileId("gaming"))
        self.assertEqual(snap.active_layer, LayerId("general")) # fallback to initial_layer

    async def test_set_invalid_profile(self):
        with self.assertRaises(ValueError):
            await self.ctx.set_profile("unknown", ContextChangeSource.management_cli)

    async def test_reconcile_after_reload(self):
        # Change layer
        await self.ctx.set_layer("layer_1", ContextChangeSource.management_cli)
        
        new_config = LayeredControlConfig(
            schema_version=2,
            default_profile=ProfileId("default"),
            initial_layer=LayerId("general"),
            profiles={
                ProfileId("default"): ProfileConfig(profile_id=ProfileId("default"), layers={
                    LayerId("general"): LayerConfig(layer_id=LayerId("general"), controls={}),
                    # nav removed
                })
            }
        )
        
        changed = await self.ctx.reconcile_after_reload(new_config)
        self.assertTrue(changed)
        snap = await self.ctx.snapshot()
        self.assertEqual(snap.active_layer, LayerId("general")) # Fell back to initial
        self.assertEqual(snap.last_change_source, ContextChangeSource.config_reload)
        
if __name__ == '__main__':
    unittest.main()
