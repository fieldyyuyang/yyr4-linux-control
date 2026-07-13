import asyncio
import logging
from typing import Optional
from pathlib import Path

from yyr4_linux_control.control.config import load_control_config_from_file
from yyr4_linux_control.control.actions import ActionResolver, ResolutionStatus
from yyr4_linux_control.control.errors import ConfigValidationError

from .models import DaemonState, RuntimeSettings, RuntimeSnapshot
from .interfaces import InputSessionFactory, ActionPlanExecutor, Clock
from .queue import DropNewestActionQueue
from .errors import FatalRuntimeError, RecoverableSessionError, InvalidStateTransitionError

logger = logging.getLogger("yyr4_linux_control.daemon")

class SystemClock(Clock):
    def monotonic(self) -> float:
        return asyncio.get_event_loop().time()

    async def sleep(self, seconds: float) -> None:
        await asyncio.sleep(seconds)

class DaemonRuntime:
    def __init__(
        self,
        settings: RuntimeSettings,
        input_session_factory: InputSessionFactory,
        action_executor: ActionPlanExecutor,
        clock: Optional[Clock] = None
    ):
        self._settings = settings
        self._input_session_factory = input_session_factory
        self._action_executor = action_executor
        self._clock = clock or SystemClock()
        
        self._state = DaemonState.CREATED
        self._state_lock = asyncio.Lock()
        
        self._queue = DropNewestActionQueue(settings.queue_capacity)
        
        # Snapshot counters
        self._started_at = 0.0
        self._config_revision = 0
        self._sessions_started = 0
        self._successful_sessions = 0
        self._reconnect_attempts = 0
        self._events_received = 0
        self._plans_resolved = 0
        self._plans_enqueued = 0
        self._plans_executed = 0
        self._executions_succeeded = 0
        self._executions_failed = 0
        self._unmapped_events = 0
        self._discarded_on_shutdown = 0
        self._config_reload_successes = 0
        self._config_reload_failures = 0
        self._last_error_code = None
        
        self._current_session = None
        
        self._action_resolver: Optional[ActionResolver] = None
        
        self._stop_event = asyncio.Event()
        self._reload_event = asyncio.Event()
        
        # Internal task handles
        self._main_task = None
        self._executor_task = None
        self._session_task = None
        self._reload_task = None

    @property
    def state(self) -> DaemonState:
        return self._state

    def snapshot(self) -> RuntimeSnapshot:
        uptime = 0.0
        if self._state not in (DaemonState.CREATED, DaemonState.STARTING):
            uptime = max(0.0, self._clock.monotonic() - self._started_at)
            
        return RuntimeSnapshot(
            state=self._state,
            execution_mode=self._settings.execution_mode,
            started_at=self._started_at,
            uptime_seconds=uptime,
            config_revision=self._config_revision,
            current_session_active=(self._current_session is not None),
            sessions_started=self._sessions_started,
            successful_sessions=self._successful_sessions,
            reconnect_attempts=self._reconnect_attempts,
            events_received=self._events_received,
            plans_resolved=self._plans_resolved,
            plans_enqueued=self._plans_enqueued,
            plans_executed=self._plans_executed,
            executions_succeeded=self._executions_succeeded,
            executions_failed=self._executions_failed,
            unmapped_events=self._unmapped_events,
            queue_dropped=self._queue.dropped_count,
            discarded_on_shutdown=self._discarded_on_shutdown,
            config_reload_successes=self._config_reload_successes,
            config_reload_failures=self._config_reload_failures,
            last_error_code=self._last_error_code,
            queue_size=self._queue.size,
            queue_capacity=self._settings.queue_capacity,
        )

    def request_stop(self) -> None:
        """Idempotent stop request."""
        self._stop_event.set()

    def request_reload(self) -> None:
        self._reload_event.set()

    async def _try_load_config(self) -> ActionResolver:
        try:
            config = load_control_config_from_file(Path(self._settings.config_path))
            return ActionResolver(config=config)
        except ConfigValidationError as e:
            raise FatalRuntimeError(f"Configuration is invalid: {e}") from e
        except Exception as e:
            raise FatalRuntimeError(f"Failed to load configuration: {e}") from e

    async def _handle_reload(self) -> None:
        logger.info("Handling configuration reload request...")
        try:
            new_resolver = await self._try_load_config()
            self._action_resolver = new_resolver
            self._config_revision += 1
            self._config_reload_successes += 1
            logger.info(f"Configuration reloaded successfully. Revision: {self._config_revision}")
        except FatalRuntimeError as e:
            self._config_reload_failures += 1
            self._last_error_code = "RELOAD_FAILED"
            logger.error(f"Configuration reload failed: {e}. Retaining previous configuration.")

    async def _executor_loop(self) -> None:
        try:
            while not self._stop_event.is_set():
                # We use wait_for to periodically check stop_event
                try:
                    plan = await asyncio.wait_for(self._queue.dequeue(), timeout=0.5)
                except asyncio.TimeoutError:
                    continue
                
                try:
                    # Execute
                    res = await self._action_executor.execute(plan)
                    self._plans_executed += 1
                    if res.execution_status.name == "SUCCESS":
                        self._executions_succeeded += 1
                    else:
                        self._executions_failed += 1
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    self._executions_failed += 1
                    logger.error(f"Unexpected error during action execution: {e}")
                finally:
                    self._queue.task_done()
        except asyncio.CancelledError:
            pass
        finally:
            # Drain queue and mark discarded
            discarded = self._queue.get_all_nowait()
            self._discarded_on_shutdown += len(discarded)
            for _ in discarded:
                self._queue.task_done()

    async def _reload_loop(self) -> None:
        try:
            while not self._stop_event.is_set():
                try:
                    await asyncio.wait_for(self._reload_event.wait(), timeout=0.5)
                except asyncio.TimeoutError:
                    continue
                self._reload_event.clear()
                await self._handle_reload()
        except asyncio.CancelledError:
            pass

    async def _run_session(self) -> None:
        self._current_session = self._input_session_factory.create_session()
        self._sessions_started += 1
        logger.info("Input session created. Observing events...")
        try:
            has_seen_event = False
            
            async def consume_events():
                nonlocal has_seen_event
                async for event in self._current_session.observe():
                    if not has_seen_event:
                        self._successful_sessions += 1
                        self._reconnect_attempts = 0  # reset backoff
                        has_seen_event = True
                        async with self._state_lock:
                            self._state = DaemonState.RUNNING

                    self._events_received += 1
                    
                    plan = self._action_resolver.resolve(event)
                    self._plans_resolved += 1
                    
                    if plan.resolution_status == ResolutionStatus.UNMAPPED:
                        self._unmapped_events += 1
                        continue
                    
                    enqueued = self._queue.enqueue(plan)
                    if enqueued:
                        self._plans_enqueued += 1

                    if self._stop_event.is_set():
                        break

            self._session_task = asyncio.create_task(consume_events())
            
            stop_waiter = asyncio.create_task(self._stop_event.wait())
            done, pending = await asyncio.wait(
                [self._session_task, stop_waiter], 
                return_when=asyncio.FIRST_COMPLETED
            )
            
            if stop_waiter in done:
                self._session_task.cancel()
                try:
                    await self._session_task
                except asyncio.CancelledError:
                    pass
            elif self._session_task in done:
                stop_waiter.cancel()
                try:
                    await stop_waiter
                except asyncio.CancelledError:
                    pass
                await self._session_task

        finally:
            self._session_task = None
            if self._current_session:
                await self._current_session.close()
                self._current_session = None

    async def run(self) -> None:
        async with self._state_lock:
            if self._state != DaemonState.CREATED:
                raise InvalidStateTransitionError("Runtime can only run once from CREATED state.")
            self._state = DaemonState.STARTING
        
        self._started_at = self._clock.monotonic()
        logger.info("Daemon starting...")

        # Load initial config
        try:
            self._action_resolver = await self._try_load_config()
            self._config_revision += 1
            logger.info("Initial configuration loaded successfully.")
        except FatalRuntimeError as e:
            logger.critical(str(e))
            self._last_error_code = "INITIAL_CONFIG_INVALID"
            async with self._state_lock:
                self._state = DaemonState.FAILED
            return

        self._executor_task = asyncio.create_task(self._executor_loop())
        self._reload_task = asyncio.create_task(self._reload_loop())

        while not self._stop_event.is_set():
            async with self._state_lock:
                self._state = DaemonState.CONNECTING if self._reconnect_attempts == 0 else DaemonState.RECONNECTING
            
            try:
                # If it's a reconnect, wait with exponential backoff
                if self._reconnect_attempts > 0:
                    delay = min(
                        self._settings.reconnect_initial_seconds * (self._settings.reconnect_multiplier ** (self._reconnect_attempts - 1)),
                        self._settings.reconnect_max_seconds
                    )
                    logger.info(f"Reconnecting in {delay:.1f} seconds (attempt {self._reconnect_attempts})...")
                    
                    # Cancellable sleep
                    stop_wait_task = asyncio.create_task(self._stop_event.wait())
                    sleep_task = asyncio.create_task(self._clock.sleep(delay))
                    done, pending = await asyncio.wait(
                        [stop_wait_task, sleep_task], 
                        return_when=asyncio.FIRST_COMPLETED
                    )
                    for t in pending:
                        t.cancel()
                        try:
                            await t
                        except asyncio.CancelledError:
                            pass
                        
                    if self._stop_event.is_set():
                        break

                await self._run_session()

                # If session exits normally without stop requested
                if not self._stop_event.is_set():
                    logger.info("Session completed. Scheduling reconnect.")
                    self._reconnect_attempts += 1

            except RecoverableSessionError as e:
                logger.warning(f"Session disconnected: {e}")
                self._last_error_code = "SESSION_DISCONNECTED"
                self._reconnect_attempts += 1
            except FatalRuntimeError as e:
                logger.critical(f"Fatal error: {e}")
                self._last_error_code = "FATAL_ERROR"
                async with self._state_lock:
                    self._state = DaemonState.FAILED
                break
            except Exception as e:
                logger.critical(f"Unexpected fatal error: {e}")
                self._last_error_code = "UNEXPECTED_ERROR"
                async with self._state_lock:
                    self._state = DaemonState.FAILED
                break

        # Cleanup Phase
        async with self._state_lock:
            if self._state != DaemonState.FAILED:
                self._state = DaemonState.STOPPING

        logger.info("Daemon stopping. Waiting for graceful shutdown...")
        
        # Stop tasks
        if self._executor_task:
            self._executor_task.cancel()
        if self._reload_task:
            self._reload_task.cancel()
            
        try:
            wait_tasks = []
            if self._executor_task:
                wait_tasks.append(self._executor_task)
            if self._reload_task:
                wait_tasks.append(self._reload_task)
            if wait_tasks:
                await asyncio.wait_for(asyncio.gather(*wait_tasks, return_exceptions=True), timeout=self._settings.shutdown_grace_seconds)
        except asyncio.TimeoutError:
            logger.warning("Tasks did not complete within grace period.")
        except asyncio.CancelledError:
            pass

        async with self._state_lock:
            if self._state != DaemonState.FAILED:
                self._state = DaemonState.STOPPED
                
        logger.info("Daemon stopped.")
