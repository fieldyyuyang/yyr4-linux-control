"""Self-contained HTML editor page generation.

CSS and JavaScript are produced as Python strings and served as
separate, token-gated HTTP resources.  The HTML contains no inline
styles, no inline scripts, and no inline event handlers.
"""

_BUTTON_CONTROLS = tuple(f"A{i}" for i in range(1, 13))
_ENCODER_GROUPS = {
    "A": ("AL", "AP", "AR"),
    "B": ("BL", "BP", "BR"),
    "C": ("CL", "CP", "CR"),
    "D": ("DL", "DP", "DR"),
}
_ALL_CONTROLS = list(_BUTTON_CONTROLS)
for grp in ("A", "B", "C", "D"):
    _ALL_CONTROLS.extend(_ENCODER_GROUPS[grp])

# ═══════════════════════════════════════════════════════════════════
#  CSS  (served as /s/<TOKEN>/assets/editor.css)
# ═══════════════════════════════════════════════════════════════════

EDITOR_CSS = r"""* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
       font-size: 14px; color: #222; background: #f5f5f5; line-height: 1.4; }
a { color: #0366d6; text-decoration: none; }
button { cursor: pointer; padding: 4px 10px; border: 1px solid #ccc;
         border-radius: 3px; background: #f0f0f0; font-size: 13px; }
button:hover { background: #e0e0e0; }
button:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-primary { background: #0366d6; color: #fff; border-color: #0366d6; }
.btn-primary:hover { background: #0250a3; }
.btn-danger { background: #d73a49; color: #fff; border-color: #d73a49; }
.btn-danger:hover { background: #b5303c; }

#top-bar { display: flex; align-items: center; gap: 12px; padding: 8px 16px;
           background: #24292e; color: #e1e4e8; flex-wrap: wrap; font-size: 13px; }
#top-bar .logo { font-weight: 700; font-size: 16px; margin-right: 8px; }
#top-bar .badge { padding: 2px 6px; border-radius: 3px; font-size: 11px; font-weight: 600; }
.badge.modified { background: #d73a49; color: #fff; }
.badge.clean { background: #28a745; color: #fff; }
.badge.valid { background: #28a745; color: #fff; }
.badge.invalid { background: #d73a49; color: #fff; }
#top-bar button { background: #444d56; color: #e1e4e8; border-color: #586069; }
#top-bar button:hover { background: #586069; }
#status-msg { padding: 4px 12px; font-weight: 600; }
#status-msg.error { color: #d73a49; }
#status-msg.ok { color: #28a745; }

#main { display: flex; height: calc(100vh - 48px); }
#nav-panel { width: 220px; background: #fff; border-right: 1px solid #ddd;
             padding: 12px; overflow-y: auto; flex-shrink: 0; }
#center-panel { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
#controls-panel { padding: 12px; overflow-y: auto; background: #fff; border-bottom: 1px solid #ddd; }
#editor-panel { padding: 12px; overflow-y: auto; flex: 1; background: #fafafa; }
#review-panel { display: none; padding: 12px; background: #fffbe6; border-bottom: 1px solid #ddd;
                max-height: 50vh; overflow-y: auto; }

#nav-panel h3 { font-size: 13px; color: #586069; margin-bottom: 6px; margin-top: 12px;
                 text-transform: uppercase; letter-spacing: 0.5px; }
#nav-panel h3:first-child { margin-top: 0; }
.nav-list { list-style: none; }
.nav-item { padding: 4px 8px; cursor: pointer; border-radius: 3px; font-size: 13px; }
.nav-item:hover { background: #f0f0f0; }
.nav-item.selected { background: #0366d6; color: #fff; }
.nav-actions { display: flex; gap: 4px; margin: 6px 0; flex-wrap: wrap; }

.button-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; margin-bottom: 12px; }
.encoder-row { display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; margin-bottom: 12px; }
.ctrl-cell { padding: 8px; border: 1px solid #ddd; border-radius: 4px; cursor: pointer;
             text-align: center; font-size: 13px; }
.ctrl-cell:hover { border-color: #0366d6; background: #f0f7ff; }
.ctrl-mapped { background: #e8f4e8; border-color: #a0d0a0; }
.ctrl-unmapped { background: #fafafa; color: #999; }
.ctrl-name { display: block; font-weight: 600; font-size: 15px; }
.ctrl-action { display: block; font-size: 11px; color: #666; margin-top: 2px; }

#editor-panel h3 { margin-bottom: 8px; }
.action-type-picker { display: flex; flex-wrap: wrap; gap: 4px; margin: 8px 0; }
.at-btn { padding: 3px 8px; font-size: 12px; }
.at-btn.selected { background: #0366d6; color: #fff; border-color: #0366d6; }
#action-form { margin: 10px 0; }
#action-form label { display: block; margin-top: 8px; font-weight: 600; font-size: 13px; }
#action-form input, #action-form textarea, #action-form select {
  width: 100%; padding: 4px 6px; margin-top: 2px; border: 1px solid #ccc;
  border-radius: 3px; font-size: 13px; font-family: monospace; }
#action-form textarea { width: 100%; max-width: 500px; }
.hint { font-size: 11px; color: #888; margin-top: 2px; }
.action-actions { margin-top: 12px; }

.macro-steps { margin: 8px 0; }
.macro-step { display: flex; align-items: center; gap: 8px; padding: 4px;
              border-bottom: 1px solid #eee; font-size: 13px; }
.step-num { width: 24px; text-align: right; font-weight: 600; color: #888; }
.step-type { font-family: monospace; font-weight: 600; min-width: 100px; }
.step-summary { flex: 1; font-size: 12px; color: #666; overflow: hidden; text-overflow: ellipsis; }
.step-actions { display: flex; gap: 2px; }
.macro-add-step { margin-top: 10px; display: flex; gap: 6px; align-items: flex-end; }
.macro-add-step input { flex: 1; }
.macro-add-step input { flex: 1; }

/* Macro typed step editor — no inline styles */
.macro-new-step { border: 1px solid #ddd; padding: 8px; margin-top: 8px; }
.ms-fields-box { margin-top: 4px; }
.ms-add-btn { margin-top: 4px; }
.ms-json-toggle { font-size: 11px; }
.ms-json-area { display: none; margin-top: 4px; }
.ms-json-area.visible { display: block; }
.macro-step-item { cursor: pointer; display: flex; gap: 4px; align-items: center; }
.macro-step-del-btn { font-size: 10px; padding: 0 3px; }
.shutdown-msg { padding: 2em; text-align: center; }
.topbar-actions { margin-left: auto; display: flex; gap: 6px; }
.hidden { display: none; }

.diff-changes { margin: 8px 0; }
.diff-item { padding: 4px 8px; border-left: 3px solid #ccc; margin-bottom: 4px; font-size: 13px; }
.diff-item.risk-high { border-left-color: #d73a49; }
.diff-item.risk-medium { border-left-color: #f0ad4e; }
.diff-item.risk-low { border-left-color: #28a745; }
.diff-kind { font-weight: 600; text-transform: uppercase; font-size: 11px; }
.diff-path { font-family: monospace; font-size: 12px; }
.risk-badge { padding: 1px 4px; border-radius: 2px; font-size: 10px; font-weight: 600;
              background: #eee; text-transform: uppercase; }
.unified-diff { padding: 8px; font-size: 12px; font-family: monospace; background: #fff;
                border: 1px solid #ddd; border-radius: 3px; overflow-x: auto; max-height: 300px; }

.diag { padding: 4px 8px; margin-bottom: 2px; font-size: 13px; }
.diag-error { background: #ffe0e0; color: #a00; border-left: 3px solid #d73a49; }
.diag-warn { background: #fff8e0; color: #840; border-left: 3px solid #f0ad4e; }

:focus { outline: 2px solid #0366d6; outline-offset: 1px; }
button:focus, input:focus, textarea:focus, select:focus { outline: 2px solid #0366d6; outline-offset: 1px; }
"""

