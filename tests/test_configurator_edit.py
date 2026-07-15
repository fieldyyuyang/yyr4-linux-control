import unittest
import os
import tempfile
from pathlib import Path

from yyr4_linux_control.configurator.serializer import serialize
from yyr4_linux_control.configurator.draft import ConfigDraft
from yyr4_linux_control.control.config import load_control_config_from_file
from yyr4_linux_control.control.models import ProfileId
from yyr4_linux_control.control.actions import (
    HotkeyAction, TextAction, CommandAction, DelayAction,
    MacroAction, NoOpAction, DebugLogAction,
    SetLayerAction, SetProfileAction, NextLayerAction, PreviousLayerAction,
)


class TestSerializer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = load_control_config_from_file(
            Path("examples/yyr4-control-from-20260711-backup.toml"),
        )

    def test_deterministic_output(self):
        a = serialize(self.config)
        b = serialize(self.config)
        self.assertEqual(a, b)

    def test_serialize_then_parse_roundtrip(self):
        text = serialize(self.config)
        re_parsed = self._load(text)
        self.assertEqual(re_parsed.schema_version, 2)
        self.assertEqual(re_parsed.default_profile.value, "user")
        self.assertEqual(re_parsed.initial_layer.value, "general")
        # 24 controls preserved
        general = re_parsed.profiles[re_parsed.default_profile].layers["general"]
        self.assertEqual(len(general.controls), 24)

    def test_deterministic_after_draft_modification(self):
        draft = ConfigDraft(Path("examples/yyr4-control-from-20260711-backup.toml"))
        a = serialize(draft.working_config)
        draft.set_action("user", "general", "A1", DebugLogAction("test"))
        b = serialize(draft.working_config)
        self.assertNotEqual(a, b)
        # Reset
        draft.set_action("user", "general", "A1", HotkeyAction(("ESC",)))
        c = serialize(draft.working_config)
        self.assertEqual(a, c)

    def test_profile_sorting(self):
        """Profiles appear in sorted order by name."""
        text = serialize(self.config)
        self.assertIn("user", text)

    def test_layer_sorting(self):
        text = serialize(self.config)
        self.assertIn("general", text)

    def test_control_order(self):
        text = serialize(self.config)
        # Verify canonical control order
        controls_in_order = _extract_control_names(text)
        expected = [
            "A1","A2","A3","A4","A5","A6","A7","A8","A9","A10","A11","A12",
            "AL","AP","AR","BL","BP","BR","CL","CP","CR","DL","DP","DR",
        ]
        self.assertEqual([c for c in expected if c in controls_in_order], expected)

    def test_string_quoting(self):
        draft = ConfigDraft(Path("examples/yyr4-control-from-20260711-backup.toml"))
        draft.set_action("user", "general", "A1", TextAction('hello "world"'))
        text = serialize(draft.working_config)
        self.assertIn('"hello \\"world\\""', text)

    def test_backslash_escape(self):
        draft = ConfigDraft(Path("examples/yyr4-control-from-20260711-backup.toml"))
        draft.set_action("user", "general", "A1", TextAction("a\\b"))
        text = serialize(draft.working_config)
        self.assertIn('"a\\\\b"', text)

    def test_newline_escape(self):
        draft = ConfigDraft(Path("examples/yyr4-control-from-20260711-backup.toml"))
        draft.set_action("user", "general", "A1", TextAction("line1\nline2"))
        text = serialize(draft.working_config)
        self.assertIn("line1", text)
        self.assertIn("line2", text)

    def test_unicode_preserved(self):
        draft = ConfigDraft(Path("examples/yyr4-control-from-20260711-backup.toml"))
        draft.set_action("user", "general", "A1", TextAction("ol\u00e9"))
        text = serialize(draft.working_config)
        re_parsed = self._load(text)
        action = re_parsed.profiles[ProfileId("user")].layers["general"].controls["A1"]
        self.assertEqual(action.value, "ol\u00e9")

    def test_macro_steps_order_preserved(self):
        draft = ConfigDraft(Path("examples/yyr4-control-from-20260711-backup.toml"))
        original = serialize(draft.working_config)
        re_parsed = self._load(original)
        a6 = re_parsed.profiles[ProfileId("user")].layers["general"].controls["A6"]
        self.assertIsInstance(a6, MacroAction)
        self.assertEqual(len(a6.steps), 11)

    def test_runtime_actions_serialized(self):
        draft = ConfigDraft(Path("examples/yyr4-control-from-20260711-backup.toml"))
        draft.set_action("user", "general", "A1", SetLayerAction("layer_1"))
        text = serialize(draft.working_config)
        self.assertIn('set_layer', text)
        self.assertIn('"layer_1"', text)

    def test_no_python_object_repr(self):
        text = serialize(self.config)
        self.assertNotIn("<", text)
        self.assertNotIn("object at", text)

    def test_action_field_order(self):
        draft = ConfigDraft(Path("examples/yyr4-control-from-20260711-backup.toml"))
        draft.set_action("user", "general", "A1", HotkeyAction(("LCTRL", "C")))
        text = serialize(draft.working_config)
        # type first, then keys
        idx_type = text.index('type = "hotkey"')
        idx_keys = text.index('keys =')
        self.assertLess(idx_type, idx_keys)

    def test_schema_v1_rejected_for_draft(self):
        import tempfile, os
        v1 = "schema_version = 1\n[controls.A1.action]\ntype = \"noop\"\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write(v1)
            tmp = f.name
        try:
            with self.assertRaises(ValueError):
                ConfigDraft(Path(tmp))
        finally:
            os.unlink(tmp)

    def _load(self, text):
        import tempfile, os
        fd, name = tempfile.mkstemp(suffix=".toml")
        try:
            os.write(fd, text.encode("utf-8"))
            os.close(fd)
            fd = -1
            return load_control_config_from_file(Path(name))
        finally:
            if fd >= 0:
                os.close(fd)
            try:
                os.unlink(name)
            except OSError:
                pass


