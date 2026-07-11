# Development Roadmap

This roadmap defines the sequential dependencies for the project. Moving to the next milestone requires passing all gates of the current one.

## Milestone 0: Device & Physical Event Audit (Completed)
* **Goal**: Establish architecture and execute a read-only audit of raw `evdev` packets.
* **Deliverables**: Product documentation, event log tables.
* **Validation Gate**: Physical controls uniquely identified in logs.
* **Security Gate**: No arbitrary code execution required for logging.
* **Non-goals**: Writing the mapping engine.
* **Exit Criteria**: A populated mapping table mapping physical inputs to logical IDs.

## Milestone 1: Userspace Transport Daemon MVP

* **Milestone 1.0 (COMPLETED)**: Project bootstrap and transport-code parser core.
* **Milestone 1.1 (COMPLETED)**: Safe device discovery and evdev input adapter.
* **Milestone 1.2 (COMPLETED)**: Read-only control observation pipeline (simulated tests complete, read-only, fail-closed model).
* **Goal**: A foundational daemon reading `evdev`.
* **Deliverables**: Python daemon, precise `udev` rules.
* **Validation Gate**: Reads inputs exclusively from the YYR4.
* **Security Gate**: Users not added to global `input` group.
* **Non-goals**: Profile execution.
* **Exit Criteria**: Terminal outputs raw events cleanly.

## Milestone 2: Device Learning & Event Normalization
* **Goal**: Convert raw packets into `button.k01.down`.
* **Deliverables**: Normalization module.
* **Validation Gate**: Handles debounce and missing press/release states safely.
* **Security Gate**: Drops invalid evdev types.
* **Non-goals**: Graphical UI.
* **Exit Criteria**: Monitor CLI shows normalized events.

## Milestone 3: uinput Mapping MVP & Level 1 Approvals
* **Goal**: Hardcoded mappings resulting in virtual keystrokes (including Vibe Coding Level 1).
* **Deliverables**: `uinput` sink.
* **Validation Gate**: Virtual events register in X11 applications.
* **Security Gate**: Panic/Emergency stop halts `uinput`.
* **Non-goals**: JSON configurations.
* **Exit Criteria**: Key presses emit synthesized events.

## Milestone 4: Profile, Layer, and Action Engine
* **Goal**: Schema-driven dynamic behavior.
* **Deliverables**: SQLite DB, JSON schemas, Action model.
* **Validation Gate**: Schema successfully validates or rejects inputs.
* **Security Gate**: SQL injection protection.
* **Non-goals**: Web frontend.
* **Exit Criteria**: Daemon loads and runs valid JSON profiles.

## Milestone 5: X11 Context Switching
* **Goal**: Auto-switch Profiles based on Window properties.
* **Deliverables**: Context Engine using X11/EWMH.
* **Validation Gate**: Profile changes when clicking different apps.
* **Security Gate**: Window matching handles malformed window titles gracefully.
* **Non-goals**: Wayland support.
* **Exit Criteria**: Active Profile updates accurately on focus change.

## Milestone 6: Web API & WebSocket
* **Goal**: Expose backend state securely.
* **Deliverables**: FastAPI / HTTP interface.
* **Validation Gate**: Clients can connect and read state.
* **Security Gate**: Bound strictly to `127.0.0.1`.
* **Non-goals**: LAN access.
* **Exit Criteria**: API documentation generated and functional.

## Milestone 7: Web UI MVP
* **Goal**: Basic configuration dashboard.
* **Deliverables**: React/Vite SPA.
* **Validation Gate**: Can read and display current mappings.
* **Security Gate**: CORS restricted.
* **Non-goals**: Advanced visual editors.
* **Exit Criteria**: User can change a binding via the browser.

## Milestone 8: Visual Editors & CLI Adapters
* **Goal**: Graphic layout editor, Macro designer, and Vibe Coding CLI Adapters.
* **Deliverables**: Drag-and-drop interfaces, CLI matching logic.
* **Validation Gate**: Complex macros save and execute correctly.
* **Security Gate**: Command allowlists strictly enforced.
* **Non-goals**: Third-party plugins.
* **Exit Criteria**: Web UI replaces all manual config editing.

## Milestone 9: Professional Profile Library
* **Goal**: Bundled templates.
* **Deliverables**: Pre-configured JSON profiles for the 14 use cases.
* **Validation Gate**: Templates import without errors.
* **Security Gate**: High-risk actions prompt users on import.
* **Non-goals**: Community sharing hub.
* **Exit Criteria**: 14 templates available in Web UI.

## Milestone 10: Packaging
* **Goal**: Distribution ready.
* **Deliverables**: `systemd` user services, Debian `.deb`.
* **Validation Gate**: Installs cleanly on Debian 13.
* **Security Gate**: Permissions set according to least privilege.
* **Non-goals**: Cross-platform installers.
* **Exit Criteria**: `.deb` generates and installs successfully.

## Milestone 11: Wayland Adapter
* **Goal**: Context switching for Wayland compositors.
* **Deliverables**: Desktop Adapter abstraction.
* **Validation Gate**: Works on GNOME Wayland.
* **Security Gate**: Complies with Wayland security models.
* **Non-goals**: Supporting every minor compositor.
* **Exit Criteria**: Context switches correctly under Wayland.

## Milestone 12: Protocol Research & Level 3 Approvals
* **Goal**: Investigate **[Planned]** RGB control, MIDI, persistence, and Prompt-Aware AI integrations.
* **Deliverables**: Research docs, feature prototypes.
* **Validation Gate**: Features tested against actual firmware.
* **Security Gate**: Hardware bricking risks mitigated.
* **Non-goals**: Guaranteeing support for locked hardware features.
* **Exit Criteria**: Feasibility reports published.

## Milestone 13: Plugin Ecosystem
* **Goal**: Third-party extensibility.
* **Deliverables**: Plugin API.
* **Validation Gate**: External scripts can register Actions.
* **Security Gate**: Plugins run in restricted scopes.
* **Non-goals**: Creating a marketplace.
* **Exit Criteria**: An example plugin successfully integrates.
