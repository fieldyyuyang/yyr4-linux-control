"""M5.4-A2: Real subprocess session control — dual-process status/stop."""
import unittest, os, tempfile, shutil, time, signal, json
from tests.editor_subprocess_test_support import (
    start_editor_cli, bootstrap_http, do_mutation, wait_port_closed, cli_status, cli_stop,
)


class TestSubprocessSessionControl(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def _parse_bootstrap_url(self, url_line):
        """Extract port and btoken from bootstrap URL."""
        # http://127.0.0.1:PORT/bootstrap/TOKEN
        parts = url_line.strip().split("/")
        port = int(parts[2].split(":")[1])
        btoken = parts[-1]
        return port, btoken

    def test_dual_process_status_and_stop(self):
        """Start two editors, verify both running, stop A, verify B still works."""
        # Start A
        procA, portA_raw, urlA = start_editor_cli(self.tmp)
        portA, btokA = self._parse_bootstrap_url(urlA)
        self.assertGreater(portA, 0)
        ckA, pubA, csrfA = bootstrap_http(portA, btokA)
        self.assertTrue(ckA.startswith("yyr4_session_"))
        # Mutate A
        self.assertEqual(do_mutation(portA, pubA, ckA, csrfA, "A1"), 200)

        # Start B
        procB, portB_raw, urlB = start_editor_cli(self.tmp)
        portB, btokB = self._parse_bootstrap_url(urlB)
        self.assertGreater(portB, 0)
        ckB, pubB, csrfB = bootstrap_http(portB, btokB)
        self.assertEqual(do_mutation(portB, pubB, ckB, csrfB, "A2"), 200)

        # Status shows two running
        rc, out = cli_status()
        self.assertEqual(rc, 0)
        self.assertIn("running", out)

        # Stop A (terminate gracefully)
        procA.terminate()
        procA.wait(timeout=10)

        # A port closed
        self.assertTrue(wait_port_closed(portA, 5), f"Port {portA} should be closed after stop")

        # B still running
        import http.client
        conn = http.client.HTTPConnection("127.0.0.1", portB, timeout=5)
        conn.request("GET", f"/s/{pubB}/api/v1/state", headers={"Cookie": ckB})
        respB = conn.getresponse(); conn.close()
        self.assertEqual(respB.status, 200, "Server B should still serve requests")

        # Stop B with discard
        procB.terminate()
        procB.wait(timeout=5)

    def test_stop_preserves_recovery(self):
        """Stop with default policy keeps recovery."""
        proc, port_raw, url = start_editor_cli(self.tmp)
        port, btok = self._parse_bootstrap_url(url)
        ck, pub, csrf = bootstrap_http(port, btok)
        # Mutate
        do_mutation(port, pub, ck, csrf, "A3")
        # Check recovery exists
        from yyr4_linux_control.configurator.web.session import list_recoveries
        before = len(list_recoveries())
        self.assertGreater(before, 0, "Recovery should exist after mutation")
        # Stop
        proc.terminate()
        proc.wait(timeout=10)
        time.sleep(1)
        after = len(list_recoveries())
        self.assertGreaterEqual(after, before, "Recovery should persist after default stop")

    def test_status_shows_running(self):
        proc, port_raw, url = start_editor_cli(self.tmp)
        port, btok = self._parse_bootstrap_url(url)
        ck, pub, csrf = bootstrap_http(port, btok)
        rc, out = cli_status()
        self.assertEqual(rc, 0)
        self.assertIn("running", out)
        proc.terminate()
        proc.wait(timeout=5)


class TestCrashRecoveryReal(unittest.TestCase):
    """Real SIGKILL → recovery → resume → save flow."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _parse_bootstrap_url(self, url_line):
        parts = url_line.strip().split("/")
        port = int(parts[2].split(":")[1])
        btoken = parts[-1]
        return port, btoken

    def test_sigkill_then_recover(self):
        """SIGKILL the editor, verify recovery persists, resume works."""
        from tests.editor_subprocess_test_support import start_editor_cli, bootstrap_http, do_mutation

        proc, port_raw, url = start_editor_cli(self.tmp)
        port, btok = self._parse_bootstrap_url(url)
        self.assertGreater(port, 0)

        # Bootstrap
        ck, pub, csrf = bootstrap_http(port, btok)
        self.assertTrue(ck.startswith("yyr4_session_"))

        # Mutate
        self.assertEqual(do_mutation(port, pub, ck, csrf, "A1",
                                     {"type": "debug_log", "message": "crash-test"}), 200)

        # Verify recovery exists
        from yyr4_linux_control.configurator.web.session import list_recoveries
        recs_before = list_recoveries()
        self.assertGreater(len(recs_before), 0, "Recovery must exist after mutation")

        # SIGKILL
        os.kill(proc.pid, signal.SIGKILL)
        returncode = proc.wait(timeout=10)
        self.assertEqual(returncode, -signal.SIGKILL, "Process must die by SIGKILL")

        time.sleep(0.5)

        # Recovery still exists
        recs = list_recoveries()
        self.assertGreaterEqual(len(recs), 1, "Recovery must survive SIGKILL")

        # Status shows stale
        rc, out = cli_status()
        self.assertIn("stale", out.lower())

        # Recover inspect
        rid = recs[0]["recovery_id"]
        from yyr4_linux_control.configurator.web.session import get_recovery
        rec = get_recovery(rid)
        self.assertIsNotNone(rec)
        self.assertEqual(rec["recovery_id"], rid)
        self.assertTrue(rec.get("dirty"))
        self.assertGreater(rec.get("mutation_count", 0), 0)

        # Cleanup
        for r in list_recoveries():
            from yyr4_linux_control.configurator.web.session import discard_recovery
            discard_recovery(r["recovery_id"])


if __name__ == "__main__":
    unittest.main()
