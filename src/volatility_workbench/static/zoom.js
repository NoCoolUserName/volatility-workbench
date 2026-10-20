(() => {
  'use strict';
  const minimum = 75, maximum = 200;
  const root = document.documentElement;
  let percent = 100, fluidPercent = 100, touched = false, connected = false, loading = false;
  let gestureStart = null, saveTimer = null, saveGeneration = 0, saveQueue = Promise.resolve();
  let currentStatus = '';

  function status(message) {
    currentStatus = message;
    document.querySelectorAll('[data-ui-zoom-status]').forEach(node => {
      node.textContent = message;
      node.hidden = !message;
    });
  }
  function layout() {
    const scale = percent / 100;
    root.style.setProperty('--text-scale', String(scale));
    root.dataset.textScaled = percent === 100 ? 'false' : 'true';
    document.querySelectorAll('[data-ui-zoom-value]').forEach(node => { node.textContent = `${percent}%`; });
    document.querySelectorAll('[data-ui-zoom-out]').forEach(node => { node.disabled = !connected || percent <= minimum; });
    document.querySelectorAll('[data-ui-zoom-in]').forEach(node => { node.disabled = !connected || percent >= maximum; });
    document.querySelectorAll('[data-ui-zoom-reset]').forEach(node => { node.disabled = !connected; });
    document.dispatchEvent(new Event('workbench-text-scale'));
  }
  function scheduleSave() {
    const generation = ++saveGeneration;
    clearTimeout(saveTimer);
    saveTimer = setTimeout(() => {
      const value = percent;
      saveQueue = saveQueue.catch(() => {}).then(async () => {
        if (generation !== saveGeneration) return;
        const response = await fetch('/api/settings/zoom', {
          method: 'POST', credentials: 'same-origin', headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({percent: value}),
        });
        const result = await response.json();
        if (!response.ok || result.schema !== 'zoom/1' || result.percent !== value)
          throw Error('Zoom preference save failed');
        if (generation === saveGeneration) status('');
      }).catch(() => {
        if (generation === saveGeneration) status('Zoom changed here, but could not be saved.');
      });
    }, 350);
  }
  function apply(value, save = false, preserveFluid = false) {
    const next = Math.min(maximum, Math.max(minimum, Math.round(value / 5) * 5));
    if (next === percent) return;
    percent = next;
    if (!preserveFluid) fluidPercent = next;
    if (save) { touched = true; scheduleSave(); }
    layout();
  }
  function mount() {
    document.querySelectorAll('[data-ui-zoom-out]').forEach(node => node.addEventListener('click', () => apply(percent - 10, true)));
    document.querySelectorAll('[data-ui-zoom-in]').forEach(node => node.addEventListener('click', () => apply(percent + 10, true)));
    document.querySelectorAll('[data-ui-zoom-reset]').forEach(node => node.addEventListener('click', () => apply(100, true)));
    layout();
    status(currentStatus);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', mount, {once: true});
  else mount();

  async function load() {
    if (loading) return;
    loading = true;
    try {
      const response = await fetch('/api/settings/zoom', {credentials: 'same-origin'});
      if (!response.ok) throw Error('Zoom preference could not be loaded');
      const saved = await response.json();
      if (saved.schema !== 'zoom/1' || !Number.isInteger(saved.percent)
          || saved.percent < minimum || saved.percent > maximum || saved.percent % 5)
        throw Error('Zoom preference is invalid');
      if (!touched) apply(saved.percent);
      if (saved.error) status(saved.error);
    } catch {
      status('Zoom preference could not be loaded; using 100%.');
    } finally {
      connected = true;
      layout();
    }
  }
  window.WorkbenchZoom = Object.freeze({load});

  window.addEventListener('wheel', event => {
    if (!event.ctrlKey || event.altKey || event.metaKey) return;
    event.preventDefault();
    if (!connected) return;
    if (gestureStart !== null) return;
    const delta = event.deltaY * (event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? window.innerHeight : 1);
    fluidPercent = Math.min(maximum, Math.max(minimum, fluidPercent * Math.exp(-delta * 0.0015)));
    apply(fluidPercent, true, true);
  }, {passive: false});
  window.addEventListener('gesturestart', event => {
    event.preventDefault();
    if (!connected) return;
    gestureStart = fluidPercent;
  }, {passive: false});
  window.addEventListener('gesturechange', event => {
    event.preventDefault();
    if (!connected) return;
    if (gestureStart === null) gestureStart = fluidPercent;
    fluidPercent = Math.min(maximum, Math.max(minimum, gestureStart * Number(event.scale || 1)));
    apply(fluidPercent, true, true);
  }, {passive: false});
  window.addEventListener('gestureend', event => {
    event.preventDefault();
    gestureStart = null;
  }, {passive: false});
})();