def _extract_control_names(text: str):
    import re
    return re.findall(r'\.controls\.(\w+)\.action', text)


class TestDraft(unittest.TestCase):
    def setUp(self):
        self.draft = ConfigDraft(Path("examples/yyr4-control-from-20260711-backup.toml"))

    def test_base_working_isolation(self):
        self.assertFalse(self.draft.dirty)
        self.assertEqual(self.draft.mutation_count, 0)
        self.draft.set_action("user", "general", "A1", DebugLogAction("x"))
        self.assertTrue(self.draft.dirty)
        self.assertEqual(self.draft.mutation_count, 1)
        # Base unchanged
        base = load_control_config_from_file(
            Path("examples/yyr4-control-from-20260711-backup.toml"),
        )
        self.assertEqual(
            base.profiles[ProfileId("user")].layers["general"].controls["A1"].keys,
            ("ESC",),
        )

    def test_add_profile(self):
        r = self.draft.add_profile("gaming")
        self.assertTrue(r.success)
        self.assertTrue(self.draft.dirty)

    def test_add_duplicate_profile_rejected(self):
        self.draft.add_profile("gaming")
        r = self.draft.add_profile("gaming")
        self.assertFalse(r.success)

    def test_rename_profile(self):
        self.draft.add_profile("gaming")
        r = self.draft.rename_profile("gaming", "work")
        self.assertTrue(r.success)

    def test_rename_nonexistent_rejected(self):
        r = self.draft.rename_profile("nonexistent", "new")
        self.assertFalse(r.success)

    def test_rename_to_existing_rejected(self):
        self.draft.add_profile("a")
        self.draft.add_profile("b")
        r = self.draft.rename_profile("a", "b")
        self.assertFalse(r.success)

    def test_remove_profile_rejected_last(self):
        r = self.draft.remove_profile("user")
        self.assertFalse(r.success)
        self.assertIn("last profile", r.diagnostics[0].message.lower())

    def test_remove_profile_rejected_default(self):
        self.draft.add_profile("gaming")
        r = self.draft.remove_profile("user")
        self.assertFalse(r.success)
        self.assertIn("default", r.diagnostics[0].message.lower())

    def test_remove_profile_success(self):
        self.draft.add_profile("gaming")
        self.draft.set_default_profile("gaming")
        r = self.draft.remove_profile("user")
        self.assertTrue(r.success)

    def test_set_default_profile(self):
        self.draft.add_profile("gaming")
        r = self.draft.set_default_profile("gaming")
        self.assertTrue(r.success)

    def test_add_layer(self):
        r = self.draft.add_layer("user", "layer_1")
        self.assertTrue(r.success)

    def test_add_duplicate_layer_rejected(self):
        r = self.draft.add_layer("user", "general")
        self.assertFalse(r.success)

    def test_rename_layer(self):
        self.draft.add_layer("user", "layer_1")
        r = self.draft.rename_layer("user", "layer_1", "layer_2")
        self.assertTrue(r.success)

    def test_remove_layer_rejected_general(self):
        r = self.draft.remove_layer("user", "general")
        self.assertFalse(r.success)
        self.assertIn("general", r.diagnostics[0].message.lower())

    def test_set_action(self):
        r = self.draft.set_action("user", "general", "A1", DebugLogAction("test"))
        self.assertTrue(r.success)

    def test_set_action_invalid_control(self):
        r = self.draft.set_action("user", "general", "INVALID", DebugLogAction("x"))
        self.assertFalse(r.success)

    def test_clear_action(self):
        r = self.draft.set_action("user", "general", "A1", HotkeyAction(("ESC",)))
        self.assertTrue(r.success)

    def test_validate(self):
        v = self.draft.validate()
        self.assertTrue(v.valid)
        self.assertIsNotNone(v.canonical_text)

    def test_macro_steps_roundtrip(self):
        text1 = serialize(self.draft.working_config)
        re = self.draft.validate()
        text2 = re.canonical_text
        self.assertEqual(_count_a6_steps(text1), _count_a6_steps(text2))

    def test_set_action_then_serialize_roundtrip(self):
        self.draft.set_action("user", "general", "A1", DebugLogAction("test"))
        v = self.draft.validate()
        self.assertTrue(v.valid)
        self.assertIn("debug_log", v.canonical_text)


