import unittest
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

    def test_snapshot_to_dict(self):
        snap = RuntimeSnapshot(
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
            queue_size=0,
            queue_capacity=10
        )
        d = snap.to_dict()
        self.assertEqual(d["state"], "RUNNING")
        self.assertEqual(d["execution_mode"], "DRY_RUN")
        self.assertEqual(d["events_received"], 10)
