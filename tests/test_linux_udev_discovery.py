import unittest
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
    def test_missing_pyudev(self):
        # Temporarily shadow pyudev if it exists
        old = sys.modules.get("pyudev")
        sys.modules["pyudev"] = None
        try:
            with self.assertRaises(DependencyUnavailableError):
                LinuxUdevDiscoveryBackend()
        finally:
            if old:
                sys.modules["pyudev"] = old
            else:
                del sys.modules["pyudev"]
                
    def test_enumerate(self):
        # Provide fake pyudev
        parent = FakePyudevDevice(None, "/sys/usb", {}, [])
        dev = FakePyudevDevice("/dev/input/event0", "/sys/kb", {"NAME": '"Test Device"'}, ["/dev/input/by-path/x"], parent)
        
        old = sys.modules.get("pyudev")
        sys.modules["pyudev"] = FakePyudevModule([dev])
        try:
            backend = LinuxUdevDiscoveryBackend()
            records = backend.enumerate_input_records()
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0].device_node, "/dev/input/event0")
            self.assertEqual(records[0].parent_usb_syspath, "/sys/usb")
            self.assertEqual(records[0].device_name, "Test Device")
        finally:
            if old:
                sys.modules["pyudev"] = old
            else:
                del sys.modules["pyudev"]

    def test_enumerate_skip_no_node(self):
        dev = FakePyudevDevice(None, "/sys/kb", {}, [])
        old = sys.modules.get("pyudev")
        sys.modules["pyudev"] = FakePyudevModule([dev])
        try:
            backend = LinuxUdevDiscoveryBackend()
            records = backend.enumerate_input_records()
            self.assertEqual(len(records), 0)
        finally:
            if old:
                sys.modules["pyudev"] = old
            else:
                del sys.modules["pyudev"]
                
    def test_enumerate_skip_no_parent(self):
        dev = FakePyudevDevice("/dev/input/event0", "/sys/kb", {}, [])
        old = sys.modules.get("pyudev")
        sys.modules["pyudev"] = FakePyudevModule([dev])
        try:
            backend = LinuxUdevDiscoveryBackend()
            records = backend.enumerate_input_records()
            self.assertEqual(len(records), 0)
        finally:
            if old:
                sys.modules["pyudev"] = old
            else:
                del sys.modules["pyudev"]

    def test_enumerate_properties_immutable(self):
        parent = FakePyudevDevice(None, "/sys/usb", {}, [])
        dev = FakePyudevDevice("/dev/input/event0", "/sys/kb", {"NAME": '"Test"'}, [], parent)
        old = sys.modules.get("pyudev")
        sys.modules["pyudev"] = FakePyudevModule([dev])
        try:
            backend = LinuxUdevDiscoveryBackend()
            records = backend.enumerate_input_records()
            with self.assertRaises(TypeError):
                records[0].properties["NAME"] = "Modified"
        finally:
            if old: sys.modules["pyudev"] = old
            else: del sys.modules["pyudev"]

    def test_enumerate_invalid_device_links(self):
        parent = FakePyudevDevice(None, "/sys/usb", {}, [])
        dev = FakePyudevDevice("/dev/input/event0", "/sys/kb", {}, "just a string not list", parent)
        old = sys.modules.get("pyudev")
        sys.modules["pyudev"] = FakePyudevModule([dev])
        try:
            backend = LinuxUdevDiscoveryBackend()
            records = backend.enumerate_input_records()
            self.assertEqual(len(records[0].devlinks), 22) # Length of string
        finally:
            if old: sys.modules["pyudev"] = old
            else: del sys.modules["pyudev"]
