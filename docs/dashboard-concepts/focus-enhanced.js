(function () {
  'use strict';

  const STORAGE_KEY = 'nexroll-concept-a-enhanced-v1';
  const SIZE_ORDER = [4, 6, 8, 12];
  const SIZE_LABELS = { 4: 'Third', 6: 'Half', 8: 'Wide', 12: 'Full' };
  const TILE_META = {
    schedule: { name: 'Current & next', note: 'Active and upcoming schedules', glyph: '▶', defaultSpan: 8 },
    health: { name: 'System health', note: 'Scheduler, servers, integrations, issues', glyph: '♡', defaultSpan: 4 },
    library: { name: 'Library', note: 'Prerolls, categories, and trailers', glyph: '▥', defaultSpan: 4 },
    actions: { name: 'Quick actions', note: 'Common maintenance commands', glyph: '✦', defaultSpan: 4 },
    storage: { name: 'Storage', note: 'Space usage by content type', glyph: '▰', defaultSpan: 4 },
    servers: { name: 'Media servers', note: 'Useful for multi-server installs', glyph: '▣', defaultSpan: 4 },
    quality: { name: 'Video quality', note: 'Resolution and codec analysis', glyph: '▥', defaultSpan: 4 },
    community: { name: 'Community', note: 'Index status and matched prerolls', glyph: '◎', defaultSpan: 4 }
  };
  const DEFAULT_ORDER = Object.keys(TILE_META);
  const PRESETS = {
    essential: ['schedule', 'health', 'library', 'actions', 'storage'],
    operations: ['schedule', 'health', 'library', 'actions', 'storage', 'servers'],
    everything: DEFAULT_ORDER.slice()
  };

  const defaultState = () => ({
    order: DEFAULT_ORDER.slice(),
    visible: PRESETS.essential.slice(),
    spans: Object.fromEntries(DEFAULT_ORDER.map(id => [id, TILE_META[id].defaultSpan])),
    details: Object.fromEntries(DEFAULT_ORDER.map(id => [id, 'detailed'])),
    density: 'comfortable',
    showGreeting: true,
    showFriendlyStatus: true,
    showClock: true,
    preset: 'essential'
  });

  let state = loadState();
  let draft = clone(state);
  let arranging = false;
  let draggedId = null;
  let toastTimer = 0;

  const body = document.body;
  const grid = document.getElementById('dashboardGrid');
  const dialog = document.getElementById('customizeDialog');
  const configList = document.getElementById('tileConfigList');
  const arrangeButton = document.getElementById('arrangeButton');
  const customizeButton = document.getElementById('customizeButton');
  const optionalCount = document.getElementById('optionalCount');
  const toast = document.getElementById('toast');
  const toastText = document.getElementById('toastText');
  const qaStatus = document.getElementById('qaStatus');

  function clone(value) { return JSON.parse(JSON.stringify(value)); }

  function loadState() {
    const fallback = defaultState();
    try {
      const stored = JSON.parse(localStorage.getItem(STORAGE_KEY));
      if (!stored || !Array.isArray(stored.order) || !Array.isArray(stored.visible)) return fallback;
      const order = stored.order.filter(id => TILE_META[id]);
      DEFAULT_ORDER.forEach(id => { if (!order.includes(id)) order.push(id); });
      return {
        ...fallback,
        ...stored,
        order,
        visible: stored.visible.filter(id => TILE_META[id]),
        spans: { ...fallback.spans, ...(stored.spans || {}) },
        details: { ...fallback.details, ...(stored.details || {}) }
      };
    } catch (_) { return fallback; }
  }

  function saveState() {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(state)); } catch (_) {}
  }

  function renderDashboard() {
    state.order.forEach(id => {
      const tile = grid.querySelector(`[data-tile-id="${id}"]`);
      if (!tile) return;
      grid.appendChild(tile);
      const span = Number(state.spans[id]) || TILE_META[id].defaultSpan;
      tile.style.setProperty('--tile-span', span);
      tile.hidden = !state.visible.includes(id);
      tile.classList.toggle('tile-compact', state.details[id] === 'compact');
      tile.querySelector('.tile-size-cycle').textContent = SIZE_LABELS[span] || 'Third';
      tile.draggable = arranging;
    });
    body.dataset.density = state.density;
    document.getElementById('greetingBlock').style.display = state.showGreeting ? '' : 'none';
    document.getElementById('friendlyNote').style.display = state.showGreeting && state.showFriendlyStatus ? '' : 'none';
    document.getElementById('globalClock').style.display = state.showClock ? '' : 'none';
    const hiddenCount = DEFAULT_ORDER.length - state.visible.length;
    optionalCount.textContent = hiddenCount ? `+ ${hiddenCount} optional tile${hiddenCount === 1 ? '' : 's'}` : 'All tiles shown';
  }

  function renderConfig() {
    document.getElementById('showGreeting').checked = draft.showGreeting;
    document.getElementById('showFriendlyStatus').checked = draft.showFriendlyStatus;
    document.getElementById('showClock').checked = draft.showClock;
    document.getElementById('densitySelect').value = draft.density;
    document.querySelectorAll('.preset').forEach(button => button.classList.toggle('active', button.dataset.preset === draft.preset));
    configList.innerHTML = '';
    draft.order.forEach((id, index) => {
      const meta = TILE_META[id];
      const visible = draft.visible.includes(id);
      const row = document.createElement('div');
      row.className = `tile-config-row${visible ? '' : ' is-hidden'}`;
      row.dataset.configId = id;
      row.innerHTML = `
        <div class="reorder-pair"><button type="button" data-move="up" aria-label="Move ${meta.name} up" ${index === 0 ? 'disabled' : ''}>▲</button><button type="button" data-move="down" aria-label="Move ${meta.name} down" ${index === draft.order.length - 1 ? 'disabled' : ''}>▼</button></div>
        <span class="config-glyph">${meta.glyph}</span>
        <span class="config-name"><strong>${meta.name}</strong><span>${meta.note}</span></span>
        <select class="select width-select" aria-label="${meta.name} width"><option value="4">One third</option><option value="6">Half width</option><option value="8">Two thirds</option><option value="12">Full width</option></select>
        <select class="select detail-select" aria-label="${meta.name} detail"><option value="detailed">Detailed</option><option value="compact">Compact</option></select>
        <label class="switch"><input type="checkbox" class="visibility-toggle" aria-label="Show ${meta.name}" ${visible ? 'checked' : ''}><span></span></label>`;
      row.querySelector('.width-select').value = String(draft.spans[id]);
      row.querySelector('.detail-select').value = draft.details[id];
      configList.appendChild(row);
    });
  }

  function openCustomize() {
    if (arranging) setArranging(false);
    draft = clone(state);
    renderConfig();
    dialog.showModal();
  }

  function applyPreset(name) {
    if (!PRESETS[name]) return;
    draft.visible = PRESETS[name].slice();
    draft.preset = name;
    if (name === 'essential') {
      draft.order = DEFAULT_ORDER.slice();
      draft.spans = { ...defaultState().spans };
    } else if (name === 'operations') {
      draft.order = ['schedule','health','library','actions','storage','servers','quality','community'];
    }
    renderConfig();
  }

  function updateDraftFromControls() {
    draft.showGreeting = document.getElementById('showGreeting').checked;
    draft.showFriendlyStatus = document.getElementById('showFriendlyStatus').checked;
    draft.showClock = document.getElementById('showClock').checked;
    draft.density = document.getElementById('densitySelect').value;
    configList.querySelectorAll('.tile-config-row').forEach(row => {
      const id = row.dataset.configId;
      draft.spans[id] = Number(row.querySelector('.width-select').value);
      draft.details[id] = row.querySelector('.detail-select').value;
      const checked = row.querySelector('.visibility-toggle').checked;
      draft.visible = draft.visible.filter(tileId => tileId !== id);
      if (checked) draft.visible.push(id);
    });
    draft.visible = draft.order.filter(id => draft.visible.includes(id));
  }

  function saveDraft() {
    updateDraftFromControls();
    state = clone(draft);
    saveState();
    renderDashboard();
    showToast('Dashboard preferences saved');
  }

  function resetDraft() {
    draft = defaultState();
    renderConfig();
    showToast('Essential layout restored in preview');
  }

  function moveDraftTile(id, direction) {
    updateDraftFromControls();
    const index = draft.order.indexOf(id);
    const next = direction === 'up' ? index - 1 : index + 1;
    if (index < 0 || next < 0 || next >= draft.order.length) return;
    [draft.order[index], draft.order[next]] = [draft.order[next], draft.order[index]];
    draft.preset = 'custom';
    renderConfig();
  }

  function setArranging(enabled) {
    arranging = enabled;
    body.classList.toggle('is-arranging', enabled);
    arrangeButton.classList.toggle('active', enabled);
    arrangeButton.querySelector('.label').textContent = enabled ? 'Done' : 'Arrange';
    state.order.forEach(id => {
      const tile = grid.querySelector(`[data-tile-id="${id}"]`);
      if (tile) tile.draggable = enabled;
    });
    if (!enabled) {
      saveState();
      showToast('Tile order saved');
    }
  }

  function cycleTileSize(tile) {
    const id = tile.dataset.tileId;
    const current = Number(state.spans[id]) || 4;
    const next = SIZE_ORDER[(SIZE_ORDER.indexOf(current) + 1) % SIZE_ORDER.length];
    state.spans[id] = next;
    state.preset = 'custom';
    renderDashboard();
    saveState();
    showToast(`${TILE_META[id].name} changed to ${SIZE_LABELS[next].toLowerCase()} width`);
  }

  function runAction(button) {
    const action = button.dataset.action;
    if (action === 'all-actions') { showToast('In the live app, this opens the full command menu'); return; }
    const messages = {
      refresh: ['Refreshing dashboard data…', 'Dashboard data refreshed'],
      scan: ['Scanning preroll folders…', 'File scan completed · no changes'],
      sync: ['Syncing Radarr and Sonarr…', 'NeX-Up sync completed'],
      thumbs: ['Queueing thumbnail rebuild…', 'Thumbnail rebuild started']
    };
    const copy = messages[action] || ['Working…', 'Action completed'];
    button.classList.add('running');
    button.disabled = true;
    if (qaStatus) qaStatus.textContent = copy[0];
    showToast(copy[0]);
    window.setTimeout(() => {
      button.classList.remove('running');
      button.disabled = false;
      if (qaStatus) qaStatus.textContent = `${copy[1]} · just now`;
      showToast(copy[1]);
    }, 1100);
  }

  function showToast(message) {
    window.clearTimeout(toastTimer);
    toastText.textContent = message;
    toast.classList.add('show');
    toastTimer = window.setTimeout(() => toast.classList.remove('show'), 2200);
  }

  function updateClock() {
    const now = new Date();
    const hour = now.getHours();
    const greeting = hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening';
    document.getElementById('greetingText').textContent = `${greeting}, JB`;
    document.getElementById('clockTime').textContent = now.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
    document.getElementById('clockDate').textContent = now.toLocaleDateString([], { weekday: 'long', month: 'long', day: 'numeric' });
  }

  customizeButton.addEventListener('click', openCustomize);
  optionalCount.addEventListener('click', openCustomize);
  arrangeButton.addEventListener('click', () => setArranging(!arranging));

  document.querySelectorAll('.preset').forEach(button => button.addEventListener('click', () => applyPreset(button.dataset.preset)));
  document.getElementById('resetButton').addEventListener('click', resetDraft);
  dialog.addEventListener('close', () => {
    if (dialog.returnValue === 'save') saveDraft();
  });

  configList.addEventListener('click', event => {
    const button = event.target.closest('[data-move]');
    if (!button) return;
    const row = button.closest('.tile-config-row');
    moveDraftTile(row.dataset.configId, button.dataset.move);
  });

  configList.addEventListener('change', event => {
    const row = event.target.closest('.tile-config-row');
    if (row && event.target.classList.contains('visibility-toggle')) row.classList.toggle('is-hidden', !event.target.checked);
    draft.preset = 'custom';
    document.querySelectorAll('.preset').forEach(button => button.classList.remove('active'));
  });

  grid.addEventListener('click', event => {
    const sizeButton = event.target.closest('.tile-size-cycle');
    if (sizeButton) { event.preventDefault(); cycleTileSize(sizeButton.closest('.interactive-tile')); return; }
    const link = event.target.closest('.tile-link');
    if (link) { showToast(`In the live app, this opens ${link.dataset.destination}`); }
  });

  document.querySelectorAll('.demo-action').forEach(button => button.addEventListener('click', () => runAction(button)));

  grid.addEventListener('dragstart', event => {
    if (!arranging) { event.preventDefault(); return; }
    const tile = event.target.closest('.interactive-tile');
    if (!tile) return;
    draggedId = tile.dataset.tileId;
    tile.classList.add('dragging');
    event.dataTransfer.effectAllowed = 'move';
    event.dataTransfer.setData('text/plain', draggedId);
  });

  grid.addEventListener('dragover', event => {
    if (!arranging || !draggedId) return;
    const target = event.target.closest('.interactive-tile');
    if (!target || target.dataset.tileId === draggedId || target.hidden) return;
    event.preventDefault();
    grid.querySelectorAll('.drag-over').forEach(tile => tile.classList.remove('drag-over'));
    target.classList.add('drag-over');
  });

  grid.addEventListener('drop', event => {
    if (!arranging || !draggedId) return;
    const target = event.target.closest('.interactive-tile');
    if (!target || target.dataset.tileId === draggedId) return;
    event.preventDefault();
    const from = state.order.indexOf(draggedId);
    const to = state.order.indexOf(target.dataset.tileId);
    state.order.splice(from, 1);
    state.order.splice(to, 0, draggedId);
    state.preset = 'custom';
    renderDashboard();
    saveState();
  });

  grid.addEventListener('dragend', () => {
    grid.querySelectorAll('.dragging,.drag-over').forEach(tile => tile.classList.remove('dragging', 'drag-over'));
    draggedId = null;
  });

  updateClock();
  window.setInterval(updateClock, 30000);
  renderDashboard();
  const demoParams = new URLSearchParams(window.location.search);
  if (demoParams.get('customize') === '1') window.setTimeout(openCustomize, 0);
  if (demoParams.get('arrange') === '1') window.setTimeout(() => setArranging(true), 0);
})();
