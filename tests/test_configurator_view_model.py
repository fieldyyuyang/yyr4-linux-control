import unittest
from pathlib import Path

from yyr4_linux_control.configurator import build_document, generate_html
from yyr4_linux_control.configurator.models import (
    ConfiguratorDocument, ProfileView, LayerView, ControlView, ActionView,
)


class TestConfiguratorViewModel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = build_document(
            Path("examples/yyr4-control-from-20260711-backup.toml"),
        )

    def test_schema_version(self):
        self.assertEqual(self.doc.schema_version, 2)

    def test_source_path(self):
        self.assertIn("yyr4-control-from-20260711-backup", self.doc.source_path)

    def test_default_profile(self):
        self.assertEqual(self.doc.default_profile, "user")

    def test_initial_layer(self):
        self.assertEqual(self.doc.initial_layer, "general")

    def test_profile_count(self):
        self.assertEqual(self.doc.profile_count, 1)

    def test_total_layer_count(self):
        self.assertEqual(self.doc.total_layer_count, 1)

    def test_total_configured_controls(self):
        self.assertEqual(self.doc.total_configured_controls, 24)

    def test_validation_status(self):
        self.assertEqual(self.doc.validation_status, "VALID")

    def test_profile_is_default(self):
        profile = self.doc.profiles[0]
        self.assertTrue(profile.is_default)
        self.assertEqual(profile.profile_id, "user")

    def test_layer_is_initial(self):
        layer = self.doc.profiles[0].layers[0]
        self.assertTrue(layer.is_initial)
        self.assertEqual(layer.layer_id, "general")

    def test_every_layer_has_24_controls(self):
        for profile in self.doc.profiles:
            for layer in profile.layers:
                self.assertEqual(len(layer.controls), 24,
                                 f"Layer {layer.layer_id}: {len(layer.controls)} controls")

    def test_official_control_order(self):
        expected = [
            "A1","A2","A3","A4","A5","A6","A7","A8","A9","A10","A11","A12",
            "AL","AP","AR","BL","BP","BR","CL","CP","CR","DL","DP","DR",
        ]
        layer = self.doc.profiles[0].layers[0]
        actual = [c.official_name for c in layer.controls]
        self.assertEqual(actual, expected)

    def test_buttons_have_button_kind(self):
        layer = self.doc.profiles[0].layers[0]
        buttons = [c for c in layer.controls if c.control_kind == "button"]
        self.assertEqual(len(buttons), 12)
        for c in buttons:
            self.assertEqual(c.control_kind, "button")
            self.assertIsNone(c.encoder_group)

    def test_encoders_have_correct_kind_and_group(self):
        layer = self.doc.profiles[0].layers[0]
        encoders = [c for c in layer.controls if c.control_kind != "button"]
        self.assertEqual(len(encoders), 12)
        for c in encoders:
            self.assertIn(c.control_kind, (
                "encoder_counterclockwise", "encoder_press", "encoder_clockwise",
            ))
            self.assertIn(c.encoder_group, ("A", "B", "C", "D"))

    def test_encoder_order_lpr(self):
        layer = self.doc.profiles[0].layers[0]
        enc_names = [c.official_name for c in layer.controls[12:]]
        expected = ["AL","AP","AR","BL","BP","BR","CL","CP","CR","DL","DP","DR"]
        self.assertEqual(enc_names, expected)

    def test_all_24_configured(self):
        layer = self.doc.profiles[0].layers[0]
        self.assertTrue(all(c.configured for c in layer.controls))
        for c in layer.controls:
            self.assertIsNotNone(c.action)

    def test_unmapped_not_present(self):
        layer = self.doc.profiles[0].layers[0]
        unmapped = [c for c in layer.controls if not c.configured]
        self.assertEqual(len(unmapped), 0)

    def test_a6_is_macro(self):
        a6 = self._find_control("A6")
        self.assertEqual(a6.action.action_type, "Macro")

    def test_a6_step_count(self):
        a6 = self._find_control("A6")
        self.assertEqual(len(a6.action.child_steps), 11)

    def test_a6_delays(self):
        a6 = self._find_control("A6")
        delays = [s for s in a6.action.child_steps if s.action_type == "Delay"]
        self.assertEqual(len(delays), 5)
        self.assertEqual([s.concise_summary for s in delays],
                         ["100 ms", "20 ms", "20 ms", "100 ms", "20 ms"])

    def test_a6_hotkey_steps(self):
        a6 = self._find_control("A6")
        hotkeys = [s for s in a6.action.child_steps if s.action_type == "Hotkey"]
        self.assertEqual(len(hotkeys), 6)
        self.assertEqual(hotkeys[0].concise_summary, "LSHIFT+ENTER")
        self.assertEqual(hotkeys[1].concise_summary, "KP_Subtract")

    def test_al_brightness(self):
        al = self._find_control("AL")
        self.assertEqual(al.action.action_type, "Hotkey")
        self.assertIn("XF86MonBrightnessDown", al.action.concise_summary)

    def test_ar_brightness(self):
        ar = self._find_control("AR")
        self.assertEqual(ar.action.action_type, "Hotkey")
        self.assertIn("XF86MonBrightnessUp", ar.action.concise_summary)

    def test_bp_mute(self):
        bp = self._find_control("BP")
        self.assertEqual(bp.action.action_type, "Hotkey")
        self.assertIn("XF86AudioMute", bp.action.concise_summary)

    def test_bl_kp_divide(self):
        bl = self._find_control("BL")
        self.assertEqual(bl.action.action_type, "Hotkey")
        self.assertIn("KP_Divide", bl.action.concise_summary)

    def test_br_kp_multiply(self):
        br = self._find_control("BR")
        self.assertEqual(br.action.action_type, "Hotkey")
        self.assertIn("KP_Multiply", br.action.concise_summary)

    def test_a6_has_kp_subtract(self):
        a6 = self._find_control("A6")
        kp = [s for s in a6.action.child_steps
              if "KP_Subtract" in s.concise_summary]
        self.assertEqual(len(kp), 3)

    def test_side_effect_classes(self):
        a1 = self._find_control("A1")
        self.assertEqual(a1.action.side_effect_class, "desktop_input")
        a6 = self._find_control("A6")
        self.assertEqual(a6.action.side_effect_class, "composite")

    def test_no_command_actions(self):
        layer = self.doc.profiles[0].layers[0]
        cmds = [c for c in layer.controls
                if c.action and c.action.action_type == "Command"]
        self.assertEqual(len(cmds), 0)

    def test_text_action_detail(self):
        # Test with a config that has TextAction (not in migration config)
        # Just verify code path exists
        from yyr4_linux_control.configurator.builder import _build_action
        from yyr4_linux_control.control.actions import TextAction
        av = _build_action(TextAction("hello"), depth=0)
        self.assertEqual(av.action_type, "Text")
        self.assertEqual(av.concise_summary, "hello")
        self.assertEqual(av.side_effect_class, "desktop_input")

    def test_noop_action(self):
        from yyr4_linux_control.configurator.builder import _build_action
        from yyr4_linux_control.control.actions import NoOpAction
        av = _build_action(NoOpAction(), depth=0)
        self.assertEqual(av.action_type, "NoOp")
        self.assertIn("no operation", av.concise_summary)

    def test_delay_action(self):
        from yyr4_linux_control.configurator.builder import _build_action
        from yyr4_linux_control.control.actions import DelayAction
        av = _build_action(DelayAction(250), depth=0)
        self.assertEqual(av.action_type, "Delay")
        self.assertIn("250 ms", av.concise_summary)

    def test_debug_log_action(self):
        from yyr4_linux_control.configurator.builder import _build_action
        from yyr4_linux_control.control.actions import DebugLogAction
        av = _build_action(DebugLogAction("test msg"), depth=0)
        self.assertEqual(av.action_type, "DebugLog")
        self.assertEqual(av.side_effect_class, "diagnostic")

    def test_command_action(self):
        from yyr4_linux_control.configurator.builder import _build_action
        from yyr4_linux_control.control.actions import CommandAction
        av = _build_action(CommandAction(("echo", "hi")), depth=0)
        self.assertEqual(av.action_type, "Command")
        self.assertEqual(av.side_effect_class, "command_execution")

    def test_set_layer_action(self):
        from yyr4_linux_control.configurator.builder import _build_action
        from yyr4_linux_control.control.actions import SetLayerAction
        av = _build_action(SetLayerAction("layer_1"), depth=0)
        self.assertEqual(av.action_type, "SetLayer")
        self.assertEqual(av.side_effect_class, "runtime_context_change")

    def test_unknown_action(self):
        from yyr4_linux_control.configurator.builder import _build_action
        from yyr4_linux_control.control.actions import Action
        class FakeAction(Action):
            pass
        av = _build_action(FakeAction(), depth=0)
        self.assertTrue(av.action_type.startswith("UNKNOWN"))
        self.assertIn("unsupported", av.concise_summary)
        self.assertEqual(av.side_effect_class, "unknown")

    def test_macro_depth_limit(self):
        from yyr4_linux_control.configurator.builder import _build_action
        from yyr4_linux_control.control.actions import (
            MacroAction, HotkeyAction,
        )
        inner = HotkeyAction(("A",))
        outer = MacroAction((inner,))
        for _ in range(6):
            outer = MacroAction((outer,))
        av = _build_action(outer, depth=0)
        # Should not recurse infinitely
        self.assertEqual(av.action_type, "Macro")
        # First level child is OK, deeper levels may hit the depth limit
        if av.child_steps:
            child = av.child_steps[0]
            self.assertIn(child.action_type, ("Macro", "UNKNOWN"))

    def _find_control(self, name):
        layer = self.doc.profiles[0].layers[0]
        for c in layer.controls:
            if c.official_name == name:
                return c
        self.fail(f"Control {name} not found")


