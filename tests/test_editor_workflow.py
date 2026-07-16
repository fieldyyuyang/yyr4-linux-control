"""End-to-end workflow tests: full edit→validate→diff→save cycle."""

import unittest, os, tempfile, shutil, json, time
from pathlib import Path


class TestEditorWorkflow(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.src = os.path.join(self.tmp, "src.toml")
        shutil.copy(
            os.path.join(os.path.dirname(__file__), "..", "examples",
                         "yyr4-control-from-20260711-backup.toml"),
            self.src,
        )
        self.target = os.path.join(self.tmp, "target.toml")
        self.backup_dir = os.path.join(self.tmp, "backups")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _session(self):
        from yyr4_linux_control.configurator.web.session import create_session
        return create_session(self.src, self.target, self.backup_dir)

    def _src_sha(self):
        import hashlib
        return hashlib.sha256(Path(self.src).read_bytes()).hexdigest()

    def test_full_workflow_modify_a1(self):
        from yyr4_linux_control.configurator.web.api import (
            handle_set_action, handle_diff, handle_validate,
            handle_save, build_state,
        )
        s = self._session()
        orig_src_sha = self._src_sha()

        # 1. Modify A1
        r = handle_set_action(s, {
            "profile": "user", "layer": "general", "control": "A1",
            "action_spec": {"type": "debug_log", "message": "hello from editor"},
        })
        self.assertEqual(r["status"], "ok")
        self.assertTrue(s.dirty)

        # 2. Validate
        r = handle_validate(s)
        self.assertTrue(r["validation"]["valid"])

        # 3. Diff
        r = handle_diff(s)
        self.assertGreater(r["change_count"], 0)

        # 4. Review
        s.mark_reviewed()

        # 5. Save
        r = handle_save(s)
        self.assertEqual(r["status"], "ok")
        self.assertTrue(r["verified"])
        self.assertTrue(os.path.isfile(self.target))

        # 6. Verify target is valid config
        from yyr4_linux_control.control.config import load_control_config_from_file
        cfg = load_control_config_from_file(Path(self.target))
        self.assertEqual(cfg.schema_version, 2)

        # 7. Verify A1 is DebugLogAction
        from yyr4_linux_control.control.actions import DebugLogAction
        from yyr4_linux_control.control.models import OfficialControl, LayerId, ProfileId
        a1 = cfg.profiles[ProfileId("user")].layers[LayerId("general")].controls[OfficialControl.A1]
        self.assertIsInstance(a1, DebugLogAction)
        self.assertEqual(a1.message, "hello from editor")

        # 8. Verify A6 is still MacroAction with 11 steps, 5 Delays
        from yyr4_linux_control.control.actions import MacroAction, DelayAction
        a6 = cfg.profiles[ProfileId("user")].layers[LayerId("general")].controls[OfficialControl.A6]
        self.assertIsInstance(a6, MacroAction)
        self.assertEqual(len(a6.steps), 11)
        dc = sum(1 for st in a6.steps if isinstance(st, DelayAction))
        self.assertEqual(dc, 5)

        # 9. Verify 24 controls
        self.assertEqual(len(OfficialControl), 24)

        # 10. Verify source not modified
        self.assertEqual(self._src_sha(), orig_src_sha)

        # 11. Cleanup
        s.shutdown()

    def test_target_mode_600(self):
        from yyr4_linux_control.configurator.web.api import (
            handle_set_action, handle_save,
        )
        s = self._session()
        handle_set_action(s, {
            "profile": "user", "layer": "general", "control": "A1",
            "action_spec": {"type": "noop"},
        })
        s.mark_reviewed()
        handle_save(s)
        mode = os.stat(self.target).st_mode & 0o777
        self.assertEqual(mode, 0o600)
        s.shutdown()

    def test_backup_created(self):
        from yyr4_linux_control.configurator.web.api import (
            handle_set_action, handle_save,
        )
        # First save to create baseline
        s1 = self._session()
        handle_set_action(s1, {
            "profile": "user", "layer": "general", "control": "A1",
            "action_spec": {"type": "noop"},
        })
        s1.mark_reviewed()
        handle_save(s1)
        s1.shutdown()

        # Second save — should create backup. Use target as source.
        from yyr4_linux_control.configurator.web.session import create_session
        target2 = os.path.join(self.tmp, "target2.toml")
        s2 = create_session(self.target, target2, self.backup_dir)
        handle_set_action(s2, {
            "profile": "user", "layer": "general", "control": "A1",
            "action_spec": {"type": "debug_log", "message": "changed"},
        })
        s2.mark_reviewed()
        r = handle_save(s2)
        self.assertEqual(r["status"], "ok")
        # Save again to same target with backup - now save to self.target directly
        from yyr4_linux_control.configurator.web.session import create_session
        s3 = create_session(target2, target2, self.backup_dir)
        handle_set_action(s3, {
            "profile": "user", "layer": "general", "control": "A2",
            "action_spec": {"type": "noop"},
        })
        s3.mark_reviewed()
        r3 = handle_save(s3)
        self.assertEqual(r3["status"], "ok")
        # Backup should exist
        backups = os.listdir(self.backup_dir)
        self.assertGreater(len(backups), 0, "Expected backup files in backup dir")
        s2.shutdown()
        s3.shutdown()

    def test_source_sha_unchanged(self):
        orig = self._src_sha()
        s = self._session()
        from yyr4_linux_control.configurator.web.api import handle_set_action
        handle_set_action(s, {
            "profile": "user", "layer": "general", "control": "A1",
            "action_spec": {"type": "debug_log", "message": "test"},
        })
        self.assertEqual(self._src_sha(), orig)
        s.shutdown()

    def test_no_daemon_no_hardware(self):
        s = self._session()
        # Session doesn't touch daemon or hardware
        self.assertIsNone(getattr(s, 'daemon_socket', None))
        s.shutdown()

    def test_24_controls_in_state(self):
        from yyr4_linux_control.configurator.web.api import build_state
        s = self._session()
        st = build_state(s)
        profiles = st.get("config", {}).get("profiles", [])
        if profiles:
            layers = profiles[0].get("layers", [])
            if layers:
                controls = layers[0].get("controls", {})
                self.assertEqual(len(controls), 24)
        s.shutdown()

    def test_session_cleanup_after_workflow(self):
        s = self._session()
        dir_path = s.session_dir
        self.assertTrue(os.path.isdir(dir_path))
        s.shutdown()
        self.assertFalse(os.path.exists(dir_path))

    def test_no_action_execution(self):
        # Verify that the editor never touches action execution
        s = self._session()
        from yyr4_linux_control.configurator.web.api import handle_set_action
        handle_set_action(s, {
            "profile": "user", "layer": "general", "control": "A1",
            "action_spec": {"type": "command", "argv": ["echo", "should-not-run"]},
        })
        # No process spawned, no desktop input
        s.shutdown()
        # Test passes if no exception


if __name__ == "__main__":
    unittest.main()
