"""Self-contained HTTP server for the local graphical editor.

Binds 127.0.0.1 only, uses a random ephemeral port, and gates all
mutations behind a session token.  Serves CSS and JS as external,
token-gated resources with strict Content-Security-Policy.
"""

from __future__ import annotations
import json
import os
import secrets
import sys
import threading
import time
import traceback
import urllib.parse
from http.cookies import SimpleCookie
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Optional, Dict

from .session import EditorSession, create_session
from .security import (
    SECURITY_HEADERS, STRICT_CSP, MAX_BODY_SIZE, ALLOWED_METHODS,
    validate_origin, validate_host, validate_content_type,
    safe_path, is_allowed_asset, error_json,
)
from . import api as editor_api


# ═══════════════════════════════════════════════════════════════════
#  Static assets (CSS / JS)
# ═══════════════════════════════════════════════════════════════════

_EDITOR_HTML = None
_EDITOR_CSS = None
_EDITOR_JS = None


def _get_editor_html() -> str:
    global _EDITOR_HTML
    if _EDITOR_HTML is None:
        from .templates import render_editor_page
        _EDITOR_HTML = render_editor_page()
    return _EDITOR_HTML


def _get_editor_css() -> str:
    global _EDITOR_CSS
    if _EDITOR_CSS is None:
        from .templates import EDITOR_CSS
        _EDITOR_CSS = EDITOR_CSS
    return _EDITOR_CSS


def _get_editor_js() -> str:
    global _EDITOR_JS
    if _EDITOR_JS is None:
        from .templates import EDITOR_JS
        _EDITOR_JS = EDITOR_JS
    return _EDITOR_JS


# ═══════════════════════════════════════════════════════════════════
#  Request handler
# ═══════════════════════════════════════════════════════════════════

