import unittest
from unittest.mock import patch
import sys
from yyr4_linux_control.device.linux_udev import LinuxUdevDiscoveryBackend
from yyr4_linux_control.device.errors import DependencyUnavailableError

class FakePyudevDevice:
    def __init__(self, device_node, sys_path, properties, device_links, parent=None):
        self.device_node = device_node
        self.sys_path = sys_path
        self.properties = properties
        self.device_links = device_links
        self._parent = parent

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

class TestLinuxUdevDiscovery(unittest.TestCase):
    @patch.dict(sys.modules, {"pyudev": None})
    def test_missing_pyudev(self):
        with self.assertRaises(DependencyUnavailableError) as ctx:
            LinuxUdevDiscoveryBackend()
        self.assertIsInstance(ctx.exception.__cause__, ImportError)

    def test_pyudev_restored_after_patch(self):
        import pyudev
        self.assertIsNotNone(pyudev.__file__)

                
    def test_enumerate(self):
        # Provide fake pyudev
        parent = FakePyudevDevice(None, "/sys/usb", {}, [])
        dev = FakePyudevDevice("/dev/input/event0", "/sys/kb", {"NAME": '"Test Device"'}, ["/dev/input/by-path/x"], parent)
        
        with patch.dict(sys.modules, {"pyudev": FakePyudevModule([dev])}):
                backend = LinuxUdevDiscoveryBackend()
                records = backend.enumerate_input_records()
                self.assertEqual(len(records), 1)
                self.assertEqual(records[0].device_node, "/dev/input/event0")
                self.assertEqual(records[0].parent_usb_syspath, "/sys/usb")
                self.assertEqual(records[0].device_name, "Test Device")


    def test_enumerate_skip_no_node(self):
        dev = FakePyudevDevice(None, "/sys/kb", {}, [])
        with patch.dict(sys.modules, {"pyudev": FakePyudevModule([dev])}):
                backend = LinuxUdevDiscoveryBackend()
                records = backend.enumerate_input_records()
                self.assertEqual(len(records), 0)

                
    def test_enumerate_skip_no_parent(self):
        dev = FakePyudevDevice("/dev/input/event0", "/sys/kb", {}, [])
        with patch.dict(sys.modules, {"pyudev": FakePyudevModule([dev])}):
                backend = LinuxUdevDiscoveryBackend()
                records = backend.enumerate_input_records()
                self.assertEqual(len(records), 0)


    def test_enumerate_properties_immutable(self):
        parent = FakePyudevDevice(None, "/sys/usb", {}, [])
        dev = FakePyudevDevice("/dev/input/event0", "/sys/kb", {"NAME": '"Test"'}, [], parent)
        with patch.dict(sys.modules, {"pyudev": FakePyudevModule([dev])}):
                backend = LinuxUdevDiscoveryBackend()
                records = backend.enumerate_input_records()
                with self.assertRaises(TypeError):
                    records[0].properties["NAME"] = "Modified"


    def test_enumerate_invalid_device_links(self):
        parent = FakePyudevDevice(None, "/sys/usb", {}, [])
        dev = FakePyudevDevice("/dev/input/event0", "/sys/kb", {}, "just a string not list", parent)
        with patch.dict(sys.modules, {"pyudev": FakePyudevModule([dev])}):
                backend = LinuxUdevDiscoveryBackend()
                records = backend.enumerate_input_records()
                self.assertEqual(len(records[0].devlinks), 22) # Length of string
