import unittest
from unittest.mock import patch, MagicMock, AsyncMock
import asyncio
import os
import tempfile
import sys

from yyr4_linux_control.daemon.cli import _main_async
from yyr4_linux_control.daemon.models import DaemonState

class FakeArgs:
    def __init__(self, **kwargs):
        self.config = kwargs.get("config", "")
        self.execute = kwargs.get("execute", False)
        self.queue_capacity = kwargs.get("queue_capacity", 128)
        self.reconnect_initial = kwargs.get("reconnect_initial", 1.0)
        self.reconnect_max = kwargs.get("reconnect_max", 60.0)
        self.reconnect_multiplier = kwargs.get("reconnect_multiplier", 2.0)
        self.shutdown_grace = kwargs.get("shutdown_grace", 5.0)
        self.log_level = kwargs.get("log_level", "INFO")
        self.json_final_status = kwargs.get("json_final_status", False)

class TestDaemonCli(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.fd, self.config_path = tempfile.mkstemp()
        with open(self.config_path, "w") as f:
            f.write("""
schema_version = 1
[controls.A1.action]
type = "text"
value = "cli"
""")

    def tearDown(self):
        os.close(self.fd)
        os.remove(self.config_path)

    @patch("yyr4_linux_control.daemon.cli.os.geteuid", return_value=0)
    async def test_root_rejected(self, mock_geteuid):
        args = FakeArgs(config=self.config_path)
        exit_code = await _main_async(args)
        self.assertEqual(exit_code, 1)

    @patch("yyr4_linux_control.daemon.cli.os.geteuid", return_value=1000)
    async def test_missing_config_rejected(self, mock_geteuid):
        args = FakeArgs(config="")
        exit_code = await _main_async(args)
        self.assertEqual(exit_code, 1)

    @patch("yyr4_linux_control.daemon.cli.os.geteuid", return_value=1000)
    @patch("yyr4_linux_control.daemon.cli.DaemonRuntime")
    @patch("yyr4_linux_control.daemon.cli.NativeSignalController")
    async def test_successful_run(self, mock_sig, mock_runtime_cls, mock_geteuid):
        # mock runtime
        mock_runtime = MagicMock()
        mock_runtime.run = AsyncMock()
        
        # mock snapshot to be STOPPED
        snap_mock = MagicMock()
        snap_mock.state = DaemonState.STOPPED
        snap_mock.to_dict.return_value = {"state": "STOPPED"}
        mock_runtime.snapshot.return_value = snap_mock
        
        mock_runtime_cls.return_value = mock_runtime
        
        args = FakeArgs(config=self.config_path, json_final_status=True)
        exit_code = await _main_async(args)
        
        self.assertEqual(exit_code, 0)
        mock_runtime_cls.assert_called_once()
        # Verify it ran
        mock_runtime.run.assert_called_once()
