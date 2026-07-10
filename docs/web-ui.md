# Web UI Design

The Web UI is the primary, indispensable configuration interface for `yyr4-linux-control`. The system is designed such that all mapping and management MUST be possible via the browser, without requiring hand-editing of configuration files.

## 1. Core User Flows and Pages

* **Dashboard**: Displays overall system health, current active Profile, automatic switching status, and a quick "Emergency Stop" toggle.
* **Device**: Shows USB connection data, firmware Hypotheses, and `eventN` node status. Displays a prominent "Device Disconnected" empty state if the hardware is unplugged.
* **Physical Layout Editor**: An interactive SVG/Canvas representation of K01-K12 and E01-E04.
* **Device Learning Wizard**: Guides the user through a physical press-and-turn sequence to normalize `evdev` codes to logical events.
* **Live Event Monitor**: A WebSocket-driven real-time log of raw inputs, normalization results, and dispatched Actions. Includes pause, filter, and export capabilities.
* **Profile Manager**: Lists all Profiles. Supports cloning, prioritizing, exporting, and conflict resolution for Application Rules.
* **Layer Editor**: Edits the stacked Layers within a specific Profile.
* **Application Rules**: Form-based builder for `WM_CLASS`, Window Title, and PID matching conditions.
* **Action Editor & Macro/Workflow Designer**: Visual node-based or timeline editor for complex workflows.
* **Vibe Coding Approvals**: Specialized dashboard for managing CLI Adapters and reviewing Approval Layer security.
* **CLI Adapter Manager**: Import and manage versioned CLI Adapters.
* **Template Library**: Import ready-made Profiles.
* **Security & Diagnostics**: Adjust command execution allowlists, view logs, and backup/restore the SQLite database.
* **Unsupported/Unverified Capabilities**: A dedicated section explaining why RGB or MIDI might be disabled (awaiting research).

## 2. Interaction and State Management

* **Graceful Degradation**: If the WebSocket disconnects, the UI enters a "Read-Only / Reconnecting" state. Reconnection must happen automatically without losing unsaved form data.
* **Unsaved Changes**: Warns the user if navigating away from the Action Editor with unsaved modifications.
* **Error Handling & Rollback**: Saving a configuration applies it via a transaction. If `yyr4d` rejects it, the UI surfaces the validation error and keeps the previous state.
* **Security Prompts**: Dangerous configurations (e.g., executing a script) trigger an explicit confirmation modal.

## 3. Experience Requirements
* **Responsive & Accessible**: Must support keyboard navigation (Tab indexing) and respect the user's preferred color scheme (Dark/Light mode).
* **Local First**: Must function completely offline. The UI is served directly by the `control service`.
* **Headless Resiliency**: Closing the browser MUST NOT stop the `yyr4d` mappings. The daemon operates independently.

*See also: [System Architecture](architecture.md).*
