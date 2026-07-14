# Development Governance and Anti-Drift Rules

## 1. Milestone discipline
一个里程碑必须代表完整、可交付的功能边界。

禁止：
- 为单行修改单独创建里程碑；
- 为格式清理创建提交；
- 为每个测试修复重复提交；
- 在一个功能尚未完成时反复双远程推送；
- 用审计步骤替代功能开发。

## 2. Git policy
采用：
完整功能开发 -> 目标测试 -> 完整测试 -> 集中差异审查 -> 一个提交 -> 一次双远程同步

不得默认采用：
改一点 -> 提交 -> 推送 -> 再改一点 -> 再提交 -> 再推送

只有以下情况允许额外提交：
- 紧急安全修复；
- 已发布版本的独立回滚；
- 无法与主里程碑安全合并的阻断性修复。

## 3. Hardware-test policy
人工硬件测试必须同时满足：
- 新功能已经实现；
- 自动测试全部通过；
- validation ledger无法覆盖该结论；
- 测试结果直接决定产品是否可用；
- 测试步骤和通过标准已经定义；
- 只测试缺失的最小范围。

禁止以以下理由重测：
- 再确认一次；
- 新Agent没有看到旧对话；
- 临时证据文件丢失，但结论已进入fixture和测试；
- 文档没有写清楚；
- 更换了报告格式；
- 为了让测试记录更完整。

## 4. Validation exit criteria
一个结论一旦同时具有以下任一充分证据，即视为关闭：
- 官方配置证据；
- 版本控制fixture；
- 自动回归测试；
- 已提交真实验证报告；
- validation ledger中的VERIFIED状态。

只有明确的retest trigger才可重新打开。

## 5. AI Agent execution rules
AI Agent必须：
- 开始任务前读取project-charter、roadmap和development-governance；
- 优先完成当前Roadmap标记的下一里程碑；
- 不擅自把工作转向硬件验证；
- 不擅自把外围部署能力提到核心运行时之前；
- 不创建临时脚本版本循环；
- 不使用内部键名指导用户；
- 不在没有阻断证据时要求用户进行硬件操作；
- 不将Probe或diagnostics当作最终产品；
- 报告必须简洁聚焦于实际交付。

## 6. Drift detection checklist
每个里程碑开始前回答：
- 当前工作是否直接推进产品能力？
- 是否属于Roadmap中的当前阶段？
- 是否已经存在等价实现或验证？
- 是否可以通过自动测试完成？
- 是否在重复解决已关闭问题？
- 是否在优化一个尚未成为产品阻断的外围系统？
- 是否达到了值得Git提交的边界？

任一问题表明漂移时，停止并回到Charter和Roadmap。

## Context Refresh Protocol

AI Agents must adhere to the following protocol to maintain strict alignment with the project trajectory and avoid premature implementation (e.g. implementing Milestone 4 while in Milestone 3):

**Trigger Conditions:**
Agents MUST perform a full context refresh by reading authoritative documentation:
1. Before commencing work on a new milestone.
2. Upon taking over a session or when a new Agent is spawned.
3. Following context compression, quota limits, or noticeable context loss.
4. When encountering a discrepancy regarding the current stage in `roadmap.md`.
5. Before finalizing testing and creating milestone boundary commits.

**Minimum Required Reading:**
* `AGENTS.md`
* `docs/project-charter.md`
* `docs/development-governance.md`
* `docs/roadmap.md`
* `docs/architecture.md`
* Any active milestone-specific documentation.

**Refresh Constraints:**
* Written documentation dictates truth; model memory is secondary.
* Skipping milestones or inventing unlisted milestones is strictly forbidden.
* Do not mark future phases as COMPLETE.
* Stop and report if docs and code are conflicting.
* Do not loop this refresh unnecessarily for micro-edits.
