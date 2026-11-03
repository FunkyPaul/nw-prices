"""Web-Oberflaeche fuer die Preisdatenbank (Flask)."""
import collections
import csv
import datetime
import hmac
import io
import json
import os
import re
import secrets
import threading
import time
import urllib.request

from flask import (Flask, Response, abort, g, jsonify, redirect, render_template, request, send_file, session,
                   url_for)
from werkzeug.middleware.proxy_fix import ProxyFix

from . import categories, db, decoder, gamedata, i18n

DB_PATH = os.environ.get('NWP_DB', os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'prices.db'))
# Admin-Zugang (darf alles aendern). Ohne Passwort ist die Weboberflaeche nur lesbar.
USER = os.environ.get('NWP_USER', 'admin')
PASSWORD = os.environ.get('NWP_PASSWORD', '')
# NWP_PRIVATE=1: auch Ansehen nur nach Login (Standard: Seite ist oeffentlich lesbar)
PRIVATE = os.environ.get('NWP_PRIVATE', '').lower() in ('1', 'true', 'yes', 'on')
MAX_UPLOAD_MB = int(os.environ.get('NWP_MAX_UPLOAD_MB', '500'))
# Icons werden vom nw-buddy-CDN geholt und lokal zwischengespeichert. NWP_ICON_CDN=off schaltet das ab.
ICON_CDN = os.environ.get('NWP_ICON_CDN', 'https://cdn.nw-buddy.de/nw-data/live/').strip()
ICON_CACHE = os.environ.get('NWP_ICON_CACHE', os.path.join(os.path.dirname(os.path.abspath(DB_PATH)), 'icons'))
ICON_PATH_RE = re.compile(r'^lyshineui/images/[a-z0-9_./-]+\.(webp|png)$')

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)   # hinter Caddy/nginx


def _secret_key():
    key = os.environ.get('NWP_SECRET_KEY')
    if key:
        return key
    path = os.path.join(os.path.dirname(os.path.abspath(DB_PATH)), 'secret_key')
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not os.path.exists(path):
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as f:
            f.write(secrets.token_hex(32))
    with open(path) as f:
        return f.read().strip()


app.config.update(
    SECRET_KEY=_secret_key(),
    SESSION_COOKIE_NAME='nwp_session',
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    # Hinter HTTPS (Docker/Caddy mit NWP_DOMAIN) nur ueber verschluesselte Verbindungen senden
    SESSION_COOKIE_SECURE=os.environ.get('NWP_COOKIE_SECURE', '1' if os.environ.get('NWP_DOMAIN') else '0') == '1',
    PERMANENT_SESSION_LIFETIME=datetime.timedelta(days=14),
)
if not PASSWORD:
    app.logger.warning(i18n.t('web.no_password', i18n.cli_lang()))
LANG_COOKIE = 'nwp_lang'

# Bremse gegen Passwort-Raten: 5 Fehlversuche je IP in 10 Minuten -> 10 Minuten gesperrt
_fails = collections.defaultdict(collections.deque)
_fails_lock = threading.Lock()
FAIL_WINDOW, FAIL_MAX, FAIL_GLOBAL_MAX = 600, 5, 30


def _client_ip():
    return request.remote_addr or '?'


def _login_blocked(ip):
    now = time.time()
    with _fails_lock:
        for q in list(_fails.values()):
            while q and now - q[0] > FAIL_WINDOW:
                q.popleft()
        total = sum(len(q) for q in _fails.values())
        return len(_fails[ip]) >= FAIL_MAX or total >= FAIL_GLOBAL_MAX


def _login_failed(ip):
    with _fails_lock:
        _fails[ip].append(time.time())


def is_admin():
    return bool(PASSWORD) and session.get('admin') is True and session.get('pw') == _pw_tag()


def _pw_tag():
    # Aendert sich das Passwort in der .env, werden alte Sitzungen ungueltig
    return hmac.new(app.config['SECRET_KEY'].encode(), PASSWORD.encode(), 'sha256').hexdigest()[:16]


