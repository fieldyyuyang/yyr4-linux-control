import unittest
from unittest.mock import patch, MagicMock, AsyncMock
import asyncio
import os
import tempfile
import sys
import io

from yyr4_linux_control.daemon.cli import _main_async, main
from yyr4_linux_control.daemon.models import DaemonState

def run_cli(args):
    with patch("sys.argv", ["yyr4d"] + args):
        main()

class FakeArgs:
    config = "valid.toml"
    execution_mode = "DRY_RUN"
    control_socket = None
    queue_capacity = 128
    reconnect_initial = 1.0
    reconnect_max = 60.0
    reconnect_multiplier = 2.0
    shutdown_grace = 5.0
    json_final_status = False
    log_level = "INFO"

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
        args = FakeArgs()
        args.config = self.config_path
        exit_code = await _main_async(args)
        self.assertEqual(exit_code, 1)

    @patch("yyr4_linux_control.daemon.cli.os.geteuid", return_value=1000)
    async def test_missing_config_rejected(self, mock_geteuid):
        args = FakeArgs()
        args.config = ""
        exit_code = await _main_async(args)
        self.assertEqual(exit_code, 1)

    @patch('yyr4_linux_control.daemon.cli.ManagementServer')
    @patch('yyr4_linux_control.daemon.cli.NativeSignalController')
    @patch('yyr4_linux_control.daemon.cli.DaemonRuntime')
    @patch('yyr4_linux_control.daemon.cli.Path')
    def test_default_mode_is_dry_run(self, mock_path_cls, mock_runtime_cls, mock_signals, mock_server):
        mock_path_cls.return_value.is_file.return_value = True
        
        mock_runtime = MagicMock()
        mock_runtime.run = AsyncMock()
        mock_runtime.snapshot.return_value = MagicMock()
        mock_runtime_cls.return_value = mock_runtime
        
        mock_server_inst = MagicMock()
        mock_server_inst.start = AsyncMock()
        mock_server_inst.stop = AsyncMock()
        mock_server.return_value = mock_server_inst
        
        args = FakeArgs()
        args.execution_mode = "DRY_RUN"
        exit_code = asyncio.run(_main_async(args))
        
        self.assertEqual(exit_code, 0)
        args, kwargs = mock_runtime_cls.call_args
        self.assertEqual(kwargs['settings'].execution_mode.value, "DRY_RUN")

    @patch('yyr4_linux_control.daemon.cli.ManagementServer')
    @patch('yyr4_linux_control.daemon.cli.NativeSignalController')
    @patch('yyr4_linux_control.daemon.cli.DaemonRuntime')
    @patch('yyr4_linux_control.daemon.cli.Path')
    def test_execute_flag_selects_execute_mode(self, mock_path_cls, mock_runtime_cls, mock_signals, mock_server):
        mock_path_cls.return_value.is_file.return_value = True
        
        mock_runtime = MagicMock()
        mock_runtime.run = AsyncMock()
        mock_runtime.snapshot.return_value = MagicMock()
        mock_runtime_cls.return_value = mock_runtime
        
        mock_server_inst = MagicMock()
        mock_server_inst.start = AsyncMock()
        mock_server_inst.stop = AsyncMock()
        mock_server.return_value = mock_server_inst
        
        args = FakeArgs()
        args.execution_mode = "EXECUTE"
        exit_code = asyncio.run(_main_async(args))
        
        self.assertEqual(exit_code, 0)
        args, kwargs = mock_runtime_cls.call_args
        self.assertEqual(kwargs['settings'].execution_mode.value, "EXECUTE")

    @patch('sys.stderr', new_callable=io.StringIO)
    def test_missing_config_returns_argument_error(self, mock_stderr):
        with self.assertRaises(SystemExit) as cm:
            run_cli([])
        self.assertEqual(cm.exception.code, 1)

    @patch('yyr4_linux_control.daemon.cli.DaemonRuntime')
    @patch('yyr4_linux_control.daemon.cli.ManagementServer')
    @patch('os.geteuid', return_value=0, create=True)
    def test_root_is_rejected_before_runtime_construction(self, mock_geteuid, mock_server, mock_runtime):
        with self.assertRaises(SystemExit) as cm:
            run_cli(["--config", "dummy.toml"])
        self.assertEqual(cm.exception.code, 1)
        mock_runtime.assert_not_called()

    @patch('sys.stderr', new_callable=io.StringIO)
    def test_invalid_runtime_number_arguments_are_rejected(self, mock_stderr):
        with self.assertRaises(SystemExit) as cm:
            run_cli(["--config", self.config_path, "--queue-capacity", "abc"])
        self.assertEqual(cm.exception.code, 2)

    @patch('sys.stdout', new_callable=io.StringIO)
    @patch('sys.stderr', new_callable=io.StringIO)
    @patch('yyr4_linux_control.daemon.cli.DaemonRuntime')
    @patch('yyr4_linux_control.daemon.cli.ManagementServer')
    def test_json_final_status_is_written_only_to_stdout(self, mock_server, mock_runtime, mock_stderr, mock_stdout):
        mock_instance = mock_runtime.return_value
        mock_instance.run = AsyncMock()
        mock_snap = MagicMock()
        mock_snap.to_dict.return_value = {"state": "STOPPED"}
        mock_instance.snapshot.return_value = mock_snap
        
        mock_server_inst = mock_server.return_value
        mock_server_inst.start = AsyncMock()
        mock_server_inst.stop = AsyncMock()

        with self.assertRaises(SystemExit) as cm:
            run_cli(["--config", self.config_path, "--json-final-status"])

        self.assertEqual(cm.exception.code, 0)
        self.assertIn('"state": "STOPPED"', mock_stdout.getvalue())

    @patch('sys.stdout', new_callable=io.StringIO)
    @patch('sys.stderr', new_callable=io.StringIO)
    @patch('yyr4_linux_control.daemon.cli.DaemonRuntime')
    @patch('yyr4_linux_control.daemon.cli.ManagementServer')
    def test_logs_are_written_only_to_stderr(self, mock_server, mock_runtime, mock_stderr, mock_stdout):
        mock_instance = mock_runtime.return_value
        mock_instance.run = AsyncMock()
        mock_snap = MagicMock()
        mock_snap.to_dict.return_value = {"state": "STOPPED"}
        mock_instance.snapshot.return_value = mock_snap

        mock_server_inst = mock_server.return_value
        mock_server_inst.start = AsyncMock()
        mock_server_inst.stop = AsyncMock()

        with self.assertRaises(SystemExit) as cm:
            run_cli(["--config", self.config_path])
            
        self.assertEqual(cm.exception.code, 0)
        self.assertEqual(mock_stdout.getvalue(), "")

    @patch('sys.stderr', new_callable=io.StringIO)
    def test_cli_help_and_version(self, mock_stderr):
        with self.assertRaises(SystemExit) as cm:
            run_cli(["--help"])
        self.assertEqual(cm.exception.code, 0)

        with self.assertRaises(SystemExit) as cm:
            run_cli(["--version"])
        self.assertEqual(cm.exception.code, 0)

    @patch('sys.stderr', new_callable=io.StringIO)
    def test_cli_does_not_offer_daemonize_pidfile_systemd_or_udev_options(self, mock_stderr):
        with self.assertRaises(SystemExit) as cm:
            run_cli(["--daemonize"])
        self.assertEqual(cm.exception.code, 2)
        
        with self.assertRaises(SystemExit) as cm:
            run_cli(["--pidfile", "pid"])
        self.assertEqual(cm.exception.code, 2)

        with self.assertRaises(SystemExit) as cm:
            run_cli(["--systemd"])
        self.assertEqual(cm.exception.code, 2)
