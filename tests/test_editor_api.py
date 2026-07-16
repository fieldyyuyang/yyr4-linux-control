"""Tests for the editor REST API via direct function calls."""

import unittest, os, tempfile, shutil, json
from pathlib import Path


class TestEditorAPI(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.src = os.path.join(self.tmp, "src.toml")
        shutil.copy(
            os.path.join(os.path.dirname(__file__), "..", "examples",
                         "yyr4-control-from-20260711-backup.toml"),
            self.src,
        )
        self.target = os.path.join(self.tmp, "target.toml")
        from yyr4_linux_control.configurator.web.session import create_session
        self.session = create_session(self.src, self.target)

    def tearDown(self):
        self.session.shutdown()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_build_state(self):
        from yyr4_linux_control.configurator.web.api import build_state
        st = build_state(self.session)
        self.assertIn("config", st)
        self.assertIn("profiles", st["config"])
        self.assertIn("validation", st)
        self.assertIn("session", st)

    def test_handle_validate(self):
        from yyr4_linux_control.configurator.web.api import handle_validate
        r = handle_validate(self.session)
        self.assertEqual(r["status"], "ok")
        self.assertTrue(r["validation"]["valid"])

    def test_handle_diff_no_change(self):
        from yyr4_linux_control.configurator.web.api import handle_diff
        r = handle_diff(self.session)
        self.assertEqual(r["status"], "ok")
        self.assertEqual(r["change_count"], 0)

    def test_handle_unified_diff_no_change(self):
        from yyr4_linux_control.configurator.web.api import handle_unified_diff
        r = handle_unified_diff(self.session)
        self.assertEqual(r["status"], "ok")
        self.assertIn("unified_diff", r)

    def test_handle_set_action(self):
        from yyr4_linux_control.configurator.web.api import handle_set_action
        r = handle_set_action(self.session, {
            "profile": "user",
            "layer": "general",
            "control": "A1",
            "action_spec": {"type": "debug_log", "message": "test"},
        })
        self.assertEqual(r["status"], "ok")
        self.assertTrue(self.session.dirty)

    def test_handle_set_action_invalid_type(self):
        from yyr4_linux_control.configurator.web.api import handle_set_action
        r = handle_set_action(self.session, {
            "profile": "user",
            "layer": "general",
            "control": "A1",
            "action_spec": {"type": "NONEXISTENT"},
        })
        self.assertEqual(r["status"], "error")

    def test_handle_clear_action(self):
        from yyr4_linux_control.configurator.web.api import (
            handle_set_action, handle_clear_action,
        )
        handle_set_action(self.session, {
            "profile": "user", "layer": "general", "control": "A2",
            "action_spec": {"type": "debug_log", "message": "test"},
        })
        r = handle_clear_action(self.session, {
            "profile": "user", "layer": "general", "control": "A2",
        })
        self.assertEqual(r["status"], "ok")

    def test_handle_add_profile(self):
        from yyr4_linux_control.configurator.web.api import handle_add_profile
        r = handle_add_profile(self.session, {"profile_id": "gaming"})
        self.assertEqual(r["status"], "ok")

    def test_handle_add_profile_duplicate(self):
        from yyr4_linux_control.configurator.web.api import handle_add_profile
        r = handle_add_profile(self.session, {"profile_id": "user"})
        self.assertEqual(r["status"], "error")

    def test_handle_rename_profile(self):
        from yyr4_linux_control.configurator.web.api import (
            handle_add_profile, handle_rename_profile,
        )
        handle_add_profile(self.session, {"profile_id": "temp"})
        r = handle_rename_profile(self.session, {
            "old_profile_id": "temp", "new_profile_id": "renamed",
        })
        self.assertEqual(r["status"], "ok")

    def test_handle_remove_profile(self):
        from yyr4_linux_control.configurator.web.api import (
            handle_add_profile, handle_remove_profile,
        )
        handle_add_profile(self.session, {"profile_id": "extra"})
        # Make "extra" not the default
        from yyr4_linux_control.configurator.web.api import handle_set_default_profile
        handle_set_default_profile(self.session, {"profile_id": "user"})
        r = handle_remove_profile(self.session, {"profile_id": "extra"})
        self.assertEqual(r["status"], "ok")

    def test_handle_set_default_profile(self):
        from yyr4_linux_control.configurator.web.api import handle_set_default_profile
        r = handle_set_default_profile(self.session, {"profile_id": "user"})
        self.assertEqual(r["status"], "ok")

    def test_handle_add_layer(self):
        from yyr4_linux_control.configurator.web.api import handle_add_layer
        r = handle_add_layer(self.session, {
            "profile": "user", "layer_id": "layer_1",
        })
        self.assertEqual(r["status"], "ok")

    def test_handle_rename_layer(self):
        from yyr4_linux_control.configurator.web.api import (
            handle_add_layer, handle_rename_layer,
        )
        handle_add_layer(self.session, {"profile": "user", "layer_id": "layer_2"})
        r = handle_rename_layer(self.session, {
            "profile": "user", "old_layer_id": "layer_2",
            "new_layer_id": "layer_3",
        })
        self.assertEqual(r["status"], "ok")

    def test_handle_remove_layer(self):
        from yyr4_linux_control.configurator.web.api import (
            handle_add_layer, handle_remove_layer,
        )
        handle_add_layer(self.session, {"profile": "user", "layer_id": "layer_1"})
        r = handle_remove_layer(self.session, {
            "profile": "user", "layer_id": "layer_1",
        })
        self.assertEqual(r["status"], "ok")

    def test_handle_set_initial_layer(self):
        from yyr4_linux_control.configurator.web.api import handle_set_initial_layer
        r = handle_set_initial_layer(self.session, {"layer_id": "general"})
        self.assertEqual(r["status"], "ok")

    def test_handle_save_without_review(self):
        from yyr4_linux_control.configurator.web.api import handle_save
        r = handle_save(self.session)
        self.assertEqual(r["status"], "error")

    def test_handle_save_with_review(self):
        from yyr4_linux_control.configurator.web.api import (
            handle_set_action, handle_save,
        )
        handle_set_action(self.session, {
            "profile": "user", "layer": "general", "control": "A1",
            "action_spec": {"type": "debug_log", "message": "test"},
        })
        self.session.mark_reviewed()
        r = handle_save(self.session)
        self.assertEqual(r["status"], "ok")
        self.assertIn("saved_sha256", r)
        self.assertTrue(r["verified"])

    def test_handle_diff_after_mutation(self):
        from yyr4_linux_control.configurator.web.api import (
            handle_set_action, handle_diff,
        )
        handle_set_action(self.session, {
            "profile": "user", "layer": "general", "control": "A1",
            "action_spec": {"type": "debug_log", "message": "hello"},
        })
        r = handle_diff(self.session)
        self.assertGreater(r["change_count"], 0)

    def test_all_11_action_types_set(self):
        from yyr4_linux_control.configurator.web.api import handle_set_action
        actions = [
            {"type": "noop"},
            {"type": "debug_log", "message": "test"},
            {"type": "hotkey", "keys": ["CTRL", "A"]},
            {"type": "text", "value": "hello"},
            {"type": "command", "argv": ["echo", "hi"]},
            {"type": "delay", "milliseconds": 500},
            {"type": "macro", "steps": [{"type": "noop"}]},
            {"type": "set_layer", "layer": "general"},
            {"type": "next_layer"},
            {"type": "previous_layer"},
            {"type": "set_profile", "profile": "user"},
        ]
        for i, action in enumerate(actions):
            ctrl = f"A{i + 1}"
            r = handle_set_action(self.session, {
                "profile": "user", "layer": "general",
                "control": ctrl, "action_spec": action,
            })
            self.assertEqual(r["status"], "ok", f"Failed for {action['type']} on {ctrl}")

    def test_hotkey_rejects_empty(self):
        from yyr4_linux_control.configurator.web.api import handle_set_action
        r = handle_set_action(self.session, {
            "profile": "user", "layer": "general", "control": "A1",
            "action_spec": {"type": "hotkey", "keys": []},
        })
        self.assertEqual(r["status"], "error")

    def test_command_argv(self):
        from yyr4_linux_control.configurator.web.api import handle_set_action
        r = handle_set_action(self.session, {
            "profile": "user", "layer": "general", "control": "A1",
            "action_spec": {"type": "command", "argv": ["myapp", "--verbose"], "timeout_seconds": 30},
        })
        self.assertEqual(r["status"], "ok")

    def test_delay_rejects_negative(self):
        from yyr4_linux_control.configurator.web.api import handle_set_action
        r = handle_set_action(self.session, {
            "profile": "user", "layer": "general", "control": "A1",
            "action_spec": {"type": "delay", "milliseconds": -1},
        })
        self.assertEqual(r["status"], "error")

    def test_set_layer_target_invalid(self):
        from yyr4_linux_control.configurator.web.api import handle_set_action
        r = handle_set_action(self.session, {
            "profile": "user", "layer": "general", "control": "A1",
            "action_spec": {"type": "set_layer", "layer": "NONEXISTENT!!!"},
        })
        self.assertEqual(r["status"], "error")

    def test_set_profile_target_invalid(self):
        from yyr4_linux_control.configurator.web.api import handle_set_action
        r = handle_set_action(self.session, {
            "profile": "user", "layer": "general", "control": "A1",
            "action_spec": {"type": "set_profile", "profile": "BAD!!!"},
        })
        self.assertEqual(r["status"], "error")

    def test_save_new_target_no_replace(self):
        from yyr4_linux_control.configurator.web.api import (
            handle_set_action, handle_save,
        )
        handle_set_action(self.session, {
            "profile": "user", "layer": "general", "control": "A1",
            "action_spec": {"type": "debug_log", "message": "test"},
        })
        self.session.mark_reviewed()
        self.session._target_path = os.path.join(self.tmp, "new-target.toml")
        r = handle_save(self.session)
        self.assertEqual(r["status"], "ok")


if __name__ == "__main__":
    unittest.main()
