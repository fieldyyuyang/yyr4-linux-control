# yyr4-linux-control

> A professional, context-aware Linux control surface platform for the YYR4 programmable keypad.

## Project Positioning
`yyr4-linux-control` is a professional, context-aware control surface platform tailored for Debian 13 and modern Linux desktops. It maximizes the capabilities of the YYR4 programmable keypad (12 mechanical keys, 4 encoders) by providing context-aware app switching, multi-layer mapping, macros, and deep system integration.

## Current State
**[Status: Milestone 1 - Parser Core]**
Device research and transport code auditing (Milestone 0) is complete. The Python parser core and evdev adapter logic are implemented. The project currently has NO functioning daemon, CLI, or Web UI, and cannot be used as a product yet.

### Milestones
- Milestone 1.0: Transport code parser core (Completed)
- Milestone 1.1: Safe device discovery and evdev adapter (Completed - using mock backends)

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
* [Product Vision](docs/product-vision.md)
* [System Architecture](docs/architecture.md)
* [Web UI Design](docs/web-ui.md)
* [Device Research](docs/device-research.md)
* [Event Audit](docs/event-audit.md)
* [Action Model](docs/action-model.md)
* [Use Cases](docs/use-cases.md)
* [Profile Library](docs/profile-library.md)
* [Security Model](docs/security.md)
* [Development Roadmap](docs/roadmap.md)
* [Vibe Coding Approvals](docs/vibe-coding-approvals.md)
