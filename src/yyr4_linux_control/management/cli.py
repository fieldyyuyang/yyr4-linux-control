import argparse
import sys
import json
import asyncio
from pathlib import Path

from yyr4_linux_control.management.client import ManagementClient
from yyr4_linux_control.management.errors import ProtocolError
from yyr4_linux_control.management.socket_path import get_default_socket_path

from yyr4_linux_control.control.config import load_control_config_from_file
from yyr4_linux_control.control.errors import ConfigValidationError
from yyr4_linux_control.control.actions import ActionResolver, ResolutionStatus, DryRunExecutor
from yyr4_linux_control.control.models import OfficialControlEvent, OfficialControl

# Exit codes
EXIT_SUCCESS = 0
EXIT_ARGS = 2
EXIT_CONFIG = 3
EXIT_NOT_RUNNING = 4
EXIT_PROTOCOL = 5
EXIT_REJECTED = 6
EXIT_RELOAD_FAILED = 7
EXIT_PERMISSION = 8
EXIT_INTERNAL = 9

def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

def _get_socket_path(args) -> Path:
    if hasattr(args, 'socket') and args.socket:
        return Path(args.socket)
    return get_default_socket_path()

async def _send_command(args, command: str, params: dict = None) -> dict:
    try:
        sock_path = _get_socket_path(args)
    except Exception as e:
        if args.json:
            print(json.dumps({"error": str(e)}))
        else:
            eprint(f"Error determining socket path: {e}")
        sys.exit(EXIT_INTERNAL)

    client = ManagementClient(sock_path)
    try:
        resp = await client.send_request(command, params)
        if not resp.ok:
            if args.json:
                print(json.dumps(resp.error))
            else:
                eprint(f"Daemon rejected request: {resp.error.get('message', 'Unknown error')}")
            if resp.error.get('code') == 'RELOAD_FAILED':
                sys.exit(EXIT_RELOAD_FAILED)
            sys.exit(EXIT_REJECTED)
        return resp.result
    except ProtocolError as e:
        if args.json:
            print(json.dumps({"error": str(e), "code": e.code}))
        else:
            eprint(f"Protocol error: {e}")
        if e.code == "DAEMON_NOT_RUNNING":
            sys.exit(EXIT_NOT_RUNNING)
        elif e.code == "PERMISSION_DENIED":
            sys.exit(EXIT_PERMISSION)
        sys.exit(EXIT_PROTOCOL)
    except Exception as e:
        if args.json:
            print(json.dumps({"error": str(e)}))
        else:
            eprint(f"Unexpected error: {e}")
        sys.exit(EXIT_INTERNAL)

def cmd_validate(args):
    try:
        config = load_control_config_from_file(Path(args.config))
        count = len(config)
        types = set()
        for ctrl_action in config.values():
            from yyr4_linux_control.control.actions import MacroAction
            if isinstance(ctrl_action, MacroAction):
                types.update([type(a).__name__ for a in ctrl_action.steps])
            else:
                types.add(type(ctrl_action).__name__)
        
        if args.json:
            print(json.dumps({
                "schema_version": 1,
                "configured_control_count": count,
                "action_types": list(types),
                "valid": True
            }))
        else:
            print(f"Schema Version: 1")
            print(f"Configured Controls: {count}")
            print(f"Action Types: {', '.join(types) if types else 'None'}")
            print("Status: VALID")
        sys.exit(EXIT_SUCCESS)
    except ConfigValidationError as e:
        if args.json:
            print(json.dumps({"error": str(e), "valid": False}))
        else:
            eprint(f"Validation Error: {e}")
            eprint("Status: INVALID")
        sys.exit(EXIT_CONFIG)
    except Exception as e:
        if args.json:
            print(json.dumps({"error": str(e), "valid": False}))
        else:
            eprint(f"Error: {e}")
            eprint("Status: INVALID")
        sys.exit(EXIT_CONFIG)

