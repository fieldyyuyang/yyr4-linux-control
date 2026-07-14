# Development Roadmap

This roadmap defines the sequential dependencies for the project. Moving to the next milestone requires passing all gates of the current one.

## Milestone 1 — Device and input foundation
状态：
COMPLETE

包括：
- Discovery；
- Identity；
- Permission；
- Parser；
- Pipeline；
- Probe基础设施；
- Validation Ledger。

当前Transport完整24项CLI端到端状态作为独立PARTIAL项，不阻断M1关闭。

## Milestone 2 — Core runtime MVP

### M2.1 Configurable Control-to-Action Runtime
当前状态：
COMPLETE

准确范围：
- OfficialControl枚举或等价领域类型；
- 官方名称与内部名称转换；
- 版本化配置schema；
- 选择一种配置格式，不同时支持多套格式；
- 配置加载；
- 配置校验；
- HotkeyAction；
- TextAction；
- CommandAction；
- DelayAction；
- MacroAction；
- NoOpAction；
- Debug/LogAction；
- ActionResolver；
- ActionPlan；
- DryRunExecutor；
- 错误类型；
- 自动测试；
- 示例配置；
- 用户文档。

明确不包括：
- 真实桌面键盘注入；
- daemon；
- systemd；
- udev；
- GUI；
- 软件包发布；
- 真实硬件测试。

M2.1完成标准：
输入官方ControlEvent和配置后，稳定产生确定的ActionPlan。
必须包含示例：
A1 -> Ctrl+Shift+C
AP -> Ctrl+Enter -> 输入“---” -> Ctrl+Enter

### M2.2 Action Execution Engine
当前状态：
COMPLETE

范围：
- 真实动作执行后端；
- 快捷键注入抽象；
- 文本输入抽象；
- argv命令执行；
- timeout；
- 取消；
- 错误隔离；
- 宏顺序执行；
- 结构化执行结果。

### M2.3 Long-running daemon
当前状态：
COMPLETE

范围：
- yyr4d；
- 配置加载；
- 事件循环；
- 动作执行；
- 设备断线重连；
- 优雅停止；
- 配置热加载；
- 结构化日志；
- 非root运行。

### M2.4 Management CLI
当前状态：
COMPLETE

具备命令：
- yyr4ctl validate
- yyr4ctl status
- yyr4ctl list-controls
- yyr4ctl show-config
- yyr4ctl reload
- yyr4ctl dry-run A1

本地管理接口使用 Unix Domain Socket 验证 `SO_PEERCRED`，无 HTTP/TCP 暴露。

## Milestone 3 — Context-Aware Runtime

### M3.1 Layered Configuration Domain
当前状态：
COMPLETE

systemd和udev仍属于M4。

### M3.2 Active Layer Runtime and Switching
当前状态：
COMPLETE

包括：
- 通用层；
- 第一层至第八层；
- active layer；
- 层切换；
- 每层独立动作；
- 预设；
- 导入导出；
- schema迁移。

## Milestone 4 — Linux integration and deployment
当前状态： IMPLEMENTATION COMPLETE, HOST ACCEPTANCE PENDING

NEXT: Milestone 4 — Real Host Integration Acceptance

已实现静态集成资产：
- 精确udev uaccess规则；
- systemd user unit；
- 可重复的安装与卸载Makefile；
- 集成验证测试。

剩余真实主机验证（Real Host Integration Acceptance）：
- 安装规则与unit；
- reload udev并重插设备验证logind ACL；
- 启动服务验证status与context；
- 注销重登验证autostart；
- 验证回滚。

## Milestone 5 — Optional graphical configurator
包括：
- 官方控件布局；
- 动作编辑；
- 层和预设管理；
- daemon状态；
- 日志与错误展示。

GUI不直接访问设备，应调用daemon/API。

## Milestone 6 — Final hardware and product acceptance
采用代表性集中验收，不重复100次全量按键测试。
至少包括：
- 一个按键；
- 一个旋钮左转；
- 一个旋钮按压；
- 一个旋钮右转；
- 一个层切换；
- 一个快捷键动作；
- 一个文本宏；
- 一个命令动作；
- daemon重启；
- 拔插恢复。

只有发现具体异常时才扩大范围。
