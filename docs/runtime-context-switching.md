# Runtime Context Switching

This document details the Active Layer Runtime and Switching architecture implemented in Milestone 3.2.

## Overview

The `yyr4d` daemon now manages an active `RuntimeContext` consisting of:
- `selected_profile`: The currently active profile (e.g., "default", "gaming").
- `active_layer`: The currently active layer within that profile (e.g., "general", "layer_1").

This context replaces the single-layer resolution process, enabling dynamic behavior where a single physical control can perform different actions depending on the active layer.

## Component Architecture

### Runtime Context Manager

The `RuntimeContextManager` safely encapsulates the current state:
- Tracks `selected_profile` and `active_layer`.
- Implements thread-safe access using `asyncio.Lock()`.
- Updates context upon control actions or CLI management requests.
- Recalculates validity during atomic config reloads (fallback to initial layer/profile if missing).
- Triggers context revisions to notify UI or management tools of state changes.

### Event Processing Pipeline

1. **Queueing Events**: `OfficialControlEvent` objects are enqueued rather than pre-resolved plans.
2. **Dequeuing**: The `_executor_loop` retrieves an event.
3. **Context Capture**: It retrieves a snapshot of the current `RuntimeContext`.
4. **Resolution**: `LayeredActionResolver` uses the event and context to yield an `ActionPlan`.
5. **Execution**: The `ActionExecutionEngine` executes the plan. If the plan dictates a context switch, it uses the injected backend to update the runtime context.

### Control Actions

Four new action types natively manage context changes without external dependencies:
- `SetLayerAction`: Direct jump to a specified layer.
- `NextLayerAction`: Cycle forward through the active profile's layers.
- `PreviousLayerAction`: Cycle backward through the active profile's layers.
- `SetProfileAction`: Direct jump to a specified profile.

### Management CLI (`yyr4ctl`)

The Management Server and CLI client have been updated to support runtime context observation and control:
- `get-context`: View the current profile, layer, revision, and change source.
- `set-layer <layer>`: Force a context switch to a new layer.
- `next-layer` / `previous-layer`: Cycle layers from the CLI.
- `set-profile <profile>`: Switch to a different profile, automatically falling back to its initial layer.

## Safety and Concurrency

- **FIFO Guarantee**: Enqueuing events instead of plans ensures that if an event triggers a layer switch, subsequent events in the queue are evaluated against the *new* context.
- **Atomic Operations**: All context updates are synchronized.
- **Config Reloads**: `reconcile_after_reload` handles structural shifts cleanly. If a profile disappears, it falls back to the default profile and initial layer. If only the active layer disappears, it falls back to the initial layer of the current profile.

## Traceability

All context changes track the `ContextChangeSource` (`startup`, `config_reload`, `management_cli`, `control_action`) and increment a monotonically increasing `context_revision` counter. This ensures that downstream observers can accurately track state transitions.
