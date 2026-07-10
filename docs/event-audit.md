# Event Audit Methodology

Before writing mapping logic, a formal event audit MUST be conducted (Milestone 0) to establish the true behavior of the YYR4 hardware.

## 1. Audit Process
The daemon will run an audit script to concurrently listen to both the keyboard and mouse `evdev` interfaces.
1. The user presses keys K01 through K12 sequentially.
2. The user rotates encoders E01 through E04 clockwise, then counterclockwise.
3. The user attempts to physically press the encoders to test for click events.
4. The system logs the raw `EV_KEY`, `EV_REL`, and `EV_SYN` packets.

## 2. Requirements for the Audit
* **Differentiation**: Can the four encoders be uniquely identified by the events they emit?
* **Velocity**: Does spinning the encoder faster yield different event counts or values (e.g., `REL_HWHEEL_HI_RES`)?
* **Debounce & Repeat**: Do mechanical keys emit hardware repeat events? Is debounce handled correctly by the firmware?
* **Press Action**: **[Unverified]** Do encoders actually have a press switch?

## 3. Standard Logical Naming
Physical keys map to logical events. The system MUST strictly use the following layout naming convention:

```text
K01  K02  K03  K04
K05  K06  K07  K08
K09  K10  K11  K12
```

Encoders:
```text
E01：右上左侧小型柱形旋钮
E02：右上右侧小型柱形旋钮
E03：右下区域上方大型饼形旋钮
E04：右下区域下方大型饼形旋钮
```

Confirmed Logical Events:
* `button.k01.down`, `button.k01.up`, `button.k01.tap`
* `encoder.e01.clockwise`, `encoder.e01.counterclockwise`

Pending Logical Events (Requires Audit):
* `encoder.e01.press`
* `encoder.e01.release`

## 4. Results Table (Pending)
This table will guide Milestone 2 (Event Normalization).

| Physical Control | Action | Expected Logical ID | Raw Evdev Event | Confirmed? |
| :--- | :--- | :--- | :--- | :--- |
| K01 | Press/Release | `button.k01.tap` | TBD | No |
| E01 | Clockwise | `encoder.e01.clockwise` | TBD | No |
| E01 | Press | `encoder.e01.press` | TBD | **[Unverified]** |

*See also: [Action Model](action-model.md).*