def cmd_list_controls(args):
    # Enforce exact order for 24 items
    controls = [
        f"A{i}" for i in range(1, 13)
    ]
    for row in ["A", "B", "C", "D"]:
        for d in ["L", "P", "R"]:
            controls.append(f"{row}{d}")

    if args.json:
        print(json.dumps({"controls": controls}))
    else:
        for c in controls:
            print(c)
    sys.exit(EXIT_SUCCESS)

def cmd_show_config(args):
    try:
        config = load_control_config_from_file(Path(args.config))
        summary = {
            "schema_version": 1,
            "controls": {}
        }
        for name, ctrl_action in config.items():
            ctrl_name = name.value
            
            from yyr4_linux_control.control.actions import MacroAction
            if isinstance(ctrl_action, MacroAction):
                steps = ctrl_action.steps
            else:
                steps = [ctrl_action]
            
            steps_sum = []
            for step in steps:
                t = type(step).__name__
                if t == "TextAction":
                    if args.show_sensitive:
                        steps_sum.append({"type": t, "text": step.value})
                    else:
                        steps_sum.append({"type": t, "length": len(step.value)})
                elif t == "CommandAction":
                    if args.show_sensitive:
                        steps_sum.append({"type": t, "command": step.argv[0] if step.argv else "", "args": list(step.argv[1:])})
                    else:
                        basename = Path(step.argv[0]).name if step.argv else ""
                        steps_sum.append({"type": t, "basename": basename})
                elif t == "DebugLogAction":
                    if args.show_sensitive:
                        steps_sum.append({"type": t, "message": step.message})
                    else:
                        steps_sum.append({"type": t})
                elif t == "HotkeyAction":
                    steps_sum.append({"type": t, "keys": list(step.keys)})
                elif t == "DelayAction":
                    steps_sum.append({"type": t, "milliseconds": step.milliseconds})
                elif t == "NoOpAction":
                    steps_sum.append({"type": t})

            summary["controls"][ctrl_name] = {"action": steps_sum}
        
        if args.json:
            print(json.dumps(summary))
        else:
            print(f"Schema Version: 1")
            for c, ctrl in summary["controls"].items():
                print(f"[{c}]")
                for i, step in enumerate(ctrl["action"]):
                    print(f"  Step {i+1}: {step}")
            if not summary["controls"]:
                print("No controls mapped.")
        sys.exit(EXIT_SUCCESS)
    except ConfigValidationError as e:
        if args.json:
            print(json.dumps({"error": str(e)}))
        else:
            eprint(f"Validation Error: {e}")
        sys.exit(EXIT_CONFIG)

def cmd_dry_run(args):
    try:
        from yyr4_linux_control.domain.events import ControlPhase
        
        try:
            official_ctrl = OfficialControl(args.control)
        except ValueError:
            if args.json:
                print(json.dumps({"error": f"Unknown control format: {args.control}"}))
            else:
                eprint(f"Unknown control format: {args.control}. Must be official name.")
            sys.exit(EXIT_ARGS)
            
        ev = OfficialControlEvent(
            timestamp_ns=0,
            control=official_ctrl,
            phase=ControlPhase.DOWN
        )
        
        config = load_control_config_from_file(Path(args.config))
        resolver = ActionResolver(config)
        plan = resolver.resolve(ev)
        
        res_dict = {
            "control": args.control,
            "resolution": plan.resolution_status.name,
        }
        
        if plan.resolution_status == ResolutionStatus.CONFIGURED:
            executor = DryRunExecutor()
            exec_res = executor.execute(plan)
            
            res_dict["execution"] = {
                "status": exec_res.execution_status.name if hasattr(exec_res, 'execution_status') else "SUCCESS",
                "completed_steps": exec_res.completed_steps if hasattr(exec_res, 'completed_steps') else len(plan.steps),
                "error": str(exec_res.error) if hasattr(exec_res, 'error') and exec_res.error else None,
                "logs": exec_res.dry_run_logs if hasattr(exec_res, 'dry_run_logs') else []
            }
            
        if args.json:
            print(json.dumps(res_dict))
        else:
            print(f"Control: {res_dict['control']}")
            print(f"Resolution: {res_dict['resolution']}")
            if "execution" in res_dict:
                print("Dry Run Execution Logs:")
                for log in res_dict["execution"]["logs"]:
                    print(f"  {log}")
                print(f"Status: {res_dict['execution']['status']}")
                print(f"Completed Steps: {res_dict['execution']['completed_steps']}")
                
        sys.exit(EXIT_SUCCESS)
    except Exception as e:
        if args.json:
            print(json.dumps({"error": str(e)}))
        else:
            eprint(f"Error: {e}")
        sys.exit(EXIT_INTERNAL)

