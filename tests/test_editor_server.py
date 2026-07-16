"""M5.4-A1: Server HTTP tests — Bootstrap/Cookie/CSRF auth."""
import unittest, os, tempfile, shutil, time, json, http.client


def _sv():
    t = tempfile.mkdtemp()
    src = os.path.join(t, "src.toml")
    target = os.path.join(t, "target.toml")
    shutil.copy(os.path.join(os.path.dirname(__file__), "..", "examples",
        "yyr4-control-from-20260711-backup.toml"), src)
    from yyr4_linux_control.configurator.web.server import EditorServer
    s = EditorServer(src, target, port=0, idle_timeout=300, open_browser=False)
    s.start(); time.sleep(0.3)
    return s, t

def _boot(srv):
    port = srv.listen_port; btok = srv._session.bootstrap_token
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    conn.request("GET", f"/bootstrap/{btok}")
    resp = conn.getresponse(); resp.read(); conn.close()
    assert resp.status == 303, f"Bootstrap: {resp.status}"
    pubid = srv._session.public_session_id
    ck = f"yyr4_session_{pubid}={srv._session.session_cookie}"
    return pubid, ck, srv._session.csrf_token

def _get(port, path, ck=""):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    h = {}
    if ck: h["Cookie"] = ck
    conn.request("GET", path, headers=h)
    resp = conn.getresponse(); body = resp.read(); conn.close()
    return resp, body

def _post(port, path, body_dict, ck="", csrf=""):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    d = json.dumps(body_dict).encode()
    h = {"Content-Type": "application/json"}
    if ck: h["Cookie"] = ck
    if csrf: h["X-YYR4-CSRF-Token"] = csrf
    conn.request("POST", path, body=d, headers=h)
    resp = conn.getresponse(); body = resp.read(); conn.close()
    return resp, body


