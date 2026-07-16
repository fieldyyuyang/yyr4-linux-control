"""HTTP security: headers, origin/host validation, request guards."""

from __future__ import annotations
import json
import re
import urllib.parse
from typing import Optional, Tuple


# Maximum request body size: 256 KiB
MAX_BODY_SIZE = 256 * 1024

ALLOWED_CONTENT_TYPES = {"application/json"}
ALLOWED_METHODS = {"GET", "POST"}

_ALLOWED_ORIGIN_PATTERNS = (
    re.compile(r"^http://127\.0\.0\.1:\d+$"),
    re.compile(r"^http://localhost:\d+$"),
)
_ALLOWED_HOST_PATTERN = re.compile(r"^127\.0\.0\.1:\d+$")

# Allowed static asset names (whitelist)
_ALLOWED_ASSETS = {"editor.css", "editor.js"}

STRICT_CSP = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self'; "
    "img-src 'self'; "
    "connect-src 'self'; "
    "font-src 'none'; "
    "object-src 'none'; "
    "frame-src 'none'; "
    "frame-ancestors 'none'; "
    "base-uri 'none'; "
    "form-action 'self'"
)

SECURITY_HEADERS = {
    "Content-Security-Policy": STRICT_CSP,
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
    return json.dumps(make_error(code, message, path, details), indent=2)


def validate_origin(origin: Optional[str], listen_host: str,
                    listen_port: int) -> Tuple[bool, str]:
    if origin is None:
        return True, ""
    for pat in _ALLOWED_ORIGIN_PATTERNS:
        if pat.match(origin):
            return True, ""
    return False, "forbidden_origin"


def validate_host(host: Optional[str]) -> Tuple[bool, str]:
    if host is None:
        return True, ""
    if _ALLOWED_HOST_PATTERN.match(host):
        return True, ""
    if host == "127.0.0.1" or host == "localhost":
        return True, ""
    return False, "forbidden_host"


def validate_content_type(content_type: Optional[str],
                          method: str) -> Tuple[bool, str]:
    if method != "POST":
        return True, ""
    if content_type is None:
        return False, "invalid_request"
    ct = content_type.split(";")[0].strip().lower()
    if ct not in ALLOWED_CONTENT_TYPES:
        return False, "invalid_json"
    return True, ""


def safe_path(component: str) -> bool:
    """Reject path traversal in a URL path component.

    Covers: ../, ..%2f, %2e%2e/, %2e%2e%2f, double-encoding,
    backslash forms, and absolute paths.
    """
    if not component:
        return False
    # Reject raw traversal
    if ".." in component:
        return False
    # Decode once and check
    try:
        decoded = urllib.parse.unquote(component)
    except Exception:
        return False
    if ".." in decoded:
        return False
    # Decode twice (double encoding)
    try:
        decoded2 = urllib.parse.unquote(decoded)
    except Exception:
        return False
    if ".." in decoded2:
        return False
    # Reject backslash forms
    if "\\" in component or "\\" in decoded:
        return False
    # Reject percent-encoded backslash
    if "%5c" in component.lower() or "%5C" in component:
        return False
    # Reject absolute paths in component
    if decoded.startswith("/"):
        return False
    return True


def is_allowed_asset(name: str) -> bool:
    """Check if *name* is in the static asset whitelist."""
    return name in _ALLOWED_ASSETS
