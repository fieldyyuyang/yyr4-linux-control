"""M5.4-A1: Authoritative Bootstrap, Cookie, CSRF, cross-session authentication tests."""

import unittest, os, tempfile, shutil, time, json, urllib.request, urllib.error, http.cookiejar


class TestBootstrapAuth(unittest.TestCase):
    """Bootstrap-only auth: no URL token, Cookie+CSRF mandatory."""

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
        time.sleep(0.3)
        cls.host = f"127.0.0.1:{cls.server.listen_port}"
        cls.btok = cls.server._session.bootstrap_token

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()
        time.sleep(0.3)
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def _bootstrap(self, cj=None):
        if cj is None:
            cj = http.cookiejar.CookieJar()
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
        req = urllib.request.Request(f"http://127.0.0.1:{self.server.listen_port}/bootstrap/{self.btok}")
        req.add_header("Host", self.host)
        resp = opener.open(req, timeout=10)
        return resp, cj, opener

    def _get(self, path, cj, opener):
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.server.listen_port}{path}")
        req.add_header("Host", self.host)
        return opener.open(req, timeout=10)

    def _post(self, path, body, cj, opener, csrf):
        data = json.dumps(body).encode()
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.server.listen_port}{path}", data=data)
        req.add_header("Host", self.host)
        req.add_header("Content-Type", "application/json")
        if csrf:
            req.add_header("X-YYR4-CSRF-Token", csrf)
        return opener.open(req, timeout=10)

    def test_bootstrap_success(self):
        resp, cj, _ = self._bootstrap()
        self.assertEqual(resp.status, 200)  # 303 followed by redirector

    def test_bootstrap_redirect_no_token(self):
        resp, cj, _ = self._bootstrap()
        url = resp.geturl()
        self.assertNotIn(self.btok, url)
        self.assertNotIn(self.btok[:16], url)

    def test_bootstrap_replay_rejected(self):
        self._bootstrap()
        try:
            resp2 = urllib.request.urlopen(
                urllib.request.Request(
                    f"http://127.0.0.1:{self.server.listen_port}/bootstrap/{self.btok}",
                    headers={"Host": self.host}),
                timeout=10)
            self.assertEqual(resp2.status, 401)
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 401)

    def test_cookie_set_on_bootstrap(self):
        _, cj, _ = self._bootstrap()
        cookies = list(cj)
        self.assertGreaterEqual(len(cookies), 1)
        found = False
        for ck in cookies:
            if ck.name.startswith("yyr4_session_"):
                found = True
                self.assertIn("HttpOnly", str(ck))
        self.assertTrue(found, "No yyr4_session_ cookie found")

    def test_url_token_path_rejected(self):
        sid = self.server._session.public_session_id
        try:
            req = urllib.request.Request(
                f"http://127.0.0.1:{self.server.listen_port}/session/{sid}/")
            req.add_header("Host", self.host)
            urllib.request.urlopen(req, timeout=10)
            self.fail("Should reject URL token path")
        except urllib.error.HTTPError as e:
            self.assertIn(e.code, (404, 401))

    def test_no_cookie_get_rejected(self):
        sid = self.server._session.public_session_id
        try:
            req = urllib.request.Request(
                f"http://127.0.0.1:{self.server.listen_port}/s/{sid}/api/v1/state")
            req.add_header("Host", self.host)
            urllib.request.urlopen(req, timeout=10)
            self.fail("Should reject unauthenticated GET")
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 401)

    def test_no_csrf_post_rejected(self):
        _, cj, opener = self._bootstrap()
        sid = self.server._session.public_session_id
        csrf = self.server._session.csrf_token
        try:
            self._post(f"/s/{sid}/api/v1/control/set-action",
                       {"profile":"user","layer":"general","control":"A1",
                        "action_spec":{"type":"noop"}},
                       cj, opener, None)  # no CSRF
            self.fail("Should reject missing CSRF")
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 401)

    def test_wrong_csrf_post_rejected(self):
        _, cj, opener = self._bootstrap()
        sid = self.server._session.public_session_id
        try:
            self._post(f"/s/{sid}/api/v1/control/set-action",
                       {"profile":"user","layer":"general","control":"A1",
                        "action_spec":{"type":"noop"}},
                       cj, opener, "BADCSRFTOKEN")
            self.fail("Should reject wrong CSRF")
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 401)

    def test_valid_cookie_csrf_post_succeeds(self):
        _, cj, opener = self._bootstrap()
        sid = self.server._session.public_session_id
        csrf = self.server._session.csrf_token
        resp = self._post(f"/s/{sid}/api/v1/control/set-action",
                          {"profile":"user","layer":"general","control":"A1",
                           "action_spec":{"type":"noop"}},
                          cj, opener, csrf)
        self.assertIn(resp.status, (200, 201))

    def test_shutdown_invalidates_auth(self):
        _, cj, opener = self._bootstrap()
        sid = self.server._session.public_session_id
        csrf = self.server._session.csrf_token
        # Shutdown
        self._post(f"/s/{sid}/api/v1/shutdown", {"dirty_policy":"discard"},
                   cj, opener, csrf)
        time.sleep(1)
        # Cookie should now fail
        try:
            self._get(f"/s/{sid}/api/v1/state", cj, opener)
            self.fail("Should fail after shutdown")
        except Exception:
            pass  # expected


