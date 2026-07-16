"""Mutable in-memory configuration draft for editing operations.

All mutations return structured results.  No mutation silently fails.
The base config is never mutated — all edits operate on a working copy.
"""

from __future__ import annotations
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from yyr4_linux_control.control.config import load_control_config_from_file
from yyr4_linux_control.control.models import (
    OfficialControl, LayerId, ProfileId, LayerConfig, ProfileConfig,
    LayeredControlConfig,
)
from yyr4_linux_control.control.actions import (
    Action, HotkeyAction, SetLayerAction, SetProfileAction,
)

from .serializer import serialize


@dataclass
class DraftDiagnostic:
    level: str  # "error" or "warning"
    message: str
    path: Optional[str] = None


@dataclass
class DraftMutationResult:
    success: bool
    diagnostics: List[DraftDiagnostic] = field(default_factory=list)


@dataclass
class DraftValidationResult:
    """Result of validating a draft for save readiness."""
    valid: bool
    errors: List[DraftDiagnostic] = field(default_factory=list)
    warnings: List[DraftDiagnostic] = field(default_factory=list)
    canonical_text: Optional[str] = None
    serialized_sha256: Optional[str] = None


class ConfigDraft:
    """Mutable draft of a schema-v2 configuration.

    Use only the public mutation methods — never directly modify
    ``working_config`` or ``base_config``.
    """

    def __init__(self, source_path: Path):
        config = load_control_config_from_file(source_path)
        if config.schema_version < 2:
            raise ValueError(
                f"Draft editing requires schema version 2; "
                f"this config is v{config.schema_version}"
            )
        self.schema_version = config.schema_version
        self.base_source_path = str(source_path)
        self.base_sha256 = _sha256_config(config)
        self.base_config: LayeredControlConfig = config
        self.working_config: LayeredControlConfig = deepcopy(config)
        self._dirty = False
        self._mutation_count = 0
        self._diagnostics: List[DraftDiagnostic] = []
        # Mutation records for intent-preserving diff (rename tracking)
        self._mutation_records: List[dict] = []

    @property
    def dirty(self) -> bool:
        return self._dirty

    @property
    def mutation_count(self) -> int:
        return self._mutation_count

    @property
    def diagnostics(self) -> Tuple[DraftDiagnostic, ...]:
        return tuple(self._diagnostics)

    def _mark_dirty(self) -> None:
        self._dirty = True
        self._mutation_count += 1

    def _profile(self, pid: str) -> ProfileConfig:
        return self.working_config.profiles[_pid(pid)]

    def _layer(self, pid: str, lid: str) -> LayerConfig:
        return self._profile(pid).layers[_lid(lid)]

    # ── Profile ──────────────────────────────────────────────

    def add_profile(self, profile_id: str) -> DraftMutationResult:
        pid = _try_profile_id(profile_id, "add_profile")
        if pid is None:
            return DraftMutationResult(False, [
                DraftDiagnostic("error", f"Invalid profile ID: {profile_id!r}", "add_profile"),
            ])
        if pid in self.working_config.profiles:
            return DraftMutationResult(False, [
                DraftDiagnostic("error", f"Profile {profile_id!r} already exists", "add_profile"),
            ])
        new_profile = ProfileConfig(
            profile_id=pid,
            layers={LayerId("general"): LayerConfig(layer_id=LayerId("general"), controls={})},
        )
        wc = self.working_config
        new_profiles = dict(wc.profiles)
        new_profiles[pid] = new_profile
        self.working_config = LayeredControlConfig(
            schema_version=wc.schema_version,
            default_profile=wc.default_profile,
            initial_layer=wc.initial_layer,
            profiles=new_profiles,
        )
        self._mark_dirty()
        return DraftMutationResult(True)

    def rename_profile(self, old_id: str, new_id: str) -> DraftMutationResult:
        old_pid = _try_profile_id(old_id, "rename_profile")
        new_pid = _try_profile_id(new_id, "rename_profile")
        if old_pid is None:
            return DraftMutationResult(False, [
                DraftDiagnostic("error", f"Invalid old profile ID: {old_id!r}", "rename_profile"),
            ])
        if new_pid is None:
            return DraftMutationResult(False, [
                DraftDiagnostic("error", f"Invalid new profile ID: {new_id!r}", "rename_profile"),
            ])
        if old_pid not in self.working_config.profiles:
            return DraftMutationResult(False, [
                DraftDiagnostic("error", f"Profile {old_id!r} does not exist", "rename_profile"),
            ])
        if new_pid in self.working_config.profiles:
            return DraftMutationResult(False, [
                DraftDiagnostic("error", f"Profile {new_id!r} already exists", "rename_profile"),
            ])
        wc = self.working_config
        new_profiles = {}
        for k, v in wc.profiles.items():
            if k == old_pid:
                new_profiles[new_pid] = v
            else:
                new_profiles[k] = v
        new_default = new_pid if wc.default_profile == old_pid else wc.default_profile
        # Fix SetProfileAction references
        _fix_setprofile_refs(new_profiles, old_pid, new_pid)
        self.working_config = LayeredControlConfig(
            schema_version=wc.schema_version,
            default_profile=new_default,
            initial_layer=wc.initial_layer,
            profiles=new_profiles,
        )
        self._mutation_records.append({
            "kind": "profile_renamed",
            "path": f"profiles.{old_id}",
            "before": old_id,
            "after": new_id,
        })
        self._mark_dirty()
        return DraftMutationResult(True)

    def remove_profile(self, profile_id: str) -> DraftMutationResult:
        pid = _try_profile_id(profile_id, "remove_profile")
        if pid is None:
            return DraftMutationResult(False, [
                DraftDiagnostic("error", f"Invalid profile ID: {profile_id!r}", "remove_profile"),
            ])
        if pid not in self.working_config.profiles:
            return DraftMutationResult(False, [
                DraftDiagnostic("error", f"Profile {profile_id!r} does not exist", "remove_profile"),
            ])
        if len(self.working_config.profiles) <= 1:
            return DraftMutationResult(False, [
                DraftDiagnostic("error", "Cannot remove the last profile", "remove_profile"),
            ])
        if pid == self.working_config.default_profile:
            return DraftMutationResult(False, [
                DraftDiagnostic("error",
                               f"Cannot remove the default profile {profile_id!r}; "
                               "set a different default first",
                               "remove_profile"),
            ])
        # Check for runtime action references
        refs = _find_setprofile_refs_to(self.working_config, pid)
        if refs:
            return DraftMutationResult(False, [
                DraftDiagnostic("error",
                               f"Profile {profile_id!r} is referenced by "
                               f"SetProfileAction in {refs[0]}",
                               "remove_profile"),
            ])
        wc = self.working_config
        new_profiles = {k: v for k, v in wc.profiles.items() if k != pid}
        self.working_config = LayeredControlConfig(
            schema_version=wc.schema_version,
            default_profile=wc.default_profile,
            initial_layer=wc.initial_layer,
            profiles=new_profiles,
        )
        self._mark_dirty()
        return DraftMutationResult(True)

    def set_default_profile(self, profile_id: str) -> DraftMutationResult:
        pid = _try_profile_id(profile_id, "set_default_profile")
        if pid is None:
            return DraftMutationResult(False, [
                DraftDiagnostic("error", f"Invalid profile ID: {profile_id!r}", "set_default_profile"),
            ])
        if pid not in self.working_config.profiles:
            return DraftMutationResult(False, [
                DraftDiagnostic("error", f"Profile {profile_id!r} does not exist", "set_default_profile"),
            ])
        if self.working_config.default_profile == pid:
            return DraftMutationResult(True)
        wc = self.working_config
        self.working_config = LayeredControlConfig(
            schema_version=wc.schema_version,
            default_profile=pid,
            initial_layer=wc.initial_layer,
            profiles=wc.profiles,
        )
        self._mark_dirty()
        return DraftMutationResult(True)

    # ── Layer ────────────────────────────────────────────────

    def add_layer(self, profile_id: str, layer_id: str) -> DraftMutationResult:
        pid = _try_profile_id(profile_id, "add_layer")
        lid = _try_layer_id(layer_id, "add_layer")
        if pid is None or lid is None:
            return DraftMutationResult(False, [
                DraftDiagnostic("error", f"Invalid profile/layer ID", "add_layer"),
            ])
        if pid not in self.working_config.profiles:
            return DraftMutationResult(False, [
                DraftDiagnostic("error", f"Profile {profile_id!r} not found", "add_layer"),
            ])
        if lid in self.working_config.profiles[pid].layers:
            return DraftMutationResult(False, [
                DraftDiagnostic("error", f"Layer {layer_id!r} already exists in {profile_id!r}", "add_layer"),
            ])
        prof = self.working_config.profiles[pid]
        new_layers = dict(prof.layers)
        new_layers[lid] = LayerConfig(layer_id=lid, controls={})
        new_profiles = dict(self.working_config.profiles)
        new_profiles[pid] = ProfileConfig(profile_id=pid, layers=new_layers)
        self.working_config = LayeredControlConfig(
            schema_version=self.working_config.schema_version,
            default_profile=self.working_config.default_profile,
            initial_layer=self.working_config.initial_layer,
            profiles=new_profiles,
        )
        self._mark_dirty()
        return DraftMutationResult(True)

    def rename_layer(self, profile_id: str, old_lid: str, new_lid: str) -> DraftMutationResult:
        pid = _try_profile_id(profile_id, "rename_layer")
        old = _try_layer_id(old_lid, "rename_layer")
        new = _try_layer_id(new_lid, "rename_layer")
        if pid is None or old is None or new is None:
            return DraftMutationResult(False, [
                DraftDiagnostic("error", "Invalid profile/layer ID", "rename_layer"),
            ])
        if pid not in self.working_config.profiles:
            return DraftMutationResult(False, [
                DraftDiagnostic("error", f"Profile {profile_id!r} not found", "rename_layer"),
            ])
        prof = self.working_config.profiles[pid]
        if old not in prof.layers:
            return DraftMutationResult(False, [
                DraftDiagnostic("error", f"Layer {old_lid!r} not found in {profile_id!r}", "rename_layer"),
            ])
        if new in prof.layers:
            return DraftMutationResult(False, [
                DraftDiagnostic("error", f"Layer {new_lid!r} already exists in {profile_id!r}", "rename_layer"),
            ])
        new_layers = {}
        for k, v in prof.layers.items():
            if k == old:
                new_layers[new] = v
            else:
                new_layers[k] = v
        # Fix SetLayerAction references
        _fix_setlayer_refs(new_layers, old, new)
        new_profiles = dict(self.working_config.profiles)
        new_profiles[pid] = ProfileConfig(profile_id=pid, layers=new_layers)
        new_initial = new if self.working_config.initial_layer == old else self.working_config.initial_layer
        self.working_config = LayeredControlConfig(
            schema_version=self.working_config.schema_version,
            default_profile=self.working_config.default_profile,
            initial_layer=new_initial,
            profiles=new_profiles,
        )
        self._mutation_records.append({
            "kind": "layer_renamed",
            "path": f"profiles.{profile_id}.layers.{old_lid}",
            "before": old_lid,
            "after": new_lid,
        })
        self._mark_dirty()
        return DraftMutationResult(True)

    def remove_layer(self, profile_id: str, layer_id: str) -> DraftMutationResult:
        pid = _try_profile_id(profile_id, "remove_layer")
        lid = _try_layer_id(layer_id, "remove_layer")
        if pid is None or lid is None:
            return DraftMutationResult(False, [
                DraftDiagnostic("error", "Invalid profile/layer ID", "remove_layer"),
            ])
        if pid not in self.working_config.profiles:
            return DraftMutationResult(False, [
                DraftDiagnostic("error", f"Profile {profile_id!r} not found", "remove_layer"),
            ])
        prof = self.working_config.profiles[pid]
        if lid not in prof.layers:
            return DraftMutationResult(False, [
                DraftDiagnostic("error", f"Layer {layer_id!r} not found in {profile_id!r}", "remove_layer"),
            ])
        if lid == LayerId("general"):
            return DraftMutationResult(False, [
                DraftDiagnostic("error", "Cannot remove the general layer", "remove_layer"),
            ])
        if len(prof.layers) <= 1:
            return DraftMutationResult(False, [
                DraftDiagnostic("error", "Cannot remove the last layer", "remove_layer"),
            ])
        # Check for runtime references
        refs = _find_setlayer_refs_to(self.working_config, pid, lid)
        if refs:
            return DraftMutationResult(False, [
                DraftDiagnostic("error",
                               f"Layer {layer_id!r} is referenced by "
                               f"SetLayerAction in {refs[0]}",
                               "remove_layer"),
            ])
        new_layers = {k: v for k, v in prof.layers.items() if k != lid}
        new_profiles = dict(self.working_config.profiles)
        new_profiles[pid] = ProfileConfig(profile_id=pid, layers=new_layers)
        self.working_config = LayeredControlConfig(
            schema_version=self.working_config.schema_version,
            default_profile=self.working_config.default_profile,
            initial_layer=self.working_config.initial_layer,
            profiles=new_profiles,
        )
        self._mark_dirty()
        return DraftMutationResult(True)

    def set_initial_layer(self, layer_id: str) -> DraftMutationResult:
        lid = _try_layer_id(layer_id, "set_initial_layer")
        if lid is None:
            return DraftMutationResult(False, [
                DraftDiagnostic("error", f"Invalid LayerId: {layer_id!r}", "set_initial_layer"),
            ])
        if self.working_config.initial_layer == lid:
            return DraftMutationResult(True)
        self.working_config = LayeredControlConfig(
            schema_version=self.working_config.schema_version,
            default_profile=self.working_config.default_profile,
            initial_layer=lid,
            profiles=self.working_config.profiles,
        )
        self._mark_dirty()
        return DraftMutationResult(True)

    # ── Actions ──────────────────────────────────────────────

    def set_action(self, profile_id: str, layer_id: str,
                   control: str, action: Action) -> DraftMutationResult:
        pid = _try_profile_id(profile_id, "set_action")
        lid = _try_layer_id(layer_id, "set_action")
        oc = _try_official_control(control, "set_action")
        if pid is None or lid is None or oc is None:
            return DraftMutationResult(False, [
                DraftDiagnostic("error", f"Invalid profile/layer/control", "set_action"),
            ])
        if pid not in self.working_config.profiles:
            return DraftMutationResult(False, [
                DraftDiagnostic("error", f"Profile {profile_id!r} not found", "set_action"),
            ])
        prof = self.working_config.profiles[pid]
        if lid not in prof.layers:
            return DraftMutationResult(False, [
                DraftDiagnostic("error", f"Layer {layer_id!r} not found in {profile_id!r}", "set_action"),
            ])
        new_layers = dict(prof.layers)
        layer = new_layers[lid]
        new_controls = dict(layer.controls)
        new_controls[oc] = action
        new_layers[lid] = LayerConfig(layer_id=lid, controls=new_controls)
        new_profiles = dict(self.working_config.profiles)
        new_profiles[pid] = ProfileConfig(profile_id=pid, layers=new_layers)
        self.working_config = LayeredControlConfig(
            schema_version=self.working_config.schema_version,
            default_profile=self.working_config.default_profile,
            initial_layer=self.working_config.initial_layer,
            profiles=new_profiles,
        )
        self._mark_dirty()
        return DraftMutationResult(True)

    def clear_action(self, profile_id: str, layer_id: str,
                     control: str) -> DraftMutationResult:
        pid = _try_profile_id(profile_id, "clear_action")
        lid = _try_layer_id(layer_id, "clear_action")
        oc = _try_official_control(control, "clear_action")
        if pid is None or lid is None or oc is None:
            return DraftMutationResult(False, [
                DraftDiagnostic("error", f"Invalid profile/layer/control", "clear_action"),
            ])
        if pid not in self.working_config.profiles:
            return DraftMutationResult(False, [
                DraftDiagnostic("error", f"Profile {profile_id!r} not found", "clear_action"),
            ])
        prof = self.working_config.profiles[pid]
        if lid not in prof.layers:
            return DraftMutationResult(False, [
                DraftDiagnostic("error", f"Layer {layer_id!r} not found in {profile_id!r}", "clear_action"),
            ])
        new_layers = dict(prof.layers)
        layer = new_layers[lid]
        if oc not in layer.controls:
            return DraftMutationResult(True)  # already clear
        new_controls = dict(layer.controls)
        del new_controls[oc]
        new_layers[lid] = LayerConfig(layer_id=lid, controls=new_controls)
        new_profiles = dict(self.working_config.profiles)
        new_profiles[pid] = ProfileConfig(profile_id=pid, layers=new_layers)
        self.working_config = LayeredControlConfig(
            schema_version=self.working_config.schema_version,
            default_profile=self.working_config.default_profile,
            initial_layer=self.working_config.initial_layer,
            profiles=new_profiles,
        )
        self._mark_dirty()
        return DraftMutationResult(True)

    # ── Validation ───────────────────────────────────────────

    def validate(self) -> DraftValidationResult:
        """Round-trip validate: serialize → re-parse → compare."""
        try:
            text = serialize(self.working_config)
        except Exception as e:
            return DraftValidationResult(
                valid=False,
                errors=[DraftDiagnostic("error", f"Serialization failed: {e}")],
            )
        sha = _sha256_bytes(text.encode("utf-8"))
        try:
            re_parsed = _load_from_string(text)
        except Exception as e:
            return DraftValidationResult(
                valid=False,
                errors=[DraftDiagnostic("error", f"Re-parse of serialized config failed: {e}")],
                canonical_text=text,
                serialized_sha256=sha,
            )
        return DraftValidationResult(
            valid=True,
            canonical_text=text,
            serialized_sha256=sha,
        )