# ═══════════════════════════════════════════════════════════════════
#  JavaScript  (served as /s/<TOKEN>/assets/editor.js)
# ═══════════════════════════════════════════════════════════════════

EDITOR_JS = r"""
const API_BASE = window.location.pathname.replace(/\/+$/, '') + '/api/v1';
var STATE = null;
var ACTIVE_PROFILE = null;
var ACTIVE_LAYER = null;
var EDITING_CONTROL = null;

function apiGet(path) {
  return fetch(API_BASE + path, { credentials: 'same-origin' })
    .then(r => { if (!r.ok) throw new Error(r.status); return r.json(); });
}

function apiPost(path, body) {
  return fetch(API_BASE + path, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body), credentials: 'same-origin'
  }).then(r => { if (!r.ok) throw new Error(r.status); return r.json(); });
}

function showStatus(msg, cls) {
  var el = document.getElementById('status-msg');
  el.textContent = msg; el.className = cls || '';
  setTimeout(function() { el.textContent = ''; el.className = ''; }, 4000);
}
function showError(msg) { showStatus(msg, 'error'); }
function showOk(msg) { showStatus(msg, 'ok'); }

function esc(s) {
  if (typeof s !== 'string') return s;
  return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}

function loadState() {
  apiGet('/state').then(function(data) {
    STATE = data.config || data;
    if (STATE.profiles && STATE.profiles.length > 0) {
      ACTIVE_PROFILE = STATE.profiles.find(function(p) { return p.is_default; }) || STATE.profiles[0];
      if (ACTIVE_PROFILE.layers && ACTIVE_PROFILE.layers.length > 0) {
        ACTIVE_LAYER = ACTIVE_PROFILE.layers.find(function(l) { return l.is_initial; }) || ACTIVE_PROFILE.layers[0];
      }
    }
    render();
  }).catch(function(e) { showError('Failed to load state: ' + e.message); });
}

function render() { renderTopBar(); renderNav(); renderControls(); renderEditor(); updateSaveButton(); }

function renderTopBar() {
  var s = STATE;
  document.getElementById('tb-source').textContent = s.source ? s.source.split('/').pop() : '';
  document.getElementById('tb-target').textContent = s.target ? s.target.split('/').pop() : '';
  document.getElementById('tb-base-sha').textContent = (s.base_sha256 || '').substring(0, 16);
  document.getElementById('tb-draft-sha').textContent = (s.draft_sha256 || '').substring(0, 16);
  document.getElementById('tb-dirty').textContent = s.dirty ? 'MODIFIED' : 'Clean';
  document.getElementById('tb-dirty').className = s.dirty ? 'badge modified' : 'badge clean';
  document.getElementById('tb-mutations').textContent = s.mutation_count || 0;
  var v = STATE.validation || {};
  document.getElementById('tb-valid').textContent = v.valid ? 'VALID' : 'ERRORS';
  document.getElementById('tb-valid').className = v.valid ? 'badge valid' : 'badge invalid';
}

function renderNav() {
  var el = document.getElementById('nav-content');
  var profiles = STATE.profiles || [];
  var h = '<h3>Profiles</h3><ul class="nav-list">';
  for (var i = 0; i < profiles.length; i++) {
    var p = profiles[i];
    var sel = ACTIVE_PROFILE && ACTIVE_PROFILE.profile_id === p.profile_id ? ' selected' : '';
    var def = p.is_default ? ' (default)' : '';
    h += '<li class="nav-item' + sel + '" data-action="select-profile" data-pid="' + esc(p.profile_id) + '">' + esc(p.profile_id) + def + '</li>';
  }
  h += '</ul>';
  h += '<div class="nav-actions">';
  h += '<button data-action="add-profile">+ Profile</button>';
  h += '<button data-action="rename-profile">&#9998;</button>';
  h += '<button data-action="remove-profile">&#10005;</button>';
  h += '<button data-action="set-default-profile">&#9733;</button>';
  h += '</div>';
  if (ACTIVE_PROFILE && ACTIVE_PROFILE.layers) {
    h += '<h3>Layers</h3><ul class="nav-list">';
    for (var j = 0; j < ACTIVE_PROFILE.layers.length; j++) {
      var l = ACTIVE_PROFILE.layers[j];
      var lsel = ACTIVE_LAYER && ACTIVE_LAYER.layer_id === l.layer_id ? ' selected' : '';
      var init = l.is_initial ? ' (initial)' : '';
      h += '<li class="nav-item' + lsel + '" data-action="select-layer" data-lid="' + esc(l.layer_id) + '">' + esc(l.layer_id) + init + '</li>';
    }
    h += '</ul>';
    h += '<div class="nav-actions">';
    h += '<button data-action="add-layer">+ Layer</button>';
    h += '<button data-action="rename-layer">&#9998;</button>';
    h += '<button data-action="remove-layer">&#10005;</button>';
    h += '<button data-action="set-initial-layer">&#9679;</button>';
    h += '</div>';
  }
  el.innerHTML = h;
}

function selectProfile(pid) {
  ACTIVE_PROFILE = STATE.profiles.find(function(p) { return p.profile_id === pid; });
  if (ACTIVE_PROFILE && ACTIVE_PROFILE.layers && ACTIVE_PROFILE.layers.length > 0) {
    ACTIVE_LAYER = ACTIVE_PROFILE.layers.find(function(l) { return l.is_initial; }) || ACTIVE_PROFILE.layers[0];
  } else { ACTIVE_LAYER = null; }
  render();
}
function selectLayer(lid) {
  if (!ACTIVE_PROFILE) return;
  ACTIVE_LAYER = ACTIVE_PROFILE.layers.find(function(l) { return l.layer_id === lid; });
  render();
}

function renderControls() {
  var el = document.getElementById('controls-grid');
  if (!ACTIVE_LAYER) { el.innerHTML = '<p>Select a layer to view controls.</p>'; return; }
  var ctrls = ACTIVE_LAYER.controls || {};
  var h = '<h3>Buttons</h3><div class="button-grid">';
  var btnNames = ['A1','A2','A3','A4','A5','A6','A7','A8','A9','A10','A11','A12'];
  for (var i = 0; i < btnNames.length; i++) {
    var name = btnNames[i];
    var spec = ctrls[name];
    var cls = spec ? 'ctrl-mapped' : 'ctrl-unmapped';
    var summary = spec ? (spec.type || '?') : 'unmapped';
    h += '<div class="ctrl-cell ' + cls + '" data-action="edit-control" data-ctrl="' + name + '">';
    h += '<span class="ctrl-name">' + name + '</span>';
    h += '<span class="ctrl-action">' + esc(summary) + '</span></div>';
  }
  h += '</div>';
  var groups = {A: ['AL','AP','AR'], B: ['BL','BP','BR'], C: ['CL','CP','CR'], D: ['DL','DP','DR']};
  var labels = ['Left', 'Press', 'Right'];
  for (var grp in groups) {
    h += '<h3>Encoder ' + grp + '</h3><div class="encoder-row">';
    for (var j = 0; j < 3; j++) {
      var ename = groups[grp][j];
      var espec = ctrls[ename];
      var ecls = espec ? 'ctrl-mapped' : 'ctrl-unmapped';
      var esum = espec ? (espec.type || '?') : 'unmapped';
      h += '<div class="ctrl-cell ' + ecls + '" data-action="edit-control" data-ctrl="' + ename + '">';
      h += '<span class="ctrl-name">' + ename + ' (' + labels[j] + ')</span>';
      h += '<span class="ctrl-action">' + esc(esum) + '</span></div>';
    }
    h += '</div>';
  }
  el.innerHTML = h;
}

function editControl(name) { EDITING_CONTROL = name; renderEditor(); }

function renderEditor() {
  var el = document.getElementById('editor-panel');
  if (!EDITING_CONTROL || !ACTIVE_LAYER) { el.innerHTML = '<p>Select a control to edit its action.</p>'; return; }
  var spec = ACTIVE_LAYER.controls[EDITING_CONTROL];
  var atype = spec ? spec.type : 'unmapped';
  var h = '<h3>Editing: ' + esc(EDITING_CONTROL) + '</h3>';
  h += '<p>Current: <strong>' + esc(atype) + '</strong></p>';
  h += '<div class="action-type-picker">';
  var types = ['noop','debug_log','hotkey','text','command','delay','macro','set_layer','next_layer','previous_layer','set_profile'];
  for (var i = 0; i < types.length; i++) {
    var t = types[i];
    var sel = t === atype ? ' selected' : '';
    h += '<button class="at-btn' + sel + '" data-action="set-action-type" data-atype="' + t + '">' + t + '</button>';
  }
  h += '</div>';
  h += '<div id="action-form">';
  if (atype === 'unmapped') {
    h += '<p>Select an action type above.</p>';
  } else {
    h += renderActionForm(atype, spec);
  }
  h += '</div>';
  if (spec) {
    h += '<div class="action-actions"><button data-action="clear-action" class="btn-danger">Clear Action</button></div>';
  }
  el.innerHTML = h;
}

function renderActionForm(type, spec) {
  var h = '';
  if (type === 'noop') { h += '<p>No operation.</p>'; }
  else if (type === 'debug_log') { h += '<label for="af-message">Message:</label><input id="af-message" value="' + esc(spec&&spec.message||'') + '" size="40">'; }
  else if (type === 'hotkey') { var keys = (spec&&spec.keys)?spec.keys.join('+'):''; h += '<label for="af-keys">Keys (e.g. CTRL+SHIFT+A):</label><input id="af-keys" value="' + esc(keys) + '" size="40"><p class="hint">Separate with +</p>'; }
  else if (type === 'text') { h += '<label for="af-value">Text:</label><textarea id="af-value" rows="3" cols="40">' + esc(spec&&spec.value||'') + '</textarea>'; }
  else if (type === 'command') {
    var argv = (spec&&spec.argv)?spec.argv.join('\n'):'';
    h += '<label for="af-argv">Arguments (one per line):</label><textarea id="af-argv" rows="3" cols="40">' + esc(argv) + '</textarea>';
    h += '<label for="af-timeout">Timeout (seconds):</label><input id="af-timeout" type="number" value="' + (spec&&spec.timeout_seconds||'') + '">';
    h += '<p class="hint">Executed only by daemon runtime, not by editor.</p>';
  }
  else if (type === 'delay') { h += '<label for="af-ms">Milliseconds:</label><input id="af-ms" type="number" min="0" value="' + (spec&&spec.milliseconds||0) + '"> ms'; }
  else if (type === 'macro') {
    var steps = (spec&&spec.steps) || [];
    h += '<div class="macro-steps">';
    for (var i = 0; i < steps.length; i++) {
      h += '<div class="macro-step">';
      h += '<span class="step-num">' + (i+1) + '</span>';
      h += '<span class="step-type">' + esc(steps[i].type) + '</span>';
      h += '<span class="step-summary">' + esc(JSON.stringify(steps[i]).substring(0,60)) + '</span>';
      h += '<div class="step-actions">';
      h += '<button data-action="macro-edit" data-idx="' + i + '">Edit</button>';
      h += '<button data-action="macro-add-before" data-idx="' + i + '">+Before</button>';
      h += '<button data-action="macro-add-after" data-idx="' + i + '">+After</button>';
      h += '<button data-action="macro-move-up" data-idx="' + i + '">&#8593;</button>';
      h += '<button data-action="macro-move-down" data-idx="' + i + '">&#8595;</button>';
      h += '<button data-action="macro-delete" data-idx="' + i + '">&#10005;</button>';
      h += '</div></div>';
    }
    h += '</div>';
    // Typed step adder
    h += '<div id="macro-new-step" class="macro-add-step" class="macro-new-step">';
    h += '<strong>New Step:</strong> ';
    h += '<select id="ms-type"><option value="">-- type --</option>';
    var mtypes = ['noop','debug_log','hotkey','text','command','delay','macro','set_layer','next_layer','previous_layer','set_profile'];
    for (var mi = 0; mi < mtypes.length; mi++) {
      h += '<option value="' + mtypes[mi] + '">' + mtypes[mi] + '</option>';
    }
    h += '</select>';
    h += '<div id="ms-fields" class="ms-fields-box"></div>';
    h += '<button data-action="macro-add-typed" class="ms-fields-box">Add Step</button>';
    h += ' <button data-action="macro-add-json-toggle" class="ms-json-toggle">Advanced (JSON)</button>';
    h += '<div id="ms-json-area" class="ms-json-area">';
    h += '<input id="ma-step-json" placeholder=\'{"type":"debug_log","message":"step"}\' size="50">';
    h += '<button data-action="macro-add-json">Add from JSON</button></div>';
    h += '</div>';
  }
  else if (type === 'set_layer' || type === 'set_profile') {
    var targetKey = type === 'set_layer' ? 'layer' : 'profile';
    var targets = type === 'set_layer' ? (ACTIVE_PROFILE?ACTIVE_PROFILE.layers.map(function(l){return l.layer_id}):[]) : (STATE.profiles?STATE.profiles.map(function(p){return p.profile_id}):[]);
    var cur = spec ? (spec[targetKey]||'') : '';
    h += '<label for="af-target">Target:</label><select id="af-target">';
    for (var j = 0; j < targets.length; j++) {
      var s = targets[j] === cur ? ' selected' : '';
      h += '<option value="' + esc(targets[j]) + '"' + s + '>' + esc(targets[j]) + '</option>';
    }
    h += '</select>';
  }
  else if (type === 'next_layer' || type === 'previous_layer') { h += '<p>Cycles to the ' + (type==='next_layer'?'next':'previous') + ' layer at runtime.</p>'; }
  h += '<br><button data-action="apply-action" data-atype="' + type + '" class="btn-primary">Apply Action</button>';
  return h;
}

// ── Event delegation on body ──
document.addEventListener('DOMContentLoaded', function() {
  document.addEventListener('change', function(e) { if (e.target && e.target.id === 'ms-type') renderMsFields(); });
  document.body.addEventListener('click', function(e) {
    var target = e.target;
    while (target && target !== document.body) {
      var action = target.getAttribute('data-action');
      if (action) {
        e.preventDefault();
        handleAction(action, target);
        return;
      }
      target = target.parentElement;
    }
  });
  loadState();
});

function handleAction(action, el) {
  switch (action) {
    case 'select-profile': selectProfile(el.getAttribute('data-pid')); break;
    case 'select-layer': selectLayer(el.getAttribute('data-lid')); break;
    case 'edit-control': editControl(el.getAttribute('data-ctrl')); break;
    case 'set-action-type': setActionType(el.getAttribute('data-atype')); break;
    case 'apply-action': saveAction(el.getAttribute('data-atype')); break;
    case 'clear-action': clearAction(); break;
    case 'add-profile': addProfile(); break;
    case 'rename-profile': renameProfile(); break;
    case 'remove-profile': removeProfile(); break;
    case 'set-default-profile': setDefaultProfile(); break;
    case 'add-layer': addLayer(); break;
    case 'rename-layer': renameLayer(); break;
    case 'remove-layer': removeLayer(); break;
    case 'set-initial-layer': setInitialLayer(); break;
    case 'macro-edit': editMacroStep(parseInt(el.getAttribute('data-idx'))); break;
    case 'macro-add-before': addBeforeMacroStep(parseInt(el.getAttribute('data-idx'))); break;
    case 'macro-add-after': addAfterMacroStep(parseInt(el.getAttribute('data-idx'))); break;
    case 'macro-move-up': moveMacroStep(parseInt(el.getAttribute('data-idx')), -1); break;
    case 'macro-move-down': moveMacroStep(parseInt(el.getAttribute('data-idx')), 1); break;
    case 'macro-delete': deleteMacroStep(parseInt(el.getAttribute('data-idx'))); break;
    case 'macro-add-typed': addMacroStep(); break;
    case 'macro-add-json': addMacroJsonStep(); break;
    case 'macro-add-json-toggle': toggleJsonArea(); break;
    case 'show-validate': showValidate(); break;
    case 'show-review': showReview(); break;
    case 'confirm-review': confirmReview(); break;
    case 'do-save': doSave(); break;
    case 'do-shutdown': doShutdown(); break;
  }
}

function setActionType(type) {
  if (!EDITING_CONTROL) return;
  var defaults = {
    noop: {type:'noop'}, debug_log: {type:'debug_log',message:''}, hotkey: {type:'hotkey',keys:[]},
    text: {type:'text',value:''}, command: {type:'command',argv:[''],timeout_seconds:30},
    delay: {type:'delay',milliseconds:100}, macro: {type:'macro',steps:[]},
    set_layer: {type:'set_layer',layer:ACTIVE_PROFILE&&ACTIVE_PROFILE.layers[0]?ACTIVE_PROFILE.layers[0].layer_id:'general'},
    next_layer: {type:'next_layer'}, previous_layer: {type:'previous_layer'},
    set_profile: {type:'set_profile',profile:STATE.profiles[0]?STATE.profiles[0].profile_id:''},
  };
  if (ACTIVE_LAYER) ACTIVE_LAYER.controls[EDITING_CONTROL] = defaults[type] || {type:type};
  renderEditor();
}

function saveAction(type) {
  if (!EDITING_CONTROL || !ACTIVE_PROFILE || !ACTIVE_LAYER) return;
  var spec = {type: type};
  if (type === 'debug_log') spec.message = document.getElementById('af-message').value;
  else if (type === 'hotkey') { var raw = document.getElementById('af-keys').value; spec.keys = raw.split('+').map(function(s){return s.trim()}).filter(Boolean); }
  else if (type === 'text') spec.value = document.getElementById('af-value').value;
  else if (type === 'command') {
    spec.argv = document.getElementById('af-argv').value.split('\n').filter(function(s){return s.trim()!==''});
    var to = parseInt(document.getElementById('af-timeout').value);
    if (!isNaN(to) && to > 0) spec.timeout_seconds = to;
  }
  else if (type === 'delay') spec.milliseconds = parseInt(document.getElementById('af-ms').value) || 100;
  else if (type === 'macro') { spec.steps = (ACTIVE_LAYER.controls[EDITING_CONTROL]&&ACTIVE_LAYER.controls[EDITING_CONTROL].steps)||[]; }
  else if (type === 'set_layer') spec.layer = document.getElementById('af-target').value;
  else if (type === 'set_profile') spec.profile = document.getElementById('af-target').value;
  apiPost('/control/set-action', {profile:ACTIVE_PROFILE.profile_id,layer:ACTIVE_LAYER.layer_id,control:EDITING_CONTROL,action_spec:spec})
    .then(function(data) {
      if (data.status === 'ok') {
        STATE = data;
        if (ACTIVE_PROFILE) ACTIVE_PROFILE = STATE.profiles.find(function(p){return p.profile_id===ACTIVE_PROFILE.profile_id});
        if (ACTIVE_PROFILE&&ACTIVE_LAYER) ACTIVE_LAYER = ACTIVE_PROFILE.layers.find(function(l){return l.layer_id===ACTIVE_LAYER.layer_id});
        showOk('Action saved'); render(); editControl(EDITING_CONTROL);
      } else showError(data.error?data.error.message:'Unknown error');
    }).catch(function(e){showError('Save failed: '+e.message)});
}

function clearAction() {
  if (!EDITING_CONTROL||!ACTIVE_PROFILE||!ACTIVE_LAYER) return;
  apiPost('/control/clear-action',{profile:ACTIVE_PROFILE.profile_id,layer:ACTIVE_LAYER.layer_id,control:EDITING_CONTROL})
    .then(function(data){
      if(data.status==='ok'){STATE=data;if(ACTIVE_PROFILE)ACTIVE_PROFILE=STATE.profiles.find(function(p){return p.profile_id===ACTIVE_PROFILE.profile_id});if(ACTIVE_PROFILE&&ACTIVE_LAYER)ACTIVE_LAYER=ACTIVE_PROFILE.layers.find(function(l){return l.layer_id===ACTIVE_LAYER.layer_id});showOk('Action cleared');EDITING_CONTROL=null;render();}else showError(data.error?data.error.message:'Unknown error');
    }).catch(function(e){showError('Clear failed: '+e.message)});
}

function addProfile() { var n=prompt('New profile ID:'); if(!n)return; apiPost('/profile/add',{profile_id:n}).then(function(d){if(d.status==='ok'){STATE=d;ACTIVE_PROFILE=STATE.profiles.find(function(p){return p.profile_id===n});render();}else showError(d.error.message);}).catch(function(e){showError(e.message)}); }
function renameProfile() { if(!ACTIVE_PROFILE)return; var n=prompt('New name:',ACTIVE_PROFILE.profile_id); if(!n||n===ACTIVE_PROFILE.profile_id)return; apiPost('/profile/rename',{old_profile_id:ACTIVE_PROFILE.profile_id,new_profile_id:n}).then(function(d){if(d.status==='ok'){STATE=d;ACTIVE_PROFILE=STATE.profiles.find(function(p){return p.profile_id===n});render();}else showError(d.error.message);}).catch(function(e){showError(e.message)}); }
function removeProfile() { if(!ACTIVE_PROFILE)return; if(!confirm('Delete profile?'))return; apiPost('/profile/remove',{profile_id:ACTIVE_PROFILE.profile_id}).then(function(d){if(d.status==='ok'){STATE=d;ACTIVE_PROFILE=STATE.profiles.length>0?(STATE.profiles.find(function(p){return p.is_default})||STATE.profiles[0]):null;render();}else showError(d.error.message);}).catch(function(e){showError(e.message)}); }
function setDefaultProfile() { if(!ACTIVE_PROFILE)return; apiPost('/profile/set-default',{profile_id:ACTIVE_PROFILE.profile_id}).then(function(d){if(d.status==='ok'){STATE=d;render();}else showError(d.error.message);}).catch(function(e){showError(e.message)}); }
function addLayer() { if(!ACTIVE_PROFILE)return; var n=prompt('Layer ID:','layer_1'); if(!n)return; apiPost('/layer/add',{profile:ACTIVE_PROFILE.profile_id,layer_id:n}).then(function(d){if(d.status==='ok'){STATE=d;ACTIVE_PROFILE=STATE.profiles.find(function(p){return p.profile_id===ACTIVE_PROFILE.profile_id});ACTIVE_LAYER=ACTIVE_PROFILE.layers.find(function(l){return l.layer_id===n});render();}else showError(d.error.message);}).catch(function(e){showError(e.message)}); }
function renameLayer() { if(!ACTIVE_PROFILE||!ACTIVE_LAYER)return; var n=prompt('New name:',ACTIVE_LAYER.layer_id); if(!n||n===ACTIVE_LAYER.layer_id)return; apiPost('/layer/rename',{profile:ACTIVE_PROFILE.profile_id,old_layer_id:ACTIVE_LAYER.layer_id,new_layer_id:n}).then(function(d){if(d.status==='ok'){STATE=d;ACTIVE_PROFILE=STATE.profiles.find(function(p){return p.profile_id===ACTIVE_PROFILE.profile_id});ACTIVE_LAYER=ACTIVE_PROFILE.layers.find(function(l){return l.layer_id===n});render();}else showError(d.error.message);}).catch(function(e){showError(e.message)}); }
function removeLayer() { if(!ACTIVE_PROFILE||!ACTIVE_LAYER)return; if(!confirm('Delete layer?'))return; apiPost('/layer/remove',{profile:ACTIVE_PROFILE.profile_id,layer_id:ACTIVE_LAYER.layer_id}).then(function(d){if(d.status==='ok'){STATE=d;ACTIVE_PROFILE=STATE.profiles.find(function(p){return p.profile_id===ACTIVE_PROFILE.profile_id});ACTIVE_LAYER=ACTIVE_PROFILE.layers.length>0?ACTIVE_PROFILE.layers[0]:null;render();}else showError(d.error.message);}).catch(function(e){showError(e.message)}); }
function setInitialLayer() { if(!ACTIVE_LAYER)return; apiPost('/layer/set-initial',{layer_id:ACTIVE_LAYER.layer_id}).then(function(d){if(d.status==='ok'){STATE=d;render();}else showError(d.error.message);}).catch(function(e){showError(e.message)}); }

var MACRO_EDIT_IDX = -1;

function renderMsFields() {
  var sel = document.getElementById('ms-type');
  if (!sel) return;
  var t = sel.value;
  var el = document.getElementById('ms-fields');
  if (!el) return;
  var h = '';
  if (t === 'noop' || t === 'next_layer' || t === 'previous_layer') {
    h += '<p>No additional fields needed.</p>';
  } else if (t === 'debug_log') {
    h += '<label>Message: <input id="msf-message" size="40"></label>';
  } else if (t === 'hotkey') {
    h += '<div id="msf-keys"><label>Key: <input id="msf-key-input" size="15"></label>';
    h += '<button id="msf-key-add" type="button">Add</button>';
    h += '<ul id="msf-key-list"></ul></div>';
    h += '<p class="hint">Add keys one at a time (e.g. CTRL, SHIFT, A)</p>';
  } else if (t === 'text') {
    h += '<label>Text: <textarea id="msf-value" rows="2" cols="40"></textarea></label>';
  } else if (t === 'command') {
    h += '<div id="msf-argv"><label>Arg: <input id="msf-arg-input" size="20"></label>';
    h += '<button id="msf-arg-add" type="button">Add</button>';
    h += '<ul id="msf-arg-list"></ul></div>';
    h += '<label>Timeout (s): <input id="msf-timeout" type="number" value="30" size="5"></label>';
    h += '<p class="hint">One arg at a time. Executed by daemon only.</p>';
  } else if (t === 'delay') {
    h += '<label>Milliseconds: <input id="msf-ms" type="number" min="0" value="100" size="10"> ms</label>';
  } else if (t === 'macro') {
    h += '<p>Nested macro — edit after adding.</p>';
  } else if (t === 'set_layer') {
    h += '<label>Target Layer: <select id="msf-layer">';
    var layers = ACTIVE_PROFILE ? ACTIVE_PROFILE.layers.map(function(l){return l.layer_id}) : [];
    for (var lj = 0; lj < layers.length; lj++) {
      h += '<option value="' + esc(layers[lj]) + '">' + esc(layers[lj]) + '</option>';
    }
    h += '</select></label>';
  } else if (t === 'set_profile') {
    h += '<label>Target Profile: <select id="msf-profile">';
    var profs = STATE.profiles ? STATE.profiles.map(function(p){return p.profile_id}) : [];
    for (var pj = 0; pj < profs.length; pj++) {
      h += '<option value="' + esc(profs[pj]) + '">' + esc(profs[pj]) + '</option>';
    }
    h += '</select></label>';
  }
  el.innerHTML = h;
  // Wire dynamic add buttons
  var ka = document.getElementById('msf-key-add');
  if (ka) ka.onclick = function() {
    var inp = document.getElementById('msf-key-input');
    if (!inp || !inp.value.trim()) return;
    var li = document.createElement('li');
    li.textContent = inp.value.trim();
    li.className = 'macro-step-item';
    var del = document.createElement('button');
    del.textContent = '×'; del.className = 'macro-step-del-btn';
    del.onclick = function() { li.remove(); };
    li.appendChild(del);
    var ul = document.getElementById('msf-key-list');
    if (ul) ul.appendChild(li);
    inp.value = '';
  };
  var aa = document.getElementById('msf-arg-add');
  if (aa) aa.onclick = function() {
    var inp = document.getElementById('msf-arg-input');
    if (!inp || !inp.value.trim()) return;
    var li = document.createElement('li');
    li.textContent = inp.value.trim();
    li.className = 'macro-step-item';
    var del = document.createElement('button');
    del.textContent = '×'; del.className = 'macro-step-del-btn';
    del.onclick = function() { li.remove(); };
    li.appendChild(del);
    var ul = document.getElementById('msf-arg-list');
    if (ul) ul.appendChild(li);
    inp.value = '';
  };
}

function collectMsSpec() {
  var sel = document.getElementById('ms-type');
  if (!sel) return null;
  var t = sel.value;
  if (!t) { showError('Select a step type'); return null; }
  var spec = { type: t };
  if (t === 'debug_log') spec.message = document.getElementById('msf-message') ? document.getElementById('msf-message').value : '';
  else if (t === 'hotkey') {
    var items = document.querySelectorAll('#msf-key-list li');
    spec.keys = [];
    items.forEach(function(li) { spec.keys.push(li.textContent.replace(/×$/, '').trim()); });
    if (spec.keys.length === 0) { showError('Hotkey requires at least one key'); return null; }
  }
  else if (t === 'text') spec.value = document.getElementById('msf-value') ? document.getElementById('msf-value').value : '';
  else if (t === 'command') {
    var args = document.querySelectorAll('#msf-arg-list li');
    spec.argv = [];
    args.forEach(function(li) { spec.argv.push(li.textContent.replace(/×$/, '').trim()); });
    if (spec.argv.length === 0) { showError('Command requires at least one argument'); return null; }
    var to = parseInt(document.getElementById('msf-timeout') ? document.getElementById('msf-timeout').value : 0);
    if (!isNaN(to) && to > 0) spec.timeout_seconds = to;
  }
  else if (t === 'delay') spec.milliseconds = parseInt(document.getElementById('msf-ms') ? document.getElementById('msf-ms').value : 100) || 100;
  else if (t === 'set_layer') spec.layer = document.getElementById('msf-layer') ? document.getElementById('msf-layer').value : '';
  else if (t === 'set_profile') spec.profile = document.getElementById('msf-profile') ? document.getElementById('msf-profile').value : '';
  return spec;
}

function insertMacroStep(idx, spec) {
  if (!ACTIVE_LAYER || !EDITING_CONTROL) return;
  var cur = ACTIVE_LAYER.controls[EDITING_CONTROL];
  var steps = (cur && cur.steps) ? cur.steps.slice() : [];
  if (idx < 0) idx = 0;
  if (idx > steps.length) idx = steps.length;
  steps.splice(idx, 0, spec);
  ACTIVE_LAYER.controls[EDITING_CONTROL] = { type: 'macro', steps: steps };
  renderEditor();
}

function addMacroStep() {
  var spec = collectMsSpec();
  if (!spec) return;
  insertMacroStep((ACTIVE_LAYER.controls[EDITING_CONTROL]&&ACTIVE_LAYER.controls[EDITING_CONTROL].steps||[]).length, spec);
}

function editMacroStep(idx) {
  var cur = ACTIVE_LAYER.controls[EDITING_CONTROL];
  if (!cur || !cur.steps) return;
  var old = cur.steps[idx];
  var sel = document.getElementById('ms-type');
  if (sel) sel.value = old.type;
  renderMsFields();
  // Pre-fill known fields
  setTimeout(function() {
    if (old.type==='debug_log'&&old.message) { var m=document.getElementById('msf-message'); if(m)m.value=old.message; }
    else if (old.type==='hotkey'&&old.keys) { var ul=document.getElementById('msf-key-list'); if(ul){ul.innerHTML='';old.keys.forEach(function(k){var li=document.createElement('li');li.textContent=k+' ';var b=document.createElement('button');b.textContent='×';b.className='macro-step-del-btn';b.onclick=function(){li.remove()};li.appendChild(b);ul.appendChild(li)});} }
    else if (old.type==='text'&&old.value) { var v=document.getElementById('msf-value'); if(v)v.value=old.value; }
    else if (old.type==='command'&&old.argv) { var ul2=document.getElementById('msf-arg-list'); if(ul2){ul2.innerHTML='';old.argv.forEach(function(a){var li=document.createElement('li');li.textContent=a+' ';var b=document.createElement('button');b.textContent='×';b.className='macro-step-del-btn';b.onclick=function(){li.remove()};li.appendChild(b);ul2.appendChild(li)});} if(old.timeout_seconds){var ti=document.getElementById('msf-timeout');if(ti)ti.value=old.timeout_seconds;} }
    else if (old.type==='delay'&&old.milliseconds) { var ms=document.getElementById('msf-ms'); if(ms)ms.value=old.milliseconds; }
    else if (old.type==='set_layer'&&old.layer) { var sl=document.getElementById('msf-layer'); if(sl)sl.value=old.layer; }
    else if (old.type==='set_profile'&&old.profile) { var sp=document.getElementById('msf-profile'); if(sp)sp.value=old.profile; }
  }, 50);
  showOk('Editing step ' + (idx+1) + '. Change fields and re-add.');
  // Select existing in typed form — user clicks Add Step to replace
  var cur2 = ACTIVE_LAYER.controls[EDITING_CONTROL];
  var steps2 = (cur2 && cur2.steps) ? cur2.steps.slice() : [];
  steps2.splice(idx, 1);
  ACTIVE_LAYER.controls[EDITING_CONTROL] = { type: 'macro', steps: steps2 };
  // The old step is removed; user adds the replacement
}

function addBeforeMacroStep(idx) {
  var spec = collectMsSpec();
  if (!spec) return;
  insertMacroStep(idx, spec);
}
function addAfterMacroStep(idx) {
  var spec = collectMsSpec();
  if (!spec) return;
  insertMacroStep(idx + 1, spec);
}
function toggleJsonArea() {
  var el = document.getElementById('ms-json-area');
  if (el) el.classList.toggle('visible');
}
function addMacroJsonStep() {
  var raw = document.getElementById('ma-step-json').value;
  var stepSpec;
  try { stepSpec = JSON.parse(raw); } catch(e) { showError('Invalid JSON'); return; }
  if (!stepSpec.type) { showError('Missing type'); return; }
  insertMacroStep((ACTIVE_LAYER.controls[EDITING_CONTROL]&&ACTIVE_LAYER.controls[EDITING_CONTROL].steps||[]).length, stepSpec);
}
function moveMacroStep(idx, dir) {
  if (!ACTIVE_LAYER || !EDITING_CONTROL) return;
  var cur = ACTIVE_LAYER.controls[EDITING_CONTROL]; if (!cur || !cur.steps) return;
  var steps = cur.steps.slice(); var ni = idx + dir;
  if (ni < 0 || ni >= steps.length) return;
  var tmp = steps[idx]; steps[idx] = steps[ni]; steps[ni] = tmp;
  ACTIVE_LAYER.controls[EDITING_CONTROL] = { type: 'macro', steps: steps };
  renderEditor();
}
function deleteMacroStep(idx) {
  if (!ACTIVE_LAYER || !EDITING_CONTROL) return;
  var cur = ACTIVE_LAYER.controls[EDITING_CONTROL]; if (!cur || !cur.steps) return;
  var steps = cur.steps.slice(); steps.splice(idx, 1);
  ACTIVE_LAYER.controls[EDITING_CONTROL] = { type: 'macro', steps: steps };
  renderEditor();
}

function showReview() {
  Promise.all([apiGet('/diff'), apiGet('/diff/unified')]).then(function(results) {
    var d = results[0], u = results[1];
    var el = document.getElementById('review-panel');
    var h = '<h3>Review Changes</h3>';
    h += '<p>Changes: <strong>' + (d.change_count||0) + '</strong> | Risk: <strong>' + esc(d.risk_summary||'LOW') + '</strong></p>';
    if (d.changes && d.changes.length > 0) {
      h += '<div class="diff-changes">';
      for (var i = 0; i < d.changes.length; i++) {
        var c = d.changes[i];
        h += '<div class="diff-item risk-' + (c.risk||'LOW').toLowerCase() + '">';
        h += '<span class="diff-kind">' + esc(c.kind) + '</span> ';
        h += '<span class="diff-path">' + esc(c.path) + '</span>: ';
        h += '<span class="diff-before">' + esc(c.before) + '</span> → ';
        h += '<span class="diff-after">' + esc(c.after) + '</span>';
        h += ' <span class="risk-badge">' + esc(c.risk) + '</span>';
        h += '</div>';
      }
      h += '</div>';
    }
    if (u.unified_diff) { h += '<h4>Unified Diff</h4><pre class="unified-diff">' + esc(u.unified_diff) + '</pre>'; }
    h += '<button data-action="confirm-review" class="btn-primary">Review Complete</button>';
    el.innerHTML = h; el.classList.remove('hidden');
  }).catch(function(e) { showError('Review failed: ' + e.message); });
}
function confirmReview() {
  document.getElementById('review-panel').classList.add('hidden');
  showOk('Review confirmed.');
  apiGet('/validate').then(function(d){ STATE = d.status==='ok'?d:STATE; render(); });
}
function showValidate() {
  apiGet('/validate').then(function(d) {
    STATE = d.status==='ok'?d:STATE;
    var v = STATE.validation || {};
    var el = document.getElementById('review-panel');
    var h = '<h3>Validation</h3><p>Valid: <strong>' + (v.valid?'YES':'NO') + '</strong></p>';
    var errs = v.errors||[], warns = v.warnings||[];
    if (errs.length>0) { h+='<h4>Errors ('+errs.length+')</h4>'; for(var i=0;i<errs.length;i++) h+='<div class="diag diag-error">'+esc(errs[i].path||'')+': '+esc(errs[i].message)+'</div>'; }
    if (warns.length>0) { h+='<h4>Warnings ('+warns.length+')</h4>'; for(var j=0;j<warns.length;j++) h+='<div class="diag diag-warn">'+esc(warns[j].path||'')+': '+esc(warns[j].message)+'</div>'; }
    if (errs.length===0&&warns.length===0) h+='<p class="ok">No errors or warnings.</p>';
    el.innerHTML=h; el.classList.remove('hidden');
  }).catch(function(e){showError('Validate failed: '+e.message)});
}

function updateSaveButton() {
  var s = STATE, v = s.validation||{};
  var canSave = s.dirty && v.valid;
  var btn = document.getElementById('btn-save');
  if (btn) { btn.disabled = !canSave; }
}

function doSave() {
  var target = STATE.target||'';
  if (!confirm('Save to ' + target + '?\\nSave does not reload daemon.')) return;
  apiPost('/save',{}).then(function(d){
    if(d.status==='ok'){STATE.dirty=false;STATE.mutation_count=0;showOk('Saved!');loadState();}else showError(d.error?d.error.message:'Save failed');
  }).catch(function(e){showError('Save failed: '+e.message)});
}

function doShutdown() {
  if (!confirm('Close the editor?')) return;
  apiPost('/shutdown',{}).catch(function(){});
  document.body.innerHTML = '<div class="shutdown-msg"><h2>Editor Closed</h2><p>You may close this tab.</p></div>';
}
"""

