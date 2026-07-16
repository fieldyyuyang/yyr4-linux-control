"""HTTP server integration tests: binding, token auth, security rejection."""

import unittest, os, tempfile, shutil, json, time
import urllib.request
import urllib.error


class TestServerLifecycle(unittest.TestCase):
    """Test server startup/shutdown without HTTP traffic."""

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

    def test_server_binds_loopback(self):
        from yyr4_linux_control.configurator.web.server import EditorServer
        s = EditorServer(
            source_path=self.src,
            target_path=os.path.join(self.tmp, "target.toml"),
            port=0, idle_timeout=60, open_browser=False,
        )
        url = s.start()
        self.assertIn("127.0.0.1", url)
        self.assertGreater(s.listen_port, 0)
        time.sleep(0.2)
        s.stop()

    def test_port_is_ephemeral(self):
        from yyr4_linux_control.configurator.web.server import EditorServer
        s = EditorServer(
            source_path=self.src,
            target_path=os.path.join(self.tmp, "target.toml"),
            port=0, idle_timeout=60, open_browser=False,
        )
        s.start()
        time.sleep(0.2)
        self.assertGreater(s.listen_port, 0)
        self.assertLess(s.listen_port, 65536)
        s.stop()

    def test_session_cleanup_on_stop(self):
        from yyr4_linux_control.configurator.web.server import EditorServer
        s = EditorServer(
            source_path=self.src,
            target_path=os.path.join(self.tmp, "target.toml"),
            port=0, idle_timeout=60, open_browser=False,
        )
        s.start()
        time.sleep(0.2)
        sd = s._session.session_dir if s._session else None
        self.assertIsNotNone(sd)
        s.stop()
        time.sleep(0.5)
        if sd:
            self.assertFalse(os.path.exists(sd))