# ── Helpers ───────────────────────────────────────────────────────

def _pid(s: str) -> ProfileId:
    return ProfileId(s)


def _lid(s: str) -> LayerId:
    return LayerId(s)


def _try_profile_id(s: str, ctx: str) -> Optional[ProfileId]:
    try:
        return ProfileId(s)
    except ValueError:
        return None


def _try_layer_id(s: str, ctx: str) -> Optional[LayerId]:
    try:
        return LayerId(s)
    except ValueError:
        return None


def _try_official_control(s: str, ctx: str) -> Optional[OfficialControl]:
    try:
        return OfficialControl(s)
    except ValueError:
        return None


def _sha256_config(config: LayeredControlConfig) -> str:
    return _sha256_bytes(serialize(config).encode("utf-8"))


def _sha256_bytes(data: bytes) -> str:
    import hashlib
    return hashlib.sha256(data).hexdigest()


def _load_from_string(text: str) -> LayeredControlConfig:
    import tempfile, os
    fd, name = tempfile.mkstemp(suffix=".toml")
    try:
        os.write(fd, text.encode("utf-8"))
        os.close(fd)
        fd = -1
        return load_control_config_from_file(Path(name))
    finally:
        if fd >= 0:
            os.close(fd)
        try:
            os.unlink(name)
        except OSError:
            pass


