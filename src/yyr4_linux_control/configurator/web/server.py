"""Self-contained HTTP server for the local graphical editor.

Binds 127.0.0.1 only, uses a random ephemeral port, and gates all
mutations behind a session token.
"""

from __future__ import annotations
import json
import os
import signal
import socket
import sys
import threading
import time
import traceback
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Optional, Dict

from .session import EditorSession, create_session
from .security import (
    SECURITY_HEADERS, MAX_BODY_SIZE, ALLOWED_METHODS,
    validate_origin, validate_host, validate_content_type,
    safe_path, error_json,
)
from . import api as editor_api


# ── HTML page ──────────────────────────────────────────────────────

_EDITOR_HTML = None


def _get_editor_html() -> str:
    global _EDITOR_HTML
    if _EDITOR_HTML is None:
        from .templates import render_editor_page
        _EDITOR_HTML = render_editor_page()
    return _EDITOR_HTML


# ── Request handler ────────────────────────────────────────────────

class _EditorHandler(BaseHTTPRequestHandler):
    """Per-request handler with security checks and API routing."""

    server_version = "yyr4-editor"
    sys_version = ""
    error_message_format = "%(code)d - %(message)s"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        """Suppress default stderr logging in production."""
        pass

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
        # Relax CSP slightly for the main page (which is self-contained)
        headers = dict(SECURITY_HEADERS)
        headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "connect-src 'self'; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self'"
        )
        for k, v in headers.items():
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

    def _check_security(self) -> Optional[dict]:
        """Return error response dict if security check fails, else None."""
        host = self.headers.get("Host", "")
        ok, err = validate_host(host)
        if not ok:
            return self._send_error(err, 403)

        if self.command not in ALLOWED_METHODS:
            return self._send_error("invalid_request", 405,
                                     f"Method not allowed: {self.command}")

        content_type = self.headers.get("Content-Type", "")
        ok, err = validate_content_type(content_type, self.command)
        if not ok:
            return self._send_error(err, 400)

        # Check body size
        cl = self.headers.get("Content-Length", "0")
        try:
            cl_int = int(cl)
        except ValueError:
            return self._send_error("invalid_request", 400, "Bad Content-Length")
        if cl_int > MAX_BODY_SIZE:
            return self._send_error("payload_too_large", 413)

        return None

    def _get_session(self) -> Optional[EditorSession]:
        """Extract and validate the session token from the path."""
        path = self.path.split("?")[0]
        parts = [p for p in path.split("/") if p]

        if len(parts) < 3 or parts[0] != "session":
            return None

        token = parts[1]
        server = self.server  # type: _EditorServer
        session = server._sessions.get(token)
        if session is None:
            return None
        return session

    # ── Routing ────────────────────────────────────────────────────

    def do_GET(self):
        if self._check_security():
            return

        path = self.path.split("?")[0]
        parts = [p for p in path.split("/") if p]

        # Session page: /session/<token>/
        if len(parts) == 2 and parts[0] == "session":
            token = parts[1]
            session = self.server._sessions.get(token)  # type: ignore
            if session is None:
                self._send_error("unauthorized", 401)
                return
            session.touch()
            self._send_html(_get_editor_html())
            return

        # API routes: /session/<token>/api/v1/...
        session = self._get_session()
        if session is None:
            self._send_error("unauthorized", 401)
            return
        session.touch()

        api_path = "/" + "/".join(parts[2:]) if len(parts) > 2 else "/"

        try:
            if api_path == "/api/v1/state":
                result = editor_api.build_state(session)
                self._send_json({"status": "ok", **result})
            elif api_path == "/api/v1/validate":
                self._send_json(editor_api.handle_validate(session))
            elif api_path == "/api/v1/diff":
                self._send_json(editor_api.handle_diff(session))
            elif api_path == "/api/v1/diff/unified":
                self._send_json(editor_api.handle_unified_diff(session))
            else:
                self._send_error("invalid_request", 404, f"Unknown API path: {api_path}")
        except Exception:
            traceback.print_exc(file=sys.stderr)
            self._send_error("internal_error", 500)

    def do_POST(self):
        if self._check_security():
            return

        session = self._get_session()
        if session is None:
            self._send_error("unauthorized", 401)
            return
        session.touch()

        api_path = "/" + "/".join(self.path.split("?")[0].split("/")[3:])

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
            elif api_path == "/api/v1/control/clear-action":
                self._send_json(editor_api.handle_clear_action(session, body))
            elif api_path == "/api/v1/profile/add":
                self._send_json(editor_api.handle_add_profile(session, body))
            elif api_path == "/api/v1/profile/rename":
                self._send_json(editor_api.handle_rename_profile(session, body))
            elif api_path == "/api/v1/profile/remove":
                self._send_json(editor_api.handle_remove_profile(session, body))
            elif api_path == "/api/v1/profile/set-default":
                self._send_json(editor_api.handle_set_default_profile(session, body))
            elif api_path == "/api/v1/layer/add":
                self._send_json(editor_api.handle_add_layer(session, body))
            elif api_path == "/api/v1/layer/rename":
                self._send_json(editor_api.handle_rename_layer(session, body))
            elif api_path == "/api/v1/layer/remove":
                self._send_json(editor_api.handle_remove_layer(session, body))
            elif api_path == "/api/v1/layer/set-initial":
                self._send_json(editor_api.handle_set_initial_layer(session, body))
            elif api_path == "/api/v1/save":
                self._send_json(editor_api.handle_save(session, body))
            elif api_path == "/api/v1/shutdown":
                self._send_json({"status": "ok", "message": "Shutting down"})
                # Schedule shutdown after response
                t = threading.Thread(target=self._delayed_shutdown, daemon=True)
                t.start()
            else:
                self._send_error("invalid_request", 404, f"Unknown API path: {api_path}")
        except KeyError as e:
            self._send_error("invalid_request", 400, f"Missing required field: {e}")
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
        server = self.server  # type: _EditorServer
        server._shutdown_flag = True