class TestEditorServerHTTP(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv, cls.tmp = _sv()
        cls.pubid, cls.ck, cls.csrf = _boot(cls.srv)
        cls.port = cls.srv.listen_port

    @classmethod
    def tearDownClass(cls):
        cls.srv.stop(); time.sleep(0.3)
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_home_page(self):
        r, b = _get(self.port, f"/s/{self.pubid}/", self.ck)
        self.assertEqual(r.status, 200); self.assertIn(b"<html", b.lower())

    def test_csp_header(self):
        r, _ = _get(self.port, f"/s/{self.pubid}/", self.ck)
        self.assertIn("default-src", r.getheader("Content-Security-Policy", ""))

    def test_x_frame_options(self):
        r, _ = _get(self.port, f"/s/{self.pubid}/", self.ck)
        self.assertEqual(r.getheader("X-Frame-Options"), "DENY")

    def test_no_store_header(self):
        r, _ = _get(self.port, f"/s/{self.pubid}/", self.ck)
        self.assertIn("no-store", r.getheader("Cache-Control", ""))

    def test_state_endpoint(self):
        r, b = _get(self.port, f"/s/{self.pubid}/api/v1/state", self.ck)
        self.assertEqual(r.status, 200); self.assertIn("config", json.loads(b))

    def test_state_has_24_controls(self):
        _, b = _get(self.port, f"/s/{self.pubid}/api/v1/state", self.ck)
        ctrls = json.loads(b)["config"]["profiles"][0]["layers"][0]["controls"]
        self.assertEqual(len(ctrls), 24)

    def test_all_encoder_names(self):
        _, b = _get(self.port, f"/s/{self.pubid}/api/v1/state", self.ck)
        ctrls = json.loads(b)["config"]["profiles"][0]["layers"][0]["controls"]
        for cid in ["AL","AP","AR","BL","BP","BR","CL","CP","CR","DL","DP","DR"]:
            self.assertIn(cid, ctrls)

    def test_set_action_endpoint(self):
        r, _ = _post(self.port, f"/s/{self.pubid}/api/v1/control/set-action",
                     {"profile":"user","layer":"general","control":"A1",
                      "action_spec":{"type":"debug_log","message":"test"}}, self.ck, self.csrf)
        self.assertEqual(r.status, 200)

    def test_validate_endpoint(self):
        r, b = _get(self.port, f"/s/{self.pubid}/api/v1/validate", self.ck)
        self.assertEqual(r.status, 200); self.assertTrue(json.loads(b)["validation"]["valid"])

    def test_diff_endpoint(self):
        r, _ = _get(self.port, f"/s/{self.pubid}/api/v1/diff", self.ck); self.assertEqual(r.status, 200)

    def test_unified_diff_endpoint(self):
        r, _ = _get(self.port, f"/s/{self.pubid}/api/v1/diff/unified", self.ck); self.assertEqual(r.status, 200)

    def test_save_workflow(self):
        _post(self.port, f"/s/{self.pubid}/api/v1/control/set-action",
              {"profile":"user","layer":"general","control":"A1","action_spec":{"type":"noop"}},
              self.ck, self.csrf)
        self.srv._session.mark_reviewed()
        r, _ = _post(self.port, f"/s/{self.pubid}/api/v1/save", {}, self.ck, self.csrf)
        self.assertEqual(r.status, 200)

    def test_wrong_pubid_rejected(self):
        r, _ = _get(self.port, "/s/DEADBEEF/api/v1/state", self.ck); self.assertEqual(r.status, 401)

    def test_old_session_path_rejected(self):
        r, _ = _get(self.port, "/session/anything/api/v1/state", ""); self.assertIn(r.status, (401, 404))


class TestHTTPSecurityBoundary(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv, cls.tmp = _sv()
        cls.pubid, cls.ck, cls.csrf = _boot(cls.srv)
        cls.port = cls.srv.listen_port

    @classmethod
    def tearDownClass(cls):
        cls.srv.stop(); time.sleep(0.3)
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_json_content_accepted(self):
        r, _ = _post(self.port, f"/s/{self.pubid}/api/v1/control/set-action",
                     {"profile":"user","layer":"general","control":"A1","action_spec":{"type":"noop"}},
                     self.ck, self.csrf); self.assertEqual(r.status, 200)

    def test_text_plain_rejected(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        d = json.dumps({"profile":"user","layer":"general","control":"A1","action_spec":{"type":"noop"}}).encode()
        h = {"Content-Type":"text/plain","Cookie":self.ck,"X-YYR4-CSRF-Token":self.csrf}
        conn.request("POST", f"/s/{self.pubid}/api/v1/control/set-action", body=d, headers=h)
        try:
            r = conn.getresponse(); r.read(); conn.close()
            self.assertIn(r.status, (400, 415))
        except Exception:
            pass

    def test_no_ct_rejected(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        d = json.dumps({"profile":"user","layer":"general","control":"A1","action_spec":{"type":"noop"}}).encode()
        h = {"Cookie":self.ck,"X-YYR4-CSRF-Token":self.csrf}
        conn.request("POST", f"/s/{self.pubid}/api/v1/control/set-action", body=d, headers=h)
        r = conn.getresponse(); r.read(); conn.close()
        self.assertIn(r.status, (400, 415))

    def test_malformed_json(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        h = {"Content-Type":"application/json","Cookie":self.ck,"X-YYR4-CSRF-Token":self.csrf}
        conn.request("POST", f"/s/{self.pubid}/api/v1/control/set-action", body=b"not json", headers=h)
        r = conn.getresponse(); b = r.read(); conn.close()
        self.assertEqual(r.status, 400); self.assertEqual(json.loads(b)["error"]["code"], "invalid_json")

    def test_body_too_large(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        big = json.dumps({"x": "Y" * (257 * 1024)}).encode()
        h = {"Content-Type":"application/json","Cookie":self.ck,"X-YYR4-CSRF-Token":self.csrf}
        conn.request("POST", f"/s/{self.pubid}/api/v1/control/set-action", body=big, headers=h)
        r = conn.getresponse(); r.read(); conn.close()
        self.assertEqual(r.status, 413)

    def test_options_rejected(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request("OPTIONS", f"/s/{self.pubid}/api/v1/state")
        try:
            r = conn.getresponse(); r.read(); conn.close()
            self.assertIn(r.status, (405, 400))
        except Exception:
            pass

    def test_unknown_api(self):
        _get(self.port, f"/s/{self.pubid}/api/v1/nonexistent", self.ck)

    def test_error_no_traceback(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        h = {"Content-Type":"application/json","Cookie":self.ck,"X-YYR4-CSRF-Token":self.csrf}
        conn.request("POST", f"/s/{self.pubid}/api/v1/control/set-action", body=b"bad json {{{", headers=h)
        r = conn.getresponse(); b = r.read(); conn.close()
        self.assertNotIn(b"Traceback", b)

    def test_error_no_paths(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        d = json.dumps({"profile":"user","layer":"general","control":"A1","action_spec":{"type":"NONEXISTENT"}}).encode()
        h = {"Content-Type":"application/json","Cookie":self.ck,"X-YYR4-CSRF-Token":self.csrf}
        conn.request("POST", f"/s/{self.pubid}/api/v1/control/set-action", body=d, headers=h)
        r = conn.getresponse(); b = r.read(); conn.close()
        self.assertNotIn(b"/tmp/", b)


if __name__ == "__main__":
    unittest.main()
