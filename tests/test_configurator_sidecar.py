import unittest, os, json, tempfile
from pathlib import Path
from yyr4_linux_control.configurator.sidecar import (
    read_sidecar, write_sidecar, update_sidecar_after_mutation,
)

class TestSidecar(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.draft = Path(self.tmp) / "draft.toml"
        self.draft.write_text("x")
        self.sp = write_sidecar(self.draft, "/src/config.toml", "abc123", "def456", 0)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_create(self):
        sc = read_sidecar(self.draft)
        self.assertEqual(sc["metadata_version"], 1)
        self.assertEqual(sc["base_sha256"], "abc123")
        self.assertEqual(sc["draft_sha256"], "def456")
        self.assertEqual(sc["mutation_count"], 0)

    def test_mode_600(self):
        mode = self.sp.stat().st_mode & 0o777
        self.assertLessEqual(mode, 0o600)

    def test_deterministic_json(self):
        write_sidecar(self.draft, "/src/config.toml", "abc123", "def456", 0)
        t1 = read_sidecar(self.draft)
        write_sidecar(self.draft, "/src/config.toml", "abc123", "def456", 0)
        t2 = read_sidecar(self.draft)
        for k in ("metadata_version", "base_source_path", "base_sha256",
                  "draft_sha256", "mutation_count"):
            self.assertEqual(t1[k], t2[k], f"Mismatch on {k}")

    def test_update_mutation(self):
        update_sidecar_after_mutation(self.draft, "newsha", 5)
        sc = read_sidecar(self.draft)
        self.assertEqual(sc["draft_sha256"], "newsha")
        self.assertEqual(sc["mutation_count"], 5)

    def test_missing_sidecar(self):
        dp2 = Path(self.tmp) / "no-sidecar.toml"
        dp2.write_text("x")
        with self.assertRaises(FileNotFoundError):
            read_sidecar(dp2)

    def test_symlink_sidecar_rejected(self):
        # Remove the sidecar that setUp created so we can replace it with a symlink
        sym = Path(str(self.draft) + ".yyr4-draft.json")
        os.unlink(str(sym))
        target = self.draft.parent / "real.json"
        target.write_text("{}")
        os.symlink(str(target), str(sym))
        self.assertTrue(sym.is_symlink())
        with self.assertRaises((FileNotFoundError, OSError, json.JSONDecodeError)):
            read_sidecar(self.draft)

    def test_created_at_preserved_on_update(self):
        sc1 = read_sidecar(self.draft)
        update_sidecar_after_mutation(self.draft, "newsha", 5)
        sc2 = read_sidecar(self.draft)
        self.assertEqual(sc1["created_at_utc"], sc2["created_at_utc"])

    def test_updated_at_changes_on_update(self):
        sc1 = read_sidecar(self.draft)
        import time; time.sleep(0.01)
        update_sidecar_after_mutation(self.draft, "newsha", 5)
        sc2 = read_sidecar(self.draft)
        self.assertNotEqual(sc1["updated_at_utc"], sc2["updated_at_utc"])

    def test_missing_sidecar_for_nonexistent_draft(self):
        dp3 = Path(self.tmp) / "never-created.toml"
        with self.assertRaises(FileNotFoundError):
            read_sidecar(dp3)

    def test_update_without_sidecar(self):
        dp4 = Path(self.tmp) / "no-sc.toml"
        dp4.write_text("x")
        with self.assertRaises(FileNotFoundError):
            update_sidecar_after_mutation(dp4, "sha", 1)


if __name__ == "__main__":
    unittest.main()
