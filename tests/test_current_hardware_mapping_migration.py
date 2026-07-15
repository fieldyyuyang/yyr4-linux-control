import json
import unittest
from pathlib import Path

from yyr4_linux_control.control.config import load_control_config_from_file
from yyr4_linux_control.control.actions import (
    ActionResolver, DryRunExecutor, HotkeyAction, MacroAction,
    DelayAction, CommandAction, NoOpAction,
)
from yyr4_linux_control.control.models import OfficialControl

BACKUP_PATH = "docs/WinUI/YYR4-driver-2.0.3-hardware-2.0.1-20260711-before-transport-profile.json"
CONFIG_PATH = Path("examples/yyr4-control-from-20260711-backup.toml")

class TestCurrentHardwareMappingMigration(unittest.TestCase):
    """Offline migration verification — no hardware access, no daemon."""

    # ── Backup file integrity ──

    def test_backup_file_exists(self):
        self.assertTrue(Path(BACKUP_PATH).is_file(),
                        f"Backup JSON not found at {BACKUP_PATH}")

    def test_backup_json_parsable(self):
        with open(BACKUP_PATH, "r") as f:
            data = json.load(f)
        self.assertIsInstance(data, dict)

    def test_app_name_count(self):
        with open(BACKUP_PATH, "r") as f:
            data = json.load(f)
        self.assertEqual(len(data["app_name"]), 8)

    def test_layer0_both_arrays_12_items(self):
        with open(BACKUP_PATH, "r") as f:
            data = json.load(f)
        self.assertEqual(len(data["layer0"][0]), 12)
        self.assertEqual(len(data["layer0"][1]), 12)

    def test_layer1_to_layer7_all_empty(self):
        with open(BACKUP_PATH, "r") as f:
            data = json.load(f)
        for i in range(1, 8):
            layer = data[f"layer{i}"]
            self.assertEqual(layer[0], [""] * 12,
                             f"layer{i}[0] is not all empty strings")
            self.assertEqual(layer[1], [""] * 12,
                             f"layer{i}[1] is not all empty strings")

    def test_super_key_and_open_file_empty(self):
        with open(BACKUP_PATH, "r") as f:
            data = json.load(f)
        sk_nonempty = [x for x in data["super_key_config_data"][0] if x]
        of_nonempty = [x for x in data["open_file_config_data"][0] if x]
        self.assertEqual(sk_nonempty, [], "super_key_config_data is not empty")
        self.assertEqual(of_nonempty, [], "open_file_config_data is not empty")

    # ── button (A1-A12) raw string verification ──

    def test_a1_to_a12_raw_strings(self):
        with open(BACKUP_PATH, "r") as f:
            layer0_0 = json.load(f)["layer0"][0]
        expected = [
            "ESC", "BACKSPACE",
            "LCTRL+LSHIFT+END", "LCTRL+LSHIFT+HOME",
            "LCTRL+E",
            "LSHIFT+ENTER Delay(100) KP_- Delay(20) KP_- Delay(20) KP_- Delay(100) LSHIFT+ENTER Delay(20) LSHIFT+ENTER",
            "LALT+D", "LSHIFT+LCTRL+Z",
            "LCTRL+C", "LCTRL+V",
            "LSHIFT+LCTRL+C", "LSHIFT+LCTRL+V",
        ]
        for i, exp in enumerate(expected):
            self.assertEqual(layer0_0[i], exp,
                             f"A{i+1}: expected {exp!r}, got {layer0_0[i]!r}")

    # ── encoder (AL–DP) raw string verification ──

    def test_encoder_raw_strings_ccw_cw_press_order(self):
        with open(BACKUP_PATH, "r") as f:
            layer0_1 = json.load(f)["layer0"][1]
        # WinUI encodes in CCW-CW-Press order per encoder
        expected = [
            # E01
            ("AL", 0, "屏幕亮度_减"), ("AR", 1, "屏幕亮度_增"), ("AP", 2, "LCTRL+DELETE"),
            # E02
            ("BL", 3, "KP_/"), ("BR", 4, "KP_*"), ("BP", 5, "静音"),
            # E03
            ("CL", 6, "LEFT"), ("CR", 7, "RIGHT"), ("CP", 8, "SPACE"),
            # E04
            ("DL", 9, "LCTRL+-"), ("DR", 10, "LCTRL+="), ("DP", 11, "ENTER"),
        ]
        for name, idx, exp in expected:
            self.assertEqual(layer0_1[idx], exp,
                             f"{name} at idx {idx}: expected {exp!r}, got {layer0_1[idx]!r}")

    # ── Migrated config structural tests ──

    @classmethod
    def setUpClass(cls):
        cls.config = load_control_config_from_file(CONFIG_PATH)

    def test_schema_version(self):
        self.assertEqual(self.config.schema_version, 2)

    def test_single_profile(self):
        self.assertEqual(len(self.config.profiles), 1)

    def test_profile_has_only_general_layer(self):
        profile = self.config.profiles[self.config.default_profile]
        self.assertEqual(len(profile.layers), 1)
        self.assertIn("general", [l.value for l in profile.layers])

    def test_config_has_exactly_24_controls(self):
        profile = self.config.profiles[self.config.default_profile]
        general = profile.layers["general"]
        self.assertEqual(len(general.controls), 24)

    def test_all_24_official_controls_present(self):
        profile = self.config.profiles[self.config.default_profile]
        general = profile.layers["general"]
        configured = {c.value for c in general.controls}
        all_official = {o.value for o in OfficialControl}
        self.assertEqual(configured, all_official)

    def test_no_unknown_controls(self):
        profile = self.config.profiles[self.config.default_profile]
        general = profile.layers["general"]
        for ctrl in general.controls:
            self.assertIn(ctrl, OfficialControl)

    # ── Action type verification ──

    def _action_for(self, name):
        profile = self.config.profiles[self.config.default_profile]
        return profile.layers["general"].controls[OfficialControl(name)]

    def test_a1_escape(self):
        a = self._action_for("A1")
        self.assertIsInstance(a, HotkeyAction)
        self.assertEqual(a.keys, ("ESC",))

    def test_a2_backspace(self):
        a = self._action_for("A2")
        self.assertIsInstance(a, HotkeyAction)
        self.assertEqual(a.keys, ("BACKSPACE",))

    def test_a3_ctrl_shift_end(self):
        a = self._action_for("A3")
        self.assertEqual(a.keys, ("LCTRL", "LSHIFT", "END"))

    def test_a4_ctrl_shift_home(self):
        a = self._action_for("A4")
        self.assertEqual(a.keys, ("LCTRL", "LSHIFT", "HOME"))

    def test_a5_ctrl_e(self):
        a = self._action_for("A5")
        self.assertEqual(a.keys, ("LCTRL", "E"))

    def test_a6_is_macro(self):
        a = self._action_for("A6")
        self.assertIsInstance(a, MacroAction)

    def test_a6_step_count(self):
        a = self._action_for("A6")
        self.assertEqual(len(a.steps), 11)

    def test_a6_delay_sequence(self):
        a = self._action_for("A6")
        delays = [s for s in a.steps if isinstance(s, DelayAction)]
        self.assertEqual(len(delays), 5)
        self.assertEqual([d.milliseconds for d in delays],
                         [100, 20, 20, 100, 20])

    def test_a6_three_kp_subtract(self):
        a = self._action_for("A6")
        kp_subs = [s for s in a.steps
                   if isinstance(s, HotkeyAction) and s.keys == ("KP_Subtract",)]
        self.assertEqual(len(kp_subs), 3)

    def test_a6_three_shift_enter(self):
        a = self._action_for("A6")
        se = [s for s in a.steps
              if isinstance(s, HotkeyAction) and s.keys == ("LSHIFT", "ENTER")]
        self.assertEqual(len(se), 3)

    def test_a6_step_by_step(self):
        """Verify exact step sequence: hotkey, delay, hotkey, delay, ..."""
        a = self._action_for("A6")
        step_types = [(type(s).__name__,
                       s.keys if isinstance(s, HotkeyAction) else
                       s.milliseconds if isinstance(s, DelayAction) else None)
                      for s in a.steps]
        expected = [
            ("HotkeyAction", ("LSHIFT", "ENTER")),
            ("DelayAction", 100),
            ("HotkeyAction", ("KP_Subtract",)),
            ("DelayAction", 20),
            ("HotkeyAction", ("KP_Subtract",)),
            ("DelayAction", 20),
            ("HotkeyAction", ("KP_Subtract",)),
            ("DelayAction", 100),
            ("HotkeyAction", ("LSHIFT", "ENTER")),
            ("DelayAction", 20),
            ("HotkeyAction", ("LSHIFT", "ENTER")),
        ]
        self.assertEqual(step_types, expected)

    def test_a7_alt_d(self):
        a = self._action_for("A7")
        self.assertEqual(a.keys, ("LALT", "D"))

    def test_a8_shift_ctrl_z(self):
        a = self._action_for("A8")
        self.assertEqual(a.keys, ("LSHIFT", "LCTRL", "Z"))

    def test_a9_ctrl_c(self):
        a = self._action_for("A9")
        self.assertEqual(a.keys, ("LCTRL", "C"))

    def test_a10_ctrl_v(self):
        a = self._action_for("A10")
        self.assertEqual(a.keys, ("LCTRL", "V"))

    def test_a11_shift_ctrl_c(self):
        a = self._action_for("A11")
        self.assertEqual(a.keys, ("LSHIFT", "LCTRL", "C"))

    def test_a12_shift_ctrl_v(self):
        a = self._action_for("A12")
        self.assertEqual(a.keys, ("LSHIFT", "LCTRL", "V"))

    # ── Encoder verification ──

    def test_al_brightness_down(self):
        a = self._action_for("AL")
        self.assertEqual(a.keys, ("XF86MonBrightnessDown",))

    def test_ar_brightness_up(self):
        a = self._action_for("AR")
        self.assertEqual(a.keys, ("XF86MonBrightnessUp",))

    def test_ap_ctrl_delete(self):
        a = self._action_for("AP")
        self.assertEqual(a.keys, ("LCTRL", "DELETE"))

    def test_bl_kp_divide(self):
        a = self._action_for("BL")
        self.assertEqual(a.keys, ("KP_Divide",))

    def test_br_kp_multiply(self):
        a = self._action_for("BR")
        self.assertEqual(a.keys, ("KP_Multiply",))

    def test_bp_mute(self):
        a = self._action_for("BP")
        self.assertEqual(a.keys, ("XF86AudioMute",))

    def test_cl_left(self):
        a = self._action_for("CL")
        self.assertEqual(a.keys, ("LEFT",))

    def test_cr_right(self):
        a = self._action_for("CR")
        self.assertEqual(a.keys, ("RIGHT",))

    def test_cp_space(self):
        a = self._action_for("CP")
        self.assertEqual(a.keys, ("SPACE",))

    def test_dl_ctrl_minus(self):
        a = self._action_for("DL")
        self.assertEqual(a.keys, ("LCTRL", "MINUS"))

    def test_dr_ctrl_equal(self):
        a = self._action_for("DR")
        self.assertEqual(a.keys, ("LCTRL", "EQUAL"))

    def test_dp_enter(self):
        a = self._action_for("DP")
        self.assertEqual(a.keys, ("ENTER",))

    # ── Safety: no command, no shell, no sensitive data ──

    def test_no_command_actions(self):
        profile = self.config.profiles[self.config.default_profile]
        general = profile.layers["general"]
        for ctrl, action in general.controls.items():
            self.assertNotIsInstance(action, CommandAction,
                                     f"CommandAction found at {ctrl.value}")

    def test_no_shell_or_sensitive_in_keys(self):
        profile = self.config.profiles[self.config.default_profile]
        general = profile.layers["general"]
        for action in general.controls.values():
            if isinstance(action, HotkeyAction):
                for k in action.keys:
                    self.assertNotIn("/dev/", k)
                    self.assertNotIn("$", k)
                    self.assertNotIn("sudo", k.lower())
            if isinstance(action, MacroAction):
                for s in action.steps:
                    if isinstance(s, HotkeyAction):
                        for k in s.keys:
                            self.assertNotIn("/dev/", k)

    # ── Dry-run all 24 controls ──

    def test_dry_run_all_24_configured(self):
        resolver = ActionResolver(
            config=self.config.profiles[self.config.default_profile]
                   .layers["general"].controls,
        )
        executor = DryRunExecutor()
        from yyr4_linux_control.domain.events import ControlPhase
        from yyr4_linux_control.control.models import OfficialControlEvent

        for ctrl in OfficialControl:
            event = OfficialControlEvent(control=ctrl, phase=ControlPhase.DOWN, timestamp_ns=0)
            plan = resolver.resolve(event)
            self.assertEqual(plan.resolution_status.name, "CONFIGURED",
                             f"{ctrl.value} is not CONFIGURED")
            result = executor.execute(plan)
            self.assertEqual(result.status, "CONFIGURED",
                             f"{ctrl.value} dry-run failed")
            self.assertGreater(result.step_count, 0,
                               f"{ctrl.value} has zero steps")

    def test_a6_dry_run_11_steps(self):
        resolver = ActionResolver(
            config=self.config.profiles[self.config.default_profile]
                   .layers["general"].controls,
        )
        executor = DryRunExecutor()
        from yyr4_linux_control.domain.events import ControlPhase
        from yyr4_linux_control.control.models import OfficialControlEvent

        event = OfficialControlEvent(control=OfficialControl.A6,
                                     phase=ControlPhase.DOWN, timestamp_ns=0)
        plan = resolver.resolve(event)
        result = executor.execute(plan)
        self.assertEqual(result.step_count, 11)

    def test_dry_run_a6_step_types(self):
        resolver = ActionResolver(
            config=self.config.profiles[self.config.default_profile]
                   .layers["general"].controls,
        )
        executor = DryRunExecutor()
        from yyr4_linux_control.domain.events import ControlPhase
        from yyr4_linux_control.control.models import OfficialControlEvent

        event = OfficialControlEvent(control=OfficialControl.A6,
                                     phase=ControlPhase.DOWN, timestamp_ns=0)
        plan = resolver.resolve(event)
        result = executor.execute(plan)
        # Verify step types match expectations
        step_types = [s["type"] for s in result.steps]
        expected = ["hotkey", "delay", "hotkey", "delay", "hotkey",
                    "delay", "hotkey", "delay", "hotkey", "delay", "hotkey"]
        self.assertEqual(step_types, expected)

    # no-op: test_no_real_device_access moved to TestRecordingBackendExecution


