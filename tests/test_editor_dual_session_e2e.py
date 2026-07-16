"""M5.4-A1: Dual-session E2E — real HTTP, cookie/CSRF isolation, shutdown."""
import unittest, os, tempfile, shutil, time, json, http.client, socket


class TestDualSessionE2E(unittest.TestCase):
    """Two servers, full isolation, real HTTP."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        from yyr4_linux_control.configurator.web.server import EditorServer
        srcA = os.path.join(self.tmp, "srcA.toml")
        targetA = os.path.join(self.tmp, "targetA.toml")
        shutil.copy(os.path.join(os.path.dirname(__file__), "..", "examples",
            "yyr4-control-from-20260711-backup.toml"), srcA)
        self.srvA = EditorServer(srcA, targetA, port=0, idle_timeout=60, open_browser=False)
        self.srvA.start(); time.sleep(0.2)
        srcB = os.path.join(self.tmp, "srcB.toml")
        targetB = os.path.join(self.tmp, "targetB.toml")
        shutil.copy(os.path.join(os.path.dirname(__file__), "..", "examples",
            "yyr4-control-from-20260711-backup.toml"), srcB)
        self.srvB = EditorServer(srcB, targetB, port=0, idle_timeout=60, open_browser=False)
        self.srvB.start(); time.sleep(0.2)
        # Bootstrap both
        _, _, scA = self._bootstrap(self.srvA.listen_port, self.srvA._session.bootstrap_token)
        _, _, scB = self._bootstrap(self.srvB.listen_port, self.srvB._session.bootstrap_token)
        self.ckA = self._parse_cookie(scA); self.ckB = self._parse_cookie(scB)
        self.pubA = self.srvA._session.public_session_id; self.pubB = self.srvB._session.public_session_id
        self.portA = self.srvA.listen_port; self.portB = self.srvB.listen_port
        # Get CSRF from authenticated state responses (not from private fields)
        _, stA = self._get(self.srvA.listen_port, f"/s/{self.pubA}/api/v1/state", self.ckA)
        _, stB = self._get(self.srvB.listen_port, f"/s/{self.pubB}/api/v1/state", self.ckB)
        self.csrfA = stA["csrf_token"]; self.csrfB = stB["csrf_token"]

    def tearDown(self):
        self.srvA.stop(); self.srvB.stop(); time.sleep(0.2)
        shutil.rmtree(self.tmp, ignore_errors=True)

    @staticmethod
    def _bootstrap(port, btok):
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("GET", f"/bootstrap/{btok}")
        resp = conn.getresponse()
        loc = resp.getheader("Location", "")
        sc = resp.getheader("Set-Cookie", "")
        resp.read(); conn.close()
        return resp.status, loc, sc

    @staticmethod
    def _parse_cookie(set_cookie_hdr):
        """Extract cookie name=value from Set-Cookie header."""
        parts = set_cookie_hdr.split(";")[0].strip()
        return parts  # "name=value"

    @staticmethod
    def _get(port, path, cookie_hdr):
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("GET", path, headers={"Cookie": cookie_hdr})
        resp = conn.getresponse(); body = resp.read(); conn.close()
        return resp.status, json.loads(body) if body else {}

    @staticmethod
    def _post(port, path, body_dict, cookie_hdr, csrf):
        data = json.dumps(body_dict).encode()
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("POST", path, body=data, headers={
            "Content-Type": "application/json",
            "Cookie": cookie_hdr,
            "X-YYR4-CSRF-Token": csrf,
        })
        resp = conn.getresponse(); body = resp.read(); conn.close()
        return resp.status, json.loads(body) if body else {}

    @staticmethod
    def _port_open(port):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.5)
        r = s.connect_ex(("127.0.0.1", port))
        s.close()
        return r == 0

    def test_01_bootstrap_was_done(self):
        # setUp already bootstrapped — verify cookie header is valid
        self.assertTrue(self.ckA); self.assertIn("yyr4_session", self.ckA)

    def test_02_cookie_b_valid(self):
        self.assertTrue(self.ckB); self.assertIn("yyr4_session", self.ckB)

    def test_03_locations_no_secrets(self):
        _, locA, _ = self._bootstrap(self.srvA.listen_port, self.srvA._session.bootstrap_token)
        _, locB, _ = self._bootstrap(self.srvB.listen_port, self.srvB._session.bootstrap_token)
        for loc in (locA, locB):
            self.assertNotIn(self.srvA._session.bootstrap_token, loc)
            self.assertNotIn(self.srvB._session.bootstrap_token, loc)
            self.assertNotIn("bootstrap", loc)

    def _boot_both(self):
        return self.ckA, self.ckB, self.csrfA, self.csrfB, self.pubA, self.pubB, self.portA, self.portB

    def test_04_get_state_a(self):
        ckA, _, _, _, pubA, _, portA, _ = self._boot_both()
        st, body = self._get(portA, f"/s/{pubA}/api/v1/state", ckA)
        self.assertEqual(st, 200); self.assertIn("config", body)

    def test_05_get_state_b(self):
        _, ckB, _, _, _, pubB, _, portB = self._boot_both()
        st, body = self._get(portB, f"/s/{pubB}/api/v1/state", ckB)
        self.assertEqual(st, 200); self.assertIn("config", body)

    def test_06_mutation_a(self):
        ckA, _, csrfA, _, pubA, _, portA, _ = self._boot_both()
        st, _ = self._post(portA, f"/s/{pubA}/api/v1/control/set-action",
                           {"profile":"user","layer":"general","control":"A1",
                            "action_spec":{"type":"debug_log","message":"test-A"}},
                           ckA, csrfA)
        self.assertEqual(st, 200)

    def test_07_mutation_b(self):
        _, ckB, _, csrfB, _, pubB, _, portB = self._boot_both()
        st, _ = self._post(portB, f"/s/{pubB}/api/v1/control/set-action",
                           {"profile":"user","layer":"general","control":"A2",
                            "action_spec":{"type":"debug_log","message":"test-B"}},
                           ckB, csrfB)
        self.assertEqual(st, 200)

    def test_08_mutations_isolated(self):
        ckA, ckB, csrfA, csrfB, pubA, pubB, portA, portB = self._boot_both()
        # A mutates A1
        self._post(portA, f"/s/{pubA}/api/v1/control/set-action",
                   {"profile":"user","layer":"general","control":"A1","action_spec":{"type":"noop"}},
                   ckA, csrfA)
        # B mutates B1
        self._post(portB, f"/s/{pubB}/api/v1/control/set-action",
                   {"profile":"user","layer":"general","control":"A2","action_spec":{"type":"noop"}},
                   ckB, csrfB)
        # Verify A's state shows A1 changed, B1 unchanged
        _, stA = self._get(portA, f"/s/{pubA}/api/v1/state", ckA)
        ctrlsA = stA["config"]["profiles"][0]["layers"][0]["controls"]
        self.assertEqual(ctrlsA["A1"]["type"], "noop")
        self.assertNotEqual(ctrlsA["A2"]["type"], "noop")
        # Verify B's state shows B1 changed, A1 unchanged
        _, stB = self._get(portB, f"/s/{pubB}/api/v1/state", ckB)
        ctrlsB = stB["config"]["profiles"][0]["layers"][0]["controls"]
        self.assertEqual(ctrlsB["A2"]["type"], "noop")

    def test_09_validate_a_and_b(self):
        ckA, ckB, _, _, pubA, pubB, portA, portB = self._boot_both()
        for ck, pub, port in [(ckA, pubA, portA), (ckB, pubB, portB)]:
            st, body = self._get(port, f"/s/{pub}/api/v1/validate", ck)
            self.assertEqual(st, 200); self.assertTrue(body["validation"]["valid"])

    def test_10_diff_a_and_b(self):
        ckA, ckB, _, _, pubA, pubB, portA, portB = self._boot_both()
        for ck, pub, port in [(ckA, pubA, portA), (ckB, pubB, portB)]:
            st, _ = self._get(port, f"/s/{pub}/api/v1/diff", ck)
            self.assertEqual(st, 200)

    def test_11_cookie_a_rejected_by_b(self):
        ckA, _, _, _, _, pubB, _, portB = self._boot_both()
        st, _ = self._get(portB, f"/s/{pubB}/api/v1/state", ckA)
        self.assertEqual(st, 401)

    def test_12_cookie_b_rejected_by_a(self):
        _, ckB, _, _, pubA, _, portA, _ = self._boot_both()
        st, _ = self._get(portA, f"/s/{pubA}/api/v1/state", ckB)
        self.assertEqual(st, 401)

    def test_13_csrf_a_rejected_by_b(self):
        ckA, _, csrfA, _, _, pubB, _, portB = self._boot_both()
        st, _ = self._post(portB, f"/s/{pubB}/api/v1/control/set-action",
                           {"profile":"user","layer":"general","control":"A1","action_spec":{"type":"noop"}},
                           ckA, csrfA)
        self.assertEqual(st, 401)

    def test_14_csrf_b_rejected_by_a(self):
        _, ckB, _, csrfB, pubA, _, portA, _ = self._boot_both()
        st, _ = self._post(portA, f"/s/{pubA}/api/v1/control/set-action",
                           {"profile":"user","layer":"general","control":"A2","action_spec":{"type":"noop"}},
                           ckB, csrfB)
        self.assertEqual(st, 401)

    def test_15_shutdown_a_then_b_still_works(self):
        """Start fresh servers for shutdown isolation."""
        tmp2 = tempfile.mkdtemp()
        from yyr4_linux_control.configurator.web.server import EditorServer
        srcC = os.path.join(tmp2, "srcC.toml")
        targetC = os.path.join(tmp2, "targetC.toml")
        shutil.copy(os.path.join(os.path.dirname(__file__), "..", "examples",
            "yyr4-control-from-20260711-backup.toml"), srcC)
        srvC = EditorServer(srcC, targetC, port=0, idle_timeout=60, open_browser=False)
        srvC.start(); time.sleep(0.2)
        srcD = os.path.join(tmp2, "srcD.toml")
        targetD = os.path.join(tmp2, "targetD.toml")
        shutil.copy(os.path.join(os.path.dirname(__file__), "..", "examples",
            "yyr4-control-from-20260711-backup.toml"), srcD)
        srvD = EditorServer(srcD, targetD, port=0, idle_timeout=60, open_browser=False)
        srvD.start(); time.sleep(0.2)

        # Bootstrap both
        _, _, scC = self._bootstrap(srvC.listen_port, srvC._session.bootstrap_token)
        _, _, scD = self._bootstrap(srvD.listen_port, srvD._session.bootstrap_token)
        ckC = self._parse_cookie(scC); ckD = self._parse_cookie(scD)
        pubC = srvC._session.public_session_id; pubD = srvD._session.public_session_id
        _, stC = self._get(srvC.listen_port, f"/s/{pubC}/api/v1/state", ckC)
        csrfC = stC["csrf_token"]
        _, stD = self._get(srvD.listen_port, f"/s/{pubD}/api/v1/state", ckD)
        csrfD = stD["csrf_token"]

        # Shutdown C
        st, _ = self._post(srvC.listen_port, f"/s/{pubC}/api/v1/shutdown",
                           {"dirty_policy":"discard"}, ckC, csrfC)
        self.assertEqual(st, 200)
        srvC.stop()
        deadline = time.time() + 8
        while time.time() < deadline:
            if not srvC._thread.is_alive():
                break
            time.sleep(0.2)
        self.assertFalse(srvC._thread.is_alive(), "Server C should stop")
        self.assertFalse(self._port_open(srvC.listen_port), f"Port {srvC.listen_port} should be closed")

        # D still works
        stD2, bodyD = self._get(srvD.listen_port, f"/s/{pubD}/api/v1/state", ckD)
        self.assertEqual(stD2, 200); self.assertIn("config", bodyD)

        # Cleanup
        srvD.stop(); time.sleep(0.5)
        shutil.rmtree(tmp2, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
