import unittest, json
from pathlib import Path
from yyr4_linux_control.configurator.diff import diff_configs, unified_diff
from yyr4_linux_control.configurator.draft import ConfigDraft
from yyr4_linux_control.configurator.serializer import serialize
from yyr4_linux_control.control.config import load_control_config_from_file
from yyr4_linux_control.control.models import ProfileId
from yyr4_linux_control.control.actions import (
    DebugLogAction, SetLayerAction, SetProfileAction,
    MacroAction, DelayAction, HotkeyAction,
)

class TestDiff(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = load_control_config_from_file(
            Path("examples/yyr4-control-from-20260711-backup.toml"))

    def _draft(self):
        return ConfigDraft(Path("examples/yyr4-control-from-20260711-backup.toml"))

    def test_no_change(self):
        d = diff_configs(self.base, self.base)
        self.assertEqual(len(d.changes), 0)
        self.assertEqual(d.risk_summary, "LOW")

    def test_control_changed(self):
        draft = self._draft()
        draft.set_action("user", "general", "A1", DebugLogAction("x"))
        d = diff_configs(self.base, draft.working_config)
        ch = [c for c in d.changes if c.kind == "changed"]
        self.assertEqual(len(ch), 1)
        self.assertEqual(ch[0].path, "profiles.user.layers.general.controls.A1")

    def test_default_profile_changed(self):
        draft = self._draft()
        draft.add_profile("gaming")
        draft.set_default_profile("gaming")
        d = diff_configs(self.base, draft.working_config)
        self.assertEqual(d.default_profile_changed, ("user", "gaming"))

    def test_layer_added(self):
        draft = self._draft()
        draft.add_layer("user", "layer_1")
        draft.set_action("user", "layer_1", "A1", DebugLogAction("x"))
        d = diff_configs(self.base, draft.working_config)
        added = [c for c in d.changes if c.kind == "added"]
        self.assertGreaterEqual(len(added), 1)

    def test_profile_renamed(self):
        draft = self._draft()
        draft.add_profile("gaming")
        draft.set_default_profile("gaming")
        draft.rename_profile("user", "legacy")
        d = diff_configs(self.base, draft.working_config)
        renamed = [c for c in d.changes if c.kind in ("added", "removed")]
        self.assertGreaterEqual(len(renamed), 1)

    def test_layer_renamed(self):
        draft = self._draft()
        draft.add_layer("user", "layer_1")
        draft.set_action("user", "layer_1", "A1", DebugLogAction("x"))
        draft.rename_layer("user", "general", "main")
        d = diff_configs(self.base, draft.working_config)
        removed = [c for c in d.changes if c.kind == "removed"]
        added = [c for c in d.changes if c.kind == "added"]
        self.assertGreaterEqual(len(removed) + len(added), 1)

    def test_macro_step_added(self):
        draft = self._draft()
        base_a6 = self.base.profiles[ProfileId("user")].layers["general"].controls["A6"]
        steps = list(base_a6.steps) + [DebugLogAction("extra step")]
        draft.set_action("user", "general", "A6", MacroAction(tuple(steps)))
        d = diff_configs(self.base, draft.working_config)
        ch = [c for c in d.changes if c.kind == "changed"]
        self.assertGreaterEqual(len(ch), 1)
        self.assertIn("A6", ch[0].path)

    def test_macro_step_removed(self):
        draft = self._draft()
        base_a6 = self.base.profiles[ProfileId("user")].layers["general"].controls["A6"]
        steps = tuple(list(base_a6.steps)[:5])
        draft.set_action("user", "general", "A6", MacroAction(steps))
        d = diff_configs(self.base, draft.working_config)
        ch = [c for c in d.changes if c.kind == "changed"]
        self.assertGreaterEqual(len(ch), 1)

    def test_macro_step_changed(self):
        draft = self._draft()
        base_a6 = self.base.profiles[ProfileId("user")].layers["general"].controls["A6"]
        steps = list(base_a6.steps)
        steps[0] = DebugLogAction("changed first step")
        draft.set_action("user", "general", "A6", MacroAction(tuple(steps)))
        d = diff_configs(self.base, draft.working_config)
        ch = [c for c in d.changes if c.kind == "changed"]
        self.assertGreaterEqual(len(ch), 1)

    def test_set_layer_target_changed(self):
        draft = self._draft()
        draft.add_layer("user", "layer_1")
        draft.set_action("user", "general", "A1", SetLayerAction("layer_1"))
        d = diff_configs(self.base, draft.working_config)
        ch = [c for c in d.changes if c.kind == "changed"]
        self.assertGreaterEqual(len(ch), 1)

    def test_set_profile_target_changed(self):
        draft = self._draft()
        draft.add_profile("gaming")
        draft.set_action("user", "general", "A1", SetProfileAction("gaming"))
        d = diff_configs(self.base, draft.working_config)
        ch = [c for c in d.changes if c.kind == "changed"]
        self.assertGreaterEqual(len(ch), 1)

    def test_stable_json(self):
        draft = self._draft()
        draft.set_action("user", "general", "A1", DebugLogAction("x"))
        d = diff_configs(self.base, draft.working_config)
        out1 = json.dumps([{"kind": c.kind, "path": c.path, "risk": c.risk,
                           "before": c.before_summary, "after": c.after_summary}
                           for c in d.changes], sort_keys=True)
        d2 = diff_configs(self.base, draft.working_config)
        out2 = json.dumps([{"kind": c.kind, "path": c.path, "risk": c.risk,
                           "before": c.before_summary, "after": c.after_summary}
                           for c in d2.changes], sort_keys=True)
        self.assertEqual(out1, out2)

    def test_unified_diff_no_timestamps(self):
        draft = self._draft()
        draft.set_action("user", "general", "A1", DebugLogAction("x"))
        udiff = unified_diff(serialize(self.base), serialize(draft.working_config))
        self.assertIn("--- base", udiff)
        self.assertNotIn("202", udiff)

    def test_risk_classification(self):
        draft = self._draft()
        draft.add_profile("gaming")
        draft.set_default_profile("gaming")
        draft.remove_profile("user")
        d = diff_configs(self.base, draft.working_config)
        self.assertIn(d.risk_summary, ("MEDIUM", "HIGH"))


if __name__ == "__main__":
    unittest.main()
