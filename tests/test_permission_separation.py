import unittest
import os
from unittest.mock import patch, call
from yyr4_linux_control.device.identity import YYR4Identity, InputInterface, InterfaceRole
from yyr4_linux_control.integration.preflight import FilesystemIdentityPermissionChecker

class TestPermissionSeparation(unittest.TestCase):
    def setUp(self):
        self.kb = InputInterface(InterfaceRole.KEYBOARD, "/dev/input/fake_event999", "KB", "02", "/sys/kb", "/sys/usb")
        self.ms = InputInterface(InterfaceRole.MOUSE, "/dev/input/fake_event888", "MS", "02", "/sys/ms", "/sys/usb")
        self.identity = YYR4Identity("239a", "80f4", "M", "P", "/sys/usb", self.kb, self.ms, False)
        self.checker = FilesystemIdentityPermissionChecker()

    @patch("os.access")
    def test_both_unreadable(self, mock_access):
        mock_access.return_value = False

        result = self.checker.check(self.identity)

        self.assertFalse(result.keyboard_readable)
        self.assertFalse(result.mouse_readable)
        self.assertFalse(result.all_required_readable)

        self.assertEqual(mock_access.call_count, 2)
        mock_access.assert_has_calls([
            call("/dev/input/fake_event999", os.R_OK),
            call("/dev/input/fake_event888", os.R_OK)
        ], any_order=True)

    @patch("os.access")
    def test_kb_readable_ms_unreadable(self, mock_access):
        def side_effect(path, mode):
            if path == "/dev/input/fake_event999": return True
            if path == "/dev/input/fake_event888": return False
            return False
        mock_access.side_effect = side_effect

        result = self.checker.check(self.identity)

        self.assertTrue(result.keyboard_readable)
        self.assertFalse(result.mouse_readable)
        self.assertFalse(result.all_required_readable)

    @patch("os.access")
    def test_kb_unreadable_ms_readable(self, mock_access):
        def side_effect(path, mode):
            if path == "/dev/input/fake_event999": return False
            if path == "/dev/input/fake_event888": return True
            return False
        mock_access.side_effect = side_effect

        result = self.checker.check(self.identity)

        self.assertFalse(result.keyboard_readable)
        self.assertTrue(result.mouse_readable)
        self.assertFalse(result.all_required_readable)

    @patch("os.access")
    def test_both_readable_and_identity_unchanged(self, mock_access):
        mock_access.return_value = True

        result = self.checker.check(self.identity)

        self.assertTrue(result.keyboard_readable)
        self.assertTrue(result.mouse_readable)
        self.assertTrue(result.all_required_readable)

        # Check Identity unchanged
        self.assertEqual(self.identity.keyboard.device_node, "/dev/input/fake_event999")
        self.assertEqual(self.identity.mouse.device_node, "/dev/input/fake_event888")

if __name__ == "__main__":
    unittest.main()
