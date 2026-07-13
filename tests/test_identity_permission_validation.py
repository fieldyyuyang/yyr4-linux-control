"""Tests for Identity and Permission validation service."""

import unittest
from typing import Sequence, Optional, List
from unittest.mock import MagicMock, patch

from yyr4_linux_control.device.discovery import (
    DiscoveryBackend,
    UdevInputRecord,
    DiscoveryDiagnostics,
    YYR4Identity,
)
from yyr4_linux_control.device.errors import (
    DeviceNotFoundError,
    DeviceAmbiguousError,
    DeviceIncompleteError,
)
from yyr4_linux_control.integration.preflight import (
    IdentityPermissionChecker,
    PermissionCheck,
)
from yyr4_linux_control.integration.identity_permission_validation import (
    validate_identity_and_permissions,
    IdentityPermissionValidationResult,
)
from yyr4_linux_control.device.identity import InputInterface, InterfaceRole

class FakePermissionChecker(IdentityPermissionChecker):
    def __init__(self, kbd_read=True, ms_read=True):
        self.check_calls = 0
        self.kbd_read = kbd_read
        self.ms_read = ms_read

    def check(self, identity: YYR4Identity) -> PermissionCheck:
        self.check_calls += 1
        return PermissionCheck(
            keyboard_readable=self.kbd_read,
            mouse_readable=self.ms_read,
            all_required_readable=self.kbd_read and self.ms_read,
            blockers=tuple(["blocker1"]) if not (self.kbd_read and self.ms_read) else tuple(),
            warnings=tuple(),
        )

class FakeBackend(DiscoveryBackend):
    def __init__(self, records: Sequence[UdevInputRecord]):
        self.enumerate_calls = 0
        self._records = records

    def enumerate_input_records(self) -> Sequence[UdevInputRecord]:
        self.enumerate_calls += 1
        return self._records

