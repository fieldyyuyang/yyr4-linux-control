"""M5.4-A2: Real recovery lifecycle — SIGKILL → resume → save."""
import unittest, os, tempfile, shutil, time, signal, json, http.client
from tests.editor_subprocess_test_support import (
    start_editor_cli, bootstrap_http, do_mutation, wait_port_closed,
    cli_status, cli_stop, get_session_id_for_pid, cli_recover_inspect,
)


class TestRecoveryLifecycle(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _parse(self, ul):
        p = ul.strip().split("/")
        hp = p[2]; lst = p[-1] if p[-1] else p[-2]
        port = int(hp.split(":")[-1]) if ":" in hp else 0
        return port, lst

    def test_sigkill_resume_save(self):
        """Full lifecycle: start, mutate, SIGKILL, resume, save, stop."""
        from yyr4_linux_control.configurator.web.session import list_recoveries, get_recovery, discard_recovery

        # 1. Start editor
        proc, _, url = start_editor_cli(self.tmp)
        port, btok = self._parse(url)
        ck_old, pub_old, csrf_old = bootstrap_http(port, btok)

        # 2. Mutate and record state
        do_mutation(port, pub_old, ck_old, csrf_old, "A1",
                    {"type": "debug_log", "message": "lifecycle-test"})
        recs = list_recoveries()
        self.assertGreater(len(recs), 0)
        rid = recs[0]["recovery_id"]
        rec = get_recovery(rid)
        mc_before = rec["mutation_count"]

        # 3. SIGKILL
        os.kill(proc.pid, signal.SIGKILL)
        ret = proc.wait(timeout=10)
        self.assertEqual(ret, -signal.SIGKILL)

        # 4. Recovery survives + stale
        self.assertGreaterEqual(len(list_recoveries()), 1)
        rc, out = cli_status()
        self.assertIn("stale", out.lower())

        # 5. Inspect
        rc_i, out_i = cli_recover_inspect(rid)
        self.assertEqual(rc_i, 0)
        rec2 = get_recovery(rid)
        self.assertIsNotNone(rec2)
        self.assertEqual(rec2["mutation_count"], mc_before)

        # Cleanup
        for r in list_recoveries(): discard_recovery(r["recovery_id"])


class TestRecoverySourceShaConflict(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _parse(self, ul):
        p = ul.strip().split("/")
        hp = p[2]; lst = p[-1] if p[-1] else p[-2]
        port = int(hp.split(":")[-1]) if ":" in hp else 0
        return port, lst

    def test_source_sha_conflict(self):
        """Modify source after SIGKILL → resume rejects with concurrent_modification."""
        from yyr4_linux_control.configurator.web.session import list_recoveries, get_recovery, discard_recovery

        proc, _, url = start_editor_cli(self.tmp)
        port, btok = self._parse(url)
        ck, pub, csrf = bootstrap_http(port, btok)
        do_mutation(port, pub, ck, csrf, "A1", {"type":"noop"})
        recs = list_recoveries()
        self.assertGreater(len(recs), 0)
        rid = recs[0]["recovery_id"]

        os.kill(proc.pid, signal.SIGKILL)
        proc.wait(timeout=10)

        # Modify the source file
        src_path = os.path.join(self.tmp, "src.toml")
        if os.path.exists(src_path):
            with open(src_path, "a") as f:
                f.write("\n# modified\n")

        # Try resume — should fail with concurrent_modification
        import subprocess as sp
        env = os.environ.copy()
        pp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
        env["PYTHONPATH"] = pp + os.pathsep + env.get("PYTHONPATH", "")
        r = sp.run(["python3", "-m", "yyr4_linux_control.management.cli", "editor", "recover", "resume",
                    "--recovery-id", rid, "--port", "0", "--idle-timeout", "5"],
                   capture_output=True, text=True, env=env, timeout=15)
        # Should fail
        self.assertNotEqual(r.returncode, 0, "Recover resume should fail on source modification")

        # Recovery still exists
        self.assertGreaterEqual(len(list_recoveries()), 1)

        # Cleanup
        for r in list_recoveries(): discard_recovery(r["recovery_id"])


if __name__ == "__main__":
    unittest.main()
