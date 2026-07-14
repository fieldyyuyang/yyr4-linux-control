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
        self.assertEqual(config.schema_version, 1)
        self.assertEqual(config.default_profile.value, "default")
        self.assertEqual(config.initial_layer.value, "general")
        self.assertIn("default", [p.value for p in config.profiles.keys()])
        
        default_profile = config.profiles[config.default_profile]
        general_layer = default_profile.layers[config.initial_layer]
        controls = general_layer.controls
        
        self.assertEqual(len(controls), 3)
        self.assertIsInstance(controls[OfficialControl.A1], HotkeyAction)
        self.assertEqual(controls[OfficialControl.A1].keys, ("CTRL", "C"))
        
        self.assertIsInstance(controls[OfficialControl.AP], MacroAction)
        self.assertEqual(len(controls[OfficialControl.AP].steps), 2)
        self.assertIsInstance(controls[OfficialControl.AP].steps[0], TextAction)
        self.assertIsInstance(controls[OfficialControl.AP].steps[1], DelayAction)

        self.assertIsInstance(controls[OfficialControl.BL], NoOpAction)

    def test_missing_schema_version(self):
        with self.assertRaises(UnsupportedSchemaVersionError):
            load_control_config_from_string("[controls.A1]")

    def test_wrong_schema_version(self):
        with self.assertRaises(UnsupportedSchemaVersionError):
            load_control_config_from_string("schema_version = 3\n")

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

    def test_schema_v2_valid(self):
        toml_str = """
schema_version = 2
default_profile = "my_prof"
initial_layer = "layer_1"

[profiles.my_prof.layers.general.controls.A1]
action = { type = "noop" }

[profiles.my_prof.layers.layer_1.controls.A1]
action = { type = "text", value = "hello" }
"""
        config = load_control_config_from_string(toml_str)
        self.assertEqual(config.schema_version, 2)
        self.assertEqual(config.default_profile.value, "my_prof")
        self.assertEqual(config.initial_layer.value, "layer_1")
        self.assertIn("my_prof", [p.value for p in config.profiles.keys()])
        
        prof = config.profiles[config.default_profile]
        self.assertEqual(len(prof.layers), 2)
        self.assertIsInstance(prof.layers[config.initial_layer].controls[OfficialControl.A1], TextAction)
        self.assertIsInstance(prof.layers[config.profiles[config.default_profile].layers["general"].layer_id].controls[OfficialControl.A1], NoOpAction)
