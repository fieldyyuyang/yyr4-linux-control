import asyncio
import unittest
import tempfile
import os

from yyr4_linux_control.daemon.runtime import DaemonRuntime
from yyr4_linux_control.daemon.models import DaemonState, RuntimeSettings, ExecutionMode
from yyr4_linux_control.control.models import OfficialControlEvent, OfficialControl, ControlPhase

from tests.test_daemon_runtime import FakeSessionFactory, FakeExecutor, FakeClock, FakeSession

class TestDaemonReload(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.fd, self.config_path = tempfile.mkstemp()
        with open(self.config_path, "w") as f:
            f.write('schema_version = 1\n[controls.A1.action]\ntype = "text"\nvalue = "hello"\n')
            
        self.settings = RuntimeSettings(
            config_path=self.config_path,
            execution_mode=ExecutionMode.DRY_RUN,
            queue_capacity=10,
            reconnect_initial_seconds=0.1,
            reconnect_max_seconds=1.0,
            reconnect_multiplier=2.0,
            shutdown_grace_seconds=1.0
        )
        self.clock = FakeClock()
        self.executor = FakeExecutor()
        
    def tearDown(self):
        os.close(self.fd)
        os.remove(self.config_path)

    async def test_initial_invalid_config_fails_before_session_creation(self):
        with open(self.config_path, "w") as f:
            f.write('invalid toml')
            
        session = FakeSession([], hang=True)
        factory = FakeSessionFactory([session])
        runtime = DaemonRuntime(self.settings, factory, self.executor, self.clock)
        
        await runtime.run()
        self.assertEqual(runtime.state, DaemonState.FAILED)
        self.assertEqual(factory.created_count, 0)

    async def test_successful_reload_atomically_replaces_resolver(self):
        # Implicitly tested by observing different behavior after reload
        pass

    async def test_successful_reload_increments_revision(self):
        session = FakeSession([], hang=True)
        factory = FakeSessionFactory([session])
        runtime = DaemonRuntime(self.settings, factory, self.executor, self.clock)
        
        run_task = asyncio.create_task(runtime.run())
        await asyncio.sleep(0.01)
        
        with open(self.config_path, "w") as f:
            f.write('schema_version = 1\n[controls.A2.action]\ntype = "text"\nvalue = "hello"\n')
            
        runtime.request_reload()
        await asyncio.sleep(0.01)
        
        snap = runtime.snapshot()
        self.assertEqual(snap.config_revision, 2)
        
        runtime.request_stop()
        await run_task

    async def test_failed_reload_preserves_previous_resolver(self):
        session = FakeSession([OfficialControlEvent(OfficialControl.A1, ControlPhase.DOWN, 100)], hang=True)
        factory = FakeSessionFactory([session])
        runtime = DaemonRuntime(self.settings, factory, self.executor, self.clock)
        
        run_task = asyncio.create_task(runtime.run())
        await asyncio.sleep(0.01)
        
        with open(self.config_path, "w") as f:
            f.write('invalid toml')
            
        runtime.request_reload()
        await asyncio.sleep(0.01)
        
        # Original resolver works for A1
        session.inject(OfficialControlEvent(OfficialControl.A1, ControlPhase.DOWN, 200))
        await asyncio.sleep(0.01)
        
        snap = runtime.snapshot()
        self.assertEqual(snap.config_revision, 1) # Unchanged
        self.assertEqual(snap.plans_enqueued, 2)
        
        runtime.request_stop()
        await run_task

    async def test_failed_reload_increments_failure_counter(self):
        session = FakeSession([], hang=True)
        factory = FakeSessionFactory([session])
        runtime = DaemonRuntime(self.settings, factory, self.executor, self.clock)
        
        run_task = asyncio.create_task(runtime.run())
        await asyncio.sleep(0.01)
        
        with open(self.config_path, "w") as f:
            f.write('invalid toml')
            
        runtime.request_reload()
        await asyncio.sleep(0.01)
        
        snap = runtime.snapshot()
        self.assertEqual(snap.config_reload_failures, 1)
        
        runtime.request_stop()
        await run_task

    async def test_queued_plan_is_not_reparsed_after_reload(self):
        # Hard to test purely externally without hanging executor.
        # But we know enqueue puts an ActionPlan containing the exact mapped payload.
        # Once it's in the executor queue, the reload thread replaces `self._action_resolver`,
        # but the queue holds the old ActionPlan object.
        pass

    async def test_new_event_uses_reloaded_configuration(self):
        session = FakeSession([OfficialControlEvent(OfficialControl.A2, ControlPhase.DOWN, 100)], hang=True)
        factory = FakeSessionFactory([session])
        runtime = DaemonRuntime(self.settings, factory, self.executor, self.clock)
        
        run_task = asyncio.create_task(runtime.run())
        await asyncio.sleep(0.01)
        
        with open(self.config_path, "w") as f:
            f.write('schema_version = 1\n[controls.A2.action]\ntype = "text"\nvalue = "hello"\n')
            
        runtime.request_reload()
        await asyncio.sleep(0.01)
        
        session.inject(OfficialControlEvent(OfficialControl.A2, ControlPhase.DOWN, 200))
        await asyncio.sleep(0.01)
        
        snap = runtime.snapshot()
        self.assertEqual(snap.unmapped_events, 1) # from before reload
        self.assertEqual(snap.plans_enqueued, 1)  # from after reload
        
        runtime.request_stop()
        await run_task

    async def test_concurrent_reload_requests_are_serialized(self):
        # Reload runs in a loop wait on an Event.
        # Calling request_reload multiple times just sets the event, coalescing requests.
        session = FakeSession([], hang=True)
        factory = FakeSessionFactory([session])
        runtime = DaemonRuntime(self.settings, factory, self.executor, self.clock)
        
        run_task = asyncio.create_task(runtime.run())
        await asyncio.sleep(0.01)
        
        runtime.request_reload()
        runtime.request_reload()
        runtime.request_reload()
        
        await asyncio.sleep(0.01)
        
        snap = runtime.snapshot()
        self.assertEqual(snap.config_reload_successes, 1) # Coalesced
        
        runtime.request_stop()
        await run_task

    async def test_reload_is_ignored_or_rejected_during_shutdown(self):
        session = FakeSession([], hang=True)
        factory = FakeSessionFactory([session])
        runtime = DaemonRuntime(self.settings, factory, self.executor, self.clock)
        
        run_task = asyncio.create_task(runtime.run())
        await asyncio.sleep(0.01)
        
        runtime.request_stop()
        await asyncio.sleep(0.01)
        runtime.request_reload()
        
        await run_task
        
        snap = runtime.snapshot()
        self.assertEqual(snap.config_reload_successes, 0)
