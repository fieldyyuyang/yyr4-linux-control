import unittest
from yyr4_linux_control.control.config import load_control_config_from_string
from yyr4_linux_control.control.errors import ConfigValidationError
from yyr4_linux_control.control.models import OfficialControl
from yyr4_linux_control.control.actions import NoOpAction, TextAction

class TestLayeredConfig(unittest.TestCase):
    def test_schema_v2_valid_multi_profile(self):
        toml_str = """
schema_version = 2
default_profile = "prof1"
initial_layer = "layer_1"

[profiles.prof1.layers.general.controls.A1]
action = { type = "noop" }

[profiles.prof1.layers.layer_1.controls.A1]
action = { type = "text", value = "override" }

[profiles.prof2.layers.general.controls.A2]
action = { type = "noop" }
"""
        config = load_control_config_from_string(toml_str)
        self.assertEqual(config.schema_version, 2)
        self.assertEqual(len(config.profiles), 2)
        self.assertIn("prof1", [p.value for p in config.profiles])
        self.assertIn("prof2", [p.value for p in config.profiles])
        self.assertIsInstance(config.profiles[config.default_profile].layers[config.initial_layer].controls[OfficialControl.A1], TextAction)

    def test_schema_v2_missing_profiles(self):
        toml_str = """
schema_version = 2
default_profile = "default"
initial_layer = "general"
"""
        with self.assertRaisesRegex(ConfigValidationError, "profiles must be a non-empty table"):
            load_control_config_from_string(toml_str)

    def test_schema_v2_empty_profiles(self):
        toml_str = """
schema_version = 2
default_profile = "default"
initial_layer = "general"
[profiles]
"""
        with self.assertRaisesRegex(ConfigValidationError, "profiles must be a non-empty table"):
            load_control_config_from_string(toml_str)

    def test_schema_v2_missing_general_layer(self):
        toml_str = """
schema_version = 2
default_profile = "prof1"
initial_layer = "layer_1"

[profiles.prof1.layers.layer_1.controls.A1]
action = { type = "noop" }
"""
        with self.assertRaisesRegex(ConfigValidationError, "Profile prof1 must contain a 'general' layer"):
            load_control_config_from_string(toml_str)

    def test_schema_v2_default_profile_not_exist(self):
        toml_str = """
schema_version = 2
default_profile = "prof2"
initial_layer = "general"

[profiles.prof1.layers.general.controls.A1]
action = { type = "noop" }
"""
        with self.assertRaisesRegex(ConfigValidationError, "default_profile 'prof2' is not defined in profiles"):
            load_control_config_from_string(toml_str)

    def test_schema_v2_unknown_top_level_field(self):
        toml_str = """
schema_version = 2
default_profile = "prof1"
initial_layer = "general"
unknown = "field"

[profiles.prof1.layers.general.controls.A1]
action = { type = "noop" }
"""
        with self.assertRaisesRegex(ConfigValidationError, "Unknown top-level field: unknown"):
            load_control_config_from_string(toml_str)

    def test_schema_v2_unknown_profile_field(self):
        toml_str = """
schema_version = 2
default_profile = "prof1"
initial_layer = "general"

[profiles.prof1]
unknown_field = 123

[profiles.prof1.layers.general.controls.A1]
action = { type = "noop" }
"""
        with self.assertRaisesRegex(ConfigValidationError, "Unknown field in profile"):
            load_control_config_from_string(toml_str)

    def test_schema_v2_invalid_layer_name(self):
        toml_str = """
schema_version = 2
default_profile = "prof1"
initial_layer = "general"

[profiles.prof1.layers.general.controls.A1]
action = { type = "noop" }

[profiles.prof1.layers.layer_9.controls.A2]
action = { type = "noop" }
"""
        with self.assertRaisesRegex(ConfigValidationError, "Unknown LayerId"):
            load_control_config_from_string(toml_str)

    def test_schema_v2_unknown_layer_field(self):
        toml_str = """
schema_version = 2
default_profile = "prof1"
initial_layer = "general"

[profiles.prof1.layers.general]
unknown_field = 123
[profiles.prof1.layers.general.controls.A1]
action = { type = "noop" }
"""
        with self.assertRaisesRegex(ConfigValidationError, "Unknown field in layer"):
            load_control_config_from_string(toml_str)
