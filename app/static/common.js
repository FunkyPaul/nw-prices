// Gemeinsame Helfer
const NF = new Intl.NumberFormat(window.LOCALE, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const NI = new Intl.NumberFormat(window.LOCALE);

// Uebersetzung: t('key', {param: wert})
function t(key, params) {
  let s = (window.STRINGS || {})[key] ?? key;
  if (params) for (const [k, v] of Object.entries(params)) s = s.split('{' + k + '}').join(v);
  return s;
}

// Sprachumschalter: Cookie fuer 1 Jahr setzen und neu laden
document.querySelectorAll('.lang-toggle button[data-lang]').forEach(b => b.addEventListener('click', () => {
  if (b.dataset.lang === window.LANG) return;
  document.cookie = `${window.LANG_COOKIE}=${b.dataset.lang}; path=/; max-age=31536000; SameSite=Lax`;
  location.reload();
}));

function gold(v) { return v == null ? '–' : NF.format(v); }
function int(v) { return v == null ? '–' : NI.format(v); }
function esc(s) {
  return String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}
function tierBadge(tier) { return tier ? `<span class="tier t${tier}">T${tier}</span>` : ''; }

// Preiseingabe passend zur Sprache lesen: EN "1,234.56", DE "1.234,56" (Punkt ohne Komma = Dezimalpunkt)
function parsePrice(s) {
  s = String(s).trim().replace(/\s/g, '');
  if (!s) return null;
  if (window.LANG === 'de') {
    if (s.includes(',')) s = s.replace(/\./g, '').replace(',', '.');
  } else {
    s = s.replace(/,/g, '');
  }
  const v = Number(s);
  return Number.isFinite(v) && v >= 0 ? Math.round(v * 100) / 100 : NaN;
}
function fmtDate(iso) {
  if (!iso) return '–';
  return new Date(iso).toLocaleString(window.LOCALE, { dateStyle: 'short', timeStyle: 'short' });
}
function fmtDay(ts) { return new Date(ts).toLocaleDateString(window.LOCALE); }

async function api(url, body) {
  const opt = body instanceof FormData
    ? { method: 'POST', body, headers: { 'X-NWP': '1' } }
    : body !== undefined
      ? { method: 'POST', body: JSON.stringify(body), headers: { 'X-NWP': '1', 'Content-Type': 'application/json' } }
      : {};
  const r = await fetch(url, opt);
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.error || `HTTP ${r.status}`);
  return data;
}
let toastTimer;
function toast(msg) {
  const el = document.getElementById('toast');
  el.textContent = msg; el.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.hidden = true; }, 2500);
}
function saveShop(itemId, price, note) {
  return api('/api/shop/' + encodeURIComponent(itemId), { price, note });
}

// Kleine SVG-Charts ohne externe Bibliothek
function niceTicks(min, max, n = 5, log = false) {
  if (log) {
    const out = [];
    for (let e = Math.floor(Math.log10(min)); e <= Math.ceil(Math.log10(max)); e++) out.push(10 ** e);
    return out;
  }
  if (min === max) { min -= 1; max += 1; }
  const step0 = (max - min) / n, mag = 10 ** Math.floor(Math.log10(step0));
  const step = [1, 2, 5, 10].map(m => m * mag).find(s => s >= step0);
  const out = [];
  for (let v = Math.ceil(min / step) * step; v <= max + 1e-9; v += step) out.push(+v.toFixed(10));
  return out;
}
function shortNum(v) {
  if (Math.abs(v) >= 1e6) return NI.format(+(v / 1e6).toFixed(1)) + ' ' + t('num.million');
  if (Math.abs(v) >= 1e3) return NI.format(+(v / 1e3).toFixed(1)) + ' ' + t('num.thousand');
  return NI.format(+v.toFixed(2));
}

// Anzeige-Einstellungen (nur in diesem Browser): ausgeblendete Spalten der Item-Uebersicht
const HIDDEN_COLS_KEY = 'nwp_hidden_cols';
function hiddenCols() {
  try {
    const v = JSON.parse(localStorage.getItem(HIDDEN_COLS_KEY) || '[]');
    return Array.isArray(v) ? v.filter(x => typeof x === 'string') : [];
  } catch (e) { return []; }
}
function saveHiddenCols(list) {
  try { localStorage.setItem(HIDDEN_COLS_KEY, JSON.stringify(list)); return true; } catch (e) { return false; }
}

// Abmelden
document.getElementById('logoutBtn')?.addEventListener('click', async () => {
  try { await api('/api/logout', {}); } catch (e) { /* egal */ }
  location.reload();
});

// Server-Auswahl: Cookie fuer 1 Jahr setzen und neu laden
document.getElementById('serverSelect')?.addEventListener('change', e => {
  const v = e.target.value;
  document.cookie = `${window.SERVER_COOKIE}=${v}; path=/; max-age=${v ? 31536000 : 0}; SameSite=Lax`;
  location.reload();
});
