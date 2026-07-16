"""HTTP security: headers, origin/host validation, request guards."""

from __future__ import annotations
import json
import re
from typing import Optional, Tuple


# Maximum request body size: 256 KiB
MAX_BODY_SIZE = 256 * 1024

# Allowed content types for mutation requests
ALLOWED_CONTENT_TYPES = {"application/json"}

# Allowed methods
ALLOWED_METHODS = {"GET", "POST"}

# Origin must be one of these patterns
_ALLOWED_ORIGIN_PATTERNS = (
    re.compile(r"^http://127\.0\.0\.1:\d+$"),
    re.compile(r"^http://localhost:\d+$"),
)

# Forbid non-loopback Host headers
_ALLOWED_HOST_PATTERN = re.compile(r"^127\.0\.0\.1:\d+$")


SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self'; "
        "img-src 'self'; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    ),
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store, max-age=0",
    "X-Frame-Options": "DENY",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}


# ── Error codes ────────────────────────────────────────────────────

_ERROR_TEMPLATES = {
    "invalid_request": "The request is malformed or missing required parameters.",
    "invalid_json": "The request body is not valid JSON.",
    "invalid_action_spec": "The action specification is invalid.",
    "validation_error": "Configuration validation failed.",
    "draft_sha_mismatch": "The draft has been modified externally.",
    "concurrent_modification": "The target file was modified concurrently.",
    "symlink_rejected": "The target or backup path is a symlink.",
    "session_expired": "The editor session has expired.",
    "unauthorized": "Authentication required.",
    "forbidden_origin": "Request origin is not allowed.",
    "forbidden_host": "Request host is not allowed.",
    "payload_too_large": "Request body exceeds the maximum allowed size.",
    "internal_error": "An internal error occurred.",
}


def make_error(code: str, message: str = "", path: str = "",
               details: dict = None) -> dict:
    """Build a structured error dict."""
    err = {
        "error": {
            "code": code,
            "message": message or _ERROR_TEMPLATES.get(code, "Unknown error"),
        }
    }
    if path:
        err["error"]["path"] = path
    if details:
        err["error"]["details"] = details
    return err


def error_json(code: str, message: str = "", path: str = "",
               details: dict = None) -> str:
    """Return a JSON error response string."""
    return json.dumps(make_error(code, message, path, details), indent=2)


def validate_origin(origin: Optional[str], listen_host: str,
                    listen_port: int) -> Tuple[bool, str]:
    """Check if the Origin header is allowed."""
    if origin is None:
        return True, ""
    for pat in _ALLOWED_ORIGIN_PATTERNS:
        if pat.match(origin):
            return True, ""
    return False, "forbidden_origin"


def validate_host(host: Optional[str]) -> Tuple[bool, str]:
    """Ensure Host header is loopback-only."""
    if host is None:
        return True, ""
    if _ALLOWED_HOST_PATTERN.match(host):
        return True, ""
    # Also accept no-port variants
    if host == "127.0.0.1" or host == "localhost":
        return True, ""
    return False, "forbidden_host"


def validate_content_type(content_type: Optional[str],
                          method: str) -> Tuple[bool, str]:
    """Only POST mutations must have application/json content-type."""
    if method != "POST":
        return True, ""
    if content_type is None:
        return False, "invalid_request"
    # Allow charset suffix
    ct = content_type.split(";")[0].strip().lower()
    if ct not in ALLOWED_CONTENT_TYPES:
        return False, "invalid_json"
    return True, ""


def safe_path(path: str) -> bool:
    """Reject obvious path traversal attempts."""
    if ".." in path or path.startswith("/root/") or path.startswith("~"):
        return False
    # Normalize and check
    cleaned = path.replace("\\", "/")
    if ".." in cleaned:
        return False
    return True
