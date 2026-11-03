(() => {
  const tbody = document.querySelector('#items tbody');
  if (!tbody) return;
  const $ = id => document.getElementById(id);
  const state = { rows: [], sort: 'category', dir: 1, cat: '' };

  // Filter in der URL merken, damit Links/Lesezeichen funktionieren
  const params = new URLSearchParams(location.search);
  for (const k of ['q', 'tier', 'days', 'has']) if (params.get(k)) $(k).value = params.get(k);
  state.cat = params.get('cat') || '';
  if (params.get('gs_min')) $('gsMin').value = params.get('gs_min');
  if (params.get('gs_max')) $('gsMax').value = params.get('gs_max');
  const gsQuery = () => ($('gsMin').value ? '&gs_min=' + encodeURIComponent($('gsMin').value) : '') + ($('gsMax').value ? '&gs_max=' + encodeURIComponent($('gsMax').value) : '');
  $('onlyEmpty').checked = params.get('empty') === '1';
  if (params.get('sort')) { state.sort = params.get('sort'); state.dir = params.get('dir') === '-1' ? -1 : 1; }

  // ---- Kategorien wie im Spiel: Baum vom Server, Zaehler aus den geladenen Zeilen
  const norm = p => (p || '').toLowerCase();
  let baseTree = [], nav = { roots: [], by: new Map(), rank: new Map() };
  const ICONS = {
    all: '<path d="M4 4h4v4H4zM10 4h4v4h-4zM16 4h4v4h-4zM4 10h4v4H4zM10 10h4v4h-4zM16 10h4v4h-4zM4 16h4v4H4zM10 16h4v4h-4zM16 16h4v4h-4z" fill="currentColor" stroke="none"/>',
    weapons: '<path d="M5 19L19 5M19 19L5 5M14 4h6v6M10 4H4v6M4 20l2-2M20 20l-2-2"/>',
    tools: '<path d="M5 20L15 10M14 4c4 0 6 2 6 6M14 4c-2 2-3 4-3 6M20 10c-2 0-4 1-6 3"/>',
    apparel: '<path d="M8 4l-5 3 2 4 3-1v10h8V10l3 1 2-4-5-3c0 2-2 3-4 3S8 6 8 4z"/>',
    resources: '<path d="M4 17l3-8h10l3 8zM8 12h8"/>',
    utilities: '<path d="M9 4h6M10 4v3c-3 2-4 4-4 7a6 6 0 0012 0c0-3-1-5-4-7V4"/>',
    furnishings: '<path d="M8 4h8v8H8zM7 12h10M8 12v8M16 12v8"/>',
  };
  const icon = key => `<svg viewBox="0 0 24 24" aria-hidden="true">${ICONS[key] || ICONS.all}</svg>`;
  const CLIP = '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M4 2h8v12H4zM6 5h4M6 8h4M6 11h4"/></svg>';

  function buildNav() {
    const by = new Map(), roots = [];
    const clone = (nodes, parent) => nodes.map(n => {
      const c = { p: n.p, n: n.n, parent, c: [], count: 0 };
      by.set(norm(n.p), c);
      c.c = clone(n.c || [], c);
      return c;
    });
    roots.push(...clone(baseTree, null));
    // Kategorien aus den Daten, die nicht im Baum stehen, hinten anhaengen
    for (const r of state.rows) {
      const segs = (r.category || '').split('/').filter(Boolean);
      for (let d = 1; d <= segs.length; d++) {
        const path = segs.slice(0, d).join('/');
        if (by.has(norm(path))) continue;
        const parent = d > 1 ? by.get(norm(segs.slice(0, d - 1).join('/'))) : null;
        const node = { p: path, n: segs[d - 1], parent, c: [], count: 0 };
        by.set(norm(path), node);
        (parent ? parent.c : roots).push(node);
      }
    }
    for (const r of state.rows) {
      const segs = (r.category || '').split('/').filter(Boolean);
      for (let d = 1; d <= segs.length; d++) by.get(norm(segs.slice(0, d).join('/'))).count += r.listings || 0;
    }
    const rank = new Map();
    (function walk(nodes) { for (const n of nodes) { rank.set(norm(n.p), rank.size); walk(n.c); } })(roots);
    nav = { roots, by, rank };
  }

  function rankOf(path) {
    const segs = (path || '').split('/').filter(Boolean);
    for (let d = segs.length; d > 0; d--) {
      const r = nav.rank.get(norm(segs.slice(0, d).join('/')));
      if (r != null) return r;
    }
    return Infinity;
  }
  function catLabel(path) {
    const segs = (path || '').split('/').filter(Boolean);
    return segs.map((s, i) => nav.by.get(norm(segs.slice(0, i + 1).join('/')))?.n || s).join('/');
  }

  function setCat(path) {
    state.cat = path;
    renderNav();
    render();
  }

  function renderNav() {
    const box = $('catnav');
    if (!box) return;
    const sel = state.cat ? nav.by.get(norm(state.cat)) : null;
    // Blatt gewaehlt: Liste der Geschwister zeigen und den Eintrag markieren
    const shown = sel && sel.c.length ? sel : (sel ? sel.parent : null);
    const list = shown ? shown.c : nav.roots;
    let top = sel; while (top?.parent) top = top.parent;
    const entry = n => `<button type="button" class="cat-entry${sel === n ? ' sel' : ''}" data-p="${esc(n.p)}"><span>${esc(n.n)}</span>` +
      (n.count ? `<span class="cat-count" title="${esc(t('cat.listings', { n: int(n.count) }))}">${CLIP}${int(n.count)}</span>`
        : `<span class="cat-count none">${CLIP}${esc(t('cat.none'))}</span>`) + '</button>';
    box.innerHTML = `
      <div class="cat-rail">
        <button type="button" class="${top ? '' : 'on'}" data-p="" title="${esc(t('cat.all'))}">${icon('all')}</button>
        ${nav.roots.map(n => `<button type="button" class="${top === n ? 'on' : ''}" data-p="${esc(n.p)}" title="${esc(n.n)}">${icon(norm(n.p))}</button>`).join('')}
      </div>
      <div class="cat-list${shown ? '' : ' root'}">
        ${shown ? `<button type="button" class="cat-back" data-p="${esc(shown.parent ? shown.parent.p : '')}"><svg viewBox="0 0 16 16" aria-hidden="true"><path d="M10 3L5 8l5 5"/></svg>${esc(t('cat.back'))}</button>` : ''}
        <div class="cat-title">${esc(shown ? shown.n : t('cat.all'))}</div>
        ${list.map(entry).join('')}
      </div>`;
  }
  $('catnav')?.addEventListener('click', e => {
    const b = e.target.closest('button[data-p]');
    if (b) setCat(b.dataset.p);
  });

  async function load() {
    if (!baseTree.length) baseTree = await api('/api/categories').catch(() => []);
    state.rows = await api('/api/items?days=' + $('days').value + gsQuery());
    buildNav();
    renderNav();
    fillSelects();
    render();
  }

  function fillSelects() {
    const tiers = [...new Set(state.rows.map(r => r.tier).filter(t => t != null))].sort();
    const curTier = $('tier').value || params.get('tier') || '';
    $('tier').innerHTML = `<option value="">${esc(t('filter.all_tiers'))}</option>` + tiers.map(n => `<option value="${n}">${esc(t('filter.tier_n', { n }))}</option>`).join('');
    $('tier').value = curTier;
  }

  function filtered() {
    const q = $('q').value.trim().toLowerCase();
    const cat = norm(state.cat), tier = $('tier').value, onlyEmpty = $('onlyEmpty').checked, has = $('has').value;
    return state.rows.filter(r =>
      (!q || r.item_id.toLowerCase().includes(q) || (r.name || '').toLowerCase().includes(q) || (r.category || '').toLowerCase().includes(q) ||
        catLabel(r.category).toLowerCase().includes(q)) &&
      (!cat || norm(r.category) === cat || norm(r.category).startsWith(cat + '/')) &&
      (!tier || String(r.tier) === tier) &&
      (!onlyEmpty || r.shop_price == null) &&
      (!has || (has === 'yes') === (r.listings > 0)));
  }

  function render() {
    const rows = filtered();
    const k = state.sort, d = state.dir;
    rows.sort((a, b) => {
      // Kategorie: Reihenfolge wie im Spiel, darin die Item-Reihenfolge der Gruppe (sonst Tier, Name)
      if (k === 'category') return (rankOf(a.category) - rankOf(b.category) || 0) * d || a.rank - b.rank || (a.tier || 0) - (b.tier || 0) ||
        (a.name || a.item_id).localeCompare(b.name || b.item_id);
      const x = a[k], y = b[k];
      if (x == null && y == null) return a.item_id.localeCompare(b.item_id);
      if (x == null) return 1;
      if (y == null) return -1;
      return (typeof x === 'string' ? x.localeCompare(y) : x - y) * d || a.item_id.localeCompare(b.item_id);
    });
    document.querySelectorAll('#items th').forEach(th => {
      th.classList.toggle('sorted', th.dataset.k === k);
      th.dataset.dir = d > 0 ? '↑' : '↓';
    });
    tbody.innerHTML = rows.map(r => `
      <tr>
        <td class="item" data-id="${esc(r.item_id)}"><div class="item-cell"><span class="mini-icon">${r.icon ? `<img src="${NWCard.iconUrl(r.icon)}" alt="" loading="lazy" onerror="this.remove()">` : ''}</span><span><a href="/item/${encodeURIComponent(r.item_id)}">${esc(r.name || r.item_id)}</a>${r.name && r.name !== r.item_id ? `<span class="iid">${esc(r.item_id)}</span>` : ''}</span></div></td>
        <td class="cat">${esc(catLabel(r.category)).replace(/\//g, '/<wbr>')}</td>
        <td class="num">${tierBadge(r.tier)}</td>
        <td class="num">${r.gs_max ? (r.gs_min === r.gs_max ? r.gs_min : `${r.gs_min}–${r.gs_max}`) : '<span class="muted">–</span>'}</td>
        <td class="num">${r.listings ? int(r.listings) : `<span class="pill muted" title="${esc(t('items.no_listings_title'))}">${esc(t('items.no_listings'))}</span>`}</td>
        <td class="num">${int(r.quantity)}</td>
        <td class="num">${gold(r.min)}</td>
        <td class="num">${gold(r.median)}</td>
        <td class="num">${gold(r.avg_weighted)}</td>
        <td class="num">${gold(r.max)}</td>
        <td class="num">${window.IS_ADMIN ? `<input class="shop ${r.shop_price != null ? 'set' : ''}" data-id="${esc(r.item_id)}"
             value="${r.shop_price != null ? NF.format(r.shop_price) : ''}" placeholder="${r.median != null ? NF.format(r.median) : ''}"
             inputmode="decimal" aria-label="${esc(t('items.shop_for', { item: r.item_id }))}">`
             : `<span class="shop-ro">${r.shop_price != null ? gold(r.shop_price) : '–'}</span>`}</td>
      </tr>`).join('');
    $('count').textContent = t('items.count', { n: int(rows.length), total: int(state.rows.length) });
    $('shopCount').textContent = state.rows.filter(r => r.shop_price != null).length;
    if ($('bulkN')) $('bulkN').textContent = rows.length;
    const p = new URLSearchParams();
    for (const key of ['q', 'tier', 'has']) if ($(key).value) p.set(key, $(key).value);
    if (state.cat) p.set('cat', state.cat);
    if ($('days').value !== '0') p.set('days', $('days').value);
    if ($('gsMin').value) p.set('gs_min', $('gsMin').value);
    if ($('gsMax').value) p.set('gs_max', $('gsMax').value);
    if ($('onlyEmpty').checked) p.set('empty', '1');
    if (state.sort !== 'category') { p.set('sort', state.sort); p.set('dir', state.dir); }
    history.replaceState(null, '', p.toString() ? '?' + p : location.pathname);
  }

  document.querySelectorAll('#items th').forEach(th => th.addEventListener('click', () => {
    if (state.sort === th.dataset.k) state.dir *= -1;
    else { state.sort = th.dataset.k; state.dir = ['name', 'category'].includes(th.dataset.k) ? 1 : -1; }
    render();
  }));
  for (const id of ['q', 'tier', 'onlyEmpty', 'has']) $(id).addEventListener('input', render);
  $('days').addEventListener('change', load);
  let gsTimer;
  for (const id of ['gsMin', 'gsMax']) $(id).addEventListener('input', () => { clearTimeout(gsTimer); gsTimer = setTimeout(load, 350); });

  // Shop-Preis direkt in der Tabelle bearbeiten
  tbody.addEventListener('change', async e => {
    const inp = e.target.closest('input.shop');
    if (!inp) return;
    const v = parsePrice(inp.value);
    if (Number.isNaN(v)) { toast(t('toast.invalid_price')); inp.focus(); return; }
    const row = state.rows.find(r => r.item_id === inp.dataset.id);
    try {
      await saveShop(inp.dataset.id, v, row?.shop_note);
      if (row) row.shop_price = v;
      inp.value = v == null ? '' : NF.format(v);
      inp.classList.toggle('set', v != null);
      inp.classList.add('saved'); setTimeout(() => inp.classList.remove('saved'), 900);
      $('shopCount').textContent = state.rows.filter(r => r.shop_price != null).length;
    } catch (err) { toast(t('toast.save_failed', { msg: err.message })); }
  });
  tbody.addEventListener('keydown', e => {
    if (e.key === 'Enter' && e.target.matches('input.shop')) {
      e.target.blur();
      const next = e.target.closest('tr').nextElementSibling?.querySelector('input.shop');
      next?.focus();
    }
  });

  // Massen-Vorschlag
  $('bulkBtn')?.addEventListener('click', () => $('bulk').showModal());
  $('bulkGo')?.addEventListener('click', async e => {
    e.preventDefault();
    const ids = filtered().map(r => r.item_id);
    try {
      const r = await api('/api/shop-bulk?days=' + $('days').value + gsQuery(), {
        base: $('bulkBase').value, factor: Number($('bulkFactor').value || 1),
        only_empty: $('bulkOnlyEmpty').checked, item_ids: ids });
      $('bulk').close();
      toast(t('bulk.done', { n: r.updated }));
      load();
    } catch (err) { toast(t('toast.error', { msg: err.message })); }
  });

  // Hover-Vorschau: Karte des guenstigsten Angebots
  const cardCache = new Map();
  NWCard.attach(tbody, 'td.item[data-id]', td => {
    const r = state.rows.find(x => x.item_id === td.dataset.id);
    if (!r) return null;
    const key = r.item_id + '|' + r.rep_gs + '|' + r.rep_perks;
    if (!cardCache.has(key)) {
      const q = new URLSearchParams({ gs: r.rep_gs || '', perks: (r.rep_perks || '').split(' ').join(',') });
      cardCache.set(key, api('/api/card/' + encodeURIComponent(r.item_id) + '?' + q).catch(() => null));
    }
    return cardCache.get(key);
  });

  load().catch(err => { tbody.innerHTML = `<tr><td colspan="11" class="err">${esc(t('items.load_failed', { msg: err.message }))}</td></tr>`; });
})();
