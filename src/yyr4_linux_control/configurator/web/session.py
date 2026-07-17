"""M5.4-A Session: Bootstrap/Cookie/CSRF auth, active registry, crash-safe recovery."""

import os, json, secrets, shutil, time, hashlib, signal, tempfile, threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


RECOVERY_BASE_DIR = os.path.join(
    os.environ.get("XDG_STATE_HOME", os.path.expanduser("~/.local/state")),
    "yyr4", "editor-recovery",
)
_SESSIONS_DIR = os.path.join(
    os.environ.get("XDG_RUNTIME_DIR", tempfile.gettempdir()),
    "yyr4", "editor", "sessions",
)

MAX_PROFILES = 32
MAX_LAYERS = 16
MAX_MACRO_STEPS = 100
MAX_COMMAND_ARGV = 64
MAX_TEXT_LENGTH = 4096
MAX_JSON_DEPTH = 12
MAX_URL_LENGTH = 2048
MAX_HEADER_BYTES = 16384
MAX_CONCURRENT_CONNECTIONS = 16
RATE_LIMIT_REQUESTS = 120
RATE_LIMIT_WINDOW = 60
REQUEST_TIMEOUT = 30


@dataclass
class EditorSession:
    session_id: str
    session_token: str          # backward compatible URL token
    bootstrap_token: str = ""   # one-time bootstrap (M5.4-A)
    session_cookie: str = ""    # session cookie value
    csrf_token: str = ""        # X-YYR4-CSRF-Token
    bootstrap_used: bool = False
    _bootstrap_lock: object = field(default_factory=threading.Lock)
    dirty_policy: str = "keep_recovery"
    public_session_id: str = "" # public, non-auth session ID for routes
    pid: int = field(default_factory=os.getpid)
    port: int = 0
    source_path: str = ""
    target_path: str = ""
    backup_dir: Optional[str] = None
    session_dir: str = ""
    draft_path: str = ""
    base_sha256: str = ""
    draft: Optional["ConfigDraft"] = None  # type: ignore
    created_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    _reviewed_mutation: int = -1
    _shutdown: bool = False
    _recovery_id: Optional[str] = None
    _version: str = "1.0.0"

    @property
    def draft_sha256(self) -> str:
        from yyr4_linux_control.configurator.sidecar import read_sidecar
        sc = read_sidecar(Path(self.draft_path))
        return sc["draft_sha256"]

    @property
    def dirty(self) -> bool:
        return self.draft.dirty if self.draft else False

    @property
    def mutation_count(self) -> int:
        return self.draft.mutation_count if self.draft else 0

    @property
    def reviewed(self) -> bool:
        return self._reviewed_mutation == self.mutation_count

    def mark_reviewed(self) -> None:
        self._reviewed_mutation = self.mutation_count

    def consume_bootstrap_token(self, candidate: str) -> bool:
        """Atomically validate and consume bootstrap token."""
        with self._bootstrap_lock:
            if self.bootstrap_used or not self.bootstrap_token:
                return False
            if not secrets.compare_digest(self.bootstrap_token, candidate):
                return False
            self.bootstrap_used = True
            return True

    def touch(self) -> None:
        self.last_activity = time.time()

    def is_expired(self, idle_timeout: float) -> bool:
        return (time.time() - self.last_activity) > idle_timeout

    @property
    def control_socket_path(self) -> str:
        control_dir = os.path.join(
            os.environ.get("XDG_RUNTIME_DIR", tempfile.gettempdir()),
            "yyr4", "editor", "control")
        return os.path.join(control_dir, f"{self.session_id}.sock")

    def create_control_socket(self) -> None:
        """Create AF_UNIX control socket for status/stop commands."""
        import socket
        path = self.control_socket_path
        d = os.path.dirname(path)
        os.makedirs(d, exist_ok=True)
        os.chmod(d, 0o700)
        if os.path.exists(path):
            # Stale socket — remove and verify it was ours
            try:
                s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                s.settimeout(1)
                s.connect(path)
                s.sendall(json.dumps({"operation":"ping"}).encode() + b"\n")
                data = s.recv(1024)
                s.close()
                # If we get a response, socket is alive — someone else's
                if b"pong" in data:
                    raise OSError(f"Control socket {path} already in use (alive)")
            except (ConnectionRefusedError, FileNotFoundError, OSError, json.JSONDecodeError):
                pass
            os.unlink(path)
        self._control_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._control_sock.bind(path)
        self._control_sock.listen(1)
        os.chmod(path, 0o600)
        self.control_socket_path_var = path
        # Start control listener thread
        threading.Thread(target=self._control_loop, daemon=True).start()

    def _control_loop(self) -> None:
        """Accept and handle control socket connections."""
        import socket as sock_mod
        while not self._shutdown:
            try:
                self._control_sock.settimeout(1.0)
                conn, _ = self._control_sock.accept()
                self._handle_control(conn)
            except sock_mod.timeout:
                continue
            except Exception:
                break

    def _handle_control(self, conn) -> None:
        """Process a single control socket request."""
        try:
            data = conn.recv(4096).decode().strip()
            if not data:
                conn.close()
                return
            req = json.loads(data)
            op = req.get("operation", "")
            resp = {"protocol_version": 1, "session_id": self.session_id}
            if op == "ping":
                resp["status"] = "pong"
            elif op == "status":
                resp["status"] = "ok"
                resp["dirty"] = self.dirty
                resp["mutation_count"] = self.mutation_count
                resp["running"] = True
            elif op == "stop":
                policy = req.get("dirty_policy", "keep_recovery")
                resp["status"] = "ok"
                resp["action"] = "stopping"
                conn.sendall((json.dumps(resp) + "\n").encode())
                conn.close()
                self.shutdown(policy=policy)
                return
            else:
                resp = {"status": "error", "code": "unknown_operation"}
            conn.sendall((json.dumps(resp) + "\n").encode())
            conn.close()
        except Exception:
            pass
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def cleanup_control_socket(self) -> None:
        """Remove control socket."""
        try:
            if hasattr(self, '_control_sock'):
                self._control_sock.close()
            p = self.control_socket_path
            if os.path.exists(p):
                os.unlink(p)
        except Exception:
            pass

    def write_registry(self) -> None:
        d = Path(_SESSIONS_DIR)
        d.mkdir(parents=True, exist_ok=True)
        os.chmod(str(d), 0o700)
        # Get process start time from /proc
        pst = ""
        try:
            pst = Path(f"/proc/{self.pid}/stat").read_text().split()[21]
        except Exception:
            pass
        r = {
            "registry_version": 1, "session_id": self.session_id,
            "public_session_id": self.public_session_id,
            "pid": self.pid, "uid": os.getuid(),
            "process_start_time": pst,
            "process_identity": f"yyr4-editor-{self.session_id[:8]}",
            "port": self.port,
            "control_socket": getattr(self, 'control_socket_path', None),
            "source": os.path.basename(self.source_path),
            "target": os.path.basename(self.target_path),
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.created_at)),
            "last_activity": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.last_activity)),
            "dirty": self.dirty, "mutation_count": self.mutation_count,
            "recovery_id": self._recovery_id,
        }
        p = d / f"{self.session_id}.json"
        p.write_text(json.dumps(r, indent=2))
        os.chmod(str(p), 0o600)

    def _remove_registry(self) -> None:
        p = Path(_SESSIONS_DIR) / f"{self.session_id}.json"
        try: p.unlink(missing_ok=True)
        except OSError: pass

    def write_recovery(self) -> None:
        """Crash-safe: persist after every mutation."""
        if not self.draft or not self.dirty:
            return
        rid = self._recovery_id or secrets.token_hex(12)
        self._recovery_id = rid
        rdir = Path(RECOVERY_BASE_DIR) / rid
        rdir.mkdir(parents=True, exist_ok=True)
        os.chmod(str(rdir), 0o700)
        dp = Path(self.draft_path)
        sp = Path(str(self.draft_path) + ".yyr4-draft.json")
        if dp.is_file():
            shutil.copy2(str(dp), str(rdir / "draft.toml"))
            os.chmod(str(rdir / "draft.toml"), 0o600)
        if sp.is_file():
            shutil.copy2(str(sp), str(rdir / "draft.toml.yyr4-draft.json"))
            os.chmod(str(rdir / "draft.toml.yyr4-draft.json"), 0o600)
        v = self.draft.validate()
        mf = {
            "recovery_version": 1, "recovery_id": rid,
            "source": os.path.basename(self.source_path),
            "target": os.path.basename(self.target_path),
            "base_sha256": self.base_sha256,
            "draft_sha256": self.draft_sha256,
            "mutation_count": self.mutation_count,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.created_at)),
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.last_activity)),
            "valid": v.valid, "errors": [e.message for e in v.errors],
            "dirty": self.dirty, "reviewed_mutation": self._reviewed_mutation,
            "application_version": self._version,
        }
        p = rdir / "manifest.json"; p.write_text(json.dumps(mf, indent=2)); os.chmod(str(p), 0o600)

    def discard_recovery(self) -> None:
        if self._recovery_id:
            shutil.rmtree(str(Path(RECOVERY_BASE_DIR) / self._recovery_id), ignore_errors=True)
            self._recovery_id = None

    def shutdown(self, policy: str = "keep_recovery") -> None:
        if self._shutdown: return
        self._shutdown = True
        if policy == "keep_recovery" and self.dirty:
            self.write_recovery()
        elif policy == "discard":
            self.discard_recovery()
        self.cleanup_control_socket()
        self._remove_registry()
        try: shutil.rmtree(self.session_dir, ignore_errors=True)
        except OSError: pass

    def shutdown_clean(self) -> None:
        self.shutdown(policy="discard")

    def refresh_base(self) -> None:
        from yyr4_linux_control.control.config import load_control_config_from_file
        from yyr4_linux_control.configurator.serializer import serialize
        from yyr4_linux_control.configurator.sidecar import write_sidecar
        from yyr4_linux_control.configurator.draft import ConfigDraft
        new_config = load_control_config_from_file(Path(self.target_path))
        new_sha = hashlib.sha256(serialize(new_config).encode()).hexdigest()
        self.base_sha256 = new_sha
        self.draft = ConfigDraft(Path(self.target_path))
        draft_sha = hashlib.sha256(serialize(self.draft.working_config).encode()).hexdigest()
        write_sidecar(Path(self.draft_path), self.target_path, new_sha, draft_sha, 0)
        self._reviewed_mutation = -1
        self.discard_recovery()


