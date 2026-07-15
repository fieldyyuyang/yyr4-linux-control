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
        count = 0
        types = set()
        for profile in config.profiles.values():
            for layer in profile.layers.values():
                for ctrl_action in layer.controls.values():
                    count += 1
                    from yyr4_linux_control.control.actions import MacroAction
                    if isinstance(ctrl_action, MacroAction):
                        types.update([type(a).__name__ for a in ctrl_action.steps])
                    else:
                        types.add(type(ctrl_action).__name__)
        
        profile_count = len(config.profiles)
        layer_count = sum(len(p.layers) for p in config.profiles.values())
        
        if args.json:
            print(json.dumps({
                "schema_version": config.schema_version,
                "profile_count": profile_count,
                "default_profile": config.default_profile.value,
                "initial_layer": config.initial_layer.value,
                "layer_count": layer_count,
                "configured_control_count": count,
                "action_types": list(types),
                "valid": True
            }))
        else:
            print(f"Schema Version: {config.schema_version}")
            print(f"Profiles: {profile_count}")
            print(f"Default Profile: {config.default_profile.value}")
            print(f"Initial Layer: {config.initial_layer.value}")
            print(f"Total Layers: {layer_count}")
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
            "schema_version": config.schema_version,
            "default_profile": config.default_profile.value,
            "initial_layer": config.initial_layer.value,
            "profiles": {}
        }
        for profile_id, profile in config.profiles.items():
            profile_summary = {}
            for layer_id, layer in profile.layers.items():
                layer_summary = {}
                for name, ctrl_action in layer.controls.items():
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
                        elif t == "SetLayerAction":
                            steps_sum.append({"type": t, "layer": step.layer})
                        elif t == "SetProfileAction":
                            steps_sum.append({"type": t, "profile": step.profile})
                        elif t in ("NextLayerAction", "PreviousLayerAction"):
                            steps_sum.append({"type": t})

                    layer_summary[ctrl_name] = {"action": steps_sum}
                profile_summary[layer_id.value] = layer_summary
            summary["profiles"][profile_id.value] = profile_summary
        
        if args.json:
            print(json.dumps(summary))
        else:
            print(f"Schema Version: {config.schema_version}")
            print(f"Default Profile: {config.default_profile.value}")
            print(f"Initial Layer: {config.initial_layer.value}")
            for p_id, p_data in summary["profiles"].items():
                print(f"\n[Profile: {p_id}]")
                for l_id, l_data in p_data.items():
                    print(f"  [Layer: {l_id}]")
                    for c, ctrl in l_data.items():
                        print(f"    [{c}]")
                        for i, step in enumerate(ctrl["action"]):
                            print(f"      Step {i+1}: {step}")
                    if not l_data:
                        print("    No controls mapped.")
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
        from yyr4_linux_control.control.actions import LayeredActionResolver
        from yyr4_linux_control.control.models import ProfileId, LayerId
        
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
        
        profile_str = args.profile if hasattr(args, 'profile') and args.profile else config.default_profile.value
        try:
            profile_id = ProfileId(profile_str)
        except ValueError as e:
            if args.json:
                print(json.dumps({"error": str(e)}))
            else:
                eprint(f"Invalid profile: {e}")
            sys.exit(EXIT_ARGS)
            
        layer_str = args.layer if hasattr(args, 'layer') and args.layer else config.initial_layer.value
        try:
            layer_id = LayerId(layer_str)
        except ValueError as e:
            if args.json:
                print(json.dumps({"error": f"Unknown LayerId: {layer_str}"}))
            else:
                eprint(f"Unknown LayerId: {layer_str}")
            sys.exit(EXIT_ARGS)
        
        resolver = LayeredActionResolver(config)
        try:
            plan = resolver.resolve(ev, profile_id, layer_id)
        except Exception as e:
            if args.json:
                print(json.dumps({"error": str(e)}))
            else:
                eprint(f"Resolution Error: {e}")
            sys.exit(EXIT_CONFIG)
        
        res_dict = {
            "control": args.control,
            "profile": profile_id.value,
            "layer": layer_id.value,
            "mapping_source": plan.mapping_source,
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
            print(f"Profile: {res_dict['profile']}")
            print(f"Layer: {res_dict['layer']}")
            print(f"Mapping Source: {res_dict['mapping_source']}")
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
        print(f"Selected Profile: {res.get('selected_profile')}")
        print(f"Active Layer: {res.get('active_layer')}")
        print(f"Context Revision: {res.get('context_revision')}")
        print(f"Context Change Source: {res.get('last_context_change_source')}")
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

def cmd_preview(args):
    """Generate a read-only HTML preview of a configuration file."""
    from yyr4_linux_control.configurator import (
        build_document, generate_html, write_preview,
    )
    from pathlib import Path

    config_path = Path(args.config).resolve()
    if not config_path.is_file():
        eprint(f"Configuration file not found: {config_path}")
        sys.exit(EXIT_CONFIG)

    output_path = Path(args.output).resolve()
    try:
        doc = build_document(config_path)
        html_content = generate_html(doc, title=args.title)
        write_preview(html_content, output_path, config_path, force=args.force)
    except FileExistsError as e:
        eprint(str(e))
        sys.exit(EXIT_CONFIG)
    except (ValueError, IsADirectoryError) as e:
        eprint(str(e))
        sys.exit(EXIT_INTERNAL)
    except Exception as e:
        eprint(f"Failed to generate preview: {e}")
        sys.exit(EXIT_INTERNAL)

    print(f"Preview generated: {output_path}")
    print(f"Profiles: {doc.profile_count}")
    print(f"Layers: {doc.total_layer_count}")
    print(f"Configured controls: {doc.total_configured_controls}")
    sys.exit(EXIT_SUCCESS)

def cmd_context_command(args):
    cmd_name = args.command
    params = {}
    if cmd_name == "set-layer":
        params["layer"] = args.layer
    elif cmd_name == "set-profile":
        params["profile"] = args.profile
    
    cmd = "get-context" if cmd_name == "context" else cmd_name
        
    res = asyncio.get_event_loop().run_until_complete(_send_command(args, cmd, params))
    if args.json:
        print(json.dumps(res))
    else:
        if cmd == "get-context":
            print(f"Profile: {res.get('selected_profile')}")
            print(f"Layer: {res.get('active_layer')}")
            print(f"Revision: {res.get('context_revision')}")
            print(f"Source: {res.get('last_change_source')}")
        else:
            print(f"Previous Profile: {res.get('previous_profile')}")
            print(f"Previous Layer: {res.get('previous_layer')}")
            print(f"New Profile: {res.get('selected_profile')}")
            print(f"New Layer: {res.get('active_layer')}")
            print(f"Changed: {res.get('changed')}")
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
    p_dry.add_argument("--profile", type=str, help="Override profile for dry run")
    p_dry.add_argument("--layer", type=str, help="Override layer for dry run")
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

    p_ctx = subparsers.add_parser("context")
    p_ctx.add_argument("--socket", type=str)
    p_ctx.add_argument("--json", action="store_true")

    p_sl = subparsers.add_parser("set-layer")
    p_sl.add_argument("layer", type=str)
    p_sl.add_argument("--socket", type=str)
    p_sl.add_argument("--json", action="store_true")

    p_nl = subparsers.add_parser("next-layer")
    p_nl.add_argument("--socket", type=str)
    p_nl.add_argument("--json", action="store_true")

    p_pl = subparsers.add_parser("previous-layer")
    p_pl.add_argument("--socket", type=str)
    p_pl.add_argument("--json", action="store_true")

    p_sp = subparsers.add_parser("set-profile")
    p_sp.add_argument("profile", type=str)
    p_sp.add_argument("--socket", type=str)
    p_sp.add_argument("--json", action="store_true")

    p_preview = subparsers.add_parser("preview")
    p_preview.add_argument("--config", required=True, type=str,
                           help="Path to configuration file")
    p_preview.add_argument("--output", required=True, type=str,
                           help="Output HTML file path")
    p_preview.add_argument("--title", type=str, default="YYR4 Config Preview",
                           help="HTML page title")
    p_preview.add_argument("--force", action="store_true",
                           help="Overwrite existing output file")

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
    elif args.command in ("context", "set-layer", "next-layer", "previous-layer", "set-profile"):
        cmd_context_command(args)
    elif args.command == "preview":
        cmd_preview(args)
