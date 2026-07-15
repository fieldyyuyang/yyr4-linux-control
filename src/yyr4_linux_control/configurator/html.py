"""Generate a self-contained, read-only HTML preview from Configurator View Models.

No external resources, no JavaScript, no server, no hardware access.
"""

import html
from typing import Optional

from .models import (
    ConfiguratorDocument, ProfileView, LayerView, ControlView, ActionView,
)

_CSS = r"""
body{font-family:system-ui,sans-serif;background:#1a1a2e;color:#e0e0e0;margin:0;padding:20px}
h1,h2,h3{margin:0 0 8px 0}
.meta{display:flex;flex-wrap:wrap;gap:12px;margin-bottom:16px;color:#a0a0b0}
.meta span{background:#16213e;padding:4px 10px;border-radius:4px;font-size:13px}
.warn{background:#332200;border-left:3px solid #ffaa00;padding:8px 12px;margin:8px 0;border-radius:4px}
.flag-readonly{background:#661111;color:#ff8888;padding:4px 10px;font-weight:bold;display:inline-block;margin-bottom:12px;border-radius:3px}
.profile{margin:20px 0;border:1px solid #333;border-radius:6px;overflow:hidden}
.profile-header{background:#16213e;padding:12px 16px;display:flex;justify-content:space-between;align-items:center}
.profile-header h2{margin:0}
.profile-header .badge{background:#0f3460;color:#e0e0e0;padding:2px 8px;border-radius:4px;font-size:12px}
.layer{margin:4px 16px 12px 16px}
.layer h3{color:#7aa2f7;margin-bottom:4px}
.layer .meta-line{color:#a0a0b0;font-size:12px;margin-bottom:8px}
.desk{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:16px}
.desk-label{width:100%;color:#7aa2f7;font-size:14px;font-weight:bold;margin-top:12px}
.ctrl{background:#0f3460;border-radius:6px;padding:10px;width:180px;min-height:50px;flex-shrink:0}
.ctrl-name{font-weight:bold;font-size:15px}
.ctrl-kind{font-size:10px;color:#a0a0b0;text-transform:uppercase}
.ctrl-summary{font-size:12px;margin-top:4px;color:#c0c0c0}
.ctrl-unmapped{color:#666}
.ctrl .tag{display:inline-block;padding:1px 6px;border-radius:3px;font-size:10px;margin-right:3px}
.tag-hotkey{background:#1a3a1a;color:#7f7}
.tag-text{background:#1a3a1a;color:#7cc}
.tag-command{background:#331;color:#fc6}
.tag-macro{background:#113;color:#aaf}
.tag-delay{background:#133;color:#aaa}
.tag-noop{background:#222;color:#888}
.tag-debug{background:#222;color:#8af}
.tag-layer{background:#313;color:#f8f}
.tag-unknown{background:#311;color:#f66}
.encoder-group{display:flex;gap:8px;align-items:flex-start}
.encoder-label{writing-mode:vertical-lr;text-orientation:mixed;background:#16213e;padding:6px 4px;border-radius:4px;font-size:11px;color:#7aa2f7;min-height:60px;display:flex;align-items:center;justify-content:center}
.macro-steps{margin-left:16px;margin-top:4px}
.macro-step{font-size:11px;color:#a0a0b0;margin:2px 0}
.safety{background:#112;border:1px solid #333;padding:12px;margin-top:20px;border-radius:6px;font-size:12px;color:#888}
"""


def generate_html(doc: ConfiguratorDocument, title: str = "YYR4 Config Preview") -> str:
    """Return a complete self-contained HTML page as a string."""
    parts = [
        "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n",
        f"<meta charset=\"utf-8\">\n<title>{html.escape(title)}</title>\n",
        f"<style>{_CSS}</style>\n</head>\n<body>\n",
        f"<div class=\"flag-readonly\">READ-ONLY CONFIGURATION PREVIEW</div>\n",
        f"<h1>{html.escape(title)}</h1>\n",
        _build_meta(doc),
    ]

    for profile in doc.profiles:
        parts.append(_build_profile(profile, doc))

    parts.append(_build_safety(doc))
    parts.append("</body>\n</html>")
    return "".join(parts)


def _build_meta(doc: ConfiguratorDocument) -> str:
    return (
        '<div class="meta">'
        f"<span>Source: {html.escape(doc.source_path)}</span>"
        f"<span>Schema v{doc.schema_version}</span>"
        f"<span>Default: {html.escape(doc.default_profile)}</span>"
        f"<span>Initial layer: {html.escape(doc.initial_layer)}</span>"
        f"<span>Profiles: {doc.profile_count}</span>"
        f"<span>Layers: {doc.total_layer_count}</span>"
        f"<span>Controls: {doc.total_configured_controls}</span>"
        f"<span>Status: {html.escape(doc.validation_status)}</span>"
        "</div>\n"
    )


