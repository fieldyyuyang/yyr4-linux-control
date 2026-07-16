# Local Graphical Configuration Editor

## Architecture

```
Browser → Loopback HTTP → EditorServer → Editor API → ConfigDraft / Action Spec / Intent-aware Diff → save_draft
```

Components:
- `session.py` — Token-gated session lifecycle
- `security.py` — CSP, Host/Origin validation, path traversal, body limits
- `server.py` — HTTP server bound to 127.0.0.1
- `api.py` — 16 REST endpoints integrating M5.2 domain
- `templates.py` — Self-contained HTML + external CSS/JS resources

## CLI Usage

```bash
yyr4ctl editor \
  --config SOURCE \
  [--target TARGET] \
  [--backup-dir DIRECTORY] \
  [--port 0] \
  [--idle-timeout 1800] \
  [--open-browser]
```

Defaults: 127.0.0.1 only, port=0 (OS-assigned), no browser auto-launch, no daemon reload.

## 16 REST API Endpoints

**GET:**
1. `state` — Full configuration state
2. `validate` — Validation diagnostics
3. `diff` — Semantic diff with intent-aware renames
4. `diff/unified` — Textual unified diff

**POST:**
5. `control/set-action`
6. `control/clear-action`
7. `profile/add`
8. `profile/rename`
9. `profile/remove`
10. `profile/set-default`
11. `layer/add`
12. `layer/rename`
13. `layer/remove`
14. `layer/set-initial`
15. `save`
16. `shutdown`

## 15 Semantic Diff Kinds

- `profile_added`, `profile_removed`, `profile_renamed`
- `layer_added`, `layer_removed`, `layer_renamed`
- `control_mapped`, `control_unmapped`, `control_action_changed`
- `macro_step_added`, `macro_step_removed`, `macro_step_changed`
- `default_profile_changed`, `initial_layer_changed`
- `runtime_target_changed`

`diff_draft()` uses ConfigDraft mutation records for intent-aware rename detection. Standalone `diff_configs()` produces add/remove for independent comparison.

## Typed Macro Editor

Each macro step provides:
- Step number
- Action type selector (all 11 types)
- Type-specific form fields (no JSON required)
- Add Before / Add After
- Delete
- Move Up / Move Down

**Advanced JSON** view is available but collapsed by default — not required for any normal operation.

## Security

- **CSP**: `script-src 'self'; style-src 'self'` — no `unsafe-inline` or `unsafe-eval`
- **CSS/JS**: External resources served via token-gated `/session/<TOKEN>/assets/` paths
- **Token**: `secrets.token_urlsafe(32)`, all mutations require valid token
- **Host**: 127.0.0.1 only
- **Origin**: Loopback patterns only
- **Body limit**: 256 KiB
- **Path traversal**: Encoded form rejection (`..%2f`, `%252e`, `%5c`, etc.)
- **Asset whitelist**: Only `editor.css` / `editor.js`
- **Session cleanup**: Directory removed on shutdown

## Save and Review Gates

- Save enabled only when: dirty + valid + reviewed
- Review must be confirmed for current mutation version
- Uses M5.2 `save_draft()`: atomic, O_EXCL backup, dual-SHA verification

## Non-Goals

- No daemon connection
- No hardware access
- No action execution
- No desktop input
- No browser auto-launch
- No external network access
- No automatic reload
