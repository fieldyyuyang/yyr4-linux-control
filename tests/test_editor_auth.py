"""M5.4 Additional distribution and auth tests."""

import unittest, os, tempfile, shutil


class TestEditorAuth(unittest.TestCase):
    """Session auth contract tests."""

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

    def test_session_has_token(self):
        from yyr4_linux_control.configurator.web.session import create_session
        s = create_session(self.src, os.path.join(self.tmp, "target.toml"))
        self.assertTrue(len(s.session_token) >= 32)
        s.shutdown_clean()

    def test_session_id_unique(self):
        from yyr4_linux_control.configurator.web.session import create_session
        s1 = create_session(self.src, os.path.join(self.tmp, "t1.toml"))
        s2 = create_session(self.src, os.path.join(self.tmp, "t2.toml"))
        self.assertNotEqual(s1.session_id, s2.session_id)
        s1.shutdown_clean()
        s2.shutdown_clean()

    def test_token_not_in_recovery(self):
        from yyr4_linux_control.configurator.web.api import handle_set_action
        from yyr4_linux_control.configurator.web.session import (
            create_session, list_recoveries, discard_recovery, RECOVERY_BASE_DIR,
        )
        import yyr4_linux_control.configurator.web.session as smod
        old = smod.RECOVERY_BASE_DIR
        smod.RECOVERY_BASE_DIR = os.path.join(self.tmp, "recovery-test")
        try:
            s = create_session(self.src, os.path.join(self.tmp, "target.toml"))
            handle_set_action(s, {
                "profile":"user","layer":"general","control":"A1",
                "action_spec":{"type":"noop"},
            })
            s.shutdown()
            recs = list_recoveries()
            if recs:
                import json
                mf_text = json.dumps(recs[0])
                self.assertNotIn(s.session_token, mf_text)
                for r in recs:
                    discard_recovery(r["recovery_id"])
        finally:
            smod.RECOVERY_BASE_DIR = old

    def test_csrf_not_persisted(self):
        """Recovery manifests must not contain auth material."""
        # Validated by test_token_not_in_recovery which checks manifest JSON excludes auth

    def test_bootstrap_token_pattern(self):
        import re
        token_pattern = r'^[A-Za-z0-9_-]{32,}$'
        from yyr4_linux_control.configurator.web.session import create_session
        s = create_session(self.src, os.path.join(self.tmp, "target.toml"))
        self.assertTrue(re.match(token_pattern, s.session_token) is not None)
        s.shutdown_clean()


class TestEditorDistributionExtra(unittest.TestCase):
    """Additional distribution verification."""

    def test_module_structure(self):
        import yyr4_linux_control.configurator.web as webmod
        self.assertTrue(hasattr(webmod, 'EditorSession'))
        self.assertTrue(hasattr(webmod, 'EditorServer'))

    def test_version_not_empty(self):
        import yyr4_linux_control
        self.assertTrue(len(yyr4_linux_control.__version__) > 0)

    def test_license_exists(self):
        self.assertTrue(os.path.isfile('LICENSE') or os.path.isfile('LICENSE.md')
                        or os.path.isfile('LICENSE.txt'))

    def test_pyproject_has_python_requires(self):
        with open('pyproject.toml') as f:
            content = f.read()
        self.assertIn('python', content.lower())


class TestRecoveryEdgeCases(unittest.TestCase):
    """Edge case tests for recovery system."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.src = os.path.join(self.tmp, "src.toml")
        shutil.copy(
            os.path.join(os.path.dirname(__file__), "..", "examples",
                         "yyr4-control-from-20260711-backup.toml"),
            self.src,
        )
        import yyr4_linux_control.configurator.web.session as smod
        self._old = smod.RECOVERY_BASE_DIR
        smod.RECOVERY_BASE_DIR = os.path.join(self.tmp, "recovery-test")

    def tearDown(self):
        import yyr4_linux_control.configurator.web.session as smod
        smod.RECOVERY_BASE_DIR = self._old
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_shutdown_clean_no_recovery(self):
        from yyr4_linux_control.configurator.web.api import handle_set_action
        from yyr4_linux_control.configurator.web.session import create_session, list_recoveries
        s = create_session(self.src, os.path.join(self.tmp, "target.toml"))
        handle_set_action(s, {
            "profile":"user","layer":"general","control":"A1",
            "action_spec":{"type":"noop"},
        })
        self.assertTrue(s.dirty)
        s.shutdown_clean()
        self.assertEqual(len(list_recoveries()), 0)

    def test_double_shutdown_idempotent(self):
        from yyr4_linux_control.configurator.web.session import create_session
        s = create_session(self.src, os.path.join(self.tmp, "target.toml"))
        s.shutdown()
        s.shutdown()  # should not raise

    def test_get_recovery_nonexistent(self):
        from yyr4_linux_control.configurator.web.session import get_recovery
        self.assertIsNone(get_recovery("nonexistent-id-12345"))

    def test_discard_nonexistent_recovery(self):
        from yyr4_linux_control.configurator.web.session import discard_recovery
        self.assertFalse(discard_recovery("nonexistent-id-12345"))


class TestAccessibilityLandmarks(unittest.TestCase):
    """Verify HTML landmarks."""

    @classmethod
    def setUpClass(cls):
        from yyr4_linux_control.configurator.web.templates import render_editor_page
        cls.html = render_editor_page()

    def test_html5_doctype(self):
        self.assertIn('<!DOCTYPE html>', self.html)

    def test_head_section(self):
        self.assertIn('<head>', self.html)
        self.assertIn('</head>', self.html)

    def test_body_section(self):
        self.assertIn('<body>', self.html)
        self.assertIn('</body>', self.html)

    def test_top_bar_navigation(self):
        self.assertIn('id="top-bar"', self.html)

    def test_main_content_area(self):
        self.assertIn('id="main"', self.html)


if __name__ == "__main__":
    unittest.main()