class TestBackendKeyNormalization(unittest.TestCase):
    """Verify _map_key produces exact X11 keysym names."""

    def setUp(self):
        from yyr4_linux_control.execution.desktop import XDoToolDesktopInputBackend
        self.backend = XDoToolDesktopInputBackend.__new__(XDoToolDesktopInputBackend)

    def _verify_keysym(self, token):
        """Check that mapped value is a valid X11 keysym via XStringToKeysym."""
        import ctypes, ctypes.util
        x11 = ctypes.cdll.LoadLibrary(ctypes.util.find_library("X11"))
        x11.XStringToKeysym.restype = ctypes.c_ulong
        x11.XStringToKeysym.argtypes = [ctypes.c_char_p]
        mapped = self.backend._map_key(token)
        ks = x11.XStringToKeysym(mapped.encode())
        self.assertNotEqual(ks, 0,
                            f"{token!r} → {mapped!r} → NoSymbol (xdotool will fail)")
        return mapped

    def test_all_25_migration_tokens_resolve(self):
        tokens = [
            "ESC", "BACKSPACE", "ENTER", "SPACE",
            "LCTRL", "LSHIFT", "LALT",
            "END", "HOME", "DELETE",
            "LEFT", "RIGHT",
            "E", "D", "Z", "C", "V",
            "MINUS", "EQUAL",
            "KP_Subtract", "KP_Divide", "KP_Multiply",
            "XF86MonBrightnessDown", "XF86MonBrightnessUp", "XF86AudioMute",
        ]
        for t in tokens:
            self._verify_keysym(t)

    # ── Exact modifier keysym tests ──

    def test_lctrl_maps_to_control_l(self):
        self.assertEqual(self.backend._map_key("LCTRL"), "Control_L")

    def test_lshift_maps_to_shift_l(self):
        self.assertEqual(self.backend._map_key("LSHIFT"), "Shift_L")

    def test_lalt_maps_to_alt_l(self):
        self.assertEqual(self.backend._map_key("LALT"), "Alt_L")

    def test_rctrl_maps_to_control_r(self):
        self.assertEqual(self.backend._map_key("RCTRL"), "Control_R")

    def test_rshift_maps_to_shift_r(self):
        self.assertEqual(self.backend._map_key("RSHIFT"), "Shift_R")

    def test_ralt_maps_to_alt_r(self):
        self.assertEqual(self.backend._map_key("RALT"), "Alt_R")

    def test_generic_ctrl_still_control_l(self):
        self.assertEqual(self.backend._map_key("CTRL"), "Control_L")

    def test_generic_shift_still_shift_l(self):
        self.assertEqual(self.backend._map_key("SHIFT"), "Shift_L")

    def test_generic_alt_still_alt_l(self):
        self.assertEqual(self.backend._map_key("ALT"), "Alt_L")

    # ── Named key tests ──

    def test_esc_maps_to_escape(self):
        self.assertEqual(self.backend._map_key("ESC"), "Escape")

    def test_backspace_maps_correctly(self):
        self.assertEqual(self.backend._map_key("BACKSPACE"), "BackSpace")

    def test_enter_maps_to_return(self):
        self.assertEqual(self.backend._map_key("ENTER"), "Return")

    def test_space_maps_correctly(self):
        self.assertEqual(self.backend._map_key("SPACE"), "space")

    def test_delete_home_end_map_correctly(self):
        self.assertEqual(self.backend._map_key("DELETE"), "Delete")
        self.assertEqual(self.backend._map_key("HOME"), "Home")
        self.assertEqual(self.backend._map_key("END"), "End")

    def test_minus_equal_map_correctly(self):
        self.assertEqual(self.backend._map_key("MINUS"), "minus")
        self.assertEqual(self.backend._map_key("EQUAL"), "equal")

    def test_kp_tokens_preserve_case(self):
        self.assertEqual(self.backend._map_key("KP_Subtract"), "KP_Subtract")
        self.assertEqual(self.backend._map_key("KP_Divide"), "KP_Divide")
        self.assertEqual(self.backend._map_key("KP_Multiply"), "KP_Multiply")

    def test_xf86_tokens_preserve_case(self):
        self.assertEqual(self.backend._map_key("XF86MonBrightnessDown"),
                         "XF86MonBrightnessDown")
        self.assertEqual(self.backend._map_key("XF86MonBrightnessUp"),
                         "XF86MonBrightnessUp")
        self.assertEqual(self.backend._map_key("XF86AudioMute"),
                         "XF86AudioMute")

    # ── Negative tests ──

    def test_unknown_multichar_token_rejected(self):
        from yyr4_linux_control.execution.errors import DesktopInputError
        with self.assertRaises(DesktopInputError):
            self.backend._map_key("UNKNOWN_TOKEN")

    def test_unknown_lowercase_multichar_rejected(self):
        from yyr4_linux_control.execution.errors import DesktopInputError
        with self.assertRaises(DesktopInputError):
            self.backend._map_key("nonexistent")

    def test_invalid_keysym_not_silently_passed(self):
        """A token that looks plausible but is not a real keysym must be rejected."""
        from yyr4_linux_control.execution.errors import DesktopInputError
        with self.assertRaises(DesktopInputError):
            self.backend._map_key("FAKE_KEY_NAME")

    def test_kp_subtract_lowercase_is_handled(self):
        """Lowercase kp_subtract is in the map, so it resolves correctly."""
        self.assertEqual(self.backend._map_key("kp_subtract"), "KP_Subtract")

    def test_xf86_lowercase_is_handled(self):
        self.assertEqual(self.backend._map_key("xf86audiomute"), "XF86AudioMute")

    # ── Standard keysym passthrough ──

    def test_f13_accepted(self):
        self.assertEqual(self.backend._map_key("F13"), "F13")

    def test_page_up_accepted(self):
        self.assertEqual(self.backend._map_key("Page_Up"), "Page_Up")

    def test_control_r_accepted(self):
        self.assertEqual(self.backend._map_key("Control_R"), "Control_R")

    def test_shift_r_accepted(self):
        self.assertEqual(self.backend._map_key("Shift_R"), "Shift_R")

    def test_alt_r_accepted(self):
        self.assertEqual(self.backend._map_key("Alt_R"), "Alt_R")

    def test_xf86_audio_lower_volume_accepted(self):
        self.assertEqual(self.backend._map_key("XF86AudioLowerVolume"),
                         "XF86AudioLowerVolume")


