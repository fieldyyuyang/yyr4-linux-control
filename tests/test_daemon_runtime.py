import asyncio
import unittest
import tempfile
import os
from typing import AsyncIterator

from yyr4_linux_control.control.models import OfficialControlEvent, OfficialControl, ControlPhase
from yyr4_linux_control.daemon.models import RuntimeSettings, DaemonState, ExecutionMode
from yyr4_linux_control.daemon.interfaces import InputSession, InputSessionFactory, ActionPlanExecutor, Clock
from yyr4_linux_control.daemon.runtime import DaemonRuntime
from yyr4_linux_control.daemon.errors import RecoverableSessionError, FatalRuntimeError
from yyr4_linux_control.execution.models import ActionExecutionResult, ExecutionStatus

class FakeClock(Clock):
    def __init__(self):
        self._time = 0.0

    def monotonic(self) -> float:
        return self._time

    async def sleep(self, seconds: float) -> None:
        self._time += seconds
        await asyncio.sleep(0.001)

class FakeSession(InputSession):
    def __init__(self, events=None, error=None, hang=False):
        self.error = error
        self.closed = False
        self.hang = hang
        self._queue = asyncio.Queue()
        if events:
            for e in events:
                self._queue.put_nowait(e)

    def inject(self, event):
        self._queue.put_nowait(event)

    async def observe(self) -> AsyncIterator[OfficialControlEvent]:
        while not self._queue.empty():
            yield self._queue.get_nowait()
        
        if self.error:
            raise self.error
        
        if self.hang:
            try:
                # keep waiting for newly injected events or hang forever
                while True:
                    e = await self._queue.get()
                    yield e
            except asyncio.CancelledError:
                pass

    async def close(self) -> None:
        self.closed = True

class FakeSessionFactory(InputSessionFactory):
    def __init__(self, sessions):
        self.sessions = sessions
        self.created_count = 0

    def create_session(self) -> InputSession:
        if self.created_count < len(self.sessions):
            sess = self.sessions[self.created_count]
            self.created_count += 1
            return sess
        return FakeSession([], hang=True)

class FakeExecutor(ActionPlanExecutor):
    def __init__(self):
        self.executed = []

    async def execute(self, plan) -> ActionExecutionResult:
        self.executed.append(plan)
        return ActionExecutionResult(
            control=plan.control,
            plan_resolution_status=plan.resolution_status,
            execution_status=ExecutionStatus.SUCCESS,
            started_at=0.0,
            finished_at=0.0,
            duration_seconds=0.0,
            total_steps=1,
            completed_steps=1,
            step_results=()
        )

