"""Tests for integration preflight and permission checks."""

from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import patch, MagicMock

from yyr4_linux_control.device.identity import YYR4Identity
from yyr4_linux_control.integration.preflight import (
    check_runtime_preflight,
    FilesystemIdentityPermissionChecker,
    RuntimePreflight,
)

class TestIntegrationPreflight(unittest.TestCase):

    @patch("sys.version_info", (3, 8))
    def test_python_version_blocker(self):
        pre = check_runtime_preflight()
        self.assertFalse(pre.python_supported)
        self.assertIn("Python 3.9+ is required", pre.blockers)
        self.assertFalse(pre.ready_for_discovery)

    @patch("sys.platform", "darwin")
    def test_platform_blocker(self):
        pre = check_runtime_preflight()
        self.assertFalse(pre.platform_supported)
        self.assertIn("Only Linux is supported by the yyr4_linux_control backend", pre.blockers)
        self.assertFalse(pre.ready_for_discovery)

    @patch("os.geteuid", return_value=0, create=True)
    def test_root_blocker(self, *args):
        pre = check_runtime_preflight()
        self.assertTrue(pre.is_root)
        self.assertIn("Running as root is forbidden for safety and security reasons", pre.blockers)
        self.assertFalse(pre.ready_for_discovery)

    @patch("importlib.util.find_spec")
    def test_missing_evdev(self, mock_find_spec):
        def _find_spec(name):
            if name == "evdev":
                return None
            return MagicMock()
        mock_find_spec.side_effect = _find_spec
        pre = check_runtime_preflight()
        self.assertFalse(pre.evdev.available)
        self.assertIn("evdev package is missing", pre.blockers)
        self.assertFalse(pre.ready_for_discovery)

    @patch("importlib.util.find_spec")
    def test_missing_pyudev(self, mock_find_spec):
        def _find_spec(name):
            if name == "pyudev":
                return None
            return MagicMock()
        mock_find_spec.side_effect = _find_spec
        pre = check_runtime_preflight()
        self.assertFalse(pre.pyudev.available)
        self.assertIn("pyudev package is missing", pre.blockers)
        self.assertFalse(pre.ready_for_discovery)

    @patch("sys.version_info", (3, 9))
    @patch("sys.platform", "linux")
    @patch("os.geteuid", return_value=1000, create=True)
    @patch("importlib.util.find_spec", return_value=MagicMock())
    def test_ready_for_discovery(self, *args):
        pre = check_runtime_preflight()
        self.assertTrue(pre.python_supported)
        self.assertTrue(pre.platform_supported)
        self.assertFalse(pre.is_root)
        self.assertTrue(pre.evdev.available)
        self.assertTrue(pre.pyudev.available)
        self.assertTrue(pre.ready_for_discovery)
        self.assertEqual(len(pre.blockers), 0)

    def test_blockers_and_warnings_immutable(self):
        pre = check_runtime_preflight()
        self.assertIsInstance(pre.blockers, tuple)
        self.assertIsInstance(pre.warnings, tuple)


class TestIntegrationPermissions(unittest.TestCase):
    
    def setUp(self):
        self.checker = FilesystemIdentityPermissionChecker()
        self.identity = MagicMock(spec=YYR4Identity)
        self.identity.keyboard = MagicMock()
        self.identity.keyboard.device_node = "/mock/kbd"
        self.identity.mouse = MagicMock()
        self.identity.mouse.device_node = "/mock/mouse"

    @patch("os.access")
    def test_all_readable(self, mock_access):
        mock_access.return_value = True
        res = self.checker.check(self.identity)
        self.assertTrue(res.keyboard_readable)
        self.assertTrue(res.mouse_readable)
        self.assertTrue(res.all_required_readable)
        self.assertEqual(len(res.blockers), 0)

    @patch("os.access")
    def test_keyboard_not_readable(self, mock_access):
        def _access(path, mode):
            return path == "/mock/mouse"
        mock_access.side_effect = _access
        res = self.checker.check(self.identity)
        self.assertFalse(res.keyboard_readable)
        self.assertTrue(res.mouse_readable)
        self.assertFalse(res.all_required_readable)
        self.assertIn("keyboard device node is not readable by the current user", res.blockers)
        # Should NOT contain full path
        for b in res.blockers:
            self.assertNotIn("/mock", b)

    @patch("os.access")
    def test_mouse_not_readable(self, mock_access):
        def _access(path, mode):
            return path == "/mock/kbd"
        mock_access.side_effect = _access
        res = self.checker.check(self.identity)
        self.assertTrue(res.keyboard_readable)
        self.assertFalse(res.mouse_readable)
        self.assertFalse(res.all_required_readable)
        self.assertIn("mouse device node is not readable by the current user", res.blockers)

    @patch("os.access")
    def test_neither_readable(self, mock_access):
        mock_access.return_value = False
        res = self.checker.check(self.identity)
        self.assertFalse(res.keyboard_readable)
        self.assertFalse(res.mouse_readable)
        self.assertFalse(res.all_required_readable)
        self.assertEqual(len(res.blockers), 2)
        
    def test_missing_nodes(self):
        ident = MagicMock(spec=YYR4Identity)
        ident.keyboard = None
        ident.mouse = None
        res = self.checker.check(ident)
        self.assertFalse(res.keyboard_readable)
        self.assertFalse(res.mouse_readable)
        self.assertFalse(res.all_required_readable)
        self.assertIn("keyboard device node is missing from identity", res.blockers)
        self.assertIn("mouse device node is missing from identity", res.blockers)

    @patch("os.access")
    def test_only_checks_identity_nodes(self, mock_access):
        mock_access.return_value = True
        self.checker.check(self.identity)
        # Verify it didn't glob or read dir
        self.assertEqual(mock_access.call_count, 2)
        args = [c[0][0] for c in mock_access.call_args_list]
        self.assertIn("/mock/kbd", args)
        self.assertIn("/mock/mouse", args)
