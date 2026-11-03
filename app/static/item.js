(() => {
  const $ = id => document.getElementById(id);
  let data;
  const selected = new Set();   // ausgewaehlte Perk-Hashes
  let cardListing = null;       // Angebot, dessen Karte angezeigt wird
  function showCard(l) {
    cardListing = l;
    $('card').innerHTML = NWCard.render(l ? l.card : data.card);
    document.querySelectorAll('#listings tbody tr[data-i]').forEach(tr =>
      tr.classList.toggle('selected', shown()[+tr.dataset.i] === cardListing));
  }
  const shown = () => selected.size
    ? data.listings.filter(l => [...selected].every(h => (l.perks || '').split(' ').includes(h)))
    : data.listings;

  function perkChip(p) {
    const cls = p.type === 'Gem' ? 'gem' : p.type === 'Inherent' ? 'inherent' : p.id ? '' : 'unknown';
    const title = p.id ? `${p.name}: ${p.text}` : t('item.unknown_perk', { hash: p.hash });
    return `<button type="button" class="perk ${cls} ${selected.has(p.hash) ? 'sel' : ''}" data-h="${esc(p.hash)}" title="${esc(title)}">${esc(p.name)}</button>`;
  }

  function renderListings() {
    const L = shown();
    $('listCount').textContent = selected.size ? `(${L.length} / ${data.listings.length})` : `(${data.listings.length})`;
    document.querySelector('#listings tbody').innerHTML = L.map((l, i) => `
      <tr data-i="${i}" class="${l === cardListing ? 'selected' : ''}">${window.SERVER ? '' : `<td><span class="pill srv-pill">${esc(l.server || '?')}</span></td>`}
        <td class="num">${gold(l.price)}</td><td class="num">${int(l.quantity)}</td>
        <td class="num">${l.gear_score || '–'}</td><td class="num">${tierBadge(l.tier)}</td>
        <td class="perks">${(l.perk_list || []).map(perkChip).join('') || '<span class="muted">–</span>'}</td>
        <td>${fmtDate(l.listed_at)}</td><td class="muted">${fmtDate(l.seen_at)}</td>
      </tr>`).join('');
    const fb = $('perkFilter');
    fb.hidden = !selected.size;
    if (selected.size) {
      const names = [...selected].map(h => data.perkInfo[h]?.name || h).join(', ');
      fb.querySelector('span').textContent = t('item.filter_active', { perks: names });
    }
    document.querySelectorAll('#perkTable tr[data-h]').forEach(tr => tr.classList.toggle('sel', selected.has(tr.dataset.h)));
    drawMain();
  }

  function renderPerkTable() {
    const by = {};
    for (const l of data.listings) for (const p of (l.perk_list || [])) {
      (by[p.hash] ||= { p, listings: [] }).listings.push(l);
    }
    data.perkInfo = Object.fromEntries(Object.entries(by).map(([h, v]) => [h, v.p]));
    const rows = Object.entries(by).map(([h, v]) => {
      const prices = v.listings.map(l => l.price).sort((a, b) => a - b);
      const mid = v.listings.slice().sort((a, b) => (a.gear_score || 0) - (b.gear_score || 0))[Math.floor(v.listings.length / 2)];
      const p = (mid.perk_list || []).find(x => x.hash === h) || v.p;
      return { h, p, n: prices.length, min: prices[0], median: prices.length % 2 ? prices[(prices.length - 1) / 2] : (prices[prices.length / 2 - 1] + prices[prices.length / 2]) / 2 };
    }).sort((a, b) => b.n - a.n || a.min - b.min);
    $('perkPanel').hidden = !rows.length;
    document.querySelector('#perkTable tbody').innerHTML = rows.map(r => `
      <tr data-h="${esc(r.h)}" class="clickable">
        <td>${perkChip(r.p)}${r.p.type ? `<span class="ptype">${esc(t('perktype.' + r.p.type) === 'perktype.' + r.p.type ? r.p.type : t('perktype.' + r.p.type))}</span>` : ''}</td>
        <td class="effect">${esc(r.p.id ? r.p.text : t('item.unknown_perk', { hash: r.h }))}</td>
        <td class="num">${int(r.n)}</td><td class="num">${gold(r.min)}</td><td class="num">${gold(r.median)}</td>
      </tr>`).join('');
  }

  function renderServers() {
    const rows = data.by_server || [];
    document.querySelector('#serverCompare tbody').innerHTML = rows.map(r => `
      <tr class="${window.SERVER === r.server_id ? 'selected' : ''}">
        <td><b>${esc(r.server)}</b>${window.SERVER === r.server_id ? ` <span class="pill">${esc(t('srv.current'))}</span>` : ''}</td>
        <td class="muted">${esc(r.region || '')}</td>
        ${r.listings ? `<td class="num">${int(r.listings)}</td><td class="num">${int(r.quantity)}</td>
          <td class="num">${gold(r.min)}</td><td class="num">${gold(r.median)}</td><td class="num">${gold(r.max)}</td>
          <td class="muted">${fmtDate(r.last_seen)}</td>`
        : `<td colspan="6" class="muted">${esc(r.has_captures ? t('srv.no_listings') : t('srv.no_data'))}</td>`}
      </tr>`).join('');
  }

  function togglePerk(h) {
    if (selected.has(h)) selected.delete(h); else selected.add(h);
    renderListings();
  }

  async function load() {
    data = await api('/api/item/' + encodeURIComponent(ITEM_ID));
    const s = data.stats;
    if (data.category) $('crumbCat').textContent = '› ' + data.category.split('/').join(' › ');
    const tier = data.listings.length ? Math.max(...data.listings.map(l => l.tier || 0)) : null;
    const cards = [
      [t('item.lowest'), gold(s.min), 'gold'], [t('item.p25'), gold(s.p25)], [t('item.median'), gold(s.median)],
      [t('item.avg'), gold(s.avg_weighted)], [t('item.highest'), gold(s.max)],
      [t('item.listings'), int(s.listings)], [t('item.total_qty'), int(s.quantity)], [t('item.tier'), tier ? 'T' + tier : '–'],
    ];
    $('statCards').innerHTML = cards.map(([l, v, c]) => `<div class="stat ${c || ''}"><b>${v}</b><span>${l}</span></div>`).join('');

    if (!window.IS_ADMIN) {
      $('shopView').innerHTML = data.shop?.price != null
        ? `<b class="shop-ro">${gold(data.shop.price)}</b>${data.shop.note ? ` <span class="muted">– ${esc(data.shop.note)}</span>` : ''}`
        : `<span class="muted">${esc(t('item.shop_none'))}</span>`;
    } else if (data.shop) {
      $('shopPrice').value = data.shop.price != null ? NF.format(data.shop.price) : '';
      $('shopNote').value = data.shop.note || '';
    }
    const sug = [[t('col.min'), s.min], ['P25', s.p25], [t('col.median'), s.median], ['Ø', s.avg_weighted]].filter(x => x[1] != null);
    if ($('suggest')) $('suggest').innerHTML = sug.length ? esc(t('item.use')) + ' ' + sug.map(([l, v]) =>
      `<button class="ghost" data-v="${v}">${esc(l)} ${gold(v)}</button>`).join(' ') : esc(t('item.no_market'));

    renderServers();
    renderPerkTable();
    renderListings();
    showCard(data.listings[0] || null);

    drawHistory();
  }

  function shopPrice() { return data.shop?.price ?? null; }

  // Gear: Preis über Gear Score. Sonst: Angebotstiefe (kumulierte Menge bis Preis X).
  function drawMain() {
    const L = shown();
    $('chartPanel').hidden = !L.length;
    if (!L.length) return;
    const isGear = L.some(l => l.gear_score > 0);
    const W = 900, H = 300, m = { l: 70, r: 20, t: 15, b: 40 };
    const iw = W - m.l - m.r, ih = H - m.t - m.b;
    let svg = '';
    const gsVaries = new Set(L.map(l => l.gear_score)).size > 1;
    if (isGear) {
      const byGs = isGear && gsVaries;
      $('chartTitle').textContent = byGs ? t('chart.by_gs') : t('chart.ladder');
      const xs = L.map((l, i) => byGs ? l.gear_score : i + 1), ys = L.map(l => l.price);
      const xOf = (l, i) => byGs ? l.gear_score : i + 1;
      let x0 = Math.min(...xs), x1 = Math.max(...xs);
      if (x0 === x1) { const d = byGs ? 10 : 1; x0 -= d; x1 += d; }
      const pad = (x1 - x0) * 0.03; x0 -= pad; x1 += pad;
      const sp = shopPrice();
      let y0 = Math.min(...ys, sp ?? Infinity), y1 = Math.max(...ys, sp ?? -Infinity);
      const log = y1 / Math.max(y0, 0.01) > 30;
      if (log) { y0 = Math.max(y0, 0.01); } else { y0 = 0; y1 *= 1.05; }
      const fx = v => m.l + (v - x0) / (x1 - x0) * iw;
      const ly = v => Math.log10(Math.max(v, 0.01));
      const fy = log ? v => m.t + ih - (ly(v) - ly(y0)) / (ly(y1) - ly(y0) || 1) * ih
                     : v => m.t + ih - v / (y1 || 1) * ih;
      for (const tk of niceTicks(y0, y1, 5, log)) {
        if (tk < y0 * 0.999 || tk > y1 * 1.001) continue;
        svg += `<line class="gridline" x1="${m.l}" x2="${W - m.r}" y1="${fy(tk)}" y2="${fy(tk)}"/><text x="${m.l - 8}" y="${fy(tk) + 4}" text-anchor="end">${shortNum(tk)}</text>`;
      }
      for (const tk of niceTicks(x0, x1, 8)) if (byGs || (Number.isInteger(tk) && tk >= 1 && tk <= L.length)) svg += `<text x="${fx(tk)}" y="${H - m.b + 18}" text-anchor="middle">${tk}</text>`;
      svg += `<text x="${m.l + iw / 2}" y="${H - 4}" text-anchor="middle">${esc(byGs ? t('chart.gs') : t('chart.listing_no'))}${log ? esc(t('chart.log')) : ''}</text>`;
      if (sp != null) svg += `<line class="shopline" x1="${m.l}" x2="${W - m.r}" y1="${fy(sp)}" y2="${fy(sp)}"><title>${esc(t('chart.shop_line', { price: gold(sp) }))}</title></line>`;
      L.forEach((l, i) => { svg += `<circle class="dot" cx="${fx(xOf(l, i))}" cy="${fy(l.price)}" r="5"><title>${esc(t('chart.dot', { price: gold(l.price), gs: l.gear_score ? ' · GS ' + l.gear_score : '', qty: int(l.quantity), perks: (l.perk_list || []).length }))}${(l.perk_list || []).length ? '\n' + esc((l.perk_list || []).map(p => p.name).join(', ')) : ''}</title></circle>`; });
    } else {
      $('chartTitle').textContent = t('chart.depth');
      if (L[0].price === L[L.length - 1].price) {
        $('chartTitle').textContent = t('chart.all_same', { n: int(L.length), price: gold(L[0].price) });
        $('chart').innerHTML = '';
        return;
      }
      let cum = 0;
      const pts = L.map(l => ({ p: l.price, q: (cum += (l.quantity || 0)) }));
      const x0 = 0, x1 = Math.max(...pts.map(p => p.p), shopPrice() ?? 0) || 1;
      const xl = v => x1 < 10 ? gold(v) : shortNum(v);
      const y1 = cum || 1;
      const fx = v => m.l + (v - x0) / (x1 - x0) * iw, fy = v => m.t + ih - v / y1 * ih;
      for (const tk of niceTicks(0, y1, 5)) svg += `<line class="gridline" x1="${m.l}" x2="${W - m.r}" y1="${fy(tk)}" y2="${fy(tk)}"/><text x="${m.l - 8}" y="${fy(tk) + 4}" text-anchor="end">${shortNum(tk)}</text>`;
      for (const tk of niceTicks(0, x1, 8)) svg += `<text x="${fx(tk)}" y="${H - m.b + 18}" text-anchor="middle">${xl(tk)}</text>`;
      svg += `<text x="${m.l + iw / 2}" y="${H - 4}" text-anchor="middle">${esc(t('chart.unit_price'))}</text>`;
      let d = `M${fx(pts[0].p)},${fy(0)}`, prev = 0;
      for (const p of pts) { d += ` L${fx(p.p)},${fy(prev)} L${fx(p.p)},${fy(p.q)}`; prev = p.q; }
      svg += `<path class="line" d="${d}"/>`;
      for (const p of pts) svg += `<circle class="dot" cx="${fx(p.p)}" cy="${fy(p.q)}" r="3.5"><title>${esc(t('chart.up_to', { price: gold(p.p), qty: int(p.q) }))}</title></circle>`;
      const sp = shopPrice();
      if (sp != null) svg += `<line class="shopline" x1="${fx(sp)}" x2="${fx(sp)}" y1="${m.t}" y2="${m.t + ih}"><title>${esc(t('chart.shop_line', { price: gold(sp) }))}</title></line>`;
    }
    svg += `<line class="axis" x1="${m.l}" x2="${W - m.r}" y1="${m.t + ih}" y2="${m.t + ih}"/>`;
    $('chart').innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="img">${svg}</svg>`;
  }

  function drawHistory() {
    const h = data.history;
    if (h.length < 2) { $('historyPanel').hidden = true; return; }
    $('historyPanel').hidden = false;
    const W = 900, H = 240, m = { l: 70, r: 20, t: 15, b: 40 };
    const iw = W - m.l - m.r, ih = H - m.t - m.b;
    const ts = h.map(x => new Date(x.seen_at).getTime());
    const t0 = Math.min(...ts), t1 = Math.max(...ts);
    const ys = h.flatMap(x => [x.min, x.median]);
    const y1 = Math.max(...ys) * 1.1 || 1;
    const fx = t => m.l + (t - t0) / ((t1 - t0) || 1) * iw, fy = v => m.t + ih - v / y1 * ih;
    let svg = '';
    for (const tk of niceTicks(0, y1, 4)) svg += `<line class="gridline" x1="${m.l}" x2="${W - m.r}" y1="${fy(tk)}" y2="${fy(tk)}"/><text x="${m.l - 8}" y="${fy(tk) + 4}" text-anchor="end">${shortNum(tk)}</text>`;
    const path = k => h.map((x, i) => `${i ? 'L' : 'M'}${fx(ts[i])},${fy(x[k])}`).join(' ');
    svg += `<path class="line" d="${path('min')}"/><path class="line2" d="${path('median')}"/>`;
    h.forEach((x, i) => {
      svg += `<circle class="dot" cx="${fx(ts[i])}" cy="${fy(x.min)}" r="4"><title>${esc(t('chart.hist_dot', { capture: x.capture, min: gold(x.min), median: gold(x.median), n: x.listings }))}</title></circle>`;
      const anchor = i === 0 ? 'start' : i === h.length - 1 ? 'end' : 'middle';
      svg += `<text x="${fx(ts[i])}" y="${H - m.b + 18}" text-anchor="${anchor}">${fmtDay(ts[i])}</text>`;
    });
    svg += `<text x="${W - m.r}" y="${m.t + 10}" text-anchor="end"><tspan fill="#d9a845">— ${esc(t('col.min'))}</tspan>  <tspan fill="#8fc0f0">— ${esc(t('col.median'))}</tspan></text>`;
    $('history').innerHTML = `<svg viewBox="0 0 ${W} ${H}">${svg}</svg>`;
  }

  async function save() {
    const v = parsePrice($('shopPrice').value);
    if (Number.isNaN(v)) { toast(t('toast.invalid_price')); return; }
    try {
      await saveShop(ITEM_ID, v, $('shopNote').value);
      data.shop = { price: v, note: $('shopNote').value };
      $('shopPrice').value = v == null ? '' : NF.format(v);
      toast(v == null ? t('toast.shop_removed') : t('toast.shop_saved', { price: gold(v) }));
      drawMain();
    } catch (e) { toast(t('toast.error', { msg: e.message })); }
  }
  document.addEventListener('click', e => {
    const chip = e.target.closest('button.perk[data-h]');
    const row = e.target.closest('#perkTable tr[data-h]');
    const lrow = e.target.closest('#listings tr[data-i]');
    if (chip) togglePerk(chip.dataset.h);
    else if (row) togglePerk(row.dataset.h);
    else if (lrow) { showCard(shown()[+lrow.dataset.i]); NWCard.hide(); }
  });
  NWCard.attach(document.querySelector('#listings tbody'), 'tr[data-i]', tr => {
    const l = shown()[+tr.dataset.i];
    return l && l !== cardListing ? l.card : null;
  });
  $('perkFilterClear').addEventListener('click', () => { selected.clear(); renderListings(); });
  $('shopSave')?.addEventListener('click', save);
  $('shopPrice')?.addEventListener('keydown', e => { if (e.key === 'Enter') save(); });
  $('suggest')?.addEventListener('click', e => {
    const b = e.target.closest('button[data-v]');
    if (b) { $('shopPrice').value = NF.format(+b.dataset.v); save(); }
  });

  load().catch(e => toast(t('toast.load_failed', { msg: e.message })));
})();