# ═══════════════════════════════════════════════════════════════════
#  HTML  (no inline CSS, no inline JS, no inline event handlers)
# ═══════════════════════════════════════════════════════════════════

def render_editor_page() -> str:
    """Return the HTML page that loads CSS and JS as external resources."""
    return """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>YYR4 Configuration Editor</title>
<link rel="stylesheet" href="assets/editor.css">
</head>
<body>

<div id="top-bar">
  <span class="logo">YYR4 Editor</span>
  <span>Source: <strong id="tb-source">-</strong></span>
  <span>Target: <strong id="tb-target">-</strong></span>
  <span>Base SHA: <code id="tb-base-sha">-</code></span>
  <span>Draft SHA: <code id="tb-draft-sha">-</code></span>
  <span id="tb-dirty" class="badge clean">Clean</span>
  <span id="tb-valid" class="badge valid">-</span>
  <span>Mutations: <strong id="tb-mutations">0</strong></span>
  <span id="status-msg"></span>
  <span class="topbar-actions">
    <button data-action="show-validate">Validate</button>
    <button data-action="show-review">Review</button>
    <button id="btn-save" data-action="do-save" disabled>Save</button>
    <button data-action="do-shutdown" class="btn-danger">Shutdown</button>
  </span>
</div>

<div id="main">
  <div id="nav-panel">
    <div id="nav-content"></div>
  </div>
  <div id="center-panel">
    <div id="review-panel" class="hidden"></div>
    <div id="controls-panel">
      <div id="controls-grid"></div>
    </div>
    <div id="editor-panel">
      <p>Select a control to edit its action.</p>
    </div>
  </div>
</div>

<script defer src="assets/editor.js"></script>
</body>
</html>"""
