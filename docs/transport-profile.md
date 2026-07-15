# Transport Profile

## Purpose

The YYR4 keypad natively produces raw keystrokes according to its Windows configuration. To ensure `yyr4d` can securely and uniquely identify the 24 physical controls without conflicting with the user's desktop environment or regular typing, we translate them into an intermediate **neutral Transport Profile**.

This is achieved by mapping the 12 mechanical keys to `F13`–`F24`, and the 12 encoder positions (3 per encoder × 4 encoders) to `Shift + F13`–`Shift + F24`.

**Authority**: The canonical transport mapping is defined in `src/yyr4_linux_control/transport/codebook.py` (`DEFAULT_CODEBOOK`). This document is a derived human-readable reference.

## Development State

- **Current Milestone**: M4 (Linux integration and deployment)
- **Current hardware state**: The user's YYR4 is configured with their actual everyday macros and key bindings. **The device does NOT currently output the neutral Transport Profile codes.**
- **Parser state**: The `TransportParser` and `Codebook` are fully implemented and tested against offline anonymized event fixtures (`tests/fixtures/m010_transport_streams.json`) and programmatic assertions.
- **Next hardware step**: The user must preserve their current hardware mapping, then re-import the neutral Transport Profile JSON configuration before real-device end-to-end validation.

## Official Control Set

The project recognizes exactly **24 official physical controls**:

| Category | Official Names | Count |
|---|---|---|
| Mechanical Keys | A1, A2, A3, A4, A5, A6, A7, A8, A9, A10, A11, A12 | 12 |
| Encoder E01 | AL (CounterClockwise), AP (Press), AR (Clockwise) | 3 |
| Encoder E02 | BL (CounterClockwise), BP (Press), BR (Clockwise) | 3 |
| Encoder E03 | CL (CounterClockwise), CP (Press), CR (Clockwise) | 3 |
| Encoder E04 | DL (CounterClockwise), DP (Press), DR (Clockwise) | 3 |
| **Total** | | **24** |

This set is enforced by `OfficialControl` enum and `_OFFICIAL_CONTROL_NAMES` frozenset in `src/yyr4_linux_control/control/models.py`.

## Complete Neutral Transport Mapping Table

### Mechanical Keys (A1–A12)

Each key produces a single unmodified F-key press/release pair.

| Official | Control ID | evdev Code | Modifiers | Press Sequence | Release Sequence |
|---|---|---|---|---|---|
| A1 | `button.k01` | `KEY_F13` | none | F13↓ | F13↑ |
| A2 | `button.k02` | `KEY_F14` | none | F14↓ | F14↑ |
| A3 | `button.k03` | `KEY_F15` | none | F15↓ | F15↑ |
| A4 | `button.k04` | `KEY_F16` | none | F16↓ | F16↑ |
| A5 | `button.k05` | `KEY_F17` | none | F17↓ | F17↑ |
| A6 | `button.k06` | `KEY_F18` | none | F18↓ | F18↑ |
| A7 | `button.k07` | `KEY_F19` | none | F19↓ | F19↑ |
| A8 | `button.k08` | `KEY_F20` | none | F20↓ | F20↑ |
| A9 | `button.k09` | `KEY_F21` | none | F21↓ | F21↑ |
| A10 | `button.k10` | `KEY_F22` | none | F22↓ | F22↑ |
| A11 | `button.k11` | `KEY_F23` | none | F23↓ | F23↑ |
| A12 | `button.k12` | `KEY_F24` | none | F24↓ | F24↑ |

### Encoders (AL/AP/AR – DL/DP/DR)

Each encoder position produces `KEY_LEFTSHIFT` + an F-key. No other modifier keys are used.

