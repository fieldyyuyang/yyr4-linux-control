import unittest
from pathlib import Path
from yyr4_linux_control.control.config import load_control_config_from_string
from yyr4_linux_control.control.models import OfficialControl
from yyr4_linux_control.control.actions import (
    HotkeyAction, TextAction, CommandAction, DelayAction, MacroAction, NoOpAction, DebugLogAction
)
from yyr4_linux_control.control.errors import (
    UnsupportedSchemaVersionError, ConfigSyntaxError, ConfigValidationError,
    UnknownControlError, UnknownActionTypeError, InvalidActionError
)

class TestControlConfig(unittest.TestCase):
    def test_valid_config(self):
        toml_str = """
schema_version = 1
[controls.A1.action]
type = "hotkey"
keys = ["CTRL", "C"]

[controls.AP.action]
type = "macro"
steps = [
    { type = "text", value = "hello" },
    { type = "delay", milliseconds = 100 }
]

[controls.BL.action]
type = "noop"
"""
        config = load_control_config_from_string(toml_str)
        self.assertEqual(len(config), 3)
        self.assertIsInstance(config[OfficialControl.A1], HotkeyAction)
        self.assertEqual(config[OfficialControl.A1].keys, ("CTRL", "C"))
        
        self.assertIsInstance(config[OfficialControl.AP], MacroAction)
        self.assertEqual(len(config[OfficialControl.AP].steps), 2)
        self.assertIsInstance(config[OfficialControl.AP].steps[0], TextAction)
        self.assertIsInstance(config[OfficialControl.AP].steps[1], DelayAction)

        self.assertIsInstance(config[OfficialControl.BL], NoOpAction)

    def test_missing_schema_version(self):
        with self.assertRaises(UnsupportedSchemaVersionError):
            load_control_config_from_string("[controls.A1]")

    def test_wrong_schema_version(self):
        with self.assertRaises(UnsupportedSchemaVersionError):
            load_control_config_from_string("schema_version = 2\n[controls.A1]")

    def test_syntax_error(self):
        with self.assertRaises(ConfigSyntaxError):
            load_control_config_from_string("schema_version = 1\n[controls.A1")

    def test_unknown_top_level(self):
        with self.assertRaises(ConfigValidationError):
            load_control_config_from_string("schema_version = 1\n[foo]")

    def test_unknown_control(self):
        with self.assertRaisesRegex(UnknownControlError, "Unknown control: UNKNOWN"):
            load_control_config_from_string("schema_version = 1\n[controls.UNKNOWN.action]\ntype='noop'")

    def test_unknown_action_type(self):
        with self.assertRaisesRegex(UnknownActionTypeError, "Unknown action type: magic"):
            load_control_config_from_string("schema_version = 1\n[controls.A1.action]\ntype='magic'")

    def test_invalid_hotkey(self):
        with self.assertRaises(InvalidActionError):
            load_control_config_from_string("schema_version = 1\n[controls.A1.action]\ntype='hotkey'\nkeys='CTRL'")
        with self.assertRaises(InvalidActionError):
            load_control_config_from_string("schema_version = 1\n[controls.A1.action]\ntype='hotkey'\nkeys=[]")

    def test_invalid_text(self):
        with self.assertRaises(InvalidActionError):
            load_control_config_from_string("schema_version = 1\n[controls.A1.action]\ntype='text'\nvalue=123")

    def test_invalid_command(self):
        with self.assertRaises(InvalidActionError):
            load_control_config_from_string("schema_version = 1\n[controls.A1.action]\ntype='command'\nargv='ls'")
        with self.assertRaises(InvalidActionError):
            load_control_config_from_string("schema_version = 1\n[controls.A1.action]\ntype='command'\nargv=[]")
        with self.assertRaises(InvalidActionError):
            load_control_config_from_string("schema_version = 1\n[controls.A1.action]\ntype='command'\nargv=['ls']\ntimeout_seconds='1'")

    def test_invalid_delay(self):
        with self.assertRaises(InvalidActionError):
            load_control_config_from_string("schema_version = 1\n[controls.A1.action]\ntype='delay'\nmilliseconds='10'")
        with self.assertRaises(InvalidActionError):
            load_control_config_from_string("schema_version = 1\n[controls.A1.action]\ntype='delay'\nmilliseconds=-5")

    def test_invalid_macro(self):
        with self.assertRaises(InvalidActionError):
            load_control_config_from_string("schema_version = 1\n[controls.A1.action]\ntype='macro'\nsteps={}")

    def test_invalid_debug_log(self):
        with self.assertRaises(InvalidActionError):
            load_control_config_from_string("schema_version = 1\n[controls.A1.action]\ntype='debug_log'\nmessage=1")

    def test_unknown_field_in_action(self):
        with self.assertRaises(ConfigValidationError):
            load_control_config_from_string("schema_version = 1\n[controls.A1.action]\ntype='noop'\nfoo='bar'")
