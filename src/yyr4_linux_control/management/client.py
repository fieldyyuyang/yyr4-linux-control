import asyncio
import json
import uuid
from pathlib import Path
from .models import ProtocolRequest, ProtocolResponse
from .errors import ProtocolError

class ManagementClient:
    def __init__(self, socket_path: Path):
        self._socket_path = socket_path

    async def send_request(self, command: str, params: dict = None) -> ProtocolResponse:
        if not self._socket_path.exists():
            raise ProtocolError("Daemon socket not found", "DAEMON_NOT_RUNNING")

        req = ProtocolRequest(
            protocol_version=1,
            request_id=str(uuid.uuid4()),
            command=command,
            params=params or {}
        )
        data = json.dumps({
            "protocol_version": req.protocol_version,
            "request_id": req.request_id,
            "command": req.command,
            "params": req.params
        })

        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_unix_connection(str(self._socket_path)),
                timeout=5.0
            )
        except ConnectionRefusedError:
            raise ProtocolError("Daemon socket connection refused", "DAEMON_NOT_RUNNING")
        except PermissionError:
            raise ProtocolError("Permission denied connecting to socket", "PERMISSION_DENIED")
        except asyncio.TimeoutError:
            raise ProtocolError("Connection timeout", "TIMEOUT")

        try:
            writer.write(data.encode('utf-8') + b'\n')
            await asyncio.wait_for(writer.drain(), timeout=5.0)

            line = await asyncio.wait_for(reader.readline(), timeout=5.0)
            if not line:
                raise ProtocolError("Empty response from daemon", "EMPTY_RESPONSE")
                
            line_str = line.decode('utf-8', errors='replace')
            try:
                resp_data = json.loads(line_str)
            except json.JSONDecodeError:
                raise ProtocolError("Malformed JSON response from daemon", "MALFORMED_RESPONSE")

            resp = ProtocolResponse(
                protocol_version=resp_data.get("protocol_version", 1),
                request_id=resp_data.get("request_id", ""),
                ok=resp_data.get("ok", False),
                result=resp_data.get("result"),
                error=resp_data.get("error")
            )
            
            if resp.request_id != req.request_id:
                raise ProtocolError("Request ID mismatch", "ID_MISMATCH")
                
            return resp

        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass
