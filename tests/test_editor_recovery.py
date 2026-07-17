"""M5.4-A2: Recovery — permissions, symlink, manifest, shutdown policies."""
import unittest, os, tempfile, shutil, time, json, http.client
from pathlib import Path


class TestRecoveryPermissions(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        import yyr4_linux_control.configurator.web.session as smod
        self._old = smod.RECOVERY_BASE_DIR
        smod.RECOVERY_BASE_DIR = os.path.join(self.tmp, "recovery")

    def tearDown(self):
        import yyr4_linux_control.configurator.web.session as smod
        smod.RECOVERY_BASE_DIR = self._old
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _start_and_mutate(self):
        from yyr4_linux_control.configurator.web.server import EditorServer
        src = os.path.join(self.tmp, "src.toml")
        target = os.path.join(self.tmp, "target.toml")
        shutil.copy(os.path.join(os.path.dirname(__file__), "..", "examples",
            "yyr4-control-from-20260711-backup.toml"), src)
        s = EditorServer(src, target, port=0, idle_timeout=30, open_browser=False)
        s.start(); time.sleep(0.2)
        pub = s._session.public_session_id
        ck = f"yyr4_session_{pub}={s._session.session_cookie}"
        d = json.dumps({"profile":"user","layer":"general","control":"A1",
                         "action_spec":{"type":"noop"}}).encode()
        conn = http.client.HTTPConnection("127.0.0.1", s.listen_port, timeout=5)
        conn.request("GET", f"/bootstrap/{s._session.bootstrap_token}")
        conn.getresponse().read(); conn.close()
        conn2 = http.client.HTTPConnection("127.0.0.1", s.listen_port, timeout=5)
        conn2.request("POST", f"/s/{pub}/api/v1/control/set-action", body=d,
                      headers={"Content-Type":"application/json","Cookie":ck,
                               "X-YYR4-CSRF-Token":s._session.csrf_token})
        conn2.getresponse().read(); conn2.close()
        return s

    def test_recovery_dir_mode_700(self):
        s = self._start_and_mutate()
        from yyr4_linux_control.configurator.web.session import list_recoveries, discard_recovery
        recs = list_recoveries()
        self.assertGreater(len(recs), 0)
        rdir = Path(os.path.join(self.tmp,"recovery")) / recs[0]["recovery_id"]
        self.assertEqual(os.stat(str(rdir)).st_mode & 0o777, 0o700)
        s.stop()
        for r in list_recoveries(): discard_recovery(r["recovery_id"])

    def test_dirty_session_creates_recovery(self):
        s = self._start_and_mutate()
        from yyr4_linux_control.configurator.web.session import list_recoveries, discard_recovery
        self.assertGreater(len(list_recoveries()), 0)
        s.stop()
        for r in list_recoveries(): discard_recovery(r["recovery_id"])

    def test_clean_session_no_recovery(self):
        from yyr4_linux_control.configurator.web.server import EditorServer
        src = os.path.join(self.tmp, "src2.toml")
        target = os.path.join(self.tmp, "target2.toml")
        shutil.copy(os.path.join(os.path.dirname(__file__), "..", "examples",
            "yyr4-control-from-20260711-backup.toml"), src)
        s = EditorServer(src, target, port=0, idle_timeout=30, open_browser=False)
        s.start(); time.sleep(0.2)
        s.stop()
        from yyr4_linux_control.configurator.web.session import list_recoveries
        self.assertEqual(len(list_recoveries()), 0)

    def test_recovery_manifest_fields(self):
        s = self._start_and_mutate()
        from yyr4_linux_control.configurator.web.session import list_recoveries, discard_recovery
        recs = list_recoveries()
        self.assertGreaterEqual(len(recs), 1)
        r = recs[0]
        for field in ("recovery_version","recovery_id","base_sha256","draft_sha256",
                       "mutation_count","dirty","application_version"):
            self.assertIn(field, r)
        s.stop()
        for r in list_recoveries(): discard_recovery(r["recovery_id"])

    def test_recovery_no_tokens(self):
        s = self._start_and_mutate()
        from yyr4_linux_control.configurator.web.session import list_recoveries, discard_recovery
        recs = list_recoveries()
        txt = json.dumps(recs[0])
        self.assertNotIn("token", txt.lower())
        self.assertNotIn("cookie", txt.lower())
        self.assertNotIn("csrf", txt.lower())
        s.stop()
        for r in list_recoveries(): discard_recovery(r["recovery_id"])


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
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request("GET", f"/bootstrap/{self.srv._session.bootstrap_token}")
        conn.getresponse().read(); conn.close()
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

    def test_keep_recovery(self):
        st, _ = self._shutdown("keep_recovery")
        self.assertEqual(st, 200)
        time.sleep(1)
        from yyr4_linux_control.configurator.web.session import list_recoveries, discard_recovery
        self.assertGreater(len([r for r in list_recoveries() if r.get("dirty")]), 0)
        for r in list_recoveries(): discard_recovery(r["recovery_id"])

    def test_discard(self):
        st, _ = self._shutdown("discard")
        self.assertEqual(st, 200)
        time.sleep(1)

    def test_cancel(self):
        st, _ = self._shutdown("cancel")
        self.assertEqual(st, 200)
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request("GET", f"/s/{self.pub}/api/v1/state", headers={"Cookie": self.ck})
        self.assertEqual(conn.getresponse().status, 200); conn.close()


if __name__ == "__main__":
    unittest.main()
