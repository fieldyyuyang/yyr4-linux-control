# YYR4 Linux Control — Project Charter

## 1. Product mission
本项目旨在让YYR4在Linux下以非root、可配置、可维护、可长期后台运行的方式工作，把官方物理控件输入转换为用户定义的Linux操作。

最终产品链路：
YYR4 device -> Discovery and Identity -> Input event ingestion -> Official control naming -> Configuration resolution -> Action planning -> Action execution -> Long-running daemon -> CLI and optional GUI management

## 2. User-facing product capabilities
最终目标至少包括：
- A1～A12按键映射；
- AL/AP/AR、BL/BP/BR、CL/CP/CR、DL/DP/DR旋钮操作映射；
- 快捷键动作；
- 文本输入；
- 受控命令执行；
- 延时；
- 多步骤宏；
- 无操作；
- 调试或日志动作；
- 多层配置；
- 预设管理；
- 后台daemon；
- 配置校验和重载；
- 状态查询；
- Linux安装与权限集成；
- 后续可选图形配置器。

## 3. Official control naming
用户界面、文档、CLI提示和日志必须优先使用：
- A1～A12
- AL、AP、AR
- BL、BP、BR
- CL、CP、CR
- DL、DP、DR

内部辅助映射：
- K01～K12 = A1～A12
- E01-L/P/R = AL/AP/AR
- E02-L/P/R = BL/BP/BR
- E03-L/P/R = CL/CP/CR
- E04-L/P/R = DL/DP/DR

不得使用K01等内部名称单独指导用户进行物理操作。

## 4. Completed foundation
将以下内容标记为稳定基础：
- VID/PID Discovery；
- descriptor normalization；
- keyboard/mouse角色识别；
- 唯一Identity；
- 权限检查；
- Transport Parser；
- Shift-first release处理；
- repeat处理；
- timeout/reset；
- Observation Pipeline；
- Probe基础设施；
- Daily Profile A1 EV_KEY阳性对照；
- validation ledger；
- 当前自动测试基线。

说明：
这些能力只有在相关代码契约发生变化时才重新验证。

## 5. Explicit non-goals for the current phase
当前阶段不优先：
- 重复硬件协议研究；
- 重复全量按键测试；
- 临时诊断脚本；
- 自测脚本的自我审计；
- 完整GUI；
- 软件包发布；
- 动态udev规则生成器；
- 为尚不存在的daemon过度设计部署体系；
- 将验证工具当作最终产品。

## 6. Delivery principles
- 产品功能优先于验证基础设施扩建；
- 自动测试优先于人工硬件测试；
- 最小正确实现优先于过度工程化；
- 正式项目代码优先于/tmp实验脚本；
- 用户价值优先于架构装饰；
- 安全边界必须存在，但不能阻止产品交付；
- 每个阶段必须具有明确退出条件。

## 7. Source-of-truth hierarchy
按优先级列出：
1. docs/project-charter.md
2. docs/roadmap.md
3. docs/architecture.md
4. docs/validation-ledger.md
5. docs/security.md
6. docs/real-device-validation.md
7. 其他历史文档和阶段报告

如文档冲突，高级文档优先，冲突必须在当前里程碑中修正。
