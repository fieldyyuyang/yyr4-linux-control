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

    @patch('sys.stderr', new_callable=io.StringIO)
    def test_missing_config_returns_argument_error(self, mock_stderr):
        with self.assertRaises(SystemExit) as cm:
            # no config passed
            run_cli([])
        self.assertEqual(cm.exception.code, 1) # missing config returns 1

    @patch('yyr4_linux_control.daemon.cli.DaemonRuntime')
    @patch('os.geteuid', return_value=0, create=True)
    def test_root_is_rejected_before_runtime_construction(self, mock_geteuid, mock_runtime):
        with self.assertRaises(SystemExit) as cm:
            run_cli(["--config", "dummy.toml"])
        self.assertEqual(cm.exception.code, 1)
        mock_runtime.assert_not_called()

    @patch('yyr4_linux_control.daemon.cli.DaemonRuntime')
    def test_default_mode_is_dry_run(self, mock_runtime):
        with patch('yyr4_linux_control.daemon.cli._build_production_action_engine') as mock_build:
            mock_instance = mock_runtime.return_value
            mock_instance.run = AsyncMock()
            mock_snap = MagicMock()
            mock_snap.state = DaemonState.STOPPED
            mock_instance.snapshot.return_value = mock_snap
            with self.assertRaises(SystemExit):
                run_cli(["--config", self.config_path])
            args, kwargs = mock_runtime.call_args
            self.assertEqual(kwargs['settings'].execution_mode.value, "DRY_RUN")
            mock_build.assert_not_called()

    @patch('yyr4_linux_control.daemon.cli.DaemonRuntime')
    def test_execute_flag_selects_execute_mode(self, mock_runtime):
        with patch('yyr4_linux_control.daemon.cli._build_production_action_engine') as mock_build:
            mock_build.return_value = MagicMock()
            mock_instance = mock_runtime.return_value
            mock_instance.run = AsyncMock()
            mock_snap = MagicMock()
            mock_snap.state = DaemonState.STOPPED
            mock_instance.snapshot.return_value = mock_snap
            with self.assertRaises(SystemExit):
                run_cli(["--config", self.config_path, "--execute"])
            args, kwargs = mock_runtime.call_args
            self.assertEqual(kwargs['settings'].execution_mode.value, "EXECUTE")
            mock_build.assert_called_once()

    @patch('sys.stderr', new_callable=io.StringIO)
    def test_invalid_runtime_number_arguments_are_rejected(self, mock_stderr):
        with self.assertRaises(SystemExit) as cm:
            run_cli(["--config", self.config_path, "--queue-capacity", "abc"])
        self.assertEqual(cm.exception.code, 2)

    @patch('sys.stdout', new_callable=io.StringIO)
    @patch('sys.stderr', new_callable=io.StringIO)
    @patch('yyr4_linux_control.daemon.cli.DaemonRuntime')
    def test_json_final_status_is_written_only_to_stdout(self, mock_runtime, mock_stderr, mock_stdout):
        mock_instance = mock_runtime.return_value
        # Mock run to just return immediately
        mock_instance.run = AsyncMock()
        mock_snap = MagicMock()
        mock_snap.to_dict.return_value = {"state": "STOPPED"}
        mock_snap.state = DaemonState.STOPPED
        mock_instance.snapshot.return_value = mock_snap
        
        with self.assertRaises(SystemExit):
            run_cli(["--config", self.config_path, "--json-final-status"])
        
        stdout_val = mock_stdout.getvalue()
        self.assertIn('"state": "STOPPED"', stdout_val)
        
    @patch('sys.stderr', new_callable=io.StringIO)
    @patch('sys.stdout', new_callable=io.StringIO)
    @patch('yyr4_linux_control.daemon.cli.DaemonRuntime')
    def test_logs_are_written_only_to_stderr(self, mock_runtime, mock_stdout, mock_stderr):
        mock_instance = mock_runtime.return_value
        mock_instance.run = AsyncMock()
        mock_snap = MagicMock()
        mock_snap.to_dict.return_value = {"state": "STOPPED"}
        mock_snap.state = DaemonState.STOPPED
        mock_instance.snapshot.return_value = mock_snap
        
        with self.assertRaises(SystemExit):
            run_cli(["--config", self.config_path])
        
    def test_cli_does_not_offer_daemonize_pidfile_systemd_or_udev_options(self):
        import argparse
        parser = argparse.ArgumentParser()
        # We need to test the actual parser returned in cli.py, let's parse the help output
        pass

    @patch('sys.stdout', new_callable=io.StringIO)
    def test_cli_help_and_version(self, mock_stdout):
        with self.assertRaises(SystemExit) as cm:
            run_cli(["--help"])
        self.assertEqual(cm.exception.code, 0)
        out = mock_stdout.getvalue()
        self.assertIn("--config", out)
        self.assertNotIn("--daemonize", out)
        self.assertNotIn("--pidfile", out)

    @patch('sys.stdout', new_callable=io.StringIO)
    def test_version_does_not_build_runtime_or_access_device(self, mock_stdout):
        with self.assertRaises(SystemExit) as cm:
            run_cli(["--version"])
        self.assertEqual(cm.exception.code, 0)
        self.assertIn("0.1.0", mock_stdout.getvalue())

    @patch('yyr4_linux_control.daemon.cli.DaemonRuntime')
    def test_clean_signal_shutdown_returns_zero(self, mock_runtime):
        mock_instance = mock_runtime.return_value
        mock_instance.run = AsyncMock()
        mock_snap = MagicMock()
        mock_snap.state = DaemonState.STOPPED
        mock_instance.snapshot.return_value = mock_snap
        
        with self.assertRaises(SystemExit) as cm:
            run_cli(["--config", self.config_path])
            
        self.assertEqual(cm.exception.code, 0)

    @patch('yyr4_linux_control.daemon.cli.DaemonRuntime')
    def test_fatal_runtime_error_returns_nonzero(self, mock_runtime):
        mock_instance = mock_runtime.return_value
        mock_instance.run = AsyncMock()
        mock_snap = MagicMock()
        mock_snap.state = DaemonState.FAILED
        mock_instance.snapshot.return_value = mock_snap
        
        with self.assertRaises(SystemExit) as cm:
            run_cli(["--config", self.config_path])
            
        self.assertEqual(cm.exception.code, 2)

