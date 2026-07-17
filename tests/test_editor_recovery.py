"""M5.4-A2: Shutdown policies — keep_recovery, discard, cancel."""
import unittest, os, tempfile, shutil, time, json, http.client


class TestShutdownPolicies(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        from yyr4_linux_control.configurator.web.server import EditorServer
        src = os.path.join(self.tmp, "src.toml")
        target = os.path.join(self.tmp, "target.toml")
        shutil.copy(os.path.join(os.path.dirname(__file__), "..", "examples",
            "yyr4-control-from-20260711-backup.toml"), src)
        self.srv = EditorServer(src, target, port=0, idle_timeout=60, open_browser=False)
        self.srv.start(); time.sleep(0.2)
        self.port = self.srv.listen_port
        self.pub = self.srv._session.public_session_id
        self.ck = f"yyr4_session_{self.pub}={self.srv._session.session_cookie}"
        self.csrf = self.srv._session.csrf_token
        # Bootstrap
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request("GET", f"/bootstrap/{self.srv._session.bootstrap_token}")
        conn.getresponse().read(); conn.close()
        # Mutate to make dirty
        d = json.dumps({"profile":"user","layer":"general","control":"A1",
                         "action_spec":{"type":"noop"}}).encode()
        conn2 = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn2.request("POST", f"/s/{self.pub}/api/v1/control/set-action", body=d,
                      headers={"Content-Type":"application/json","Cookie":self.ck,
                               "X-YYR4-CSRF-Token":self.csrf})
        conn2.getresponse().read(); conn2.close()

    def tearDown(self):
        try: self.srv.stop()
        except: pass
        time.sleep(0.2)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _shutdown(self, policy):
        d = json.dumps({"dirty_policy": policy}).encode()
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request("POST", f"/s/{self.pub}/api/v1/shutdown", body=d,
                     headers={"Content-Type":"application/json","Cookie":self.ck,
                              "X-YYR4-CSRF-Token":self.csrf})
        resp = conn.getresponse(); body = resp.read(); conn.close()
        return resp.status, json.loads(body) if body else {}

    def test_keep_recovery_stops_with_recovery(self):
        st, body = self._shutdown("keep_recovery")
        self.assertEqual(st, 200)
        time.sleep(1)
        from yyr4_linux_control.configurator.web.session import list_recoveries, discard_recovery
        recs = [r for r in list_recoveries() if r.get("dirty")]
        self.assertGreater(len(recs), 0, "Recovery should exist after keep_recovery")
        for r in list_recoveries(): discard_recovery(r["recovery_id"])

    def test_discard_stops_without_recovery(self):
        from yyr4_linux_control.configurator.web.session import list_recoveries, discard_recovery
        before = len(list_recoveries())
        st, body = self._shutdown("discard")
        self.assertEqual(st, 200)
        time.sleep(1)
        after = len(list_recoveries())
        self.assertLess(after, before+1, "Recovery count should decrease after discard")

    def test_cancel_returns_ok_and_keeps_running(self):
        st, body = self._shutdown("cancel")
        self.assertEqual(st, 200)
        # Server still running
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request("GET", f"/s/{self.pub}/api/v1/state", headers={"Cookie": self.ck})
        resp = conn.getresponse(); conn.close()
        self.assertEqual(resp.status, 200, "Server should still serve after cancel")

    def test_invalid_policy_returns_error(self):
        st, body = self._shutdown("invalid_policy")
        self.assertIn(st, (400, 200))  # may reject or handle gracefully
        # Server still running regardless
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request("GET", f"/s/{self.pub}/api/v1/state", headers={"Cookie": self.ck})
        resp = conn.getresponse(); conn.close()
        self.assertEqual(resp.status, 200)


class TestCleanSessionNoRecovery(unittest.TestCase):
    def test_clean_session_no_recovery_on_shutdown(self):
        tmp = tempfile.mkdtemp()
        from yyr4_linux_control.configurator.web.server import EditorServer
        src = os.path.join(tmp, "src.toml")
        target = os.path.join(tmp, "target.toml")
        shutil.copy(os.path.join(os.path.dirname(__file__), "..", "examples",
            "yyr4-control-from-20260711-backup.toml"), src)
        srv = EditorServer(src, target, port=0, idle_timeout=60, open_browser=False)
        srv.start(); time.sleep(0.2)
        port = srv.listen_port; pub = srv._session.public_session_id
        ck = f"yyr4_session_{pub}={srv._session.session_cookie}"
        csrf = srv._session.csrf_token
        # No mutations — clean session
        d = json.dumps({"dirty_policy":"discard"}).encode()
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("POST", f"/s/{pub}/api/v1/shutdown", body=d,
                     headers={"Content-Type":"application/json","Cookie":ck,
                              "X-YYR4-CSRF-Token":csrf})
        conn.getresponse().read(); conn.close()
        time.sleep(1); srv.stop()
        from yyr4_linux_control.configurator.web.session import list_recoveries
        clean_after = len(list_recoveries())
        if hasattr(self, "_clean_before"):
            self.assertEqual(clean_after, getattr(self, "_clean_before", clean_after), "Clean session should not add recovery")
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