def cmd_status(args):
    res = asyncio.get_event_loop().run_until_complete(_send_command(args, "status"))
    if args.json:
        print(json.dumps(res))
    else:
        print(f"Daemon State: {res.get('state')}")
        print(f"Execution Mode: {res.get('execution_mode')}")
        print(f"Uptime (s): {res.get('uptime_seconds')}")
        print(f"Config Revision: {res.get('config_revision')}")
        print(f"Current Session Active: {res.get('current_session_active')}")
        print(f"Sessions Started: {res.get('sessions_started')}")
        print(f"Reconnect Attempts: {res.get('reconnect_attempts')}")
        print(f"Events Received: {res.get('events_received')}")
        print(f"Plans Executed: {res.get('plans_executed')}")
        print(f"Executions Succeeded: {res.get('executions_succeeded')}")
        print(f"Executions Failed: {res.get('executions_failed')}")
        print(f"Unmapped Events: {res.get('unmapped_events')}")
        print(f"Queue Size: {res.get('queue_size')} / {res.get('queue_capacity')}")
        print(f"Queue Dropped: {res.get('queue_dropped')}")
        print(f"Reload Successes: {res.get('config_reload_successes')}")
        print(f"Reload Failures: {res.get('config_reload_failures')}")
        print(f"Last Error Code: {res.get('last_error_code')}")
    sys.exit(EXIT_SUCCESS)

def cmd_reload(args):
    res = asyncio.get_event_loop().run_until_complete(_send_command(args, "reload"))
    if args.json:
        print(json.dumps(res))
    else:
        print(f"Reload Success! New Revision: {res.get('config_revision')}")
    sys.exit(EXIT_SUCCESS)

def cmd_ping(args):
    res = asyncio.get_event_loop().run_until_complete(_send_command(args, "ping"))
    if args.json:
        print(json.dumps(res))
    else:
        print("PONG")
    sys.exit(EXIT_SUCCESS)

def main():
    parser = argparse.ArgumentParser(description="YYR4 Linux Control Management CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_validate = subparsers.add_parser("validate")
    p_validate.add_argument("--config", required=True, type=str)
    p_validate.add_argument("--json", action="store_true")

    p_list = subparsers.add_parser("list-controls")
    p_list.add_argument("--json", action="store_true")

    p_show = subparsers.add_parser("show-config")
    p_show.add_argument("--config", required=True, type=str)
    p_show.add_argument("--json", action="store_true")
    p_show.add_argument("--show-sensitive", action="store_true", help="WARNING: May reveal sensitive command line arguments or text")

    p_dry = subparsers.add_parser("dry-run")
    p_dry.add_argument("control", type=str)
    p_dry.add_argument("--config", required=True, type=str)
    p_dry.add_argument("--json", action="store_true")

    p_status = subparsers.add_parser("status")
    p_status.add_argument("--socket", type=str)
    p_status.add_argument("--json", action="store_true")

    p_reload = subparsers.add_parser("reload")
    p_reload.add_argument("--socket", type=str)
    p_reload.add_argument("--json", action="store_true")

    p_ping = subparsers.add_parser("ping")
    p_ping.add_argument("--socket", type=str)
    p_ping.add_argument("--json", action="store_true")

    args = parser.parse_args()

    if args.command == "validate":
        cmd_validate(args)
    elif args.command == "list-controls":
        cmd_list_controls(args)
    elif args.command == "show-config":
        cmd_show_config(args)
    elif args.command == "dry-run":
        cmd_dry_run(args)
    elif args.command == "status":
        cmd_status(args)
    elif args.command == "reload":
        cmd_reload(args)
    elif args.command == "ping":
        cmd_ping(args)
