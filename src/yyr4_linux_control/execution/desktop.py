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


# ── X11 keysym validation ────────────────────────────────────────

def _try_resolve_keysym(name: str) -> bool:
    """Return True if *name* is a known X11 keysym.

    This uses libX11's ``XStringToKeysym`` (read-only, no input).
    We cache the library handle to avoid repeated dlopen calls.
    """
    try:
        _try_resolve_keysym._x11
    except AttributeError:
        import ctypes, ctypes.util
        _lib = ctypes.util.find_library("X11")
        if _lib is None:
            raise DesktopInputError(
                "libX11 not found — cannot validate keysym names"
            )
        _x11 = ctypes.cdll.LoadLibrary(_lib)
        _x11.XStringToKeysym.restype = ctypes.c_ulong
        _x11.XStringToKeysym.argtypes = [ctypes.c_char_p]
        _try_resolve_keysym._x11 = _x11

    return _try_resolve_keysym._x11.XStringToKeysym(name.encode()) != 0


class XDoToolDesktopInputBackend(DesktopInputBackend):
    def __init__(self, command_runner: CommandRunner):
        self.command_runner = command_runner

    def availability(self) -> bool:
        if not shutil.which("xdotool"):
            return False
        if "DISPLAY" not in os.environ:
            return False
        if os.environ.get("XDG_SESSION_TYPE") == "wayland":
            return False
        return True

    # ── Key normalization ───────────────────────────────────────

    # Lowered config token → canonical X11 keysym string.
    # Entries fall into two categories:
    #   1.  Exact keysym names — validated at construction time against
    #       libX11 (XStringToKeysym).  Unknown keysyms raise immediately.
    #   2.  Single ASCII letters / digits — resolved at call time via
    #       XStringToKeysym; rejected if not found.
    #
    # Tokens NOT in this map are rejected — we never silently lowercase
    # and pass through arbitrary multi-character strings.
    _KEY_MAP = {
        # ── Pre-existing public contract (from original implementation) ──
        "ctrl":  "Control_L",
        "shift": "Shift_L",
        "alt":   "Alt_L",
        "super": "Super_L",
        "meta":  "Meta_L",

        "enter":  "Return",
        "return": "Return",
        "esc":    "Escape",
        "escape": "Escape",
        "space":  "space",
        "tab":    "Tab",
        "backspace": "BackSpace",

        "up":    "Up",
        "down":  "Down",
        "left":  "Left",
        "right": "Right",

        # ── Exact left/right modifiers (added for migration fidelity) ──
        "lctrl":  "Control_L",
        "rctrl":  "Control_R",
        "lshift": "Shift_L",
        "rshift": "Shift_R",
        "lalt":   "Alt_L",
        "ralt":   "Alt_R",

        # ── Navigation / editing (migration config) ──
        "delete": "Delete",
        "home":   "Home",
        "end":    "End",

        # ── Keypad (migration config, must not degrade to main-keyboard) ──
        "kp_subtract": "KP_Subtract",
        "kp_divide":   "KP_Divide",
        "kp_multiply": "KP_Multiply",

        # ── Punctuation (migration config) ──
        "minus": "minus",
        "equal": "equal",

        # ── Media keys (migration config) ──
        "xf86monbrightnessdown": "XF86MonBrightnessDown",
        "xf86monbrightnessup":   "XF86MonBrightnessUp",
        "xf86audiomute":         "XF86AudioMute",
    }

    @classmethod
    def _validate_map(cls) -> None:
        """Ensure every value in _KEY_MAP is a valid X11 keysym.

        Called once at class-definition time.  If libX11 is unavailable
        the check is skipped (the error will surface later when a hotkey
        is actually sent).
        """
        for token, keysym in cls._KEY_MAP.items():
            if not _try_resolve_keysym(keysym):
                raise DesktopInputError(
                    f"Invalid keysym in key map: {token!r} → {keysym!r}"
                )

    def _map_key(self, key: str) -> str:
        """Normalize a config key token to a validated X11 keysym."""
        k = key.lower()

        # Single ASCII letter / digit — validate via XStringToKeysym
        if len(key) == 1 and key.isascii():
            if _try_resolve_keysym(k):
                return k
            raise DesktopInputError(
                f"Unknown single-character key: {key!r}"
            )

        # Look up in explicit mapping
        mapped = self._KEY_MAP.get(k)
        if mapped is not None:
            return mapped

        # Unknown multi-character token — NEVER silently pass through
        raise DesktopInputError(
            f"Unknown key token: {key!r} — must be an official control "
            f"key name or standard X11 keysym"
        )

    # ── Hotkey dispatch ──────────────────────────────────────────

    async def send_hotkey(self, keys: Tuple[str, ...]) -> None:
        if not self.availability():
            raise DesktopInputError("xdotool backend is not available")

        if not keys:
            raise DesktopInputError("No keys provided for hotkey")

        mapped_keys = [self._map_key(k) for k in keys]
        hotkey_str = "+".join(mapped_keys)

        # --clearmodifiers: xdotool releases any currently-held
        # modifiers (Ctrl, Shift, Alt, Super) before sending the chord,
        # and does NOT restore them afterwards.  This is acceptable for
        # the YYR4 control device because the user is NOT simultaneously
        # typing on the main keyboard — YYR4 events are isolated.
        argv = ("xdotool", "key", "--clearmodifiers", hotkey_str)
        try:
            exit_code, _, stderr = await self.command_runner.run(
                argv, timeout_seconds=5,
            )
            if exit_code != 0:
                raise DesktopInputError(
                    f"xdotool returned non-zero exit code {exit_code}: "
                    f"{stderr.decode('utf-8', errors='replace')}"
                )
        except Exception as e:
            raise DesktopInputError(f"Failed to execute xdotool: {e}") from e

    async def type_text(self, value: str) -> None:
        if not self.availability():
            raise DesktopInputError("xdotool backend is not available")

        if not value:
            return

        argv = ("xdotool", "type", "--clearmodifiers", "--delay", "0", "--", value)
        try:
            exit_code, _, stderr = await self.command_runner.run(
                argv, timeout_seconds=10,
            )
            if exit_code != 0:
                raise DesktopInputError(
                    f"xdotool returned non-zero exit code {exit_code}: "
                    f"{stderr.decode('utf-8', errors='replace')}"
                )
        except Exception as e:
            raise DesktopInputError(f"Failed to execute xdotool: {e}") from e


# ── Validate the map at import time ──────────────────────────────

try:
    XDoToolDesktopInputBackend._validate_map()
except DesktopInputError:
    # libX11 not available — keysyms will be validated at runtime
    pass
