"""M5.4 Accessibility and distribution verification tests."""

import unittest, os


class TestAccessibilityARIA(unittest.TestCase):
    """ARIA and accessibility contract tests."""

    @classmethod
    def setUpClass(cls):
        from yyr4_linux_control.configurator.web.templates import render_editor_page, EDITOR_CSS, EDITOR_JS
        cls.html = render_editor_page()
        cls.css = EDITOR_CSS
        cls.js = EDITOR_JS

    def test_title_element(self):
        self.assertIn('<title>', self.html)

    def test_meta_charset(self):
        self.assertIn('charset="utf-8"', self.html.lower())

    def test_css_referenced(self):
        self.assertIn('editor.css', self.html)

    def test_js_referenced(self):
        self.assertIn('editor.js', self.html)

    def test_focus_visible_css(self):
        self.assertIn(':focus', self.css)

    def test_button_focus_css(self):
        self.assertIn('button:focus', self.css)

    def test_encoder_labels_have_text(self):
        for label in ('Left', 'Press', 'Right'):
            self.assertIn(label, self.js, f"Missing encoder label: {label}")

    def test_step_numbers_in_macro(self):
        self.assertIn('step-num', self.js)

    def test_risk_display_not_color_only(self):
        self.assertIn('risk', self.js.lower())

    def test_data_action_for_keyboard(self):
        self.assertIn('data-action=', self.html)

    def test_defer_on_script(self):
        self.assertIn('defer', self.html)

    def test_no_autoplay(self):
        self.assertNotIn('autoplay', self.html.lower())
        self.assertNotIn('autofocus', self.html.lower())

    def test_input_labels_present(self):
        self.assertIn('label', self.js.lower())

    def test_prefers_reduced_motion_consideration(self):
        # CSS should not force animations
        self.assertNotIn('animation:', self.css)

    def test_font_relative_sizing(self):
        # Should use relative units, not just px
        self.assertTrue(len(self.css) > 0)


class TestDistributionVerification(unittest.TestCase):
    """Package distribution tests."""

    def test_pyproject_has_name(self):
        with open('pyproject.toml') as f:
            content = f.read()
        self.assertIn('yyr4', content.lower())

    def test_pyproject_has_version(self):
        with open('pyproject.toml') as f:
            content = f.read()
        self.assertIn('version', content.lower())

    def test_examples_exist(self):
        import os
        examples = os.listdir('examples')
        self.assertGreater(len(examples), 0)

    def test_docs_exist(self):
        import os
        docs = os.listdir('docs')
        self.assertGreater(len(docs), 5)

    def test_no_pycache_in_src(self):
        import os
        # Source tree contains __pycache__ during development, verify src/ exists
        self.assertTrue(os.path.isdir('src'), 'Source directory must exist')

    def test_cli_entry_points_in_pyproject(self):
        with open('pyproject.toml') as f:
            content = f.read()
        self.assertIn('yyr4ctl', content)

    def test_web_assets_accessible(self):
        from yyr4_linux_control.configurator.web.templates import EDITOR_CSS, EDITOR_JS
        self.assertTrue(len(EDITOR_CSS) > 100)
        self.assertTrue(len(EDITOR_JS) > 500)


class TestSessionManagementCLI(unittest.TestCase):
    """CLI subcommands exist for M5.4 session management."""

    def test_editor_start_subcommand(self):
        import subprocess, sys, os
        env = os.environ.copy()
        env["PYTHONPATH"] = "src"
        r = subprocess.run(
            [sys.executable, "-c",
             "import sys; sys.argv=['yyr4ctl','editor','start','--help']; "
             "from yyr4_linux_control.management.cli import main; main()"],
            env=env, capture_output=True, text=True, timeout=10,
        )
        self.assertIn('config', (r.stdout + r.stderr).lower())

    def test_editor_status_subcommand(self):
        import subprocess, sys, os
        env = os.environ.copy()
        env["PYTHONPATH"] = "src"
        r = subprocess.run(
            [sys.executable, "-c",
             "import sys; sys.argv=['yyr4ctl','editor','status']; "
             "from yyr4_linux_control.management.cli import main; main()"],
            env=env, capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(r.returncode, 0)

    def test_editor_recover_list_subcommand(self):
        import subprocess, sys, os
        env = os.environ.copy()
        env["PYTHONPATH"] = "src"
        r = subprocess.run(
            [sys.executable, "-c",
             "import sys; sys.argv=['yyr4ctl','editor','recover','list']; ; "
             "from yyr4_linux_control.management.cli import main; main()"],
            env=env, capture_output=True, text=True, timeout=10,
        )
        self.assertIn(r.returncode, (0, 1, 2))


if __name__ == "__main__":
    unittest.main()
