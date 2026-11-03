(() => {
  const tbody = document.querySelector('#items tbody');
  if (!tbody) return;
  const $ = id => document.getElementById(id);
  const state = { rows: [], sort: 'category', dir: 1 };

  // Filter in der URL merken, damit Links/Lesezeichen funktionieren
  const params = new URLSearchParams(location.search);
  for (const k of ['q', 'cat', 'tier', 'days', 'has']) if (params.get(k)) $(k).value = params.get(k);
  if (params.get('gs_min')) $('gsMin').value = params.get('gs_min');
  if (params.get('gs_max')) $('gsMax').value = params.get('gs_max');
  const gsQuery = () => ($('gsMin').value ? '&gs_min=' + encodeURIComponent($('gsMin').value) : '') + ($('gsMax').value ? '&gs_max=' + encodeURIComponent($('gsMax').value) : '');
  $('onlyEmpty').checked = params.get('empty') === '1';
  if (params.get('sort')) { state.sort = params.get('sort'); state.dir = params.get('dir') === '-1' ? -1 : 1; }

  async function load() {
    state.rows = await api('/api/items?days=' + $('days').value + gsQuery());
    fillSelects();
    render();
  }

  function fillSelects() {
    const cats = new Set();
    for (const r of state.rows) {
      if (!r.category) continue;
      const parts = r.category.split('/');
      for (let i = 1; i <= parts.length; i++) cats.add(parts.slice(0, i).join('/'));
    }
    const curCat = $('cat').value || params.get('cat') || '';
    $('cat').innerHTML = `<option value="">${esc(t('filter.all_categories'))}</option>` + [...cats].sort().map(c => {
      const depth = c.split('/').length - 1;
      return `<option value="${esc(c)}">${' '.repeat(depth)}${esc(c.split('/').pop())}</option>`;
    }).join('');
    $('cat').value = curCat;
    const tiers = [...new Set(state.rows.map(r => r.tier).filter(t => t != null))].sort();
    const curTier = $('tier').value || params.get('tier') || '';
    $('tier').innerHTML = `<option value="">${esc(t('filter.all_tiers'))}</option>` + tiers.map(n => `<option value="${n}">${esc(t('filter.tier_n', { n }))}</option>`).join('');
    $('tier').value = curTier;
  }

  function filtered() {
    const q = $('q').value.trim().toLowerCase();
    const cat = $('cat').value, tier = $('tier').value, onlyEmpty = $('onlyEmpty').checked, has = $('has').value;
    return state.rows.filter(r =>
      (!q || r.item_id.toLowerCase().includes(q) || (r.name || '').toLowerCase().includes(q) || (r.category || '').toLowerCase().includes(q)) &&
      (!cat || (r.category || '') === cat || (r.category || '').startsWith(cat + '/')) &&
      (!tier || String(r.tier) === tier) &&
      (!onlyEmpty || r.shop_price == null) &&
      (!has || (has === 'yes') === (r.listings > 0)));
  }

  function render() {
    const rows = filtered();
    const k = state.sort, d = state.dir;
    rows.sort((a, b) => {
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
        <td class="cat">${esc(r.category || '').replace(/\//g, '/<wbr>')}</td>
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
    for (const key of ['q', 'cat', 'tier', 'has']) if ($(key).value) p.set(key, $(key).value);
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
  for (const id of ['q', 'cat', 'tier', 'onlyEmpty', 'has']) $(id).addEventListener('input', render);
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
