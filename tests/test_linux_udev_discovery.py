import unittest
from unittest.mock import patch
import sys
from yyr4_linux_control.device.linux_udev import LinuxUdevDiscoveryBackend
from yyr4_linux_control.device.errors import DependencyUnavailableError

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

    def test_read_usb_descriptor_sysfs_bytes(self):
        # 原始sysfs是bytes，包含尾随NUL和空格
        parent = FakePyudevDevice(None, "/sys/usb", {}, [], attributes={"manufacturer": b"  YOUYOU TEC.\x00  \x00"})
        dev = FakePyudevDevice("/dev/input/event0", "/sys/kb", {"NAME": '"Test Device"'}, [], parent)
        with patch.dict(sys.modules, {"pyudev": FakePyudevModule([dev])}):
            backend = LinuxUdevDiscoveryBackend()
            records = backend.enumerate_input_records()
            self.assertEqual(records[0].properties["YYR4_NORMALIZED_MANUFACTURER"], "YOUYOU TEC.")

    def test_read_usb_descriptor_sysfs_string(self):
        # 原始sysfs是string
        parent = FakePyudevDevice(None, "/sys/usb", {}, [], attributes={"manufacturer": "  YOUYOU TEC.\x00"})
        dev = FakePyudevDevice("/dev/input/event0", "/sys/kb", {"NAME": '"Test Device"'}, [], parent)
        with patch.dict(sys.modules, {"pyudev": FakePyudevModule([dev])}):
            backend = LinuxUdevDiscoveryBackend()
            records = backend.enumerate_input_records()
            self.assertEqual(records[0].properties["YYR4_NORMALIZED_MANUFACTURER"], "YOUYOU TEC.")

    def test_read_usb_descriptor_udev_enc(self):
        # fallback to ENC
        parent = FakePyudevDevice(None, "/sys/usb", {}, [], attributes={})
        dev = FakePyudevDevice("/dev/input/event0", "/sys/kb", {"NAME": '"Test Device"', "ID_VENDOR_ENC": "YOUYOU\\x20TEC.\\x00"}, [], parent)
        with patch.dict(sys.modules, {"pyudev": FakePyudevModule([dev])}):
            backend = LinuxUdevDiscoveryBackend()
            records = backend.enumerate_input_records()
            self.assertEqual(records[0].properties["YYR4_NORMALIZED_MANUFACTURER"], "YOUYOU TEC.")

    def test_read_usb_descriptor_udev_fallback(self):
        # fallback to normal
        parent = FakePyudevDevice(None, "/sys/usb", {}, [], attributes={})
        dev = FakePyudevDevice("/dev/input/event0", "/sys/kb", {"NAME": '"Test Device"', "ID_VENDOR": "YOUYOU_TEC.\x00"}, [], parent)
        with patch.dict(sys.modules, {"pyudev": FakePyudevModule([dev])}):
            backend = LinuxUdevDiscoveryBackend()
            records = backend.enumerate_input_records()
            self.assertEqual(records[0].properties["YYR4_NORMALIZED_MANUFACTURER"], "YOUYOU_TEC.")


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

from yyr4_linux_control.device.linux_udev import _decode_udev_encoded_text, _decode_sysfs_bytes, _truncate_nul_text

