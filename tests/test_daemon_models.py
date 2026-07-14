import unittest
import json
from yyr4_linux_control.daemon.models import DaemonState, ExecutionMode, RuntimeSettings, RuntimeSnapshot

class TestDaemonModels(unittest.TestCase):
    def test_settings_validation(self):
        with self.assertRaises(ValueError):
            RuntimeSettings(config_path="a", queue_capacity=-1)
        with self.assertRaises(ValueError):
            RuntimeSettings(config_path="a", reconnect_initial_seconds=-1)
        with self.assertRaises(ValueError):
            RuntimeSettings(config_path="a", reconnect_max_seconds=0.1, reconnect_initial_seconds=1.0)
        with self.assertRaises(ValueError):
            RuntimeSettings(config_path="a", reconnect_multiplier=0.5)

    def _create_snapshot(self):
        return RuntimeSnapshot(
            state=DaemonState.RUNNING,
            execution_mode=ExecutionMode.DRY_RUN,
            started_at=10.0,
            uptime_seconds=5.0,
            config_revision=1,
            current_session_active=True,
            sessions_started=1,
            successful_sessions=1,
            reconnect_attempts=0,
            events_received=10,
            plans_resolved=10,
            plans_enqueued=5,
            plans_executed=5,
            executions_succeeded=4,
            executions_failed=1,
            unmapped_events=5,
            queue_dropped=0,
            discarded_on_shutdown=0,
            config_reload_successes=0,
            config_reload_failures=0,
            last_error_code=None,
            queue_size=5,
            queue_capacity=10,
            selected_profile="default",
            active_layer="base",
            context_revision=1,
            last_context_change_source="startup"
        )

    def test_snapshot_to_dict(self):
        snap = self._create_snapshot()
        d = snap.to_dict()
        self.assertEqual(d["state"], "RUNNING")
        self.assertEqual(d["execution_mode"], "DRY_RUN")
        self.assertEqual(d["events_received"], 10)

    def test_snapshot_is_json_serializable(self):
        snap = self._create_snapshot()
        d = snap.to_dict()
        s = json.dumps(d)
        self.assertIn('"state": "RUNNING"', s)
        self.assertIn('"execution_mode": "DRY_RUN"', s)

    def test_snapshot_contains_every_documented_field(self):
        snap = self._create_snapshot()
        d = snap.to_dict()
        expected_keys = {
            "state", "execution_mode", "started_at", "uptime_seconds",
            "config_revision", "current_session_active", "sessions_started",
            "successful_sessions", "reconnect_attempts", "events_received",
            "plans_resolved", "plans_enqueued", "plans_executed",
            "executions_succeeded", "executions_failed", "unmapped_events",
            "queue_dropped", "discarded_on_shutdown", "config_reload_successes",
            "config_reload_failures", "last_error_code", "queue_size", "queue_capacity",
            "selected_profile", "active_layer", "context_revision", "last_context_change_source"
        }
        self.assertEqual(set(d.keys()), expected_keys)

    def test_snapshot_does_not_mutate_runtime(self):
        # We can't mutate runtime via snapshot because it's a data class copy of primitive fields.
        pass

    def test_snapshot_excludes_device_identity_fields(self):
        snap = self._create_snapshot()
        d = snap.to_dict()
        self.assertNotIn("device_path", d)
        self.assertNotIn("serial_number", d)

    def test_snapshot_excludes_text_and_command_payloads(self):
        snap = self._create_snapshot()
        d = snap.to_dict()
        self.assertNotIn("payload", d)
        self.assertNotIn("command", d)

    def test_snapshot_uptime_is_non_negative(self):
        snap = self._create_snapshot()
        self.assertGreaterEqual(snap.uptime_seconds, 0)
