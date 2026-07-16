import unittest, os, tempfile, shutil
from pathlib import Path
from yyr4_linux_control.configurator.save import (
    save_draft, restore_backup, ConcurrentModificationError,
    SymlinkTargetError, SaveValidationError, ConfigSaveResult,
)
from yyr4_linux_control.configurator.draft import ConfigDraft
from yyr4_linux_control.configurator.sidecar import write_sidecar, read_sidecar
from yyr4_linux_control.control.config import load_control_config_from_file
from yyr4_linux_control.control.actions import DebugLogAction

class TestSaveVerification(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(self.tmp, ignore_errors=True))
        self.draft = ConfigDraft(Path("examples/yyr4-control-from-20260711-backup.toml"))

    def _target(self, name="target.toml"):
        return Path(self.tmp) / name

    # New target
    def test_new_target_save(self):
        t = self._target()
        r = save_draft(self.draft, t, None)
        self.assertTrue(r.verified)
        self.assertTrue(t.is_file())
        self.assertEqual(t.stat().st_mode & 0o777, 0o600)

    def test_new_target_no_backup(self):
        t = self._target()
        r = save_draft(self.draft, t, None, backup_dir=Path(self.tmp) / "backups")
        self.assertIsNone(r.backup_path)

    def test_concurrent_new_file_detected(self):
        t = self._target()
        # Simulate concurrent creation by pre-creating the file before save
        t.write_text("concurrent")
        with self.assertRaises(ConcurrentModificationError):
            save_draft(self.draft, t, None)

    # Existing target
    def test_existing_target_save(self):
        t = self._target()
        r1 = save_draft(self.draft, t, None)
        r2 = save_draft(self.draft, t, r1.saved_sha256, backup_dir=Path(self.tmp) / "bkups")
        self.assertTrue(r2.verified)
        self.assertIsNotNone(r2.backup_path)

    def test_existing_target_wrong_sha(self):
        t = self._target()
        save_draft(self.draft, t, None)
        self.draft.set_action("user", "general", "A1", DebugLogAction("mod"))
        with self.assertRaises(ConcurrentModificationError):
            save_draft(self.draft, t, "00000000")

    def test_backup_mode(self):
        t = self._target()
        r1 = save_draft(self.draft, t, None)
        r2 = save_draft(self.draft, t, r1.saved_sha256, backup_dir=Path(self.tmp) / "bkups")
        mode = r2.backup_path.stat().st_mode & 0o777
        self.assertLessEqual(mode, 0o600)

    def test_symlink_target_rejected(self):
        t = self._target()
        r = Path(self.tmp) / "real.toml"
        r.write_text("x")
        os.symlink(str(r), str(t))
        with self.assertRaises(SymlinkTargetError):
            save_draft(self.draft, t, None)

    def test_source_unchanged(self):
        src = Path(self.tmp) / "src.toml"
        ref = Path("examples/yyr4-control-from-20260711-backup.toml")
        src.write_bytes(ref.read_bytes())
        d2 = ConfigDraft(src)
        src_bytes = src.read_bytes()
        t = self._target("from-src.toml")
        save_draft(d2, t, None)
        self.assertEqual(src.read_bytes(), src_bytes)

    def test_draft_unchanged_after_save(self):
        t = self._target()
        v1 = self.draft.validate()
        save_draft(self.draft, t, None)
        v2 = self.draft.validate()
        self.assertEqual(v1.serialized_sha256, v2.serialized_sha256)


if __name__ == "__main__":
    unittest.main()