class _EditorHandler(BaseHTTPRequestHandler):
    """Per-request handler with security checks and API routing."""

    server_version = "yyr4-editor"
    sys_version = ""
    error_message_format = "%(code)d - %(message)s"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        pass  # suppress default stderr logging

    # ── Response helpers ───────────────────────────────────────────

    def _send_json(self, data: dict, status: int = 200):
        body = json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        for k, v in SECURITY_HEADERS.items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html: str, status: int = 200):
        body = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        for k, v in SECURITY_HEADERS.items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _send_css(self, css: str, status: int = 200):
        body = css.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/css; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        for k, v in SECURITY_HEADERS.items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _send_js(self, js: str, status: int = 200):
        body = js.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/javascript; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        for k, v in SECURITY_HEADERS.items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, code: str, status: int = 400,
                    message: str = "", path: str = "",
                    details: dict = None):
        body = error_json(code, message, path, details)
        b = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        for k, v in SECURITY_HEADERS.items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(b)

    # ── Security validation ────────────────────────────────────────

    def _check_security(self) -> bool:
        """Return True if the request should be rejected."""
        host = self.headers.get("Host", "")
        ok, err = validate_host(host)
        if not ok:
            self._send_error(err, 403)
            return True

        if self.command not in ALLOWED_METHODS:
            self._send_error("invalid_request", 405,
                             f"Method not allowed: {self.command}")
            return True

        content_type = self.headers.get("Content-Type", "")
        ok, err = validate_content_type(content_type, self.command)
        if not ok:
            self._send_error(err, 400)
            return True

        cl = self.headers.get("Content-Length", "0")
        try:
            cl_int = int(cl)
        except ValueError:
            self._send_error("invalid_request", 400, "Bad Content-Length")
            return True
        if cl_int > MAX_BODY_SIZE:
            self._send_error("payload_too_large", 413)
            return True

        return False

    def _get_session(self, require_cookie: bool = True) -> Optional[EditorSession]:
        """Authenticate via Cookie only. Returns session or None."""
        path = self.path.split("?")[0]
        parts = [p for p in path.split("/") if p]

        # Bootstrap route: /bootstrap/<TOKEN>
        if len(parts) == 2 and parts[0] == "bootstrap":
            token = parts[1]
            for s in self.server._sessions.values():
                if s.bootstrap_token and secrets.compare_digest(s.bootstrap_token, token) and not s.bootstrap_used:
                    return s
            return None

        if not require_cookie:
            return None

        cookie_header = self.headers.get("Cookie", "")
        if not cookie_header:
            return None

        try:
            sc = SimpleCookie()
            sc.load(cookie_header)
        except Exception:
            return None

        # Explicit duplicate detection: each yyr4_session_* cookie must appear at most once
        pairs = [p.strip() for p in cookie_header.split(';')]
        counts = {}
        for p in pairs:
            if '=' in p:
                k = p.split('=')[0].strip()
                counts[k] = counts.get(k, 0) + 1
        for s in self.server._sessions.values():
            cname = f"yyr4_session_{s.public_session_id}"
            if counts.get(cname, 0) > 1:
                return None  # Duplicate cookie

        # Extract session ID from path: /s/<public_session_id>/...
        pub_id = None
        for s in self.server._sessions.values():
            if len(parts) >= 2 and parts[0] == "s" and parts[1] == s.public_session_id:
                pub_id = s.public_session_id
                break
        if pub_id is None:
            return None

        # Find matching session by cookie
        cname = f"yyr4_session_{pub_id}"
        cookie_val = sc.get(cname)
        if cookie_val is None:
            return None

        for s in self.server._sessions.values():
            if s.public_session_id == pub_id and s.session_cookie and                secrets.compare_digest(s.session_cookie, cookie_val.value):
                return s
        return None

    def _check_csrf(self, session: EditorSession) -> bool:
        """Verify CSRF token for all POST mutations — mandatory."""
        if self.command != "POST":
            return True
        expected = session.csrf_token
        actual = self.headers.get("X-YYR4-CSRF-Token", "")
        return bool(expected and secrets.compare_digest(expected, actual))

    # ── Routing ────────────────────────────────────────────────────

    def _route_parts(self):
        """Return (parts-list, is-homepage, is-asset, asset-name)."""
        path = self.path.split("?")[0]
        parts = [p for p in path.split("/") if p]

        # /session/<token>/
        if len(parts) == 2 and parts[0] == "session":
            return (parts, True, False, None)

        # /session/<token>/assets/<name>
        if (len(parts) >= 4 and parts[0] == "session"
                and parts[2] == "assets"):
            asset_name = parts[3]
            return (parts, False, True, asset_name)

        # /session/<token>/api/v1/...
        return (parts, False, False, None)

    def do_GET(self):
        # Bootstrap must work before security checks (needs different headers)
        bpath = self.path.split("?")[0]
        bp = [p for p in bpath.split("/") if p]
        if len(bp) == 2 and bp[0] == "bootstrap":
            session = self._get_session(require_cookie=False)
            if session is None or not session.consume_bootstrap_token(bp[1]):
                self._send_error("unauthorized", 401)
                return
            session.touch()
            remaining = max(1, int(self.server._idle_timeout - (time.time() - session.last_activity)))
            location = f"/s/{session.public_session_id}/"
            self.send_response(303)
            self.send_header("Location", location)
            cname = f"yyr4_session_{session.public_session_id}"
            cval = f"{cname}={session.session_cookie}; HttpOnly; SameSite=Strict; Path=/s/{session.public_session_id}/; Max-Age={remaining}"
            self.send_header("Set-Cookie", cval)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if self._check_security():
            return



        # ── Legacy /session/<TOKEN>/... → 404 ──
        if len(bp) >= 2 and bp[0] == "session":
            self._send_error("invalid_request", 404, "URL token auth removed; use bootstrap")
            return

        # ── /s/<pubid>/... routing ──
        session = self._get_session()
        if session is None:
            self._send_error("unauthorized", 401)
            return
        session.touch()

        # Build path relative to /s/<pubid>/
        rel = bp[2:] if len(bp) >= 3 else []

        # Homepage: /s/<pubid>/
        if len(rel) == 0:
            self._send_html(_get_editor_html())
            return

        # Assets: /s/<pubid>/assets/...
        if len(rel) >= 2 and rel[0] == "assets":
            an = rel[1]
            if not is_allowed_asset(an):
                self._send_error("invalid_request", 404, f"Unknown asset: {an}")
                return
            if an == "editor.css": self._send_css(_get_editor_css())
            elif an == "editor.js": self._send_js(_get_editor_js())
            return

        # API: /s/<pubid>/api/v1/...
        if len(rel) >= 3 and rel[0] == "api":
            api_path = "/" + "/".join(rel)

        try:
            if api_path == "/api/v1/state":
                result = editor_api.build_state(session)
                result["csrf_token"] = session.csrf_token
                self._send_json({"status": "ok", **result})
            elif api_path == "/api/v1/validate":
                self._send_json(editor_api.handle_validate(session))
            elif api_path == "/api/v1/diff":
                self._send_json(editor_api.handle_diff(session))
            elif api_path == "/api/v1/diff/unified":
                self._send_json(editor_api.handle_unified_diff(session))
            else:
                self._send_error("invalid_request", 404,
                                 f"Unknown API path: {api_path}")
        except Exception:
            traceback.print_exc(file=sys.stderr)
            self._send_error("internal_error", 500)

    def do_POST(self):
        if self._check_security():
            return

        parts, is_home, is_asset, _ = self._route_parts()
        if is_home or is_asset:
            self._send_error("invalid_request", 405, "Method not allowed")
            return

        session = self._get_session()
        if session is None:
            self._send_error("unauthorized", 401)
            return
        session.touch()
        if not self._check_csrf(session):
            self._send_error("unauthorized", 401, "Missing or invalid CSRF token")
            return
        # Build API path from filtered parts
        api_path = "/" + "/".join(parts[2:]) if len(parts) > 2 else "/"
        if len(parts) >= 2 and parts[0] == "api":
            api_path = "/" + "/".join(parts)

        # Read body
        cl = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(cl) if cl > 0 else b"{}"

        try:
            body = json.loads(raw.decode("utf-8")) if raw else {}
        except json.JSONDecodeError:
            self._send_error("invalid_json", 400)
            return

        try:
            if api_path == "/api/v1/control/set-action":
                self._send_json(editor_api.handle_set_action(session, body))
                session.write_recovery()
                session.write_registry()
            elif api_path == "/api/v1/control/clear-action":
                self._send_json(editor_api.handle_clear_action(session, body))
                session.write_recovery()
                session.write_registry()
            elif api_path == "/api/v1/profile/add":
                self._send_json(editor_api.handle_add_profile(session, body))
                session.write_recovery()
                session.write_registry()
            elif api_path == "/api/v1/profile/rename":
                self._send_json(editor_api.handle_rename_profile(session, body))
                session.write_recovery()
                session.write_registry()
            elif api_path == "/api/v1/profile/remove":
                self._send_json(editor_api.handle_remove_profile(session, body))
                session.write_recovery()
                session.write_registry()
            elif api_path == "/api/v1/profile/set-default":
                self._send_json(editor_api.handle_set_default_profile(session, body))
                session.write_recovery()
                session.write_registry()
            elif api_path == "/api/v1/layer/add":
                self._send_json(editor_api.handle_add_layer(session, body))
                session.write_recovery()
                session.write_registry()
            elif api_path == "/api/v1/layer/rename":
                self._send_json(editor_api.handle_rename_layer(session, body))
                session.write_recovery()
                session.write_registry()
            elif api_path == "/api/v1/layer/remove":
                self._send_json(editor_api.handle_remove_layer(session, body))
                session.write_recovery()
                session.write_registry()
            elif api_path == "/api/v1/layer/set-initial":
                self._send_json(editor_api.handle_set_initial_layer(session, body))
                session.write_recovery()
                session.write_registry()
            elif api_path == "/api/v1/save":
                self._send_json(editor_api.handle_save(session, body))
                if session.draft and not session.dirty:
                    session.discard_recovery()
                session.write_registry()
            elif api_path == "/api/v1/shutdown":
                # Parse dirty_policy from body
                policy = body.get("dirty_policy", "keep_recovery") if isinstance(body, dict) else "keep_recovery"
                if policy not in ("keep_recovery", "discard", "cancel"):
                    self._send_error("invalid_request", 400, f"Unknown dirty_policy: {policy}")
                    return
                if policy == "cancel":
                    self._send_json({"status": "ok", "message": "Shutdown cancelled"})
                    return
                self._send_json({"status": "ok", "message": "Shutting down", "policy": policy})
                session.dirty_policy = policy
                t = threading.Thread(target=self._delayed_shutdown, daemon=True)
                t.start()
            else:
                self._send_error("invalid_request", 404,
                                 f"Unknown API path: {api_path}")
        except KeyError as e:
            self._send_error("invalid_request", 400,
                             f"Missing required field: {e}")
        except Exception:
            traceback.print_exc(file=sys.stderr)
            self._send_error("internal_error", 500)

    def do_OPTIONS(self):
        """Limited CORS — mostly deny."""
        self.send_response(405)
        self.send_header("Allow", "GET, POST")
        for k, v in SECURITY_HEADERS.items():
            self.send_header(k, v)
        self.end_headers()

    def _delayed_shutdown(self):
        time.sleep(0.5)
        self.server._shutdown_flag = True


