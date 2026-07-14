import json
from typing import Any
from .models import ProtocolRequest, ProtocolResponse
from .errors import ProtocolError

MAX_REQUEST_SIZE = 65536
MAX_RESPONSE_SIZE = 65536
PROTOCOL_VERSION = 1

def parse_request(line: str) -> ProtocolRequest:
    try:
        data = json.loads(line)
    except json.JSONDecodeError as e:
        raise ProtocolError(f"Invalid JSON: {e}", "INVALID_JSON")

    if not isinstance(data, dict):
        raise ProtocolError("Request must be a JSON object", "INVALID_FORMAT")

    if "protocol_version" not in data:
        raise ProtocolError("Missing protocol_version", "MISSING_VERSION")
    if data["protocol_version"] != PROTOCOL_VERSION:
        raise ProtocolError(f"Unsupported protocol version: {data['protocol_version']}", "UNSUPPORTED_VERSION")

    if "request_id" not in data or not isinstance(data["request_id"], str):
        raise ProtocolError("Missing or invalid request_id", "INVALID_REQUEST_ID")

    if "command" not in data or not isinstance(data["command"], str):
        raise ProtocolError("Missing or invalid command", "INVALID_COMMAND")

    params = data.get("params", {})
    if not isinstance(params, dict):
        raise ProtocolError("params must be an object", "INVALID_PARAMS")

    # Reject unknown fields
    allowed_keys = {"protocol_version", "request_id", "command", "params"}
    if not set(data.keys()).issubset(allowed_keys):
        raise ProtocolError("Unknown fields in request", "UNKNOWN_FIELDS")

    return ProtocolRequest(
        protocol_version=data["protocol_version"],
        request_id=data["request_id"],
        command=data["command"],
        params=params,
    )

def serialize_response(resp: ProtocolResponse) -> str:
    data = {
        "protocol_version": resp.protocol_version,
        "request_id": resp.request_id,
        "ok": resp.ok,
    }
    if resp.ok:
        data["result"] = resp.result or {}
    else:
        data["error"] = resp.error or {}
    return json.dumps(data)