def lang():
    return i18n.normalize(request.cookies.get(LANG_COOKIE))


def tr(key, **params):
    return i18n.t(key, lang(), **params)


@app.context_processor
def inject_i18n():
    cur = lang()
    return dict(t=tr, lang=cur, langs=i18n.LANGS, lang_names=i18n.LANG_NAMES,
                locale=i18n.LOCALES[cur], js_strings=i18n.js_strings(cur), lang_cookie=LANG_COOKIE,
                is_admin=is_admin(), login_enabled=bool(PASSWORD),
                servers=db.list_servers(get_db()), server=current_server(), server_cookie=SERVER_COOKIE)
app.config['MAX_CONTENT_LENGTH'] = MAX_UPLOAD_MB * 1024 * 1024


def get_db():
    if 'db' not in g:
        g.db = db.connect(DB_PATH)
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    con = g.pop('db', None)
    if con is not None:
        con.close()


PUBLIC_PATHS = ('/healthz', '/login', '/api/login', '/static/')


@app.before_request
def auth_and_csrf():
    path = request.path
    if request.method not in ('GET', 'HEAD', 'OPTIONS'):
        # Aendernde Anfragen nur per fetch() mit eigenem Header (Schutz gegen CSRF) ...
        if request.headers.get('X-NWP') != '1':
            abort(403)
        # ... und nur als Admin (Login/Logout ausgenommen)
        if path not in ('/api/login', '/api/logout') and not is_admin():
            return jsonify(error=tr('err.admin_required')), 403
        return None
    if PRIVATE and not is_admin() and not path.startswith(PUBLIC_PATHS):
        if path.startswith(('/api/', '/export/', '/icons/')):
            return jsonify(error=tr('auth.required')), 401
        return redirect(url_for('login_page', next=request.full_path.rstrip('?')))
    return None


@app.get('/login')
def login_page():
    nxt = request.args.get('next') or '/'
    if not nxt.startswith('/') or nxt.startswith('//'):
        nxt = '/'
    return render_template('login.html', page='login', next=nxt, private=PRIVATE)


@app.post('/api/login')
def api_login():
    if not PASSWORD:
        return jsonify(error=tr('login.disabled')), 403
    ip = _client_ip()
    if _login_blocked(ip):
        return jsonify(error=tr('login.locked')), 429
    body = request.get_json(force=True, silent=True) or {}
    ok = hmac.compare_digest(str(body.get('user') or ''), USER) & \
        hmac.compare_digest(str(body.get('password') or ''), PASSWORD)
    if not ok:
        _login_failed(ip)
        app.logger.warning('Fehlgeschlagener Admin-Login von %s', ip)
        time.sleep(0.5)
        return jsonify(error=tr('login.failed')), 401
    session.clear()
    session.permanent = True
    session['admin'] = True
    session['pw'] = _pw_tag()
    return jsonify(ok=True)


@app.post('/api/logout')
def api_logout():
    session.clear()
    return jsonify(ok=True)


SERVER_COOKIE = 'nwp_server'


def current_server():
    """Gewaehlter Server (Cookie oder ?server=); None = alle Server."""
    if 'server' not in g:
        raw = request.args.get('server') or request.cookies.get(SERVER_COOKIE) or ''
        g.server = None
        if raw.isdigit():
            g.server = db.get_server(get_db(), int(raw))
    return g.server


def sid():
    srv = current_server()
    return srv['id'] if srv else None


def _int_arg(name):
    try:
        return int(request.args[name])
    except (KeyError, ValueError):
        return None


def _gs():
    return _int_arg('gs_min'), _int_arg('gs_max')


def _days():
    try:
        d = int(request.args.get('days', '0'))
        return d if d > 0 else None
    except ValueError:
        return None


# ---------------------------------------------------------------- Seiten

@app.get('/')
def index():
    return render_template('index.html', summary=db.summary(get_db(), sid()), page='items')


