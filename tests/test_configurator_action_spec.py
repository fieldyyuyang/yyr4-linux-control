import unittest, json
from yyr4_linux_control.configurator.action_spec import parse_spec, action_to_spec
from yyr4_linux_control.control.actions import (
    HotkeyAction, TextAction, CommandAction, DelayAction,
    MacroAction, NoOpAction, DebugLogAction,
    SetLayerAction, NextLayerAction, PreviousLayerAction, SetProfileAction,
)

class TestActionSpec(unittest.TestCase):
    def test_noop(self):
        a = parse_spec({"type": "noop"})
        self.assertIsInstance(a, NoOpAction)
        self.assertEqual(action_to_spec(a), {"type": "noop"})

    def test_debug_log(self):
        a = parse_spec({"type": "debug_log", "message": "hello"})
        self.assertIsInstance(a, DebugLogAction)
        self.assertEqual(action_to_spec(a), {"type": "debug_log", "message": "hello"})

    def test_hotkey(self):
        a = parse_spec({"type": "hotkey", "keys": ["A", "B"]})
        self.assertEqual(a.keys, ("A", "B"))
        self.assertEqual(action_to_spec(a), {"type": "hotkey", "keys": ["A", "B"]})

    def test_text(self):
        a = parse_spec({"type": "text", "value": "hi"})
        self.assertEqual(a.value, "hi")
        self.assertEqual(action_to_spec(a), {"type": "text", "value": "hi"})

    def test_command(self):
        a = parse_spec({"type": "command", "argv": ["echo", "a"]})
        self.assertEqual(a.argv, ("echo", "a"))
        self.assertEqual(action_to_spec(a), {"type": "command", "argv": ["echo", "a"]})

    def test_command_with_timeout(self):
        a = parse_spec({"type": "command", "argv": ["x"], "timeout_seconds": 10})
        self.assertEqual(action_to_spec(a)["timeout_seconds"], 10)

    def test_delay(self):
        a = parse_spec({"type": "delay", "milliseconds": 250})
        self.assertEqual(a.milliseconds, 250)
        self.assertEqual(action_to_spec(a), {"type": "delay", "milliseconds": 250})

    def test_macro(self):
        a = parse_spec({"type": "macro", "steps": [
            {"type": "delay", "milliseconds": 100},
            {"type": "hotkey", "keys": ["A"]},
        ]})
        self.assertIsInstance(a, MacroAction)
        self.assertEqual(len(a.steps), 2)

    def test_set_layer(self):
        a = parse_spec({"type": "set_layer", "layer": "layer_1"})
        self.assertIsInstance(a, SetLayerAction)

    def test_next_layer(self):
        a = parse_spec({"type": "next_layer"})
        self.assertIsInstance(a, NextLayerAction)

    def test_previous_layer(self):
        a = parse_spec({"type": "previous_layer"})
        self.assertIsInstance(a, PreviousLayerAction)

    def test_set_profile(self):
        a = parse_spec({"type": "set_profile", "profile": "user"})
        self.assertIsInstance(a, SetProfileAction)

    # Negative tests
    def test_not_dict(self):
        with self.assertRaisesRegex(ValueError, "object"):
            parse_spec([])

    def test_missing_type(self):
        with self.assertRaisesRegex(ValueError, "type"):
            parse_spec({})

    def test_unknown_type(self):
        with self.assertRaisesRegex(ValueError, "unknown"):
            parse_spec({"type": "bogus"})

    def test_unknown_field(self):
        with self.assertRaisesRegex(ValueError, "unknown field"):
            parse_spec({"type": "noop", "extra": 1})

    def test_empty_hotkey(self):
        with self.assertRaisesRegex(ValueError, "non-empty"):
            parse_spec({"type": "hotkey", "keys": []})

    def test_hotkey_non_string(self):
        with self.assertRaisesRegex(ValueError, "non-empty string"):
            parse_spec({"type": "hotkey", "keys": [1]})

    def test_command_shell_string(self):
        with self.assertRaisesRegex(ValueError, "array"):
            parse_spec({"type": "command", "argv": "echo hi"})

    def test_negative_delay(self):
        with self.assertRaisesRegex(ValueError, "non-negative"):
            parse_spec({"type": "delay", "milliseconds": -1})

    def test_macro_depth_limit(self):
        inner = {"type": "delay", "milliseconds": 1}
        spec = inner
        for _ in range(12):
            spec = {"type": "macro", "steps": [spec]}
        with self.assertRaisesRegex(ValueError, "depth"):
            parse_spec(spec)

    def test_invalid_layer_id(self):
        with self.assertRaisesRegex(ValueError, "LayerId"):
            parse_spec({"type": "set_layer", "layer": "INVALID_LAYER"})

    def test_error_path(self):
        with self.assertRaises(ValueError) as ctx:
            parse_spec({"type": "macro", "steps": [
                {"type": "delay", "milliseconds": -5}
            ]})
        self.assertIn("action.steps[0].milliseconds", str(ctx.exception))

    def test_roundtrip_stable(self):
        import hashlib
        for atype, fields in [
            ("noop", {}),
            ("debug_log", {"message": "x"}),
            ("hotkey", {"keys": ["A"]}),
            ("text", {"value": "hi"}),
            ("command", {"argv": ["echo", "a"]}),
            ("delay", {"milliseconds": 100}),
            ("set_layer", {"layer": "layer_1"}),
            ("next_layer", {}),
            ("previous_layer", {}),
            ("set_profile", {"profile": "user"}),
        ]:
            spec = {"type": atype, **fields}
            a1 = parse_spec(spec)
            s1 = json.dumps(action_to_spec(a1), sort_keys=True)
            a2 = parse_spec(json.loads(s1))
            s2 = json.dumps(action_to_spec(a2), sort_keys=True)
            self.assertEqual(s1, s2, f"Unstable for {atype}")


if __name__ == "__main__":
    unittest.main()
