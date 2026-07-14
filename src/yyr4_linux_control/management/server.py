import asyncio
import logging
import os
from pathlib import Path
from typing import Optional

from yyr4_linux_control.daemon.runtime import DaemonRuntime
from yyr4_linux_control.daemon.models import DaemonState
from yyr4_linux_control.daemon.context import ContextChangeSource
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
        elif req.command == "get-context":
            ctx = await self._runtime.get_runtime_context()
            if not ctx:
                return ProtocolResponse(
                    protocol_version=req.protocol_version,
                    request_id=req.request_id,
                    ok=False,
                    error={"code": "RUNTIME_NOT_AVAILABLE", "message": "Runtime context not available yet"}
                )
            return ProtocolResponse(
                protocol_version=req.protocol_version,
                request_id=req.request_id,
                ok=True,
                result={
                    "selected_profile": str(ctx.selected_profile),
                    "active_layer": ctx.active_layer.value if hasattr(ctx.active_layer, "value") else str(ctx.active_layer),
                    "context_revision": ctx.revision,
                    "last_change_source": ctx.last_change_source.value,
                }
            )
            
        elif req.command in ("set-layer", "next-layer", "previous-layer", "set-profile"):
            state = self._runtime.state
            if state in (DaemonState.STOPPING, DaemonState.STOPPED, DaemonState.FAILED):
                return ProtocolResponse(
                    protocol_version=req.protocol_version,
                    request_id=req.request_id,
                    ok=False,
                    error={"code": "RUNTIME_NOT_AVAILABLE", "message": f"Daemon state is {state.value}"}
                )
                
            prev_ctx = await self._runtime.get_runtime_context()
            if not prev_ctx:
                return ProtocolResponse(
                    protocol_version=req.protocol_version,
                    request_id=req.request_id,
                    ok=False,
                    error={"code": "RUNTIME_NOT_AVAILABLE", "message": "Runtime context not available yet"}
                )
                
            changed = False
            try:
                if req.command == "set-layer":
                    layer_id = req.params.get("layer")
                    if not layer_id or not isinstance(layer_id, str):
                        raise ValueError("Missing or invalid 'layer' parameter")
                    changed = await self._runtime.set_active_layer(layer_id, ContextChangeSource.management_cli)
                    
                elif req.command == "next-layer":
                    changed = await self._runtime.next_active_layer(ContextChangeSource.management_cli)
                    
                elif req.command == "previous-layer":
                    changed = await self._runtime.previous_active_layer(ContextChangeSource.management_cli)
                    
                elif req.command == "set-profile":
                    profile_id = req.params.get("profile")
                    if not profile_id or not isinstance(profile_id, str):
                        raise ValueError("Missing or invalid 'profile' parameter")
                    changed = await self._runtime.set_selected_profile(profile_id, ContextChangeSource.management_cli)
                    
            except ValueError as e:
                return ProtocolResponse(
                    protocol_version=req.protocol_version,
                    request_id=req.request_id,
                    ok=False,
                    error={"code": "INVALID_PARAM", "message": str(e)}
                )
                
            new_ctx = await self._runtime.get_runtime_context()
            return ProtocolResponse(
                protocol_version=req.protocol_version,
                request_id=req.request_id,
                ok=True,
                result={
                    "previous_profile": str(prev_ctx.selected_profile),
                    "previous_layer": prev_ctx.active_layer.value if hasattr(prev_ctx.active_layer, "value") else str(prev_ctx.active_layer),
                    "selected_profile": str(new_ctx.selected_profile),
                    "active_layer": new_ctx.active_layer.value if hasattr(new_ctx.active_layer, "value") else str(new_ctx.active_layer),
                    "context_revision": new_ctx.revision,
                    "changed": changed
                }
            )
            
        else:
            return ProtocolResponse(
                protocol_version=req.protocol_version,
                request_id=req.request_id,
                ok=False,
                error={"code": "UNKNOWN_COMMAND", "message": f"Unknown command: {req.command}"}
            )