def create_session(source_path: str, target_path: str,
                   backup_dir: Optional[str] = None) -> EditorSession:
    from yyr4_linux_control.configurator.draft import ConfigDraft
    from yyr4_linux_control.configurator.serializer import serialize
    from yyr4_linux_control.configurator.sidecar import write_sidecar

    source = Path(source_path).resolve()
    if not source.is_file():
        raise FileNotFoundError(f"Source config not found: {source_path}")
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR")
    if runtime_dir:
        session_parent = Path(runtime_dir) / "yyr4" / "editor"
    else:
        session_parent = Path(tempfile.mkdtemp(prefix="yyr4-editor-"))
    session_parent.mkdir(parents=True, exist_ok=True)
    os.chmod(str(session_parent), 0o700)
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
    bootstrap_token = secrets.token_urlsafe(32)
    session_cookie = secrets.token_urlsafe(32)
    csrf_token = secrets.token_hex(24)
    public_session_id = secrets.token_hex(8)

    draft = ConfigDraft(source)
    base_sha = draft.base_sha256
    draft_path = session_dir / "draft.toml"
    text = serialize(draft.working_config)
    draft_path.write_text(text, encoding="utf-8")
    os.chmod(str(draft_path), 0o600)
    draft_sha = hashlib.sha256(text.encode()).hexdigest()
    write_sidecar(draft_path, str(source), base_sha, draft_sha, 0)

    s = EditorSession(
        session_id=session_id, session_token=session_token,
        bootstrap_token=bootstrap_token, session_cookie=session_cookie,
        csrf_token=csrf_token,
        public_session_id=public_session_id,
        source_path=str(source),
        target_path=str(Path(target_path).resolve()),
        backup_dir=str(Path(backup_dir).resolve()) if backup_dir else None,
        session_dir=str(session_dir), draft_path=str(draft_path),
        base_sha256=base_sha, draft=draft,
    )
    s.write_registry()
    return s