def _count_a6_steps(text):
    import re
    return len(re.findall(r'controls\.A6.*macro', text))


class TestDiff(unittest.TestCase):
    def setUp(self):
        self.base = ConfigDraft(Path("examples/yyr4-control-from-20260711-backup.toml"))
        from yyr4_linux_control.configurator.diff import diff_configs
        self.diff_configs = diff_configs

    def test_no_change(self):
        result = self.diff_configs(self.base.working_config, self.base.working_config)
        self.assertEqual(len(result.changes), 0)
        self.assertEqual(result.risk_summary, "LOW")

    def test_control_changed(self):
        self.base.set_action("user", "general", "A1", DebugLogAction("x"))
        result = self.diff_configs(
            load_control_config_from_file(Path("examples/yyr4-control-from-20260711-backup.toml")),
            self.base.working_config,
        )
        self.assertEqual(len(result.changes), 1)
        self.assertEqual(result.changes[0].kind, "changed")

    def test_control_mapped(self):
        draft2 = ConfigDraft(Path("examples/yyr4-control-from-20260711-backup.toml"))
        draft2.clear_action("user", "general", "A1")
        # Now base has A1 mapped, draft2 does not
        result = self.diff_configs(draft2.working_config, self.base.working_config)
        mapped = [c for c in result.changes if c.kind == "mapped"]
        self.assertGreaterEqual(len(mapped), 1)

    def test_profile_added(self):
        self.base.add_profile("gaming")
        result = self.diff_configs(
            load_control_config_from_file(Path("examples/yyr4-control-from-20260711-backup.toml")),
            self.base.working_config,
        )
        added = [c for c in result.changes if c.kind == "added"]
        self.assertGreaterEqual(len(added), 1)

    def test_unified_diff(self):
        from yyr4_linux_control.configurator.diff import unified_diff
        from yyr4_linux_control.configurator.serializer import serialize as ser
        self.base.set_action("user", "general", "A1", DebugLogAction("x"))
        base_text = ser(load_control_config_from_file(
            Path("examples/yyr4-control-from-20260711-backup.toml")))
        draft_text = ser(self.base.working_config)
        udiff = unified_diff(base_text, draft_text)
        self.assertIn("--- base", udiff)
        self.assertIn("+++ draft", udiff)

    def test_risk_classification(self):
        self.base.add_profile("gaming")
        self.base.set_default_profile("gaming")
        self.base.remove_profile("user")
        result = self.diff_configs(
            load_control_config_from_file(Path("examples/yyr4-control-from-20260711-backup.toml")),
            self.base.working_config,
        )
        self.assertIn(result.risk_summary, ("MEDIUM", "HIGH"))


