# Vibe Coding Approval Console

The Vibe Coding Approval Console is a complete, independent sub-system of `yyr4-linux-control`. It enables users to securely navigate and approve/reject AI agent requests without disrupting their physical workflow.

## 1. Functional Goal
Intercept agent permission requests (file writes, network access, shell commands) and map them to physical YYR4 inputs, respecting risk boundaries and Context constraints.

## 2. Semantic Approval Action Model
To remain CLI-agnostic, the system maps physical keys to semantic intentions:

* **Navigation**: `approval.navigate.previous` / `next` / `left` / `right`
* **Authorization**: `approval.select` / `approval.approve.once` / `approval.approve.session` / `approval.approve.scope` / `approval.plan.approve`
* **Denial**: `approval.reject` / `approval.cancel` / `approval.back` / `approval.plan.reject`
* **Execution Control**: `approval.execution.stop` / `approval.execution.interrupt` / `approval.emergency_deny`
* **Information**: `approval.details.toggle` / `approval.details.scroll_up` / `approval.details.scroll_down`

## 3. CLI Adapter Architecture
A `CLI Adapter` bridges semantic Actions to application-specific inputs.
Each adapter defines:
* Tool ID (e.g., `gemini-cli`, `agy`).
* Process/Terminal recognition rules.
* Keystrokes bound to semantics (e.g., "Approve Once" = `y`).
* Supported scopes.
* Version validation.

*Note: Adapters for AGY, Gemini CLI, Claude Code, and others are currently **[Planned]** and **[Unverified]**.*

## 4. Phased Implementation Strategy

### Level 1: Focused Terminal Input
* **Mechanism**: When an AI CLI window is focused, semantic Actions emit standard keyboard events (`y`, `n`, `Enter`, arrows) to the active window.
* **Safety**: Relies on the user reading the terminal. Does NOT automatically parse text or blindly send `Enter` on timers.

### Level 2: CLI-Aware Mapping
* **Mechanism**: Dynamically switches the Approval Layer based on the specific CLI identified. Adapters provide varying mappings per CLI.

### Level 3: Prompt-Aware Integration
* **Mechanism**: Deep integration via hooks or PTY parsing to securely display summaries in the Web UI.
* **Constraint**: MUST NOT rely on fragile screen-scraping/OCR.

## 5. Physical Layout Template
*Default template, customizable in Web UI.*

### Approval Layer Keys
* K01: Previous option
* K02: Next option
* K03: Approve once
* K04: Reject
* K05: Left / previous scope
* K06: Right / next scope
* K07: Select / Enter
* K08: Cancel / Escape
* K09: Toggle details
* K10: Open Approval Console in Web UI
* K11: Stop current execution
* K12: Emergency deny

### Approval Layer Encoders
* E01: Move between approval options
* E02: Scroll permission details
* E03: Scroll diff / logs
* E04: Change approval scope

## 6. Security Boundaries
* YYR4 MUST NOT be used as a blind auto-approval tool.
* Bypassing sandboxes or applying "Always Allow" by default is strictly forbidden.
* **Level D** actions (e.g., `rm -rf`, force push) MUST default to rejection or require explicit Web UI confirmation.
* Approval Layers automatically drop when focus is lost.

*See also: [Security Model](security.md), [Action Model](action-model.md).*
