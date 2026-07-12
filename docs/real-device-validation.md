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
Real device probing demands explicit user acknowledgement through three mandatory parameters:
1. `--acknowledge-read-only-device-access`
2. `--acknowledge-transport-profile-active`
3. `--acknowledge-no-actions`
All three authorizations are absolutely required before proceeding.

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
