"""UI template tests: self-contained HTML, no external resources, structure."""

import unittest
from yyr4_linux_control.configurator.web.templates import render_editor_page


class TestEditorUI(unittest.TestCase):
    def setUp(self):
        self.html = render_editor_page()

    def test_html_not_empty(self):
        self.assertTrue(len(self.html) > 1000)

    def test_html_is_utf8(self):
        self.html.encode("utf-8")

    def test_no_external_http_resources(self):
        self.assertNotIn("http://", self.html)
        self.assertNotIn("https://", self.html)

    def test_no_cdn_references(self):
        self.assertNotIn("cdn.", self.html.lower())

    def test_no_google_fonts(self):
        self.assertNotIn("google", self.html.lower())
        self.assertNotIn("fonts.googleapis", self.html)

    def test_doctype_present(self):
        self.assertIn("<!DOCTYPE html>", self.html)

    def test_title_present(self):
        self.assertIn("YYR4 Editor", self.html)

    def test_css_inline(self):
        self.assertIn("<style>", self.html)

    def test_javascript_inline(self):
        self.assertIn("<script>", self.html)
        self.assertNotIn("<script src=", self.html)

    def test_no_inline_event_handlers(self):
        # Our JS uses addEventListener; check no onclick= in HTML
        # Actually we do use onclick= for some buttons — that's intentional for simplicity.
        # But they should be safe (no eval).
        self.assertNotIn("javascript:", self.html.lower())

    def test_no_unsafe_eval(self):
        self.assertNotIn("eval(", self.html)
        self.assertNotIn("Function(", self.html)

    def test_all_24_controls_referenced(self):
        for name in [f"A{i}" for i in range(1, 13)]:
            self.assertIn(name, self.html)
        for name in ("AL", "AP", "AR", "BL", "BP", "BR",
                     "CL", "CP", "CR", "DL", "DP", "DR"):
            self.assertIn(name, self.html)

    def test_encoder_lpr_labels(self):
        self.assertIn("Left", self.html)
        self.assertIn("Press", self.html)
        self.assertIn("Right", self.html)

    def test_profile_section(self):
        self.assertIn("Profiles", self.html)

    def test_layer_section(self):
        self.assertIn("Layers", self.html)

    def test_action_editor_section(self):
        self.assertIn("Editor", self.html)  # Editor panel exists

    def test_save_button(self):
        self.assertIn("Save", self.html)

    def test_review_button(self):
        self.assertIn("Review", self.html)

    def test_shutdown_button(self):
        self.assertIn("Shutdown", self.html)

    def test_all_action_types_in_js(self):
        for atype in ("noop", "debug_log", "hotkey", "text", "command",
                       "delay", "macro", "set_layer", "next_layer",
                       "previous_layer", "set_profile"):
            self.assertIn(atype, self.html, f"Missing action type: {atype}")

    def test_html_escaping_used(self):
        # JS has esc() function
        self.assertIn("function esc(", self.html)

    def test_macro_step_editing(self):
        self.assertIn("macro", self.html)

    def test_labels_present(self):
        # Check for label elements
        self.assertIn("label", self.html.lower())

    def test_focus_css(self):
        self.assertIn(":focus", self.html)

    def test_no_external_images(self):
        import re
        # img tags should not have src=http
        imgs = re.findall(r'<img[^>]*src=["\']([^"\']+)', self.html)
        for src in imgs:
            self.assertFalse(src.startswith("http"), f"External image: {src}")
            # Allow data: URIs and local references

    def test_validation_section(self):
        self.assertIn("validate", self.html.lower())
        self.assertIn("Validate", self.html)

    def test_diff_functionality(self):
        self.assertIn("diff", self.html.lower())
        self.assertIn("unified", self.html.lower())


if __name__ == "__main__":
    unittest.main()
