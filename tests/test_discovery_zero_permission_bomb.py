import unittest
from unittest.mock import patch
from yyr4_linux_control.device.linux_udev import LinuxUdevDiscoveryBackend
from yyr4_linux_control.device.discovery import YYR4DeviceDiscovery
from yyr4_linux_control.device.errors import DeviceNotFoundError, DeviceAmbiguousError, DeviceIncompleteError

class FakePyudevDevice:
    def __init__(self, device_node, sys_path, properties, device_links, parent=None, attributes=None):
        self.device_node = device_node
        self.sys_path = sys_path
        self.properties = properties
        self.device_links = device_links
        self._parent = parent
        self.attributes = attributes or {}

    def find_parent(self, subsystem, devtype):
        return self._parent

class FakePyudevContext:
    def __init__(self, devices):
        self._devices = devices

    def list_devices(self, subsystem):
        return self._devices

class FakePyudevModule:
    def __init__(self, devices):
        self.Context = lambda: FakePyudevContext(devices)

class TestDiscoveryZeroPermissionBomb(unittest.TestCase):
    def setUp(self):
        # We will patch os.access. If any call is made, it will raise AssertionError.
        patcher = patch("os.access")
        self.mock_os_access = patcher.start()
        def bomb_os_access(path, mode, *args, **kwargs):
            raise AssertionError(f"BOMB: os.access called on {path} with mode {mode} during discovery!")
        self.mock_os_access.side_effect = bomb_os_access
        self.addCleanup(patcher.stop)

        # Parent USB device for YYR4
        self.valid_parent = FakePyudevDevice("/sys/usb", "/sys/usb", {}, (), attributes={"idVendor": "239a", "idProduct": "80f4", "manufacturer": "YOUYOU TEC.", "product": "YOUYOU Keyb_V2"})

    def run_discovery_with_devices(self, devices):
        fake_module = FakePyudevModule(devices)
        with patch.dict("sys.modules", {"pyudev": fake_module}):
            backend = LinuxUdevDiscoveryBackend()
            selector = YYR4DeviceDiscovery(backend)
            return selector.select_single()

    def test_1_six_record_composite_success(self):
        # Keyboard
        kb_props = {"ID_BUS": "usb", "ID_USB_INTERFACE_NUM": "02", "ID_INPUT_KEYBOARD": "1", "NAME": '"YOUYOU Keyb_V2 Keyboard"'}
        kb = FakePyudevDevice("/dev/input/event1", "/sys/kb", kb_props, (), parent=self.valid_parent)

        # Mouse
        ms_props = {"ID_BUS": "usb", "ID_USB_INTERFACE_NUM": "02", "ID_INPUT_MOUSE": "1", "NAME": '"YOUYOU Keyb_V2 Mouse"'}
        ms = FakePyudevDevice("/dev/input/event2", "/sys/ms", ms_props, (), parent=self.valid_parent)

        # 4 Extras
        extras = []
        for i in range(4):
            ex_props = {"ID_BUS": "usb", "ID_USB_INTERFACE_NUM": "02", "NAME": f'"YOUYOU Keyb_V2 Extra {i}"'}
            extras.append(FakePyudevDevice(f"/dev/input/event{3+i}", f"/sys/ex{i}", ex_props, (), parent=self.valid_parent))

        devices = [kb, ms] + extras

        identity = self.run_discovery_with_devices(devices)
        self.assertEqual(identity.keyboard.device_node, "/dev/input/event1")
        self.assertEqual(identity.mouse.device_node, "/dev/input/event2")
        # Ensure bomb was not triggered
        self.mock_os_access.assert_not_called()

    def test_2_unrelated_vendor_device(self):
        other_parent = FakePyudevDevice("/sys/other", "/sys/other", {}, (), attributes={"idVendor": "1111", "idProduct": "2222", "manufacturer": "Other", "product": "Device"})
        other_kb = FakePyudevDevice("/dev/input/event0", "/sys/okb", {"ID_BUS": "usb", "ID_USB_INTERFACE_NUM": "01", "ID_INPUT_KEYBOARD": "1"}, (), parent=other_parent)

        with self.assertRaises(DeviceNotFoundError):
            self.run_discovery_with_devices([other_kb])
        self.mock_os_access.assert_not_called()

    def test_3_wrong_interface(self):
        kb_props = {"ID_BUS": "usb", "ID_USB_INTERFACE_NUM": "01", "ID_INPUT_KEYBOARD": "1"}
        kb = FakePyudevDevice("/dev/input/event1", "/sys/kb", kb_props, (), parent=self.valid_parent)

        with self.assertRaises(DeviceNotFoundError):
            self.run_discovery_with_devices([kb])
        self.mock_os_access.assert_not_called()

    def test_4_incomplete_device(self):
        kb_props = {"ID_BUS": "usb", "ID_USB_INTERFACE_NUM": "02", "ID_INPUT_KEYBOARD": "1"}
        kb = FakePyudevDevice("/dev/input/event1", "/sys/kb", kb_props, (), parent=self.valid_parent)

        with self.assertRaises(DeviceIncompleteError):
            self.run_discovery_with_devices([kb])
        self.mock_os_access.assert_not_called()

    def test_5_ambiguous_devices(self):
        kb1_props = {"ID_BUS": "usb", "ID_USB_INTERFACE_NUM": "02", "ID_INPUT_KEYBOARD": "1", "NAME": '"YOUYOU Keyb_V2 Keyboard"'}
        kb1 = FakePyudevDevice("/dev/input/event1", "/sys/kb1", kb1_props, (), parent=self.valid_parent)

        ms1_props = {"ID_BUS": "usb", "ID_USB_INTERFACE_NUM": "02", "ID_INPUT_MOUSE": "1", "NAME": '"YOUYOU Keyb_V2 Mouse"'}
        ms1 = FakePyudevDevice("/dev/input/event2", "/sys/ms1", ms1_props, (), parent=self.valid_parent)

        parent2 = FakePyudevDevice("/sys/usb2", "/sys/usb2", {}, (), attributes={"idVendor": "239a", "idProduct": "80f4", "manufacturer": "YOUYOU TEC.", "product": "YOUYOU Keyb_V2"})
        kb2 = FakePyudevDevice("/dev/input/event3", "/sys/kb2", kb1_props, (), parent=parent2)
        ms2 = FakePyudevDevice("/dev/input/event4", "/sys/ms2", ms1_props, (), parent=parent2)

        with self.assertRaises(DeviceAmbiguousError):
            self.run_discovery_with_devices([kb1, ms1, kb2, ms2])
        self.mock_os_access.assert_not_called()

if __name__ == "__main__":
    unittest.main()