@app.get('/item/<path:item_id>')
def item_page(item_id):
    return render_template('item.html', item_id=item_id, page='items',
                           item_name=gamedata.item_name(item_id, lang()) or item_id)


# Spalten der Item-Uebersicht, die sich ausblenden lassen (Schluessel = data-col in index.html / items.js)
OVERVIEW_COLS = (('icon', 'set.col.icon'), ('itemid', 'set.col.itemid'), ('category', 'set.col.category'),
                 ('tier', 'set.col.tier'), ('gs', 'set.col.gs'), ('listings', 'set.col.listings'),
                 ('quantity', 'set.col.quantity'), ('min', 'set.col.min'), ('median', 'set.col.median'),
                 ('avg', 'set.col.avg'), ('max', 'set.col.max'), ('shop', 'set.col.shop'))


@app.get('/settings')
def settings_page():
    return render_template('settings.html', page='settings', cols=OVERVIEW_COLS)


@app.get('/captures')
def captures_page():
    return render_template('captures.html', captures=db.list_captures(get_db(), sid()), page='captures',
                           max_mb=MAX_UPLOAD_MB)


@app.get('/healthz')
def healthz():
    return 'ok'


def _cached_asset(path, base, cache_dir, magics, max_bytes, mime):
    """Datei aus dem lokalen Cache liefern oder einmalig von base laden (mit 1-Tag-Sperre bei Fehlschlag)."""
    if '..' in path:
        abort(404)
    local = os.path.join(cache_dir, path)
    missing = local + '.missing'
    if not os.path.exists(local):
        if base.lower() in ('', 'off', '0', 'false') or (
                os.path.exists(missing) and time.time() - os.path.getmtime(missing) < 86400):
            abort(404)
        os.makedirs(os.path.dirname(local), exist_ok=True)
        try:
            req = urllib.request.Request(base.rstrip('/') + '/' + path, headers={'User-Agent': 'nw-prices'})
            with urllib.request.urlopen(req, timeout=30) as r:
                blob = r.read(max_bytes + 1)
            if len(blob) > max_bytes or not blob.startswith(magics):
                raise ValueError('unerwarteter Inhalt')
            tmp = local + '.tmp%d.%d' % (os.getpid(), threading.get_ident())
            with open(tmp, 'wb') as f:
                f.write(blob)
            os.replace(tmp, local)
        except Exception as e:
            app.logger.info('Asset nicht verfuegbar: %s (%s)', path, e)
            open(missing, 'w').close()
            abort(404)
    return send_file(local, mimetype=mime, max_age=2592000, conditional=True)


@app.get('/icons/<path:path>')
def icon(path):
    path = path.lower()
    if not ICON_PATH_RE.match(path):
        abort(404)
    mime = 'image/webp' if path.endswith('.webp') else 'image/png'
    return _cached_asset(path, ICON_CDN, ICON_CACHE, (b'RIFF', b'\x89PNG'), 2 * 1024 * 1024, mime)


# ---------------------------------------------------------------- API

def _with_names(rows, cur):
    for r in rows:
        r['name'] = gamedata.item_name(r['item_id'], cur) or r['item_id']
        r['icon'] = (gamedata.item_info(r['item_id']) or {}).get('icon') or ''
        r['rank'] = categories.item_rank(r['item_id'])
    return rows


@app.get('/api/items')
def api_items():
    return jsonify(_with_names(db.item_overview(get_db(), _days(), sid(), *_gs()), lang()))


@app.get('/api/categories')
def api_categories():
    return jsonify(categories.tree(lang()))


@app.get('/api/item/<path:item_id>')
def api_item(item_id):
    cur = lang()
    d = db.item_detail(get_db(), item_id, _days(), sid())
    d['name'] = gamedata.item_name(item_id, cur) or item_id
    for l in d['listings']:
        c = gamedata.card(item_id, l.get('gear_score'), (l.get('perks') or '').split(), cur)
        l['perk_list'] = c['perks']
        l['card'] = c
    d['card'] = gamedata.card(item_id, d['listings'][0]['gear_score'] if d['listings'] else None,
                              (d['listings'][0]['perks'] or '').split() if d['listings'] else [], cur)
    return jsonify(d)


