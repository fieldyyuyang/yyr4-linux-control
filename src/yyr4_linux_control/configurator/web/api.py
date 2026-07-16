"""REST API for the local graphical editor.

Every mutation endpoint: validates token, calls M5.2 domain API,
updates session draft and sidecar, returns latest state summary.
"""

from __future__ import annotations
import json
import os
import time
from pathlib import Path
from typing import Optional

from yyr4_linux_control.configurator.draft import ConfigDraft
from yyr4_linux_control.configurator.serializer import serialize
from yyr4_linux_control.configurator.action_spec import parse_spec, action_to_spec
from yyr4_linux_control.configurator.diff import diff_configs, unified_diff
from yyr4_linux_control.configurator.save import (
    save_draft, ConcurrentModificationError,
    SymlinkTargetError, SaveValidationError,
)
from yyr4_linux_control.configurator.sidecar import (
    write_sidecar, read_sidecar, update_sidecar_after_mutation,
)
from yyr4_linux_control.control.models import OfficialControl
from yyr4_linux_control.control.actions import Action

from .session import EditorSession


def _update_draft(session: EditorSession) -> None:
    """Atomically write draft and update sidecar after mutation."""
    import hashlib
    dp = Path(session.draft_path)
    text = serialize(session.draft.working_config)
    _atomic_write(text, dp)
    sha = hashlib.sha256(text.encode()).hexdigest()
    update_sidecar_after_mutation(dp, sha, session.draft.mutation_count)
    # M5.4-A: crash-safe recovery after every mutation
    session.write_recovery()
    session.write_registry()


def _atomic_write(text: str, path: Path) -> None:
    """Write *text* atomically to *path*."""
    import tempfile
    fd, tmp = tempfile.mkstemp(
        prefix=".yyr4-draft-write-", dir=str(path.parent),
    )
    try:
        os.write(fd, text.encode("utf-8"))
        os.fsync(fd)
        os.close(fd)
        fd = -1
        os.chmod(tmp, 0o600)
        os.replace(tmp, str(path))
    except BaseException:
        if fd >= 0:
            os.close(fd)
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _fsync_dir(path: str) -> None:
    try:
        fd = os.open(path, os.O_RDONLY)
        os.fsync(fd)
        os.close(fd)
    except OSError:
        pass


# ── State ──────────────────────────────────────────────────────────

def build_state(session: EditorSession) -> dict:
    """Build the full session state for the UI."""
    draft = session.draft
    wc = draft.working_config
    sc = read_sidecar(Path(session.draft_path))

    profiles = []
    for pid in sorted(wc.profiles.keys(), key=lambda p: p.value):
        prof = wc.profiles[pid]
        layers = []
        for lid in sorted(prof.layers.keys(), key=lambda l: l.value):
            layer = prof.layers[lid]
            controls = {}
            for oc in OfficialControl:
                action = layer.controls.get(oc)
                if action is not None:
                    controls[oc.value] = action_to_spec(action)
                else:
                    controls[oc.value] = None
            layers.append({
                "layer_id": lid.value,
                "is_initial": lid == wc.initial_layer,
                "controls": controls,
            })
        profiles.append({
            "profile_id": pid.value,
            "is_default": pid == wc.default_profile,
            "layers": layers,
        })

    validation = draft.validate()

    return {
        "session": {
            "source": session.source_path,
            "target": session.target_path,
            "idle_timeout": 0,  # filled by server
        },
        "config": {
            "schema_version": wc.schema_version,
            "default_profile": wc.default_profile.value,
            "initial_layer": wc.initial_layer.value,
            "base_sha256": sc.get("base_sha256", draft.base_sha256),
            "draft_sha256": sc.get("draft_sha256", ""),
            "dirty": draft.dirty,
            "mutation_count": draft.mutation_count,
            "profiles": profiles,
        },
        "validation": {
            "valid": validation.valid,
            "errors": [{"level": e.level, "message": e.message, "path": e.path}
                       for e in validation.errors],
            "warnings": [{"level": w.level, "message": w.message, "path": w.path}
                        for w in validation.warnings],
        },
    }


# ── Control mutations ──────────────────────────────────────────────

def handle_set_action(session: EditorSession, body: dict) -> dict:
    profile = _require(body, "profile")
    layer = _require(body, "layer")
    control = _require(body, "control")
    spec = _require(body, "action_spec")

    try:
        action = parse_spec(spec)
    except ValueError as e:
        return _err("invalid_action_spec", str(e))

    result = session.draft.set_action(profile, layer, control, action)
    if not result.success:
        return _err("validation_error", result.diagnostics[0].message,
                     result.diagnostics[0].path)

    _update_draft(session)
    session.touch()
    return _ok(build_state(session))


def handle_clear_action(session: EditorSession, body: dict) -> dict:
    profile = _require(body, "profile")
    layer = _require(body, "layer")
    control = _require(body, "control")

    result = session.draft.clear_action(profile, layer, control)
    if not result.success:
        return _err("validation_error", result.diagnostics[0].message)

    _update_draft(session)
    session.touch()
    return _ok(build_state(session))


# ── Profile mutations ──────────────────────────────────────────────

def handle_add_profile(session: EditorSession, body: dict) -> dict:
    pid = _require(body, "profile_id")
    result = session.draft.add_profile(pid)
    if not result.success:
        return _err("validation_error", result.diagnostics[0].message)
    _update_draft(session)
    session.touch()
    return _ok(build_state(session))


