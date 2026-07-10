# AGENTS.md

This file establishes strict behavioral constraints for AI Agents working on the `yyr4-linux-control` project.

## Core Constraints
1. **Documentation First**: Agents MUST plan and document changes before implementation.
2. **Verify Then Implement**: Agents MUST NOT write code for hardware features unless practically verified.
3. **Do Not Guess Hardware Behavior**:
   * Agents MUST NOT assume encoders support physical press events (`[Unverified]`).
   * Agents MUST NOT assume the USB Audio interface acts as a MIDI interface (`[Unverified]`).
   * Agents MUST NOT claim the device uses an RP2040 chip or CircuitPython without firmware dumps (`[Hypothesis]`).
   * Agents MUST NOT claim the RGB control protocol is known (`[Unverified]`).
   * Agents MUST NOT assume on-device persistence (`[Unverified]`).
4. **Web UI First**: The primary interface MUST be the Web UI. Agents MUST NOT build GTK/Qt apps for configuration.
5. **Clear Architecture Boundaries**: Agents MUST keep `yyr4d` separated from the Web UI.
6. **Security Principles**:
   * Agents MUST NOT hardcode dynamic device nodes (e.g., `/dev/input/eventN`).
   * Agents MUST NOT read from the user's main keyboard.
   * Agents MUST NOT execute arbitrary, unverified shell commands.
7. **Git Milestone Principles**:
   * Agents MUST NOT automatically force push.
   * Agents MUST NOT commit secrets, full serial numbers, or local home directory paths.
8. **Evidence Tracking**: All facts MUST be tagged (`[Confirmed]`, `[Observed]`, `[Descriptor-declared]`, `[Publicly stated]`, `[Hypothesis]`, `[Unverified]`, `[Planned]`, `[Out of scope]`).
9. **Vibe Coding Approval Constraints**:
   * Agents MUST NOT design YYR4 as a blind auto-approval tool.
   * Agents MUST NOT default-bind "Always Allow", YOLO, bypass, or equivalent modes.
   * Agents MUST NOT blindly send 'Enter' on a timer to simulate approvals.
   * Actual CLI bindings MUST be verified by versioned auditing.
   * Reject, Cancel, and Emergency Stop MUST always be available.
