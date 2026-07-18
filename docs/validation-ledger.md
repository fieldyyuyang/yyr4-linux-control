# YYR4 Validation Ledger

This document acts as the definitive source of truth for hardware and protocol validation status.

## 1. Scope and evidence classes

To avoid endlessly re-testing the hardware on every hypothesis, evidence is classified as follows:

*   **Official vendor configuration evidence**: Used to prove the physical key names and key value mappings configured officially.
*   **Historical operator real-device evidence**: Records extensive manual keystroke and knob validation already completed by the operator, though some early raw files weren't permanently saved.
*   **Versioned parser fixture evidence**: Offline JSON files capturing raw events used for automated unit tests.
*   **Automated regression evidence**: Python `unittest` suites ensuring software continually meets Parser, Discovery, Identity, Permission, and Pipeline contracts.
*   **Current maintained CLI real-device evidence**: Proves the end-to-end behavior of the formal CLI on specific commits.
*   **Configuration / contract evidence**: Static verification that configurations, codebooks, and profiles are structurally correct and mutually consistent (not a substitute for real-device event capture).
*   **Risk-based compositional evidence**: Acceptance of a milestone by combining multiple independent evidence classes linked through a stable Transport contract; explicitly notes any deferred hardware testing.

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
| V001 | A1-A12 key mapping | Maps F13-F24 to A1-A12 Down/Up | VERIFIED | Official vendor configuration evidence | Official software / Historical operator real-device evidence | N/A | None |
| V002 | AL/AP/AR mapping | Maps Shift+F13-F15 to AL/AP/AR | VERIFIED | Official vendor configuration evidence | Official software / Historical operator real-device evidence | N/A | None |
| V003 | BL/BP/BR mapping | Maps Shift+F16-F18 to BL/BP/BR | VERIFIED | Official vendor configuration evidence | Official software / Historical operator real-device evidence | N/A | None |
| V004 | CL/CP/CR mapping | Maps Shift+F19-F21 to CL/CP/CR | VERIFIED | Official vendor configuration evidence | Official software / Historical operator real-device evidence | N/A | None |
| V005 | DL/DP/DR mapping | Maps Shift+F22-F24 to DL/DP/DR | VERIFIED | Official vendor configuration evidence | Official software / Historical operator real-device evidence | N/A | None |
| V006 | Shift pre-release | Modifiers released before key drop event gracefully | VERIFIED | Automated regression evidence | `tests/test_transport_parser.py` | 2445c8e | None |
| V007 | Repeated events | EV_KEY repeats (value=2) are ignored | VERIFIED | Automated regression evidence | `tests/test_transport_parser.py` | 2445c8e | None |
| V008 | Timeout/Reset | Modifiers timeout and reset correctly | VERIFIED | Automated regression evidence | `tests/test_transport_parser.py` | 2445c8e | None |
| V009 | VID/PID Discovery | pyudev discovers 239a:80f4 devices | VERIFIED | Historical operator real-device evidence | `.local/hardware-validation/identity-permission-*` | d60cb37 | Relies on local udev rules matching current session. |
| V010 | Descriptor spaces | Spaces are normalized to underscores in udev properties | VERIFIED | Historical operator real-device evidence | `.local/hardware-validation/identity-permission-*` | 026a844 | Confirmed via local testing output logs. |
| V011 | Role identification | Keyboard/Mouse separated by `ID_INPUT_*` properties | VERIFIED | Historical operator real-device evidence | `.local/hardware-validation/identity-permission-*` | 026a844 | Confirmed via local testing output logs. |
| V012 | Unique Identity | Same USB parent, specific interfaces pair uniquely | VERIFIED | Historical operator real-device evidence | `.local/hardware-validation/identity-permission-*` | d60cb37 | Confirmed via local testing output logs. |
| V013 | Node read permission | Selected evdev nodes are readable by user | VERIFIED | Historical operator real-device evidence | `.local/hardware-validation/identity-permission-*` | d60cb37 | Requires user in `input` group. |
| V014 | Daily Profile A1 EV_KEY positive control | A1 keypress yields > 0 raw EV_KEY events | VERIFIED | Current maintained CLI real-device evidence | `.local/hardware-validation/daily-evkey-visible-*` | cacfa19 | Confirms evdev read path works for standard keys. |
| V015 | No-action Daily run | Daily profile run without user interaction | INVALID_TEST | Current maintained CLI real-device evidence | `.local/hardware-validation/daily-evkey-positive-*` | cacfa19 | Originally mislabeled as failed positive control. User did not press keys. |
| V016 | 1st Transport Probe AttributeError | Initial observe_probe crashed on diagnostics | INVALID_TEST | Current maintained CLI real-device evidence | `.local/hardware-validation/*` | d60cb37 | Software bug. |
| V017 | Fixed Transport EV_KEY run | Transport profile emitted 0 EV_KEY events | PARTIAL | Current maintained CLI real-device evidence | `.local/hardware-validation/*` | 909c04c | Could mean Transport doesn't use EV_KEY, or other layers are filtering. |
| V018 | Full 24-op CLI verification | Test all 24 physical operations end-to-end | NOT_YET_VERIFIED | Current maintained CLI real-device evidence | N/A | N/A | Deferred: requires device in neutral transport mode; user elected not to repeat reflash cycle. |
| V019 | Risk-based M4 acceptance | Compose historical real-device + configuration contract + automated + host evidence | VERIFIED | Risk-based compositional evidence | V001-V005, V009-V014, 590 tests, codebook/parser unchanged since 909c04c, live config deployed, keysym verified | 4252c9f | Fresh 24-control hardware event capture (V018) remains explicitly deferred. See real-device-validation.md. |

