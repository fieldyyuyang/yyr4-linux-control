"""Semantic configuration diff and unified text diff for YYR4 configurations.

Produces fully-qualified kind names that clearly identify the entity
type (profile_added, layer_removed, control_mapped, macro_step_changed,
runtime_target_changed, etc.).
"""

from __future__ import annotations
import difflib
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from yyr4_linux_control.control.models import OfficialControl

from .serializer import serialize


@dataclass
class ControlDiff:
    path: str                    # profiles.X.layers.Y.controls.Z
    kind: str                    # control_mapped, control_unmapped, control_action_changed
    before_summary: str
    after_summary: str
    risk: str = "LOW"


@dataclass
class LayerDiff:
    path: str                    # profiles.X.layers.Y
    kind: str                    # layer_added, layer_removed, layer_renamed
    before_summary: str
    after_summary: str
    risk: str = "LOW"


@dataclass
class ProfileDiff:
    path: str                    # profiles.X
    kind: str                    # profile_added, profile_removed, profile_renamed
    before_summary: str
    after_summary: str
    risk: str = "LOW"


@dataclass
class ConfigDiff:
    changes: List[ProfileDiff | LayerDiff | ControlDiff] = field(default_factory=list)
    default_profile_changed: Optional[Tuple[str, str]] = None   # (before, after)
    initial_layer_changed: Optional[Tuple[str, str]] = None     # (before, after)
    risk_summary: str = "LOW"


_RISK_ORDER = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}


def diff_configs(base: "LayeredControlConfig",  # type: ignore
                 draft: "LayeredControlConfig",  # type: ignore
                 ) -> ConfigDiff:
    """Compute semantic differences between two configurations."""
    changes: List[ProfileDiff | LayerDiff | ControlDiff] = []

    base_profiles = set(base.profiles.keys())
    draft_profiles = set(draft.profiles.keys())

    for pid in sorted(base_profiles - draft_profiles, key=lambda p: p.value):
        changes.append(ProfileDiff(
            path=f"profiles.{pid.value}",
            kind="profile_removed",
            before_summary=f"Profile {pid.value}",
            after_summary="(removed)",
            risk="HIGH",
        ))

    for pid in sorted(draft_profiles - base_profiles, key=lambda p: p.value):
        changes.append(ProfileDiff(
            path=f"profiles.{pid.value}",
            kind="profile_added",
            before_summary="(new)",
            after_summary=f"Profile {pid.value}",
            risk="MEDIUM",
        ))

    for pid in sorted(base_profiles & draft_profiles, key=lambda p: p.value):
        b_prof = base.profiles[pid]
        d_prof = draft.profiles[pid]
        b_layers = set(b_prof.layers.keys())
        d_layers = set(d_prof.layers.keys())

        for lid in sorted(b_layers - d_layers, key=lambda l: l.value):
            changes.append(LayerDiff(
                path=f"profiles.{pid.value}.layers.{lid.value}",
                kind="layer_removed",
                before_summary=f"Layer {lid.value}",
                after_summary="(removed)",
                risk="HIGH",
            ))

        for lid in sorted(d_layers - b_layers, key=lambda l: l.value):
            changes.append(LayerDiff(
                path=f"profiles.{pid.value}.layers.{lid.value}",
                kind="layer_added",
                before_summary="(new)",
                after_summary=f"Layer {lid.value}",
                risk="MEDIUM",
            ))

        for lid in sorted(b_layers & d_layers, key=lambda l: l.value):
            b_ctrl = b_prof.layers[lid].controls
            d_ctrl = d_prof.layers[lid].controls
            all_names = set(list(b_ctrl.keys()) + list(d_ctrl.keys()))
            for oc in sorted(all_names, key=lambda c: c.value):
                b_act = b_ctrl.get(oc)
                d_act = d_ctrl.get(oc)
                cpath = f"profiles.{pid.value}.layers.{lid.value}.controls.{oc.value}"
                if b_act is None and d_act is not None:
                    changes.append(ControlDiff(
                        path=cpath, kind="control_mapped",
                        before_summary="UNMAPPED",
                        after_summary=_summarize(d_act),
                        risk=_risk_action(d_act),
                    ))
                elif b_act is not None and d_act is None:
                    changes.append(ControlDiff(
                        path=cpath, kind="control_unmapped",
                        before_summary=_summarize(b_act),
                        after_summary="UNMAPPED",
                        risk="MEDIUM",
                    ))
                elif b_act is not None and d_act is not None and b_act != d_act:
                    # Check for macro step changes and runtime target changes
                    sub = _sub_control_diffs(cpath, b_act, d_act)
                    changes.extend(sub)
                    changes.append(ControlDiff(
                        path=cpath, kind="control_action_changed",
                        before_summary=_summarize(b_act),
                        after_summary=_summarize(d_act),
                        risk=_max_risk(_risk_action(b_act), _risk_action(d_act)),
                    ))

    def_profile_changed = None
    if base.default_profile != draft.default_profile:
        def_profile_changed = (base.default_profile.value, draft.default_profile.value)
        changes.insert(0, ProfileDiff(
            path="default_profile",
            kind="default_profile_changed",
            before_summary=base.default_profile.value,
            after_summary=draft.default_profile.value,
            risk="MEDIUM",
        ))

    init_layer_changed = None
    if base.initial_layer != draft.initial_layer:
        init_layer_changed = (base.initial_layer.value, draft.initial_layer.value)
        changes.insert(0, LayerDiff(
            path="initial_layer",
            kind="initial_layer_changed",
            before_summary=base.initial_layer.value,
            after_summary=draft.initial_layer.value,
            risk="MEDIUM",
        ))

    risks = [_RISK_ORDER.get(c.risk, 0) for c in changes]
    max_risk = max(risks) if risks else 0
    risk_label = {0: "LOW", 1: "MEDIUM", 2: "HIGH"}.get(max_risk, "UNKNOWN")

    return ConfigDiff(
        changes=changes,
        default_profile_changed=def_profile_changed,
        initial_layer_changed=init_layer_changed,
        risk_summary=risk_label,
    )