class TestDaemonRuntime(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.fd, self.config_path = tempfile.mkstemp()
        with open(self.config_path, "w") as f:
            f.write("""
schema_version = 1
[controls.A1.action]
type = "text"
value = "hello"
""")
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

    async def test_successful_run_and_stop(self):
        event = OfficialControlEvent(OfficialControl.A1, ControlPhase.DOWN, 100)
        session = FakeSession([event, event], hang=True) # 2 events
        factory = FakeSessionFactory([session])
        
        runtime = DaemonRuntime(self.settings, factory, self.executor, self.clock)
        
        run_task = asyncio.create_task(runtime.run())
        
        # Give it a moment to process
        await asyncio.sleep(0.1)
        
        # Request stop
        runtime.request_stop()
        await run_task
        
        snap = runtime.snapshot()
        self.assertEqual(snap.state, DaemonState.STOPPED)
        self.assertEqual(snap.events_received, 2)
        self.assertEqual(snap.plans_enqueued, 2)
        self.assertTrue(session.closed)
        self.assertEqual(len(self.executor.executed), 2)

    async def test_unmapped_event_does_not_enter_queue(self):
        event = OfficialControlEvent(OfficialControl.A2, ControlPhase.DOWN, 100)
        session = FakeSession([event], hang=True)
        factory = FakeSessionFactory([session])
        runtime = DaemonRuntime(self.settings, factory, self.executor, self.clock)
        
        run_task = asyncio.create_task(runtime.run())
        await asyncio.sleep(0.1)
        runtime.request_stop()
        await run_task
        
        snap = runtime.snapshot()
        self.assertEqual(snap.unmapped_events, 1)
        self.assertEqual(snap.plans_enqueued, 1)
        self.assertEqual(snap.plans_executed, 0)

    async def test_explicit_noop_enters_execution_queue(self):
        with open(self.config_path, "w") as f:
            f.write('schema_version = 1\n[controls.A1.action]\ntype = "noop"\n')
            
        event = OfficialControlEvent(OfficialControl.A1, ControlPhase.DOWN, 100)
        session = FakeSession([event], hang=True)
        factory = FakeSessionFactory([session])
        runtime = DaemonRuntime(self.settings, factory, self.executor, self.clock)
        
        run_task = asyncio.create_task(runtime.run())
        await asyncio.sleep(0.1)
        runtime.request_stop()
        await run_task
        
        snap = runtime.snapshot()
        self.assertEqual(snap.plans_enqueued, 1)
        self.assertEqual(snap.unmapped_events, 0)
        self.assertEqual(snap.plans_executed, 1)

    async def test_backend_unavailable_records_failure_without_stopping_runtime(self):
        class FailingExecutor(ActionPlanExecutor):
            async def execute(self, plan):
                raise Exception("Backend unavailable")
                
        failing_executor = FailingExecutor()
        
        event = OfficialControlEvent(OfficialControl.A1, ControlPhase.DOWN, 100)
        session = FakeSession([event], hang=True)
        factory = FakeSessionFactory([session])
        runtime = DaemonRuntime(self.settings, factory, failing_executor, self.clock)
        
        run_task = asyncio.create_task(runtime.run())
        await asyncio.sleep(0.1)
        runtime.request_stop()
        await run_task
        
        snap = runtime.snapshot()
        self.assertEqual(snap.plans_executed, 0)
        self.assertEqual(snap.executions_failed, 1)
        self.assertEqual(snap.state, DaemonState.STOPPED) # did not crash

    async def test_reconnect_backoff(self):
        s1 = FakeSession([], error=RecoverableSessionError("test disconnect"))
        s2 = FakeSession([], error=RecoverableSessionError("test disconnect 2"))
        # s3 will just stay open until we stop
        s3_events = [OfficialControlEvent(OfficialControl.A1, ControlPhase.DOWN, 100)]
        s3 = FakeSession(s3_events, hang=True) 
        
        factory = FakeSessionFactory([s1, s2, s3])
        runtime = DaemonRuntime(self.settings, factory, self.executor, self.clock)
        
        run_task = asyncio.create_task(runtime.run())
        await asyncio.sleep(0.2)
        runtime.request_stop()
        await run_task
        
        snap = runtime.snapshot()
        self.assertEqual(snap.reconnect_attempts, 0) # reset after s3 succeeds
        self.assertEqual(snap.sessions_started, 3)
        self.assertEqual(snap.successful_sessions, 1)
        
    async def test_fatal_error_aborts(self):
        s1 = FakeSession([], error=FatalRuntimeError("boom"))
        factory = FakeSessionFactory([s1])
        runtime = DaemonRuntime(self.settings, factory, self.executor, self.clock)
        
        await runtime.run()
        snap = runtime.snapshot()
        self.assertEqual(snap.state, DaemonState.FAILED)
        self.assertEqual(snap.last_error_code, "FATAL_ERROR")

    async def test_reload_config(self):
        # We start with A1 mapped
        s1 = FakeSession([
            OfficialControlEvent(OfficialControl.A1, ControlPhase.DOWN, 100),
            OfficialControlEvent(OfficialControl.A2, ControlPhase.DOWN, 200) # unmapped
        ], hang=True)
        factory = FakeSessionFactory([s1])
        runtime = DaemonRuntime(self.settings, factory, self.executor, self.clock)
        
        # Start
        run_task = asyncio.create_task(runtime.run())
        await asyncio.sleep(0.05)
        
        # Rewrite config
        with open(self.config_path, "w") as f:
            f.write("""
schema_version = 1
[controls.A2.action]
type = "text"
value = "new"
""")
        runtime.request_reload()
        await asyncio.sleep(0.05)
        
        # Inject more events
        s1.inject(OfficialControlEvent(OfficialControl.A2, ControlPhase.DOWN, 300))
        await asyncio.sleep(0.05)
        
        runtime.request_stop()
        await run_task
        
        snap = runtime.snapshot()
        self.assertEqual(snap.config_revision, 2)
        self.assertEqual(snap.config_reload_successes, 1)
        self.assertEqual(snap.unmapped_events, 1) # the first A2 was unmapped
        self.assertEqual(snap.plans_enqueued, 3)  # A1, A2, A2
        self.assertEqual(snap.plans_executed, 2)  # A1, A2(after reload)
