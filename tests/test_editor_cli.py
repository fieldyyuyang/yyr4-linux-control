"""CLI integration tests: yyr4ctl editor argument parsing and startup."""

import unittest, os, tempfile, shutil, subprocess, sys


class TestEditorCLI(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.src = os.path.join(self.tmp, "src.toml")
        shutil.copy(
            os.path.join(os.path.dirname(__file__), "..", "examples",
                         "yyr4-control-from-20260711-backup.toml"),
            self.src,
        )

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _env(self):
        env = os.environ.copy()
        env["PYTHONPATH"] = os.path.join(os.path.dirname(__file__), "..", "src")
        env["PYTHONUNBUFFERED"] = "1"
        return env

    def _run(self, extra_args=None):
        """Run the CLI and collect stdout/stderr for a short time."""
        if extra_args is None:
            extra_args = []
        cmd = (
            "import sys; sys.argv=['yyr4ctl','editor',"
            f"'start','--config','{self.src}',"
            f"'--target','{os.path.join(self.tmp, 'target.toml')}',"
            f"'--idle-timeout','3'"
        )
        for a in extra_args:
            cmd += f",'{a}'"
        cmd += "]; from yyr4_linux_control.management.cli import main; main()"

        proc = subprocess.Popen(
            [sys.executable, "-c", cmd],
            env=self._env(),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        return proc

    def _read_until(self, proc, needle, timeout=10):
        import time as _time
        deadline = _time.time() + timeout
        output = ""
        while _time.time() < deadline:
            line = proc.stdout.readline()
            if line:
                output += line
                if needle in output:
                    return output
            _time.sleep(0.1)
        return output

    def test_cli_help(self):
        r = subprocess.run(
            [sys.executable, "-c",
             "import sys; sys.argv=['yyr4ctl','editor','start','--help']; "
             "from yyr4_linux_control.management.cli import main; main()"],
            env=self._env(), capture_output=True, text=True, timeout=15,
        )
        out = r.stdout + r.stderr
        self.assertIn("config", out.lower())

    def test_cli_startup_output(self):
        proc = self._run()
        try:
            output = self._read_until(proc, "Editor started")
            self.assertIn("Editor started", output)
            self.assertIn("127.0.0.1", output)
        finally:
            proc.terminate()
            try: proc.wait(timeout=5)
            except subprocess.TimeoutExpired: proc.kill(); proc.wait()

    def test_cli_accepts_port(self):
        proc = self._run(["--port", "0"])
        try:
            output = self._read_until(proc, "Editor started")
            self.assertIn("Editor started", output)
        finally:
            proc.terminate()
            try: proc.wait(timeout=5)
            except subprocess.TimeoutExpired: proc.kill(); proc.wait()

    def test_cli_no_open_browser_by_default(self):
        proc = self._run()
        try:
            output = self._read_until(proc, "Editor started")
            self.assertNotIn("Opening", output)
        finally:
            proc.terminate()
            try: proc.wait(timeout=5)
            except subprocess.TimeoutExpired: proc.kill(); proc.wait()


if __name__ == "__main__":
    unittest.main()
