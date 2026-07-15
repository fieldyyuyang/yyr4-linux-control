# Current Hardware Mapping — Migration from WinUI Backup

This document records the authoritative mapping from the user's current YYR4 hardware configuration (as preserved in the WinUI backup JSON) to the equivalent schema v2 software configuration for `yyr4d`.

## Authoritative Backup

- **Path**: `docs/WinUI/YYR4-driver-2.0.3-hardware-2.0.1-20260711-before-transport-profile.json`
- **SHA-256**: `c1c0c9aa761815321abfcc7f653883df06452e1091bdb392245f3bb41ef3724a`
- **Status**: Read-only. Never modified by any migration step.

## JSON Structure Verified

| Field | Type | Verified |
|---|---|---|
| `other_data` | dict (6 keys) | ✓ |
| `super_key_config_data` | list[2] (both empty) | ✓ |
| `open_file_config_data` | list[2] (both empty) | ✓ |
| `app_name` | list[8] | ✓ |
| `layer0` | list[2], each length 12 | ✓ |
| `layer1`–`layer7` | list[2], all empty | ✓ |
| `light_settings_data` | list[5] | ✓ (RGB, not migrated) |

## Hardware Layer Map

Only `layer0` (通用层) contains active mappings. Layers 1–7 (第二层 through 第八层) are all empty.

## Encoder Array Order

The WinUI JSON stores encoder positions per-encoder in CCW–CW–Press order:

```
layer0[1] indices by encoder:
  E01: [0]=AL(CCW), [1]=AR(CW), [2]=AP(Press)
  E02: [3]=BL(CCW), [4]=BR(CW), [5]=BP(Press)
  E03: [6]=CL(CCW), [7]=CR(CW), [8]=CP(Press)
  E04: [9]=DL(CCW), [10]=DR(CW), [11]=DP(Press)
```

The project uses L–P–R order (CCW–Press–CW). Migration performs explicit reordering.

## Complete Migration Matrix

### Mechanical Keys (A1–A12)

| Official | JSON Index | Original String | Semantics | Target Type | Target Keys / Steps | Delay(s) | Lossless? | Notes |
|---|---|---|---|---|---|---|---|---|
| A1 | layer0[0][0] | `ESC` | Escape key | hotkey | `["ESC"]` | — | ✓ |  |
| A2 | layer0[0][1] | `BACKSPACE` | Backspace key | hotkey | `["BACKSPACE"]` | — | ✓ |  |
| A3 | layer0[0][2] | `LCTRL+LSHIFT+END` | Ctrl+Shift+End | hotkey | `["LCTRL", "LSHIFT", "END"]` | — | ✓ |  |
| A4 | layer0[0][3] | `LCTRL+LSHIFT+HOME` | Ctrl+Shift+Home | hotkey | `["LCTRL", "LSHIFT", "HOME"]` | — | ✓ |  |
| A5 | layer0[0][4] | `LCTRL+E` | Ctrl+E | hotkey | `["LCTRL", "E"]` | — | ✓ |  |
| A6 | layer0[0][5] | `LSHIFT+ENTER Delay(100) KP_- Delay(20) KP_- Delay(20) KP_- Delay(100) LSHIFT+ENTER Delay(20) LSHIFT+ENTER` | Macro: Shift+Enter, 3× KP_Minus, 3× Shift+Enter with timed delays | macro | see A6 detail below | 100,20,20,100,20 | ✓ | Requires X11/xdotool for keypad minus |
| A7 | layer0[0][6] | `LALT+D` | Alt+D | hotkey | `["LALT", "D"]` | — | ✓ |  |
| A8 | layer0[0][7] | `LSHIFT+LCTRL+Z` | Ctrl+Shift+Z | hotkey | `["LSHIFT", "LCTRL", "Z"]` | — | ✓ |  |
| A9 | layer0[0][8] | `LCTRL+C` | Ctrl+C (copy) | hotkey | `["LCTRL", "C"]` | — | ✓ |  |
| A10 | layer0[0][9] | `LCTRL+V` | Ctrl+V (paste) | hotkey | `["LCTRL", "V"]` | — | ✓ |  |
| A11 | layer0[0][10] | `LSHIFT+LCTRL+C` | Ctrl+Shift+C | hotkey | `["LSHIFT", "LCTRL", "C"]` | — | ✓ |  |
| A12 | layer0[0][11] | `LSHIFT+LCTRL+V` | Ctrl+Shift+V | hotkey | `["LSHIFT", "LCTRL", "V"]` | — | ✓ |  |

### Encoder A (E01)

| Official | JSON Index | Original String | Semantics | Target Type | Target Keys | Lossless? | Notes |
|---|---|---|---|---|---|---|---|
| AL | layer0[1][0] | `屏幕亮度_减` | Screen brightness down | hotkey | `["XF86MonBrightnessDown"]` | ✓ | Requires X11 |
| AR | layer0[1][1] | `屏幕亮度_增` | Screen brightness up | hotkey | `["XF86MonBrightnessUp"]` | ✓ | Requires X11 |
| AP | layer0[1][2] | `LCTRL+DELETE` | Ctrl+Delete | hotkey | `["LCTRL", "DELETE"]` | ✓ |  |

### Encoder B (E02)