def list_recoveries() -> list:
    base = Path(RECOVERY_BASE_DIR)
    if not base.is_dir(): return []
    results = []
    for entry in sorted(base.iterdir()):
        mf = entry / "manifest.json"
        if mf.is_file():
            try: results.append(json.loads(mf.read_text()))
            except: pass
    return results

def get_recovery(rid: str) -> Optional[dict]:
    mf = Path(RECOVERY_BASE_DIR) / rid / "manifest.json"
    if not mf.is_file(): return None
    return json.loads(mf.read_text())

def discard_recovery(rid: str) -> bool:
    rdir = Path(RECOVERY_BASE_DIR) / rid
    if not rdir.is_dir(): return False
    shutil.rmtree(str(rdir), ignore_errors=True)
    return True

def list_sessions() -> list:
    d = Path(_SESSIONS_DIR)
    if not d.is_dir(): return []
    results = []
    for f in sorted(d.iterdir()):
        if f.suffix == ".json":
            try:
                r = json.loads(f.read_text())
                r["stale"] = _is_stale(r)
                results.append(r)
            except: pass
    return results

def _is_stale(r: dict) -> bool:
    pid = r.get("pid", 0)
    if pid == 0: return True
    try:
        os.kill(pid, 0)
    except OSError:
        return True
    try:
        proc_uid = os.stat(f"/proc/{pid}").st_uid
        if proc_uid != r.get("uid", os.getuid()):
            return True
    except Exception:
        return True
    # Verify process start time (PID reuse protection)
    try:
        current_pst = Path(f"/proc/{pid}/stat").read_text().split()[21]
        if r.get("process_start_time") and current_pst != r["process_start_time"]:
            return True
    except Exception:
        return True
    return False

def resume_session(rid: str, target_path: str,
                   backup_dir: Optional[str] = None) -> EditorSession:
    rdir = Path(RECOVERY_BASE_DIR) / rid
    mf = rdir / "manifest.json"
    if not mf.is_file():
        raise FileNotFoundError(f"Recovery {rid} not found")
    manifest = json.loads(mf.read_text())
    if manifest.get("recovery_version") != 1:
        raise ValueError(f"Unknown recovery version: {manifest.get('recovery_version')}")
    s = create_session(
        manifest.get("source", ""), target_path or manifest.get("target", ""), backup_dir,
    )
    return s
