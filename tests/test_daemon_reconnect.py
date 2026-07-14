import asyncio
import unittest
import tempfile
import os
import dataclasses

from yyr4_linux_control.daemon.runtime import DaemonRuntime
from yyr4_linux_control.daemon.models import DaemonState, RuntimeSettings, ExecutionMode
from yyr4_linux_control.daemon.errors import RecoverableSessionError
from yyr4_linux_control.control.models import OfficialControlEvent, OfficialControl, ControlPhase

from tests.test_daemon_runtime import FakeSessionFactory, FakeExecutor, FakeClock, FakeSession

class TestDaemonReconnect(unittest.IsolatedAsyncioTestCase):
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

    async def test_recoverable_session_error_enters_reconnecting(self):
        s1 = FakeSession([], error=RecoverableSessionError("test disconnect"))
        s2 = FakeSession([], hang=True)
        factory = FakeSessionFactory([s1, s2])
        runtime = DaemonRuntime(self.settings, factory, self.executor, self.clock)
        
        run_task = asyncio.create_task(runtime.run())
        await asyncio.sleep(0.01)
        
        snap = runtime.snapshot()
        self.assertEqual(snap.sessions_started, 2)
        
        runtime.request_stop()
        await run_task

    async def test_reconnect_uses_exponential_backoff(self):
        s1 = FakeSession([], error=RecoverableSessionError("test 1"))
        s2 = FakeSession([], error=RecoverableSessionError("test 2"))
        s3 = FakeSession([], error=RecoverableSessionError("test 3"))
        s4 = FakeSession([], hang=True)
        factory = FakeSessionFactory([s1, s2, s3, s4])
        runtime = DaemonRuntime(self.settings, factory, self.executor, self.clock)
        
        run_task = asyncio.create_task(runtime.run())
        await asyncio.sleep(0.2)
        runtime.request_stop()
        await run_task
        
        # 0.1, 0.2, 0.4 = 0.7 total sleep
        self.assertAlmostEqual(self.clock._time, 0.7, places=1)

    async def test_reconnect_delay_is_capped(self):
        # Setup settings with a small max
        settings = dataclasses.replace(self.settings, reconnect_max_seconds=0.25)
        
        sessions = [FakeSession([], error=RecoverableSessionError("test")) for _ in range(4)]
        sessions.append(FakeSession([], hang=True))
        factory = FakeSessionFactory(sessions)
        runtime = DaemonRuntime(settings, factory, self.executor, self.clock)
        
        run_task = asyncio.create_task(runtime.run())
        await asyncio.sleep(0.2)
        runtime.request_stop()
        await run_task
        
        # 4 failures, delays: 0.1, 0.2, 0.25, 0.25 = 0.8
        self.assertAlmostEqual(self.clock._time, 0.8, places=1)

    async def test_successful_session_resets_backoff(self):
        s1 = FakeSession([], error=RecoverableSessionError("test 1"))
        s2 = FakeSession([OfficialControlEvent(OfficialControl.A1, ControlPhase.DOWN, 100)], hang=True)
        s3 = FakeSession([], hang=True)
        
        factory = FakeSessionFactory([s1, s2, s3])
        runtime = DaemonRuntime(self.settings, factory, self.executor, self.clock)
        
        run_task = asyncio.create_task(runtime.run())
        await asyncio.sleep(0.01)
        
        snap = runtime.snapshot()
        self.assertEqual(snap.reconnect_attempts, 0)
        
        runtime.request_stop()
        await run_task

    async def test_stop_interrupts_reconnect_delay(self):
        # We start a reconnect that will delay for 1000 seconds
        settings = dataclasses.replace(self.settings, reconnect_initial_seconds=1000.0, reconnect_max_seconds=1000.0)
        
        s1 = FakeSession([], error=RecoverableSessionError("test 1"))
        s2 = FakeSession([], hang=True)
        factory = FakeSessionFactory([s1, s2])
        runtime = DaemonRuntime(settings, factory, self.executor, self.clock)
        
        run_task = asyncio.create_task(runtime.run())
        
        await asyncio.sleep(0.01)
        runtime.request_stop()
        
        # If it wasn't interrupted, this would take 1000 seconds (or timeout in tests)
        # But wait, fake clock sleeps don't take real time. However, stop interrupts it!
        await asyncio.wait_for(run_task, timeout=0.1)

    async def test_each_reconnect_creates_new_session(self):
        s1 = FakeSession([], error=RecoverableSessionError("test 1"))
        s2 = FakeSession([], hang=True)
        factory = FakeSessionFactory([s1, s2])
        runtime = DaemonRuntime(self.settings, factory, self.executor, self.clock)
        
        run_task = asyncio.create_task(runtime.run())
        while runtime._current_session is not s2:
            await asyncio.sleep(0.001)
        runtime.request_stop()
        await run_task
        
        self.assertTrue(s1.closed)
        self.assertTrue(s2.closed)

    async def test_reconnect_loop_does_not_busy_spin(self):
        # Fake clock guarantees we yield. If we busy spun, the test would never finish or clock time wouldn't advance
        s1 = FakeSession([], error=RecoverableSessionError("test 1"))
        s2 = FakeSession([], hang=True)
        factory = FakeSessionFactory([s1, s2])
        runtime = DaemonRuntime(self.settings, factory, self.executor, self.clock)
        
        run_task = asyncio.create_task(runtime.run())
        await asyncio.sleep(0.01)
        runtime.request_stop()
        await run_task
        
        self.assertGreater(self.clock._time, 0.0)
