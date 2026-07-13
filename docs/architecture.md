# System Architecture

## Terminology
* `YYR4`: The programmable hardware keypad.
* `yyr4-linux-control`: The project name.
* `yyr4d`: The privileged background daemon.
* `Web UI`: The browser-based frontend configuration tool.
* `Web API` / `WebSocket`: Interfaces exposed by the `control service`.
* `Profile`: A collection of Layers tied to an application context.
* `Layer`: A specific mapping of keys/encoders to Actions.
* `Action`: A discrete task (e.g., emitting a keystroke, running a command).
* `Macro` / `Workflow`: A sequence of Actions and logic.
* `Vibe Coding Approval Console`: The sub-system managing AI agent interactions.
* `CLI Adapter`: Tool-specific mappings for the Approval Console.
* `uinput` / `evdev` / `EVIOCGRAB`: Linux kernel subsystems for input management.

## Component Overview

```mermaid
graph TD
    HW[YYR4 Hardware] -->|USB/evdev/hidraw| D[yyr4d Daemon]
    D -->|uinput| OS[Linux Desktop / Apps]

    UI[Web UI] <-->|Web API / WebSocket| CS[control service]
    CS <--> D
```

## Process and Permission Boundaries
1. **yyr4d (Daemon)**: Runs with sufficient privileges to use `EVIOCGRAB` on the YYR4's `evdev` nodes and write to `/dev/uinput`. The daemon operates strictly in userspace. Note: We are currently in Milestone 1.3A, preparing a read-only validation tool. The full daemon and uinput generation are not yet implemented.
2. **control service**: Exposes the local Web API (`127.0.0.1` only). It must safely proxy configurations to `yyr4d`.
3. **Web UI**: Runs in the browser unprivileged.

## Target Architecture Data Flow
1. **Device Discovery**: `yyr4d` finds the YYR4 using stable udev properties.
2. **YYR4 Identity**: Input adapter reads and normalizes raw events.
3. **Transport Parser**: Converts transmission sequences to Control semantics.
4. **Official Control Event**: Maps cleanly using official naming.
5. **Configuration Resolver**: Maps Control to Action definition.
6. **Action Plan**: Generates deterministic ActionPlan.
7. **Action Executor**: Executes actions isolating system side-effects.
8. **Daemon Runtime**: Coordinates lifecycle and configuration loading.
9. **CLI / GUI**: Presentation and configuration tools (no direct hardware access).

## Fault Recovery & Extensions
* Hotplug disconnections cause graceful release of `EVIOCGRAB`.
* Invalid Profile loads rollback to the previous valid transaction.
* Wayland support is planned via an extensible Desktop Adapter model, decoupling the Context Engine from pure X11 tools.

*See also: [Web UI](web-ui.md), [Security Model](security.md).*


## Layered Responsibilities

### Device layer
只负责发现、身份和设备接口。

### Input layer
只负责读取和归一化原始事件。

### Transport layer
只负责把传输序列转换为控件语义。

### Control domain layer
只使用官方名称。

### Configuration layer
把Control映射为Action定义。

### Action planning layer
生成确定、可测试、无副作用的ActionPlan。

### Execution layer
执行动作并隔离系统副作用。

### Runtime layer
负责daemon生命周期、重连、热加载和日志。

### Presentation layer
CLI和GUI，不直接访问硬件。

同时明确：
- Probe是诊断工具，不是主运行时；
- validation ledger是验证决策来源，不是产品执行层；
- udev属于部署层；
- GUI不得直接承担设备访问。
