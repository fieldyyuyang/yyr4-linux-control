"""M5.4-A2-R4a1: Genuine venv install + yyr4ctl console script smoke test."""
import unittest, os, tempfile, shutil, subprocess, sys, zipfile, json, stat
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestInstalledPackageSmoke(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls.wheel_dir = cls.tmp / "wheel"; cls.wheel_dir.mkdir()
        cls.venv_dir = cls.tmp / "venv"
        cls.home = cls.tmp / "home"
        cls.xdg_config = cls.tmp / "xdg_config"
        cls.xdg_state = cls.tmp / "xdg_state"
        cls.xdg_cache = cls.tmp / "xdg_cache"
        cls.xdg_runtime = cls.tmp / "xdg_runtime"
        for d in [cls.home, cls.xdg_config, cls.xdg_state, cls.xdg_cache, cls.xdg_runtime]:
            d.mkdir(parents=True, exist_ok=True)
        os.chmod(str(cls.xdg_runtime), 0o700)

        # 1. Build wheel: strict no-network
        build_env = os.environ.copy()
        build_env.pop("PYTHONPATH", None)
        build_env["PYTHONNOUSERSITE"] = "1"
        # Use uv build (no network needed if cache has setuptools)
        build_cmd = [
            sys.executable, "-m", "pip", "wheel",
            "--no-deps", "--no-index", "--no-build-isolation",
            "--wheel-dir", str(cls.wheel_dir), str(REPO_ROOT),
        ]
        r_build = subprocess.run(build_cmd, capture_output=True, text=True,
                                 timeout=120, cwd=str(cls.tmp), env=build_env)
        cls.build_rc = r_build.returncode
        cls.build_out = r_build.stdout + r_build.stderr
        wheels = list(cls.wheel_dir.glob("*.whl"))
        cls.wheel_path = wheels[0] if wheels else None
        cls.wheel_name = cls.wheel_path.name if cls.wheel_path else None

        # 2. Create venv
        if cls.wheel_path:
            r_v = subprocess.run([sys.executable, "-m", "venv", str(cls.venv_dir)],
                                 capture_output=True, text=True, timeout=30)
            cls.venv_rc = r_v.returncode
            cls.venv_python = cls.venv_dir / "bin" / "python"
            cls.venv_pip = cls.venv_dir / "bin" / "pip"
            cls.venv_has_python = cls.venv_python.is_file()
            cls.venv_has_pip = cls.venv_pip.is_file()

            # Verify venv identity
            if cls.venv_has_python:
                r_id = subprocess.run(
                    [str(cls.venv_python), "-c",
                     "import sys; print(sys.executable); print(sys.prefix); print(sys.base_prefix)"],
                    capture_output=True, text=True, timeout=10)
                cls.venv_id_lines = r_id.stdout.strip().split("\n")
                cls.venv_exe = cls.venv_id_lines[0] if len(cls.venv_id_lines) > 0 else ""
                cls.venv_prefix = cls.venv_id_lines[1] if len(cls.venv_id_lines) > 1 else ""
                cls.venv_base = cls.venv_id_lines[2] if len(cls.venv_id_lines) > 2 else ""

            # 3. Install wheel via venv pip
            if cls.venv_has_pip:
                inst_env = os.environ.copy()
                inst_env.pop("PYTHONPATH", None)
                inst_env["PYTHONNOUSERSITE"] = "1"
                inst_env["PIP_NO_INDEX"] = "1"
                r_inst = subprocess.run(
                    [str(cls.venv_python), "-m", "pip", "install",
                     "--no-deps", "--no-index", str(cls.wheel_path)],
                    capture_output=True, text=True, timeout=60,
                    cwd=str(cls.tmp), env=inst_env)
                cls.install_rc = r_inst.returncode
                cls.install_out = r_inst.stdout + r_inst.stderr
            else:
                cls.install_rc = -1
        else:
            cls.venv_rc = -1
            cls.install_rc = -1

        # Console script path
        cls.yyr4ctl = cls.venv_dir / "bin" / "yyr4ctl"
        cls.has_yyr4ctl = cls.yyr4ctl.is_file()

        # Wheel content snapshot
        cls.wheel_members = []
        if cls.wheel_path:
            with zipfile.ZipFile(str(cls.wheel_path), "r") as zf:
                cls.wheel_members = sorted(zf.namelist())

        # Metadata version
        cls.dist_version = ""
        if cls.venv_has_python and cls.install_rc == 0:
            r_meta = subprocess.run(
                [str(cls.venv_python), "-c",
                 "import importlib.metadata as m; print(m.version('yyr4-linux-control'))"],
                capture_output=True, text=True, timeout=10)
            cls.dist_version = r_meta.stdout.strip()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(str(cls.tmp), ignore_errors=True)

    def _venv_env(self):
        env = os.environ.copy()
        env.pop("PYTHONPATH", None)
        env["PYTHONNOUSERSITE"] = "1"
        env["HOME"] = str(self.home)
        env["XDG_CONFIG_HOME"] = str(self.xdg_config)
        env["XDG_STATE_HOME"] = str(self.xdg_state)
        env["XDG_CACHE_HOME"] = str(self.xdg_cache)
        env["XDG_RUNTIME_DIR"] = str(self.xdg_runtime)
        return env

    def test_wheel_installs_and_runs_cli_outside_source_tree(self):
        # Build assertions
        self.assertEqual(self.build_rc, 0,
                         f"Wheel build failed: {self.build_out[:500]}")
        self.assertIsNotNone(self.wheel_path, "No wheel produced")
        self.assertEqual(len(list(self.wheel_dir.glob("*.whl"))), 1)

        # Venv assertions
        self.assertEqual(self.venv_rc, 0)
        self.assertTrue(self.venv_has_python, "venv must have python")
        self.assertTrue(self.venv_has_pip, "venv must have pip")
        self.assertIn(str(self.tmp), self.venv_exe)
        self.assertIn(str(self.tmp), self.venv_prefix)
        self.assertNotEqual(self.venv_prefix, self.venv_base)

        # Install assertions
        self.assertEqual(self.install_rc, 0,
                         f"Wheel install failed: {self.install_out[:500]}")
        self.assertNotIn("Downloading", (self.install_out or "").lower())

        # Console script
        self.assertTrue(self.has_yyr4ctl)
        st = os.stat(str(self.yyr4ctl))
        self.assertTrue(st.st_mode & stat.S_IXUSR)
        self.assertNotIn("site-packages/bin", str(self.yyr4ctl))

        # Module path
        r_mod = subprocess.run(
            [str(self.venv_python), "-c",
             "import json, sys, yyr4_linux_control, importlib.metadata as m; "
             "json.dump({'exe': sys.executable, 'prefix': sys.prefix, "
             "'mod': yyr4_linux_control.__file__, 'path': sys.path, "
             "'ver': m.version('yyr4-linux-control')}, sys.stdout)"],
            capture_output=True, text=True, timeout=10, cwd=str(self.tmp),
            env=self._venv_env())
        self.assertEqual(r_mod.returncode, 0, f"Module import failed: {r_mod.stderr[:300]}")
        mod_info = json.loads(r_mod.stdout)
        self.assertIn(str(self.tmp), mod_info["exe"])
        self.assertIn("site-packages", mod_info["mod"])
        self.assertNotIn(str(REPO_ROOT), mod_info["mod"])
        self.assertNotIn(str(REPO_ROOT), str(mod_info["path"]))

        # CLI help
        cli = str(self.yyr4ctl)
        for args in [["--help"], ["editor", "--help"], ["editor", "recover", "--help"]]:
            r = subprocess.run([cli] + args, capture_output=True, text=True,
                               timeout=10, cwd=str(self.tmp), env=self._venv_env())
            self.assertEqual(r.returncode, 0,
                             f"yyr4ctl {' '.join(args)} failed: {r.stderr[:200]}")
            self.assertTrue(r.stdout.strip())
            self.assertNotIn("Traceback", r.stderr + r.stdout)
            self.assertNotIn("ModuleNotFoundError", r.stderr + r.stdout)

        # editor status
        r_st = subprocess.run([cli, "editor", "status"], capture_output=True, text=True,
                              timeout=10, cwd=str(self.tmp), env=self._venv_env())
        self.assertEqual(r_st.returncode, 0)
        self.assertNotIn("Traceback", r_st.stderr + r_st.stdout)

        # Wheel content
        members = self.wheel_members
        pkg_members = [m for m in members if "yyr4_linux_control/" in m]
        self.assertGreater(len(pkg_members), 0)
        has_templates = any("templates.py" in m or "configurator/web" in m for m in members)
        self.assertTrue(has_templates, "Wheel must contain Web resources")
        forbidden = [".git", "__pycache__", ".patch", ".local",
                     "bootstrap", "cookie", "csrf", "secret"]
        for m in members:
            ml = m.lower()
            for fb in forbidden:
                self.assertNotIn(fb, ml, f"Wheel: {m}")


if __name__ == "__main__":
    unittest.main()