def unified_diff(base_text: str, draft_text: str,
                 fromfile: str = "base",
                 tofile: str = "draft") -> str:
    """Return a unified diff between two canonical TOML texts."""
    diff = difflib.unified_diff(
        base_text.splitlines(keepends=True),
        draft_text.splitlines(keepends=True),
        fromfile=fromfile,
        tofile=tofile,
    )
    return "".join(diff)


def diff_draft(draft) -> ConfigDiff:
    """Compute semantic differences using mutation intent for rename detection."""
    from copy import deepcopy
    from yyr4_linux_control.control.models import ProfileId, LayerId

    records = getattr(draft, '_mutation_records', [])

    # Collect rename records to emit directly
    direct_renames = []
    for rec in records:
        if rec['kind'] == 'profile_renamed':
            direct_renames.append(ProfileDiff(
                path=rec['path'], kind='profile_renamed',
                before_summary=rec['before'], after_summary=rec['after'],
                risk='MEDIUM',
            ))
        elif rec['kind'] == 'layer_renamed':
            direct_renames.append(LayerDiff(
                path=rec['path'], kind='layer_renamed',
                before_summary=rec['before'], after_summary=rec['after'],
                risk='MEDIUM',
            ))

    # Align base config to match renamed profiles so layer comparison works
    aligned_base = deepcopy(draft.base_config)
    for rec in records:
        if rec['kind'] == 'profile_renamed':
            old_pid = ProfileId(rec['before'])
            new_pid = ProfileId(rec['after'])
            if old_pid in aligned_base.profiles:
                prof = aligned_base.profiles.pop(old_pid)
                aligned_base.profiles[new_pid] = prof
            if aligned_base.default_profile == old_pid:
                aligned_base = type(aligned_base)(
                    schema_version=aligned_base.schema_version,
                    default_profile=new_pid,
                    initial_layer=aligned_base.initial_layer,
                    profiles=aligned_base.profiles,
                )

    result = diff_configs(aligned_base, draft.working_config)

    # Filter out add/remove that correspond to renames
    rename_afters = set()
    for rec in records:
        if rec['kind'] in ('profile_renamed', 'layer_renamed'):
            rename_afters.add(rec['after'])

    filtered = []
    for c in result.changes:
        if c.kind in ('profile_added', 'layer_added', 'profile_removed', 'layer_removed'):
            parts = c.path.rsplit('.', 1)
            name = parts[-1] if len(parts) > 1 else c.path
            if name in rename_afters:
                continue
            # Also filter by old name
            skip = False
            for rec in records:
                if rec.get('before') == name and rec['kind'].startswith(c.kind.split('_')[0] + '_renamed'):
                    skip = True; break
            if skip:
                continue
        filtered.append(c)

    result.changes = direct_renames + filtered
    return result

