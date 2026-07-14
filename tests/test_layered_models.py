import unittest
from yyr4_linux_control.control.models import ProfileId, LayerId

class TestLayeredModels(unittest.TestCase):
    def test_layer_id_valid_values(self):
        expected_layers = {
            "general", "layer_1", "layer_2", "layer_3",
            "layer_4", "layer_5", "layer_6", "layer_7", "layer_8"
        }
        self.assertEqual(len(LayerId), 9)
        self.assertEqual({l.value for l in LayerId}, expected_layers)
        self.assertEqual(LayerId("general"), LayerId.GENERAL)
        self.assertEqual(LayerId("layer_1"), LayerId.LAYER_1)
        self.assertEqual(LayerId("layer_8"), LayerId.LAYER_8)

    def test_layer_id_invalid_values(self):
        with self.assertRaises(ValueError):
            LayerId("layer_0")
        with self.assertRaises(ValueError):
            LayerId("layer_9")
        with self.assertRaises(ValueError):
            LayerId("unknown")

    def test_profile_id_valid(self):
        # Valid shortest (1 char) and longest (64 chars)
        self.assertEqual(ProfileId("a").value, "a")
        self.assertEqual(ProfileId("default").value, "default")
        self.assertEqual(ProfileId("my-profile_123").value, "my-profile_123")
        self.assertEqual(ProfileId("a" * 64).value, "a" * 64)

    def test_profile_id_invalid(self):
        with self.assertRaisesRegex(ValueError, "Invalid ProfileId"):
            ProfileId("")
        with self.assertRaisesRegex(ValueError, "Invalid ProfileId"):
            ProfileId("A")
        with self.assertRaisesRegex(ValueError, "Invalid ProfileId"):
            ProfileId("my profile")
        with self.assertRaisesRegex(ValueError, "Invalid ProfileId"):
            ProfileId("my/profile")
        with self.assertRaisesRegex(ValueError, "Invalid ProfileId"):
            ProfileId(".")
        with self.assertRaisesRegex(ValueError, "Invalid ProfileId"):
            ProfileId("..")
        with self.assertRaisesRegex(ValueError, "Invalid ProfileId"):
            ProfileId("a" * 65)
        with self.assertRaisesRegex(ValueError, "ProfileId must be a string"):
            ProfileId(123)
