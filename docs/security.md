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

## 2.5 Local Management API (CLI)
* **Threat**: Malicious local users reloading daemon configuration or executing dry-runs.
* **Prevention**:
  * The management socket MUST use Unix Domain Sockets (UDS) located securely in `$XDG_RUNTIME_DIR`.
  * The daemon MUST verify the UID of the connected client using `SO_PEERCRED` to ensure exact identity matching.
  * Socket permissions MUST be 0600 or 0700.

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
To safely acquire the device without risk of opening the users main keyboard, we strictly match the parent USB topology, vendor, product, and ensure exactly one keyboard and one mouse interface are present on interface 02. The discovery logic fails closed on any ambiguity. When normalizing USB descriptors, we prioritize `sysfs` descriptors to avoid `udev` space-to-underscore normalization issues, and use strict matching when using `udev` property fallbacks.

## Explicit Hardware Probe Authorizations (Milestone 1.3A+)
Before any real hardware validation tool runs, users must explicitly acknowledge its execution. For the M1.3B-2K Identity and Permission Validation Probe, users must explicitly supply `--real`. Automatic authorizations are strictly forbidden. The probe only reads properties and checks `os.access`; no device node is opened, grabbed, or read from.

### Discovery and Permission Separation
* Device nodes are evaluated for filesystem `os.access` readability only if they precisely match the composite YYR4 identity. Unrelated device nodes are never tested for read access.
* The separation ensures that missing read permissions map clearly to `IntegrationPermissionError` (or `PERMISSION_BLOCKED` via the probe tool) rather than misleadingly indicating device absence (`DeviceNotFoundError`).



## M5.3 Local Graphical Editor Security

### Session Token
- Random  per session
- Token embedded in URL path (/session/TOKEN/)
- All mutation endpoints require valid token (401 on invalid/missing)
- Token never logged to disk or console

### Network
- Binds 127.0.0.1 only (no 0.0.0.0 or LAN)
- Random ephemeral port (port=0)
- Host header validated against 127.0.0.1 pattern
- Origin header validated against loopback patterns
- No CORS headers (same-origin only)

### Content Security Policy
-  — no inline scripts, no unsafe-eval
-  — no inline styles, no unsafe-inline
- , , 
- CSS and JS served as external, token-gated resources
- No external CDN, frameworks, fonts, or images

### Request Guards
- Content-Type enforced: application/json for all POST mutations
- Body size limit: 256 KiB
- Fixed routing (no user-controlled paths in filesystem)
- Asset whitelist: only editor.css / editor.js
- Path traversal: encoded form rejection (..%2f, %252e%252e, %5c, etc.)

### Session Cleanup
- Session directory removed on shutdown
- Source, target, and backups preserved
- No daemon, hardware, or action execution access

## 安全实施顺序 (Phased Security Implementation)
1. M2.1纯领域模型与dry-run，无系统副作用 (已完成)；
2. M2.2集中封装真实副作用 (已完成)；
3. M2.3 daemon使用最小权限 (已完成)；
4. M2.4 本地管理平面使用UDS/SO_PEERCRED身份验证 (已完成)；
5. M3/M4再实现精确udev/systemd部署；
6. 禁止为了提前完成udev而阻塞核心运行时开发。

## 命令动作约束 (Command Action Security Constraints)
命令动作要求预先记录：
- 使用argv而非shell字符串；
- 默认shell=False；
- 参数验证；
- timeout；
- 无隐式sudo；
- 错误隔离；
- 可配置白名单策略。

这只是设计约束，不在本阶段实现。
