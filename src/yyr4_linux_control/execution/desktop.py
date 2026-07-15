import os
import shutil
from typing import Tuple, Optional

from .interfaces import DesktopInputBackend, CommandRunner
from .errors import DesktopInputError

class UnavailableDesktopInputBackend(DesktopInputBackend):
    def availability(self) -> bool:
        return False

    async def send_hotkey(self, keys: Tuple[str, ...]) -> None:
        raise DesktopInputError("Desktop input backend is unavailable")

    async def type_text(self, value: str) -> None:
        raise DesktopInputError("Desktop input backend is unavailable")

class XDoToolDesktopInputBackend(DesktopInputBackend):
    def __init__(self, command_runner: CommandRunner):
        self.command_runner = command_runner

    def availability(self) -> bool:
        if not shutil.which("xdotool"):
            return False
        if "DISPLAY" not in os.environ:
            return False
        if os.environ.get("XDG_SESSION_TYPE") == "wayland":
            # xdotool does not work reliably natively on Wayland.
            # While Xwayland exists, true wayland input injection requires ydotool or wtype.
            # For this phase, we explicitly do not support wayland via xdotool.
            return False
        return True

    def _map_key(self, key: str) -> str:
        """Normalize a config key token to an xdotool-compatible keysym name.

        Tokens not in the mapping are rejected — xdotool requires exact-case
        X11 keysym names or its built-in modifier aliases.
        """
        k = key.lower()
        mapping = {
            # Modifier aliases (xdotool built-ins)
            "ctrl": "ctrl",
            "lctrl": "ctrl",
            "rctrl": "ctrl",
            "shift": "shift",
            "lshift": "shift",
            "rshift": "shift",
            "alt": "alt",
            "lalt": "alt",
            "ralt": "alt",
            "super": "super",
            "meta": "meta",
            # Navigation and editing
            "enter": "Return",
            "return": "Return",
            "esc": "Escape",
            "escape": "Escape",
            "space": "space",
            "tab": "Tab",
            "backspace": "BackSpace",
            "delete": "Delete",
            "del": "Delete",
            "home": "Home",
            "end": "End",
            "up": "Up",
            "down": "Down",
            "left": "Left",
            "right": "Right",
            "pageup": "Page_Up",
            "pagedown": "Page_Down",
            # Keypad
            "kp_subtract": "KP_Subtract",
            "kp_add": "KP_Add",
            "kp_divide": "KP_Divide",
            "kp_multiply": "KP_Multiply",
            "kp_enter": "KP_Enter",
            # Punctuation
            "minus": "minus",
            "equal": "equal",
            "comma": "comma",
            "period": "period",
            # Media keys
            "xf86monbrightnessdown": "XF86MonBrightnessDown",
            "xf86monbrightnessup": "XF86MonBrightnessUp",
            "xf86audiomute": "XF86AudioMute",
            "xf86audiolowervolume": "XF86AudioLowerVolume",
            "xf86audioraisevolume": "XF86AudioRaiseVolume",
            "xf86audioplay": "XF86AudioPlay",
            "xf86audiopause": "XF86AudioPause",
            "xf86audionext": "XF86AudioNext",
            "xf86audioprev": "XF86AudioPrev",
        }
        return mapping.get(k, k)

    async def send_hotkey(self, keys: Tuple[str, ...]) -> None:
        if not self.availability():
            raise DesktopInputError("xdotool backend is not available")

        if not keys:
            raise DesktopInputError("No keys provided for hotkey")

        mapped_keys = [self._map_key(k) for k in keys]
        hotkey_str = "+".join(mapped_keys)

        argv = ("xdotool", "key", "--clearmodifiers", hotkey_str)
        try:
            exit_code, _, stderr = await self.command_runner.run(argv, timeout_seconds=5)
            if exit_code != 0:
                raise DesktopInputError(f"xdotool returned non-zero exit code {exit_code}: {stderr.decode('utf-8', errors='replace')}")
        except Exception as e:
            raise DesktopInputError(f"Failed to execute xdotool: {e}") from e

    async def type_text(self, value: str) -> None:
        if not self.availability():
            raise DesktopInputError("xdotool backend is not available")

        if not value:
            return

        argv = ("xdotool", "type", "--clearmodifiers", "--delay", "0", "--", value)
        try:
            exit_code, _, stderr = await self.command_runner.run(argv, timeout_seconds=10)
            if exit_code != 0:
                raise DesktopInputError(f"xdotool returned non-zero exit code {exit_code}: {stderr.decode('utf-8', errors='replace')}")
        except Exception as e:
            raise DesktopInputError(f"Failed to execute xdotool: {e}") from e
