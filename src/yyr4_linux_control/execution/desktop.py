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
        # Simple mapper from our unified config keys to xdotool keys
        k = key.lower()
        mapping = {
            "ctrl": "ctrl",
            "shift": "shift",
            "alt": "alt",
            "super": "super",
            "meta": "meta",
            "enter": "Return",
            "return": "Return",
            "esc": "Escape",
            "escape": "Escape",
            "space": "space",
            "tab": "Tab",
            "backspace": "BackSpace",
            "up": "Up",
            "down": "Down",
            "left": "Left",
            "right": "Right",
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
