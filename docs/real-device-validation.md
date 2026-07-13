# Real Device Validation

Milestone 1.3A prepares the production composition and a gated read-only validation tool. **This milestone does not perform actual hardware access or integration.**
- Implementation and simulated tests are complete; controlled hardware validation is pending.
- We have not run a real preflight.
- We have not discovered real devices.
- We have not called os.access on real device nodes.
- We have not opened or read the real YYR4.
- We have not executed EVIOCGRAB (`grab`).
- We have not created `uinput` devices.
- We have not executed any Actions.
- The `observe_probe` tool is a validation script, not a daemon.

## Preflight vs Permission Check
- **Runtime Preflight**: Checks environmental safety without interacting with the OS file system or device nodes. Verifies the current Python version, platform, root privilege (rejected), and availability of required dependencies.
- **Identity Permission Checker**: Checks actual OS read-access permissions on device nodes using `os.access`. It does *not* open the devices or scan paths. This is separate from RuntimePreflight.
- Devices are discovered exactly once, and the pipeline is locked to that single identity (no double discovery).

## Explicit Authorization
Real device probing demands explicit user acknowledgement through mandatory parameters:
1. `--acknowledge-read-only-device-access`
2. `--acknowledge-no-actions`
And exactly ONE profile confirmation:
3a. `--acknowledge-transport-profile-active`
3b. `--acknowledge-daily-profile-positive-control`
All required authorizations are absolutely required before proceeding.

## Daily Profile EV_KEY Positive Control
A previous Transport Profile probe run resulted in 0 observed raw events. However, the `raw_events_seen` counter in `ObservationPipeline` only increments for `EV_KEY` events because the underlying `EvdevInputAdapter` filters out non-key events (like `EV_REL` or `EV_SYN`). Therefore, the zero-event result cannot reliably prove that the Transport Profile uses a different communication layer entirely. There is currently no evidence requiring a shift to `hidraw`.

To validate the `evdev` event chain correctly, the CLI now includes a `Daily Profile EV_KEY positive-control` mode (`--acknowledge-daily-profile-positive-control`). This mode specifically tests the formal `evdev` EV_KEY read path without enforcing the Transport mapping. A repaired, real Daily positive control run is pending.

## Probe Constraints
The probe is explicitly bounded by:
- Event count (`--max-events`): Events are strictly bounded.
- Timeout (`--timeout`): The timeout is an overall global deadline for the entire probe run, not a per-event timeout.
- Read-only limits: It does not use `uinput`, grab the device exclusively, or attempt any output commands.
- **Signal Handling**: Supports SIGINT/KeyboardInterrupt and SIGTERM gracefully. Note: full robust SIGTERM daemon capability is not claimed yet.

## Output Redaction
By design, all outputs emitted by the CLI are desensitized. USB topologies, complete serial numbers, and home directory paths are hidden. The probe translates raw `ControlEvent` models into safer `ProbeEvent` summaries before printing.

## State
Currently, users *do not* need to switch to the Transport Profile. Implementation and simulated tests are complete. Users will only import the transport profile right before controlled validation, and can restore their normal profile immediately after.


### M1.3B-2B Discovery Attempt
- The M1.3B-2B real discovery execution successfully constructed a `pyudev.Context` and enumerated the input subsystem.
- However, it was intentionally aborted by the safe wrapper because the discovery layer eagerly attempted `os.access` checks on unrelated nodes before completing identity matching.
- **Zero Real Access Maintained**: No devices were opened, no events were read.
- **Next Steps**: Following the M1.3B-2C decoupling patch, a single-run controlled discovery must be re-executed. The user still does not need to switch transmission configurations yet.

### M1.3B-2I Role Classification Update
- Following a read-only metadata diagnosis, it was identified that the original production logic improperly used the empty optional `NAME` attribute as a gate for role detection.
- This has been corrected to use the dedicated `ID_INPUT_KEYBOARD` and `ID_INPUT_MOUSE` properties as authoritative sources.
- No new real discovery, node reading, or event probe has been executed yet for the updated logic.
- There is currently no evidence indicating that the Transport Profile affects role metadata. We do not need to switch Transport Profile yet.

### M1.3B-2K Identity and Permission Validation Probe
- The temporary diagnostic script phase has ended. Identity/permission validation is now productized as a maintained tool (`yyr4_linux_control.tools.identity_permission_probe`).
- The tool only discovers, selects the unique Identity, and checks selected-node `R_OK` read permissions without actually opening the nodes or reading events.
- Real execution must be explicitly designated via `--real`.
- Results are written to local, Git-ignored JSON files, and are heavily desensitized.

### M1.3B-2P Transport Profile Event Probe Contract Fix
- The first formal Transport Profile event probe was executed but failed internally (`AttributeError` from `ProbeRunner` incorrectly accessing `pipeline.diagnostics` instead of `pipeline.snapshot_diagnostics()`).
- The Identity and Permission validation steps continue to be verified successfully.
- No valid Transport event validation conclusions could be drawn due to the internal crash.
- This milestone corrected the internal public interface contract, ensuring the probe consumes the formal snapshot method correctly, and added a regression test for this specific crash path.
- The repaired formal event probe is now pending a single real execution.