class TestUdevDecoding(unittest.TestCase):
    def test_truncate_nul_text(self):
        self.assertEqual(_truncate_nul_text("YOUYOU TEC.\x00"), "YOUYOU TEC.")
        self.assertEqual(_truncate_nul_text("  YOUYOU TEC.\x00  "), "YOUYOU TEC.")
        self.assertEqual(_truncate_nul_text("YOUYOU\x00EVIL"), "YOUYOU")
        self.assertEqual(_truncate_nul_text("\x00EVIL"), "")
        self.assertEqual(_truncate_nul_text("YOU\x00YOU\x00TEC."), "YOU")

    def test_decode_sysfs_bytes(self):
        self.assertEqual(_decode_sysfs_bytes(b"YOUYOU TEC.\x00"), "YOUYOU TEC.")
        self.assertEqual(_decode_sysfs_bytes(b"YOUYOU\x00EVIL"), "YOUYOU")
        self.assertEqual(_decode_sysfs_bytes(b"YOU\x00YOU\x00TEC."), "YOU")
        self.assertEqual(_decode_sysfs_bytes(b"\x00EVIL"), "")
        self.assertEqual(_decode_sysfs_bytes(b"Vendor\xe2\x84\xa2\x00"), "Vendor™")
        self.assertIsNone(_decode_sysfs_bytes(b"Vendor\xff\xff\x00"))

    def test_decode_udev_encoded_text(self):
        self.assertEqual(_decode_udev_encoded_text(r"YOUYOU\x20TEC."), "YOUYOU TEC.")
        self.assertEqual(_decode_udev_encoded_text(r"YOUYOU\x20Keyb_V2"), "YOUYOU Keyb_V2")
        self.assertEqual(_decode_udev_encoded_text(r"Vendor\xe2\x84\xa2"), "Vendor™")
        self.assertEqual(_decode_udev_encoded_text(r"YOUYOU\x00EVIL"), "YOUYOU")
        self.assertIsNone(_decode_udev_encoded_text(r"YOUYOU\x2"))
        self.assertIsNone(_decode_udev_encoded_text(r"YOUYOU\xGG"))
        self.assertIsNone(_decode_udev_encoded_text(r"YOUYOU\qTEC"))
        self.assertIsNone(_decode_udev_encoded_text(r"YOUYOU\\"))


class TestUdevVidPidPriority(unittest.TestCase):
    def test_vid_pid_sysfs_priority(self):
        parent = FakePyudevDevice(None, "/sys/usb", {}, [], attributes={"idVendor": "239a\x00", "idProduct": b"80f4\x00"})
        dev = FakePyudevDevice("/dev/input/event0", "/sys/kb", {"NAME": '"Test Device"', "ID_VENDOR_ID": "bad", "ID_MODEL_ID": "bad"}, [], parent)
        with patch.dict(sys.modules, {"pyudev": FakePyudevModule([dev])}):
            backend = LinuxUdevDiscoveryBackend()
            records = backend.enumerate_input_records()
            self.assertEqual(records[0].properties["YYR4_NORMALIZED_VID"], "239a")
            self.assertEqual(records[0].properties["YYR4_NORMALIZED_PID"], "80f4")

    def test_vid_pid_fallback(self):
        parent = FakePyudevDevice(None, "/sys/usb", {}, [], attributes={})
        dev = FakePyudevDevice("/dev/input/event0", "/sys/kb", {"NAME": '"Test Device"', "ID_VENDOR_ID": "239a", "ID_MODEL_ID": "80f4"}, [], parent)
        with patch.dict(sys.modules, {"pyudev": FakePyudevModule([dev])}):
            backend = LinuxUdevDiscoveryBackend()
            records = backend.enumerate_input_records()
            self.assertEqual(records[0].properties["YYR4_NORMALIZED_VID"], "239a")
            self.assertEqual(records[0].properties["YYR4_NORMALIZED_PID"], "80f4")

from yyr4_linux_control.device.discovery import YYR4DeviceDiscovery

