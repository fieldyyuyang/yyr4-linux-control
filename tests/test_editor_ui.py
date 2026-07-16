"""UI template tests: CSP-compatible HTML, no inline styles/scripts/handlers."""

import unittest
from yyr4_linux_control.configurator.web.templates import (
    render_editor_page, EDITOR_CSS, EDITOR_JS,
)


class TestEditorUI(unittest.TestCase):
    def setUp(self):
        self.html = render_editor_page()
        self.css = EDITOR_CSS
        self.js = EDITOR_JS

    # ── HTML structure ──
    def test_html_not_empty(self):
        self.assertTrue(len(self.html) > 500)

    def test_doctype_present(self):
        self.assertIn("<!DOCTYPE html>", self.html)

    def test_title_present(self):
        self.assertIn("YYR4 Editor", self.html)

    # ── Zero inline scripts/styles/handlers ──
    def test_no_inline_style_tag(self):
        self.assertNotIn("<style>", self.html)
        self.assertNotIn("<style ", self.html)

    def test_no_inline_script_tag(self):
        # External script with src= is fine; no bare <script> blocks
        import re
        scripts = re.findall(r'<script[^>]*>', self.html)
        for s in scripts:
            if 'src=' not in s:
                self.fail(f"Inline script found: {s}")

    def test_no_inline_event_handlers(self):
        self.assertNotIn("onclick=", self.html)
        self.assertNotIn("onchange=", self.html)
        self.assertNotIn("onsubmit=", self.html)
        self.assertNotIn("onload=", self.html)
        self.assertNotIn("onerror=", self.html)

    # ── External resource references ──
    def test_external_css_link(self):
        self.assertIn('<link rel="stylesheet" href="assets/editor.css">', self.html)

    def test_external_js_script(self):
        self.assertIn('<script defer src="assets/editor.js">', self.html)

    def test_no_external_http_resources(self):
        self.assertNotIn("http://", self.html)
        self.assertNotIn("https://", self.html)

    def test_no_cdn_references(self):
        self.assertNotIn("cdn.", self.html.lower())
        self.assertNotIn("google", self.html.lower())

    # ── CSS is valid ──
    def test_css_not_empty(self):
        self.assertTrue(len(self.css) > 100)

    def test_css_has_styles(self):
        self.assertIn("font-family", self.css)

    def test_css_has_button_grid(self):
        self.assertIn("button-grid", self.css)

    def test_css_has_encoder_row(self):
        self.assertIn("encoder-row", self.css)

    def test_css_has_focus(self):
        self.assertIn(":focus", self.css)

    # ── JS is valid ──
    def test_js_not_empty(self):
        self.assertTrue(len(self.js) > 500)

    def test_js_uses_addeventlistener(self):
        self.assertIn("addEventListener", self.js)

    def test_js_no_eval(self):
        self.assertNotIn("eval(", self.js)
        self.assertNotIn("Function(", self.js)

    def test_js_has_data_action_dispatch(self):
        self.assertIn("data-action", self.js)

    def test_js_has_esc_function(self):
        self.assertIn("function esc(", self.js)

    # ── All 24 controls referenced ──
    def test_all_24_controls_in_js(self):
        for i in range(1, 13):
            self.assertIn(f"A{i}", self.js)
        for name in ("AL", "AP", "AR", "BL", "BP", "BR",
                     "CL", "CP", "CR", "DL", "DP", "DR"):
            self.assertIn(name, self.js)

    # ── Encoder L/P/R labels ──
    def test_encoder_lpr_labels(self):
        self.assertIn("Left", self.js)
        self.assertIn("Press", self.js)
        self.assertIn("Right", self.js)

    # ── All 11 action types ──
    def test_all_action_types_in_js(self):
        for atype in ("noop", "debug_log", "hotkey", "text", "command",
                       "delay", "macro", "set_layer", "next_layer",
                       "previous_layer", "set_profile"):
            self.assertIn(atype, self.js, f"Missing action type: {atype}")

    # ── Profile/Layer sections ──
    def test_profile_section(self):
        self.assertIn("Profiles", self.js)

    def test_layer_section(self):
        self.assertIn("Layers", self.js)

    # ── Save/Review/Shutdown buttons ──
    def test_save_button(self):
        self.assertIn("btn-save", self.html)

    def test_review_referenced(self):
        self.assertIn("show-review", self.html)
        self.assertIn("Review", self.html)

    def test_shutdown_button(self):
        self.assertIn("Shutdown", self.html)

    # ── HTML uses data-action attributes ──
    def test_html_uses_data_actions(self):
        self.assertIn("data-action=", self.html)

    # ── Macro editing ──
    def test_macro_referenced(self):
        self.assertIn("macro", self.js.lower())

    def test_macro_step_move_delete_in_js(self):
        self.assertIn("moveMacroStep", self.js)
        self.assertIn("deleteMacroStep", self.js)

    # ── Validation section ──
    def test_validation_in_js(self):
        self.assertIn("showValidate", self.js)

    # ── Diff functionality ──
    def test_diff_in_js(self):
        self.assertIn("showReview", self.js)
        self.assertIn("unified", self.js.lower())
        self.assertIn("diff", self.js.lower())

    # ── Labels present ──
    def test_labels_present(self):
        # Labels are in JS (rendered as HTML via innerHTML), verify in JS
        self.assertIn("label", self.js.lower())

    # ── Focus CSS ──
    def test_focus_css(self):
        self.assertIn(":focus", self.css)


if __name__ == "__main__":
    unittest.main()