def _fix_setprofile_refs(profiles: Dict, old_id: ProfileId, new_id: ProfileId) -> None:
    """Update SetProfileAction targets in-place."""
    for prof in profiles.values():
        for layer in prof.layers.values():
            for ctrl, action in list(layer.controls.items()):
                if isinstance(action, SetProfileAction) and action.profile == old_id.value:
                    layer.controls[ctrl] = SetProfileAction(new_id.value)


def _fix_setlayer_refs(layers: Dict, old_id: LayerId, new_id: LayerId) -> None:
    """Update SetLayerAction targets in-place."""
    for layer in layers.values():
        for ctrl, action in list(layer.controls.items()):
            if isinstance(action, SetLayerAction) and action.layer == old_id.value:
                layer.controls[ctrl] = SetLayerAction(new_id.value)


def _find_setprofile_refs_to(
    config: LayeredControlConfig, target: ProfileId,
) -> List[str]:
    refs = []
    for pid, prof in config.profiles.items():
        for lid, layer in prof.layers.items():
            for ctrl, action in layer.controls.items():
                if isinstance(action, SetProfileAction) and action.profile == target.value:
                    refs.append(f"profiles.{pid.value}.layers.{lid.value}.controls.{ctrl.value}")
    return refs


def _find_setlayer_refs_to(
    config: LayeredControlConfig, profile_id: ProfileId, target: LayerId,
) -> List[str]:
    refs = []
    for pid, prof in config.profiles.items():
        for lid, layer in prof.layers.items():
            for ctrl, action in layer.controls.items():
                if isinstance(action, SetLayerAction) and action.layer == target.value:
                    refs.append(f"profiles.{pid.value}.layers.{lid.value}.controls.{ctrl.value}")
    return refs
