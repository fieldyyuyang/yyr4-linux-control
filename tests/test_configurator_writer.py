import unittest
import os
import tempfile
from pathlib import Path

from yyr4_linux_control.configurator.writer import (
    write_preview, SameFileError, SymlinkOutputError,
)
from yyr4_linux_control.configurator import build_document, generate_html


_SAMPLE_HTML = "<!DOCTYPE html><html><body>test</body></html>"


class TestConfiguratorWriter(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.addCleanup(self._cleanup)
        self.src = Path(self.tmpdir) / "config.toml"
        self.src.write_text("schema_version = 1\n", encoding="utf-8")

    def _cleanup(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _out(self, name="out.html"):
        return Path(self.tmpdir) / name

    def _write(self, output, force=False):
        return write_preview(_SAMPLE_HTML, output, self.src, force=force)

    # ── Basic success ──

    def test_new_file_written(self):
        out = self._out("new.html")
        result = self._write(out)
        self.assertTrue(out.is_file())
        self.assertEqual(result, out)

    def test_output_is_utf8(self):
        out = self._out("utf8.html")
        self._write(out)
        content = out.read_text("utf-8")
        self.assertEqual(content, _SAMPLE_HTML)

    def test_permissions_not_wider_than_644(self):
        out = self._out("perm.html")
        self._write(out)
        mode = out.stat().st_mode & 0o777
        self.assertLessEqual(mode, 0o644)

    # ── Existing file ──

    def test_existing_no_force_rejected(self):
        out = self._out("exists.html")
        out.write_text("old")
        with self.assertRaises(FileExistsError):
            self._write(out)

    def test_existing_force_replaces(self):
        out = self._out("force.html")
        out.write_text("old")
        self._write(out, force=True)
        self.assertEqual(out.read_text(), _SAMPLE_HTML)

    def test_force_preserves_source_hash(self):
        src_hash = self.src.read_bytes()
        out = self._out("force2.html")
        out.write_text("old")
        self._write(out, force=True)
        self.assertEqual(self.src.read_bytes(), src_hash)

    # ── Symlink rejection ──

    def test_symlink_no_force_rejected(self):
        target = self._out("target.html")
        target.write_text("target content")
        sym = self._out("link.html")
        os.symlink(str(target), str(sym))
        with self.assertRaises(SymlinkOutputError):
            self._write(sym)

    def test_symlink_force_also_rejected(self):
        target = self._out("target2.html")
        target.write_text("target content")
        sym = self._out("link2.html")
        os.symlink(str(target), str(sym))
        with self.assertRaises(SymlinkOutputError):
            self._write(sym, force=True)

    def test_symlink_target_unchanged(self):
        target = self._out("target3.html")
        target.write_text("original")
        sym = self._out("link3.html")
        os.symlink(str(target), str(sym))
        try:
            self._write(sym, force=True)
        except SymlinkOutputError:
            pass
        self.assertEqual(target.read_text(), "original")
        self.assertTrue(sym.is_symlink())

    def test_symlink_to_source_rejected(self):
        sym = self._out("link_to_src.html")
        os.symlink(str(self.src), str(sym))
        with self.assertRaises(SymlinkOutputError):
            self._write(sym)

    # ── Same file detection ──

    def test_hardlink_same_file_rejected(self):
        out = self._out("hardlink.html")
        out.write_text("x")
        # Remove source so we can hardlink to it
        self.src.unlink()
        os.link(str(out), str(self.src))
        with self.assertRaises(SameFileError):
            self._write(out)

    def test_different_path_same_file_rejected(self):
        out = self._out("same.html")
        out.write_text("x")
        alias = Path(self.tmpdir) / "sub" / "../same.html"
        alias.parent.mkdir(parents=True, exist_ok=True)
        self.assertTrue(os.path.samefile(str(out), str(alias.resolve())))
        # Different string path but same inode
        with self.assertRaises(SameFileError):
            write_preview(_SAMPLE_HTML, alias, out)

    # ── Directory errors ──

    def test_output_is_directory_rejected(self):
        d = self._out("mydir")
        d.mkdir()
        with self.assertRaises(IsADirectoryError):
            self._write(d)

    def test_parent_not_exist_rejected(self):
        out = Path(self.tmpdir) / "nonexistent" / "out.html"
        with self.assertRaises(FileNotFoundError):
            self._write(out)

    def test_parent_is_file_rejected(self):
        parent = self._out("parent_file")
        parent.write_text("not a dir")
        out = parent / "out.html"
        with self.assertRaises(NotADirectoryError):
            self._write(out)

    # ── Atomic write properties ──

    def test_temp_file_in_same_directory(self):
        import glob
        before = set(glob.glob(str(Path(self.tmpdir) / "*")))
        out = self._out("atomic.html")
        self._write(out)
        after = set(glob.glob(str(Path(self.tmpdir) / "*")))
        # No leftover temp files
        leftover = after - before - {str(out)}
        self.assertEqual(len(leftover), 0,
                         f"Leftover temp files: {leftover}")

    def test_temp_file_cleaned_on_write_failure(self):
        out = Path(self.tmpdir) / "readonly" / "out.html"
        out.parent.mkdir()
        os.chmod(str(out.parent), 0o400)  # read-only
        try:
            self._write(out, force=True)
        except Exception:
            pass
        os.chmod(str(out.parent), 0o700)  # restore for cleanup
        # Should not have left any files
        self.assertFalse(out.is_file())

    def test_no_x11_no_browser_no_network(self):
        """Writer does not import or use X11, browser, or network APIs."""
        out = self._out("pure.html")
        self._write(out)
        content = out.read_text()
        self.assertNotIn("http://", content)
        self.assertIn(_SAMPLE_HTML, content)

    # ── source config unchanged ──

    def test_source_unchanged_after_success(self):
        src_bytes = self.src.read_bytes()
        out = self._out("src_ok.html")
        self._write(out)
        self.assertEqual(self.src.read_bytes(), src_bytes)

    def test_source_unchanged_after_failure(self):
        src_bytes = self.src.read_bytes()
        out = self._out("src_fail.html")
        out.write_text("existing")
        try:
            self._write(out)
        except FileExistsError:
            pass
        self.assertEqual(self.src.read_bytes(), src_bytes)


if __name__ == "__main__":
    unittest.main()
