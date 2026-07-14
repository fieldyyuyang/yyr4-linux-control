import asyncio
import logging
import os
from pathlib import Path
from typing import Optional

from yyr4_linux_control.daemon.runtime import DaemonRuntime
from .protocol import parse_request, serialize_response
from .models import ProtocolRequest, ProtocolResponse
from .errors import ProtocolError
from .socket_path import setup_server_socket
from .peer_cred import check_peer_uid

logger = logging.getLogger(__name__)

class ManagementServer:
    def __init__(self, runtime: DaemonRuntime, socket_path: Path):
        self._runtime = runtime
        self._socket_path = socket_path
        self._server: Optional[asyncio.Server] = None
        self._bound_socket = False

    async def start(self) -> None:
        await setup_server_socket(self._socket_path)
        self._server = await asyncio.start_unix_server(
            self._handle_client,
            path=str(self._socket_path)
        )
        os.chmod(self._socket_path, 0o600)
        self._bound_socket = True
        logger.info(f"Management server listening on {self._socket_path}")

    async def stop(self) -> None:
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        if self._bound_socket and self._socket_path.exists():
            self._socket_path.unlink()
            self._bound_socket = False
            logger.info("Management server stopped and socket removed")

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            sock = writer.get_extra_info('socket')
            if sock and not check_peer_uid(sock):
                logger.warning("Rejected client: peer UID mismatch")
                return

            try:
                line = await asyncio.wait_for(reader.readline(), timeout=5.0)
            except asyncio.TimeoutError:
                return

            if not line:
                return

            line_str = line.decode('utf-8', errors='replace')
            try:
                req = parse_request(line_str)
            except ProtocolError as e:
                resp = ProtocolResponse(
                    protocol_version=1,
                    request_id="",
                    ok=False,
                    error={"code": e.code, "message": str(e)}
                )
                writer.write(serialize_response(resp).encode('utf-8') + b'\n')
                await writer.drain()
                return

            resp = await self._process_request(req)
            writer.write(serialize_response(resp).encode('utf-8') + b'\n')
            await asyncio.wait_for(writer.drain(), timeout=5.0)

        except Exception as e:
            logger.error(f"Error handling management client: {e}")
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

    async def _process_request(self, req: ProtocolRequest) -> ProtocolResponse:
        if req.command == "ping":
            return ProtocolResponse(
                protocol_version=req.protocol_version,
                request_id=req.request_id,
                ok=True,
                result={"pong": True}
            )
        elif req.command == "status":
            snap = self._runtime.snapshot()
            return ProtocolResponse(
                protocol_version=req.protocol_version,
                request_id=req.request_id,
                ok=True,
                result=snap.to_dict()
            )
        elif req.command == "reload":
            res = await self._runtime.request_reload_and_wait()
            if res.get("success"):
                return ProtocolResponse(
                    protocol_version=req.protocol_version,
                    request_id=req.request_id,
                    ok=True,
                    result={"config_revision": res["config_revision"], "reload_successes": res.get("reload_successes", 0)}
                )
            else:
                return ProtocolResponse(
                    protocol_version=req.protocol_version,
                    request_id=req.request_id,
                    ok=False,
                    error={"code": res.get("error_code", "RELOAD_FAILED"), "message": "Reload failed or rejected", "config_revision": str(res.get("config_revision", 0))}
                )
        else:
            return ProtocolResponse(
                protocol_version=req.protocol_version,
                request_id=req.request_id,
                ok=False,
                error={"code": "UNKNOWN_COMMAND", "message": f"Unknown command: {req.command}"}
            )