class TestIdentityPermissionValidation(unittest.TestCase):
    def _create_six_records(self) -> List[UdevInputRecord]:
        # 2 matching, 4 non-matching
        records = []
        # Non-matching 1
        records.append(UdevInputRecord("/dev/input/event0", "/sys/p1", "/sys/usb1", {"ID_BUS": "usb", "ID_VENDOR_ID": "1234", "ID_MODEL_ID": "5678"}, (), ""))
        # Non-matching 2
        records.append(UdevInputRecord("/dev/input/event1", "/sys/p2", "/sys/usb1", {"ID_BUS": "usb", "ID_VENDOR_ID": "1234", "ID_MODEL_ID": "5678"}, (), ""))
        # Non-matching 3
        records.append(UdevInputRecord("/dev/input/event2", "/sys/p3", "/sys/usb1", {"ID_BUS": "usb", "ID_VENDOR_ID": "1234", "ID_MODEL_ID": "5678"}, (), ""))
        # Non-matching 4
        records.append(UdevInputRecord("/dev/input/event3", "/sys/p4", "/sys/usb1", {"ID_BUS": "usb", "ID_VENDOR_ID": "1234", "ID_MODEL_ID": "5678"}, (), ""))

        # Matching Keyboard
        records.append(UdevInputRecord(
            "/dev/input/event4", "/sys/p5", "/sys/usb_yyr4",
            {"ID_BUS": "usb", "ID_VENDOR_ID": "239a", "ID_MODEL_ID": "80f4", "ID_VENDOR": "YOUYOU Keyb_V2", "ID_MODEL": "YOUYOU TEC.", "ID_USB_INTERFACE_NUM": "02", "ID_INPUT_KEYBOARD": "1", "ID_SERIAL_SHORT": "S123"},
            ("/dev/input/by-id/usb-YOUYOU-event-kbd",),
            ""
        ))
        # Matching Mouse
        records.append(UdevInputRecord(
            "/dev/input/event5", "/sys/p6", "/sys/usb_yyr4",
            {"ID_BUS": "usb", "ID_VENDOR_ID": "239a", "ID_MODEL_ID": "80f4", "ID_VENDOR": "YOUYOU Keyb_V2", "ID_MODEL": "YOUYOU TEC.", "ID_USB_INTERFACE_NUM": "02", "ID_INPUT_MOUSE": "1"},
            ("/dev/input/by-id/usb-YOUYOU-event-mouse",),
            ""
        ))
        return records

    def test_six_records_fake_structure(self):
        backend = FakeBackend(self._create_six_records())
        checker = FakePermissionChecker()

        res = validate_identity_and_permissions(discovery_backend=backend, permission_checker=checker)

        # 1. 六记录Fake结构形成唯一Identity
        self.assertTrue(res.identity_created)

        # 2. backend只调用一次
        self.assertEqual(backend.enumerate_calls, 1)

        # 3. selector实际使用正式YYR4DeviceDiscovery (Implicitly tested by correct diagnostics output)
        self.assertEqual(res.enumerated_records, 6)
        self.assertEqual(res.matched_records, 2)
        self.assertEqual(res.rejected_vendor_product, 4)

        # 4. Identity成功后permission checker调用一次
        self.assertEqual(checker.check_calls, 1)

        # 6. 两个节点都可读时状态READY
        self.assertEqual(res.result_status, 0)

        # 14. canonical Identity字段正确
        self.assertEqual(res.vendor_id, "239a")
        self.assertEqual(res.product_id, "80f4")
        self.assertEqual(res.manufacturer, "YOUYOU TEC.")
        self.assertEqual(res.product, "YOUYOU Keyb_V2")

        # 15. keyboard和mouse interface均为02
        self.assertEqual(res.keyboard_interface, "02")
        self.assertEqual(res.mouse_interface, "02")

        # 16. same_usb_parent为True
        self.assertTrue(res.same_usb_parent)

        # Check stable path desensitization
        self.assertEqual(res.keyboard_stable_path_kind, "by-id")
        self.assertEqual(res.mouse_stable_path_kind, "by-id")

        # No sensitive fields
        self.assertFalse(hasattr(res, "device_node"))
        self.assertFalse(hasattr(res, "syspath"))
        self.assertFalse(hasattr(res, "serial"))

    def test_permission_blocked_keyboard(self):
        backend = FakeBackend(self._create_six_records())
        checker = FakePermissionChecker(kbd_read=False, ms_read=True)
        res = validate_identity_and_permissions(discovery_backend=backend, permission_checker=checker)
        self.assertEqual(res.result_status, 5) # PERMISSION_BLOCKED
        self.assertFalse(res.all_required_readable)

    def test_permission_blocked_mouse(self):
        backend = FakeBackend(self._create_six_records())
        checker = FakePermissionChecker(kbd_read=True, ms_read=False)
        res = validate_identity_and_permissions(discovery_backend=backend, permission_checker=checker)
        self.assertEqual(res.result_status, 5) # PERMISSION_BLOCKED
        self.assertFalse(res.all_required_readable)

    def test_permission_blocked_both(self):
        backend = FakeBackend(self._create_six_records())
        checker = FakePermissionChecker(kbd_read=False, ms_read=False)
        res = validate_identity_and_permissions(discovery_backend=backend, permission_checker=checker)
        self.assertEqual(res.result_status, 5) # PERMISSION_BLOCKED
        self.assertFalse(res.all_required_readable)

    def test_identity_fails_checker_not_called(self):
        backend = FakeBackend([])
        checker = FakePermissionChecker()
        res = validate_identity_and_permissions(discovery_backend=backend, permission_checker=checker)

        # 5. Identity失败时permission checker调用零次
        self.assertEqual(checker.check_calls, 0)
        self.assertFalse(res.identity_created)

        # 10. DeviceNotFoundError映射正确
        self.assertEqual(res.result_status, 4)

    def test_incomplete_error_mapping(self):
        recs = self._create_six_records()
        recs.pop() # Remove mouse
        backend = FakeBackend(recs)
        checker = FakePermissionChecker()
        res = validate_identity_and_permissions(discovery_backend=backend, permission_checker=checker)

        # 11. DeviceIncompleteError映射正确
        self.assertEqual(res.result_status, 6)
        self.assertEqual(res.exception_class, "DeviceIncompleteError")

    def test_ambiguous_error_mapping(self):
        recs = self._create_six_records()
        # Add another keyboard
        recs.append(UdevInputRecord(
            "/dev/input/event6", "/sys/p7", "/sys/usb_yyr4",
            {"ID_BUS": "usb", "ID_VENDOR_ID": "239a", "ID_MODEL_ID": "80f4", "ID_VENDOR": "YOUYOU Keyb_V2", "ID_MODEL": "YOUYOU TEC.", "ID_USB_INTERFACE_NUM": "02", "ID_INPUT_KEYBOARD": "1"},
            (),
            ""
        ))
        backend = FakeBackend(recs)
        checker = FakePermissionChecker()
        res = validate_identity_and_permissions(discovery_backend=backend, permission_checker=checker)

        # 12. DeviceAmbiguousError映射正确
        self.assertEqual(res.result_status, 6)
        self.assertEqual(res.exception_class, "DeviceAmbiguousError")

    def test_unexpected_error_no_raw_message(self):
        class ThrowingBackend(DiscoveryBackend):
            def enumerate_input_records(self) -> Sequence[UdevInputRecord]:
                raise ValueError("Secret message 12345")

        backend = ThrowingBackend()
        checker = FakePermissionChecker()
        res = validate_identity_and_permissions(discovery_backend=backend, permission_checker=checker)

        # 13. 未预期异常不输出异常正文
        self.assertEqual(res.result_status, 9)
        self.assertEqual(res.exception_class, "ValueError")
        self.assertFalse(hasattr(res, "error_message"))

    def test_json_desensitization(self):
        # Additional checks for 17-21
        backend = FakeBackend(self._create_six_records())
        checker = FakePermissionChecker(kbd_read=False, ms_read=True)
        res = validate_identity_and_permissions(discovery_backend=backend, permission_checker=checker)

        import json
        import dataclasses
        d = dataclasses.asdict(res)
        s = json.dumps(d)

        # Ensure no sensitive paths
        self.assertNotIn("/dev/input", s)
        self.assertNotIn("/sys", s)
        self.assertNotIn("S123", s)
        self.assertNotIn("event4", s)

        # Ensure block/warning are just counts
        self.assertEqual(res.blocker_count, 1)
        self.assertEqual(res.warning_count, 0)
        self.assertNotIn("blocker1", s)
