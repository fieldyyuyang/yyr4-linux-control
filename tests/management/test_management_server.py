import unittest
import asyncio
import tempfile
import os
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

from yyr4_linux_control.daemon.runtime import DaemonRuntime
from yyr4_linux_control.daemon.models import RuntimeSettings, ExecutionMode
from yyr4_linux_control.management.server import ManagementServer
from yyr4_linux_control.management.client import ManagementClient

class FakeSessionFactory:
    pass

class FakeExecutor:
    pass

class TestManagementServer(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.sock_path = Path(self.temp_dir) / "yyr4d.sock"
        
        self.settings = RuntimeSettings(
            config_path="dummy.toml",
            execution_mode=ExecutionMode.DRY_RUN
        )
        
        self.runtime = MagicMock()
        self.server = ManagementServer(self.runtime, self.sock_path)
        self.client = ManagementClient(self.sock_path)

    async def asyncSetUp(self):
        await self.server.start()

    async def asyncTearDown(self):
        await self.server.stop()
        for root, dirs, files in os.walk(self.temp_dir, topdown=False):
            for name in files:
                os.remove(os.path.join(root, name))
            for name in dirs:
                os.rmdir(os.path.join(root, name))
        os.rmdir(self.temp_dir)

    @patch('yyr4_linux_control.management.server.check_peer_uid')
    async def test_ping(self, mock_check):
        mock_check.return_value = True
        resp = await self.client.send_request("ping")
        self.assertTrue(resp.ok)
        self.assertEqual(resp.result["pong"], True)

    @patch('yyr4_linux_control.management.server.check_peer_uid')
    async def test_status(self, mock_check):
        mock_check.return_value = True
        
        snap = MagicMock()
        snap.to_dict.return_value = {"state": "RUNNING"}
        self.runtime.snapshot.return_value = snap
        
        resp = await self.client.send_request("status")
        self.assertTrue(resp.ok)
        self.assertEqual(resp.result["state"], "RUNNING")

    @patch('yyr4_linux_control.management.server.check_peer_uid')
    async def test_reload_success(self, mock_check):
        mock_check.return_value = True
        
        async def mock_reload():
            return {"success": True, "config_revision": 2, "reload_successes": 1}
        self.runtime.request_reload_and_wait.side_effect = mock_reload
        
        resp = await self.client.send_request("reload")
        self.assertTrue(resp.ok)
        self.assertEqual(resp.result["config_revision"], 2)

    @patch('yyr4_linux_control.management.server.check_peer_uid')
    async def test_reload_failure(self, mock_check):
        mock_check.return_value = True
        
        async def mock_reload():
            return {"success": False, "error_code": "RELOAD_FAILED", "config_revision": 1}
        self.runtime.request_reload_and_wait.side_effect = mock_reload
        
        resp = await self.client.send_request("reload")
        self.assertFalse(resp.ok)
        self.assertEqual(resp.error["code"], "RELOAD_FAILED")

    @patch('yyr4_linux_control.management.server.check_peer_uid')
    async def test_peer_uid_mismatch(self, mock_check):
        mock_check.return_value = False
        
        import socket
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(2.0)
        s.connect(str(self.sock_path))
        s.sendall(b'{"protocol_version": 1, "request_id": "1", "command": "ping", "params": {}}\n')
        # Expect empty response because connection is closed
        with self.assertRaises(Exception):
            data = s.recv(1024)
            if not data:
                raise EOFError("Connection closed")
        s.close()