| Official | JSON Index | Original String | Semantics | Target Type | Target Keys | Lossless? | Notes |
|---|---|---|---|---|---|---|---|
| BL | layer0[1][3] | `KP_/` | Keypad divide | hotkey | `["KP_Divide"]` | ✓ | Requires X11, not regular slash |
| BR | layer0[1][4] | `KP_*` | Keypad multiply | hotkey | `["KP_Multiply"]` | ✓ | Requires X11, not regular asterisk |
| BP | layer0[1][5] | `静音` | Audio mute toggle | hotkey | `["XF86AudioMute"]` | ✓ | Requires X11 |

### Encoder C (E03)

| Official | JSON Index | Original String | Semantics | Target Type | Target Keys | Lossless? | Notes |
|---|---|---|---|---|---|---|---|
| CL | layer0[1][6] | `LEFT` | Left arrow | hotkey | `["LEFT"]` | ✓ |  |
| CR | layer0[1][7] | `RIGHT` | Right arrow | hotkey | `["RIGHT"]` | ✓ |  |
| CP | layer0[1][8] | `SPACE` | Space bar | hotkey | `["SPACE"]` | ✓ |  |

### Encoder D (E04)

| Official | JSON Index | Original String | Semantics | Target Type | Target Keys | Lossless? | Notes |
|---|---|---|---|---|---|---|---|
| DL | layer0[1][9] | `LCTRL+-` | Ctrl+Minus (zoom out) | hotkey | `["LCTRL", "MINUS"]` | ✓ |  |
| DR | layer0[1][10] | `LCTRL+=` | Ctrl+Equal (zoom in) | hotkey | `["LCTRL", "EQUAL"]` | ✓ |  |
| DP | layer0[1][11] | `ENTER` | Enter key | hotkey | `["ENTER"]` | ✓ |  |

## A6 Macro Detail

Original string:
```
LSHIFT+ENTER Delay(100) KP_- Delay(20) KP_- Delay(20) KP_- Delay(100) LSHIFT+ENTER Delay(20) LSHIFT+ENTER
```

Decomposed steps (exact order, timing, and key semantics preserved):

| Step | Type | Content | Delay Before |
|---|---|---|---|
| 1 | hotkey | LSHIFT + ENTER | — |
| 2 | delay | — | 100ms |
| 3 | hotkey | KP_Subtract | — |
| 4 | delay | — | 20ms |
| 5 | hotkey | KP_Subtract | — |
| 6 | delay | — | 20ms |
| 7 | hotkey | KP_Subtract | — |
| 8 | delay | — | 100ms |
| 9 | hotkey | LSHIFT + ENTER | — |
| 10 | delay | — | 20ms |
| 11 | hotkey | LSHIFT + ENTER | — |

**Delay sequence**: 100ms, 20ms, 20ms, 100ms, 20ms (5 delays, 2 distinct values)

**Integrity rules applied**:
- Three `KP_-` presses are NOT merged — each is a distinct key event
- 20ms delays are NOT removed — they control inter-key timing
- Three `LSHIFT+ENTER` occurrences are preserved at their exact positions
- No `TextAction` substitution — KP_Subtract is not a text character
- No shell command — this is pure keyboard input

## Migration Summary

| Metric | Count |
|---|---|
| Total official controls | 24 |
| Migrated to hotkey | 23 |
| Migrated to macro | 1 (A6) |
| BLOCKED | 0 |
| Hotkey actions total | 23 |
| Macro steps total | 11 (6 hotkey + 5 delay) |
| Requires X11/xdotool | 7 (brightness ×2, mute, KP_Divide, KP_Multiply, KP_Subtract ×3 in macro) |
| Wayland compatible (without Xwayland) | No (xdotool backend limitation) |

## Items Not Migrated

The following are hardware-driver-specific and are NOT included in the software config:

| Item | Reason |
|---|---|
| `light_settings_data` | RGB control — protocol unknown [Unverified] |
| `other_data` (auto_find_app, td_timeout, ht_timeout, one_opacity, one_flow, rgb_timeout) | Windows driver UI settings |
| `super_key_config_data` | Empty — no super key bindings |
| `open_file_config_data` | Empty — no file launch bindings |
| `app_name` | Preserved for reference only — maps to Profile/Layer names |

These remain fully preserved in the original backup JSON.

## Generated Configuration

The migrated schema v2 configuration is at:
`examples/yyr4-control-from-20260711-backup.toml`

**NOT deployed to** `~/.config/yyr4/config.toml`. The user must review and manually install.

## Compatibility Notes

1. **X11 dependency**: The xdotool backend requires X11 (`DISPLAY` env var). Wayland sessions are not supported by the current desktop backend.
2. **Keypad keys**: `KP_Divide`, `KP_Multiply`, `KP_Subtract` use xdotool key names. These are distinct from main-keyboard `/`, `*`, `-`.
3. **Media keys**: `XF86MonBrightnessDown`, `XF86MonBrightnessUp`, `XF86AudioMute` are standard X11 keysyms recognized by xdotool and most Linux desktop environments.
4. **Left modifiers**: The original config uses left-specific modifiers (LCTRL, LSHIFT, LALT). These are preserved in the migration. The xdotool backend lowercases them to `lctrl`, `lshift`, `lalt` which xdotool correctly maps to `Control_L`, `Shift_L`, `Alt_L`.
5. **MINUS/EQUAL**: Key names `MINUS` and `EQUAL` are used for the main keyboard `-` and `=` keys (as opposed to keypad variants). xdotool maps these to `minus` and `equal`.
