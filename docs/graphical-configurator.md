# Graphical Configurator

## Milestone 5 Scope

The graphical configurator provides a local, offline interface for:
- Visual official 24-control layout (A1-A12, AL/AP/AR through DL/DP/DR)
- Action editing (all 11 supported types)
- Profile and Layer management (create, rename, reorder)
- Configuration validation with structured diagnostics
- Safe atomic save with diff preview, backup, and rollback

The configurator does NOT access hardware directly — it communicates
with `yyr4d` via the management socket or works offline on configuration
files.

## M5.1 — Read-Only Preview

**Status**: COMPLETE (2026-07-15)

Delivers: immutable View Model, self-contained HTML preview (no JS, no external resources), `yyr4ctl preview` CLI, atomic output safety. Test baseline: 662.

## M5.2 — Draft Editing, Validation, Diff, and Safe Save

**Status**: COMPLETE

Delivers: Action Spec (JSON ↔ Action), ConfigDraft (base/working isolation), canonical TOML serializer, 14 Draft CLI commands, Semantic Diff (added/removed/changed/mapped/unmapped with risk), safe atomic save (O_EXCL backup, dual-SHA verification), rollback, Draft Sidecar metadata. Test baseline: 784+.

## M5.3 — Interactive Local Graphical Editor

**Status**: COMPLETE (2026-07-16)

Delivers:
- Local HTTP editor server (127.0.0.1 only)
- Session management (token, isolated directory, idle timeout, cleanup)
- 16 REST API endpoints
- Self-contained HTML + external CSS/JS (no external resources)
- Strict CSP (no unsafe-inline, no unsafe-eval, no inline styles)
- All 11 action types with typed form fields
- Fully typed Macro step editor (no JSON required)
- Profile/Layer management (add/rename/remove, default/initial)
- 24-control hardware layout (Encoder L/P/R)
- Intent-aware Semantic Diff (15 qualified kinds including profile_renamed, layer_renamed)
- Review panel with unified diff
- Save gates (validation, review, dirty check)
- M5.2 concurrency-safe save (backup, atomic write, dual-SHA)
- Real HTTP security boundary testing
- Advanced JSON view (optional, collapsed by default)

Test baseline: 950.

## M5.3 Relationship to M5.2

The Editor reuses M5.2 domain APIs without duplicating configuration logic:
- ConfigDraft (base/working isolation)
- Action Spec (JSON ↔ Action)
- Canonical Serializer (deterministic TOML)
- Semantic Diff (diff_configs / diff_draft)
- Draft Sidecar (metadata tracking)
- save_draft (atomic save with concurrency protection)

The browser layer only displays and sends operations — configuration semantics live in the M5.2 domain.

## Current Limitations

- No daemon connection
- No hardware access
- No action execution
- No automatic daemon reload
- No remote/LAN access (127.0.0.1 only)
- No persistence of unsaved drafts between sessions
