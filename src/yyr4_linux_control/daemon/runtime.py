import asyncio
import logging
from typing import Optional
from pathlib import Path

from yyr4_linux_control.control.config import load_control_config_from_file
from yyr4_linux_control.control.actions import LayeredActionResolver, ResolutionStatus
from yyr4_linux_control.control.errors import ConfigValidationError

from .models import DaemonState, RuntimeSettings, RuntimeSnapshot
from .context import RuntimeContextManager, ContextChangeSource
from .interfaces import InputSessionFactory, ActionPlanExecutor, Clock
from .queue import DropNewestEventQueue
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
        
        self._queue = DropNewestEventQueue(settings.queue_capacity)
        
        self._context = None  # Instantiated after config load
        
        if hasattr(self._action_executor, 'runtime_backend'):
            self._action_executor.runtime_backend = self

        
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
        
        self._action_resolver: Optional[LayeredActionResolver] = None
        
        self._stop_event = asyncio.Event()
        self._reload_queue = asyncio.Queue()
        
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
            selected_profile=self._context._selected_profile.value if self._context else "",
            active_layer=self._context._active_layer.value if self._context else "",
            context_revision=self._context._revision if self._context else 0,
            last_context_change_source=self._context._last_change_source.value if self._context else "",
            queue_capacity=self._settings.queue_capacity,
        )

    def request_stop(self) -> None:
        """Idempotent stop request."""
        self._stop_event.set()

    def request_reload(self) -> None:
        if self._state in (DaemonState.STOPPING, DaemonState.STOPPED, DaemonState.FAILED):
            return
        # Fire and forget
        fut = asyncio.get_event_loop().create_future()
        self._reload_queue.put_nowait(fut)

    async def request_reload_and_wait(self) -> dict:
        if self._state in (DaemonState.STOPPING, DaemonState.STOPPED, DaemonState.FAILED):
            return {"success": False, "error_code": "DAEMON_STOPPING", "config_revision": self._config_revision}
            
        fut = asyncio.get_event_loop().create_future()
        await self._reload_queue.put(fut)
        return await fut

    async def _try_load_config(self) -> LayeredActionResolver:
        try:
            config = load_control_config_from_file(Path(self._settings.config_path))
            return LayeredActionResolver(config=config)
        except ConfigValidationError as e:
            raise FatalRuntimeError(f"Configuration is invalid: {e}") from e
        except Exception as e:
            raise FatalRuntimeError(f"Failed to load configuration: {e}") from e

    async def _handle_reload(self, fut: asyncio.Future) -> None:
        logger.info("Handling configuration reload request...")
        try:
            new_resolver = await self._try_load_config()
            self._action_resolver = new_resolver
            self._config_revision += 1
            self._config_reload_successes += 1
            
            # Reconcile context
            changed = await self._context.reconcile_after_reload(new_resolver.config)
            if changed:
                logger.info("Context reconciled after reload.")
                
            logger.info(f"Configuration reloaded successfully. Revision: {self._config_revision}")
            if not fut.done():
                fut.set_result({"success": True, "config_revision": self._config_revision, "reload_successes": self._config_reload_successes})
        except FatalRuntimeError as e:
            self._config_reload_failures += 1
            self._last_error_code = "RELOAD_FAILED"
            logger.error(f"Configuration reload failed: {e}. Retaining previous configuration.")
            if not fut.done():
                fut.set_result({"success": False, "error_code": "RELOAD_FAILED", "config_revision": self._config_revision})

    async def _executor_loop(self) -> None:
        try:
            while not self._stop_event.is_set():
                # We use wait_for to periodically check stop_event
                try:
                    event = await asyncio.wait_for(self._queue.dequeue(), timeout=0.5)
                except asyncio.TimeoutError:
                    continue
                
                try:
                    ctx_snap = await self._context.snapshot()
                    plan = self._action_resolver.resolve(
                        event,
                        ctx_snap.selected_profile,
                        ctx_snap.active_layer
                    )
                    self._plans_resolved += 1
                    
                    if plan.resolution_status == ResolutionStatus.UNMAPPED:
                        self._unmapped_events += 1
                        continue

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
                    # We use wait_for to periodically check stop_event
                    get_task = asyncio.create_task(self._reload_queue.get())
                    stop_wait_task = asyncio.create_task(self._stop_event.wait())
                    
                    done, pending = await asyncio.wait(
                        [get_task, stop_wait_task],
                        return_when=asyncio.FIRST_COMPLETED,
                        timeout=0.5
                    )
                    
                    if get_task in done:
                        fut = get_task.result()
                        await self._handle_reload(fut)
                        self._reload_queue.task_done()
                    else:
                        get_task.cancel()
                        
                    for t in pending:
                        t.cancel()
                        
                except asyncio.TimeoutError:
                    continue
        except asyncio.CancelledError:
            pass
        finally:
            # Reject pending reloads
            while not self._reload_queue.empty():
                fut = self._reload_queue.get_nowait()
                if not fut.done():
                    fut.set_result({"success": False, "error_code": "DAEMON_STOPPING", "config_revision": self._config_revision})
                self._reload_queue.task_done()

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
                    
                    enqueued = self._queue.enqueue(event)
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
            self._context = RuntimeContextManager(
                self._action_resolver.config.default_profile, 
                self._action_resolver.config.initial_layer,
                self._clock
            )
            self._context.set_config(self._action_resolver.config)
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

    # RuntimeControlBackend interface and Management CLI APIs
    async def get_runtime_context(self):
        if not self._context:
            return None
        return await self._context.snapshot()

    async def set_active_layer(self, layer_id: str, source: ContextChangeSource) -> bool:
        changed = await self._context.set_layer(layer_id, source)
        if changed:
            logger.info(f"Layer changed to {layer_id}")
        else:
            logger.info(f"Context unchanged (already on layer {layer_id})")
        return changed

    async def next_active_layer(self, source: ContextChangeSource) -> bool:
        changed = await self._context.next_layer(source)
        if changed:
            logger.info(f"Layer changed to next layer ({self._context._active_layer})")
        return changed

    async def previous_active_layer(self, source: ContextChangeSource) -> bool:
        changed = await self._context.previous_layer(source)
        if changed:
            logger.info(f"Layer changed to previous layer ({self._context._active_layer})")
        return changed

    async def set_selected_profile(self, profile_id: str, source: ContextChangeSource) -> bool:
        try:
            changed = await self._context.set_profile(profile_id, source)
            if changed:
                logger.info(f"Profile changed to {profile_id}")
            else:
                logger.info(f"Context unchanged (already on profile {profile_id})")
            return changed
        except ValueError as e:
            logger.warning(f"Invalid profile request: {e}")
            raise
            
    # Internal aliases for the engine interface
    async def set_layer(self, layer_id: str) -> bool:
        return await self.set_active_layer(layer_id, ContextChangeSource.control_action)

    async def next_layer(self) -> bool:
        return await self.next_active_layer(ContextChangeSource.control_action)

    async def previous_layer(self) -> bool:
        return await self.previous_active_layer(ContextChangeSource.control_action)

    async def set_profile(self, profile_id: str) -> bool:
        try:
            return await self.set_selected_profile(profile_id, ContextChangeSource.control_action)
        except ValueError as e:
            # Swallow for runtime action, it will just fail
            logger.warning(f"Runtime action rejected: {e}")
            raise
