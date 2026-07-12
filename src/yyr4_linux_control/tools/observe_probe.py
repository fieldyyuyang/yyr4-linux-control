"""CLI Tool: Read-only hardware observation probe."""

from __future__ import annotations

import argparse
import asyncio
import json
import signal
import sys
import time
from typing import NoReturn, Optional, Any

from yyr4_linux_control.integration.preflight import (
    check_runtime_preflight,
    FilesystemIdentityPermissionChecker,
    RuntimePreflight,
)
from yyr4_linux_control.integration.composition import build_linux_observation_pipeline
from yyr4_linux_control.integration.probe import (
    ProbeAuthorization,
    ProbeConfig,
    ProbeRunner,
    ProbeTermination,
    validate_probe_authorization,
)
from yyr4_linux_control.integration.errors import (
    IntegrationSafetyError,
    IntegrationDependencyError,
)
from yyr4_linux_control.observation.errors import ObservationError


# Exit codes
EXIT_OK = 0
EXIT_ARGS = 2
EXIT_PREFLIGHT = 3
EXIT_DISCOVERY = 4
EXIT_PERMISSION = 5
EXIT_OBSERVATION = 6
EXIT_TIMEOUT = 7
EXIT_INTERRUPTED = 130


def _die(code: int, msg: str) -> NoReturn:
    """Print an error message and exit."""
    print(f"Error: {msg}", file=sys.stderr)
    sys.exit(code)


def _safe_print_preflight(preflight: RuntimePreflight) -> None:
    """Safely format and print preflight results without leaking paths."""
    print("--- Preflight Checks ---")
    print(f"Python supported: {preflight.python_supported}")
    print(f"Platform supported: {preflight.platform_supported}")
    print(f"Running as root: {preflight.is_root}")
    print(f"evdev available: {preflight.evdev.available}")
    print(f"pyudev available: {preflight.pyudev.available}")
    print(f"Ready for discovery: {preflight.ready_for_discovery}")
    
    if preflight.blockers:
        print("\nBlockers:")
        for blocker in preflight.blockers:
            print(f"  - {blocker}")
    if preflight.warnings:
        print("\nWarnings:")
        for warning in preflight.warnings:
            print(f"  - {warning}")


def _build_parser() -> argparse.ArgumentParser:
    """Build the argument parser."""
    parser = argparse.ArgumentParser(
        description="YYR4 Linux Control - Read-only hardware observation probe."
    )
    
    parser.add_argument(
        "--preflight", action="store_true",
        help="Run environmental preflight checks only and exit."
    )
    parser.add_argument(
        "--max-events", type=int, default=32,
        help="Maximum number of control events to observe before exiting (default: 32)."
    )
    parser.add_argument(
        "--timeout", type=float, default=30.0,
        help="Timeout in seconds before exiting (default: 30.0)."
    )
    parser.add_argument(
        "--include-synthetic", action="store_true",
        help="Include synthetic release events in the output."
    )
    parser.add_argument(
        "--show-timestamps", action="store_true",
        help="Include raw monotonic timestamps in the output."
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Output results in JSON format."
    )
    
    # Authorizations
    auth_group = parser.add_argument_group("Explicit Authorizations")
    auth_group.add_argument(
        "--acknowledge-read-only-device-access", action="store_true",
        help="Acknowledge that this tool will read raw evdev packets."
    )
    auth_group.add_argument(
        "--acknowledge-transport-profile-active", action="store_true",
        help="Acknowledge that the device is running the Transport Profile."
    )
    auth_group.add_argument(
        "--acknowledge-no-actions", action="store_true",
        help="Acknowledge that no system actions will be executed by this tool."
    )
    return parser


def main() -> int:
    """Synchronous entry point."""
    parser = _build_parser()
    
    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        return EXIT_ARGS
        
    args = parser.parse_args()
    
    # 1. Preflight check
    preflight = check_runtime_preflight()
    if args.preflight:
        if args.json:
            out = {
                "python_supported": preflight.python_supported,
                "platform_supported": preflight.platform_supported,
                "is_root": preflight.is_root,
                "evdev_available": preflight.evdev.available,
                "pyudev_available": preflight.pyudev.available,
                "ready_for_discovery": preflight.ready_for_discovery,
                "blockers": preflight.blockers,
                "warnings": preflight.warnings,
            }
            print(json.dumps(out, indent=2))
        else:
            _safe_print_preflight(preflight)
        
        if not preflight.ready_for_discovery:
            return EXIT_PREFLIGHT
        return EXIT_OK

    # 2. Authorization check
    auth = ProbeAuthorization(
        acknowledge_read_only_device_access=args.acknowledge_read_only_device_access,
        acknowledge_current_profile_is_transport_profile=args.acknowledge_transport_profile_active,
        acknowledge_no_actions_will_run=args.acknowledge_no_actions,
    )
    try:
        validate_probe_authorization(auth)
    except IntegrationSafetyError as e:
        _die(EXIT_ARGS, f"Authorization failed: {e}")

    # 3. Environment readiness check (post-auth)
    if not preflight.ready_for_discovery:
        _die(EXIT_PREFLIGHT, "Environment not ready for discovery (run --preflight for details).")

    # 4. Probe config
    try:
        config = ProbeConfig(
            max_control_events=args.max_events,
            timeout_seconds=args.timeout,
            include_synthetic=args.include_synthetic,
            display_timestamps=args.show_timestamps,
        )
    except Exception as e:
        _die(EXIT_ARGS, f"Invalid configuration: {e}")

    try:
        return asyncio.run(_async_main(args, config))
    except KeyboardInterrupt:
        return EXIT_INTERRUPTED