| Official | Control ID | evdev Code | Modifiers | Press Sequence | Release Sequence |
|---|---|---|---|---|---|
| AL | `encoder.e01.counterclockwise` | `KEY_F13` | `KEY_LEFTSHIFT` | LSHIFT↓ → F13↓ | (see Release Order) |
| AP | `encoder.e01.press` | `KEY_F14` | `KEY_LEFTSHIFT` | LSHIFT↓ → F14↓ | (see Release Order) |
| AR | `encoder.e01.clockwise` | `KEY_F15` | `KEY_LEFTSHIFT` | LSHIFT↓ → F15↓ | (see Release Order) |
| BL | `encoder.e02.counterclockwise` | `KEY_F16` | `KEY_LEFTSHIFT` | LSHIFT↓ → F16↓ | (see Release Order) |
| BP | `encoder.e02.press` | `KEY_F17` | `KEY_LEFTSHIFT` | LSHIFT↓ → F17↓ | (see Release Order) |
| BR | `encoder.e02.clockwise` | `KEY_F18` | `KEY_LEFTSHIFT` | LSHIFT↓ → F18↓ | (see Release Order) |
| CL | `encoder.e03.counterclockwise` | `KEY_F19` | `KEY_LEFTSHIFT` | LSHIFT↓ → F19↓ | (see Release Order) |
| CP | `encoder.e03.press` | `KEY_F20` | `KEY_LEFTSHIFT` | LSHIFT↓ → F20↓ | (see Release Order) |
| CR | `encoder.e03.clockwise` | `KEY_F21` | `KEY_LEFTSHIFT` | LSHIFT↓ → F21↓ | (see Release Order) |
| DL | `encoder.e04.counterclockwise` | `KEY_F22` | `KEY_LEFTSHIFT` | LSHIFT↓ → F22↓ | (see Release Order) |
| DP | `encoder.e04.press` | `KEY_F23` | `KEY_LEFTSHIFT` | LSHIFT↓ → F23↓ | (see Release Order) |
| DR | `encoder.e04.clockwise` | `KEY_F24` | `KEY_LEFTSHIFT` | LSHIFT↓ → F24↓ | (see Release Order) |

## Contract Properties

These properties are verified by automated tests (`tests/test_codebook.py`, `tests/test_transport_parser.py`):

1. **Count**: Exactly 24 mappings, matching the 24 official controls.
2. **One-to-one**: Each `OfficialControl` ↔ exactly one `TransportCode` (and vice versa). No duplicate vendor names, control IDs, or transport code strings.
3. **F13–F24 completeness**: All 12 F-keys (`KEY_F13` through `KEY_F24`) are used.
4. **Modifier purity**: Only `KEY_LEFTSHIFT` is used as a modifier. No `KEY_RIGHTSHIFT`, `KEY_LEFTCTRL`, `KEY_LEFTALT`, or other modifiers appear in any mapping.
5. **Button simplicity**: All 12 button controls use zero modifiers.
6. **Encoder consistency**: All 12 encoder controls use exactly `(KEY_LEFTSHIFT,)` as the modifier tuple.
7. **No ambiguity**: An unmodified F13 always resolves to A1 (button), never to AL (encoder). A Shift+F13 always resolves to AL, never to A1.
8. **No false positives**: Regular keys (A–Z, digits, etc.) and non-F13–F24 F-keys (F1–F12) produce zero `ControlEvent` output.
9. **No device dependency**: The codebook does not reference event node paths (`/dev/input/eventN`), USB serial numbers, or udev properties.
10. **No desktop collision risk**: F13–F24 are rarely used by desktop applications, making them ideal neutral transport codes.

## Press and Release Semantics

### Normal Press/Release

- `DOWN` (value=1): The F-key is registered. A `ControlEvent` with phase `DOWN` is emitted immediately.
- `UP` (value=0): The F-key is released. A `ControlEvent` with phase `UP` is emitted.

### Repeat Events (value=2)

The YYR4 firmware emits `value=2` (auto-repeat) events during sustained presses. The parser **ignores all repeat events**. Only explicit `DOWN` and `UP` events drive control recognition. Tap/hold logic is deferred to the higher-level action engine.

### Shift Release Order (Device Quirk)

The YYR4 firmware exhibits a non-standard modifier release sequence:

```
LSHIFT↓ → Fxx↓ → LSHIFT↑ → Fxx↑
```

The standard behavior would be:

```
LSHIFT↓ → Fxx↓ → Fxx↑ → LSHIFT↑
```

The parser tolerates this quirk: the logical `DOWN` is emitted as soon as the F-key arrives within an active Shift window. The premature `LSHIFT↑` does not affect the pending UP event for the F-key. After both the Shift and the F-key are released, the Shift state is correctly cleared.