class TestBackendImportWithoutX11(unittest.TestCase):
    """Verify desktop module imports without libX11 or DISPLAY."""

    def setUp(self):
        import subprocess, os, sys
        self._env = {k: v for k, v in os.environ.items()
                     if k not in ("DISPLAY", "XAUTHORITY")}
        self._python = sys.executable

    def _run_import_test(self, code):
        """Run *code* in a subprocess with no DISPLAY."""
        import subprocess
        p = subprocess.run(
            [self._python, "-c", code],
            capture_output=True, text=True,
            env=self._env,
            timeout=10,
        )
        return p

    def test_import_without_display(self):
        p = self._run_import_test(
            "from yyr4_linux_control.execution.desktop import "
            "UnavailableDesktopInputBackend, XDoToolDesktopInputBackend; "
            "print('OK')"
        )
        self.assertEqual(p.returncode, 0, f"stderr: {p.stderr}")
        self.assertIn("OK", p.stdout)

    def test_validate_without_display(self):
        p = self._run_import_test(
            "from yyr4_linux_control.control.config import load_control_config_from_file; "
            "from pathlib import Path; "
            "c = load_control_config_from_file(Path('examples/yyr4-control-from-20260711-backup.toml')); "
            "assert c.schema_version == 2; "
            "print('VALIDATE OK')"
        )
        self.assertEqual(p.returncode, 0, f"stderr: {p.stderr}")
        self.assertIn("VALIDATE OK", p.stdout)

    def test_dry_run_without_display(self):
        p = self._run_import_test(
            "from yyr4_linux_control.control.config import load_control_config_from_file; "
            "from yyr4_linux_control.control.actions import ActionResolver, DryRunExecutor; "
            "from yyr4_linux_control.control.models import OfficialControl, OfficialControlEvent; "
            "from yyr4_linux_control.domain.events import ControlPhase; "
            "from pathlib import Path; "
            "c = load_control_config_from_file(Path('examples/yyr4-control-from-20260711-backup.toml')); "
            "p = c.profiles[c.default_profile]; "
            "r = ActionResolver(config=p.layers['general'].controls); "
            "e = OfficialControlEvent(control=OfficialControl.A1, phase=ControlPhase.DOWN, timestamp_ns=0); "
            "plan = r.resolve(e); "
            "assert plan.resolution_status.name == 'CONFIGURED'; "
            "print('DRY-RUN OK')"
        )
        self.assertEqual(p.returncode, 0, f"stderr: {p.stderr}")
        self.assertIn("DRY-RUN OK", p.stdout)

    def test_unavailable_backend_without_display(self):
        p = self._run_import_test(
            "from yyr4_linux_control.execution.desktop import UnavailableDesktopInputBackend; "
            "b = UnavailableDesktopInputBackend(); "
            "assert b.availability() is False; "
            "print('UNAVAILABLE OK')"
        )
        self.assertEqual(p.returncode, 0, f"stderr: {p.stderr}")
        self.assertIn("UNAVAILABLE OK", p.stdout)

    def test_import_without_libx11(self):
        """Import should succeed even with libX11 unavailable
        (simulated by mocking find_library)."""
        import textwrap
        code = textwrap.dedent("""\
            from unittest.mock import patch
            with patch('ctypes.util.find_library', return_value=None):
                from yyr4_linux_control.execution.desktop import (
                    UnavailableDesktopInputBackend,
                    XDoToolDesktopInputBackend,
                )
                print('NO-LIBX11 OK')
        """)
        p = self._run_import_test(code)
        self.assertEqual(p.returncode, 0, f"stderr: {p.stderr}")
        self.assertIn("NO-LIBX11 OK", p.stdout)


