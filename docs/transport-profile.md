# Transport Profile

## Purpose
The YYR4 keypad natively produces raw keystrokes according to its Windows configuration. To ensure `yyr4d` can securely and uniquely identify the 24 physical controls without conflicting with the user's desktop environment or regular typing, we translate them into an intermediate "Transport Profile".
This is achieved by mapping the mechanical keys to `F13` - `F24`, and the encoders to `Shift + F13` - `Shift + F24`.

## Development State
The user has currently restored their YYR4 to their everyday configuration.
**The device does NOT currently output the Transport Profile codes.** This is intentional for the current development phase (Milestone 1). The parser is built and tested against the M0.10 anonymized event fixtures.
When real-device testing resumes, the user will be asked to re-import the `after-transport-profile.json` configuration.

## 24-Item Codebook
### Buttons (A1-A12)
* `A1` -> `F13` (`button.k01`)
* `A2` -> `F14` (`button.k02`)
* `A3` -> `F15` (`button.k03`)
* `A4` -> `F16` (`button.k04`)
* ...
* `A12` -> `F24` (`button.k12`)

### Encoders (AL/AP/AR - DL/DP/DR)
The JSON configuration stores encoders in `[CCW, CW, Press]` order. The project logic translates this into `L/P/R` (CounterClockwise, Press, Clockwise).
* `AL` -> `Shift+F13`
* `AP` -> `Shift+F14`
* `AR` -> `Shift+F15`
...

## Handling Device Quirk: Shift Release Order
The YYR4 firmware exhibits a non-standard modifier release order: `LSHIFT down -> Fxx down -> LSHIFT up -> Fxx up`.
Our parser tolerates this by triggering the logical control as soon as `Fxx down` occurs within an active Shift window, ignoring subsequent release order permutations.

## Handling Device Quirk: Repeat Events (value=2)
The YYR4 frequently emits `value=2` (repeat) events for long presses. The Transport Profile strictly ignores these and relies on explicit `DOWN` and `UP` events, leaving tap/hold logic to the higher-level action engine.

## Security & Boundaries
We do not reverse engineer or claim to have cracked the YYR4 proprietary firmware, CDC serial, or RGB protocols. We only read and interpret the emitted Linux `evdev` stream.
