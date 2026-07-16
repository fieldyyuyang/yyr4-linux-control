"""Draft sidecar metadata file management."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

_METADATA_VERSION = 1


def read_sidecar(draft_path: Path) -> dict:
    sp = _sidecar_path(draft_path)
    if sp.is_symlink():
        raise OSError(f"Sidecar is a symlink, rejected for safety: {sp}")
    if not sp.is_file():
        raise FileNotFoundError(f"Sidecar not found: {sp}")
    return json.loads(sp.read_text("utf-8"))


def write_sidecar(draft_path: Path, base_source_path: str, base_sha256: str,
                  draft_sha256: str, mutation_count: int) -> Path:
    sp = _sidecar_path(draft_path)
    now = datetime.now(timezone.utc).isoformat()
    data = {
        "metadata_version": _METADATA_VERSION,
        "base_source_path": base_source_path,
        "base_sha256": base_sha256,
        "draft_sha256": draft_sha256,
        "mutation_count": mutation_count,
        "created_at_utc": now,
        "updated_at_utc": now,
    }
    text = json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False)
    # Atomic write
    fd, tmp = _mkstemp_parent(sp)
    try:
        os.write(fd, text.encode("utf-8"))
        os.fsync(fd)
        os.close(fd)
        fd = -1
        os.chmod(tmp, 0o600)
        os.replace(tmp, str(sp))
    except BaseException:
        if fd >= 0: os.close(fd)
        try: os.unlink(tmp)
        except OSError: pass
        raise
    return sp


def update_sidecar_after_mutation(draft_path: Path, draft_sha256: str,
                                  mutation_count: int) -> Path:
    """Update draft_sha256 and mutation_count without rewriting other fields."""
    existing = read_sidecar(draft_path)
    existing["draft_sha256"] = draft_sha256
    existing["mutation_count"] = mutation_count
    existing["updated_at_utc"] = datetime.now(timezone.utc).isoformat()
    text = json.dumps(existing, indent=2, sort_keys=True, ensure_ascii=False)
    sp = _sidecar_path(draft_path)
    fd, tmp = _mkstemp_parent(sp)
    try:
        os.write(fd, text.encode("utf-8"))
        os.fsync(fd)
        os.close(fd)
        fd = -1
        os.chmod(tmp, 0o600)
        os.replace(tmp, str(sp))
    except BaseException:
        if fd >= 0: os.close(fd)
        try: os.unlink(tmp)
        except OSError: pass
        raise
    return sp


def _sidecar_path(draft_path: Path) -> Path:
    return Path(str(draft_path) + ".yyr4-draft.json")


def _mkstemp_parent(path: Path):
    import tempfile
    return tempfile.mkstemp(prefix=".yyr4-sidecar-", dir=str(path.parent))
