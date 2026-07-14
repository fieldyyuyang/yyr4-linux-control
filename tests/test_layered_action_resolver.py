import unittest
from yyr4_linux_control.control.actions import LayeredActionResolver, ResolutionStatus
from yyr4_linux_control.control.models import (
    LayeredControlConfig, ProfileConfig, LayerConfig, ProfileId, LayerId,
    OfficialControl, OfficialControlEvent
)
from yyr4_linux_control.domain.events import ControlPhase
from yyr4_linux_control.control.actions import NoOpAction, TextAction

class TestLayeredActionResolver(unittest.TestCase):
    def setUp(self):
        self.config = LayeredControlConfig(
            schema_version=2,
            default_profile=ProfileId("default"),
            initial_layer=LayerId("general"),
            profiles={
                ProfileId("default"): ProfileConfig(
                    profile_id=ProfileId("default"),
                    layers={
                        LayerId("general"): LayerConfig(
                            layer_id=LayerId("general"),
                            controls={
                                OfficialControl.A1: NoOpAction(),
                                OfficialControl.A2: TextAction("fallback")
                            }
                        ),
                        LayerId("layer_1"): LayerConfig(
                            layer_id=LayerId("layer_1"),
                            controls={
                                OfficialControl.A1: TextAction("override")
                            }
                        )
                    }
                )
            }
        )
        self.resolver = LayeredActionResolver(self.config)

    def test_active_layer_override(self):
        ev = OfficialControlEvent(control=OfficialControl.A1, phase=ControlPhase.DOWN, timestamp_ns=0)
        plan = self.resolver.resolve(ev, ProfileId("default"), LayerId("layer_1"))
        self.assertEqual(plan.mapping_source, "active_layer")
        self.assertEqual(plan.resolution_status, ResolutionStatus.CONFIGURED)
        self.assertIsInstance(plan.steps[0], TextAction)
        self.assertEqual(plan.steps[0].value, "override")

    def test_general_fallback(self):
        ev = OfficialControlEvent(control=OfficialControl.A2, phase=ControlPhase.DOWN, timestamp_ns=0)
        plan = self.resolver.resolve(ev, ProfileId("default"), LayerId("layer_1"))
        self.assertEqual(plan.mapping_source, "general_fallback")
        self.assertEqual(plan.resolution_status, ResolutionStatus.CONFIGURED)
        self.assertIsInstance(plan.steps[0], TextAction)
        self.assertEqual(plan.steps[0].value, "fallback")

    def test_unmapped(self):
        ev = OfficialControlEvent(control=OfficialControl.A3, phase=ControlPhase.DOWN, timestamp_ns=0)
        plan = self.resolver.resolve(ev, ProfileId("default"), LayerId("layer_1"))
        self.assertEqual(plan.mapping_source, "unmapped")
        self.assertEqual(plan.resolution_status, ResolutionStatus.UNMAPPED)
        self.assertEqual(len(plan.steps), 0)

    def test_ignore_up_phase(self):
        ev = OfficialControlEvent(control=OfficialControl.A1, phase=ControlPhase.UP, timestamp_ns=0)
        plan = self.resolver.resolve(ev, ProfileId("default"), LayerId("layer_1"))
        self.assertEqual(plan.mapping_source, "unmapped")
        self.assertEqual(plan.resolution_status, ResolutionStatus.UNMAPPED)

    def test_unknown_profile(self):
        ev = OfficialControlEvent(control=OfficialControl.A1, phase=ControlPhase.DOWN, timestamp_ns=0)
        with self.assertRaisesRegex(ValueError, "Unknown profile: unknown"):
            self.resolver.resolve(ev, ProfileId("unknown"), LayerId("layer_1"))
