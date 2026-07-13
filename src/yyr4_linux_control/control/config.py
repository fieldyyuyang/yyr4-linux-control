import tomllib
from typing import Dict, Any, Mapping, Tuple
from pathlib import Path

from .models import OfficialControl, _OFFICIAL_CONTROL_NAMES
from .actions import (
    Action, HotkeyAction, TextAction, CommandAction,
    DelayAction, MacroAction, NoOpAction, DebugLogAction
)
from .errors import (
    UnsupportedSchemaVersionError, ConfigSyntaxError,
    ConfigValidationError, UnknownControlError,
    UnknownActionTypeError, InvalidActionError
)

def load_control_config_from_file(path: Path) -> Dict[OfficialControl, Action]:
    try:
        content = path.read_text(encoding="utf-8")
    except Exception as e:
        raise ConfigValidationError(f"Could not read file: {e}")
    return load_control_config_from_string(content)

def load_control_config_from_string(content: str) -> Dict[OfficialControl, Action]:
    try:
        data = tomllib.loads(content)
    except tomllib.TOMLDecodeError as e:
        raise ConfigSyntaxError(f"Invalid TOML: {e}")
    return _parse_config(data)

def _parse_config(data: Dict[str, Any]) -> Dict[OfficialControl, Action]:
    version = data.get("schema_version")
    if version != 1:
        raise UnsupportedSchemaVersionError(f"Unsupported or missing schema_version: {version}")

    result: Dict[OfficialControl, Action] = {}
    controls = data.get("controls", {})
    if not isinstance(controls, dict):
        raise ConfigValidationError("controls must be a table", path="controls")

    # Validate that we don't have unknown top-level keys
    allowed_top_keys = {"schema_version", "controls"}
    for key in data:
        if key not in allowed_top_keys:
            raise ConfigValidationError(f"Unknown top-level field: {key}", path=key)

    for ctrl_name, ctrl_conf in controls.items():
        path = f"controls.{ctrl_name}"
        if ctrl_name not in _OFFICIAL_CONTROL_NAMES:
            raise UnknownControlError(f"Unknown control: {ctrl_name}", path=path)

        if not isinstance(ctrl_conf, dict):
            raise ConfigValidationError("control configuration must be a table", path=path)

        action_def = ctrl_conf.get("action")
        if action_def is None:
            continue

        action = _parse_action(action_def, path=f"{path}.action")
        result[OfficialControl(ctrl_name)] = action
        
        # Check for unknown fields in control conf
        for key in ctrl_conf:
            if key != "action":
                raise ConfigValidationError(f"Unknown field in control config: {key}", path=f"{path}.{key}")

    return result

def _parse_action(data: Any, path: str) -> Action:
    if not isinstance(data, dict):
        raise ConfigValidationError("action must be a table", path=path)

    action_type = data.get("type")
    if not action_type:
        raise ConfigValidationError("action missing 'type'", path=path)

    # Check for unknown fields in action def
    allowed_action_keys = {"type", "keys", "value", "argv", "timeout_seconds", "milliseconds", "steps", "message"}
    for key in data:
        if key not in allowed_action_keys:
            raise ConfigValidationError(f"Unknown field in action: {key}", path=f"{path}.{key}")

    if action_type == "hotkey":
        keys = data.get("keys")
        if not isinstance(keys, list):
            raise InvalidActionError("hotkey action requires 'keys' as a list of strings", path=path)
        try:
            return HotkeyAction(tuple(keys))
        except ValueError as e:
            raise InvalidActionError(str(e), path=path)

    elif action_type == "text":
        val = data.get("value")
        if not isinstance(val, str):
            raise InvalidActionError("text action requires 'value' as a string", path=path)
        return TextAction(val)

    elif action_type == "command":
        argv = data.get("argv")
        timeout = data.get("timeout_seconds")
        if not isinstance(argv, list):
            raise InvalidActionError("command action requires 'argv' as a list of strings", path=path)
        if timeout is not None and not isinstance(timeout, int):
            raise InvalidActionError("timeout_seconds must be an integer", path=path)
        try:
            return CommandAction(tuple(argv), timeout_seconds=timeout)
        except ValueError as e:
            raise InvalidActionError(str(e), path=path)

    elif action_type == "delay":
        ms = data.get("milliseconds")
        if not isinstance(ms, int):
            raise InvalidActionError("delay action requires 'milliseconds' as an integer", path=path)
        try:
            return DelayAction(ms)
        except ValueError as e:
            raise InvalidActionError(str(e), path=path)

    elif action_type == "macro":
        steps_data = data.get("steps")
        if not isinstance(steps_data, list):
            raise InvalidActionError("macro action requires 'steps' as a list of actions", path=path)
        steps = []
        for i, step_data in enumerate(steps_data):
            steps.append(_parse_action(step_data, path=f"{path}.steps[{i}]"))
        return MacroAction(tuple(steps))

    elif action_type == "noop":
        return NoOpAction()

    elif action_type == "debug_log":
        msg = data.get("message")
        if not isinstance(msg, str):
            raise InvalidActionError("debug_log action requires 'message' as a string", path=path)
        return DebugLogAction(msg)

    else:
        raise UnknownActionTypeError(f"Unknown action type: {action_type}", path=path)
