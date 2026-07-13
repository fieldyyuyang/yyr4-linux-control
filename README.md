# yyr4-linux-control

> A professional, context-aware Linux control surface platform for the YYR4 programmable keypad.

## Project Positioning
`yyr4-linux-control` is a professional, context-aware control surface platform tailored for Debian 13 and modern Linux desktops. It maximizes the capabilities of the YYR4 programmable keypad (12 mechanical keys, 4 encoders) by providing context-aware app switching, multi-layer mapping, macros, and deep system integration.

## Current State
**[Status: Milestone 1 - Device and Input Foundation Completed]**
Device research, transport code auditing, safe device discovery, evdev input adapter logic, parser core, and validation infrastructure are complete.

**Current development target:**
**Milestone 2.2 — Action Execution Engine**

The project currently has NO functioning daemon, CLI, or Web UI, and cannot be used as a product yet. It is purely in the development phase.

## Core Principles
* **Web UI First**: All user interactions are handled via a local Web UI.
* **Local Daemon + Web UI**: A privileged background daemon (`yyr4d`) handles input capturing and virtual output.
* **Context-Aware**: Automatically switches Profiles based on the active Linux window.
* **Safe & Recoverable**: Non-destructive, handles errors gracefully, and runs safely.

## Verified Device Information
* **USB Identity**: Vendor ID `239a`, Product ID `80f4`, Manufacturer `YOUYOU TEC.`
* **Physical Layout**: 12 mechanical keys (3x4), 4 rotary encoders (2 small, 2 large).
* **Connection**: USB Type-C.

## Features & Vision
* **Professional Use Cases**: Deep integration for Linux Desktop, Coding, Vibe Coding, DevOps, Video/Audio/Photo editing.
* **Vibe Coding Approval Console**: A first-class feature for safely managing agentic CLI approvals.
* **Capabilities**: Single keys, combinations, macros, command execution, system control.

## Documentation Index
* [Project Charter](docs/project-charter.md)
* [Development Governance](docs/development-governance.md)
* [Development Roadmap](docs/roadmap.md)
* [System Architecture](docs/architecture.md)
* [Validation Ledger](docs/validation-ledger.md)
* [Security Model](docs/security.md)
* [Real Device Validation](docs/real-device-validation.md)
* [Product Vision](docs/product-vision.md)
* [Web UI Design](docs/web-ui.md)
* [Device Research](docs/device-research.md)
* [Event Audit](docs/event-audit.md)
* [Action Model](docs/action-model.md)
* [Control Action Configuration](docs/control-action-configuration.md)
* [Use Cases](docs/use-cases.md)
* [Profile Library](docs/profile-library.md)
* [Vibe Coding Approvals](docs/vibe-coding-approvals.md)
