import argparse
import asyncio
import sys
from pathlib import Path
import logging
import json
import os

from yyr4_linux_control.execution.engine import ActionExecutionEngine
from yyr4_linux_control.execution.command import CommandExecutionPolicy, AsyncSubprocessCommandRunner
from yyr4_linux_control.execution.desktop import XDoToolDesktopInputBackend, UnavailableDesktopInputBackend
from yyr4_linux_control.execution.delay import AsyncioDelayBackend
from yyr4_linux_control.execution.debug import PythonLoggingDebugLogBackend
from yyr4_linux_control.control.actions import DryRunExecutor, ActionPlan
from yyr4_linux_control.execution.models import ActionExecutionResult, ExecutionStatus

from .models import ExecutionMode, RuntimeSettings, DaemonState
from .runtime import DaemonRuntime
from .session import ProductionInputSessionFactory
from .signals import NativeSignalController
from .interfaces import ActionPlanExecutor
from yyr4_linux_control.management.socket_path import get_default_socket_path
from yyr4_linux_control.management.server import ManagementServer

logger = logging.getLogger("yyr4_linux_control.daemon")

class DryRunExecutorAdapter(ActionPlanExecutor):
    def __init__(self):
        self._executor = DryRunExecutor()
        self._debug_logger = PythonLoggingDebugLogBackend()

    async def execute(self, plan: ActionPlan) -> ActionExecutionResult:
        res = self._executor.execute(plan)
        # Log dry run output
        logger.info(f"DRY RUN: Executed plan for {res.control.value} with {res.step_count} steps.")
        
        # Determine status
        if res.status == "UNMAPPED":
            exec_status = ExecutionStatus.SKIPPED
        else:
            exec_status = ExecutionStatus.SUCCESS

        return ActionExecutionResult(
            control=res.control,
            plan_resolution_status=plan.resolution_status,
            execution_status=exec_status,
            started_at=0.0,
            finished_at=0.0,
            duration_seconds=0.0,
            total_steps=res.step_count,
            completed_steps=res.step_count,
            step_results=()
        )

def setup_logging(level_name: str):
    level = getattr(logging, level_name.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stderr
    )

def _build_production_action_engine() -> ActionPlanExecutor:
    policy = CommandExecutionPolicy(
        allow_commands={"playerctl", "mpc"}, # Add reasonable defaults per docs, but strictly restricted
        max_timeout_seconds=10,
    )
    runner = AsyncSubprocessCommandRunner(policy)
    
    desktop = XDoToolDesktopInputBackend(runner)
    if not desktop.availability():
        desktop = UnavailableDesktopInputBackend()
        
    delay = AsyncioDelayBackend()
    debug = PythonLoggingDebugLogBackend()
    
    return ActionExecutionEngine(
        desktop_backend=desktop,
        command_runner=runner,
        delay_backend=delay,
        debug_log_backend=debug
    )

async def _main_async(args) -> int:
    # 1. Reject root early
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        logger.critical("yyr4d must not be run as root.")
        return 1

    config_path_str = args.config
    if not config_path_str:
        default_config = Path.home() / ".config" / "yyr4" / "config.toml"
        if default_config.exists():
            config_path_str = str(default_config)
        else:
            logger.critical(f"Missing required --config argument, and default {default_config} not found.")
            return 1

    mode = ExecutionMode[args.execution_mode]

    try:
        settings = RuntimeSettings(
            config_path=config_path_str,
            execution_mode=mode,
            queue_capacity=args.queue_capacity,
            reconnect_initial_seconds=args.reconnect_initial,
            reconnect_max_seconds=args.reconnect_max,
            reconnect_multiplier=args.reconnect_multiplier,
            shutdown_grace_seconds=args.shutdown_grace,
            log_level=args.log_level
        )
    except ValueError as e:
        logger.critical(f"Invalid runtime settings: {e}")
        return 1

    factory = ProductionInputSessionFactory(include_mouse=True)
    
    if mode == ExecutionMode.EXECUTE:
        logger.warning("EXECUTE mode is enabled. Real system actions will be performed.")
        executor = _build_production_action_engine()
    else:
        logger.info("DRY_RUN mode is enabled. No real system actions will be performed.")
        executor = DryRunExecutorAdapter()

    runtime = DaemonRuntime(
        settings=settings,
        input_session_factory=factory,
        action_executor=executor
    )

    try:
        socket_path = Path(args.control_socket) if args.control_socket else get_default_socket_path()
    except Exception as e:
        logger.critical(f"Failed to determine socket path: {e}")
        return 1

    server = ManagementServer(runtime, socket_path)
    try:
        await server.start()
    except Exception as e:
        logger.critical(f"Failed to start management server: {e}")
        return 1

    run_task = asyncio.create_task(runtime.run())
    loop = asyncio.get_running_loop()
    signals = NativeSignalController()
    signals.setup(loop, on_stop=runtime.request_stop, on_reload=runtime.request_reload)

    # 2. Run
    try:
        await run_task
    except asyncio.CancelledError:
        pass
    
    # 3. Handle shutdown and output snapshot
    await server.stop()
    snapshot = runtime.snapshot()
    if args.json_final_status:
        # JSON strictly to stdout
        print(json.dumps(snapshot.to_dict(), indent=2))

    if snapshot.state == DaemonState.FAILED:
        return 2

    return 0

def main():
    parser = argparse.ArgumentParser(description="YYR4 Linux Control Daemon Runtime")
    parser.add_argument("--version", action="version", version="0.1.0")
    parser.add_argument("--config", type=str, help="Path to TOML configuration file (defaults to ~/.config/yyr4/config.toml)")
    parser.add_argument("--execution-mode", type=str, choices=["DRY_RUN", "EXECUTE"], default="EXECUTE", help="Action execution mode")
    parser.add_argument("--control-socket", type=str, help="Path to unix domain socket for management CLI")
    parser.add_argument("--queue-capacity", type=int, default=128, help="Maximum queued actions")
    parser.add_argument("--reconnect-initial", type=float, default=1.0, help="Initial reconnect backoff seconds")
    parser.add_argument("--reconnect-max", type=float, default=60.0, help="Max reconnect backoff seconds")
    parser.add_argument("--reconnect-multiplier", type=float, default=2.0, help="Reconnect backoff multiplier")
    parser.add_argument("--shutdown-grace", type=float, default=5.0, help="Shutdown grace period seconds")
    parser.add_argument("--log-level", type=str, default="INFO", help="Logging level")
    parser.add_argument("--json-final-status", action="store_true", help="Output JSON snapshot to stdout on exit")

    args = parser.parse_args()
    
    setup_logging(args.log_level)
    
    exit_code = asyncio.run(_main_async(args))
    sys.exit(exit_code)

if __name__ == "__main__":
    main()
