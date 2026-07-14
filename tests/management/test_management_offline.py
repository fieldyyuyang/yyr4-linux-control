import unittest
import json
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

from yyr4_linux_control.management.cli import (
    cmd_validate, cmd_list_controls, cmd_show_config, cmd_dry_run,
    EXIT_SUCCESS, EXIT_CONFIG, EXIT_ARGS
)

class DummyArgs:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)
        if not hasattr(self, 'json'):
            self.json = False

class TestManagementOffline(unittest.TestCase):
    def setUp(self):
        self.fd, self.temp_path = tempfile.mkstemp(suffix=".toml")
        with os.fdopen(self.fd, 'w') as f:
            f.write("""
schema_version = 1
[controls.A1.action]
type = "debug_log"
message = "Hello"
""")

    def tearDown(self):
        os.remove(self.temp_path)

    @patch('sys.exit')
    @patch('builtins.print')
    def test_validate_success(self, mock_print, mock_exit):
        args = DummyArgs(config=self.temp_path)
        cmd_validate(args)
        mock_exit.assert_called_with(EXIT_SUCCESS)

    @patch('sys.exit')
    @patch('builtins.print')
    def test_validate_syntax_error(self, mock_print, mock_exit):
        with open(self.temp_path, 'w') as f:
            f.write("schema_version = 'broken")
        args = DummyArgs(config=self.temp_path)
        cmd_validate(args)
        mock_exit.assert_called_with(EXIT_CONFIG)

    @patch('sys.exit')
    @patch('builtins.print')
    def test_validate_schema_error(self, mock_print, mock_exit):
        with open(self.temp_path, 'w') as f:
            f.write("schema_version = 999\n")
        args = DummyArgs(config=self.temp_path)
        cmd_validate(args)
        mock_exit.assert_called_with(EXIT_CONFIG)

    @patch('sys.exit')
    @patch('builtins.print')
    def test_list_controls(self, mock_print, mock_exit):
        args = DummyArgs(json=True)
        cmd_list_controls(args)
        
        # Capture the output
        output = mock_print.call_args[0][0]
        data = json.loads(output)
        
        self.assertEqual(len(data['controls']), 24)
        mock_exit.assert_called_with(EXIT_SUCCESS)

    @patch('sys.exit')
    @patch('builtins.print')
    def test_show_config_default_redacted(self, mock_print, mock_exit):
        with open(self.temp_path, 'w') as f:
            f.write("""
schema_version = 1
[controls.A1.action]
type = "macro"
steps = [
    {type = "text", value = "secret"},
    {type = "command", argv = ["/bin/ls", "-l"]}
]
""")
        args = DummyArgs(config=self.temp_path, show_sensitive=False, json=True)
        cmd_show_config(args)
        
        output = mock_print.call_args[0][0]
        data = json.loads(output)
        steps = data['profiles']['default']['general']['A1']['action']
        self.assertEqual(steps[0]['type'], 'TextAction')
        self.assertNotIn('value', steps[0])
        self.assertEqual(steps[0]['length'], 6)
        
        self.assertEqual(steps[1]['type'], 'CommandAction')
        self.assertNotIn('args', steps[1])
        self.assertEqual(steps[1]['basename'], 'ls')

        mock_exit.assert_called_with(EXIT_SUCCESS)

    @patch('sys.exit')
    @patch('builtins.print')
    def test_show_config_sensitive(self, mock_print, mock_exit):
        with open(self.temp_path, 'w') as f:
            f.write("""
schema_version = 1
[controls.BP.action]
type = "text"
value = "secret"
""")
        args = DummyArgs(config=self.temp_path, show_sensitive=True, json=True)
        cmd_show_config(args)
        
        output = mock_print.call_args[0][0]
        data = json.loads(output)
        steps = data['profiles']['default']['general']['BP']['action']
        self.assertEqual(steps[0]['text'], 'secret')

        mock_exit.assert_called_with(EXIT_SUCCESS)

    @patch('sys.exit')
    @patch('builtins.print')
    def test_dry_run_a1(self, mock_print, mock_exit):
        args = DummyArgs(config=self.temp_path, control="A1", json=True)
        cmd_dry_run(args)
        
        output = mock_print.call_args[0][0]
        data = json.loads(output)
        
        self.assertEqual(data['control'], "A1")
        self.assertEqual(data['resolution'], "CONFIGURED")
        self.assertEqual(data['execution']['status'], "SUCCESS")
        
        mock_exit.assert_called_with(EXIT_SUCCESS)

    @patch('sys.exit')
    @patch('builtins.print')
    def test_dry_run_unmapped(self, mock_print, mock_exit):
        args = DummyArgs(config=self.temp_path, control="A2", json=True)
        cmd_dry_run(args)
        
        output = mock_print.call_args[0][0]
        data = json.loads(output)
        
        self.assertEqual(data['resolution'], "UNMAPPED")
        mock_exit.assert_called_with(EXIT_SUCCESS)

    @patch('sys.exit')
    @patch('builtins.print')
    def test_dry_run_noop(self, mock_print, mock_exit):
        with open(self.temp_path, 'w') as f:
            f.write("""
schema_version = 1
[controls.A1.action]
type = "noop"
""")
        args = DummyArgs(config=self.temp_path, control="A1", json=True)
        cmd_dry_run(args)
        output = mock_print.call_args[0][0]
        data = json.loads(output)
        self.assertEqual(data['resolution'], "CONFIGURED")
        mock_exit.assert_called_with(EXIT_SUCCESS)

    @patch('sys.exit')
    @patch('yyr4_linux_control.management.cli.eprint')
    def test_dry_run_invalid_control(self, mock_eprint, mock_exit):
        args = DummyArgs(config=self.temp_path, control="K01", json=False)
        mock_exit.side_effect = SystemExit
        try:
            cmd_dry_run(args)
        except SystemExit:
            pass
        mock_exit.assert_called_with(EXIT_ARGS)
