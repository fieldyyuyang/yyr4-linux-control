import unittest
from yyr4_linux_control.control.config import load_control_config_from_string
from yyr4_linux_control.control.actions import SetLayerAction, NextLayerAction, PreviousLayerAction, SetProfileAction
from yyr4_linux_control.control.models import ProfileId, LayerId, OfficialControl

class TestConfigRuntimeActions(unittest.TestCase):
    def test_parse_runtime_actions(self):
        toml_content = """
        schema_version = 2
        default_profile = "media"
        initial_layer = "general"

        [profiles.media.layers.general.controls.A1.action]
        type = "set_layer"
        layer = "layer_1"

        [profiles.media.layers.general.controls.A2.action]
        type = "next_layer"

        [profiles.media.layers.general.controls.A3.action]
        type = "previous_layer"

        [profiles.media.layers.general.controls.A4.action]
        type = "set_profile"
        profile = "media"
        """
        config = load_control_config_from_string(toml_content)
        controls = config.profiles[ProfileId("media")].layers[LayerId("general")].controls
        self.assertIsInstance(controls[OfficialControl.A1], SetLayerAction)
        self.assertEqual(controls[OfficialControl.A1].layer, "layer_1")
        self.assertIsInstance(controls[OfficialControl.A2], NextLayerAction)
        self.assertIsInstance(controls[OfficialControl.A3], PreviousLayerAction)
        self.assertIsInstance(controls[OfficialControl.A4], SetProfileAction)
        self.assertEqual(controls[OfficialControl.A4].profile, "media")

    def test_schema_v1_rejects_runtime_actions(self):
        from yyr4_linux_control.control.errors import InvalidActionError
        toml_content = """
        schema_version = 1
        [controls.A1.action]
        type = "set_layer"
        layer = "layer_1"
        """
        with self.assertRaisesRegex(InvalidActionError, "set_layer action is only available in schema version 2"):
            load_control_config_from_string(toml_content)

if __name__ == '__main__':
    unittest.main()
