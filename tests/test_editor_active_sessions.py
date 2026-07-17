"""M5.4-A2: Active session registry — registry, stale detection, permissions."""
import unittest, os, tempfile, shutil, time, json


class TestActiveSessions(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.sessions_dir = os.path.join(self.tmp, "sessions")
        import yyr4_linux_control.configurator.web.session as smod
        self._old = smod._SESSIONS_DIR
        smod._SESSIONS_DIR = self.sessions_dir

    def tearDown(self):
        import yyr4_linux_control.configurator.web.session as smod
        smod._SESSIONS_DIR = self._old
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _start(self):
        from yyr4_linux_control.configurator.web.server import EditorServer
        src = os.path.join(self.tmp, "src.toml")
        target = os.path.join(self.tmp, "target.toml")
        shutil.copy(os.path.join(os.path.dirname(__file__), "..", "examples",
            "yyr4-control-from-20260711-backup.toml"), src)
        s = EditorServer(src, target, port=0, idle_timeout=300, open_browser=False)
        s.start(); time.sleep(0.2)
        return s

    def test_registry_created_on_start(self):
        s = self._start()
        from yyr4_linux_control.configurator.web.session import list_sessions
        ses = list_sessions()
        # Registry should contain at least this session
        self.assertGreaterEqual(len(ses), 1, 'Registry should contain at least 1 session')
        s.stop()

    def test_registry_shows_running(self):
        s = self._start()
        from yyr4_linux_control.configurator.web.session import list_sessions
        ses = list_sessions()
        self.assertGreaterEqual(len(ses), 1)
        self.assertFalse(ses[0].get("stale", True))
        s.stop()

    def test_registry_shows_stale_after_stop(self):
        s = self._start()
        pid = s._session.pid
        s.stop(); time.sleep(0.3)
        from yyr4_linux_control.configurator.web.session import list_sessions, _is_stale
        for ses in list_sessions():
            if ses.get("pid") == pid:
                self.assertTrue(_is_stale(ses))

    def test_pid_stale_detection(self):
        from yyr4_linux_control.configurator.web.session import _is_stale
        self.assertTrue(_is_stale({"pid": 999999, "uid": os.getuid(), "process_start_time": "0"}))

    def test_registry_no_secrets(self):
        s = self._start()
        from yyr4_linux_control.configurator.web.session import list_sessions
        for ses in list_sessions():
            txt = json.dumps(ses)
            for w in ("bootstrap", "cookie", "csrf", "token"):
                self.assertNotIn(w, txt.lower())
        s.stop()

    def test_list_sessions_empty(self):
        from yyr4_linux_control.configurator.web.session import list_sessions
        self.assertEqual(len(list_sessions()), 0)

    def test_registry_has_proper_fields(self):
        s = self._start()
        from yyr4_linux_control.configurator.web.session import list_sessions
        ses = list_sessions()
        self.assertGreaterEqual(len(ses), 1)
        for f in ("registry_version","session_id","public_session_id","pid","uid","port",
                  "created_at","dirty","mutation_count"):
            self.assertIn(f, ses[0])
        s.stop()


if __name__ == "__main__":
    unittest.main()
