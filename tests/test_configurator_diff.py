import unittest, json
from pathlib import Path
from yyr4_linux_control.configurator.diff import diff_configs, unified_diff
from yyr4_linux_control.configurator.draft import ConfigDraft
from yyr4_linux_control.configurator.serializer import serialize
from yyr4_linux_control.control.config import load_control_config_from_file
from yyr4_linux_control.control.actions import DebugLogAction, SetLayerAction

class TestSemanticDiff(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = load_control_config_from_file(
            Path("examples/yyr4-control-from-20260711-backup.toml"))

    def _draft(self):
        return ConfigDraft(Path("examples/yyr4-control-from-20260711-backup.toml"))

    def test_no_change(self):
        d = diff_configs(self.base, self.base)
        self.assertEqual(len(d.changes), 0)

    def test_control_changed(self):
        draft = self._draft()
        draft.set_action("user", "general", "A1", DebugLogAction("x"))
        d = diff_configs(self.base, draft.working_config)
        self.assertGreaterEqual(len(d.changes), 1)
        ch = [c for c in d.changes if c.kind == "changed"]
        self.assertGreaterEqual(len(ch), 1)

    def test_default_profile_change(self):
        draft = self._draft()
        draft.add_profile("gaming")
        draft.set_default_profile("gaming")
        d = diff_configs(self.base, draft.working_config)
        self.assertIsNotNone(d.default_profile_changed)
        self.assertEqual(d.default_profile_changed[0], "user")
        self.assertEqual(d.default_profile_changed[1], "gaming")

    def test_layer_added(self):
        draft = self._draft()
        draft.add_layer("user", "layer_1")
        d = diff_configs(self.base, draft.working_config)
        added = [c for c in d.changes if c.kind == "added"]
        self.assertGreaterEqual(len(added), 1)

    def test_control_mapped(self):
        draft = self._draft()
        draft.clear_action("user", "general", "A1")
        # base has A1, draft doesn't → from draft's perspective, A1 was unmapped
        d = diff_configs(draft.working_config, self.base)
        mapped = [c for c in d.changes if c.kind == "mapped"]
        self.assertGreaterEqual(len(mapped), 1)

    def test_control_unmapped(self):
        draft = self._draft()
        draft.clear_action("user", "general", "A1")
        d = diff_configs(self.base, draft.working_config)
        unmapped = [c for c in d.changes if c.kind == "unmapped"]
        self.assertGreaterEqual(len(unmapped), 1)

    def test_runtime_target_change(self):
        draft = self._draft()
        draft.add_layer("user", "layer_1")
        draft.set_action("user", "general", "A1", SetLayerAction("layer_1"))
        d = diff_configs(self.base, draft.working_config)
        ch = [c for c in d.changes if c.kind == "changed"]
        self.assertGreaterEqual(len(ch), 1)

    def test_stable_json(self):
        draft = self._draft()
        draft.set_action("user", "general", "A1", DebugLogAction("x"))
        d = diff_configs(self.base, draft.working_config)
        out1 = json.dumps([{"kind": c.kind, "path": c.path, "risk": c.risk}
                           for c in d.changes], sort_keys=True)
        out2 = json.dumps([{"kind": c.kind, "path": c.path, "risk": c.risk}
                           for c in d.changes], sort_keys=True)
        self.assertEqual(out1, out2)

    def test_unified_diff_no_timestamps(self):
        draft = self._draft()
        draft.set_action("user", "general", "A1", DebugLogAction("x"))
        base_text = serialize(self.base)
        draft_text = serialize(draft.working_config)
        udiff = unified_diff(base_text, draft_text)
        self.assertIn("--- base", udiff)
        self.assertIn("+++ draft", udiff)
        self.assertNotIn("202", udiff)  # no timestamps

    def test_risk_classification(self):
        draft = self._draft()
        draft.add_profile("gaming")
        draft.set_default_profile("gaming")
        draft.remove_profile("user")
        d = diff_configs(self.base, draft.working_config)
        self.assertIn(d.risk_summary, ("MEDIUM", "HIGH"))


if __name__ == "__main__":
    unittest.main()
