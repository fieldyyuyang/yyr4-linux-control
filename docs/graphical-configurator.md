# Graphical Configurator

## Milestone 5 Scope

The graphical configurator provides a local, offline interface for:
- Visual official 24-control layout (A1-A12, AL/AP/AR through DL/DP/DR)
- Action editing (all supported types: hotkey, text, command, macro, etc.)
- Profile and Layer management (create, rename, reorder)
- Configuration validation with structured diagnostics
- Daemon status display and diagnostics
- Safe atomic save with diff preview and rollback

The configurator does NOT access hardware directly — it communicates
with `yyr4d` via the management socket or works offline on configuration
files.

## M5.1 Delivered Scope

**Status**: COMPLETE (2026-07-15)

M5.1 delivers the configurator foundation:

| Feature | Status |
|---|---|
| Configurator Core (immutable View Model) | ✓ |
| Self-contained HTML preview | ✓ |
| CLI generation (`yyr4ctl preview`) | ✓ |
| Safe atomic output (symlink protection, same-file detection) | ✓ |
| All 11 action types displayed | ✓ |
| Macro step expansion (recursive, depth-limited) | ✓ |
| 24-control layout (buttons + encoders L/P/R) | ✓ |
| HTML escaping, no external resources | ✓ |
| 642 automated tests | ✓ |
| 30 writer safety tests | ✓ |
| Config editing | ✗ (M5.2) |
| Save / Apply | ✗ (M5.2) |
| Diff preview | ✗ (M5.2) |
| Daemon connection | ✗ (M5.2) |

## Architecture

```
ConfigLoader (control.config)
    │
    ▼
builder.py ──► immutable View Models (frozen dataclasses)
    │
    ▼
html.py ──► self-contained HTML string
    │
    ▼
writer.py ──► atomic file output (tempfile + fsync + os.replace)
    │
    ▼
CLI (management/cli.py) ──► yyr4ctl preview
```

- **ConfigLoader**: Reused from control domain — no custom TOML parsing.
- **builder.py**: Converts `LayeredControlConfig` → `ConfiguratorDocument`.  Handles all 11 action types, official control ordering, and encoder grouping.
- **models.py**: Frozen dataclasses: `ActionView`, `ControlView`, `LayerView`, `ProfileView`, `ConfiguratorDocument`.
- **html.py**: Generates a single self-contained HTML file with inline CSS, no JavaScript, no external resources.
- **writer.py**: Atomic output with symlink rejection, same-file detection, permission hardening.

## View Model

| Model | Fields |
|---|---|
| `ConfiguratorDocument` | schema_version, source_path, default_profile, initial_layer, profile_count, total_layer_count, total_configured_controls, validation_status, diagnostics, profiles |
| `ProfileView` | profile_id, is_default, layer_count, configured_control_count, layers |
| `LayerView` | layer_id, is_initial, configured_control_count, controls (24 items) |
| `ControlView` | official_name, control_kind (button/encoder_*), encoder_group (A-D), configured, action, action_summary |
| `ActionView` | action_type, concise_summary, structured_details, child_steps, warning_flags, side_effect_class |

## Supported Action Display

| Action | side_effect_class | Notes |
|---|---|---|
| Hotkey | desktop_input | Keys displayed as `+`-joined string |
| Text | desktop_input | Content HTML-escaped, truncated at 60 chars |
| Command | command_execution | Executable name shown; argv in structured_details (not rendered) |
| Delay | none | Shown as `N ms` |
| Macro | composite | Steps displayed recursively (depth limit 4) |
| NoOp | none | "(no operation)" |
| DebugLog | diagnostic | Message shown up to 60 chars |
| SetLayer | runtime_context_change | Target layer shown |
| NextLayer | runtime_context_change | |
| PreviousLayer | runtime_context_change | |
| SetProfile | runtime_context_change | Target profile shown |
| Unknown | unknown | Flagged with warning |

## CLI Usage

```bash
# Generate a preview
yyr4ctl preview \
  --config examples/yyr4-control-from-20260711-backup.toml \
  --output /tmp/yyr4-preview.html

# With custom title
yyr4ctl preview \
  --config ~/.config/yyr4/config.toml \
  --output ~/preview.html \
  --title "My YYR4 Layout"

# Overwrite existing file
yyr4ctl preview \
  --config my-config.toml \
  --output existing.html \
  --force
```

Rules:
- `--config` and `--output` are required.
- Output is NOT a symlink (always rejected).
- Output and input must not point to the same file.
- Existing output is rejected unless `--force` is used.
- `--force` does NOT bypass symlink or same-file checks.
- No browser is launched; no HTTP server is started.
- No daemon connection; no hardware access.

## Security Model

- **HTML escaping**: All user text (names, summaries, text content) is escaped via `html.escape()`.
- **No external resources**: Zero CDN references, external fonts, images, CSS, or JavaScript.
- **No inline JavaScript**: HTML is pure declarative.
- **Atomic write**: `tempfile.mkstemp` in output directory → `fsync` → `chmod 644` → `os.replace`.
- **Symlink protection**: Output symlinks are always rejected (even with `--force`).
- **Same-file protection**: Input and output pointing to the same inode are rejected.
- **No live config modification**: The writer never touches `~/.config/yyr4/`.
- **No Action execution**: The configurator only reads configurations.
- **No hardware access**: No evdev, no /dev/input, no xdotool, no daemon.

## Current Limitations

- Read-only — no editing capability.
- No Save or Apply functionality.
- No daemon connection (no live status, no reload).
- No Profile/Layer management UI.
- Structured details (like Command argv) are not rendered in the current HTML output.
- No diff preview between configurations.

## M5.2 (Planned)

Draft Editing, Validation, Diff Preview, and Atomic Save:
- Interactive form-based control/action editor.
- Real-time validation with inline error display.
- Diff preview before save.
- Atomic save with rollback to previous version.
- Profile and Layer creation/management.
