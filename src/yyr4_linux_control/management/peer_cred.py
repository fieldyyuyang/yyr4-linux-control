import os
import sys
import socket
import struct
import logging

logger = logging.getLogger(__name__)

def check_peer_uid(sock: socket.socket) -> bool:
    """
    Check if the connected peer's UID matches the current process's UID.
    If the platform does not support SO_PEERCRED (e.g. non-Linux),
    explicitly downgrade to relying on file system permissions.
    """
    if sys.platform != "linux":
        logger.warning("SO_PEERCRED not supported on this platform. Downgrading to file system socket permissions.")
        return True

    try:
        SO_PEERCRED = getattr(socket, 'SO_PEERCRED', 17)
        cred = sock.getsockopt(socket.SOL_SOCKET, SO_PEERCRED, struct.calcsize("3i"))
        pid, uid, gid = struct.unpack("3i", cred)
        return uid == os.geteuid()
    except Exception as e:
        logger.warning(f"Failed to read SO_PEERCRED ({e}). Downgrading to file system socket permissions.")
        return True
