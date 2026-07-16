# Local Graphical Configuration Editor

## Architecture

The M5.3 editor is a self-contained, browser-based configuration editor that runs entirely offline:

```
yyr4ctl editor --config SOURCE --target TARGET
  │
  ▼
EditorServer (configurator/web/server.py)
  │
  ├── EditorSession (session.py) — Draft lifecycle, token, cleanup
  ├── Security (security.py) — CSP, Origin, Host, Token validation
  ├── API (api.py) — REST endpoints, M5.2 integration
  └── Templates (templates.py) — Self-contained HTML+CSS+JS UI
```

All editing goes through M5.2 domain APIs:

- **ConfigDraft** — base/working isolation
- **Action Spec** — JSON ↔ Action bidirectional
- **Canonical Serializer** — deterministic TOML output
- **Semantic Diff** — structured change tracking with risk classification
- **Sidecar** — metadata tracking (SHA, mutations, timestamps)
- **save_draft** — atomic save with backup, concurrency protection
- **restore_backup** — safe rollback

## CLI Usage

```bash
yyr4ctl editor \
  --config examples/yyr4-control-from-20260711-backup.toml \
  --target /tmp/yyr4-edited.toml \
  --port 0
```

Options:
- `--config` — Source schema v2 configuration (required)
- `--target` — Save target path (default: same as config)
- `--backup-dir` — Optional backup directory
- `--port 0` — OS-assigned ephemeral port (default)
- `--idle-timeout 1800` — Auto-shutdown after inactivity (seconds)
- `--open-browser` — Explicitly launch system browser

Defaults:
- Binds 127.0.0.1 only
- Does not open browser automatically
- Does not connect to daemon
- Does not access hardware
- Does not execute actions

## Session Lifecycle

1. **Create**: `yyr4ctl editor` creates an isolated session directory
   - `$XDG_RUNTIME_DIR/yyr4/editor/<session-id>/`
   - Directory mode 0700
   - Draft and sidecar mode 0600
   - Random session token (`secrets.token_urlsafe(32)`)

2. **Active**: HTTP server handles API requests
   - Token-gated access via URL path
   - Idle timeout monitoring
   - Atomic draft updates after each mutation

3. **Shutdown**: UI button, Ctrl+C, or idle timeout
   - HTTP server stopped
   - Session directory cleaned
   - Source, target, and backups preserved
   - Idempotent (safe to call multiple times)

## Security Model

### Network
- Binds 127.0.0.1 only
- Random ephemeral port
- No CORS (same-origin only)
- Origin validation (loopback patterns only)
- Host validation (127.0.0.1 only)
- No external network access

### Authentication
- Session token in URL path
- `secrets.token_urlsafe(32)` generation
- All mutation endpoints require valid token
- Invalid/missing token returns 401

### HTTP Headers
- Content-Security-Policy: strict self-only
- X-Content-Type-Options: nosniff
- Referrer-Policy: no-referrer
- Cache-Control: no-store
- X-Frame-Options: DENY
- Permissions-Policy: camera/microphone/geolocation disabled

### Request Guards
- Body size limit: 256 KiB
- Content-Type: application/json only for POST
- Path traversal detection
- No arbitrary file paths accepted

## API Endpoints

All under `/session/<TOKEN>/api/v1/`:

### State
- `GET /state` — Full configuration state

### Control Mutations
- `POST /control/set-action` — Set a control's action
- `POST /control/clear-action` — Clear a control's mapping

### Profile Mutations
- `POST /profile/add`
- `POST /profile/rename`
- `POST /profile/remove`
- `POST /profile/set-default`

### Layer Mutations
- `POST /layer/add`
- `POST /layer/rename`
- `POST /layer/remove`
- `POST /layer/set-initial`

### Review
- `GET /validate` — Validation diagnostics
- `GET /diff` — Semantic diff with risk classification
- `GET /diff/unified` — Textual unified diff

### Persistence
- `POST /save` — Atomic save with M5.2 safety
- `POST /shutdown` — Graceful shutdown

## UI Layout

### Top Bar
- Source/Target filenames
- SHA fingerprints (truncated)
- Dirty/Clean status
- Validation status
- Mutation counter
- Validate / Review / Save / Shutdown buttons

### Left Panel — Profile & Layer Navigation
- Profile list with default indicator
- Add / Rename / Remove / Set Default buttons
- Layer list for selected profile with initial indicator
- Add / Rename / Remove / Set Initial buttons

### Center — YYR4 Hardware Layout
- A1-A12 buttons in 3×4 grid
- Encoder A-D groups with Left / Press / Right

### Right/Bottom — Action Editor
- Action type picker (all 11 types)
- Type-specific form fields
- Apply / Clear buttons

### Review Panel
- Semantic diff changes list
- Risk classification (LOW/MEDIUM/HIGH)
- Unified textual diff
- Review confirmation

## Save Workflow

1. User makes edits (mutations increment counter)
2. Validation runs after each mutation
3. User opens Review panel to see semantic diff
4. User confirms review
5. Save button enabled (requires: dirty, valid, reviewed)
6. Confirmation dialog shows target, SHA, changes, risk
7. M5.2 `save_draft()` called with:
   - Expected SHA check
   - No-replace for new files
   - Dual-SHA verification for existing
   - O_EXCL backup creation
   - Atomic replace with fsync
8. Post-save: base refreshed for subsequent edits

## Current Limitations

- No daemon connection
- No hardware access
- No action execution
- No automatic daemon reload
- No remote/LAN access
- IPv4 only (127.0.0.1)
- No persistence of unsaved drafts between sessions

## M5.2 Integration Points

| M5.2 Component | Usage |
|---|---|
| ConfigDraft | Session draft object |
| parse_spec / action_to_spec | Action editing |
| Serializer | Draft persistence |
| diff_configs / unified_diff | Review panel |
| save_draft | Atomic save |
| Sidecar | Metadata tracking |
| restore_backup | Fallback (planned M5.4) |