@app.get('/api/card/<path:item_id>')
def api_card(item_id):
    try:
        gs = int(request.args.get('gs') or 0) or None
    except ValueError:
        gs = None
    perks = [p for p in (request.args.get('perks') or '').replace(',', ' ').split() if re.fullmatch(r'[0-9a-f]{8}', p)]
    return jsonify(gamedata.card(item_id, gs, perks[:8], lang()))


def _parse_price(v):
    if v in (None, ''):
        return None
    if isinstance(v, (int, float)):
        p = float(v)
    else:
        p = float(str(v).replace('.', '').replace(',', '.')) if ',' in str(v) else float(v)
    if p < 0:
        raise ValueError
    return round(p, 2)


@app.post('/api/shop/<path:item_id>')
def api_shop(item_id):
    body = request.get_json(force=True, silent=True) or {}
    try:
        price = _parse_price(body.get('price'))
    except ValueError:
        return jsonify(error=tr('err.invalid_price')), 400
    note = (body.get('note') or '').strip() or None
    db.set_shop_price(get_db(), item_id, price, note)
    return jsonify(ok=True, item_id=item_id, price=price, note=note)


@app.post('/api/shop-bulk')
def api_shop_bulk():
    body = request.get_json(force=True, silent=True) or {}
    base = body.get('base', 'median')
    if base not in ('min', 'p25', 'median', 'avg_weighted', 'max'):
        return jsonify(error=tr('err.invalid_base')), 400
    try:
        factor = float(body.get('factor', 1))
    except (TypeError, ValueError):
        return jsonify(error=tr('err.invalid_factor')), 400
    only_empty = bool(body.get('only_empty', True))
    wanted = set(body.get('item_ids') or [])
    con = get_db()
    n = 0
    for o in db.item_overview(con, _days(), sid(), *_gs()):
        if wanted and o['item_id'] not in wanted:
            continue
        if only_empty and o['shop_price'] is not None:
            continue
        if o.get(base) is None:
            continue
        db.set_shop_price(con, o['item_id'], round(max(o[base] * factor, 0.01), 2), o.get('shop_note'))
        n += 1
    return jsonify(ok=True, updated=n)


@app.post('/api/upload')
def api_upload():
    files = request.files.getlist('file')
    if not files:
        return jsonify(error=tr('err.no_file')), 400
    srv_raw = request.form.get('server_id') or ''
    srv = db.get_server(get_db(), int(srv_raw)) if srv_raw.isdigit() else None
    if not srv:
        return jsonify(error=tr('err.server_missing')), 400
    results = []
    for f in files:
        blob = f.read()
        try:
            decoded, meta = decoder.decode_upload(blob, f.filename)
            r = db.import_decoded(get_db(), decoded, meta, request.form.get('name') or None, f.filename, blob,
                                  server_id=srv['id'])
            r['file'] = f.filename
        except decoder.DecodeError as e:
            r = dict(file=f.filename, error=e.message(lang()))
        except Exception as e:  # unerwartetes Format
            r = dict(file=f.filename, error=tr('err.unreadable', type=type(e).__name__))
        results.append(r)
    return jsonify(results=results)


@app.post('/api/captures/<int:cid>/delete')
def api_delete_capture(cid):
    db.delete_capture(get_db(), cid)
    return jsonify(ok=True)


@app.post('/api/captures/<int:cid>/server')
def api_capture_server(cid):
    body = request.get_json(force=True, silent=True) or {}
    srv = db.get_server(get_db(), int(body.get('server_id') or 0))
    if not srv:
        return jsonify(error=tr('err.server_missing')), 400
    db.set_capture_server(get_db(), cid, srv['id'])
    return jsonify(ok=True)


