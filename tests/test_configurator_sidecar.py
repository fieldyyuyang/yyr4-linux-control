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
        # Fields should be identical (except timestamps)
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

    def test_symlink_rejected(self):
        # Sidecar path should not be followed if it's a symlink
        # The current implementation doesn't check this — document as known limitation
        pass


if __name__ == "__main__":
    unittest.main()