### Modifier Timeout

If `KEY_LEFTSHIFT` is pressed but no matching F-key arrives within `modifier_timeout_ms` (default: 100ms), the Shift is discarded (timeout). A subsequent unmodified F-key in that window resolves to a button, not an encoder.

## Duplicate and Orphan Handling

- **Duplicate DOWN**: If an F-key is pressed again while already active, the second DOWN is rejected as an error. The original active control is preserved.
- **Orphan UP**: If an F-key UP arrives without a corresponding active control, it is rejected as an error.
- **Reset**: The parser can be reset, which synthesizes UP events for all currently active controls and clears all state.

## Two Operating Modes

### Mode A: Daemon-Managed Neutral Transport Mode (OFFICIALLY SUPPORTED)

This is the project's designated canonical mode for `yyr4d`.

**Hardware layer**:
- The YYR4 is loaded with the neutral Transport Profile JSON configuration.
- Each physical control emits a stable, unique, neutral transport code (F13–F24 ± LSHIFT).
- The device does NOT directly emit copy, paste, text, shell commands, or application macros.

**Software layer**:
- `Codebook` identifies each transport code as an `OfficialControl`.
- `LayeredActionResolver` maps controls to actions via the user's `config.toml` (Profile + Layer).
- `ActionExecutionEngine` executes the resolved actions.

**Advantages**:
- No double execution (hardware macro + software action).
- Layers and Profiles managed entirely in `config.toml` — version-controlled, validated, reviewable.
- Linux environment operates independently of the Windows configuration software.
- Configuration can be backed up, migrated, and rolled back.
- Device-agnostic: the same transport profile works regardless of user-specific action bindings.

### Mode B: Hardware-Direct Macro Mode (CURRENT USER STATE, NOT SUPPORTED)

The user's YYR4 is currently in this mode.

**What the hardware emits**:
- Regular keys (A–Z, 0–9, punctuation)
- Shortcuts (Ctrl+C, Ctrl+V, etc.)
- Text strings (via macro playback)
- Mouse actions
- Application-specific macros

**Why this mode is NOT supported as a Codebook target**:
- The existing `Codebook` only recognizes F13–F24 ± LSHIFT combinations.
- Hardware macros in Mode B produce arbitrary sequences of EV_KEY events that the parser does not map to any official control.
- Events may directly affect the desktop before `yyr4d` can process them (no `EVIOCGRAB` in current design).
- A single macro press may emit multiple key events interleaved with timed delays, making deterministic control identification impossible without macro awareness.
- The same physical control may produce different event sequences depending on the active hardware layer.
- Even with a configurable codebook, raw desktop side effects would persist without exclusive device grab.

**Important**: Mode B is NOT a hardware defect or error state. It is simply a different configuration of the same device. The user intentionally configured it this way for their daily workflow. We must preserve this configuration before any transition.

## Why Arbitrary Macros Cannot Replace the Neutral Transport

1. **Non-deterministic**: A macro may vary in timing and content between executions.
2. **Multi-event**: A single physical press produces multiple EV_KEY events, breaking the one-to-one mapping.
3. **Desktop collision**: Common keys (Ctrl+C, letters) conflict with normal keyboard input.
4. **Context-dependent**: The meaning of key sequences depends on application focus.
5. **Parse ambiguity**: Without knowing the macro definition, the parser cannot distinguish macro events from genuine keyboard input.
6. **No suppression**: Without `EVIOCGRAB`, macro events reach the desktop simultaneously with any daemon processing.

A configurable codebook or `EVIOCGRAB`-based exclusive grab are valid future considerations but are **not part of this milestone**.

## User Current Mapping Preservation

### Before Overwriting the YYR4 Configuration

The user MUST preserve their current hardware mapping before loading the neutral Transport Profile. This ensures no data loss.

**Preservation steps:**