def handle_rename_profile(session: EditorSession, body: dict) -> dict:
    old_id = _require(body, "old_profile_id")
    new_id = _require(body, "new_profile_id")
    result = session.draft.rename_profile(old_id, new_id)
    if not result.success:
        return _err("validation_error", result.diagnostics[0].message)
    _update_draft(session)
    session.touch()
    return _ok(build_state(session))


def handle_remove_profile(session: EditorSession, body: dict) -> dict:
    pid = _require(body, "profile_id")
    result = session.draft.remove_profile(pid)
    if not result.success:
        return _err("validation_error", result.diagnostics[0].message)
    _update_draft(session)
    session.touch()
    return _ok(build_state(session))


def handle_set_default_profile(session: EditorSession, body: dict) -> dict:
    pid = _require(body, "profile_id")
    result = session.draft.set_default_profile(pid)
    if not result.success:
        return _err("validation_error", result.diagnostics[0].message)
    _update_draft(session)
    session.touch()
    return _ok(build_state(session))


# ── Layer mutations ────────────────────────────────────────────────

def handle_add_layer(session: EditorSession, body: dict) -> dict:
    profile = _require(body, "profile")
    layer = _require(body, "layer_id")
    result = session.draft.add_layer(profile, layer)
    if not result.success:
        return _err("validation_error", result.diagnostics[0].message)
    _update_draft(session)
    session.touch()
    return _ok(build_state(session))


def handle_rename_layer(session: EditorSession, body: dict) -> dict:
    profile = _require(body, "profile")
    old_id = _require(body, "old_layer_id")
    new_id = _require(body, "new_layer_id")
    result = session.draft.rename_layer(profile, old_id, new_id)
    if not result.success:
        return _err("validation_error", result.diagnostics[0].message)
    _update_draft(session)
    session.touch()
    return _ok(build_state(session))


def handle_remove_layer(session: EditorSession, body: dict) -> dict:
    profile = _require(body, "profile")
    layer = _require(body, "layer_id")
    result = session.draft.remove_layer(profile, layer)
    if not result.success:
        return _err("validation_error", result.diagnostics[0].message)
    _update_draft(session)
    session.touch()
    return _ok(build_state(session))


def handle_set_initial_layer(session: EditorSession, body: dict) -> dict:
    layer = _require(body, "layer_id")
    result = session.draft.set_initial_layer(layer)
    if not result.success:
        return _err("validation_error", result.diagnostics[0].message)
    _update_draft(session)
    session.touch()
    return _ok(build_state(session))


# ── Review ─────────────────────────────────────────────────────────

def handle_validate(session: EditorSession, _query: dict = None) -> dict:
    session.touch()
    return _ok(build_state(session))


def handle_diff(session: EditorSession, _query: dict = None) -> dict:
    from yyr4_linux_control.configurator.diff import diff_draft
    session.touch()

    diff_result = diff_draft(session.draft)
    changes = []
    for c in diff_result.changes:
        changes.append({
            "kind": c.kind,
            "path": c.path,
            "before": c.before_summary,
            "after": c.after_summary,
            "risk": c.risk,
        })

    response = {
        "change_count": len(changes),
        "changes": changes,
        "risk_summary": diff_result.risk_summary,
    }
    if diff_result.default_profile_changed:
        response["default_profile_changed"] = list(diff_result.default_profile_changed)
    if diff_result.initial_layer_changed:
        response["initial_layer_changed"] = list(diff_result.initial_layer_changed)

    return _ok(response)


def handle_unified_diff(session: EditorSession, _query: dict = None) -> dict:
    from yyr4_linux_control.configurator.serializer import serialize as _ser
    session.touch()
    base_text = _ser(session.draft.base_config)
    draft_text = _ser(session.draft.working_config)
    ud = unified_diff(base_text, draft_text)
    return _ok({"unified_diff": ud})


# ── Save ───────────────────────────────────────────────────────────

def handle_save(session: EditorSession, _body: dict = None) -> dict:
    session.touch()

    # Require review before save
    if not session.reviewed:
        return _err("validation_error", "You must review changes before saving")

    validation = session.draft.validate()
    if not validation.valid:
        return _err("validation_error",
                     "; ".join(e.message for e in validation.errors))

    expected = session.base_sha256
    target_p = Path(session.target_path)
    # If target doesn't exist, expected should be None (new file)
    if not target_p.exists():
        expected = None

    try:
        result = save_draft(
            session.draft,
            target_p,
            expected,
            backup_dir=session.backup_dir,
        )
    except SaveValidationError as e:
        return _err("validation_error", str(e))
    except SymlinkTargetError:
        return _err("symlink_rejected", "Target is a symlink")
    except ConcurrentModificationError as e:
        return _err("concurrent_modification", str(e))

    # After successful save, refresh base
    session.refresh_base()
    session.discard_recovery()
    session.write_registry()

    return _ok({
        "saved_sha256": result.saved_sha256,
        "saved_at": time.time(),
        "verified": result.verified,
        "backup_path": str(result.backup_path) if result.backup_path else None,
    })


# ── Helpers ────────────────────────────────────────────────────────

def _require(body: dict, key: str) -> any:
    if key not in body:
        raise KeyError(f"Missing required field: {key}")
    return body[key]


def _ok(data: dict) -> dict:
    return {"status": "ok", **data}


def _err(code: str, message: str = "", path: str = "",
         details: dict = None) -> dict:
    from .security import make_error
    return {"status": "error", **make_error(code, message, path, details)}
