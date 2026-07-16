# Editor Authentication and Sessions (M5.4-A1)

## Overview

The Editor uses a Bootstrap → Cookie → CSRF authentication flow.
No permanent URL tokens remain; the old `/session/<TOKEN>/` path returns 404.

## Bootstrap

- Server starts and prints a one-time Bootstrap URL:
  `http://127.0.0.1:<PORT>/bootstrap/<BOOTSTRAP_TOKEN>`
- First GET to this URL:
  1. Atomically validates and consumes the bootstrap token (threading.Lock + compare_digest)
  2. Marks it used in a single critical section
  3. Sets a session cookie
  4. Returns 303 See Other
  5. Location: `/s/<PUBLIC_SESSION_ID>/` (no secrets)
- Replay returns 401
- 8 concurrent requests → exactly 1 × 303, 7 × 401

## Session URL

- `GET /s/<PUBLIC_SESSION_ID>/` — homepage
- `GET /s/<PUBLIC_SESSION_ID>/assets/editor.css|editor.js` — static assets
- `GET /s/<PUBLIC_SESSION_ID>/api/v1/*` — API
- `POST /s/<PUBLIC_SESSION_ID>/api/v1/*` — mutations

`public_session_id` is a non-secret, random hex string:
- Printed in the Location header and URL bar
- Not an authentication credential
- Not equal to the cookie, CSRF, or bootstrap tokens

## Cookie

- **Name**: `yyr4_session_<PUBLIC_SESSION_ID>` (session-isolated)
- **Path**: `/s/<PUBLIC_SESSION_ID>/` (scoped to session)
- **Max-Age**: `idle_timeout - elapsed seconds`, minimum 1 second
- **Attributes**: HttpOnly, SameSite=Strict
- **No Secure**: loopback HTTP — browsers do not send Secure cookies over HTTP
- **No Domain**: not set; cookie scoped to 127.0.0.1

Cookie isolation:
- Path scoping prevents different sessions' cookies from colliding
- Two editors on different ports cannot read each other's cookies

## CSRF

- All POST mutations require header: `X-YYR4-CSRF-Token: <token>`
- CSRF token obtained from authenticated `GET /s/<PUBLIC_SESSION_ID>/api/v1/state`
- CSRF is session-specific; using session A's CSRF on session B returns 401
- No CSRF bypass (no cookie-less mutation path)

## Cookie Parsing

- Uses `http.cookies.SimpleCookie` for structured parsing
- Duplicate cookies explicitly rejected: if the target cookie name appears
  more than once in the raw Cookie header, the request is rejected (401)
- Uses `secrets.compare_digest()` for all secret comparisons:
  - Bootstrap token validation
  - Cookie value validation
  - CSRF token validation

## Cross-Session Isolation

- Each session has unique `public_session_id`, `session_cookie`, and `csrf_token`
- Cookie A (`yyr4_session_pubA`) cannot authenticate on session B (`/s/pubB/`)
- CSRF A rejected by session B
- No cross-session state leakage

## Shutdown

- `POST /s/<PUBLIC_SESSION_ID>/api/v1/shutdown` requires cookie + CSRF
- Supports `dirty_policy`: `keep_recovery`, `discard`, `cancel`
- After shutdown: server thread exits, port closes, session directory deleted

## Removed Features

- `/session/<TOKEN>/` URL token authentication — returns 404
- URL-based CSRF — never in URL, localStorage, sessionStorage, or Recovery

## CLI Compatibility

The old CLI syntax is preserved:
```
yyr4ctl editor --config <SOURCE> [--target <TARGET>]
```
New subcommand syntax:
```
yyr4ctl editor start --config <SOURCE>
```
Both produce a Bootstrap URL. No other interface change.

## Constraints

- 127.0.0.1 only
- No daemon connection
- No hardware access
- No action execution
- No external network access
