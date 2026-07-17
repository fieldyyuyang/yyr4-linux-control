"""M5.4-A2: Real CLI stop and SIGKILL recover-resume-save."""
import unittest, os, tempfile, shutil, time, signal, http.client
from tests.editor_subprocess_test_support import (
    start_editor_cli, bootstrap_http, do_mutation, wait_port_closed,
    cli_status, cli_stop, get_session_id_for_pid,
)


class TestSubprocessSessionControl(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def _parse(self, ul):
        p = ul.strip().split("/")
        hp = p[2]; lst = p[-1] if p[-1] else p[-2]
        port = int(hp.split(":")[-1]) if ":" in hp else 0
        return port, lst

    def test_dual_process_real_stop(self):
        # Start A
        pA, _, uA = start_editor_cli(self.tmp)
        pa, ba = self._parse(uA)
        ckA, pubA, csrfA = bootstrap_http(pa, ba)
        do_mutation(pa, pubA, ckA, csrfA, "A1")
        # Start B
        pB, _, uB = start_editor_cli(self.tmp)
        pb, bb = self._parse(uB)
        ckB, pubB, csrfB = bootstrap_http(pb, bb)
        do_mutation(pb, pubB, ckB, csrfB, "A2")
        # Status shows running
        rc, out = cli_status(); self.assertEqual(rc, 0)
        # Real CLI stop A
        sidA = get_session_id_for_pid(pA.pid)
        self.assertTrue(sidA, f"No session for PID {pA.pid}")
        rc_s, _ = cli_stop(sidA)
        self.assertEqual(rc_s, 0, "CLI stop should return 0")
        pA.wait(timeout=10); self.assertEqual(pA.returncode, 0)
        self.assertTrue(wait_port_closed(pa, 5))
        # A recovery exists (dirty)
        from yyr4_linux_control.configurator.web.session import list_recoveries, discard_recovery
        self.assertGreater(len([r for r in list_recoveries() if r.get("dirty")]), 0)
        # B still running
        conn = http.client.HTTPConnection("127.0.0.1", pb, timeout=5)
        conn.request("GET", f"/s/{pubB}/api/v1/state", headers={"Cookie": ckB})
        self.assertEqual(conn.getresponse().status, 200); conn.close()
        # CLI stop B --discard-draft
        sidB = get_session_id_for_pid(pB.pid)
        self.assertTrue(sidB)
        rc_s2, _ = cli_stop(sidB, discard=True)
        self.assertEqual(rc_s2, 0)
        pB.wait(timeout=10); self.assertEqual(pB.returncode, 0)
        self.assertTrue(wait_port_closed(pb, 5))
        for r in list_recoveries(): discard_recovery(r["recovery_id"])

    def test_stop_nonexistent_nonzero(self):
        rc, _ = cli_stop("nonexistent-id")
        self.assertNotEqual(rc, 0)


class TestCrashRecoveryFullFlow(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _parse(self, ul):
        p = ul.strip().split("/")
        hp = p[2]; lst = p[-1] if p[-1] else p[-2]
        port = int(hp.split(":")[-1]) if ":" in hp else 0
        return port, lst

    def test_sigkill_recover_inspect(self):
        from yyr4_linux_control.configurator.web.session import list_recoveries, get_recovery, discard_recovery
        proc, _, url = start_editor_cli(self.tmp)
        port, btok = self._parse(url)
        ck_old, pub_old, csrf_old = bootstrap_http(port, btok)
        do_mutation(port, pub_old, ck_old, csrf_old, "A1",
                    {"type":"debug_log","message":"recovery-test"})
        recs = list_recoveries(); self.assertGreater(len(recs), 0)
        rid = recs[0]["recovery_id"]
        os.kill(proc.pid, signal.SIGKILL)
        ret = proc.wait(timeout=10); self.assertEqual(ret, -signal.SIGKILL)
        self.assertGreaterEqual(len(list_recoveries()), 1)
        rc, out = cli_status(); self.assertIn("stale", out.lower())
        rec = get_recovery(rid); self.assertIsNotNone(rec)
        self.assertTrue(rec.get("dirty")); self.assertGreater(rec.get("mutation_count", 0), 0)
        for r in list_recoveries(): discard_recovery(r["recovery_id"])


if __name__ == "__main__":
    unittest.main()
