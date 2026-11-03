// Tooltip-Karte im Stil des Spiels (Aufbau nach nw-buddy / Trading-Post-Tooltip)
const NWCard = (() => {
  const RARITY_IDX = { common: 0, uncommon: 1, rare: 2, epic: 3, legendary: 4, artifact: 4 };
  const iconUrl = p => p ? '/icons/' + p.split('/').map(encodeURIComponent).join('/') : '';
  const img = (src, cls) => src ? `<img src="${src}" class="${cls}" alt="" loading="lazy" onerror="this.remove()">` : '';

  function render(c) {
    if (!c) return '';
    const r = c.rarity || 'common';
    const ri = RARITY_IDX[r] ?? 0;
    const head = `
      <div class="nwc-head" style="--head-bg:url(/static/nw/tooltip_header_bg_${ri}.png)">
        <div class="nwc-icon" style="--sq-bg:url(/static/nw/itemraritybgsquare${ri}.png);--sq-border:url(/static/nw/itembgsquare${ri}.png)">
          ${img(iconUrl(c.icon), 'nwc-icon-img')}
          ${c.tier ? `<span class="nwc-tier">${esc(c.tier)}</span>` : ''}
        </div>
        <div class="nwc-title">
          <div class="nwc-name">${esc(c.name)}</div>
          <div class="nwc-rarity">${esc(t('rarity.' + r))}${c.named ? ' • ' + esc(t('card.named')) : ''}</div>
          <div class="nwc-type">${esc(c.type || '')}</div>
        </div>
      </div>`;
    const sections = [];
    if (c.gear_score || c.stats?.length) {
      sections.push(`<div class="nwc-sec">
        ${c.gear_score ? `<div class="nwc-gs"><img src="/static/nw/icon_gearscore.png" alt=""><span>${esc(c.gear_score)}</span></div>` : ''}
        ${(c.stats || []).map((s, i) => `<div class="nwc-stat"${i === 0 && /damage|schaden/i.test(s.label) ? ` title="${esc(t('card.base_damage_hint'))}"` : ''}><b>${esc(s.value)}</b> ${esc(s.label)}</div>`).join('')}
      </div>`);
    }
    if (c.perks?.length) {
      sections.push(`<div class="nwc-sec nwc-perks">${c.perks.map(p => `
        <div class="nwc-perk ${p.socket ? 'gem' : ''} ${p.id ? '' : 'unknown'}">
          <span class="nwc-perk-icon">${p.socket ? '<img src="/static/nw/frame_gemsocket.png" class="sock" alt="">' : ''}${img(iconUrl(p.icon), 'pi')}</span>
          <div>${p.id ? `<b>${esc(p.name)}:</b> ${esc(p.text)}` : `<b>${esc(t('item.unknown_perk', { hash: p.hash }))}</b>`}</div>
        </div>`).join('')}</div>`);
    }
    if (c.description) sections.push(`<div class="nwc-sec nwc-desc">${esc(c.description)}</div>`);
    if (c.info?.length) {
      sections.push(`<div class="nwc-sec nwc-info">${c.info.map(i =>
        `<div>${esc(i.pre)}<b>${esc(i.bold)}</b>${esc(i.post)}</div>`).join('')}</div>`);
    }
    return `<div class="nwc nwc-${r}">${head}<div class="nwc-body">${sections.join('')}</div></div>`;
  }

  // ---------- Schwebender Tooltip, der dem Mauszeiger folgt
  let tip;
  function show(html, ev) {
    if (!tip) { tip = document.createElement('div'); tip.className = 'nwc-float'; document.body.appendChild(tip); }
    tip.innerHTML = html;
    tip.hidden = false;
    move(ev);
  }
  function move(ev) {
    if (!tip || tip.hidden || !ev) return;
    const pad = 18, w = tip.offsetWidth, h = tip.offsetHeight;
    let x = ev.clientX + pad, y = ev.clientY + pad;
    if (x + w > innerWidth - 8) x = ev.clientX - w - pad;
    if (y + h > innerHeight - 8) y = Math.max(8, innerHeight - h - 8);
    tip.style.left = Math.max(8, x) + 'px';
    tip.style.top = y + 'px';
  }
  function hide() { if (tip) tip.hidden = true; }

  // Hover-Tooltip fuer Elemente; getCard(el) liefert Karte oder Promise
  function attach(root, selector, getCard) {
    let current = null;
    root.addEventListener('mouseover', async ev => {
      if (!window.matchMedia('(hover: hover)').matches) return;   // Touch: keine schwebende Vorschau
      const el = ev.target.closest(selector);
      if (!el || el === current) return;
      current = el;
      const c = await getCard(el);
      if (current === el && c) show(render(c), ev);
    });
    root.addEventListener('mousemove', ev => { if (current) move(ev); });
    root.addEventListener('mouseout', ev => {
      const el = ev.target.closest(selector);
      if (el && !el.contains(ev.relatedTarget)) { current = null; hide(); }
    });
  }

  return { render, attach, hide, iconUrl };
})();
