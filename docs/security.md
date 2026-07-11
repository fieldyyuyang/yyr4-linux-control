# Security and Threat Model

## 1. Input Device Isolation (Permissions)
* **Threat**: Erroneous grabbing of the main user keyboard (Keylogging).
* **Prevention**: `yyr4d` MUST use precise `udev` attribute matching to open ONLY the YYR4 interfaces. Users MUST NOT be added to the generic `input` group.
* **Detection**: Audit logs record exactly which `eventN` nodes were grabbed.

## 2. Web API and LAN Exposure
* **Threat**: Malicious websites accessing the local API via localhost (CSRF/WebSocket Hijacking), or LAN attackers executing macros.
* **Prevention**:
  * Default listen address MUST be `127.0.0.1`.
  * Strict Origin and Host header validation.
  * CSRF tokens for state-changing REST calls.
* **Audit**: Connections are logged.

## 3. Command Execution & Macro Injection
* **Threat**: A downloaded profile contains hidden `rm -rf` commands or attempts shell injection.
* **Prevention**:
  * NEVER use `shell=True` as a default.
  * Commands MUST be parsed as strict `argv` arrays.
  * High-risk commands (Level D) demand explicit Web UI authorization prior to execution.
  * Macros MUST NOT store plaintext secrets, passwords, or SSH keys.

## 4. Operational Safety (Vibe Coding & Sysadmin)
* **Threat**: Accidental triggering of destructive actions (e.g., stopping production containers).
* **Prevention**:
  * **Level A (Low Risk Navigation)**: Single click allowed.
  * **Level B (Approve Once)**: Single click allowed if context matches strictly.
  * **Level C (Session Approval)**: Requires long-press or secondary verification.
  * **Level D (Dangerous)**: Generic approval buttons disabled. Web UI/Keyboard fallback required.

## 5. Resilience & Recovery
* **Threat**: Daemon crash leaves `EVIOCGRAB` active, deadlocking the device.
* **Recovery**: The daemon handles SIGINT/SIGTERM to release grabs gracefully. The OS automatically reclaims abandoned file descriptors.
* **Threat**: Corrupt configuration upload.
* **Recovery**: SQLite schema transactions ensure rollback to the last known-good state.

*See also: [Vibe Coding Approvals](vibe-coding-approvals.md).*


## Multi-Factor Identity Matching
To safely acquire the device without risk of opening the users main keyboard, we strictly match the parent USB topology, vendor, product, and ensure exactly one keyboard and one mouse interface are present on interface 02. The discovery logic fails closed on any ambiguity.