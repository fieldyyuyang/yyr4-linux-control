"""Tests for the observe_probe CLI tool."""

from __future__ import annotations

import json
import sys
import unittest
from unittest.mock import patch, MagicMock

from yyr4_linux_control.tools.observe_probe import (
    main,
    EXIT_OK,
    EXIT_ARGS,
    EXIT_PREFLIGHT,
    EXIT_PERMISSION,
    EXIT_DISCOVERY,
    EXIT_OBSERVATION,
    EXIT_TIMEOUT,
)


class TestObserveProbeTool(unittest.TestCase):

    @patch("sys.argv", ["observe_probe.py"])
    @patch("sys.stderr.write")
    def test_no_args_shows_help(self, mock_stderr):
        self.assertEqual(main(), EXIT_ARGS)

    @patch("sys.argv", ["observe_probe.py", "--preflight"])
    @patch("sys.stdout.write")
    @patch("yyr4_linux_control.tools.observe_probe.check_runtime_preflight")
    def test_preflight_only(self, mock_check, mock_stdout):
        preflight_mock = MagicMock()
        preflight_mock.ready_for_discovery = True
        mock_check.return_value = preflight_mock
        
        self.assertEqual(main(), EXIT_OK)

    @patch("sys.argv", ["observe_probe.py", "--preflight", "--json"])
    @patch("builtins.print")
    @patch("yyr4_linux_control.tools.observe_probe.check_runtime_preflight")
    def test_preflight_json(self, mock_check, mock_print):
        preflight_mock = MagicMock()
        preflight_mock.python_supported = True
        preflight_mock.platform_supported = True
        preflight_mock.is_root = False
        preflight_mock.evdev.available = True
        preflight_mock.pyudev.available = True
        preflight_mock.ready_for_discovery = True
        preflight_mock.blockers = []
        preflight_mock.warnings = []
        mock_check.return_value = preflight_mock
        
        self.assertEqual(main(), EXIT_OK)
        
        output = mock_print.call_args[0][0]
        data = json.loads(output)
        self.assertTrue(data["ready_for_discovery"])

    @patch("sys.argv", ["observe_probe.py", "--max-events", "10"])
    @patch("sys.stderr.write")
    def test_missing_auth_rejects(self, mock_stderr):
        # Even if we pass other args, without auth it should fail
        with self.assertRaises(SystemExit) as ctx:
            main()
        self.assertEqual(ctx.exception.code, EXIT_ARGS)

    @patch("sys.argv", [
        "observe_probe.py",
        "--acknowledge-read-only-device-access",
        "--acknowledge-no-actions"
    ])
    @patch("sys.stderr.write")
    def test_missing_profile_auth_rejects(self, mock_stderr):
        with self.assertRaises(SystemExit) as ctx:
            main()
        self.assertEqual(ctx.exception.code, EXIT_ARGS)

    @patch("sys.argv", [
        "observe_probe.py",
        "--acknowledge-read-only-device-access",
        "--acknowledge-transport-profile-active",
        "--acknowledge-daily-profile-positive-control",
        "--acknowledge-no-actions"
    ])
    @patch("sys.stderr.write")
    def test_both_profile_auths_rejects(self, mock_stderr):
        with self.assertRaises(SystemExit) as ctx:
            main()
        self.assertEqual(ctx.exception.code, EXIT_ARGS)

    @patch("sys.argv", [
        "observe_probe.py",
        "--acknowledge-read-only-device-access",
        "--acknowledge-transport-profile-active",
        "--acknowledge-no-actions"
    ])
    @patch("sys.stderr.write")
    @patch("yyr4_linux_control.tools.observe_probe.check_runtime_preflight")
    def test_preflight_fails_after_auth(self, mock_check, mock_stderr):
        preflight_mock = MagicMock()
        preflight_mock.ready_for_discovery = False
        mock_check.return_value = preflight_mock
        
        with self.assertRaises(SystemExit) as ctx:
            main()
        self.assertEqual(ctx.exception.code, EXIT_PREFLIGHT)

    @patch("sys.argv", [
        "observe_probe.py",
        "--acknowledge-read-only-device-access",
        "--acknowledge-transport-profile-active",
        "--acknowledge-no-actions"
    ])
    @patch("yyr4_linux_control.tools.observe_probe.check_runtime_preflight")
    @patch("yyr4_linux_control.tools.observe_probe.build_linux_observation_pipeline")
    @patch("sys.stderr.write")
    def test_dependency_error(self, mock_stderr, mock_build, mock_check):
        preflight_mock = MagicMock()
        preflight_mock.ready_for_discovery = True
        mock_check.return_value = preflight_mock
        
        from yyr4_linux_control.integration.errors import IntegrationDependencyError
        mock_build.side_effect = IntegrationDependencyError("Missing dep")
        
        with self.assertRaises(SystemExit) as ctx:
            main()
        self.assertEqual(ctx.exception.code, EXIT_PREFLIGHT)

    @patch("sys.argv", [
        "observe_probe.py",
        "--acknowledge-read-only-device-access",
        "--acknowledge-transport-profile-active",
        "--acknowledge-no-actions"
    ])
    @patch("yyr4_linux_control.tools.observe_probe.check_runtime_preflight")
    @patch("yyr4_linux_control.tools.observe_probe.build_linux_observation_pipeline")
    @patch("sys.stderr.write")
    def test_discovery_error(self, mock_stderr, mock_build, mock_check):
        preflight_mock = MagicMock()
        preflight_mock.ready_for_discovery = True
        mock_check.return_value = preflight_mock
        
        comp_mock = MagicMock()
        from yyr4_linux_control.observation.errors import ObservationError
        comp_mock.selector.select_single.side_effect = ObservationError("Not found")
        mock_build.return_value = comp_mock
        
        with self.assertRaises(SystemExit) as ctx:
            main()
        self.assertEqual(ctx.exception.code, EXIT_DISCOVERY)

    @patch("sys.argv", [
        "observe_probe.py",
        "--acknowledge-read-only-device-access",
        "--acknowledge-transport-profile-active",
        "--acknowledge-no-actions"
    ])
    @patch("yyr4_linux_control.tools.observe_probe.check_runtime_preflight")
    @patch("yyr4_linux_control.tools.observe_probe.build_linux_observation_pipeline")
    @patch("yyr4_linux_control.tools.observe_probe.FilesystemIdentityPermissionChecker")
    @patch("sys.stderr.write")
    def test_permission_error(self, mock_stderr, mock_checker_class, mock_build, mock_check):
        preflight_mock = MagicMock()
        preflight_mock.ready_for_discovery = True
        mock_check.return_value = preflight_mock
        
        comp_mock = MagicMock()
        mock_build.return_value = comp_mock
        
        checker_mock = MagicMock()
        perm_check = MagicMock()
        perm_check.all_required_readable = False
        perm_check.blockers = ["blocker1"]
        checker_mock.check.return_value = perm_check
        mock_checker_class.return_value = checker_mock
        
        with self.assertRaises(SystemExit) as ctx:
            main()
        self.assertEqual(ctx.exception.code, EXIT_PERMISSION)

    @patch("sys.argv", [
        "observe_probe.py",
        "--acknowledge-read-only-device-access",
        "--acknowledge-transport-profile-active",
        "--acknowledge-no-actions",
        "--json"
    ])
    @patch("yyr4_linux_control.tools.observe_probe.check_runtime_preflight")
    @patch("yyr4_linux_control.tools.observe_probe.build_linux_observation_pipeline")
    @patch("yyr4_linux_control.tools.observe_probe.FilesystemIdentityPermissionChecker")
    @patch("yyr4_linux_control.tools.observe_probe.ProbeRunner")
    @patch("builtins.print")
    def test_observation_error_json_redaction(self, mock_print, mock_runner_class, mock_checker_class, mock_build, mock_check):
        preflight_mock = MagicMock()
        preflight_mock.ready_for_discovery = True
        mock_check.return_value = preflight_mock
        
        comp_mock = MagicMock()
        mock_build.return_value = comp_mock
        
        checker_mock = MagicMock()
        perm_check = MagicMock()
        perm_check.all_required_readable = True
        checker_mock.check.return_value = perm_check
        mock_checker_class.return_value = checker_mock
        
        runner_mock = MagicMock()
        from yyr4_linux_control.integration.probe import ProbeResult, ProbeTermination
        from yyr4_linux_control.observation.diagnostics import ObservationDiagnostics
        
        # We pass redacted message to result to simulate runner returning it.
        # But we also verify JSON structure
        diag_mock = MagicMock()
        diag_mock.discovery_attempts = 1
        diag_mock.identities_selected = 1
        diag_mock.streams_created = 1
        diag_mock.raw_events_seen = 1
        diag_mock.transport_source_events = 1
        diag_mock.ignored_source_events = 1
        diag_mock.control_events_emitted = 1
        diag_mock.synthetic_releases_emitted = 1
        diag_mock.normal_completions = 1
        diag_mock.discovery_errors = 1
        diag_mock.input_errors = 1
        diag_mock.parser_errors = 1
        diag_mock.cancellation_count = 1
        diag_mock.close_calls = 1

        result_mock = ProbeResult(
            termination=ProbeTermination.OBSERVATION_ERROR,
            profile_mode="transport",
            events=(),
            elapsed_seconds=0.1,
            diagnostics=diag_mock,
            error_type="ObservationInputError",
            error_message="<redacted>"
        )
        async def fake_run(): return result_mock
        runner_mock.run.side_effect = fake_run
        mock_runner_class.return_value = runner_mock
        
        self.assertEqual(main(), EXIT_OBSERVATION)
        output = mock_print.call_args[0][0]
        data = json.loads(output)
        self.assertEqual(data["termination"], "OBSERVATION_ERROR")
        self.assertEqual(data["error_message"], "<redacted>")
        self.assertNotIn("/home/", output)
        self.assertNotIn("/dev/input/", output)

    @patch("sys.argv", [
        "observe_probe.py",
        "--acknowledge-read-only-device-access",
        "--acknowledge-transport-profile-active",
        "--acknowledge-no-actions",
    ])
    @patch("yyr4_linux_control.tools.observe_probe.check_runtime_preflight")
    @patch("yyr4_linux_control.tools.observe_probe.build_linux_observation_pipeline")
    @patch("yyr4_linux_control.tools.observe_probe.FilesystemIdentityPermissionChecker")
    @patch("yyr4_linux_control.tools.observe_probe.ProbeRunner")
    @patch("builtins.print")
    def test_timeout_exit(self, mock_print, mock_runner_class, mock_checker_class, mock_build, mock_check):
        preflight_mock = MagicMock()
        preflight_mock.ready_for_discovery = True
        mock_check.return_value = preflight_mock
        
        mock_build.return_value = MagicMock()
        
        checker_mock = MagicMock()
        perm_check = MagicMock()
        perm_check.all_required_readable = True
        checker_mock.check.return_value = perm_check
        mock_checker_class.return_value = checker_mock
        
        runner_mock = MagicMock()
        from yyr4_linux_control.integration.probe import ProbeResult, ProbeTermination
        
        diag_mock = MagicMock()
        diag_mock.discovery_attempts = 1
        diag_mock.identities_selected = 1
        diag_mock.streams_created = 1
        diag_mock.raw_events_seen = 1
        diag_mock.transport_source_events = 1
        diag_mock.ignored_source_events = 1
        diag_mock.control_events_emitted = 1
        diag_mock.synthetic_releases_emitted = 1
        diag_mock.normal_completions = 1
        diag_mock.discovery_errors = 1
        diag_mock.input_errors = 1
        diag_mock.parser_errors = 1
        diag_mock.cancellation_count = 1
        diag_mock.close_calls = 1

        result_mock = ProbeResult(
            termination=ProbeTermination.TIMEOUT,
            profile_mode="transport",
            events=(),
            elapsed_seconds=0.1,
            diagnostics=diag_mock
        )
        async def fake_run(): return result_mock
        runner_mock.run.side_effect = fake_run
        mock_runner_class.return_value = runner_mock
        
        self.assertEqual(main(), EXIT_TIMEOUT)