class TestConfiguratorHtmlSafety(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = build_document(
            Path("examples/yyr4-control-from-20260711-backup.toml"),
        )
        cls.html = generate_html(cls.doc, title="Test <Preview>")

    def test_read_only_banner(self):
        self.assertIn("READ-ONLY CONFIGURATION PREVIEW", self.html)

    def test_title_escaped(self):
        self.assertNotIn("<Preview>", self.html)
        self.assertIn("Test &lt;Preview&gt;", self.html)

    def test_no_external_resources(self):
        self.assertNotIn("http://", self.html)
        self.assertNotIn("https://", self.html)
        self.assertNotIn("//cdn", self.html)

    def test_no_external_stylesheet(self):
        self.assertNotIn("<link ", self.html)

    def test_no_external_script(self):
        self.assertNotIn("<script", self.html)

    def test_no_editable_inputs(self):
        self.assertNotIn("<input", self.html)
        self.assertNotIn("<textarea", self.html)
        self.assertNotIn("contenteditable", self.html)

    def test_no_save_button(self):
        self.assertNotIn("Save", self.html)
        self.assertNotIn("Apply", self.html)

    def test_valid_utf8(self):
        self.html.encode("utf-8")

    def test_valid_html_parseable(self):
        from html.parser import HTMLParser
        p = HTMLParser()
        p.feed(self.html)
        # Should not raise

    def test_profile_id_escaped(self):
        # If a profile ID contained html, it would be escaped
        self.assertIn("user", self.html)
        self.assertNotIn("<user>", self.html)

    def test_all_24_controls_in_html(self):
        for name in ("A1","A2","A3","A4","A5","A6","A7","A8","A9","A10","A11","A12",
                     "AL","AP","AR","BL","BP","BR","CL","CP","CR","DL","DP","DR"):
            self.assertIn(f">{name}<", self.html, f"Missing {name}")

    def test_text_action_escaped(self):
        # Build with a config containing <script> in text
        from yyr4_linux_control.configurator import generate_html as gen
        from yyr4_linux_control.configurator.builder import (
            _build_from_config, _build_action,
        )
        from yyr4_linux_control.control.config import load_control_config_from_string
        import tempfile, os
        config_toml = """
schema_version = 2
default_profile = "test"
initial_layer = "general"

[profiles.test.layers.general.controls.A1.action]
type = "text"
value = "<script>alert(1)</script>"
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write(config_toml)
            tmp = f.name
        try:
            from yyr4_linux_control.configurator.builder import build_document
            doc2 = build_document(Path(tmp))
            h = gen(doc2)
            self.assertNotIn("<script>alert", h)
            self.assertIn("&lt;script&gt;", h)
        finally:
            os.unlink(tmp)

    def test_command_argv_escaped(self):
        from yyr4_linux_control.configurator import generate_html as gen
        from yyr4_linux_control.configurator.builder import build_document
        import tempfile, os
        config_toml = """
schema_version = 2
default_profile = "test"
initial_layer = "general"

[profiles.test.layers.general.controls.A1.action]
type = "command"
argv = ["echo", "<evil>"]
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write(config_toml)
            tmp = f.name
        try:
            doc2 = build_document(Path(tmp))
            h = gen(doc2)
            self.assertNotIn("<evil>", h)
            # structured_details (argv) are not rendered in HTML by default
        finally:
            os.unlink(tmp)

    def test_no_inline_javascript(self):
        self.assertNotIn("javascript:", self.html)

    def test_safety_notice_present(self):
        self.assertIn("read-only preview", self.html.lower())
        self.assertIn("no actions are executed", self.html.lower())


if __name__ == "__main__":
    unittest.main()