def _server_body():
    body = request.get_json(force=True, silent=True) or {}
    name = str(body.get('name') or '').strip()[:60]
    region = str(body.get('region') or '').strip()[:60]
    return name, region


@app.post('/api/servers')
def api_add_server():
    name, region = _server_body()
    if not name:
        return jsonify(error=tr('err.name_missing')), 400
    if db.find_server(get_db(), name):
        return jsonify(error=tr('err.server_exists')), 400
    return jsonify(ok=True, id=db.add_server(get_db(), name, region))


@app.post('/api/servers/<int:server_id>/update')
def api_update_server(server_id):
    name, region = _server_body()
    if not name:
        return jsonify(error=tr('err.name_missing')), 400
    other = db.find_server(get_db(), name)
    if other and other['id'] != server_id:
        return jsonify(error=tr('err.server_exists')), 400
    db.update_server(get_db(), server_id, name, region)
    return jsonify(ok=True)


@app.post('/api/servers/<int:server_id>/delete')
def api_delete_server(server_id):
    if not db.delete_server(get_db(), server_id):
        return jsonify(error=tr('err.server_in_use')), 400
    return jsonify(ok=True)


@app.post('/api/captures/<int:cid>/rename')
def api_rename_capture(cid):
    name = ((request.get_json(force=True, silent=True) or {}).get('name') or '').strip()
    if not name:
        return jsonify(error=tr('err.name_missing')), 400
    con = get_db()
    with con:
        con.execute('UPDATE captures SET name=? WHERE id=?', (name[:200], cid))
    return jsonify(ok=True)


# ---------------------------------------------------------------- Export

def _csv(rows, fields, filename):
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=fields, extrasaction='ignore', delimiter=';')
    w.writeheader()
    w.writerows(rows)
    return Response('﻿' + buf.getvalue(), mimetype='text/csv',
                    headers={'Content-Disposition': f'attachment; filename={filename}'})


@app.get('/export/shop.json')
def export_shop_json():
    data = json.dumps(db.export_shop(get_db(), sid()), indent=2, ensure_ascii=False)
    return Response(data, mimetype='application/json',
                    headers={'Content-Disposition': 'attachment; filename=shop_prices.json'})


@app.get('/export/shop.csv')
def export_shop_csv():
    rows = db.export_shop(get_db(), sid())
    return _csv(rows, ['item_id', 'name_en', 'name_de', 'shop_price', 'note', 'category', 'tier', 'market_min', 'market_median',
                       'updated_at'], 'shop_prices.csv')


@app.get('/export/items.csv')
def export_items_csv():
    rows = _with_names(db.item_overview(get_db(), _days(), sid(), *_gs()), lang())
    return _csv(rows, ['item_id', 'name', 'category', 'tier', 'gs_min', 'gs_max', 'listings', 'quantity', 'min', 'p25',
                       'median', 'avg_weighted', 'max', 'shop_price', 'shop_note', 'last_seen'], 'items.csv')


@app.get('/export/listings.csv')
def export_listings_csv():
    cur = lang()
    rows = [dict(r) for r in get_db().execute(
        'SELECT o.*, c.name AS capture, s.name AS server FROM observations o JOIN captures c ON c.id=o.capture_id '
        'LEFT JOIN servers s ON s.id = c.server_id WHERE (? IS NULL OR c.server_id = ?) ORDER BY item_id, price',
        (sid(), sid()))]
    for r in rows:
        r['name'] = gamedata.item_name(r['item_id'], cur) or r['item_id']
        r['perk_names'] = ' | '.join(
            p['name'] for p in gamedata.resolve_perks((r['perks'] or '').split(), r['gear_score'], r['item_id'], cur))
    return _csv(rows, ['server', 'capture', 'seen_at', 'contract_id', 'item_id', 'name', 'category', 'tier', 'gear_score',
                       'price', 'quantity', 'listed_at', 'perk_names', 'perks', 'item_hash'], 'listings.csv')