# ═══════════════════════════════════════════════════════════════════
#  HTTP Server
# ═══════════════════════════════════════════════════════════════════

class _EditorServer(HTTPServer):
    """HTTP server bound to 127.0.0.1 with session management."""

    allow_reuse_address = True

    def __init__(self, host: str, port: int, idle_timeout: float = 1800):
        super().__init__((host, port), _EditorHandler)
        self._sessions: Dict[str, EditorSession] = {}
        self._shutdown_flag = False
        self.host = host
        self.port = self.server_address[1]
        self._idle_timeout = idle_timeout

    def add_session(self, session: EditorSession) -> None:
        self._sessions[session.public_session_id] = session

    def get_session(self, token: str) -> Optional[EditorSession]:
        return self._sessions.get(token)


class EditorServer:
    """High-level wrapper: create session, start server, manage lifecycle."""

    def __init__(
        self,
        source_path: str,
        target_path: str,
        backup_dir: Optional[str] = None,
        port: int = 0,
        idle_timeout: float = 1800,
        open_browser: bool = False,
    ):
        self._source_path = source_path
        self._target_path = target_path
        self._backup_dir = backup_dir
        self._port = port
        self._idle_timeout = idle_timeout
        self._open_browser = open_browser
        self._httpd: Optional[_EditorServer] = None
        self._session: Optional[EditorSession] = None
        self._thread: Optional[threading.Thread] = None

    @property
    def listen_host(self) -> str:
        return "127.0.0.1"

    @property
    def listen_port(self) -> int:
        if self._httpd:
            return self._httpd.port
        return 0

    @property
    def session_token(self) -> Optional[str]:
        if self._session:
            return self._session.session_token
        return None

    def url(self) -> str:
        if self._session:
            return f"http://{self.listen_host}:{self.listen_port}/bootstrap/{self._session.bootstrap_token}"
        return ""

    def start(self) -> str:
        session = create_session(
            self._source_path, self._target_path, self._backup_dir,
        )
        self._session = session

        self._httpd = _EditorServer(self.listen_host, self._port, self._idle_timeout)
        self._httpd.add_session(session)
        self._port = self._httpd.server_address[1]

        url = self.url()

        print(f"Editor started: {url}", flush=True)
        print(f"  Source: {self._source_path}", flush=True)
        print(f"  Target: {self._target_path}", flush=True)
        print(f"  Session timeout: {self._idle_timeout}s", flush=True)
        print(f"  No daemon or hardware connection.", flush=True)

        if self._open_browser:
            self._launch_browser(url)
        else:
            print(f"  Open this URL in your browser to start editing.", flush=True)

        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        return url

    def _run_loop(self):
        assert self._httpd is not None
        idle_check = max(1.0, self._idle_timeout / 10)

        while not self._httpd._shutdown_flag:
            if self._session and self._session.is_expired(self._idle_timeout):
                print("Session idle timeout reached — shutting down.")
                break

            self._httpd.timeout = idle_check
            try:
                self._httpd.handle_request()
            except Exception:
                traceback.print_exc(file=sys.stderr)

        self._shutdown()

    def _shutdown(self):
        if self._session:
            self._session.shutdown(policy=self._session.dirty_policy)
        if self._httpd:
            try:
                self._httpd.server_close()
            except Exception:
                pass
        if self._session:
            try:
                parent = Path(self._session.session_dir).parent
                if parent.exists() and not any(parent.iterdir()):
                    parent.rmdir()
            except OSError:
                pass

    def _launch_browser(self, url: str):
        import subprocess
        try:
            subprocess.Popen(["xdg-open", url],
                             stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
        except Exception:
            pass

    def stop(self):
        if self._httpd:
            self._httpd._shutdown_flag = True
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        self._shutdown()
