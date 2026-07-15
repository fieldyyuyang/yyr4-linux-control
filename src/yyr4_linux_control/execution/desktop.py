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


# ── Lazy X11 keysym validator ─────────────────────────────────────
#
# libX11 is loaded ONLY on first use, never at import time.
# This means the entire execution.desktop module can be imported,
# configurations can be loaded and validated, and dry-runs can be
# performed even on systems without libX11 or an X server.

def _lazy_x11():
    """Return a (load, validate) pair for X11 keysym resolution.

    The first call loads libX11 via ctypes; subsequent calls reuse
    the cached handle.  If libX11 is not installed, *load* returns
    ``False`` and *validate* always returns ``False``.
    """
    try:
        return _lazy_x11._cached
    except AttributeError:
        pass

    try:
        import ctypes, ctypes.util
        lib_path = ctypes.util.find_library("X11")
        if lib_path is None:
            _lazy_x11._cached = (False, lambda _: False)
            return _lazy_x11._cached
        x11 = ctypes.cdll.LoadLibrary(lib_path)
        x11.XStringToKeysym.restype = ctypes.c_ulong
        x11.XStringToKeysym.argtypes = [ctypes.c_char_p]
        _lazy_x11._cached = (True, lambda name: x11.XStringToKeysym(name.encode()) != 0)
        return _lazy_x11._cached
    except Exception:
        _lazy_x11._cached = (False, lambda _: False)
        return _lazy_x11._cached


# ── Key map ───────────────────────────────────────────────────────
#
# Lowered config token → canonical X11 keysym string.
# This is a pure-data constant — no X11 dependency at import time.
#
# Entries:
#  1. Pre-existing public contract (original implementation)
#  2. Left/right modifier fidelity (migration config)
#  3. Navigation, keypad, punctuation, media keys (migration config)

_KEY_MAP = {
    # ── Pre-existing public contract ──
    "ctrl":   "Control_L",
    "shift":  "Shift_L",
    "alt":    "Alt_L",
    "super":  "Super_L",
    "meta":   "Meta_L",

    "enter":   "Return",
    "return":  "Return",
    "esc":     "Escape",
    "escape":  "Escape",
    "space":   "space",
    "tab":     "Tab",
    "backspace": "BackSpace",

    "up":    "Up",
    "down":  "Down",
    "left":  "Left",
    "right": "Right",

    # ── Exact left/right modifiers ──
    "lctrl":  "Control_L",
    "rctrl":  "Control_R",
    "lshift": "Shift_L",
    "rshift": "Shift_R",
    "lalt":   "Alt_L",
    "ralt":   "Alt_R",

    # ── Navigation / editing ──
    "delete": "Delete",
    "home":   "Home",
    "end":    "End",

    # ── Keypad ──
    "kp_subtract": "KP_Subtract",
    "kp_divide":   "KP_Divide",
    "kp_multiply": "KP_Multiply",

    # ── Punctuation ──
    "minus": "minus",
    "equal": "equal",

    # ── Media keys ──
    "xf86monbrightnessdown": "XF86MonBrightnessDown",
    "xf86monbrightnessup":   "XF86MonBrightnessUp",
    "xf86audiomute":         "XF86AudioMute",
}

# Validate the map lazily when first needed (not at import time).
_key_map_validated = False


def _ensure_map_validated() -> None:
    """Lazily validate _KEY_MAP values against libX11.

    Called once, on first backend use.  If libX11 is unavailable the
    map is trusted as-is (the error will surface later when a hotkey
    is actually sent).
    """
    global _key_map_validated
    if _key_map_validated:
        return
    _key_map_validated = True

    x11_ok, validate = _lazy_x11()
    if not x11_ok:
        return

    for token, keysym in _KEY_MAP.items():
        if not validate(keysym):
            raise DesktopInputError(
                f"Invalid keysym in key map: {token!r} → {keysym!r}"
            )


def _validate_x11_keysym(name: str) -> bool:
    """Return True if *name* is a resolvable X11 keysym."""
    _, validate = _lazy_x11()
    return validate(name)


# ── Backend ───────────────────────────────────────────────────────

class XDoToolDesktopInputBackend(DesktopInputBackend):
    def __init__(self, command_runner: CommandRunner):
        self.command_runner = command_runner
        _ensure_map_validated()

    def availability(self) -> bool:
        if not shutil.which("xdotool"):
            return False
        if "DISPLAY" not in os.environ:
            return False
        if os.environ.get("XDG_SESSION_TYPE") == "wayland":
            return False
        return True

    @staticmethod
    def _map_key(key: str) -> str:
        """Normalize a config key token to a validated X11 keysym.

        Algorithm:
          1. Single ASCII char → validate via X11 → return lowercase.
          2. Known alias (lowered lookup) → return canonical keysym.
          3. Original token is a valid X11 keysym → return as-is.
          4. Otherwise → raise DesktopInputError.
        """
        k = key.lower()

        # ── Single ASCII character ──
        if len(key) == 1 and key.isascii():
            if _validate_x11_keysym(k):
                return k
            raise DesktopInputError(
                f"Unknown single-character key: {key!r}"
            )

        # ── Known alias ──
        mapped = _KEY_MAP.get(k)
        if mapped is not None:
            return mapped

        # ── Standard X11 keysym (unmapped but valid) ──
        if _validate_x11_keysym(key):
            return key

        # ── Reject ──
        raise DesktopInputError(
            f"Unknown key token: {key!r} — must be a known alias "
            f"or a valid X11 keysym name"
        )

    # ── Hotkey dispatch ──────────────────────────────────────────

    async def send_hotkey(self, keys: Tuple[str, ...]) -> None:
        if not self.availability():
            raise DesktopInputError("xdotool backend is not available")

        if not keys:
            raise DesktopInputError("No keys provided for hotkey")

        mapped_keys = [self._map_key(k) for k in keys]
        hotkey_str = "+".join(mapped_keys)

        # --clearmodifiers (from xdotool(1) man page, Debian trixie):
        #   "Any command taking the --clearmodifiers flag will attempt
        #    to clear any active input modifiers during the command and
        #    restore them afterwards."
        #   Steps: 1) query active modifiers  2) send key-up for each
        #   3) run the command  4) send key-down to restore.
        #   There is a race: if the user physically releases a modifier
        #   between steps 2 and 4, restoration may re-press it.  For
        #   the YYR4 control device this is acceptable because the user
        #   is not simultaneously typing on the main keyboard.
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
