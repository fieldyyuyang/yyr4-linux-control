import unittest
import json
import tempfile
import os
from unittest.mock import patch

from yyr4_linux_control.management.cli import cmd_validate, cmd_dry_run, EXIT_SUCCESS, EXIT_ARGS

class DummyArgs:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)
        if not hasattr(self, 'json'):
            self.json = False

class TestLayeredManagementCli(unittest.TestCase):
    def setUp(self):
        self.fd, self.temp_path = tempfile.mkstemp(suffix=".toml")
        with os.fdopen(self.fd, 'w') as f:
            f.write("""
schema_version = 2
default_profile = "prod"
initial_layer = "general"

[profiles.prod.layers.general.controls.A1]
action = { type = "noop" }

[profiles.prod.layers.layer_1.controls.A1]
action = { type = "text", value = "hello" }
""")

    def tearDown(self):
        os.remove(self.temp_path)

    @patch('sys.exit')
    @patch('builtins.print')
    def test_validate_v2(self, mock_print, mock_exit):
        args = DummyArgs(config=self.temp_path, json=True)
        cmd_validate(args)
        
        output = mock_print.call_args[0][0]
        data = json.loads(output)
        
        self.assertEqual(data['schema_version'], 2)
        self.assertEqual(data['profile_count'], 1)
        self.assertEqual(data['layer_count'], 2)
        self.assertEqual(data['default_profile'], "prod")
        self.assertEqual(data['initial_layer'], "general")
        self.assertEqual(data['configured_control_count'], 2)
        
        mock_exit.assert_called_with(EXIT_SUCCESS)

    @patch('sys.exit')
    @patch('builtins.print')
    def test_dry_run_v2_default(self, mock_print, mock_exit):
        args = DummyArgs(config=self.temp_path, control="A1", json=True)
        cmd_dry_run(args)
        
        output = mock_print.call_args[0][0]
        data = json.loads(output)
        
        self.assertEqual(data['profile'], "prod")
        self.assertEqual(data['layer'], "general")
        self.assertEqual(data['mapping_source'], "active_layer")
        
        mock_exit.assert_called_with(EXIT_SUCCESS)

    @patch('sys.exit')
    @patch('builtins.print')
    def test_dry_run_v2_explicit_layer(self, mock_print, mock_exit):
        args = DummyArgs(config=self.temp_path, control="A1", layer="layer_1", json=True)
        cmd_dry_run(args)
        
        output = mock_print.call_args[0][0]
        data = json.loads(output)
        
        self.assertEqual(data['profile'], "prod")
        self.assertEqual(data['layer'], "layer_1")
        self.assertEqual(data['mapping_source'], "active_layer")
        
        mock_exit.assert_called_with(EXIT_SUCCESS)

    @patch('sys.exit')
    @patch('yyr4_linux_control.management.cli.eprint')
    def test_dry_run_v2_invalid_profile(self, mock_eprint, mock_exit):
        args = DummyArgs(config=self.temp_path, control="A1", profile="unknown", json=False)
        mock_exit.side_effect = SystemExit
        try:
            cmd_dry_run(args)
        except SystemExit:
            pass
        mock_exit.assert_called_with(3)  # EXIT_CONFIG

    @patch('sys.exit')
    @patch('yyr4_linux_control.management.cli.eprint')
    def test_dry_run_v2_invalid_layer(self, mock_eprint, mock_exit):
        args = DummyArgs(config=self.temp_path, control="A1", layer="layer_9", json=False)
        mock_exit.side_effect = SystemExit
        try:
            cmd_dry_run(args)
        except SystemExit:
            pass
        mock_exit.assert_called_with(EXIT_ARGS)
