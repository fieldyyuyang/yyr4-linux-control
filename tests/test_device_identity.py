import unittest
from yyr4_linux_control.device.identity import YYR4Identity, InputInterface, InterfaceRole

class TestDeviceIdentity(unittest.TestCase):
    def setUp(self):
        self.kb = InputInterface(
            role=InterfaceRole.KEYBOARD,
            device_node="/dev/input/event0",
            device_name="YYR4 Keyboard",
            usb_interface_number="02",
            readable=True,
            syspath="/sys/devices/pci0000:00/0000:00:14.0/usb1/1-1/1-1:1.2/input/input0/event0",
            parent_usb_syspath="/sys/devices/pci0000:00/0000:00:14.0/usb1/1-1"
        )
        self.ms = InputInterface(
            role=InterfaceRole.MOUSE,
            device_node="/dev/input/event1",
            device_name="YYR4 Mouse",
            usb_interface_number="2",  # Should be normalized to 02
            readable=True,
            syspath="/sys/devices/pci0000:00/0000:00:14.0/usb1/1-1/1-1:1.2/input/input1/event1",
            parent_usb_syspath="/sys/devices/pci0000:00/0000:00:14.0/usb1/1-1"
        )

    def test_valid_identity(self):
        idx = YYR4Identity(
            vendor_id="239A",
            product_id="80F4",
            manufacturer="YOUYOU Keyb_V2",
            product="YOUYOU TEC.",
            usb_parent_syspath="/sys/devices/pci0000:00/0000:00:14.0/usb1/1-1",
            keyboard=self.kb,
            mouse=self.ms,
            serial_present=True
        )
        self.assertEqual(idx.vendor_id, "239a")
        self.assertEqual(idx.product_id, "80f4")
        self.assertEqual(idx.mouse.usb_interface_number, "02")
        self.assertNotIn("raw_serial", repr(idx)) # repr shouldn't contain raw serial anyway as it's not a field

    def test_empty_device_node(self):
        with self.assertRaises(ValueError):
            InputInterface(InterfaceRole.KEYBOARD, "", "name", "02", True, "sys", "par")

    def test_empty_syspath(self):
        with self.assertRaises(ValueError):
            InputInterface(InterfaceRole.KEYBOARD, "node", "name", "02", True, "", "par")

    def test_empty_parent_syspath(self):
        with self.assertRaises(ValueError):
            InputInterface(InterfaceRole.KEYBOARD, "node", "name", "02", True, "sys", "")
            
    def test_empty_interface_number(self):
        with self.assertRaises(ValueError):
            InputInterface(InterfaceRole.KEYBOARD, "node", "name", "", True, "sys", "par")

    def test_empty_manufacturer(self):
        with self.assertRaises(ValueError):
            YYR4Identity("239a", "80f4", "", "product", "par", self.kb, self.ms, False)

    def test_empty_product(self):
        with self.assertRaises(ValueError):
            YYR4Identity("239a", "80f4", "man", "", "par", self.kb, self.ms, False)

    def test_mismatched_parent_keyboard(self):
        kb2 = InputInterface(InterfaceRole.KEYBOARD, "n", "n", "02", True, "s", "other_par")
        with self.assertRaises(ValueError):
            YYR4Identity("239a", "80f4", "man", "prod", "par", kb2, self.ms, False)

    def test_mismatched_parent_mouse(self):
        ms2 = InputInterface(InterfaceRole.MOUSE, "n", "n", "02", True, "s", "other_par")
        with self.assertRaises(ValueError):
            YYR4Identity("239a", "80f4", "man", "prod", "par", self.kb, ms2, False)

    def test_wrong_interface_keyboard(self):
        kb2 = InputInterface(InterfaceRole.KEYBOARD, "n", "n", "01", True, "s", "par")
        with self.assertRaises(ValueError):
            YYR4Identity("239a", "80f4", "man", "prod", "par", kb2, self.ms, False)

    def test_wrong_interface_mouse(self):
        ms2 = InputInterface(InterfaceRole.MOUSE, "n", "n", "03", True, "s", "par")
        with self.assertRaises(ValueError):
            YYR4Identity("239a", "80f4", "man", "prod", "par", self.kb, ms2, False)

    def test_duplicate_roles(self):
        ms2 = InputInterface(InterfaceRole.KEYBOARD, "n", "n", "02", True, "s", "par")
        with self.assertRaises(ValueError):
            YYR4Identity("239a", "80f4", "man", "prod", "par", self.kb, ms2, False)
            
    def test_immutability(self):
        idx = YYR4Identity("239a", "80f4", "m", "p", self.kb.parent_usb_syspath, self.kb, self.ms, False)
        with self.assertRaises(Exception):
            idx.manufacturer = "new"