## 4. Retest triggers and rules

**No unnecessary retesting.** The repetitive hardware test loop is officially CLOSED.
If an item is VERIFIED, do not retest it via manual hardware manipulation.

"Just to be sure" or "let's confirm again" is NOT a valid reason to request a hardware retest for:
- Official configured key mappings
- Parser foundational mappings
- Shift/repeat/timeout/reset behavior
- Discovery, Identity, and Permission checks
- Daily A1 EV_KEY positive linkage

Transport real-device testing is ONLY allowed to be triggered when one of the following occurs:

1.  The next software milestone strictly depends on capturing live Transport events.
2.  `EvdevInputAdapter` reading logic changes.
3.  `ObservationPipeline` or `ProbeRunner` event path changes.
4.  Transport Parser input contracts change.
5.  Device firmware or hardware configuration is known to have changed.
6.  Existing Transport evidence is proven invalid.
7.  A new functional target needs coverage that existing evidence does not supply.

Even if triggered, only the minimal missing scope should be tested, not a full 24-operation sequence unless strictly necessary.

## Product Route Constraints
- 验证台账不决定产品开发优先级；
- 已VERIFIED事项不得重复打开；
- 当前Transport PARTIAL不阻断M2.1；
- M2.1不依赖任何新硬件测试；
- 下一次真实硬件测试预计在真正需要事件端到端验收的里程碑边界触发；
- 用户操作必须使用官方名称。

## M5.4-A2 — Active Session Control and Crash-Safe Recovery

### 验证基线
- 基线HEAD: `36102dc7d5bd198a69728753dff873cdde2a6016`
- 验证对象: 该HEAD之上的未提交M5.4-A2工作树
- 最终Commit SHA: Milestone delivery commit; resolve with `git rev-parse HEAD` after checkout

### 安装包验证
- `pip wheel --no-deps --no-index --no-build-isolation` 成功
- 真实Python venv安装，非editable，非`--target`
- 使用venv生成的`yyr4ctl` console script
- 模块从venv site-packages导入，非仓库src

### 最终测试矩阵
- Installed Recovery: 4/4 OK
- Installed Smoke: 1/1 OK
- Source-tree Recovery regression: 41/41 OK
- Total: 46 tests
- Failures: 0
- Errors: 0
- Skipped: 0

### 已验证生命周期
- Bootstrap、Cookie与CSRF
- 多Session隔离
- Registry与AF_UNIX控制Socket
- SIGKILL后Recovery保留
- Manifest绑定Source和Target
- Draft SHA与Sidecar SHA完整性
- `recover list`, `inspect`, `resume`, `discard`
- Resume后全新认证（新Bootstrap、Cookie、CSRF、Session ID）
- Draft状态恢复（dirty、reviewed、mutation_count）
- Review
- Save到原始Manifest Target
- Save后Recovery删除和Registry `recovery_id` 解绑为null
- 后续Mutation创建全新Recovery ID
- Registry重新绑定新Recovery
- 普通Stop后保留dirty Recovery
- 正式Discard完成清理

### 资源结果
- 最终验证轮次没有产生遗留Editor、Registry、AF_UNIX Socket或Recovery
- Closeout阶段清理了35个已明确证明属于旧/tmp测试目录的陈旧测试进程
- 0个无法证明归属的用户进程

### 非阻塞技术债
- 部分旧Editor测试的Popen stdout/stderr管道在严格ResourceWarning模式下可能产生警告
- 属于测试基础设施债务，非产品运行时缺陷
- 不影响当前46项功能测试结果
- 不阻塞M5.4-A2关闭
- 后续作为独立维护任务处理

### 快照
- 当前关闭快照: `/home/fieldy/.local/state/yyr4-linux-control/wip/m54a2-final-delivery.patch`
- SHA256: `2df655c37f2b40078fc25b5d24be191f7f1b33b6f51d9bab6428a90c02ab1d03` (Closeout-2 snapshot; will be superseded by Closeout-2A)
