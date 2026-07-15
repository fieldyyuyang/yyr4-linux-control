"""Safe atomic configuration save with backup and concurrency protection."""

from __future__ import annotations
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from yyr4_linux_control.control.config import load_control_config_from_file
from yyr4_linux_control.configurator.serializer import serialize

from .draft import ConfigDraft, DraftValidationResult


class ConcurrentModificationError(OSError):
    """Target file was modified since the draft was created."""


class SaveValidationError(ValueError):
    """Draft failed round-trip validation before save."""


class SymlinkTargetError(ValueError):
    """Target path is a symbolic link — refused."""


class ConfigSaveResult:

    def __init__(self, target_path, backup_path, saved_sha256, verified):
        self.target_path = target_path
        self.backup_path = backup_path
        self.saved_sha256 = saved_sha256
        self.verified = verified


def save_draft(
    draft, target_path, expected_base_sha256, *, backup_dir=None,
):
    """Save a validated draft to *target_path* atomically."""
    target_path = Path(os.path.abspath(str(target_path)))

    if target_path.is_symlink():
        raise SymlinkTargetError(f"target must not be a symlink: {target_path}")

    # Validate draft
    validation = draft.validate()
    if not validation.valid:
        raise SaveValidationError(
            f"Draft validation failed: "
            + "; ".join(e.message for e in validation.errors)
        )
    canonical_text = validation.canonical_text
    assert canonical_text is not None

    # Concurrency check
    current_sha = _compute_sha(target_path)
    if current_sha != expected_base_sha256 and not (
        current_sha is None and expected_base_sha256 is None
    ):
        expected_display = expected_base_sha256[:16] if expected_base_sha256 else "file-does-not-exist"
        got_display = current_sha[:16] if current_sha else "file-does-not-exist"
        raise ConcurrentModificationError(
            f"Target file has been modified. Expected {expected_display}, got {got_display}"
        )

    # Backup
    backup_path: Optional[Path] = None
    if current_sha is not None and backup_dir is not None:
        backup_dir = Path(os.path.abspath(str(backup_dir)))
        backup_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(str(backup_dir), 0o700)
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        sha_prefix = current_sha[:8]
        backup_name = f"{target_path.name}.backup-{ts}-{sha_prefix}"
        bp = backup_dir / backup_name
        # O_EXCL to avoid overwriting existing backups
        fd_bak = os.open(str(bp), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            data = target_path.read_bytes()
            os.write(fd_bak, data)
            os.fsync(fd_bak)
            os.close(fd_bak)
            fd_bak = -1
        except BaseException:
            if fd_bak >= 0:
                os.close(fd_bak)
            raise
        backup_path = bp

    # Atomic write
    parent = target_path.parent
    fd, tmp_name = tempfile.mkstemp(suffix=".toml", prefix=".yyr4-save-", dir=str(parent))
    try:
        data = canonical_text.encode("utf-8")
        os.write(fd, data)
        os.fsync(fd)
        os.close(fd)
        fd = -1
        os.chmod(tmp_name, 0o600)

        if current_sha is None:
            # No-replace install for new files
            try:
                os.link(tmp_name, str(target_path))
            except FileExistsError:
                raise ConcurrentModificationError("Target was created concurrently during save")
            os.unlink(tmp_name)
        else:
            # Final recloning before replace
            current_sha2 = _compute_sha(target_path)
            if current_sha2 != expected_base_sha256:
                os.unlink(tmp_name)
                raise ConcurrentModificationError("Target modified during atomic phase")
            os.replace(tmp_name, str(target_path))

        _fsync_dir(str(parent))

    except BaseException:
        if fd >= 0:
            try:
                os.close(fd)
            except OSError:
                pass
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise

    saved_sha = _compute_sha(target_path)
    verified = saved_sha == validation.serialized_sha256
    return ConfigSaveResult(
        target_path=target_path, backup_path=backup_path,
        saved_sha256=saved_sha or "", verified=verified,
    )


def restore_backup(backup_path, target_path, expected_current_sha256, *, new_backup_dir=None):
    target_path = Path(os.path.abspath(str(target_path)))
    backup_path = Path(os.path.abspath(str(backup_path)))
    if target_path.is_symlink():
        raise SymlinkTargetError(f"target must not be a symlink: {target_path}")
    if backup_path.is_symlink():
        raise SymlinkTargetError(f"backup must not be a symlink: {backup_path}")
    try:
        load_control_config_from_file(backup_path)
    except Exception as e:
        raise ValueError(f"Backup is not a valid config: {e}")
    cur_sha = _compute_sha(target_path)
    if cur_sha != expected_current_sha256:
        raise ConcurrentModificationError("Target modified since restore was initiated")
    if new_backup_dir is not None:
        new_backup_dir = Path(os.path.abspath(str(new_backup_dir)))
        new_backup_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(str(new_backup_dir), 0o700)
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        sha_prefix = cur_sha[:8] if cur_sha else "new"
        pre_bp = new_backup_dir / f"{target_path.name}.pre-restore-{ts}-{sha_prefix}"
        shutil.copy2(str(target_path), str(pre_bp))
        os.chmod(str(pre_bp), 0o600)
    parent = target_path.parent
    fd, tmp_name = tempfile.mkstemp(suffix=".toml", prefix=".yyr4-restore-", dir=str(parent))
    try:
        data = backup_path.read_bytes()
        os.write(fd, data)
        os.fsync(fd)
        os.close(fd)
        fd = -1
        os.chmod(tmp_name, 0o600)
        os.replace(tmp_name, str(target_path))
        _fsync_dir(str(parent))
        return target_path
    except BaseException:
        if fd >= 0:
            try:
                os.close(fd)
            except OSError:
                pass
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def _compute_sha(path):
    import hashlib
    if not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fsync_dir(path):
    try:
        fd = os.open(path, os.O_RDONLY)
        os.fsync(fd)
        os.close(fd)
    except OSError:
        pass
