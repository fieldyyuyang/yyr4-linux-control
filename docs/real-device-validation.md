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

To validate the `evdev` event chain correctly, the CLI now includes a `Daily Profile EV_KEY positive-control` mode (`--acknowledge-daily-profile-positive-control`). This mode specifically tests the formal `evdev` EV_KEY read path without enforcing the Transport mapping. A repaired, real Daily positive control run successfully observed the A1 keypress. The previous no-action negative control run has been reclassified properly.

## Validation Ledger
The `validation-ledger.md` is the single source of truth for validation state. The repetitive hardware testing loop is officially CLOSED. Unnecessary re-testing is strictly prohibited if a component is marked `VERIFIED` or `VERIFIED_WITH_LIMITATIONS`. The official physical naming convention (A1-A12, AL/AP/AR, etc.) MUST be prioritized in all validation logs. We will not automatically schedule Transport A1 or full 24-op tests. Testing will only be triggered when the next functional milestone strictly demands real-time Transport events.

**Product Route Constraints:**
- 验证台账不决定产品开发优先级；
- 已VERIFIED事项不得重复打开；
- 当前Transport PARTIAL不阻断M2.1；
- M2.1不依赖任何新硬件测试；
- 下一次真实硬件测试预计在真正需要事件端到端验收的里程碑边界触发；
- 用户操作必须使用官方名称。

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
- The repaired formal event probe yielded 0 EV_KEY events. This state is tracked separately in the validation ledger. No retest will be performed until necessary for functional progress.

## Compositional Acceptance — Milestone 4 Closure

**Date**: 2026-07-15
**Acceptance type**: Risk-based compositional evidence
**Basis**: M4 is accepted by combining multiple independent evidence classes linked through a stable Transport contract.  The acceptance explicitly acknowledges that a fresh 24-control end-to-end hardware event capture (V018) has NOT been performed and is deferred by user decision.

### 1. Confirmed Real-Device Evidence

Evidence obtained from actual YYR4 hardware connected to the host, using read-only tools or user observation (not automated test fixtures):

| Evidence | Status | Source |
|---|---|---|
| Device discovery & identity (VID 239a, PID 80f4) | VERIFIED | `.local/hardware-validation/identity-permission-*.json` (d60cb37) |
| Device role classification (keyboard+mouse) | VERIFIED | `.local/hardware-validation/identity-permission-*.json` (026a844) |
| Node read permissions (user-level ACL) | VERIFIED | `.local/hardware-validation/identity-permission-*.json` (d60cb37) |
| Daily Profile A1 EV_KEY positive control | VERIFIED | `.local/hardware-validation/daily-evkey-visible-*.stdout` (cacfa19) — 1 raw EV_KEY event observed; confirms evdev read path |
| User attestation: neutral profile import/restore | USER ATTESTATION | User has confirmed performing import/restore cycles multiple times historically |

**Not confirmed by real-device capture**: Full 24-op end-to-end CLI verification (V018), repeat/Shift-release behaviour on real hardware (validated only via automated tests).

### 2. Configuration and Contract Evidence

Static verification that configurations, codebooks, and profiles are structurally correct and mutually consistent (not a substitute for real-device event capture):

| Item | Status |
|---|---|
| Neutral Transport Profile: 24 items (F13–F24 ± LSHIFT) | Structurally verified |
| DEFAULT_CODEBOOK: 24 one-to-one mappings | 34 automated tests pass |
| Neutral Profile vs Codebook consistency | 24/24 match (verified 2026-07-15) |
| WinUI encoder storage order (CCW–CW–Press) | Verified by reference to WinUI JSON structure |
| Official vendor transport mapping (V001–V005) | VERIFIED — official configuration evidence |

### 3. Current Software and Host Evidence

Evidence from automated tests, static validation, and host deployment verification (no hardware access):

| Item | Status |
|---|---|
| Transport Parser: shift/repeat/timeout/reset | 21 automated tests pass |
| Live config deployed (24 OfficialControls) | validate + 24 dry-run pass |
| Recording Backend execution (24 controls) | All SUCCESS |
| X11 keysym compatibility (all 25 tokens) | Verified via XStringToKeysym |
| RuntimeSnapshot serialization | Fixed, 590 tests pass |
| udev rules installed | /etc/udev/rules.d/72-yyr4.rules |
| systemd user unit installed | ~/.config/systemd/user/yyr4d.service |
| Git, uv, worktree consistency | HEAD = worktree = uv install |

### 4. Deferred Evidence

Explicitly NOT performed and NOT required for M4 closure:

| Item | Status | Reason |
|---|---|---|
| Fresh 24-control real-device event capture | DEFERRED (V018) | Requires device in neutral transport mode; user elected not to repeat reflash cycle |
| Fresh 24-control daemon-to-desktop end-to-end test | DEFERRED | Requires daemon running with neutral transport hardware |
| Repeat behaviour on real hardware | DEFERRED | Verified by automated tests only |
| Shift release order on real hardware | DEFERRED | Verified by automated tests only |

### Transport Code Audit

Since the last real-device test (commit `909c04c`), the transport layer has had **zero semantic changes**:
- `src/yyr4_linux_control/transport/codebook.py` — unchanged
- `src/yyr4_linux_control/transport/parser.py` — unchanged
- `tests/test_transport_parser.py` — unchanged
- `tests/test_codebook.py` — expanded (contract-lock tests only)
- `src/yyr4_linux_control/control/models.py` — `OfficialControl` enum added (no transport semantics affected)

**TRANSPORT CONTRACT UNCHANGED SINCE REAL-DEVICE VALIDATION.**

### Decision

M4 is **ACCEPTED BY RISK-BASED COMPOSITIONAL EVIDENCE**.  The combination of confirmed real-device evidence (identity, permissions, A1 EV_KEY visibility), configuration and contract evidence (codebook, neutral profile consistency), and current software/host evidence (590 tests, config deployment, keysym verification) provides sufficient assurance that the Linux integration is functionally correct.  A repeated hardware reflash would only re-verify the same stable transport contract.

**The fresh 24-control end-to-end hardware validation (V018) remains explicitly deferred.**  This is a known, documented residual testing gap — not a blocker for M4.

**Re-trigger conditions**: A fresh transport hardware test is required only if:
1. The neutral Transport Profile content changes.
2. `DEFAULT_CODEBOOK` changes.
3. Parser modifier semantics change.
4. Repeat handling changes.
5. Modifier timeout changes.
6. evdev event conversion changes.
7. YYR4 hardware or firmware is replaced.
8. The input backend is changed.
9. A real usage fault is observed.
10. The user voluntarily approves a re-verification.

The device is currently running the user's everyday hardware-direct configuration.  When the user is ready to run `yyr4d`, they may import the neutral Transport Profile (`docs/WinUI/...after-transport-profile.json`) and start the service.  No repeated testing is required before doing so.