# ── Sub-control diff helpers ──────────────────────────────────────

def _sub_control_diffs(cpath: str, b_act, d_act) -> list:
    """Produce macro_step_* and runtime_target_* diffs for a changed control."""
    from yyr4_linux_control.control.actions import (
        MacroAction, SetLayerAction, SetProfileAction,
    )
    result = []

    # Macro step diffs
    if isinstance(b_act, MacroAction) and isinstance(d_act, MacroAction):
        b_steps = b_act.steps
        d_steps = d_act.steps
        max_len = max(len(b_steps), len(d_steps))
        for i in range(max_len):
            spath = f"{cpath}.steps[{i}]"
            b_s = b_steps[i] if i < len(b_steps) else None
            d_s = d_steps[i] if i < len(d_steps) else None
            if b_s is None and d_s is not None:
                result.append(ControlDiff(
                    path=spath, kind="macro_step_added",
                    before_summary="(none)",
                    after_summary=_summarize(d_s),
                    risk=_risk_action(d_s),
                ))
            elif b_s is not None and d_s is None:
                result.append(ControlDiff(
                    path=spath, kind="macro_step_removed",
                    before_summary=_summarize(b_s),
                    after_summary="(none)",
                    risk="MEDIUM",
                ))
            elif b_s is not None and d_s is not None and b_s != d_s:
                result.append(ControlDiff(
                    path=spath, kind="macro_step_changed",
                    before_summary=_summarize(b_s),
                    after_summary=_summarize(d_s),
                    risk=_max_risk(_risk_action(b_s), _risk_action(d_s)),
                ))

    # Runtime target changes
    if isinstance(b_act, SetLayerAction) and isinstance(d_act, SetLayerAction):
        if b_act.layer != d_act.layer:
            result.append(ControlDiff(
                path=cpath, kind="runtime_target_changed",
                before_summary=f"SetLayer → {b_act.layer}",
                after_summary=f"SetLayer → {d_act.layer}",
                risk="MEDIUM",
            ))
    if isinstance(b_act, SetProfileAction) and isinstance(d_act, SetProfileAction):
        if b_act.profile != d_act.profile:
            result.append(ControlDiff(
                path=cpath, kind="runtime_target_changed",
                before_summary=f"SetProfile → {b_act.profile}",
                after_summary=f"SetProfile → {d_act.profile}",
                risk="MEDIUM",
            ))

    return result


def _summarize(action: "Action") -> str:  # type: ignore
    from yyr4_linux_control.control.actions import (
        HotkeyAction, TextAction, CommandAction, DelayAction,
        MacroAction, NoOpAction, DebugLogAction,
        SetLayerAction, NextLayerAction, PreviousLayerAction, SetProfileAction,
    )
    t = type(action).__name__
    if isinstance(action, HotkeyAction):
        return "Hotkey: " + "+".join(action.keys)
    if isinstance(action, TextAction):
        return f"Text: {action.value[:40]}"
    if isinstance(action, CommandAction):
        return f"Command: {action.argv[0]}"
    if isinstance(action, DelayAction):
        return f"Delay: {action.milliseconds}ms"
    if isinstance(action, MacroAction):
        return f"Macro: {len(action.steps)} steps"
    if isinstance(action, NoOpAction):
        return "NoOp"
    if isinstance(action, DebugLogAction):
        return "DebugLog"
    if isinstance(action, SetLayerAction):
        return f"SetLayer → {action.layer}"
    if isinstance(action, NextLayerAction):
        return "NextLayer"
    if isinstance(action, PreviousLayerAction):
        return "PreviousLayer"
    if isinstance(action, SetProfileAction):
        return f"SetProfile → {action.profile}"
    return str(t)


def _risk_action(action: "Action") -> str:  # type: ignore
    from yyr4_linux_control.control.actions import (
        CommandAction, SetProfileAction,
    )
    if isinstance(action, CommandAction):
        return "HIGH"
    if isinstance(action, SetProfileAction):
        return "MEDIUM"
    return "LOW"


def _max_risk(a: str, b: str) -> str:
    return a if _RISK_ORDER.get(a, 0) >= _RISK_ORDER.get(b, 0) else b
