import unittest
import os
import shutil
from typing import Tuple, Optional
from unittest.mock import patch, MagicMock

from yyr4_linux_control.execution.desktop import UnavailableDesktopInputBackend, XDoToolDesktopInputBackend
from yyr4_linux_control.execution.errors import DesktopInputError
from yyr4_linux_control.execution.interfaces import CommandRunner

class FakeCommandRunner(CommandRunner):
    def __init__(self, exit_code: int = 0):
        self.exit_code = exit_code
        self.calls = []

    async def run(self, argv: Tuple[str, ...], timeout_seconds: Optional[int]) -> Tuple[int, bytes, bytes]:
        self.calls.append(argv)
        return self.exit_code, b"", b"error" if self.exit_code != 0 else b""

class TestExecutionDesktop(unittest.IsolatedAsyncioTestCase):
    def test_unavailable_backend(self):
        backend = UnavailableDesktopInputBackend()
        self.assertFalse(backend.availability())

    @patch("shutil.which")
    @patch.dict(os.environ, {"DISPLAY": ":0"}, clear=True)
    def test_xdotool_available(self, mock_which):
        mock_which.return_value = "/usr/bin/xdotool"
        backend = XDoToolDesktopInputBackend(FakeCommandRunner())
        self.assertTrue(backend.availability())

    @patch("shutil.which")
    @patch.dict(os.environ, {}, clear=True)
    def test_xdotool_unavailable_no_display(self, mock_which):
        mock_which.return_value = "/usr/bin/xdotool"
        backend = XDoToolDesktopInputBackend(FakeCommandRunner())
        self.assertFalse(backend.availability())

    @patch("shutil.which")
    @patch.dict(os.environ, {"DISPLAY": ":0", "XDG_SESSION_TYPE": "wayland"}, clear=True)
    def test_xdotool_unavailable_wayland(self, mock_which):
        mock_which.return_value = "/usr/bin/xdotool"
        backend = XDoToolDesktopInputBackend(FakeCommandRunner())
        self.assertFalse(backend.availability())

    @patch.object(XDoToolDesktopInputBackend, "availability", return_value=True)
    async def test_send_hotkey(self, mock_avail):
        runner = FakeCommandRunner()
        backend = XDoToolDesktopInputBackend(runner)
        await backend.send_hotkey(("CTRL", "C"))
        self.assertEqual(len(runner.calls), 1)
        self.assertEqual(runner.calls[0], ("xdotool", "key", "--clearmodifiers", "ctrl+c"))

    @patch.object(XDoToolDesktopInputBackend, "availability", return_value=True)
    async def test_type_text(self, mock_avail):
        runner = FakeCommandRunner()
        backend = XDoToolDesktopInputBackend(runner)
        await backend.type_text("hello")
        self.assertEqual(len(runner.calls), 1)
        self.assertEqual(runner.calls[0], ("xdotool", "type", "--clearmodifiers", "--delay", "0", "--", "hello"))

    @patch.object(XDoToolDesktopInputBackend, "availability", return_value=True)
    async def test_send_hotkey_failure(self, mock_avail):
        runner = FakeCommandRunner(exit_code=1)
        backend = XDoToolDesktopInputBackend(runner)
        with self.assertRaisesRegex(DesktopInputError, "xdotool returned non-zero exit code 1: error"):
            await backend.send_hotkey(("CTRL", "C"))
