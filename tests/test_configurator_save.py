import unittest, os, tempfile, shutil
from pathlib import Path
from yyr4_linux_control.configurator.save import (
    save_draft, restore_backup, ConcurrentModificationError,
    SymlinkTargetError, SaveValidationError,
)
from yyr4_linux_control.configurator.draft import ConfigDraft
from yyr4_linux_control.control.config import load_control_config_from_file
from yyr4_linux_control.control.actions import DebugLogAction

class TestSave(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(self.tmp, ignore_errors=True))
        self.draft = ConfigDraft(Path("examples/yyr4-control-from-20260711-backup.toml"))

    def _t(self, name="target.toml"):
        return Path(self.tmp) / name

    def test_new_target_save_verified(self):
        r = save_draft(self.draft, self._t(), None)
        self.assertTrue(r.verified)
        self.assertEqual(self._t().stat().st_mode & 0o777, 0o600)

    def test_new_target_no_backup(self):
        r = save_draft(self.draft, self._t(), None, backup_dir=Path(self.tmp) / "bkups")
        self.assertIsNone(r.backup_path)

    def test_concurrent_new_file_blocked(self):
        t = self._t()
        t.write_text("concurrent")
        with self.assertRaises(ConcurrentModificationError):
            save_draft(self.draft, t, None)

    def test_existing_with_backup(self):
        t = self._t()
        r1 = save_draft(self.draft, t, None)
        r2 = save_draft(self.draft, t, r1.saved_sha256, backup_dir=Path(self.tmp) / "b")
        self.assertTrue(r2.verified)
        self.assertIsNotNone(r2.backup_path)
        self.assertTrue(r2.backup_path.is_file())

    def test_wrong_sha_blocked(self):
        t = self._t()
        save_draft(self.draft, t, None)
        with self.assertRaises(ConcurrentModificationError):
            save_draft(self.draft, t, "00000000000000000000000000000000")

    def test_backup_mode_600(self):
        t = self._t()
        r1 = save_draft(self.draft, t, None)
        r2 = save_draft(self.draft, t, r1.saved_sha256, backup_dir=Path(self.tmp) / "b")
        self.assertLessEqual(r2.backup_path.stat().st_mode & 0o777, 0o600)

    def test_symlink_target_rejected(self):
        t = self._t()
        r = Path(self.tmp) / "real.toml"
        r.write_text("x")
        os.symlink(str(r), str(t))
        with self.assertRaises(SymlinkTargetError):
            save_draft(self.draft, t, None)

    def test_source_unchanged(self):
        src = Path(self.tmp) / "src.toml"
        src.write_bytes(Path("examples/yyr4-control-from-20260711-backup.toml").read_bytes())
        sb = src.read_bytes()
        d2 = ConfigDraft(src)
        save_draft(d2, self._t("out.toml"), None)
        self.assertEqual(src.read_bytes(), sb)

    # ── Rollback ──

    def test_restore_backup_success(self):
        t = self._t()
        r1 = save_draft(self.draft, t, None)
        self.draft.set_action("user", "general", "A1", DebugLogAction("mod"))
        r2 = save_draft(self.draft, t, r1.saved_sha256, backup_dir=Path(self.tmp) / "b")
        rt = restore_backup(r2.backup_path, t, r2.saved_sha256,
                            new_backup_dir=Path(self.tmp) / "b")
        self.assertTrue(rt.is_file())
        reloaded = load_control_config_from_file(rt)
        from yyr4_linux_control.control.models import ProfileId
        a1 = reloaded.profiles[ProfileId("user")].layers["general"].controls.get("A1")
        self.assertIsInstance(a1, type(self.draft.base_config.profiles[
            ProfileId("user")].layers["general"].controls["A1"]))

    def test_restore_wrong_sha_blocked(self):
        t = self._t()
        r1 = save_draft(self.draft, t, None)
        self.draft.set_action("user", "general", "A1", DebugLogAction("mod"))
        r2 = save_draft(self.draft, t, r1.saved_sha256, backup_dir=Path(self.tmp) / "b")
        with self.assertRaises(ConcurrentModificationError):
            restore_backup(r2.backup_path, t, "00000000000000000000000000000000")

    def test_restore_backup_symlink_rejected(self):
        bp = Path(self.tmp) / "real.bak"
        bp.write_text("x")
        sym = Path(self.tmp) / "link.bak"
        os.symlink(str(bp), str(sym))
        t = self._t()
        save_draft(self.draft, t, None)
        with self.assertRaises(SymlinkTargetError):
            restore_backup(sym, t, "any")


if __name__ == "__main__":
    unittest.main()
