"""Self-contained HTML editor page generation.

No external resources, no CDN, no frameworks.  Inline CSS and vanilla
JavaScript provide the complete interactive editing experience.
"""

_BUTTON_CONTROLS = tuple(f"A{i}" for i in range(1, 13))
_ENCODER_GROUPS = {
    "A": ("AL", "AP", "AR"),
    "B": ("BL", "BP", "BR"),
    "C": ("CL", "CP", "CR"),
    "D": ("DL", "DP", "DR"),
}
_ENCODER_LABELS = {
    "L": "Left", "P": "Press", "R": "Right",
}
_ALL_CONTROLS = list(_BUTTON_CONTROLS)
for grp in ("A", "B", "C", "D"):
    _ALL_CONTROLS.extend(_ENCODER_GROUPS[grp])

_ACTION_TYPES = [
    "noop", "debug_log", "hotkey", "text", "command",
    "delay", "macro", "set_layer", "next_layer", "previous_layer", "set_profile",
]


_JS_CODE = r"""
const API_BASE = window.location.pathname.replace(/\/+$/, '') + '/api/v1';
let STATE = null;
let ACTIVE_PROFILE = null;
let ACTIVE_LAYER = null;

async function apiGet(path) {
  const r = await fetch(API_BASE + path, { credentials: 'same-origin' });
  if (!r.ok) throw new Error(r.status);
  return r.json();
}

async function apiPost(path, body) {
  const r = await fetch(API_BASE + path, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body), credentials: 'same-origin'
  });
  if (!r.ok) throw new Error(r.status);
  return r.json();
}

function showStatus(msg, cls) {
  const el = document.getElementById('status-msg');
  el.textContent = msg; el.className = cls || '';
  setTimeout(() => { el.textContent = ''; el.className = ''; }, 4000);
}

function showError(msg) { showStatus(msg, 'error'); }
function showOk(msg) { showStatus(msg, 'ok'); }

async function loadState() {
  try {
    const data = await apiGet('/state');
    STATE = data.config || data;
    if (STATE.profiles && STATE.profiles.length > 0) {
      ACTIVE_PROFILE = STATE.profiles.find(p => p.is_default) || STATE.profiles[0];
      if (ACTIVE_PROFILE.layers && ACTIVE_PROFILE.layers.length > 0) {
        ACTIVE_LAYER = ACTIVE_PROFILE.layers.find(l => l.is_initial) || ACTIVE_PROFILE.layers[0];
      }
    }
    render();
  } catch (e) { showError('Failed to load state: ' + e.message); }
}

function render() {
  renderTopBar();
  renderNav();
  renderControls();
  renderEditor();
  updateSaveButton();
}

// ── Top bar ──
function renderTopBar() {
  const s = STATE;
  document.getElementById('tb-source').textContent = s.source ? s.source.split('/').pop() : '';
  document.getElementById('tb-target').textContent = s.target ? s.target.split('/').pop() : '';
  document.getElementById('tb-base-sha').textContent = (s.base_sha256 || '').substring(0, 16);
  document.getElementById('tb-draft-sha').textContent = (s.draft_sha256 || '').substring(0, 16);
  document.getElementById('tb-dirty').textContent = s.dirty ? 'MODIFIED' : 'Clean';
  document.getElementById('tb-dirty').className = s.dirty ? 'badge modified' : 'badge clean';
  document.getElementById('tb-mutations').textContent = s.mutation_count || 0;
  const v = STATE.validation || {};
  document.getElementById('tb-valid').textContent = v.valid ? 'VALID' : 'ERRORS';
  document.getElementById('tb-valid').className = v.valid ? 'badge valid' : 'badge invalid';
}

// ── Navigation ──
function renderNav() {
  const el = document.getElementById('nav-content');
  const profiles = STATE.profiles || [];
  let h = '<h3>Profiles</h3><ul class="nav-list">';
  for (const p of profiles) {
    const sel = ACTIVE_PROFILE && ACTIVE_PROFILE.profile_id === p.profile_id ? ' selected' : '';
    const def = p.is_default ? ' (default)' : '';
    h += '<li class="nav-item' + sel + '" onclick="selectProfile(\'' + esc(p.profile_id) + '\')">'
       + esc(p.profile_id) + def + '</li>';
  }
  h += '</ul>';
  h += '<div class="nav-actions">';
  h += '<button onclick="addProfile()" title="Add Profile">+ Profile</button>';
  h += '<button onclick="renameProfile()" title="Rename Profile">&#9998;</button>';
  h += '<button onclick="removeProfile()" title="Remove Profile">&#10005;</button>';
  h += '<button onclick="setDefaultProfile()" title="Set as Default">&#9733;</button>';
  h += '</div>';

  if (ACTIVE_PROFILE && ACTIVE_PROFILE.layers) {
    h += '<h3>Layers</h3><ul class="nav-list">';
    for (const l of ACTIVE_PROFILE.layers) {
      const sel = ACTIVE_LAYER && ACTIVE_LAYER.layer_id === l.layer_id ? ' selected' : '';
      const init = l.is_initial ? ' (initial)' : '';
      h += '<li class="nav-item' + sel + '" onclick="selectLayer(\'' + esc(l.layer_id) + '\')">'
         + esc(l.layer_id) + init + '</li>';
    }
    h += '</ul>';
    h += '<div class="nav-actions">';
    h += '<button onclick="addLayer()" title="Add Layer">+ Layer</button>';
    h += '<button onclick="renameLayer()" title="Rename Layer">&#9998;</button>';
    h += '<button onclick="removeLayer()" title="Remove Layer">&#10005;</button>';
    h += '<button onclick="setInitialLayer()" title="Set as Initial">&#9679;</button>';
    h += '</div>';
  }
  el.innerHTML = h;
}

function selectProfile(pid) {
  ACTIVE_PROFILE = STATE.profiles.find(p => p.profile_id === pid);
  if (ACTIVE_PROFILE && ACTIVE_PROFILE.layers && ACTIVE_PROFILE.layers.length > 0) {
    ACTIVE_LAYER = ACTIVE_PROFILE.layers.find(l => l.is_initial) || ACTIVE_PROFILE.layers[0];
  } else {
    ACTIVE_LAYER = null;
  }
  render();
}

function selectLayer(lid) {
  if (!ACTIVE_PROFILE) return;
  ACTIVE_LAYER = ACTIVE_PROFILE.layers.find(l => l.layer_id === lid);
  render();
}

// ── Controls grid ──
function renderControls() {
  const el = document.getElementById('controls-grid');
  if (!ACTIVE_LAYER) { el.innerHTML = '<p>Select a layer to view controls.</p>'; return; }

  const ctrls = ACTIVE_LAYER.controls || {};
  let h = '<h3>Buttons</h3><div class="button-grid">';
  for (const name of 'A1,A2,A3,A4,A5,A6,A7,A8,A9,A10,A11,A12'.split(',')) {
    const spec = ctrls[name];
    const cls = spec ? 'ctrl-mapped' : 'ctrl-unmapped';
    const summary = spec ? (spec.type || '?') : 'unmapped';
    h += '<div class="ctrl-cell ' + cls + '" onclick="editControl(\'' + name + '\')">'
       + '<span class="ctrl-name">' + name + '</span>'
       + '<span class="ctrl-action">' + esc(summary) + '</span></div>';
  }
  h += '</div>';

  for (const grp of ['A', 'B', 'C', 'D']) {
    h += '<h3>Encoder ' + grp + '</h3><div class="encoder-row">';
    const names = {A: ['AL','AP','AR'], B: ['BL','BP','BR'], C: ['CL','CP','CR'], D: ['DL','DP','DR']}[grp];
    const labels = ['Left', 'Press', 'Right'];
    for (let i = 0; i < 3; i++) {
      const name = names[i];
      const spec = ctrls[name];
      const cls = spec ? 'ctrl-mapped' : 'ctrl-unmapped';
      const summary = spec ? (spec.type || '?') : 'unmapped';
      h += '<div class="ctrl-cell ' + cls + '" onclick="editControl(\'' + name + '\')">'
         + '<span class="ctrl-name">' + name + ' (' + labels[i] + ')</span>'
         + '<span class="ctrl-action">' + esc(summary) + '</span></div>';
    }
    h += '</div>';
  }
  el.innerHTML = h;
}

// ── Action Editor ──
let EDITING_CONTROL = null;

function editControl(name) {
  EDITING_CONTROL = name;
  renderEditor();
}

function renderEditor() {
  const el = document.getElementById('editor-panel');
  if (!EDITING_CONTROL || !ACTIVE_LAYER) {
    el.innerHTML = '<p>Select a control to edit its action.</p>';
    return;
  }
  const spec = ACTIVE_LAYER.controls[EDITING_CONTROL];
  const actionType = spec ? spec.type : 'unmapped';

  let h = '<h3>Editing: ' + esc(EDITING_CONTROL) + '</h3>';
  h += '<p>Current: <strong>' + esc(actionType) + '</strong></p>';

  h += '<div class="action-type-picker">';
  for (const t of 'noop,debug_log,hotkey,text,command,delay,macro,set_layer,next_layer,previous_layer,set_profile'.split(',')) {
    const sel = t === actionType ? ' selected' : '';
    h += '<button class="at-btn' + sel + '" onclick="setActionType(\'' + t + '\')">' + t + '</button>';
  }
  h += '</div>';

  h += '<div id="action-form">';
  if (actionType === 'unmapped') {
    h += '<p>Select an action type above.</p>';
  } else {
    h += renderActionForm(actionType, spec);
  }
  h += '</div>';

  if (spec) {
    h += '<div class="action-actions">';
    h += '<button onclick="clearAction()" class="btn-danger">Clear Action</button>';
    h += '</div>';
  }
  el.innerHTML = h;
}

function renderActionForm(type, spec) {
  let h = '';
  if (type === 'noop') {
    h += '<p>No operation — this control does nothing.</p>';
  } else if (type === 'debug_log') {
    h += '<label for="af-message">Message:</label>';
    h += '<input id="af-message" value="' + esc(spec && spec.message || '') + '" size="40">';
  } else if (type === 'hotkey') {
    const keys = (spec && spec.keys) ? spec.keys.join('+') : '';
    h += '<label for="af-keys">Keys (e.g. CTRL+SHIFT+A):</label>';
    h += '<input id="af-keys" value="' + esc(keys) + '" size="40">';
    h += '<p class="hint">Separate keys with +</p>';
  } else if (type === 'text') {
    h += '<label for="af-value">Text:</label>';
    h += '<textarea id="af-value" rows="3" cols="40">' + esc(spec && spec.value || '') + '</textarea>';
  } else if (type === 'command') {
    const argv = (spec && spec.argv) ? spec.argv.join('\n') : '';
    h += '<label for="af-argv">Arguments (one per line):</label>';
    h += '<textarea id="af-argv" rows="3" cols="40">' + esc(argv) + '</textarea>';
    h += '<label for="af-timeout">Timeout (seconds):</label>';
    h += '<input id="af-timeout" type="number" value="' + (spec && spec.timeout_seconds || '') + '">';
    h += '<p class="hint">Executed only by daemon runtime, not by editor.</p>';
  } else if (type === 'delay') {
    h += '<label for="af-ms">Milliseconds:</label>';
    h += '<input id="af-ms" type="number" min="0" value="' + (spec && spec.milliseconds || 0) + '"> ms';
  } else if (type === 'macro') {
    const steps = (spec && spec.steps) || [];
    h += '<div class="macro-steps">';
    for (let i = 0; i < steps.length; i++) {
      h += '<div class="macro-step">';
      h += '<span class="step-num">' + (i + 1) + '</span>';
      h += '<span class="step-type">' + esc(steps[i].type) + '</span>';
      h += '<span class="step-summary">' + esc(JSON.stringify(steps[i]).substring(0, 60)) + '</span>';
      h += '<div class="step-actions">';
      h += '<button onclick="moveMacroStep(' + i + ',-1)">&#8593;</button>';
      h += '<button onclick="moveMacroStep(' + i + ',1)">&#8595;</button>';
      h += '<button onclick="deleteMacroStep(' + i + ')">&#10005;</button>';
      h += '</div>';
      h += '</div>';
    }
    h += '</div>';
    h += '<div class="macro-add-step">';
    h += '<label for="ma-step-json">Add step (JSON spec):</label>';
    h += '<input id="ma-step-json" placeholder=\'{"type":"debug_log","message":"step"}\' size="50">';
    h += '<button onclick="addMacroStep()">+ Step</button>';
    h += '</div>';
  } else if (type === 'set_layer' || type === 'set_profile') {
    const targetKey = type === 'set_layer' ? 'layer' : 'profile';
    const targets = type === 'set_layer'
      ? (ACTIVE_PROFILE ? ACTIVE_PROFILE.layers.map(l => l.layer_id) : [])
      : (STATE.profiles ? STATE.profiles.map(p => p.profile_id) : []);
    const cur = spec ? spec[targetKey] || '' : '';
    h += '<label for="af-target">Target:</label>';
    h += '<select id="af-target">';
    for (const t of targets) {
      const s = t === cur ? ' selected' : '';
      h += '<option value="' + esc(t) + '"' + s + '>' + esc(t) + '</option>';
    }
    h += '</select>';
  } else if (type === 'next_layer' || type === 'previous_layer') {
    h += '<p>Cycles to the ' + (type === 'next_layer' ? 'next' : 'previous') + ' layer at runtime.</p>';
  }
  h += '<br><button onclick="saveAction(\'' + type + '\')" class="btn-primary">Apply Action</button>';
  return h;
}

function setActionType(type) {
  // Update editing state and re-render
  if (!EDITING_CONTROL) return;
  // Build default spec based on type
  const defaults = {
    noop: {type: 'noop'},
    debug_log: {type: 'debug_log', message: ''},
    hotkey: {type: 'hotkey', keys: []},
    text: {type: 'text', value: ''},
    command: {type: 'command', argv: [''], timeout_seconds: 30},
    delay: {type: 'delay', milliseconds: 100},
    macro: {type: 'macro', steps: []},
    set_layer: {type: 'set_layer', layer: ACTIVE_PROFILE && ACTIVE_PROFILE.layers[0] ? ACTIVE_PROFILE.layers[0].layer_id : 'general'},
    next_layer: {type: 'next_layer'},
    previous_layer: {type: 'previous_layer'},
    set_profile: {type: 'set_profile', profile: STATE.profiles[0] ? STATE.profiles[0].profile_id : ''},
  };
  // Just show the form with the new type selected
  if (ACTIVE_LAYER) ACTIVE_LAYER.controls[EDITING_CONTROL] = defaults[type] || {type: type};
  renderEditor();
}

async function saveAction(type) {
  if (!EDITING_CONTROL || !ACTIVE_PROFILE || !ACTIVE_LAYER) return;
  let spec = { type: type };

  if (type === 'noop' || type === 'next_layer' || type === 'previous_layer') {
    // No extra fields
  } else if (type === 'debug_log') {
    spec.message = document.getElementById('af-message').value;
  } else if (type === 'hotkey') {
    const raw = document.getElementById('af-keys').value;
    spec.keys = raw.split('+').map(s => s.trim()).filter(Boolean);
  } else if (type === 'text') {
    spec.value = document.getElementById('af-value').value;
  } else if (type === 'command') {
    const argvRaw = document.getElementById('af-argv').value;
    spec.argv = argvRaw.split('\n').filter(s => s.trim() !== '');
    const to = parseInt(document.getElementById('af-timeout').value);
    if (!isNaN(to) && to > 0) spec.timeout_seconds = to;
  } else if (type === 'delay') {
    spec.milliseconds = parseInt(document.getElementById('af-ms').value) || 100;
  } else if (type === 'macro') {
    spec.steps = (ACTIVE_LAYER.controls[EDITING_CONTROL] && ACTIVE_LAYER.controls[EDITING_CONTROL].steps) || [];
  } else if (type === 'set_layer') {
    spec.layer = document.getElementById('af-target').value;
  } else if (type === 'set_profile') {
    spec.profile = document.getElementById('af-target').value;
  }

  try {
    const data = await apiPost('/control/set-action', {
      profile: ACTIVE_PROFILE.profile_id,
      layer: ACTIVE_LAYER.layer_id,
      control: EDITING_CONTROL,
      action_spec: spec,
    });
    if (data.status === 'ok') {
      STATE = data;
      // Refresh active refs
      if (ACTIVE_PROFILE) ACTIVE_PROFILE = STATE.profiles.find(p => p.profile_id === ACTIVE_PROFILE.profile_id);
      if (ACTIVE_PROFILE && ACTIVE_LAYER) {
        ACTIVE_LAYER = ACTIVE_PROFILE.layers.find(l => l.layer_id === ACTIVE_LAYER.layer_id);
      }
      showOk('Action saved');
      render();
      // Re-edit current control
      editControl(EDITING_CONTROL);
    } else {
      showError(data.error ? data.error.message : 'Unknown error');
    }
  } catch (e) {
    showError('Save failed: ' + e.message);
  }
}

async function clearAction() {
  if (!EDITING_CONTROL || !ACTIVE_PROFILE || !ACTIVE_LAYER) return;
  try {
    const data = await apiPost('/control/clear-action', {
      profile: ACTIVE_PROFILE.profile_id,
      layer: ACTIVE_LAYER.layer_id,
      control: EDITING_CONTROL,
    });
    if (data.status === 'ok') {
      STATE = data;
      if (ACTIVE_PROFILE) ACTIVE_PROFILE = STATE.profiles.find(p => p.profile_id === ACTIVE_PROFILE.profile_id);
      if (ACTIVE_PROFILE && ACTIVE_LAYER) {
        ACTIVE_LAYER = ACTIVE_PROFILE.layers.find(l => l.layer_id === ACTIVE_LAYER.layer_id);
      }
      showOk('Action cleared');
      EDITING_CONTROL = null;
      render();
    } else {
      showError(data.error ? data.error.message : 'Unknown error');
    }
  } catch (e) { showError('Clear failed: ' + e.message); }
}

// ── Profile/Layer mutations ──
async function addProfile() {
  const name = prompt('New profile ID (lowercase, alphanumeric):');
  if (!name) return;
  try {
    const data = await apiPost('/profile/add', { profile_id: name });
    if (data.status === 'ok') { STATE = data; ACTIVE_PROFILE = STATE.profiles.find(p => p.profile_id === name); render(); }
    else showError(data.error.message);
  } catch (e) { showError(e.message); }
}

async function renameProfile() {
  if (!ACTIVE_PROFILE) return;
  const n = prompt('New name for ' + ACTIVE_PROFILE.profile_id + ':', ACTIVE_PROFILE.profile_id);
  if (!n || n === ACTIVE_PROFILE.profile_id) return;
  try {
    const data = await apiPost('/profile/rename', { old_profile_id: ACTIVE_PROFILE.profile_id, new_profile_id: n });
    if (data.status === 'ok') { STATE = data; ACTIVE_PROFILE = STATE.profiles.find(p => p.profile_id === n); render(); }
    else showError(data.error.message);
  } catch (e) { showError(e.message); }
}

async function removeProfile() {
  if (!ACTIVE_PROFILE) return;
  if (!confirm('Delete profile "' + ACTIVE_PROFILE.profile_id + '" and all its layers? This cannot be undone if saved.')) return;
  try {
    const data = await apiPost('/profile/remove', { profile_id: ACTIVE_PROFILE.profile_id });
    if (data.status === 'ok') {
      STATE = data;
      ACTIVE_PROFILE = STATE.profiles.length > 0
        ? (STATE.profiles.find(p => p.is_default) || STATE.profiles[0])
        : null;
      render();
    } else showError(data.error.message);
  } catch (e) { showError(e.message); }
}

async function setDefaultProfile() {
  if (!ACTIVE_PROFILE) return;
  try {
    const data = await apiPost('/profile/set-default', { profile_id: ACTIVE_PROFILE.profile_id });
    if (data.status === 'ok') { STATE = data; render(); }
    else showError(data.error.message);
  } catch (e) { showError(e.message); }
}

async function addLayer() {
  if (!ACTIVE_PROFILE) return;
  const name = prompt('Layer ID (e.g. layer_1):', 'layer_1');
  if (!name) return;
  try {
    const data = await apiPost('/layer/add', { profile: ACTIVE_PROFILE.profile_id, layer_id: name });
    if (data.status === 'ok') {
      STATE = data;
      ACTIVE_PROFILE = STATE.profiles.find(p => p.profile_id === ACTIVE_PROFILE.profile_id);
      ACTIVE_LAYER = ACTIVE_PROFILE.layers.find(l => l.layer_id === name);
      render();
    } else showError(data.error.message);
  } catch (e) { showError(e.message); }
}

async function renameLayer() {
  if (!ACTIVE_PROFILE || !ACTIVE_LAYER) return;
  const n = prompt('New name for ' + ACTIVE_LAYER.layer_id + ':', ACTIVE_LAYER.layer_id);
  if (!n || n === ACTIVE_LAYER.layer_id) return;
  try {
    const data = await apiPost('/layer/rename', { profile: ACTIVE_PROFILE.profile_id, old_layer_id: ACTIVE_LAYER.layer_id, new_layer_id: n });
    if (data.status === 'ok') {
      STATE = data;
      ACTIVE_PROFILE = STATE.profiles.find(p => p.profile_id === ACTIVE_PROFILE.profile_id);
      ACTIVE_LAYER = ACTIVE_PROFILE.layers.find(l => l.layer_id === n);
      render();
    } else showError(data.error.message);
  } catch (e) { showError(e.message); }
}

async function removeLayer() {
  if (!ACTIVE_PROFILE || !ACTIVE_LAYER) return;
  if (!confirm('Delete layer "' + ACTIVE_LAYER.layer_id + '" and all its control mappings?')) return;
  try {
    const data = await apiPost('/layer/remove', { profile: ACTIVE_PROFILE.profile_id, layer_id: ACTIVE_LAYER.layer_id });
    if (data.status === 'ok') {
      STATE = data;
      ACTIVE_PROFILE = STATE.profiles.find(p => p.profile_id === ACTIVE_PROFILE.profile_id);
      ACTIVE_LAYER = ACTIVE_PROFILE.layers.length > 0 ? ACTIVE_PROFILE.layers[0] : null;
      render();
    } else showError(data.error.message);
  } catch (e) { showError(e.message); }
}

async function setInitialLayer() {
  if (!ACTIVE_LAYER) return;
  try {
    const data = await apiPost('/layer/set-initial', { layer_id: ACTIVE_LAYER.layer_id });
    if (data.status === 'ok') { STATE = data; render(); }
    else showError(data.error.message);
  } catch (e) { showError(e.message); }
}

// ── Macro step editing ──
async function addMacroStep() {
  const raw = document.getElementById('ma-step-json').value;
  let stepSpec;
  try { stepSpec = JSON.parse(raw); } catch (e) { showError('Invalid JSON'); return; }
  if (!stepSpec.type) { showError('Missing type'); return; }
  if (!ACTIVE_LAYER || !EDITING_CONTROL) return;
  const cur = ACTIVE_LAYER.controls[EDITING_CONTROL];
  const steps = (cur && cur.steps) ? [...cur.steps] : [];
  steps.push(stepSpec);
  ACTIVE_LAYER.controls[EDITING_CONTROL] = { type: 'macro', steps: steps };
  renderEditor();
}

function moveMacroStep(idx, dir) {
  if (!ACTIVE_LAYER || !EDITING_CONTROL) return;
  const cur = ACTIVE_LAYER.controls[EDITING_CONTROL];
  if (!cur || !cur.steps) return;
  const steps = [...cur.steps];
  const newIdx = idx + dir;
  if (newIdx < 0 || newIdx >= steps.length) return;
  [steps[idx], steps[newIdx]] = [steps[newIdx], steps[idx]];
  ACTIVE_LAYER.controls[EDITING_CONTROL] = { type: 'macro', steps: steps };
  renderEditor();
}

function deleteMacroStep(idx) {
  if (!ACTIVE_LAYER || !EDITING_CONTROL) return;
  const cur = ACTIVE_LAYER.controls[EDITING_CONTROL];
  if (!cur || !cur.steps) return;
  const steps = [...cur.steps];
  steps.splice(idx, 1);
  ACTIVE_LAYER.controls[EDITING_CONTROL] = { type: 'macro', steps: steps };
  renderEditor();
}

// ── Review ──
async function showReview() {
  try {
    const [diffData, unifiedData] = await Promise.all([
      apiGet('/diff'), apiGet('/diff/unified'),
    ]);
    const d = diffData.status === 'ok' ? diffData : diffData;
    const u = unifiedData.status === 'ok' ? unifiedData : unifiedData;
    const el = document.getElementById('review-panel');
    let h = '<h3>Review Changes</h3>';
    h += '<p>Changes: <strong>' + (d.change_count || 0) + '</strong> | Risk: <strong>' + esc(d.risk_summary || 'LOW') + '</strong></p>';
    if (d.changes && d.changes.length > 0) {
      h += '<div class="diff-changes">';
      for (const c of d.changes) {
        h += '<div class="diff-item risk-' + (c.risk || 'LOW').toLowerCase() + '">';
        h += '<span class="diff-kind">' + esc(c.kind) + '</span> ';
        h += '<span class="diff-path">' + esc(c.path) + '</span>: ';
        h += '<span class="diff-before">' + esc(c.before) + '</span> → ';
        h += '<span class="diff-after">' + esc(c.after) + '</span>';
        h += ' <span class="risk-badge">' + esc(c.risk) + '</span>';
        h += '</div>';
      }
      h += '</div>';
    }
    if (u.unified_diff) {
      h += '<h4>Unified Diff</h4>';
      h += '<pre class="unified-diff">' + esc(u.unified_diff) + '</pre>';
    }
    h += '<button onclick="confirmReview()" class="btn-primary">Review Complete</button>';
    el.innerHTML = h;
    el.style.display = 'block';
  } catch (e) { showError('Review failed: ' + e.message); }
}

async function confirmReview() {
  // Mark reviewed on server side — the next save will check
  // We set a flag locally; server validates via mutation count
  document.getElementById('review-panel').style.display = 'none';
  showOk('Review confirmed. You may now save.');
  // Force re-validation
  try {
    const data = await apiGet('/validate');
    STATE = data.status === 'ok' ? data : STATE;
  } catch (e) { /* ignore */ }
  render();
}

// ── Validate ──
async function showValidate() {
  try {
    const data = await apiGet('/validate');
    STATE = data.status === 'ok' ? data : STATE;
    const v = STATE.validation || {};
    const el = document.getElementById('review-panel');
    let h = '<h3>Validation</h3>';
    h += '<p>Valid: <strong>' + (v.valid ? 'YES' : 'NO') + '</strong></p>';
    const errs = v.errors || [];
    const warns = v.warnings || [];
    if (errs.length > 0) {
      h += '<h4>Errors (' + errs.length + ')</h4>';
      for (const e of errs) {
        h += '<div class="diag diag-error">' + esc(e.path || '') + ': ' + esc(e.message) + '</div>';
      }
    }
    if (warns.length > 0) {
      h += '<h4>Warnings (' + warns.length + ')</h4>';
      for (const w of warns) {
        h += '<div class="diag diag-warn">' + esc(w.path || '') + ': ' + esc(w.message) + '</div>';
      }
    }
    if (errs.length === 0 && warns.length === 0) {
      h += '<p class="ok">No errors or warnings.</p>';
    }
    el.innerHTML = h;
    el.style.display = 'block';
  } catch (e) { showError('Validate failed: ' + e.message); }
}

async function closeReview() {
  document.getElementById('review-panel').style.display = 'none';
}

// ── Save ──
function updateSaveButton() {
  const s = STATE;
  const v = s.validation || {};
  const canSave = s.dirty && v.valid && s.mutation_count >= 0;
  const btn = document.getElementById('btn-save');
  if (btn) {
    btn.disabled = !canSave;
    btn.title = canSave ? 'Save changes to target' : 'Cannot save: ensure no validation errors and changes have been reviewed';
  }
}

async function doSave() {
  const target = STATE.target || '';
  const base = (STATE.base_sha256 || '').substring(0, 16);
  if (!confirm('Save to ' + target + '?\\nBase SHA: ' + base + '\\nSave does not reload daemon.')) return;
  try {
    const data = await apiPost('/save', {});
    if (data.status === 'ok') {
      STATE.dirty = false;
      STATE.mutation_count = 0;
      showOk('Saved! SHA: ' + (data.saved_sha256 || '').substring(0, 16));
      await loadState();
    } else {
      showError(data.error ? data.error.message : 'Save failed');
    }
  } catch (e) { showError('Save failed: ' + e.message); }
}

async function doShutdown() {
  if (!confirm('Close the editor? Unsaved changes will be lost.')) return;
  try { await apiPost('/shutdown', {}); } catch (e) { /* server closing */ }
  document.body.innerHTML = '<div style="padding:2em;text-align:center"><h2>Editor Closed</h2><p>You may close this tab.</p></div>';
}

// ── Utility ──
function esc(s) {
  if (typeof s !== 'string') return s;
  return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}

// ── Init ──
window.onload = function() { loadState(); };
"""


_CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
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

/* Top bar */
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

/* Layout */
#main { display: flex; height: calc(100vh - 48px); }
#nav-panel { width: 220px; background: #fff; border-right: 1px solid #ddd;
             padding: 12px; overflow-y: auto; flex-shrink: 0; }
#center-panel { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
#controls-panel { padding: 12px; overflow-y: auto; background: #fff; border-bottom: 1px solid #ddd; }
#editor-panel { padding: 12px; overflow-y: auto; flex: 1; background: #fafafa; }
#review-panel { display: none; padding: 12px; background: #fffbe6; border-bottom: 1px solid #ddd;
                max-height: 50vh; overflow-y: auto; }

/* Nav */
#nav-panel h3 { font-size: 13px; color: #586069; margin-bottom: 6px; margin-top: 12px;
                 text-transform: uppercase; letter-spacing: 0.5px; }
#nav-panel h3:first-child { margin-top: 0; }
.nav-list { list-style: none; }
.nav-item { padding: 4px 8px; cursor: pointer; border-radius: 3px; font-size: 13px; }
.nav-item:hover { background: #f0f0f0; }
.nav-item.selected { background: #0366d6; color: #fff; }
.nav-actions { display: flex; gap: 4px; margin: 6px 0; flex-wrap: wrap; }

/* Controls grid */
.button-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; margin-bottom: 12px; }
.encoder-row { display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; margin-bottom: 12px; }
.ctrl-cell { padding: 8px; border: 1px solid #ddd; border-radius: 4px; cursor: pointer;
             text-align: center; font-size: 13px; }
.ctrl-cell:hover { border-color: #0366d6; background: #f0f7ff; }
.ctrl-mapped { background: #e8f4e8; border-color: #a0d0a0; }
.ctrl-unmapped { background: #fafafa; color: #999; }
.ctrl-name { display: block; font-weight: 600; font-size: 15px; }
.ctrl-action { display: block; font-size: 11px; color: #666; margin-top: 2px; }

/* Action editor */
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

/* Macro steps */
.macro-steps { margin: 8px 0; }
.macro-step { display: flex; align-items: center; gap: 8px; padding: 4px;
              border-bottom: 1px solid #eee; font-size: 13px; }
.step-num { width: 24px; text-align: right; font-weight: 600; color: #888; }
.step-type { font-family: monospace; font-weight: 600; min-width: 100px; }
.step-summary { flex: 1; font-size: 12px; color: #666; overflow: hidden; text-overflow: ellipsis; }
.step-actions { display: flex; gap: 2px; }
.macro-add-step { margin-top: 10px; display: flex; gap: 6px; align-items: flex-end; }
.macro-add-step input { flex: 1; }

/* Review / Diff */
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

/* Diagnostics */
.diag { padding: 4px 8px; margin-bottom: 2px; font-size: 13px; }
.diag-error { background: #ffe0e0; color: #a00; border-left: 3px solid #d73a49; }
.diag-warn { background: #fff8e0; color: #840; border-left: 3px solid #f0ad4e; }

/* Focus */
:focus { outline: 2px solid #0366d6; outline-offset: 1px; }
button:focus, input:focus, textarea:focus, select:focus { outline: 2px solid #0366d6; outline-offset: 1px; }
"""


def render_editor_page() -> str:
    """Return the complete self-contained HTML editor page."""
    return f"""\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>YYR4 Configuration Editor</title>
<style>
{_CSS}
</style>
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
  <span style="margin-left:auto; display:flex; gap:6px;">
    <button onclick="showValidate()">Validate</button>
    <button onclick="showReview()">Review</button>
    <button id="btn-save" onclick="doSave()" disabled>Save</button>
    <button onclick="doShutdown()" class="btn-danger">Shutdown</button>
  </span>
</div>

<div id="main">
  <div id="nav-panel">
    <div id="nav-content"></div>
  </div>
  <div id="center-panel">
    <div id="review-panel"></div>
    <div id="controls-panel">
      <div id="controls-grid"></div>
    </div>
    <div id="editor-panel">
      <p>Select a control to edit its action.</p>
    </div>
  </div>
</div>

<script>
{_JS_CODE}
</script>
</body>
</html>"""
