"""M5.4 Recovery tests: crash recovery, list, inspect, discard, resume."""

import unittest, os, tempfile, shutil, json
from pathlib import Path


class TestEditorRecovery(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.src = os.path.join(self.tmp, "src.toml")
        shutil.copy(
            os.path.join(os.path.dirname(__file__), "..", "examples",
                         "yyr4-control-from-20260711-backup.toml"),
            self.src,
        )
        self.target = os.path.join(self.tmp, "target.toml")
        # Override recovery dir for testing
        self._recovery_dir = os.path.join(self.tmp, "recovery-test")
        import yyr4_linux_control.configurator.web.session as smod
        self._old_recovery = smod.RECOVERY_BASE_DIR
        smod.RECOVERY_BASE_DIR = self._recovery_dir

    def tearDown(self):
        import yyr4_linux_control.configurator.web.session as smod
        smod.RECOVERY_BASE_DIR = self._old_recovery
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _session(self):
        from yyr4_linux_control.configurator.web.session import create_session
        return create_session(self.src, self.target)

    def test_clean_session_no_recovery(self):
        s = self._session()
        s.shutdown_clean()
        from yyr4_linux_control.configurator.web.session import list_recoveries
        self.assertEqual(len(list_recoveries()), 0)

    def test_dirty_session_creates_recovery(self):
        from yyr4_linux_control.configurator.web.api import handle_set_action
        from yyr4_linux_control.configurator.web.session import list_recoveries
        s = self._session()
        handle_set_action(s, {
            "profile":"user","layer":"general","control":"A1",
            "action_spec":{"type":"debug_log","message":"recovery-test"},
        })
        self.assertTrue(s.dirty)
        s.shutdown()
        recs = list_recoveries()
        self.assertGreaterEqual(len(recs), 1)
        # Cleanup
        from yyr4_linux_control.configurator.web.session import discard_recovery
        for r in recs:
            discard_recovery(r["recovery_id"])

    def test_list_recoveries_empty(self):
        from yyr4_linux_control.configurator.web.session import list_recoveries
        self.assertEqual(len(list_recoveries()), 0)

    def test_recovery_manifest_fields(self):
        from yyr4_linux_control.configurator.web.api import handle_set_action
        from yyr4_linux_control.configurator.web.session import list_recoveries, discard_recovery
        s = self._session()
        handle_set_action(s, {
            "profile":"user","layer":"general","control":"A1",
            "action_spec":{"type":"noop"},
        })
        s.shutdown()
        recs = list_recoveries()
        self.assertGreaterEqual(len(recs), 1)
        r = recs[0]
        self.assertEqual(r["recovery_version"], 1)
        self.assertIn("recovery_id", r)
        self.assertIn("base_sha256", r)
        self.assertIn("draft_sha256", r)
        self.assertIn("mutation_count", r)
        self.assertIn("dirty", r)
        self.assertTrue(r["dirty"])
        self.assertIn("application_version", r)
        # Cleanup
        for rec in recs:
            discard_recovery(rec["recovery_id"])

    def testdiscard_recovery(self):
        from yyr4_linux_control.configurator.web.api import handle_set_action
        from yyr4_linux_control.configurator.web.session import list_recoveries, discard_recovery
        s = self._session()
        handle_set_action(s, {
            "profile":"user","layer":"general","control":"A1",
            "action_spec":{"type":"noop"},
        })
        s.shutdown()
        recs = list_recoveries()
        self.assertEqual(len(recs), 1)
        discard_recovery(recs[0]["recovery_id"])
        self.assertEqual(len(list_recoveries()), 0)

    def test_recovery_dir_mode_700(self):
        from yyr4_linux_control.configurator.web.api import handle_set_action
        from yyr4_linux_control.configurator.web.session import list_recoveries, discard_recovery, RECOVERY_BASE_DIR
        s = self._session()
        handle_set_action(s, {
            "profile":"user","layer":"general","control":"A1",
            "action_spec":{"type":"noop"},
        })
        s.shutdown()
        recs = list_recoveries()
        self.assertGreaterEqual(len(recs), 1)
        rdir = Path(RECOVERY_BASE_DIR) / recs[0]["recovery_id"]
        self.assertTrue(rdir.is_dir())
        mode = os.stat(str(rdir)).st_mode & 0o777
        self.assertEqual(mode, 0o700)
        for rec in recs:
            discard_recovery(rec["recovery_id"])

    def test_manifest_mode_600(self):
        from yyr4_linux_control.configurator.web.api import handle_set_action
        from yyr4_linux_control.configurator.web.session import list_recoveries, discard_recovery, RECOVERY_BASE_DIR
        s = self._session()
        handle_set_action(s, {
            "profile":"user","layer":"general","control":"A1",
            "action_spec":{"type":"noop"},
        })
        s.shutdown()
        recs = list_recoveries()
        mf = Path(RECOVERY_BASE_DIR) / recs[0]["recovery_id"] / "manifest.json"
        mode = os.stat(str(mf)).st_mode & 0o777
        self.assertEqual(mode, 0o600)
        for rec in recs:
            discard_recovery(rec["recovery_id"])

    def test_recovery_no_token(self):
        from yyr4_linux_control.configurator.web.api import handle_set_action
        from yyr4_linux_control.configurator.web.session import list_recoveries, discard_recovery
        s = self._session()
        handle_set_action(s, {
            "profile":"user","layer":"general","control":"A1",
            "action_spec":{"type":"noop"},
        })
        s.shutdown()
        recs = list_recoveries()
        mf_content = json.dumps(recs[0])
        self.assertNotIn("token", mf_content.lower())
        self.assertNotIn("cookie", mf_content.lower())
        self.assertNotIn("csrf", mf_content.lower())
        for rec in recs:
            discard_recovery(rec["recovery_id"])


if __name__ == "__main__":
    unittest.main()
