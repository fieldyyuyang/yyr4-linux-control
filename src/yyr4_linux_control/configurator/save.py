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
    """Result of a save operation."""

    def __init__(
        self,
        target_path: Path,
        backup_path: Optional[Path],
        saved_sha256: str,
        verified: bool,
    ):
        self.target_path = target_path
        self.backup_path = backup_path
        self.saved_sha256 = saved_sha256
        self.verified = verified


def save_draft(
    draft: ConfigDraft,
    target_path: Path,
    expected_base_sha256: str,
    *,
    backup_dir: Optional[Path] = None,
) -> ConfigSaveResult:
    """Save a validated draft to *target_path* atomically.

    Args:
        draft: A ConfigDraft whose working_config is ready to save.
        target_path: Where to write the canonical TOML.
        expected_base_sha256: SHA-256 of the file that was loaded to
            create the draft (or the empty-string constant if the file
            should not exist yet).
        backup_dir: Directory for backups; defaults to target's parent.

    Raises:
        SymlinkTargetError: *target_path* is a symbolic link.
        ConcurrentModificationError: Current target SHA doesn't match
            *expected_base_sha256*.
        SaveValidationError: Round-trip validation of the draft failed.
        Various OSError for I/O failures.
    """
    target_path = Path(os.path.abspath(str(target_path)))

    if target_path.is_symlink():
        raise SymlinkTargetError(
            f"Target path must not be a symbolic link: {target_path}"
        )

    # ── Validate draft ──
    validation = draft.validate()
    if not validation.valid:
        raise SaveValidationError(
            f"Draft validation failed: "
            + "; ".join(e.message for e in validation.errors)
        )
    canonical_text = validation.canonical_text
    assert canonical_text is not None

    # ── Concurrency check ──
    current_sha = _compute_sha(target_path)
    if current_sha != expected_base_sha256 and not (
        current_sha is None and expected_base_sha256 is None
    ):
        expected_display = expected_base_sha256[:16] if expected_base_sha256 else "file-does-not-exist"
        got_display = current_sha[:16] if current_sha else "file-does-not-exist"
        raise ConcurrentModificationError(
            f"Target file has been modified since draft was created. "
            f"Expected SHA {expected_display}, got {got_display}"
        )

    # ── Backup ──
    backup_path: Optional[Path] = None
    if target_path.is_file() and backup_dir is not None:
        backup_dir = Path(os.path.abspath(str(backup_dir)))
        backup_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(str(backup_dir), 0o700)
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        sha_prefix = current_sha[:8] if current_sha else "new"
        backup_name = f"{target_path.name}.backup-{ts}-{sha_prefix}"
        bp = backup_dir / backup_name
        shutil.copy2(str(target_path), str(bp))
        os.chmod(str(bp), 0o600)
        backup_path = bp

    # ── Atomic write ──
    parent = target_path.parent
    fd, tmp_name = tempfile.mkstemp(
        suffix=".toml",
        prefix=".yyr4-save-",
        dir=str(parent),
    )
    try:
        data = canonical_text.encode("utf-8")
        os.write(fd, data)
        os.fsync(fd)
        os.close(fd)
        fd = -1

        os.chmod(tmp_name, 0o600)
        os.replace(tmp_name, str(target_path))
        # fsync parent directory
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

    # ── Verify ──
    saved_sha = _compute_sha(target_path)
    verified = saved_sha == validation.serialized_sha256
    return ConfigSaveResult(
        target_path=target_path,
        backup_path=backup_path,
        saved_sha256=saved_sha or "",
        verified=verified,
    )


def restore_backup(
    backup_path: Path,
    target_path: Path,
    expected_current_sha256: str,
    *,
    new_backup_dir: Optional[Path] = None,
) -> Path:
    """Restore *target_path* from *backup_path*.

    Creates a fresh backup of the current *target_path* before restoring.
    Both paths must not be symbolic links.
    """
    target_path = Path(os.path.abspath(str(target_path)))
    backup_path = Path(os.path.abspath(str(backup_path)))

    if target_path.is_symlink():
        raise SymlinkTargetError(f"Target path must not be a symlink: {target_path}")
    if backup_path.is_symlink():
        raise SymlinkTargetError(f"Backup path must not be a symlink: {backup_path}")

    # Verify backup is valid config
    try:
        load_control_config_from_file(backup_path)
    except Exception as e:
        raise ValueError(f"Backup file is not a valid configuration: {e}")

    # Concurrency check
    cur_sha = _compute_sha(target_path)
    if cur_sha != expected_current_sha256:
        raise ConcurrentModificationError(
            f"Target modified since restore was initiated"
        )

    # Backup current before restore
    if new_backup_dir is not None:
        new_backup_dir = Path(os.path.abspath(str(new_backup_dir)))
        new_backup_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(str(new_backup_dir), 0o700)
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        sha_prefix = cur_sha[:8] if cur_sha else "new"
        pre_restore_bp = new_backup_dir / f"{target_path.name}.pre-restore-{ts}-{sha_prefix}"
        shutil.copy2(str(target_path), str(pre_restore_bp))
        os.chmod(str(pre_restore_bp), 0o600)

    # Atomic restore
    parent = target_path.parent
    fd, tmp_name = tempfile.mkstemp(
        suffix=".toml",
        prefix=".yyr4-restore-",
        dir=str(parent),
    )
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


def _compute_sha(path: Path) -> Optional[str]:
    import hashlib
    if not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fsync_dir(path: str) -> None:
    try:
        fd = os.open(path, os.O_RDONLY)
        os.fsync(fd)
        os.close(fd)
    except OSError:
        pass
