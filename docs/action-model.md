# Action Model

## 1. Concept
The Action Model defines how standardized logical events trigger typed behaviors in the OS.

## 2. Semantic Actions & Versioning
All configurations MUST be versioned using JSON Schema to guarantee compatibility across updates.

### Input Actions
* **Keys**: Single Key, Combos, Key Sequences, Modifiers (e.g., Shift+Ctrl+Alt).
* **Media/Mouse**: F13-F24, Media Keys, Mouse clicks/movement, scrolling (vertical/horizontal/high-res).
* **Injection**: Text injection, Unicode input, delays.

### System Actions
* **Window Management**: Launch App, Focus App, Open URL/File, Workspace switching.
* **Hardware**: Volume Control, Screen Brightness, Media Playback.
* **Integration**: D-Bus calls, systemd user service triggers.

### Automation Actions (Strict Security)
* Execute an allowlisted shell command. MUST use `argv` array, NEVER raw strings.
* HTTP Requests / Webhooks.
* Macro control: Conditional branching, loops, timeouts.

### Vibe Coding Approval Actions
* **Semantic Navigation**: `approval.navigate.previous`, `next`, `left`, `right`.
* **Semantic Authorization**: `approval.select`, `approval.approve.once`, `approval.approve.session`.
* **Semantic Denial**: `approval.reject`, `approval.cancel`, `approval.emergency_deny`.

### Profile / UI Actions
* Switch Profile, Lock Profile.
* Toggle/Hold Layer.
* Pause Daemon, Show Overlay.

## 3. Security and Execution Boundaries
* **Cancellation**: Long-running Macros MUST be interruptible by the user.
* **Confirmation Policies**: Dangerous actions (Level C/D authorizations) require secondary confirmation or long-presses.
* **Validation**: Configurations MUST NOT bypass schema checks.

*See also: [Vibe Coding Approvals](vibe-coding-approvals.md), [Security Model](security.md).*
