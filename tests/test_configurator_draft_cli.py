import unittest, os, json, subprocess, tempfile, shutil, sys
from pathlib import Path

def _yyr4ctl(*args):
    env = os.environ.copy()
    env["PYTHONPATH"] = os.path.join(os.path.dirname(__file__), "..", "src")
    r = subprocess.run(
        [sys.executable, "-c", "from yyr4_linux_control.management.cli import main; main()"] + list(args),
        capture_output=True, text=True, env=env, timeout=30,
        cwd=tempfile.mkdtemp(),
    )
    return r

_SRC = Path(__file__).resolve().parent.parent
_EXAMPLE = _SRC / "examples/yyr4-control-from-20260711-backup.toml"

class TestDraftCLI(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(self.tmp, ignore_errors=True))
        self.draft = Path(self.tmp) / "draft.toml"

    def test_create(self):
        r = _yyr4ctl("draft", "create", "--config", str(_EXAMPLE), "--output", str(self.draft))
        self.assertEqual(r.returncode, 0, f"stderr={r.stderr}")
        self.assertIn("Draft created", r.stdout)
        self.assertTrue(self.draft.is_file())

    def test_validate(self):
        _yyr4ctl("draft", "create", "--config", str(_EXAMPLE), "--output", str(self.draft))
        r = _yyr4ctl("draft", "validate", "--draft", str(self.draft))
        self.assertEqual(r.returncode, 0)
        self.assertIn("Valid: True", r.stdout)

    def test_validate_json(self):
        _yyr4ctl("draft", "create", "--config", str(_EXAMPLE), "--output", str(self.draft))
        r = _yyr4ctl("draft", "validate", "--draft", str(self.draft), "--format", "json")
        self.assertEqual(r.returncode, 0)
        data = json.loads(r.stdout)
        self.assertTrue(data["valid"])

    def test_diff(self):
        _yyr4ctl("draft", "create", "--config", str(_EXAMPLE), "--output", str(self.draft))
        aj = self.draft.parent / "action.json"
        aj.write_text('{"type":"debug_log","message":"diff-test"}')
        _yyr4ctl("draft", "set-action", "--draft", str(self.draft),
                 "--profile", "user", "--layer", "general",
                 "--control", "A1", "--action-json", str(aj))
        r = _yyr4ctl("draft", "diff", "--draft", str(self.draft))
        self.assertEqual(r.returncode, 0)
        self.assertIn("changed", r.stdout)

    def test_diff_unified(self):
        _yyr4ctl("draft", "create", "--config", str(_EXAMPLE), "--output", str(self.draft))
        aj = self.draft.parent / "action.json"
        aj.write_text('{"type":"debug_log","message":"diff-test"}')
        _yyr4ctl("draft", "set-action", "--draft", str(self.draft),
                 "--profile", "user", "--layer", "general",
                 "--control", "A1", "--action-json", str(aj))
        r = _yyr4ctl("draft", "diff", "--draft", str(self.draft), "--format", "unified")
        self.assertEqual(r.returncode, 0)
        self.assertIn("+++ draft", r.stdout)

    def test_save(self):
        _yyr4ctl("draft", "create", "--config", str(_EXAMPLE), "--output", str(self.draft))
        target = Path(self.tmp) / "saved.toml"
        r = _yyr4ctl("draft", "save", "--draft", str(self.draft),
                     "--target", str(target), "--backup-dir", str(Path(self.tmp) / "backups"))
        self.assertEqual(r.returncode, 0, f"stderr={r.stderr}")
        self.assertTrue(target.is_file())

    def test_missing_sidecar(self):
        self.draft.write_text("x")
        r = _yyr4ctl("draft", "validate", "--draft", str(self.draft))
        self.assertNotEqual(r.returncode, 0)

    def test_diff_json(self):
        _yyr4ctl("draft", "create", "--config", str(_EXAMPLE), "--output", str(self.draft))
        aj = self.draft.parent / "action.json"
        aj.write_text('{"type":"debug_log","message":"diff-test"}')
        _yyr4ctl("draft", "set-action", "--draft", str(self.draft),
                 "--profile", "user", "--layer", "general",
                 "--control", "A1", "--action-json", str(aj))
        r = _yyr4ctl("draft", "diff", "--draft", str(self.draft), "--format", "json")
        self.assertEqual(r.returncode, 0)


if __name__ == "__main__":
    unittest.main()
