import unittest
import os
import stat
import tempfile
import asyncio
from pathlib import Path
from unittest.mock import patch, MagicMock

from yyr4_linux_control.management.socket_path import setup_server_socket, get_default_socket_path
from yyr4_linux_control.management.errors import SocketError

class TestManagementSocket(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.sock_path = Path(self.temp_dir) / "yyr4d.sock"

    def tearDown(self):
        for root, dirs, files in os.walk(self.temp_dir, topdown=False):
            for name in files:
                os.remove(os.path.join(root, name))
            for name in dirs:
                os.rmdir(os.path.join(root, name))
        os.rmdir(self.temp_dir)

    @patch.dict(os.environ, {"XDG_RUNTIME_DIR": "/tmp/xdg"})
    def test_default_path(self):
        p = get_default_socket_path()
        self.assertEqual(str(p), "/tmp/xdg/yyr4/yyr4d.sock")

    @patch.dict(os.environ, clear=True)
    def test_default_path_missing(self):
        with self.assertRaises(SocketError):
            get_default_socket_path()

    async def test_setup_server_socket_creates_parent(self):
        await setup_server_socket(self.sock_path)
        self.assertTrue(self.sock_path.parent.exists())
        self.assertEqual(stat.S_IMODE(self.sock_path.parent.stat().st_mode), 0o700)

    async def test_setup_server_socket_regular_file(self):
        self.sock_path.parent.mkdir(parents=True, exist_ok=True)
        self.sock_path.write_text("not a socket")
        with self.assertRaises(SocketError):
            await setup_server_socket(self.sock_path)

    async def test_setup_server_socket_directory(self):
        self.sock_path.mkdir(parents=True, exist_ok=True)
        with self.assertRaises(SocketError):
            await setup_server_socket(self.sock_path)

    async def test_setup_server_socket_dead_socket(self):
        # Create a real socket to simulate dead daemon
        import socket
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.bind(str(self.sock_path))
        s.close() # Dead socket
        
        await setup_server_socket(self.sock_path)
        self.assertFalse(self.sock_path.exists()) # Should be removed

    @patch('yyr4_linux_control.management.socket_path.os.geteuid')
    async def test_setup_server_socket_dead_socket_wrong_owner(self, mock_euid):
        mock_euid.return_value = 9999 # Simulated wrong UID
        import socket
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.bind(str(self.sock_path))
        s.close()
        
        with self.assertRaises(SocketError):
            await setup_server_socket(self.sock_path)
