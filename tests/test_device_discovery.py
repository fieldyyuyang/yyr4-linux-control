import unittest
from typing import Sequence
from yyr4_linux_control.device.discovery import YYR4DeviceDiscovery, DiscoveryBackend, UdevInputRecord
from yyr4_linux_control.device.errors import DeviceNotFoundError, DeviceAmbiguousError, DeviceIncompleteError

class FakeDiscoveryBackend(DiscoveryBackend):
    def __init__(self, records: Sequence[UdevInputRecord]):
        self.records = records

    def enumerate_input_records(self) -> Sequence[UdevInputRecord]:
        return self.records

class TestDeviceDiscovery(unittest.TestCase):
    def setUp(self):
        self.valid_kb = UdevInputRecord(
            device_node="/dev/input/event0",
            syspath="/sys/kb",
            parent_usb_syspath="/sys/usb",
            properties={
                "ID_BUS": "usb",
                "ID_VENDOR_ID": "239A",
                "ID_MODEL_ID": "80f4",
                "ID_VENDOR": "YOUYOU TEC.",
                "ID_MODEL": "YOUYOU Keyb_V2",
                "ID_USB_INTERFACE_NUM": "02",
                "ID_INPUT_KEYBOARD": "1"
            },
            devlinks=("/dev/input/by-id/kb-event-kbd", "/dev/input/by-path/kb"),
            device_name="YOUYOU Keyb_V2 Keyboard",
        )
        self.valid_ms = UdevInputRecord(
            device_node="/dev/input/event1",
            syspath="/sys/ms",
            parent_usb_syspath="/sys/usb",
            properties={
                "ID_BUS": "usb",
                "ID_VENDOR_ID": "239a",
                "ID_MODEL_ID": "80F4",
                "ID_VENDOR": "YOUYOU TEC.",
                "ID_MODEL": "YOUYOU Keyb_V2",
                "ID_USB_INTERFACE_NUM": "2", # should normalize
                "ID_INPUT_MOUSE": "1"
            },
            devlinks=("/dev/input/by-path/ms-event-mouse",),
            device_name="YOUYOU Keyb_V2 Mouse",
        )

    def test_discover_valid_single(self):
        backend = FakeDiscoveryBackend([self.valid_kb, self.valid_ms])
        discovery = YYR4DeviceDiscovery(backend)
        identities = discovery.discover_all()
        self.assertEqual(len(identities), 1)
        self.assertEqual(identities[0].keyboard.device_node, "/dev/input/event0")
        self.assertEqual(identities[0].keyboard.stable_path, "/dev/input/by-id/kb-event-kbd")
        self.assertEqual(identities[0].mouse.stable_path, "/dev/input/by-path/ms-event-mouse")

        diag = discovery.snapshot_diagnostics()
        self.assertEqual(diag.complete_groups, 1)

    def test_select_single(self):
        backend = FakeDiscoveryBackend([self.valid_kb, self.valid_ms])
        discovery = YYR4DeviceDiscovery(backend)
        identity = discovery.select_single()
        self.assertIsNotNone(identity)

    def test_select_single_not_found(self):
        backend = FakeDiscoveryBackend([])
        discovery = YYR4DeviceDiscovery(backend)
        with self.assertRaises(DeviceNotFoundError):
            discovery.select_single()

    def test_select_single_ambiguous(self):
        kb2 = UdevInputRecord(
            device_node="/dev/input/event2",
            syspath="/sys/kb2",
            parent_usb_syspath="/sys/usb2",
            properties=self.valid_kb.properties,
            devlinks=(),
            device_name="YOUYOU Keyb_V2 Keyboard",
        )
        ms2 = UdevInputRecord(
            device_node="/dev/input/event3",
            syspath="/sys/ms2",
            parent_usb_syspath="/sys/usb2",
            properties=self.valid_ms.properties,
            devlinks=(),
            device_name="YOUYOU Keyb_V2 Mouse",
        )
        backend = FakeDiscoveryBackend([self.valid_kb, self.valid_ms, kb2, ms2])
        discovery = YYR4DeviceDiscovery(backend)
        identities = discovery.discover_all()
        self.assertEqual(len(identities), 2)
        with self.assertRaises(DeviceAmbiguousError):
            discovery.select_single()

    def test_wrong_vid(self):
        props = dict(self.valid_kb.properties)
        props["ID_VENDOR_ID"] = "1111"
        kb = UdevInputRecord(self.valid_kb.device_node, self.valid_kb.syspath, self.valid_kb.parent_usb_syspath, props, (), self.valid_kb.device_name)
        backend = FakeDiscoveryBackend([kb, self.valid_ms])
        discovery = YYR4DeviceDiscovery(backend)
        self.assertEqual(len(discovery.discover_all()), 0)
        self.assertEqual(discovery.snapshot_diagnostics().rejected_vendor_product, 1)

    def test_wrong_pid(self):
        props = dict(self.valid_kb.properties)
        props["ID_MODEL_ID"] = "1111"
        kb = UdevInputRecord(self.valid_kb.device_node, self.valid_kb.syspath, self.valid_kb.parent_usb_syspath, props, (), self.valid_kb.device_name)
        backend = FakeDiscoveryBackend([kb, self.valid_ms])
        discovery = YYR4DeviceDiscovery(backend)
        self.assertEqual(len(discovery.discover_all()), 0)
        self.assertEqual(discovery.snapshot_diagnostics().rejected_vendor_product, 1)

    def test_wrong_manufacturer(self):
        props = dict(self.valid_kb.properties)
        props["ID_VENDOR"] = "Other"
        kb = UdevInputRecord(self.valid_kb.device_node, self.valid_kb.syspath, self.valid_kb.parent_usb_syspath, props, (), self.valid_kb.device_name)
        backend = FakeDiscoveryBackend([kb, self.valid_ms])
        discovery = YYR4DeviceDiscovery(backend)
        self.assertEqual(len(discovery.discover_all()), 0)

    def test_wrong_product(self):
        props = dict(self.valid_kb.properties)
        props["ID_MODEL"] = "Other"
        kb = UdevInputRecord(self.valid_kb.device_node, self.valid_kb.syspath, self.valid_kb.parent_usb_syspath, props, (), self.valid_kb.device_name)
        backend = FakeDiscoveryBackend([kb, self.valid_ms])
        discovery = YYR4DeviceDiscovery(backend)
        self.assertEqual(len(discovery.discover_all()), 0)

    def test_wrong_interface(self):
        props = dict(self.valid_kb.properties)
        props["ID_USB_INTERFACE_NUM"] = "03"
        kb = UdevInputRecord(self.valid_kb.device_node, self.valid_kb.syspath, self.valid_kb.parent_usb_syspath, props, (), self.valid_kb.device_name)
        backend = FakeDiscoveryBackend([kb, self.valid_ms])
        discovery = YYR4DeviceDiscovery(backend)
        self.assertEqual(len(discovery.discover_all()), 0)
        self.assertEqual(discovery.snapshot_diagnostics().rejected_interface, 1)

    def test_missing_keyboard(self):
        backend = FakeDiscoveryBackend([self.valid_ms])
        discovery = YYR4DeviceDiscovery(backend)
        self.assertEqual(len(discovery.discover_all()), 0)
        self.assertEqual(discovery.snapshot_diagnostics().incomplete_groups, 1)

    def test_missing_mouse(self):
        backend = FakeDiscoveryBackend([self.valid_kb])
        discovery = YYR4DeviceDiscovery(backend)
        self.assertEqual(len(discovery.discover_all()), 0)
        self.assertEqual(discovery.snapshot_diagnostics().incomplete_groups, 1)

    def test_duplicate_keyboard(self):
        kb2 = UdevInputRecord("/dev/input/event2", "/sys/kb2", "/sys/usb", self.valid_kb.properties, (), "YOUYOU Keyb_V2 Keyboard")
        backend = FakeDiscoveryBackend([self.valid_kb, kb2, self.valid_ms])
        discovery = YYR4DeviceDiscovery(backend)
        self.assertEqual(len(discovery.discover_all()), 0)
        self.assertEqual(discovery.snapshot_diagnostics().ambiguous_groups, 1)

    def test_duplicate_mouse(self):
        ms2 = UdevInputRecord("/dev/input/event2", "/sys/ms2", "/sys/usb", self.valid_ms.properties, (), "YOUYOU Keyb_V2 Mouse")
        backend = FakeDiscoveryBackend([self.valid_kb, self.valid_ms, ms2])
        discovery = YYR4DeviceDiscovery(backend)
        self.assertEqual(len(discovery.discover_all()), 0)
        self.assertEqual(discovery.snapshot_diagnostics().ambiguous_groups, 1)

    def test_same_node(self):
        ms2 = UdevInputRecord(self.valid_kb.device_node, "/sys/ms2", "/sys/usb", self.valid_ms.properties, (), "YOUYOU Keyb_V2 Mouse")
        backend = FakeDiscoveryBackend([self.valid_kb, ms2])
        discovery = YYR4DeviceDiscovery(backend)
        self.assertEqual(len(discovery.discover_all()), 0)
        self.assertEqual(discovery.snapshot_diagnostics().ambiguous_groups, 1)

    def test_non_yyr4_device_with_same_vid_pid_ignored(self):
        # A device with same VID PID but different manufacturer
        props = dict(self.valid_kb.properties)
        props["ID_VENDOR"] = "Not YOUYOU"
        dev = UdevInputRecord("/dev/input/event0", "/s", "/p", props, (), "X")
        backend = FakeDiscoveryBackend([dev])
        discovery = YYR4DeviceDiscovery(backend)
        self.assertEqual(len(discovery.discover_all()), 0)

    def test_incomplete_group_ambiguity(self):
        # One valid, one incomplete
        backend = FakeDiscoveryBackend([self.valid_kb, self.valid_ms, self.valid_kb])
        discovery = YYR4DeviceDiscovery(backend)
        with self.assertRaises(DeviceAmbiguousError):
            discovery.select_single()

    def test_incomplete_group_only(self):
        backend = FakeDiscoveryBackend([self.valid_kb])
        discovery = YYR4DeviceDiscovery(backend)
        with self.assertRaises(DeviceIncompleteError):
            discovery.select_single()

    def test_mfg_safe_space_match(self):
        props = dict(self.valid_kb.properties)
        props["YYR4_NORMALIZED_MANUFACTURER"] = "YOUYOU_TEC."
        kb = UdevInputRecord(self.valid_kb.device_node, self.valid_kb.syspath, self.valid_kb.parent_usb_syspath, props, (), self.valid_kb.device_name)
        backend = FakeDiscoveryBackend([kb, self.valid_ms])
        discovery = YYR4DeviceDiscovery(backend)
        self.assertEqual(len(discovery.discover_all()), 1)

    def test_product_safe_space_match(self):
        props = dict(self.valid_kb.properties)
        props["YYR4_NORMALIZED_PRODUCT"] = "YOUYOU_Keyb_V2"
        kb = UdevInputRecord(self.valid_kb.device_node, self.valid_kb.syspath, self.valid_kb.parent_usb_syspath, props, (), self.valid_kb.device_name)
        backend = FakeDiscoveryBackend([kb, self.valid_ms])
        discovery = YYR4DeviceDiscovery(backend)
        self.assertEqual(len(discovery.discover_all()), 1)

    def test_original_underscore_preserved(self):
        # We ensure it matches "YOUYOU Keyb_V2" exactly and doesn't reject it just because it has an underscore.
        # But wait, Keyb_V2 has an underscore in the canonical name.
        # So matching "YOUYOU Keyb_V2" implies the underscore is preserved.
        props = dict(self.valid_kb.properties)
        props["YYR4_NORMALIZED_PRODUCT"] = "YOUYOU Keyb_V2"
        kb = UdevInputRecord(self.valid_kb.device_node, self.valid_kb.syspath, self.valid_kb.parent_usb_syspath, props, (), self.valid_kb.device_name)
        backend = FakeDiscoveryBackend([kb, self.valid_ms])
        discovery = YYR4DeviceDiscovery(backend)
        identities = discovery.discover_all()
        self.assertEqual(len(identities), 1)
        self.assertEqual(identities[0].product, "YOUYOU Keyb_V2")
        self.assertEqual(identities[0].manufacturer, "YOUYOU TEC.")

    def test_case_variation_rejected(self):
        props = dict(self.valid_kb.properties)
        props["YYR4_NORMALIZED_MANUFACTURER"] = "youyou tec."
        kb = UdevInputRecord(self.valid_kb.device_node, self.valid_kb.syspath, self.valid_kb.parent_usb_syspath, props, (), self.valid_kb.device_name)
        backend = FakeDiscoveryBackend([kb, self.valid_ms])
        discovery = YYR4DeviceDiscovery(backend)
        self.assertEqual(len(discovery.discover_all()), 0)

    def test_missing_period_rejected(self):
        props = dict(self.valid_kb.properties)
        props["YYR4_NORMALIZED_MANUFACTURER"] = "YOUYOU TEC"
        kb = UdevInputRecord(self.valid_kb.device_node, self.valid_kb.syspath, self.valid_kb.parent_usb_syspath, props, (), self.valid_kb.device_name)
        backend = FakeDiscoveryBackend([kb, self.valid_ms])
        discovery = YYR4DeviceDiscovery(backend)
        self.assertEqual(len(discovery.discover_all()), 0)

    def test_double_underscore_rejected(self):
        props = dict(self.valid_kb.properties)
        props["YYR4_NORMALIZED_MANUFACTURER"] = "YOUYOU__TEC."
        kb = UdevInputRecord(self.valid_kb.device_node, self.valid_kb.syspath, self.valid_kb.parent_usb_syspath, props, (), self.valid_kb.device_name)
        backend = FakeDiscoveryBackend([kb, self.valid_ms])
        discovery = YYR4DeviceDiscovery(backend)
        self.assertEqual(len(discovery.discover_all()), 0)

    def test_wrong_product_version_rejected(self):
        props = dict(self.valid_kb.properties)
        props["YYR4_NORMALIZED_PRODUCT"] = "YOUYOU Keyb_V3"
        kb = UdevInputRecord(self.valid_kb.device_node, self.valid_kb.syspath, self.valid_kb.parent_usb_syspath, props, (), self.valid_kb.device_name)
        backend = FakeDiscoveryBackend([kb, self.valid_ms])
        discovery = YYR4DeviceDiscovery(backend)
        self.assertEqual(len(discovery.discover_all()), 0)

    def test_six_record_composite_scenario(self):
        # 1 valid kb, 1 valid ms, 4 extra HID interfaces
        records = [self.valid_kb, self.valid_ms]
        for i in range(4):
            props = dict(self.valid_kb.properties)
            props["ID_INPUT_KEYBOARD"] = "0"
            props["ID_INPUT_MOUSE"] = "0"
            rec = UdevInputRecord(
                f"/dev/input/event{2+i}", "/sys/extra", "/sys/usb",
                props, (), f"YOUYOU Keyb_V2 Extra {i}")
            records.append(rec)
        backend = FakeDiscoveryBackend(records)
        discovery = YYR4DeviceDiscovery(backend)
        identities = discovery.discover_all()
        self.assertEqual(len(identities), 1)
        self.assertEqual(discovery.snapshot_diagnostics().complete_groups, 1)
        self.assertEqual(discovery.snapshot_diagnostics().ambiguous_groups, 0)
        self.assertEqual(discovery.snapshot_diagnostics().matched_records, 6)

    def test_duplicate_keyboard_fails(self):
        kb2 = UdevInputRecord(
            "/dev/input/event99", "/sys/kb2", "/sys/usb",
            self.valid_kb.properties, (), "YOUYOU Keyb_V2 Keyboard")
        backend = FakeDiscoveryBackend([self.valid_kb, kb2, self.valid_ms])
        discovery = YYR4DeviceDiscovery(backend)
        with self.assertRaises(DeviceAmbiguousError):
            discovery.select_single()

    def test_duplicate_mouse_fails(self):
        ms2 = UdevInputRecord(
            "/dev/input/event99", "/sys/ms2", "/sys/usb",
            self.valid_ms.properties, (), "YOUYOU Keyb_V2 Mouse")
        backend = FakeDiscoveryBackend([self.valid_kb, self.valid_ms, ms2])
        discovery = YYR4DeviceDiscovery(backend)
        with self.assertRaises(DeviceAmbiguousError):
            discovery.select_single()

    def test_different_parent_fails(self):
        ms2 = UdevInputRecord(
            self.valid_ms.device_node, self.valid_ms.syspath, "/sys/usb2",
            self.valid_ms.properties, self.valid_ms.devlinks, self.valid_ms.device_name)
        backend = FakeDiscoveryBackend([self.valid_kb, ms2])
        discovery = YYR4DeviceDiscovery(backend)
        with self.assertRaises(DeviceIncompleteError):
            discovery.select_single()

    def test_multiple_complete_groups_fails(self):
        kb2 = UdevInputRecord(
            "/dev/input/event98", "/sys/kb2", "/sys/usb2",
            self.valid_kb.properties, (), "YOUYOU Keyb_V2 Keyboard")
        ms2 = UdevInputRecord(
            "/dev/input/event99", "/sys/ms2", "/sys/usb2",
            self.valid_ms.properties, (), "YOUYOU Keyb_V2 Mouse")
        backend = FakeDiscoveryBackend([self.valid_kb, self.valid_ms, kb2, ms2])
        discovery = YYR4DeviceDiscovery(backend)
        with self.assertRaises(DeviceAmbiguousError):
            discovery.select_single()

    def test_clone_exact_match_rejected(self):
        props = dict(self.valid_kb.properties)
        props["ID_VENDOR"] = 'FAKE YOUYOU Keyb_V2 CLONE'
        kb = UdevInputRecord(self.valid_kb.device_node, self.valid_kb.syspath, self.valid_kb.parent_usb_syspath, props, (), self.valid_kb.device_name)
        backend = FakeDiscoveryBackend([kb, self.valid_ms])
        discovery = YYR4DeviceDiscovery(backend)
        self.assertEqual(len(discovery.discover_all()), 0)

    def test_stable_path_fallback(self):
        kb = UdevInputRecord(
            device_node="/dev/input/event0",
            syspath="/sys/kb",
            parent_usb_syspath="/sys/usb",
            properties=self.valid_kb.properties,
            devlinks=("/dev/input/by-path/pci-0000-event",),
            device_name="YOUYOU Keyb_V2 Keyboard",
        )
        backend = FakeDiscoveryBackend([kb, self.valid_ms])
        discovery = YYR4DeviceDiscovery(backend)
        identities = discovery.discover_all()
        self.assertEqual(identities[0].keyboard.stable_path, "/dev/input/by-path/pci-0000-event")