class TestEditorServerHTTP(unittest.TestCase):
    """Full HTTP integration tests."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.src = os.path.join(cls.tmp, "src.toml")
        shutil.copy(
            os.path.join(os.path.dirname(__file__), "..", "examples",
                         "yyr4-control-from-20260711-backup.toml"),
            cls.src,
        )
        from yyr4_linux_control.configurator.web.server import EditorServer
        cls.server = EditorServer(
            source_path=cls.src,
            target_path=os.path.join(cls.tmp, "target.toml"),
            port=0, idle_timeout=300, open_browser=False,
        )
        cls.url = cls.server.start()
        time.sleep(0.5)

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()
        time.sleep(0.5)
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def _get(self, path):
        url = self.url.rstrip("/") + path
        req = urllib.request.Request(url)
        req.add_header("Host", f"127.0.0.1:{self.server.listen_port}")
        resp = urllib.request.urlopen(req, timeout=10)
        return resp

    def _post(self, path, body=None):
        data = json.dumps(body or {}).encode("utf-8")
        url = self.url.rstrip("/") + path
        req = urllib.request.Request(url, data=data,
                                     headers={"Content-Type": "application/json"})
        req.add_header("Host", f"127.0.0.1:{self.server.listen_port}")
        resp = urllib.request.urlopen(req, timeout=10)
        return resp

    def test_home_page(self):
        resp = self._get("")
        self.assertEqual(resp.status, 200)
        body = resp.read().decode("utf-8")
        self.assertIn("YYR4 Editor", body)

    def test_state_endpoint(self):
        resp = self._get("/api/v1/state")
        data = json.loads(resp.read())
        self.assertIn("status", data)
        self.assertEqual(data["status"], "ok")

    def test_validate_endpoint(self):
        resp = self._get("/api/v1/validate")
        data = json.loads(resp.read())
        self.assertEqual(data["status"], "ok")

    def test_diff_endpoint(self):
        resp = self._get("/api/v1/diff")
        data = json.loads(resp.read())
        self.assertEqual(data["status"], "ok")

    def test_unified_diff_endpoint(self):
        resp = self._get("/api/v1/diff/unified")
        data = json.loads(resp.read())
        self.assertIn("unified_diff", data)

    def test_set_action_endpoint(self):
        body = {
            "profile": "user", "layer": "general", "control": "A1",
            "action_spec": {"type": "debug_log", "message": "test"},
        }
        resp = self._post("/api/v1/control/set-action", body)
        data = json.loads(resp.read())
        self.assertEqual(data["status"], "ok")

    def test_save_workflow(self):
        # Set action
        body = {
            "profile": "user", "layer": "general", "control": "A2",
            "action_spec": {"type": "debug_log", "message": "server-test"},
        }
        self._post("/api/v1/control/set-action", body)
        # Mark reviewed
        self.server._session.mark_reviewed()
        resp = self._post("/api/v1/save", {})
        data = json.loads(resp.read())
        self.assertEqual(data["status"], "ok")
        self.assertTrue(data["verified"])

    def test_csp_header(self):
        resp = self._get("")
        csp = resp.headers.get("Content-Security-Policy", "")
        self.assertIn("default-src 'self'", csp)

    def test_no_store_header(self):
        resp = self._get("/api/v1/state")
        cc = resp.headers.get("Cache-Control", "")
        self.assertIn("no-store", cc)

    def test_x_frame_options(self):
        resp = self._get("")
        self.assertEqual(resp.headers.get("X-Frame-Options"), "DENY")

    def test_state_has_24_controls(self):
        resp = self._get("/api/v1/state")
        data = json.loads(resp.read())
        profiles = data.get("config", {}).get("profiles", [])
        if profiles:
            layers = profiles[0].get("layers", [])
            if layers:
                controls = layers[0].get("controls", {})
                self.assertEqual(len(controls), 24)

    def test_all_encoder_names(self):
        resp = self._get("/api/v1/state")
        data = json.loads(resp.read())
        profiles = data.get("config", {}).get("profiles", [])
        if profiles:
            layers = profiles[0].get("layers", [])
            if layers:
                controls = layers[0].get("controls", {})
                for name in ("AL", "AP", "AR", "BL", "BP", "BR",
                             "CL", "CP", "CR", "DL", "DP", "DR"):
                    self.assertIn(name, controls, f"Missing encoder {name}")

    def test_no_token_rejected(self):
        ts = tempfile.mkdtemp()
        try:
            src2 = os.path.join(ts, "src.toml")
            shutil.copy(self.src, src2)
            from yyr4_linux_control.configurator.web.server import EditorServer
            s2 = EditorServer(
                source_path=src2,
                target_path=os.path.join(ts, "target.toml"),
                port=0, idle_timeout=60, open_browser=False,
            )
            url2 = s2.start()
            time.sleep(0.3)
            try:
                # Try without valid token path
                req = urllib.request.Request(
                    f"http://127.0.0.1:{s2.listen_port}/api/v1/state"
                )
                req.add_header("Host", f"127.0.0.1:{s2.listen_port}")
                try:
                    resp = urllib.request.urlopen(req, timeout=5)
                    self.assertEqual(resp.status, 401)
                except urllib.error.HTTPError as e:
                    self.assertEqual(e.code, 401)  # expected
            finally:
                s2.stop()
                time.sleep(0.3)
        finally:
            shutil.rmtree(ts, ignore_errors=True)

    def test_wrong_token_rejected(self):
        resp = urllib.request.Request(
            f"http://127.0.0.1:{self.server.listen_port}/session/BADTOKEN/api/v1/state"
        )
        resp.add_header("Host", f"127.0.0.1:{self.server.listen_port}")
        try:
            r = urllib.request.urlopen(resp, timeout=5)
            self.assertEqual(r.status, 401)
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 401)


class TestHTTPSecurityBoundary(unittest.TestCase):
    """Real HTTP tests for security boundaries."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.src = os.path.join(cls.tmp, "src.toml")
        shutil.copy(
            os.path.join(os.path.dirname(__file__), "..", "examples",
                         "yyr4-control-from-20260711-backup.toml"),
            cls.src,
        )
        from yyr4_linux_control.configurator.web.server import EditorServer
        cls.server = EditorServer(
            source_path=cls.src,
            target_path=os.path.join(cls.tmp, "target.toml"),
            port=0, idle_timeout=300, open_browser=False,
        )
        cls.url = cls.server.start()
        time.sleep(0.5)
        cls.token = cls.server.session_token
        cls.host = f"127.0.0.1:{cls.server.listen_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()
        time.sleep(0.5)
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def _api_url(self, path):
        return f"http://127.0.0.1:{self.server.listen_port}/s/{self.pubid}/{path}"

    def _get(self, path):
        req = urllib.request.Request(self._api_url(path))
        req.add_header("Host", self.host)
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cj))
        return opener.open(req, timeout=10)

    def _post(self, path, body, ct="application/json"):
        data = json.dumps(body).encode()
        req = urllib.request.Request(self._api_url(path), data=data)
        req.add_header("Host", self.host)
        req.add_header("Content-Type", ct)
        req.add_header("X-YYR4-CSRF-Token", self.server._session.csrf_token if hasattr(self.server, '_session') else "")
        return urllib.request.urlopen(req, timeout=10)

    # ── Content-Type ──
    def test_json_content_type_accepted(self):
        resp = self._post("api/v1/control/set-action", {
            "profile":"user","layer":"general","control":"A1",
            "action_spec":{"type":"noop"},
        })
        self.assertEqual(resp.status, 200)

    def test_json_charset_utf8_accepted(self):
        resp = self._post("api/v1/control/set-action", {
            "profile":"user","layer":"general","control":"A2",
            "action_spec":{"type":"noop"},
        }, ct="application/json; charset=utf-8")
        self.assertEqual(resp.status, 200)

    def test_non_json_content_type_rejected(self):
        try:
            self._post("api/v1/control/set-action", {
                "profile":"user","layer":"general","control":"A3",
                "action_spec":{"type":"noop"},
            }, ct="text/plain")
            self.fail("Should have raised HTTPError")
        except urllib.error.HTTPError as e:
            self.assertIn(e.code, (400, 415))
            body = json.loads(e.read())
            self.assertIn("error", body)

    def test_missing_content_type_rejected(self):
        data = json.dumps({
            "profile":"user","layer":"general","control":"A4",
            "action_spec":{"type":"noop"},
        }).encode()
        req = urllib.request.Request(
            self._api_url("api/v1/control/set-action"), data=data)
        req.add_header("Host", self.host)
        # No Content-Type header
        try:
            urllib.request.urlopen(req, timeout=10)
            self.fail("Should have raised")
        except urllib.error.HTTPError as e:
            self.assertIn(e.code, (400, 415))

    # ── Malformed JSON ──
    def test_malformed_json(self):
        data = b"not json at all"
        req = urllib.request.Request(
            self._api_url("api/v1/control/set-action"), data=data)
        req.add_header("Host", self.host)
        req.add_header("Content-Type", "application/json")
        try:
            urllib.request.urlopen(req, timeout=10)
            self.fail("Should have raised")
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 400)
            body = json.loads(e.read())
            self.assertEqual(body["error"]["code"], "invalid_json")

    # ── Body too large ──
    def test_body_too_large(self):
        big = "x" * (256 * 1024 + 1)
        data = json.dumps({"bad": big}).encode()
        req = urllib.request.Request(
            self._api_url("api/v1/control/set-action"), data=data)
        req.add_header("Host", self.host)
        req.add_header("Content-Type", "application/json")
        try:
            urllib.request.urlopen(req, timeout=10)
            self.fail("Should have raised")
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 413)

    # ── OPTIONS ──
    def test_options_returns_405(self):
        req = urllib.request.Request(
            self._api_url("api/v1/state"), method="OPTIONS")
        req.add_header("Host", self.host)
        try:
            resp = urllib.request.urlopen(req, timeout=10)
            self.assertGreaterEqual(resp.status, 400)
        except urllib.error.HTTPError as e:
            self.assertIn(e.code, (405, 400))

    # ── Unknown API ──
    def test_unknown_api(self):
        try:
            resp = self._get("api/v1/nonexistent")
            self.assertEqual(resp.status, 404)
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 404)

    # ── Unknown asset ──
    def test_unknown_asset_rejected(self):
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.server.listen_port}/session/{self.token}/assets/evil.js")
        req.add_header("Host", self.host)
        try:
            urllib.request.urlopen(req, timeout=10)
            self.fail("Should have raised")
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 404)

    # ── Path traversal ──
    def _check_traversal_rejected(self, path_segment):
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.server.listen_port}/session/{self.token}/assets/{path_segment}")
        req.add_header("Host", self.host)
        try:
            resp = urllib.request.urlopen(req, timeout=10)
            self.assertIn(resp.status, (400, 403, 404))
        except urllib.error.HTTPError as e:
            self.assertIn(e.code, (400, 403, 404))

    def test_dot_dot_slash_rejected(self):
        self._check_traversal_rejected("../etc/passwd")

    def test_encoded_dot_dot_rejected(self):
        self._check_traversal_rejected("..%2fetc%2fpasswd")

    def test_double_encoded_rejected(self):
        self._check_traversal_rejected("%252e%252e%252f")

    def test_backslash_rejected(self):
        self._check_traversal_rejected("..\\etc")

    # ── Error response does not leak secrets ──
    def test_error_no_traceback(self):
        data = b"bad json {{{"
        req = urllib.request.Request(
            self._api_url("api/v1/control/set-action"), data=data)
        req.add_header("Host", self.host)
        req.add_header("Content-Type", "application/json")
        try:
            urllib.request.urlopen(req, timeout=10)
        except urllib.error.HTTPError as e:
            body = e.read().decode()
            self.assertNotIn("Traceback", body)
            self.assertNotIn("File \"", body)
            self.assertNotIn(self.token, body)

    def test_error_no_session_dir(self):
        data = json.dumps({
            "profile":"user","layer":"general","control":"A1",
            "action_spec":{"type":"NONEXISTENT"},
        }).encode()
        req = urllib.request.Request(
            self._api_url("api/v1/control/set-action"), data=data)
        req.add_header("Host", self.host)
        req.add_header("Content-Type", "application/json")
        try:
            urllib.request.urlopen(req, timeout=10)
        except urllib.error.HTTPError as e:
            body = e.read().decode()
            self.assertNotIn("/tmp/", body)
            self.assertNotIn(str(self.server._session.session_dir)[:20], body)


if __name__ == "__main__":
    unittest.main()
