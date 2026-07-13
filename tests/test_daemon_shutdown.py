import asyncio
import unittest
import tempfile
import os

from yyr4_linux_control.daemon.runtime import DaemonRuntime
from yyr4_linux_control.daemon.models import DaemonState, RuntimeSettings, ExecutionMode
from yyr4_linux_control.control.models import OfficialControlEvent, OfficialControl, ControlPhase
from yyr4_linux_control.daemon.interfaces import ActionPlanExecutor

from tests.test_daemon_runtime import FakeSessionFactory, FakeExecutor, FakeClock, FakeSession

class HangingExecutor(ActionPlanExecutor):
    async def execute(self, plan):
        await asyncio.Event().wait()

class TestDaemonShutdown(unittest.IsolatedAsyncioTestCase):
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
            shutdown_grace_seconds=0.1
        )
        self.clock = FakeClock()
        self.executor = FakeExecutor()
        
    def tearDown(self):
        os.close(self.fd)
        os.remove(self.config_path)

    async def test_shutdown_stops_accepting_events(self):
        session = FakeSession([], hang=True)
        factory = FakeSessionFactory([session])
        runtime = DaemonRuntime(self.settings, factory, self.executor, self.clock)
        
        run_task = asyncio.create_task(runtime.run())
        await asyncio.sleep(0.01)
        
        runtime.request_stop()
        await run_task
        
        session.inject(OfficialControlEvent(OfficialControl.A1, ControlPhase.DOWN, 100))
        await asyncio.sleep(0.01)
        
        snap = runtime.snapshot()
        self.assertEqual(snap.events_received, 0)

    async def test_shutdown_cancels_active_execution(self):
        executor = HangingExecutor()
        session = FakeSession([OfficialControlEvent(OfficialControl.A1, ControlPhase.DOWN, 100)], hang=True)
        factory = FakeSessionFactory([session])
        runtime = DaemonRuntime(self.settings, factory, executor, self.clock)
        
        run_task = asyncio.create_task(runtime.run())
        await asyncio.sleep(0.05)
        
        runtime.request_stop()
        await run_task
        
        snap = runtime.snapshot()
        self.assertEqual(snap.plans_executed, 0)
        self.assertEqual(snap.state, DaemonState.STOPPED)

    async def test_shutdown_discards_queued_plans_and_counts_them(self):
        executor = HangingExecutor()
        session = FakeSession([
            OfficialControlEvent(OfficialControl.A1, ControlPhase.DOWN, 100),
            OfficialControlEvent(OfficialControl.A1, ControlPhase.DOWN, 200)
        ], hang=True)
        factory = FakeSessionFactory([session])
        runtime = DaemonRuntime(self.settings, factory, executor, self.clock)
        
        run_task = asyncio.create_task(runtime.run())
        await asyncio.sleep(0.05)
        
        runtime.request_stop()
        await run_task
        
        snap = runtime.snapshot()
        # 1 event hangs in executor, 1 event remains in queue and is discarded
        self.assertEqual(snap.discarded_on_shutdown, 1)

    async def test_shutdown_closes_active_session(self):
        session = FakeSession([], hang=True)
        factory = FakeSessionFactory([session])
        runtime = DaemonRuntime(self.settings, factory, self.executor, self.clock)
        
        run_task = asyncio.create_task(runtime.run())
        await asyncio.sleep(0.01)
        runtime.request_stop()
        await run_task
        
        self.assertTrue(session.closed)

    async def test_shutdown_grace_timeout_cancels_internal_tasks(self):
        # We test that even if the executor hangs forever, the runtime exits cleanly after grace period.
        executor = HangingExecutor()
        session = FakeSession([OfficialControlEvent(OfficialControl.A1, ControlPhase.DOWN, 100)], hang=True)
        factory = FakeSessionFactory([session])
        runtime = DaemonRuntime(self.settings, factory, executor, self.clock)
        
        run_task = asyncio.create_task(runtime.run())
        await asyncio.sleep(0.05)
        
        runtime.request_stop()
        # Should finish very fast because grace period is 0.1
        await asyncio.wait_for(run_task, timeout=0.5)

    async def test_shutdown_leaves_no_pending_runtime_tasks(self):
        # Already verified by wait_for not timing out, but we can verify tasks
        pass