def _build_profile(profile: ProfileView, doc: ConfiguratorDocument) -> str:
    default_badge = ' <span class="badge">DEFAULT</span>' if profile.is_default else ""
    parts = [
        '<div class="profile">\n',
        '<div class="profile-header">',
        f"<h2>{html.escape(profile.profile_id)}{default_badge}</h2>",
        f"<span>{profile.layer_count} layers, {profile.configured_control_count} controls</span>",
        "</div>\n",
    ]
    for layer in profile.layers:
        parts.append(_build_layer(layer, doc))
    parts.append("</div>\n")
    return "".join(parts)


def _build_layer(layer: LayerView, doc: ConfiguratorDocument) -> str:
    initial_badge = " [INITIAL]" if layer.is_initial else ""
    parts = [
        '<div class="layer">\n',
        f"<h3>{html.escape(layer.layer_id)}{initial_badge}</h3>\n",
        f'<div class="meta-line">{layer.configured_control_count} of 24 configured</div>\n',
    ]
    # Buttons
    buttons = [c for c in layer.controls if c.control_kind == "button"]
    if buttons:
        parts.append('<div class="desk-label">BUTTONS</div>\n<div class="desk">\n')
        for c in buttons:
            parts.append(_build_control(c))
        parts.append("</div>\n")
    # Encoders
    for group in ("A", "B", "C", "D"):
        encs = [c for c in layer.controls if c.encoder_group == group]
        if not encs:
            continue
        parts.append(
            f'<div class="desk-label">ENCODER {group} '
            f'(Left / Press / Right)</div>\n'
            '<div class="encoder-group">\n'
            f'<div class="encoder-label">E{group}</div>\n'
            '<div class="desk" style="flex:1">\n'
        )
        for c in encs:
            parts.append(_build_control(c))
        parts.append("</div></div>\n")
    parts.append("</div>\n")
    return "".join(parts)


def _build_control(ctrl: ControlView) -> str:
    kind_label = ctrl.control_kind.replace("encoder_", "").replace("counterclockwise", "CCW").replace("clockwise", "CW")
    if ctrl.configured:
        tags = _action_tags(ctrl.action)
        summary = html.escape(ctrl.action_summary)
    else:
        tags = '<span class="tag tag-noop">UNMAPPED</span>'
        summary = '<span class="ctrl-unmapped">—</span>'
    return (
        f'<div class="ctrl">'
        f'<div class="ctrl-name">{html.escape(ctrl.official_name)}</div>'
        f'<div class="ctrl-kind">{kind_label}</div>'
        f'<div class="ctrl-summary">{tags} {summary}</div>'
        f'{_build_macro_steps(ctrl.action) if ctrl.action and ctrl.action.child_steps else ""}'
        f"</div>\n"
    )


def _action_tags(action: Optional[ActionView]) -> str:
    if action is None:
        return ""
    tag_map = {
        "Hotkey": "tag-hotkey",
        "Text": "tag-text",
        "Command": "tag-command",
        "Macro": "tag-macro",
        "Delay": "tag-delay",
        "NoOp": "tag-noop",
        "DebugLog": "tag-debug",
        "SetLayer": "tag-layer",
        "NextLayer": "tag-layer",
        "PreviousLayer": "tag-layer",
        "SetProfile": "tag-layer",
    }
    cls = tag_map.get(action.action_type, "tag-unknown")
    return f'<span class="tag {cls}">{html.escape(action.action_type)}</span>'


def _build_macro_steps(action: Optional[ActionView]) -> str:
    if action is None or not action.child_steps:
        return ""
    parts = ['<div class="macro-steps">']
    for i, step in enumerate(action.child_steps):
        detail = html.escape(step.concise_summary)
        parts.append(
            f'<div class="macro-step">{i+1}. '
            f'<span class="tag {_step_tag(step)}">{html.escape(step.action_type)}</span> '
            f'{detail}</div>'
        )
    parts.append("</div>")
    return "".join(parts)


def _step_tag(step: ActionView) -> str:
    if step.action_type == "Delay":
        return "tag-delay"
    return "tag-hotkey"


def _build_safety(doc: ConfiguratorDocument) -> str:
    return (
        '<div class="safety">'
        "<strong>Safety</strong>: This is a read-only preview. "
        "No actions are executed, no hardware is accessed, no daemon is running. "
        "Configuration editing is not supported in this view."
        "</div>\n"
    )