class TestFullLinuxBackendSixRecords(unittest.TestCase):
    def test_full_six_records(self):
        parent = FakePyudevDevice(None, "/sys/devices/pci0000:00/0000:00:14.0/usb1/1-1", {}, [], attributes={
            "idVendor": "239a", "idProduct": "80f4",
            "manufacturer": "YOUYOU TEC.", "product": "YOUYOU Keyb_V2"
        })

        devices = []
        # 1 valid kb
        kb_props = {"ID_BUS": "usb", "ID_USB_INTERFACE_NUM": "02", "ID_INPUT_KEYBOARD": "1", "NAME": '"Keyboard"'}
        kb_dev = FakePyudevDevice("/dev/input/event0", "/sys/kb", kb_props, ["/dev/input/by-id/kb-event-kbd"], parent)
        devices.append(kb_dev)

        # 1 valid ms
        ms_props = {"ID_BUS": "usb", "ID_USB_INTERFACE_NUM": "02", "ID_INPUT_MOUSE": "1", "NAME": '"Mouse"'}
        ms_dev = FakePyudevDevice("/dev/input/event1", "/sys/ms", ms_props, ["/dev/input/by-path/ms-event-mouse"], parent)
        devices.append(ms_dev)

        # 4 extra non-kb/ms records
        for i in range(4):
            ex_props = {"ID_BUS": "usb", "ID_USB_INTERFACE_NUM": "02", "ID_INPUT_KEYBOARD": "0", "ID_INPUT_MOUSE": "0"}
            ex_dev = FakePyudevDevice(f"/dev/input/event{2+i}", f"/sys/ex{i}", ex_props, [], parent)
            devices.append(ex_dev)

        with patch.dict(sys.modules, {"pyudev": FakePyudevModule(devices)}):
            backend = LinuxUdevDiscoveryBackend()
            records = backend.enumerate_input_records()
            self.assertEqual(len(records), 6) # Linux backend generated 6 records

            discovery = YYR4DeviceDiscovery(backend)
            identities = discovery.discover_all()

            self.assertEqual(len(identities), 1)
            self.assertEqual(identities[0].manufacturer, "YOUYOU TEC.")
            self.assertEqual(identities[0].product, "YOUYOU Keyb_V2")

            diag = discovery.snapshot_diagnostics()
            self.assertEqual(diag.enumerated_records, 6)
            self.assertEqual(diag.matched_records, 6)
            self.assertEqual(diag.complete_groups, 1)
            self.assertEqual(diag.ambiguous_groups, 0)

    def test_full_six_records_ambiguous_role(self):
        parent = FakePyudevDevice(None, "/sys/devices/pci0000:00/0000:00:14.0/usb1/1-1", {}, [], attributes={
            "idVendor": "239a", "idProduct": "80f4",
            "manufacturer": "YOUYOU TEC.", "product": "YOUYOU Keyb_V2"
        })

        devices = []
        # 2 valid kb
        kb_props = {"ID_BUS": "usb", "ID_USB_INTERFACE_NUM": "02", "ID_INPUT_KEYBOARD": "1", "NAME": '"Keyboard"'}
        kb_dev = FakePyudevDevice("/dev/input/event0", "/sys/kb", kb_props, [], parent)
        kb_dev2 = FakePyudevDevice("/dev/input/event1", "/sys/kb2", kb_props, [], parent)
        devices.append(kb_dev)
        devices.append(kb_dev2)

        # 1 valid ms
        ms_props = {"ID_BUS": "usb", "ID_USB_INTERFACE_NUM": "02", "ID_INPUT_MOUSE": "1", "NAME": '"Mouse"'}
        ms_dev = FakePyudevDevice("/dev/input/event2", "/sys/ms", ms_props, [], parent)
        devices.append(ms_dev)

        with patch.dict(sys.modules, {"pyudev": FakePyudevModule(devices)}):
            backend = LinuxUdevDiscoveryBackend()
            discovery = YYR4DeviceDiscovery(backend)
            identities = discovery.discover_all()

            self.assertEqual(len(identities), 0)
            diag = discovery.snapshot_diagnostics()
            self.assertEqual(diag.ambiguous_groups, 1)

    def test_full_six_records_mixed_reversed(self):
        # USB Parent with NO attributes to force fallback to device node properties
        parent = FakePyudevDevice(None, "/sys/devices/pci0000:00/0000:00:14.0/usb1/1-1", {}, [], attributes={})

        devices = []
        # Target keyboard: reversed raw mfg, safe prod
        kb_props = {
            "ID_BUS": "usb",
            "ID_USB_INTERFACE_NUM": "02",
            "ID_INPUT_KEYBOARD": "1",
            "NAME": '"Keyboard"',
            "ID_VENDOR_ID": "239a", "ID_MODEL_ID": "80f4",
            "ID_VENDOR": "YOUYOU Keyb_V2", "ID_MODEL": "YOUYOU_TEC."
        }
        kb_dev = FakePyudevDevice("/dev/input/event0", "/sys/kb", kb_props, ["/dev/input/by-id/kb-event-kbd"], parent)
        devices.append(kb_dev)

        # Target mouse: reversed safe mfg, raw prod
        ms_props = {
            "ID_BUS": "usb",
            "ID_USB_INTERFACE_NUM": "02",
            "ID_INPUT_MOUSE": "1",
            "NAME": '"Mouse"',
            "ID_VENDOR_ID": "239a", "ID_MODEL_ID": "80f4",
            "ID_VENDOR": "YOUYOU_Keyb_V2", "ID_MODEL": "YOUYOU TEC."
        }
        ms_dev = FakePyudevDevice("/dev/input/event1", "/sys/ms", ms_props, ["/dev/input/by-path/ms-event-mouse"], parent)
        devices.append(ms_dev)

        # 4 extra non-yyr4 records (different VID/PID or missing fields)
        for i in range(4):
            ex_props = {
                "ID_BUS": "usb",
                "ID_USB_INTERFACE_NUM": "02",
                "ID_INPUT_KEYBOARD": "0", "ID_INPUT_MOUSE": "0",
                "ID_VENDOR_ID": "9999", "ID_MODEL_ID": "9999"
            }
            ex_dev = FakePyudevDevice(f"/dev/input/event{2+i}", f"/sys/ex{i}", ex_props, [], parent)
            devices.append(ex_dev)

        with patch.dict(sys.modules, {"pyudev": FakePyudevModule(devices)}):
            backend = LinuxUdevDiscoveryBackend()
            records = backend.enumerate_input_records()
            self.assertEqual(len(records), 6) # Linux backend generated 6 records

            discovery = YYR4DeviceDiscovery(backend)
            identities = discovery.discover_all()

            self.assertEqual(len(identities), 1)
            self.assertEqual(identities[0].manufacturer, "YOUYOU TEC.")
            self.assertEqual(identities[0].product, "YOUYOU Keyb_V2")

            diag = discovery.snapshot_diagnostics()
            self.assertEqual(diag.enumerated_records, 6)
            self.assertEqual(diag.matched_records, 2)
            self.assertEqual(diag.complete_groups, 1)
            self.assertEqual(diag.ambiguous_groups, 0)

    def test_priority_mix_canonical(self):
        # 1. 原始manufacturer存在，原始product缺失，product来自ID_MODEL安全形式
        parent = FakePyudevDevice(None, "/sys/usb", {}, [], attributes={"manufacturer": "YOUYOU TEC.\x00"})
        dev = FakePyudevDevice("/dev/input/event0", "/sys/kb", {"NAME": '"Test Device"', "ID_MODEL": "YOUYOU_Keyb_V2"}, [], parent)
        with patch.dict(sys.modules, {"pyudev": FakePyudevModule([dev])}):
            backend = LinuxUdevDiscoveryBackend()
            records = backend.enumerate_input_records()
            self.assertEqual(records[0].properties["YYR4_NORMALIZED_MANUFACTURER"], "YOUYOU TEC.")
            self.assertEqual(records[0].properties["YYR4_NORMALIZED_PRODUCT"], "YOUYOU_Keyb_V2")

    def test_priority_mix_canonical_2(self):
        # 2. 原始manufacturer缺失，manufacturer来自ID_VENDOR安全形式，原始product存在
        parent = FakePyudevDevice(None, "/sys/usb", {}, [], attributes={"product": "YOUYOU Keyb_V2\x00"})
        dev = FakePyudevDevice("/dev/input/event0", "/sys/kb", {"NAME": '"Test Device"', "ID_VENDOR": "YOUYOU_TEC."}, [], parent)
        with patch.dict(sys.modules, {"pyudev": FakePyudevModule([dev])}):
            backend = LinuxUdevDiscoveryBackend()
            records = backend.enumerate_input_records()
            self.assertEqual(records[0].properties["YYR4_NORMALIZED_MANUFACTURER"], "YOUYOU_TEC.")
            self.assertEqual(records[0].properties["YYR4_NORMALIZED_PRODUCT"], "YOUYOU Keyb_V2")

    def test_priority_mix_reversed(self):
        # 3. 反向布局中manufacturer来自原始sysfs，product来自ID_MODEL安全形式
        parent = FakePyudevDevice(None, "/sys/usb", {}, [], attributes={"manufacturer": "YOUYOU Keyb_V2\x00"})
        dev = FakePyudevDevice("/dev/input/event0", "/sys/kb", {"NAME": '"Test Device"', "ID_MODEL": "YOUYOU_TEC."}, [], parent)
        with patch.dict(sys.modules, {"pyudev": FakePyudevModule([dev])}):
            backend = LinuxUdevDiscoveryBackend()
            records = backend.enumerate_input_records()
            self.assertEqual(records[0].properties["YYR4_NORMALIZED_MANUFACTURER"], "YOUYOU Keyb_V2")
            self.assertEqual(records[0].properties["YYR4_NORMALIZED_PRODUCT"], "YOUYOU_TEC.")

    def test_priority_mix_reversed_2(self):
        # 4. 反向布局中manufacturer来自ID_VENDOR安全形式，product来自原始sysfs
        parent = FakePyudevDevice(None, "/sys/usb", {}, [], attributes={"product": "YOUYOU TEC.\x00"})
        dev = FakePyudevDevice("/dev/input/event0", "/sys/kb", {"NAME": '"Test Device"', "ID_VENDOR": "YOUYOU_Keyb_V2"}, [], parent)
        with patch.dict(sys.modules, {"pyudev": FakePyudevModule([dev])}):
            backend = LinuxUdevDiscoveryBackend()
            records = backend.enumerate_input_records()
            self.assertEqual(records[0].properties["YYR4_NORMALIZED_MANUFACTURER"], "YOUYOU_Keyb_V2")
            self.assertEqual(records[0].properties["YYR4_NORMALIZED_PRODUCT"], "YOUYOU TEC.")

    def test_full_six_records_real_evidence_structure(self):
        # Fake pyudev Context -> LinuxUdevDiscoveryBackend -> UdevInputRecord -> YYR4DeviceDiscovery -> YYR4Identity
        # R1: ID_INPUT=1, ID_INPUT_KEY=1, ID_INPUT_KEYBOARD=1, ID_INPUT_MOUSE missing or not 1, device_name=""
        # R2: ID_INPUT=1, ID_INPUT_KEY missing or not 1, ID_INPUT_KEYBOARD missing or not 1, ID_INPUT_MOUSE=1, device_name=""

        # 1. 2 YYR4 targets
        kb_props = {
            "ID_BUS": "usb",
            "ID_VENDOR_ID": "239a",
            "ID_MODEL_ID": "80f4",
            "ID_VENDOR": "YOUYOU_TEC.",      # Safe manufacturer
            "ID_MODEL": "YOUYOU Keyb_V2",    # Raw product
            "ID_USB_INTERFACE_NUM": "02",
            "ID_INPUT": "1",
            "ID_INPUT_KEY": "1",
            "ID_INPUT_KEYBOARD": "1"
        }

        ms_props = {
            "ID_BUS": "usb",
            "ID_VENDOR_ID": "239a",
            "ID_MODEL_ID": "80f4",
            "ID_VENDOR": "YOUYOU_TEC.",      # Safe manufacturer
            "ID_MODEL": "YOUYOU Keyb_V2",    # Raw product
            "ID_USB_INTERFACE_NUM": "02",
            "ID_INPUT": "1",
            "ID_INPUT_MOUSE": "1"
        }

        # 2. 4 irrelevant targets
        irrelevant_records = []
        for i in range(4):
            ex_props = {
                "ID_BUS": "usb",
                "ID_VENDOR_ID": f"100{i}",
                "ID_MODEL_ID": f"200{i}",
                "ID_USB_INTERFACE_NUM": "01",
                "ID_INPUT": "1"
            }
            irrelevant_records.append({
                "sys_path": f"/sys/devices/fake/usb{i}/event{i+10}",
                "device_node": f"/dev/input/event{i+10}",
                "properties": ex_props,
                "parent": {
                    "sys_path": f"/sys/devices/fake/usb{i}",
                    "attributes": {
                        "idVendor": f"100{i}\n".encode(),
                        "idProduct": f"200{i}\n".encode(),
                        "manufacturer": b"FakeMfg\n",
                        "product": b"FakeProd\n"
                    }
                }
            })

        class FakeDevice:
            def __init__(self, spec):
                self.sys_path = spec["sys_path"]
                self.device_node = spec["device_node"]
                self.properties = spec["properties"]

                # Setup parent hierarchy
                self.parent = self
                parent_spec = spec.get("parent")
                if parent_spec:
                    class FakeParent:
                        def __init__(self, p_spec):
                            self.sys_path = p_spec["sys_path"]
                            self.attributes = p_spec["attributes"]
                        def find_parent(self, subsystem, devtype=None):
                            return None
                    self.parent_obj = FakeParent(parent_spec)
                else:
                    self.parent_obj = None

            @property
            def device_links(self):
                return iter([])

            def find_parent(self, subsystem, devtype=None):
                return self.parent_obj

        records_specs = [
            {
                "sys_path": "/sys/devices/fake/usb/event0",
                "device_node": "/dev/input/event0",
                "properties": kb_props,
                "parent": {
                    "sys_path": "/sys/devices/fake/usb",
                    "attributes": {
                        "idVendor": b"239a\n",
                        "idProduct": b"80f4\n",
                        "manufacturer": b"YOUYOU_TEC.\n",
                        "product": b"YOUYOU Keyb_V2\n"
                    }
                }
            },
            {
                "sys_path": "/sys/devices/fake/usb/event1",
                "device_node": "/dev/input/event1",
                "properties": ms_props,
                "parent": {
                    "sys_path": "/sys/devices/fake/usb",
                    "attributes": {
                        "idVendor": b"239a\n",
                        "idProduct": b"80f4\n",
                        "manufacturer": b"YOUYOU_TEC.\n",
                        "product": b"YOUYOU Keyb_V2\n"
                    }
                }
            }
        ] + irrelevant_records

        class FakeContext:
            def list_devices(self, subsystem=None, **kwargs):
                return [FakeDevice(spec) for spec in records_specs]

        backend = LinuxUdevDiscoveryBackend()
        backend._pyudev = type('FakePyudev', (), {'Context': FakeContext})

        discovery = YYR4DeviceDiscovery(backend)
        ident = discovery.select_single()

        self.assertEqual(ident.vendor_id, "239a")
        self.assertEqual(ident.product_id, "80f4")
        self.assertEqual(ident.manufacturer, "YOUYOU TEC.")
        self.assertEqual(ident.product, "YOUYOU Keyb_V2")

        self.assertIsNotNone(ident.keyboard)
        self.assertIsNotNone(ident.mouse)
        self.assertEqual(ident.usb_parent_syspath, "/sys/devices/fake/usb")
        self.assertEqual(ident.keyboard.usb_interface_number, "02")
        self.assertEqual(ident.mouse.usb_interface_number, "02")
        self.assertEqual(ident.keyboard.parent_usb_syspath, "/sys/devices/fake/usb")
        self.assertEqual(ident.mouse.parent_usb_syspath, "/sys/devices/fake/usb")

        diag = discovery.snapshot_diagnostics()
        self.assertEqual(diag.enumerated_records, 6)
        self.assertEqual(diag.matched_records, 2)
        self.assertEqual(diag.complete_groups, 1)
        self.assertEqual(diag.incomplete_groups, 0)
        self.assertEqual(diag.ambiguous_groups, 0)
        self.assertEqual(diag.rejected_vendor_product, 4)
        self.assertEqual(diag.rejected_interface, 0)