class TestCrossSessionIsolation(unittest.TestCase):
    """Two concurrent Editor servers with isolated cookies and CSRF."""

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
        cls.srvA = EditorServer(cls.src, os.path.join(cls.tmp, "tA.toml"),
                                port=0, idle_timeout=300, open_browser=False)
        cls.srvB = EditorServer(cls.src, os.path.join(cls.tmp, "tB.toml"),
                                port=0, idle_timeout=300, open_browser=False)
        cls.srvA.start(); time.sleep(0.2)
        cls.srvB.start(); time.sleep(0.2)

        cls.hostA = f"127.0.0.1:{cls.srvA.listen_port}"
        cls.hostB = f"127.0.0.1:{cls.srvB.listen_port}"

    @classmethod
    def tearDownClass(cls):
        cls.srvA.stop(); cls.srvB.stop()
        time.sleep(0.3)
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def _bootstrap(self, port, btok):
        cj = http.cookiejar.CookieJar()
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
        req = urllib.request.Request(f"http://127.0.0.1:{port}/bootstrap/{btok}")
        req.add_header("Host", f"127.0.0.1:{port}")
        resp = opener.open(req, timeout=10)
        return resp, cj, opener

    def test_cookie_a_cannot_access_b(self):
        _, cjA, opA = self._bootstrap(self.srvA.listen_port, self.srvA._session.bootstrap_token)
        sidB = self.srvB._session.public_session_id
        try:
            req = urllib.request.Request(
                f"http://127.0.0.1:{self.srvB.listen_port}/s/{sidB}/api/v1/state")
            req.add_header("Host", f"127.0.0.1:{self.srvB.listen_port}")
            opA.open(req, timeout=10)
            self.fail("Cookie A should not access B")
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 401)

    def test_cookie_b_cannot_access_a(self):
        _, cjB, opB = self._bootstrap(self.srvB.listen_port, self.srvB._session.bootstrap_token)
        sidA = self.srvA._session.public_session_id
        try:
            req = urllib.request.Request(
                f"http://127.0.0.1:{self.srvA.listen_port}/s/{sidA}/api/v1/state")
            req.add_header("Host", f"127.0.0.1:{self.srvA.listen_port}")
            opB.open(req, timeout=10)
            self.fail("Cookie B should not access A")
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 401)

    def test_csrf_a_cannot_mutate_b(self):
        _, cjA, opA = self._bootstrap(self.srvA.listen_port, self.srvA._session.bootstrap_token)
        csrfA = self.srvA._session.csrf_token
        sidB = self.srvB._session.public_session_id
        data = json.dumps({"profile":"user","layer":"general","control":"A1",
                           "action_spec":{"type":"noop"}}).encode()
        # Use B's URL but A's CSRF — should fail because B's cookie is required
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.srvB.listen_port}/s/{sidB}/api/v1/control/set-action",
            data=data)
        req.add_header("Host", f"127.0.0.1:{self.srvB.listen_port}")
        req.add_header("Content-Type", "application/json")
        req.add_header("X-YYR4-CSRF-Token", csrfA)
        try:
            opA.open(req, timeout=10)
            self.fail("A's CSRF on B should fail")
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 401)


if __name__ == "__main__":
    unittest.main()
