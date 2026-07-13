# YYR4 Validation Ledger

This document acts as the definitive source of truth for hardware and protocol validation status.

## 1. Scope and evidence classes

To avoid endlessly re-testing the hardware on every hypothesis, evidence is classified as follows:

*   **Protocol mapping evidence**: The logical translation from raw packets to parsed control identities (e.g., F13 -> A1).
*   **Parser fixture evidence**: Offline JSON files capturing raw events used for automated unit tests.
*   **Automated regression evidence**: Python `unittest` suites ensuring software behaves deterministically based on fixtures.
*   **Real-device identity evidence**: Proven ability to correctly find the YYR4 sysfs paths and properties locally via `udev`.
*   **Real-device permission evidence**: Verified OS-level access to the nodes (e.g., readable via `input` group).
*   **Real-device event-path evidence**: Success or failure reading live `evdev` raw packets using the `observe_probe` tool.
*   **Historical or incomplete evidence**: Test runs that failed due to software bugs or invalid configurations, providing context but not proof.

## 2. Official physical naming

All user-facing logs and documentation MUST use the official names.

| Official Name | Internal / Historical Name | Hardware Role |
| :--- | :--- | :--- |
| **A1-A12** | K01-K12 | 12 Mechanical Keys (Row-major 3x4 grid) |
| **AL/AP/AR** | E01-L/P/R (Top-left) | Rotary Encoder 1 (Left/Press/Right) |
| **BL/BP/BR** | E02-L/P/R (Top-right) | Rotary Encoder 2 (Left/Press/Right) |
| **CL/CP/CR** | E03-L/P/R (Bottom-top) | Rotary Encoder 3 (Left/Press/Right) |
| **DL/DP/DR** | E04-L/P/R (Bottom-bottom) | Rotary Encoder 4 (Left/Press/Right) |

**Official Default Transport Mapping (evdev perspective):**
*   **A1-A12**: `KEY_F13` - `KEY_F24`
*   **AL/AP/AR**: `KEY_LEFTSHIFT` + `KEY_F13/F14/F15`
*   **BL/BP/BR**: `KEY_LEFTSHIFT` + `KEY_F16/F17/F18`
*   **CL/CP/CR**: `KEY_LEFTSHIFT` + `KEY_F19/F20/F21`
*   **DL/DP/DR**: `KEY_LEFTSHIFT` + `KEY_F22/F23/F24`

## 3. Validation matrix

| ID | Subject | Expected Behavior | Current Status | Evidence Class | Durable Evidence Location | Relevant Commit | Limitations |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| V001 | A1-A12 key mapping | Maps F13-F24 to A1-A12 Down/Up | VERIFIED_WITH_LIMITATIONS | Parser fixture evidence | `tests/fixtures/m010_transport_streams.json` | 2445c8e | Origin of fixture is not strictly verified from real hardware in Git history. |
| V002 | AL/AP/AR mapping | Maps Shift+F13-F15 to AL/AP/AR | VERIFIED_WITH_LIMITATIONS | Parser fixture evidence | `tests/fixtures/m010_transport_streams.json` | 2445c8e | Same as V001. |
| V003 | BL/BP/BR mapping | Maps Shift+F16-F18 to BL/BP/BR | VERIFIED_WITH_LIMITATIONS | Parser fixture evidence | `tests/fixtures/m010_transport_streams.json` | 2445c8e | Same as V001. |
| V004 | CL/CP/CR mapping | Maps Shift+F19-F21 to CL/CP/CR | VERIFIED_WITH_LIMITATIONS | Parser fixture evidence | `tests/fixtures/m010_transport_streams.json` | 2445c8e | Same as V001. |
| V005 | DL/DP/DR mapping | Maps Shift+F22-F24 to DL/DP/DR | VERIFIED_WITH_LIMITATIONS | Parser fixture evidence | `tests/fixtures/m010_transport_streams.json` | 2445c8e | Same as V001. |
| V006 | Shift pre-release | Modifiers released before key drop event gracefully | VERIFIED | Automated regression | `tests/test_transport_parser.py` | 2445c8e | None |
| V007 | Repeated events | EV_KEY repeats (value=2) are ignored | VERIFIED | Automated regression | `tests/test_transport_parser.py` | 2445c8e | None |
| V008 | Timeout/Reset | Modifiers timeout and reset correctly | VERIFIED | Automated regression | `tests/test_transport_parser.py` | 2445c8e | None |
| V009 | VID/PID Discovery | pyudev discovers 239a:80f4 devices | VERIFIED | Real-device identity | `.local/hardware-validation/identity-permission-*` | d60cb37 | Relies on local udev rules matching current session. |
| V010 | Descriptor spaces | Spaces are normalized to underscores in udev properties | VERIFIED | Real-device identity | `.local/hardware-validation/identity-permission-*` | 026a844 | Confirmed via local testing output logs. |
| V011 | Role identification | Keyboard/Mouse separated by `ID_INPUT_*` properties | VERIFIED | Real-device identity | `.local/hardware-validation/identity-permission-*` | 026a844 | Confirmed via local testing output logs. |
| V012 | Unique Identity | Same USB parent, specific interfaces pair uniquely | VERIFIED | Real-device identity | `.local/hardware-validation/identity-permission-*` | d60cb37 | Confirmed via local testing output logs. |
| V013 | Node read permission | Selected evdev nodes are readable by user | VERIFIED | Real-device permission | `.local/hardware-validation/identity-permission-*` | d60cb37 | Requires user in `input` group. |
| V014 | Daily Profile A1 EV_KEY positive control | A1 keypress yields > 0 raw EV_KEY events | VERIFIED | Real-device event-path | `.local/hardware-validation/daily-evkey-visible-*` | cacfa19 | Confirms evdev read path works for standard keys. |
| V015 | No-action Daily run | Daily profile run without user interaction | INVALID_TEST | Historical evidence | `.local/hardware-validation/daily-evkey-positive-*` | cacfa19 | Originally mislabeled as failed positive control. User did not press keys. |
| V016 | 1st Transport Probe AttributeError | Initial observe_probe crashed on diagnostics | INVALID_TEST | Historical evidence | `.local/hardware-validation/*` | d60cb37 | Software bug. |
| V017 | Fixed Transport EV_KEY run | Transport profile emitted 0 EV_KEY events | PARTIAL | Real-device event-path | `.local/hardware-validation/*` | 909c04c | Could mean Transport doesn't use EV_KEY, or other layers are filtering. |
| V018 | Full 24-op CLI verification | Test all 24 physical operations end-to-end | NOT_YET_VERIFIED | Pending | N/A | N/A | Requires resolution of Transport EV_KEY absence (V017). |

## 4. Retest triggers and rules

**No unnecessary retesting.** If an item is VERIFIED or VERIFIED_WITH_LIMITATIONS, do not retest it via manual hardware manipulation unless one of the following triggers occurs:

1.  Transport Parser semantics change significantly.
2.  `EvdevInputAdapter` reading logic changes.
3.  Discovery/Identity selection logic changes (requires udev/permission retest, not event retest).
4.  ProbeRunner event path changes.
5.  CLI profile modes are fundamentally altered.
6.  The device firmware or configuration is known to have changed.
7.  The existing evidence is proven to be invalid (e.g., simulated data mistaken for real data).
8.  A new target needs coverage that existing evidence does not cover.

"Just to be sure" is not a valid reason to request a hardware retest.