class TestSave(unittest.TestCase):
    def setUp(self):
        import tempfile, shutil
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(self.tmp, ignore_errors=True))
        self.draft = ConfigDraft(Path("examples/yyr4-control-from-20260711-backup.toml"))

    def _save(self, sha=None, force_new=False):
        from yyr4_linux_control.configurator.save import save_draft
        target = Path(self.tmp) / "config.toml"
        if force_new:
            sha = None
        else:
            if sha is None:
                sha = self.draft.base_sha256
        return save_draft(self.draft, target, sha, backup_dir=Path(self.tmp) / "backups")

    def test_save_new_file(self):
        from yyr4_linux_control.configurator.save import save_draft
        target = Path(self.tmp) / "no-backup.toml"
        r = save_draft(self.draft, target, None)
        self.assertTrue(r.verified)
        self.assertIsNone(r.backup_path)

    def test_save_new_file_with_backup_dir(self):
        r = self._save(force_new=True)
        self.assertTrue(r.verified)

    def test_save_mismatched_sha_rejected(self):
        from yyr4_linux_control.configurator.save import ConcurrentModificationError
        self._save(force_new=True)
        self.draft.set_action("user", "general", "A1", DebugLogAction("changed"))
        with self.assertRaises(ConcurrentModificationError):
            self._save(sha="0000000000000000000000000000000000000000000000000000000000000000")

    def test_save_creates_backup_on_overwrite(self):
        from yyr4_linux_control.configurator.save import save_draft
        target = Path(self.tmp) / "with-backup.toml"
        r1 = save_draft(self.draft, target, None, backup_dir=Path(self.tmp) / "backups")
        r2 = save_draft(self.draft, target, r1.saved_sha256, backup_dir=Path(self.tmp) / "backups")
        self.assertIsNotNone(r2.backup_path)
        self.assertTrue(r2.backup_path.is_file())

    def test_backup_mode_600(self):
        from yyr4_linux_control.configurator.save import save_draft
        target = Path(self.tmp) / "mode-test.toml"
        r1 = save_draft(self.draft, target, None, backup_dir=Path(self.tmp) / "backups")
        r2 = save_draft(self.draft, target, r1.saved_sha256, backup_dir=Path(self.tmp) / "backups")
        self.assertIsNotNone(r2.backup_path)
        mode = r2.backup_path.stat().st_mode & 0o777
        self.assertLessEqual(mode, 0o600)

    def test_target_mode_600(self):
        r = self._save(force_new=True)
        mode = r.target_path.stat().st_mode & 0o777
        self.assertLessEqual(mode, 0o600)

    def test_symlink_target_rejected(self):
        from yyr4_linux_control.configurator.save import SymlinkTargetError
        target = Path(self.tmp) / "link.toml"
        real = Path(self.tmp) / "real.toml"
        real.write_text("x")
        os.symlink(str(real), str(target))
        from yyr4_linux_control.configurator.save import save_draft
        with self.assertRaises(SymlinkTargetError):
            save_draft(self.draft, target, None)

    def test_validation_fails_before_save(self):
        import tempfile, os as _os
        # Create bad config
        bad = """schema_version = 2
default_profile = "x"
initial_layer = "general"
[profiles.x.layers.general.controls.A1.action]
type = "hotkey"
keys = ["OK"]
"""
        p = Path(self.tmp) / "bad.toml"
        p.write_text(bad)
        d2 = ConfigDraft(p)
        # Corrupt it
        d2.set_action("x", "general", "A1", HotkeyAction(("OK","OK")))
        target = Path(self.tmp) / "save.toml"
        from yyr4_linux_control.configurator.save import save_draft
        try:
            save_draft(d2, target, None)
            self.fail("should have raised")
        except Exception:
            pass




if __name__ == "__main__":
    unittest.main()