# ── HTTP Server ────────────────────────────────────────────────────

class _EditorServer(HTTPServer):
    """HTTP server bound to 127.0.0.1 with session management."""

    allow_reuse_address = True

    def __init__(self, host: str, port: int):
        super().__init__((host, port), _EditorHandler)
        self._sessions: Dict[str, EditorSession] = {}
        self._shutdown_flag = False
        self.host = host
        self.port = self.server_address[1]  # actual bound port

    def add_session(self, session: EditorSession) -> None:
        self._sessions[session.session_token] = session

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
        return f"http://{self.listen_host}:{self.listen_port}/session/{self.session_token}/"

    def start(self) -> str:
        """Create session, bind port, start HTTP server.  Returns the URL."""
        session = create_session(
            self._source_path,
            self._target_path,
            self._backup_dir,
        )
        self._session = session

        self._httpd = _EditorServer(self.listen_host, self._port)
        self._httpd.add_session(session)

        # Refresh actual port if port=0
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
        """Serve with idle-timeout monitoring."""
        assert self._httpd is not None
        idle_check = max(1.0, self._idle_timeout / 10)

        while not self._httpd._shutdown_flag:
            # Check idle timeout
            if self._session and self._session.is_expired(self._idle_timeout):
                print("Session idle timeout reached — shutting down.")
                break

            # Process one request with timeout
            self._httpd.timeout = idle_check
            try:
                self._httpd.handle_request()
            except Exception:
                traceback.print_exc(file=sys.stderr)

        self._shutdown()

    def _shutdown(self):
        """Clean shutdown."""
        if self._session:
            self._session.shutdown()
        if self._httpd:
            try:
                self._httpd.server_close()
            except Exception:
                pass
        # Remove session parent if empty
        if self._session:
            try:
                parent = Path(self._session.session_dir).parent
                if parent.exists() and not any(parent.iterdir()):
                    parent.rmdir()
            except OSError:
                pass

    def _launch_browser(self, url: str):
        """Open the system browser (only when explicitly requested)."""
        import subprocess
        try:
            subprocess.Popen(["xdg-open", url],
                             stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
        except Exception:
            pass

    def stop(self):
        """Signal shutdown and wait for the server thread."""
        if self._httpd:
            self._httpd._shutdown_flag = True
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        self._shutdown()
