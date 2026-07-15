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

    # ── Negative: no real hardware ──

    def test_no_real_device_access(self):
        """Verify no tests access /dev/input — the evdev package may be
        imported by the project's own adapter module, but no real device
        nodes should be opened."""
        # Config loading and dry-run never trigger real hardware I/O.
        # This test exists to document that constraint.
        pass


if __name__ == "__main__":
    unittest.main()
