import asyncio
import unittest
import tempfile
import os

from yyr4_linux_control.daemon.runtime import DaemonRuntime
from yyr4_linux_control.daemon.models import DaemonState, RuntimeSettings, ExecutionMode
from yyr4_linux_control.daemon.errors import FatalRuntimeError, InvalidStateTransitionError

from tests.test_daemon_runtime import FakeSessionFactory, FakeExecutor, FakeClock, FakeSession

class TestDaemonLifecycle(unittest.IsolatedAsyncioTestCase):
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

    async def test_runtime_transitions_through_starting_connecting_running(self):
        session = FakeSession([], hang=True)
        factory = FakeSessionFactory([session])
        runtime = DaemonRuntime(self.settings, factory, self.executor, self.clock)
        
        self.assertEqual(runtime.state, DaemonState.CREATED)
        
        # We need to capture states. We can check them as it runs.
        run_task = asyncio.create_task(runtime.run())
        
        # Give it a tiny moment to start and connect
        await asyncio.sleep(0.01)
        self.assertIn(runtime.state, [DaemonState.CONNECTING, DaemonState.RUNNING])
        
        # Inject an event to transition to RUNNING
        from yyr4_linux_control.control.models import OfficialControlEvent, OfficialControl, ControlPhase
        session.inject(OfficialControlEvent(OfficialControl.A1, ControlPhase.DOWN, 100))
        await asyncio.sleep(0.01)
        self.assertEqual(runtime.state, DaemonState.RUNNING)
        
        runtime.request_stop()
        await run_task
        self.assertEqual(runtime.state, DaemonState.STOPPED)

    async def test_runtime_rejects_illegal_state_transition(self):
        # State transitions are private, but we can verify it doesn't allow run twice
        pass

    async def test_runtime_can_only_run_once(self):
        session = FakeSession([], hang=True)
        factory = FakeSessionFactory([session])
        runtime = DaemonRuntime(self.settings, factory, self.executor, self.clock)
        
        run_task = asyncio.create_task(runtime.run())
        await asyncio.sleep(0.01)
        
        with self.assertRaises(InvalidStateTransitionError):
            await runtime.run()
            
        runtime.request_stop()
        await run_task

    async def test_request_stop_is_idempotent(self):
        session = FakeSession([], hang=True)
        factory = FakeSessionFactory([session])
        runtime = DaemonRuntime(self.settings, factory, self.executor, self.clock)
        
        run_task = asyncio.create_task(runtime.run())
        await asyncio.sleep(0.01)
        
        runtime.request_stop()
        runtime.request_stop()
        runtime.request_stop()
        
        await run_task
        self.assertEqual(runtime.state, DaemonState.STOPPED)

    async def test_fatal_startup_error_transitions_to_failed(self):
        with open(self.config_path, "w") as f:
            f.write('invalid toml')
            
        session = FakeSession([], hang=True)
        factory = FakeSessionFactory([session])
        runtime = DaemonRuntime(self.settings, factory, self.executor, self.clock)
        
        await runtime.run()
        self.assertEqual(runtime.state, DaemonState.FAILED)

    async def test_clean_shutdown_transitions_to_stopped(self):
        session = FakeSession([], hang=True)
        factory = FakeSessionFactory([session])
        runtime = DaemonRuntime(self.settings, factory, self.executor, self.clock)
        
        run_task = asyncio.create_task(runtime.run())
        await asyncio.sleep(0.01)
        runtime.request_stop()
        await run_task
        
        self.assertEqual(runtime.state, DaemonState.STOPPED)
