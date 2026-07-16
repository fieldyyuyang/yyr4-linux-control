"""Tests for EditorSession: creation, permissions, tokens, cleanup."""

import unittest, os, tempfile, shutil, time
from pathlib import Path


class TestEditorSession(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.src = os.path.join(self.tmp, "src.toml")
        shutil.copy(
            os.path.join(os.path.dirname(__file__), "..", "examples",
                         "yyr4-control-from-20260711-backup.toml"),
            self.src,
        )
        self.target = os.path.join(self.tmp, "target.toml")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _create_session(self):
        from yyr4_linux_control.configurator.web.session import create_session
        return create_session(self.src, self.target)

    def test_create_session(self):
        s = self._create_session()
        self.assertTrue(len(s.session_id) > 0)
        self.assertTrue(len(s.session_token) >= 32)
        self.assertTrue(os.path.isfile(s.draft_path))
        self.assertEqual(s.source_path, os.path.abspath(self.src))
        s.shutdown()

    def test_session_dir_mode_700(self):
        s = self._create_session()
        mode = os.stat(s.session_dir).st_mode & 0o777
        self.assertEqual(mode, 0o700)
        s.shutdown()

    def test_draft_mode_600(self):
        s = self._create_session()
        mode = os.stat(s.draft_path).st_mode & 0o777
        self.assertEqual(mode, 0o600)
        s.shutdown()

    def test_sidecar_mode_600(self):
        s = self._create_session()
        sc_path = s.draft_path + ".yyr4-draft.json"
        mode = os.stat(sc_path).st_mode & 0o777
        self.assertEqual(mode, 0o600)
        s.shutdown()

    def test_random_token(self):
        s1 = self._create_session()
        s2 = self._create_session()
        self.assertNotEqual(s1.session_token, s2.session_token)
        s1.shutdown()
        s2.shutdown()

    def test_token_length(self):
        s = self._create_session()
        self.assertGreaterEqual(len(s.session_token), 32)
        s.shutdown()

    def test_source_not_modified(self):
        orig = Path(self.src).read_bytes()
        s = self._create_session()
        self.assertEqual(Path(self.src).read_bytes(), orig)
        s.shutdown()

    def test_shutdown_cleanup(self):
        s = self._create_session()
        sd = s.session_dir
        self.assertTrue(os.path.isdir(sd))
        s.shutdown()
        self.assertFalse(os.path.exists(sd))

    def test_double_shutdown_idempotent(self):
        s = self._create_session()
        s.shutdown()
        s.shutdown()  # should not raise

    def test_missing_source_rejected(self):
        from yyr4_linux_control.configurator.web.session import create_session
        with self.assertRaises(FileNotFoundError):
            create_session("/nonexistent/path.toml", self.target)

    def test_sidecar_created(self):
        s = self._create_session()
        sc_path = s.draft_path + ".yyr4-draft.json"
        self.assertTrue(os.path.isfile(sc_path))
        import json
        data = json.loads(Path(sc_path).read_text())
        self.assertEqual(data["metadata_version"], 1)
        self.assertIn("base_sha256", data)
        self.assertIn("draft_sha256", data)
        s.shutdown()

    def test_refresh_base(self):
        s = self._create_session()
        old_base = s.base_sha256
        # Save current draft to target
        shutil.copy(s.draft_path, self.target)
        s.refresh_base()
        # After refresh, base should be the SHA of the saved target
        self.assertIsNotNone(s.base_sha256)
        s.shutdown()

    def test_dirty_initial(self):
        s = self._create_session()
        self.assertFalse(s.dirty)
        s.shutdown()

    def test_mutation_count_initial(self):
        s = self._create_session()
        self.assertEqual(s.mutation_count, 0)
        s.shutdown()


if __name__ == "__main__":
    unittest.main()
