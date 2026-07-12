# Device Research Baseline

This document tracks the verified facts and unverified hypotheses regarding the YYR4 hardware.

## 1. Verified USB Identity
* **[Confirmed]** Vendor ID: `239a`
* **[Confirmed]** Product ID: `80f4`
* **[Confirmed]** Manufacturer String: `YOUYOU TEC.`
* **[Confirmed]** Product String: `YOUYOU Keyb_V2`
* **[Observed]** `udev` may normalize spaces in `ID_VENDOR` and `ID_MODEL` to underscores (`YOUYOU_TEC.` and `YOUYOU_Keyb_V2`). Original strings are available via USB parent sysfs attributes.

## 2. Observed Linux Interfaces
* **[Observed]** CDC ACM (Serial)
* **[Observed]** HID keyboard / mouse interfaces
* **[Observed]** `evdev` (keyboard / mouse)
* **[Observed]** `hidraw`
* **[Observed]** USB Audio class interface

*Warning*: Device paths like `/dev/input/eventN` or `/dev/hidrawN` are dynamically assigned per session. They MUST NOT be hardcoded in the configuration.

## 3. HID Declared Capabilities
* **[Descriptor-declared]** Keyboard keys, Modifiers, F1-F24.
* **[Descriptor-declared]** Multimedia, Consumer Control.
* **[Descriptor-declared]** `REL_HWHEEL`, `REL_HWHEEL_HI_RES`, `ABS_VOLUME`.
* **[Descriptor-declared]** Mouse buttons and input events.

*Note: Declared capabilities do not guarantee physical generation of these events.*

## 4. Physical Layout
* **[Observed]** 12 mechanical keys. Numbered K01-K12 in a row-major 3x4 grid.
* **[Observed]** 4 encoders. Numbered E01 (top-left), E02 (top-right), E03 (bottom-top), E04 (bottom-bottom).

## 5. Unverified Hypotheses & Pending Research
* **[Unverified]** Encoder Press: We cannot assume E01-E04 support physical press events until audited.
* **[Hypothesis]** MCU & Firmware: The `239a:80f4` VID/PID strongly suggests an RP2040 microcontroller running CircuitPython or similar, but this is an unverified hypothesis.
* **[Unverified]** USB Audio Interface: Its true purpose is unknown. We MUST NOT assume it acts as a MIDI interface without testing.
* **[Unverified]** RGB Control: The device physically has RGB, but the control protocol is unknown.
* **[Unverified]** Device-Side Persistence: It is unknown if the device can save Profiles or Macros internally.
* **[Publicly stated]** Polling Rate: Product materials claim 125Hz. This is not yet a local observed fact.

*Security Note: No complete device serial numbers or private user information shall be recorded in this repository. In Milestone 1.3B-2, a controlled pyudev discovery read udev/sysfs metadata to verify exact identity mappings, but no device node was opened and no input events were read.*