1. **Export from the YYR4 Windows configuration software** (if supported):
   - Locate the profile export/save function.
   - Export all profiles to a file (preferably JSON or the software's native format).
   - Save the export to a backed-up location outside the repository.

2. **If export is not available, manually document each control**:
   - For each of the 12 keys (A1–A12), record:
     - Current action type (key, shortcut, text, macro, mouse).
     - Exact keys or text produced.
     - Modifier keys used.
     - If a macro: step-by-step sequence including delays.
   - For each of the 4 encoders (AL/AP/AR through DL/DP/DR), record:
     - CounterClockwise (L) action.
     - Press (P) action.
     - Clockwise (R) action.
   - Record any active hardware layers and their per-control bindings.
   - Take screenshots of each configuration page as visual backup.

3. **After documentation, translate to schema v2 `config.toml`**:
   - Map each physical control to the corresponding `OfficialControl` name.
   - Convert each action to the appropriate action type (`hotkey`, `text`, `command`, `macro`, `noop`).
   - Organize actions into Profiles and Layers matching the original hardware layout.
   - Validate with `yyr4ctl validate`.

4. **DO NOT overwrite the device until all mapping is preserved.**

### Migration Workflow (Hardware → Software)

1. Document current hardware mapping (as above).
2. Save the exported JSON profile outside the repository.
3. Create a `config.toml` that replicates the current behavior in software.
4. Validate the config: `yyr4ctl validate --config config.toml`
5. Dry-run critical controls: `yyr4ctl dry-run --config config.toml A1`
6. Load the neutral Transport Profile onto the YYR4.
7. Start `yyr4d` with the new `config.toml`.
8. Verify one control at a time.
9. If any control fails, stop `yyr4d`, fix the config, and retry.
10. Store the backup JSON configuration permanently.

### Recovery and Rollback

To return the YYR4 to its previous state:
1. Stop `yyr4d`: `systemctl --user stop yyr4d`
2. Re-import the original user configuration (backup JSON) into the device via the Windows configuration software.
3. The device returns to Mode B immediately.

## One-Time Final Hardware Acceptance Plan

When the user is ready for end-to-end acceptance (Milestone 6):

1. Load the neutral Transport Profile onto the YYR4.
2. Start `yyr4d` with a standard test `config.toml`.
3. Execute the minimal acceptance sequence:
   - Press one button (e.g., A1) → verify action executes.
   - Rotate one encoder left (e.g., AL) → verify action.
   - Press one encoder (e.g., AP) → verify action.
   - Rotate one encoder right (e.g., AR) → verify action.
   - Trigger a layer switch → verify context changes.
   - Execute a macro → verify all steps run.
   - Restart daemon → verify recovery.
   - Unplug/replug device → verify reconnection.
4. Only expand testing if a specific anomaly is observed.
5. Do not repeat full 24-operation testing unless a defect is found.

## Current Limitations and Future Considerations

| Item | Status | Notes |
|---|---|---|
| Neutral Transport Profile | IMPLEMENTED | Codebook + Parser complete; auto-tested |
| Hardware currently in neutral mode | NO | User's device is in Mode B |
| Configurable Codebook | Future consideration | Would allow custom transport mappings |
| EVIOCGRAB (exclusive device grab) | Future consideration | Required to suppress raw desktop side effects in Mode B |
| Macro reverse inference | Out of scope | Not planned; migrate to config.toml instead |
| Auto-burning Transport Profile | Out of scope | Requires Windows configuration tool or reverse-engineered protocol |

## Automated Test Coverage

The transport contract is locked by the following test modules:

- **`tests/test_codebook.py`** — Structure: exact count, uniqueness, F13–F24 completeness, encoder/button mapping verification.
- **`tests/test_transport_parser.py`** — Behavior: 19 scenarios covering normal press/release, repeats, shift release order, timeout, orphan events, duplicates, multi-key rolls, time regression, reset.
- **`tests/test_observation_pipeline.py`** — Integration: end-to-end event pipeline with transport fixture events.
- **`tests/test_public_api.py`** — Public API smoke test with `DEFAULT_CODEBOOK`.

All tests run without hardware access, network, systemd, udev, or desktop input.

## Security and Boundaries

We do not reverse engineer or claim to have cracked the YYR4 proprietary firmware, CDC serial, or RGB protocols. We only read and interpret the emitted Linux `evdev` stream. The transport profile relies on the fact that F13–F24 are defined in the USB HID specification and are rarely used by desktop applications, making them safe for exclusive device signaling.
