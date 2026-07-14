import dataclasses
from typing import Dict, Any, Optional

@dataclasses.dataclass
class ProtocolRequest:
    protocol_version: int
    request_id: str
    command: str
    params: Dict[str, Any]

@dataclasses.dataclass
class ProtocolResponse:
    protocol_version: int
    request_id: str
    ok: bool
    result: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, str]] = None