class TestRecordingBackendExecution(unittest.TestCase):
    """Exercise all 24 controls through ActionExecutionEngine with recording backends."""

    @classmethod
    def setUpClass(cls):
        from yyr4_linux_control.control.config import load_control_config_from_file
        cls.config = load_control_config_from_file(
            Path("examples/yyr4-control-from-20260711-backup.toml"),
        )

    def _make_engine(self):
        from yyr4_linux_control.execution.engine import ActionExecutionEngine
        return ActionExecutionEngine(
            desktop_backend=_RecordingDesktopBackend(),
            command_runner=_NoOpCommandRunner(),
            delay_backend=_FakeDelayBackend(),
            debug_log_backend=_NoOpDebugBackend(),
        )

    def test_all_24_controls_execute_successfully(self):
        from yyr4_linux_control.control.models import OfficialControl, OfficialControlEvent
        from yyr4_linux_control.control.actions import LayeredActionResolver
        from yyr4_linux_control.domain.events import ControlPhase
        import asyncio

        engine = self._make_engine()
        resolver = LayeredActionResolver(config=self.config)

        for ctrl in OfficialControl:
            event = OfficialControlEvent(control=ctrl, phase=ControlPhase.DOWN, timestamp_ns=0)
            plan = resolver.resolve(event, self.config.default_profile, self.config.initial_layer)
            self.assertEqual(plan.resolution_status.name, "CONFIGURED",
                             f"{ctrl.value} not CONFIGURED")

            result = asyncio.run(engine.execute(plan))
            self.assertEqual(result.execution_status.name, "SUCCESS",
                             f"{ctrl.value} execution failed: {result.execution_status}")
            self.assertEqual(result.completed_steps, result.total_steps,
                             f"{ctrl.value}: {result.completed_steps}/{result.total_steps} steps")

    def test_a6_macro_exact_execution_sequence(self):
        from yyr4_linux_control.control.models import OfficialControl, OfficialControlEvent
        from yyr4_linux_control.control.actions import LayeredActionResolver
        from yyr4_linux_control.domain.events import ControlPhase
        import asyncio

        engine = self._make_engine()
        resolver = LayeredActionResolver(config=self.config)

        event = OfficialControlEvent(control=OfficialControl.A6,
                                     phase=ControlPhase.DOWN, timestamp_ns=0)
        plan = resolver.resolve(event, self.config.default_profile, self.config.initial_layer)
        result = asyncio.run(engine.execute(plan))

        self.assertEqual(result.total_steps, 11)
        self.assertEqual(result.completed_steps, 11)
        self.assertEqual(result.execution_status.name, "SUCCESS")

        # Verify the key sequence sent to desktop backend
        backend = engine.desktop_backend
        self.assertEqual(len(backend.calls), 6)

        expected_calls = [
            ("LSHIFT", "ENTER"),
            ("KP_Subtract",),
            ("KP_Subtract",),
            ("KP_Subtract",),
            ("LSHIFT", "ENTER"),
            ("LSHIFT", "ENTER"),
        ]
        for i, (actual, expected) in enumerate(zip(backend.calls, expected_calls)):
            self.assertEqual(actual, expected,
                             f"Step {i}: expected {expected}, got {actual}")

    def test_a6_delay_sequence(self):
        from yyr4_linux_control.control.models import OfficialControl, OfficialControlEvent
        from yyr4_linux_control.control.actions import LayeredActionResolver
        from yyr4_linux_control.domain.events import ControlPhase
        import asyncio

        engine = self._make_engine()
        resolver = LayeredActionResolver(config=self.config)

        event = OfficialControlEvent(control=OfficialControl.A6,
                                     phase=ControlPhase.DOWN, timestamp_ns=0)
        plan = resolver.resolve(event, self.config.default_profile, self.config.initial_layer)
        asyncio.run(engine.execute(plan))

        delay_backend = engine.delay_backend
        self.assertEqual(len(delay_backend.delays), 5)
        self.assertEqual(delay_backend.delays, [100, 20, 20, 100, 20])

    def test_no_command_runner_calls(self):
        from yyr4_linux_control.control.models import OfficialControl, OfficialControlEvent
        from yyr4_linux_control.control.actions import LayeredActionResolver
        from yyr4_linux_control.domain.events import ControlPhase
        import asyncio

        engine = self._make_engine()
        resolver = LayeredActionResolver(config=self.config)

        for ctrl in OfficialControl:
            event = OfficialControlEvent(control=ctrl, phase=ControlPhase.DOWN, timestamp_ns=0)
            plan = resolver.resolve(event, self.config.default_profile, self.config.initial_layer)
            asyncio.run(engine.execute(plan))

        self.assertEqual(engine.command_runner.call_count, 0,
                         "CommandRunner was called — should not happen in this config")

    def test_no_text_input_calls(self):
        from yyr4_linux_control.control.models import OfficialControl, OfficialControlEvent
        from yyr4_linux_control.control.actions import LayeredActionResolver
        from yyr4_linux_control.domain.events import ControlPhase
        import asyncio

        engine = self._make_engine()
        resolver = LayeredActionResolver(config=self.config)

        for ctrl in OfficialControl:
            event = OfficialControlEvent(control=ctrl, phase=ControlPhase.DOWN, timestamp_ns=0)
            plan = resolver.resolve(event, self.config.default_profile, self.config.initial_layer)
            asyncio.run(engine.execute(plan))

        self.assertEqual(engine.desktop_backend.text_calls, 0,
                         "Text input was called — should not happen in this config")

    def test_backend_key_normalization_applied_in_execution(self):
        """Verify that keys passed to the recording backend are the
        config-original tokens (normalization happens downstream in xdotool)."""
        from yyr4_linux_control.control.models import OfficialControl, OfficialControlEvent
        from yyr4_linux_control.control.actions import LayeredActionResolver
        from yyr4_linux_control.domain.events import ControlPhase
        import asyncio

        engine = self._make_engine()
        resolver = LayeredActionResolver(config=self.config)

        # Test a few representative controls
        test_controls = [
            (OfficialControl.A1, ("ESC",)),
            (OfficialControl.A3, ("LCTRL", "LSHIFT", "END")),
            (OfficialControl.AL, ("XF86MonBrightnessDown",)),
            (OfficialControl.BL, ("KP_Divide",)),
            (OfficialControl.DL, ("LCTRL", "MINUS")),
        ]
        for ctrl, expected_keys in test_controls:
            event = OfficialControlEvent(control=ctrl, phase=ControlPhase.DOWN, timestamp_ns=0)
            plan = resolver.resolve(event, self.config.default_profile, self.config.initial_layer)
            asyncio.run(engine.execute(plan))

            last_call = engine.desktop_backend.calls[-1]
            self.assertEqual(last_call, expected_keys,
                             f"{ctrl.value}: expected {expected_keys}, got {last_call}")

    def test_no_real_subprocess_or_hardware_access(self):
        """All 24 controls execute through Recording backend without
        any real subprocess or hardware access."""
        from yyr4_linux_control.control.models import OfficialControl, OfficialControlEvent
        from yyr4_linux_control.control.actions import LayeredActionResolver
        from yyr4_linux_control.domain.events import ControlPhase
        import asyncio

        engine = self._make_engine()
        resolver = LayeredActionResolver(config=self.config)

        for ctrl in OfficialControl:
            event = OfficialControlEvent(control=ctrl,
                                         phase=ControlPhase.DOWN, timestamp_ns=0)
            plan = resolver.resolve(event, self.config.default_profile,
                                   self.config.initial_layer)
            result = asyncio.run(engine.execute(plan))
            self.assertEqual(result.execution_status.name, "SUCCESS")

        self.assertGreater(len(engine.desktop_backend.calls), 0,
                           "Desktop backend recorded no calls")
        self.assertEqual(engine.command_runner.call_count, 0,
                         "Real subprocess was called")


# ── Recording/mock backends ──

class _RecordingDesktopBackend:
    """Records send_hotkey calls without executing real xdotool."""

    def __init__(self):
        self.calls = []
        self.text_calls = 0

    def availability(self):
        return True

    async def send_hotkey(self, keys):
        self.calls.append(keys)

    async def type_text(self, value):
        self.text_calls += 1


class _NoOpCommandRunner:
    """Never calls real subprocess."""

    def __init__(self):
        self.call_count = 0

    async def run(self, argv, timeout_seconds=None):
        self.call_count += 1
        return (0, b"", b"")


class _FakeDelayBackend:
    """Records delay values without actually sleeping."""

    def __init__(self):
        self.delays = []

    async def delay(self, milliseconds):
        self.delays.append(milliseconds)


class _NoOpDebugBackend:
    def emit(self, message):
        pass


if __name__ == "__main__":
    unittest.main()
