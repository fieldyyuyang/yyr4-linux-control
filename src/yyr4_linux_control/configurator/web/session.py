"""Editor session: Draft lifecycle, sidecar, token, and cleanup."""

from __future__ import annotations
import os
import secrets
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from yyr4_linux_control.configurator.draft import ConfigDraft
from yyr4_linux_control.configurator.sidecar import write_sidecar, read_sidecar


@dataclass
class EditorSession:
    """Single-use editor session with token-gated access."""

    session_id: str
    session_token: str
    source_path: str
    target_path: str
    backup_dir: Optional[str]
    session_dir: str
    draft_path: str
    base_sha256: str
    draft: ConfigDraft
    created_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    _reviewed_mutation: int = -1
    _shutdown: bool = False

    @property
    def draft_sha256(self) -> str:
        sc = read_sidecar(Path(self.draft_path))
        return sc["draft_sha256"]

    @property
    def dirty(self) -> bool:
        return self.draft.dirty

    @property
    def mutation_count(self) -> int:
        return self.draft.mutation_count

    @property
    def reviewed(self) -> bool:
        return self._reviewed_mutation == self.draft.mutation_count

    def mark_reviewed(self) -> None:
        self._reviewed_mutation = self.draft.mutation_count

    def touch(self) -> None:
        self.last_activity = time.time()

    def is_expired(self, idle_timeout: float) -> bool:
        return (time.time() - self.last_activity) > idle_timeout

    def shutdown(self) -> None:
        """Idempotent cleanup of session directory."""
        if self._shutdown:
            return
        self._shutdown = True
        try:
            shutil.rmtree(self.session_dir, ignore_errors=True)
        except OSError:
            pass

    def refresh_base(self) -> None:
        """After a successful save, update the base so subsequent diffs are correct."""
        from yyr4_linux_control.control.config import load_control_config_from_file
        from yyr4_linux_control.configurator.serializer import serialize
        import hashlib

        new_config = load_control_config_from_file(Path(self.target_path))
        new_sha = hashlib.sha256(serialize(new_config).encode()).hexdigest()
        self.base_sha256 = new_sha
        self.draft = ConfigDraft(Path(self.target_path))
        # Rewrite sidecar to reflect new base
        draft_sha = hashlib.sha256(
            serialize(self.draft.working_config).encode()
        ).hexdigest()
        write_sidecar(Path(self.draft_path), self.target_path, new_sha, draft_sha, 0)
        self._reviewed_mutation = -1


def create_session(
    source_path: str,
    target_path: str,
    backup_dir: Optional[str] = None,
) -> EditorSession:
    """Create a new editor session with isolated working directory."""

    # Validate source is a schema v2 config
    source = Path(source_path).resolve()
    if not source.is_file():
        raise FileNotFoundError(f"Source config not found: {source_path}")

    # Create session directory
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR")
    if runtime_dir:
        session_parent = Path(runtime_dir) / "yyr4" / "editor"
    else:
        import tempfile
        session_parent = Path(tempfile.mkdtemp(prefix="yyr4-editor-"))

    session_parent.mkdir(parents=True, exist_ok=True)
    os.chmod(str(session_parent), 0o700)

    # Reject if session_parent is a symlink
    if session_parent.is_symlink():
        raise OSError(f"Session directory is a symlink: {session_parent}")

    session_id = secrets.token_hex(16)
    session_dir = session_parent / session_id
    session_dir.mkdir(exist_ok=False)
    os.chmod(str(session_dir), 0o700)
    if session_dir.is_symlink():
        shutil.rmtree(str(session_dir), ignore_errors=True)
        raise OSError(f"Session directory resolved to a symlink: {session_dir}")

    session_token = secrets.token_urlsafe(32)

    # Create draft
    draft = ConfigDraft(source)
    base_sha = draft.base_sha256

    # Draft file inside session directory
    draft_path = session_dir / "draft.toml"

    # Serialize and write draft
    from yyr4_linux_control.configurator.serializer import serialize
    import hashlib

    text = serialize(draft.working_config)
    draft_path.write_text(text, encoding="utf-8")
    os.chmod(str(draft_path), 0o600)

    draft_sha = hashlib.sha256(text.encode()).hexdigest()
    write_sidecar(draft_path, str(source), base_sha, draft_sha, 0)

    return EditorSession(
        session_id=session_id,
        session_token=session_token,
        source_path=str(source),
        target_path=str(Path(target_path).resolve()),
        backup_dir=str(Path(backup_dir).resolve()) if backup_dir else None,
        session_dir=str(session_dir),
        draft_path=str(draft_path),
        base_sha256=base_sha,
        draft=draft,
    )