async def _async_main(args: argparse.Namespace, config: ProbeConfig) -> int:
    """Asynchronous probe execution."""
    
    # 5. Composition Construction (deferred)
    try:
        composition = build_linux_observation_pipeline(include_mouse=True)
    except IntegrationDependencyError as e:
        _die(EXIT_PREFLIGHT, f"Missing optional dependencies: {e}")

    # 6. Discovery
    try:
        identity = composition.selector.select_single()
    except ObservationError as e:
        _die(EXIT_DISCOVERY, f"Device discovery failed: {e}")

    # 7. Permission Check (Separate from runtime preflight)
    checker = FilesystemIdentityPermissionChecker()
    perm_check = checker.check(identity)
    if not perm_check.all_required_readable:
        msg = "Device nodes not readable. Blockers: " + ", ".join(perm_check.blockers)
        _die(EXIT_PERMISSION, msg)

    # 8. Create a fixed pipeline to avoid double-discovery TOCTOU issues
    from yyr4_linux_control.observation.interfaces import DeviceSelector
    from yyr4_linux_control.device.discovery import YYR4Identity
    from yyr4_linux_control.observation.pipeline import ObservationPipeline

    class FixedIdentitySelector(DeviceSelector):
        def __init__(self, ident: YYR4Identity):
            self.ident = ident
        def select_single(self) -> YYR4Identity:
            return self.ident

    fixed_pipeline = ObservationPipeline(
        selector=FixedIdentitySelector(identity),
        input_factory=composition.input_factory,
        parser_factory=composition.parser_factory,
        transport_source_id="yyr4:keyboard"
    )

    # 9. Setup pipeline cancellation signaling
    runner = ProbeRunner(
        pipeline=fixed_pipeline,
        config=config,
        monotonic_clock=time.monotonic,
    )
    
    loop = asyncio.get_running_loop()
    main_task = asyncio.current_task(loop)
    
    def _cancel_handler(*_: Any) -> None:
        if main_task and not main_task.done():
            main_task.cancel()
            
    try:
        loop.add_signal_handler(signal.SIGINT, _cancel_handler)
        loop.add_signal_handler(signal.SIGTERM, _cancel_handler)
    except NotImplementedError:
        # Windows or unsupported platform (already blocked by preflight anyway)
        pass

    # 9. Run the probe
    try:
        result = await runner.run()
    except asyncio.CancelledError:
        if not args.json:
            print("\nInterrupted by user. Exiting...", file=sys.stderr)
        return EXIT_INTERRUPTED

    # 10. Format and output result safely
    if args.json:
        out = {
            "termination": result.termination.name,
            "elapsed_seconds": result.elapsed_seconds,
            "error_type": result.error_type,
            "error_message": result.error_message,
            "events": [
                {
                    "sequence": e.sequence,
                    "control_id": e.control_id,
                    "vendor_name": e.vendor_name,
                    "phase": e.phase.name,
                    "synthetic": e.synthetic,
                    "reason": e.reason,
                    "timestamp_ns": e.timestamp_ns,
                }
                for e in result.events
            ],
            "diagnostics": {
                "discovery_attempts": result.diagnostics.discovery_attempts,
                "identities_selected": result.diagnostics.identities_selected,
                "streams_created": result.diagnostics.streams_created,
                "raw_events_seen": result.diagnostics.raw_events_seen,
                "transport_source_events": result.diagnostics.transport_source_events,
                "ignored_source_events": result.diagnostics.ignored_source_events,
                "control_events_emitted": result.diagnostics.control_events_emitted,
                "synthetic_releases_emitted": result.diagnostics.synthetic_releases_emitted,
                "normal_completions": result.diagnostics.normal_completions,
                "discovery_errors": result.diagnostics.discovery_errors,
                "input_errors": result.diagnostics.input_errors,
                "parser_errors": result.diagnostics.parser_errors,
                "cancellation_count": result.diagnostics.cancellation_count,
                "close_calls": result.diagnostics.close_calls,
            }
        }
        print(json.dumps(out, indent=2))
    else:
        print("--- Probe Results ---")
        print(f"Termination: {result.termination.name}")
        print(f"Elapsed: {result.elapsed_seconds:.2f}s")
        if result.error_type:
            print(f"Error: {result.error_type} - {result.error_message}")
        print("\nEvents:")
        if not result.events:
            print("  (None)")
        else:
            for e in result.events:
                ts = f" ts={e.timestamp_ns}" if e.timestamp_ns is not None else ""
                synth = f" [SYNTHETIC: {e.reason}]" if e.synthetic else ""
                print(f"  {e.sequence:03d} | {e.vendor_name:<4} | {e.control_id:<12} | {e.phase.name:<6}{synth}{ts}")

    # Map termination to exit code
    if result.termination == ProbeTermination.TIMEOUT:
        return EXIT_TIMEOUT
    if result.termination == ProbeTermination.OBSERVATION_ERROR:
        return EXIT_OBSERVATION
    
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
