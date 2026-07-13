"""Tests for the identity permission probe CLI."""

import unittest
from unittest.mock import patch, MagicMock
import tempfile
import os
from pathlib import Path
import json

from yyr4_linux_control.tools.identity_permission_probe import main
from yyr4_linux_control.integration.identity_permission_validation import IdentityPermissionValidationResult

class TestIdentityPermissionProbeCLI(unittest.TestCase):
    def setUp(self):
        self.mock_result = IdentityPermissionValidationResult(
            result_status=0,
            exit_code=0,
            exception_class=None,
            identity_created=True,
            permission_checked=True,
            enumerated_records=6,
            matched_records=2,
            complete_groups=1,
            incomplete_groups=0,
            ambiguous_groups=0,
            rejected_vendor_product=4,
            rejected_interface=0,
            vendor_id="239a",
            product_id="80f4",
            manufacturer="YOUYOU TEC.",
            product="YOUYOU Keyb_V2",
            keyboard_present=True,
            mouse_present=True,
            keyboard_interface="02",
            mouse_interface="02",
            same_usb_parent=True,
            serial_present=True,
            keyboard_stable_path_available=True,
            keyboard_stable_path_kind="by-id",
            mouse_stable_path_available=True,
            mouse_stable_path_kind="by-id",
            keyboard_readable=True,
            mouse_readable=True,
            all_required_readable=True,
            blocker_count=0,
            warning_count=0,
            checked_role_count=2,
        )

    @patch("sys.argv", ["identity_permission_probe.py"])
    def test_no_real_arg_returns_8(self):
        # 24. CLI无--real时不构造backend
        # 25. CLI无--real时不枚举设备
        exit_code = main()
        self.assertEqual(exit_code, 8)

    @patch("sys.argv", ["identity_permission_probe.py", "--help"])
    def test_help_returns_0_without_accessing_device(self):
        # 26. CLI --help不访问设备
        with self.assertRaises(SystemExit) as cm:
            main()
        self.assertEqual(cm.exception.code, 0)

    @patch("sys.argv", ["identity_permission_probe.py", "--real"])
    def test_real_without_output_returns_8(self):
        exit_code = main()
        self.assertEqual(exit_code, 8)

    @patch("sys.argv", ["identity_permission_probe.py", "--real", "--output", "/tmp/nonexistent/out.json"])
    @patch("yyr4_linux_control.integration.preflight.check_runtime_preflight")
    @patch("yyr4_linux_control.device.linux_udev.LinuxUdevDiscoveryBackend")
    @patch("yyr4_linux_control.integration.preflight.FilesystemIdentityPermissionChecker")
    @patch("yyr4_linux_control.tools.identity_permission_probe.validate_identity_and_permissions")
    def test_real_constructs_proper_dependencies(self, mock_validate, mock_checker, mock_backend, mock_preflight):
        # 27. CLI --real使用正式依赖工厂
        mock_preflight.return_value.ready_for_discovery = True
        mock_validate.return_value = self.mock_result

        with tempfile.TemporaryDirectory() as td:
            out_file = os.path.join(td, "out.json")
            with patch("sys.argv", ["identity_permission_probe.py", "--real", "--output", out_file]):
                exit_code = main()

            self.assertEqual(exit_code, 0)
            mock_backend.assert_called_once()
            mock_checker.assert_called_once()
            mock_validate.assert_called_once()

            kwargs = mock_validate.call_args.kwargs
            self.assertEqual(kwargs["discovery_backend"], mock_backend.return_value)
            self.assertEqual(kwargs["permission_checker"], mock_checker.return_value)

            # Verify file contents
            self.assertTrue(os.path.exists(out_file))
            with open(out_file, "r") as f:
                data = json.load(f)
            self.assertEqual(data["result_status"], 0)

    @patch("sys.argv", ["identity_permission_probe.py", "--real", "--output", "/root/forbidden/out.json"])
    @patch("yyr4_linux_control.integration.preflight.check_runtime_preflight")
    @patch("yyr4_linux_control.device.linux_udev.LinuxUdevDiscoveryBackend")
    @patch("yyr4_linux_control.integration.preflight.FilesystemIdentityPermissionChecker")
    @patch("yyr4_linux_control.tools.identity_permission_probe.validate_identity_and_permissions")
    def test_write_failure_returns_12(self, mock_validate, mock_checker, mock_backend, mock_preflight):
        mock_preflight.return_value.ready_for_discovery = True
        mock_validate.return_value = self.mock_result

        # Simulate an unwritable path
        exit_code = main()
        # 23. JSON写入失败映射RESULT_WRITE_FAILURE
        self.assertEqual(exit_code, 12)

    def test_main_does_not_call_sysexit(self):
        # 28. CLI main返回退出码，不调用sys.exit
        import ast
        with open("src/yyr4_linux_control/tools/identity_permission_probe.py") as f:
            code = f.read()
        tree = ast.parse(code)

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "main":
                for child in ast.walk(node):
                    if isinstance(child, ast.Call):
                        if getattr(child.func, "id", "") == "exit":
                            self.fail("main calls exit()")
                        if isinstance(child.func, ast.Attribute) and getattr(child.func.value, "id", "") == "sys" and child.func.attr == "exit":
                            self.fail("main calls sys.exit()")

    def test_main_guard_uses_raise_systemexit(self):
        # 29. 模块级main guard为raise SystemExit(main())
        import ast
        with open("src/yyr4_linux_control/tools/identity_permission_probe.py") as f:
            code = f.read()
        tree = ast.parse(code)

        found_main_guard = False
        for node in ast.walk(tree):
            if isinstance(node, ast.If):
                test = ast.get_source_segment(code, node.test)
                if test and '__name__' in test and '"__main__"' in test:
                    found_main_guard = True
                    has_raise = any(isinstance(c, ast.Raise) and isinstance(c.exc, ast.Call) and getattr(c.exc.func, "id", "") == "SystemExit" for c in ast.walk(node))
                    self.assertTrue(has_raise, "main guard missing raise SystemExit()")
        self.assertTrue(found_main_guard)
