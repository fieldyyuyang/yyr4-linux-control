"""M5.4 Resource limits and session management tests."""

import unittest


class TestResourceLimits(unittest.TestCase):
    def test_max_profiles_defined(self):
        from yyr4_linux_control.configurator.web.session import MAX_PROFILES
        self.assertEqual(MAX_PROFILES, 32)

    def test_max_layers_defined(self):
        from yyr4_linux_control.configurator.web.session import MAX_LAYERS
        self.assertEqual(MAX_LAYERS, 16)

    def test_max_macro_steps_defined(self):
        from yyr4_linux_control.configurator.web.session import MAX_MACRO_STEPS
        self.assertEqual(MAX_MACRO_STEPS, 100)

    def test_max_command_argv_defined(self):
        from yyr4_linux_control.configurator.web.session import MAX_COMMAND_ARGV
        self.assertEqual(MAX_COMMAND_ARGV, 64)

    def test_max_text_length_defined(self):
        from yyr4_linux_control.configurator.web.session import MAX_TEXT_LENGTH
        self.assertEqual(MAX_TEXT_LENGTH, 4096)

    def test_max_json_depth_defined(self):
        from yyr4_linux_control.configurator.web.session import MAX_JSON_DEPTH
        self.assertEqual(MAX_JSON_DEPTH, 12)

    def test_recovery_base_dir_set(self):
        from yyr4_linux_control.configurator.web.session import RECOVERY_BASE_DIR
        self.assertIn("yyr4", RECOVERY_BASE_DIR)
        self.assertIn("editor-recovery", RECOVERY_BASE_DIR)


class TestSessionManagement(unittest.TestCase):
    def test_list_recoveries_importable(self):
        from yyr4_linux_control.configurator.web.session import list_recoveries
        self.assertTrue(callable(list_recoveries))

    def test_get_recovery_importable(self):
        from yyr4_linux_control.configurator.web.session import get_recovery
        self.assertTrue(callable(get_recovery))

    def test_discard_recovery_importable(self):
        from yyr4_linux_control.configurator.web.session import discard_recovery
        self.assertTrue(callable(discard_recovery))

    def test_shutdown_clean_exists(self):
        from yyr4_linux_control.configurator.web.session import EditorSession
        self.assertTrue(hasattr(EditorSession, 'shutdown_clean'))

    def test_write_recovery_exists(self):
        from yyr4_linux_control.configurator.web.session import EditorSession
        self.assertTrue(hasattr(EditorSession, '_write_recovery'))

    def test_discard_recovery_method_exists(self):
        from yyr4_linux_control.configurator.web.session import EditorSession
        self.assertTrue(hasattr(EditorSession, '_discard_recovery'))


class TestAccessibilityUI(unittest.TestCase):
    """Verify accessibility features in HTML templates."""

    @classmethod
    def setUpClass(cls):
        from yyr4_linux_control.configurator.web.templates import render_editor_page
        cls.html = render_editor_page()

    def test_html_lang_attribute(self):
        self.assertIn('lang="en"', self.html)

    def test_viewport_meta(self):
        self.assertIn('viewport', self.html)

    def test_has_nav_structure(self):
        self.assertIn('id="nav-panel"', self.html)
        self.assertIn('id="nav-content"', self.html)

    def test_has_main_content(self):
        self.assertIn('id="main"', self.html)
        self.assertIn('id="controls-grid"', self.html)
        self.assertIn('id="editor-panel"', self.html)

    def test_buttons_have_text(self):
        self.assertIn('Validate', self.html)
        self.assertIn('Review', self.html)
        self.assertIn('Save', self.html)
        self.assertIn('Shutdown', self.html)

    def test_encoder_labels_in_js(self):
        from yyr4_linux_control.configurator.web.templates import EDITOR_JS
        self.assertIn('Left', EDITOR_JS)
        self.assertIn('Press', EDITOR_JS)
        self.assertIn('Right', EDITOR_JS)

    def test_focus_css_present(self):
        from yyr4_linux_control.configurator.web.templates import EDITOR_CSS
        self.assertIn(':focus', EDITOR_CSS)

    def test_no_fixed_pixel_blocks(self):
        """Content should be responsive."""
        css = self.html; from yyr4_linux_control.configurator.web.templates import EDITOR_CSS; self.assertIn('overflow', EDITOR_CSS)


class TestDistribution(unittest.TestCase):
    """Verify package structure."""

    def test_pyproject_exists(self):
        import os
        self.assertTrue(os.path.isfile('pyproject.toml'))

    def test_readme_exists(self):
        import os
        self.assertTrue(os.path.isfile('README.md'))

    def test_web_module_exists(self):
        import importlib
        try:
            importlib.import_module('yyr4_linux_control.configurator.web')
        except ImportError:
            self.fail("web module not importable")

    def test_cli_module_exists(self):
        import importlib
        try:
            importlib.import_module('yyr4_linux_control.management.cli')
        except ImportError:
            self.fail("CLI module not importable")


if __name__ == "__main__":
    unittest.main()
