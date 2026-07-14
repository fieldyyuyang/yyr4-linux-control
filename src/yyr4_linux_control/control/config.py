import tomllib
from typing import Dict, Any, Mapping, Tuple
from pathlib import Path

from .models import OfficialControl, _OFFICIAL_CONTROL_NAMES, LayerId, ProfileId, LayerConfig, ProfileConfig, LayeredControlConfig
from .actions import (
    Action, HotkeyAction, TextAction, CommandAction,
    DelayAction, MacroAction, NoOpAction, DebugLogAction
)
from .errors import (
    UnsupportedSchemaVersionError, ConfigSyntaxError,
    ConfigValidationError, UnknownControlError,
    UnknownActionTypeError, InvalidActionError
)

def load_control_config_from_file(path: Path) -> LayeredControlConfig:
    try:
        content = path.read_text(encoding="utf-8")
    except Exception as e:
        raise ConfigValidationError(f"Could not read file: {e}")
    return load_control_config_from_string(content)

def load_control_config_from_string(content: str) -> LayeredControlConfig:
    try:
        data = tomllib.loads(content)
    except tomllib.TOMLDecodeError as e:
        raise ConfigSyntaxError(f"Invalid TOML: {e}")
    return _parse_config(data)

def _parse_config(data: Dict[str, Any]) -> LayeredControlConfig:
    version = data.get("schema_version")
    if version == 1:
        return _parse_schema_v1(data)
    elif version == 2:
        return _parse_schema_v2(data)
    else:
        raise UnsupportedSchemaVersionError(f"Unsupported or missing schema_version: {version}")

def _parse_schema_v1(data: Dict[str, Any]) -> LayeredControlConfig:
    allowed_top_keys = {"schema_version", "controls"}
    for key in data:
        if key not in allowed_top_keys:
            raise ConfigValidationError(f"Unknown top-level field: {key}", path=key)

    controls_data = data.get("controls", {})
    if not isinstance(controls_data, dict):
        raise ConfigValidationError("controls must be a table", path="controls")
        
    controls = _parse_controls(controls_data, "controls")
    
    general_layer = LayerConfig(layer_id=LayerId.GENERAL, controls=controls)
    default_profile = ProfileConfig(profile_id=ProfileId("default"), layers={LayerId.GENERAL: general_layer})
    
    return LayeredControlConfig(
        schema_version=1,
        default_profile=ProfileId("default"),
        initial_layer=LayerId.GENERAL,
        profiles={ProfileId("default"): default_profile}
    )

def _parse_schema_v2(data: Dict[str, Any]) -> LayeredControlConfig:
    allowed_top_keys = {"schema_version", "default_profile", "initial_layer", "profiles"}
    for key in data:
        if key not in allowed_top_keys:
            raise ConfigValidationError(f"Unknown top-level field: {key}", path=key)
            
    default_profile_str = data.get("default_profile")
    if not isinstance(default_profile_str, str):
        raise ConfigValidationError("default_profile must be a string", path="default_profile")
    try:
        default_profile = ProfileId(default_profile_str)
    except ValueError as e:
        raise ConfigValidationError(str(e), path="default_profile")
        
    initial_layer_str = data.get("initial_layer")
    if not isinstance(initial_layer_str, str):
        raise ConfigValidationError("initial_layer must be a string", path="initial_layer")
    try:
        initial_layer = LayerId(initial_layer_str)
    except ValueError:
        raise ConfigValidationError(f"Unknown LayerId: {initial_layer_str}", path="initial_layer")
        
    profiles_data = data.get("profiles")
    if not isinstance(profiles_data, dict) or not profiles_data:
        raise ConfigValidationError("profiles must be a non-empty table", path="profiles")
        
    profiles: Dict[ProfileId, ProfileConfig] = {}
    for profile_name, profile_data in profiles_data.items():
        profile_path = f"profiles.{profile_name}"
        if not isinstance(profile_data, dict):
            raise ConfigValidationError("profile configuration must be a table", path=profile_path)
            
        try:
            profile_id = ProfileId(profile_name)
        except ValueError as e:
            raise ConfigValidationError(str(e), path=profile_path)
            
        allowed_profile_keys = {"layers"}
        for key in profile_data:
            if key not in allowed_profile_keys:
                raise ConfigValidationError(f"Unknown field in profile: {key}", path=f"{profile_path}.{key}")
                
        layers_data = profile_data.get("layers", {})
        if not isinstance(layers_data, dict):
            raise ConfigValidationError("layers must be a table", path=f"{profile_path}.layers")
            
        layers: Dict[LayerId, LayerConfig] = {}
        for layer_name, layer_data in layers_data.items():
            layer_path = f"{profile_path}.layers.{layer_name}"
            if not isinstance(layer_data, dict):
                raise ConfigValidationError("layer configuration must be a table", path=layer_path)
                
            try:
                layer_id = LayerId(layer_name)
            except ValueError:
                raise ConfigValidationError(f"Unknown LayerId: {layer_name}", path=layer_path)
                
            allowed_layer_keys = {"controls"}
            for key in layer_data:
                if key not in allowed_layer_keys:
                    raise ConfigValidationError(f"Unknown field in layer: {key}", path=f"{layer_path}.{key}")
                    
            controls_data = layer_data.get("controls", {})
            if not isinstance(controls_data, dict):
                raise ConfigValidationError("controls must be a table", path=f"{layer_path}.controls")
                
            controls = _parse_controls(controls_data, f"{layer_path}.controls")
            layers[layer_id] = LayerConfig(layer_id=layer_id, controls=controls)
            
        if LayerId.GENERAL not in layers:
            raise ConfigValidationError(f"Profile {profile_name} must contain a 'general' layer", path=f"{profile_path}.layers")
            
        profiles[profile_id] = ProfileConfig(profile_id=profile_id, layers=layers)
        
    if default_profile not in profiles:
        raise ConfigValidationError(f"default_profile '{default_profile.value}' is not defined in profiles", path="default_profile")
        
    return LayeredControlConfig(
        schema_version=2,
        default_profile=default_profile,
        initial_layer=initial_layer,
        profiles=profiles
    )

def _parse_controls(controls: Dict[str, Any], path_prefix: str) -> Dict[OfficialControl, Action]:
    result: Dict[OfficialControl, Action] = {}
    for ctrl_name, ctrl_conf in controls.items():
        path = f"{path_prefix}.{ctrl_name}"
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
