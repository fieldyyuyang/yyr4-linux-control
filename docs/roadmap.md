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
状态：
COMPLETE

验收方式：基于风险的组合证据验收 — 历史真实设备证据 + 配置/契约证据 + 当前自动化与主机证据（见 docs/real-device-validation.md § Compositional Acceptance）；新鲜24控制实体端到端验证（V018）已由用户明确延后。
验收日期：2026-07-15
相关提交：02120b2b

已完成交付物：
- 精确udev uaccess规则；
- systemd user unit；
- 可重复的安装与卸载Makefile；
- 集成验证测试；
- 中性Transport Profile文档与契约锁定；
- 用户实际硬件映射保存与迁移；
- 实时软件配置部署；
- X11 keysym兼容性验证；
- RuntimeSnapshot序列化修复。

残余验证缺口（显式延后，非M4阻断）：
- 24项物理操作新鲜端到端实体事件捕获（V018）— 需要设备处于中性传输模式；
- 用户已多次执行过导入/恢复流程，本轮选择不重复高成本操作。

重新触发条件：仅当以下条件之一成立：
1. 中性Transport Profile内容改变；
2. DEFAULT_CODEBOOK改变；
3. Transport Parser修饰键语义改变；
4. repeat处理改变；
5. modifier timeout改变；
6. evdev事件转换改变；
7. YYR4硬件或固件改变；
8. Linux输入后端改变；
9. 真实运行发现故障；
10. 用户主动批准重新测试。

NEXT: Milestone 5 — Optional graphical configurator

## Milestone 5 — Optional graphical configurator

状态：IN PROGRESS

### M5.1 — Configurator Core and Read-Only Graphical Preview
状态：COMPLETE（2026-07-15）
最终提交：b3e4db82817d6f2de24c48143bdac9c2472d17e4

交付物：
- immutable View Model（frozen dataclass）
- 只读自包含HTML预览（无JavaScript，无外部资源）
- `yyr4ctl preview` CLI入口
- 输出安全（符号链接拒绝、同文件检测、原子写入）
- 全部11种Action类型展示
- 测试：662

### M5.2 — Draft Editing, Validation, Diff, and Safe Save
状态：COMPLETE
实现提交：e870e940, c50a5d99, 8384ab5c, b0d18204

交付物：
- Action Spec（JSON ↔ Action，双向，11类型）
- ConfigDraft（base/working隔离，Profile/Layer/Control操作）
- 确定性canonical TOML Serializer
- 14个Draft CLI子命令
- Semantic Diff（added/removed/changed/mapped/unmapped，risk分类）
- 安全保存（no-replace新文件，双SHA复核，O_EXCL备份）
- rollback（restore_backup）
- Draft Sidecar元数据
- 测试：784+

NEXT: M5.3 — Interactive Local Graphical Editor and Draft Review Workflow

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
