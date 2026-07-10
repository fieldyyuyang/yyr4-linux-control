# Product Vision

## Product Problem
Current macro pads rely on proprietary Windows/macOS software, leaving Linux professionals without a context-aware, robust solution. Basic key remappers lack the depth needed to handle dynamic applications, complex Macro flows, and modern Vibe Coding Approval requirements.

## Target Users
* Professionals using Linux for software development, video/audio editing, and DevOps.
* Power users deeply integrating AI-assisted Vibe Coding tools into their workflow.

## Core Value
* **Maximum Capability**: Utilizing all 12 mechanical keys and 4 encoders of the YYR4.
* **Context-Aware**: Dynamically changing functionality based on the active application (e.g., `WM_CLASS`).
* **Vibe Coding Approval Console**: A native capability for interacting with AI CLI agents safely.

## Product Boundaries & Success Criteria
### Success Criteria
* High reliability of the background `yyr4d` daemon.
* A sophisticated, responsive Web UI.
* Seamless automatic Profile switching.
* Safe Vibe Coding Approval Console mapped to physical inputs.

### Out of Scope
* Developing an in-kernel driver.
* Providing a "driverless" pure WebHID solution that replaces the daemon.
* Immediate native Wayland compositor integration (MVP uses X11 mechanisms like `_NET_ACTIVE_WINDOW`).
* Writing custom firmware to replace the stock functionality.

## Web UI Experience
* **Web UI First**: All Profile management and diagnostics are performed in the browser.
* **Secure by Default**: Binds to `127.0.0.1` only.

*See also: [System Architecture](architecture.md), [Use Cases](use-cases.md).*
