import os
import stat
import socket
import asyncio
import logging
from pathlib import Path
from .errors import SocketError

logger = logging.getLogger(__name__)

def get_default_socket_path() -> Path:
    xdg = os.environ.get("XDG_RUNTIME_DIR")
    if not xdg:
        raise SocketError("XDG_RUNTIME_DIR is not set. Cannot use default socket path.")
    return Path(xdg) / "yyr4" / "yyr4d.sock"

async def setup_server_socket(path: Path) -> None:
    """Ensure directory exists and handle existing socket safely."""
    parent = path.parent
    if not parent.exists():
        parent.mkdir(parents=True, exist_ok=True)
        os.chmod(parent, 0o700)

    if path.exists():
        mode = path.stat().st_mode
        if not stat.S_ISSOCK(mode):
            raise SocketError(f"Path {path} exists and is not a socket.")
            
        # It's a socket, try connecting
        try:
            reader, writer = await asyncio.open_unix_connection(path)
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass
            raise SocketError(f"Another daemon is already listening on {path}")
        except ConnectionRefusedError:
            # Dead socket
            pass
        except Exception as e:
            raise SocketError(f"Failed to probe existing socket at {path}: {e}")

        # Dead socket, check ownership
        if path.stat().st_uid != os.geteuid():
            raise SocketError(f"Dead socket {path} is not owned by current user. Cannot remove.")
            
        logger.info(f"Removing dead socket at {path}")
        path.unlink()
