"""SQLite-Speicher fuer Trading-Post-Beobachtungen."""
import os
import sqlite3
import statistics
import datetime
import hashlib

from . import gamedata

SCHEMA = """
CREATE TABLE IF NOT EXISTS captures (
    id            INTEGER PRIMARY KEY,
    name          TEXT NOT NULL,
    filename      TEXT,
    sha256        TEXT UNIQUE,
    started_at    TEXT,
    stopped_at    TEXT,
    imported_at   TEXT NOT NULL,
    searches      INTEGER DEFAULT 0,
    contracts     INTEGER DEFAULT 0,
    errors        INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS searches (
    id            INTEGER PRIMARY KEY,
    capture_id    INTEGER NOT NULL REFERENCES captures(id) ON DELETE CASCADE,
    time          TEXT,
    filter        TEXT,
    sort          TEXT,
    descending    INTEGER,
    returned      INTEGER,
    total         INTEGER
);
CREATE TABLE IF NOT EXISTS observations (
    id             INTEGER PRIMARY KEY,
    capture_id     INTEGER NOT NULL REFERENCES captures(id) ON DELETE CASCADE,
    seen_at        TEXT NOT NULL,
    contract_id    TEXT NOT NULL,
    item_id        TEXT NOT NULL,
    category       TEXT,
    tier           INTEGER,
    gear_score     INTEGER,
    price          REAL NOT NULL,
    quantity       INTEGER,
    listed_at      TEXT,
    perks          TEXT,
    item_hash      TEXT,
    location_field TEXT,
    UNIQUE (capture_id, contract_id)
);
CREATE INDEX IF NOT EXISTS obs_item ON observations(item_id);
CREATE INDEX IF NOT EXISTS obs_seen ON observations(seen_at);
CREATE TABLE IF NOT EXISTS servers (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE COLLATE NOCASE,
    region      TEXT,
    sort        INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS shop_prices (
    item_id     TEXT PRIMARY KEY,
    price       REAL,
    note        TEXT,
    updated_at  TEXT
);
"""


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')


def connect(path):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    con = sqlite3.connect(path, timeout=30)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA foreign_keys = ON')
    con.execute('PRAGMA journal_mode = WAL')
    con.executescript(SCHEMA)
    _migrate(con)
    return con


DEFAULT_SERVERS = [('Nysa', 'EU Central'), ('Valhalla', 'US East'), ('El Dorado', 'US West'),
                   ('Devaloka', 'SA East'), ('Delos', 'AP Southeast')]


def _migrate(con):
    cols = {r['name'] for r in con.execute('PRAGMA table_info(captures)')}
    with con:
        if 'server_id' not in cols:
            con.execute('ALTER TABLE captures ADD COLUMN server_id INTEGER REFERENCES servers(id)')
        if not con.execute('SELECT 1 FROM servers LIMIT 1').fetchone():
            con.executemany('INSERT INTO servers(name, region, sort) VALUES (?,?,?)',
                            [(n, r, i) for i, (n, r) in enumerate(DEFAULT_SERVERS)])
        # Alte Captures ohne Server gehoeren zum ersten Server (Nysa)
        first = con.execute('SELECT id FROM servers ORDER BY sort, id LIMIT 1').fetchone()
        if first:
            con.execute('UPDATE captures SET server_id=? WHERE server_id IS NULL', (first['id'],))
        con.execute('CREATE INDEX IF NOT EXISTS cap_server ON captures(server_id)')


# ---------------------------------------------------------------- Server

def list_servers(con):
    rows = con.execute('''SELECT s.*, COUNT(c.id) AS captures, MAX(c.started_at) AS last_capture
                          FROM servers s LEFT JOIN captures c ON c.server_id = s.id
                          GROUP BY s.id ORDER BY s.sort, s.id''').fetchall()
    return [dict(r) for r in rows]


def get_server(con, sid):
    r = con.execute('SELECT * FROM servers WHERE id=?', (sid,)).fetchone()
    return dict(r) if r else None


def find_server(con, name):
    r = con.execute('SELECT * FROM servers WHERE name=? COLLATE NOCASE', (name.strip(),)).fetchone()
    return dict(r) if r else None


def add_server(con, name, region):
    with con:
        sort = (con.execute('SELECT MAX(sort) FROM servers').fetchone()[0] or 0) + 1
        cur = con.execute('INSERT INTO servers(name, region, sort) VALUES (?,?,?)',
                          (name.strip(), (region or '').strip() or None, sort))
    return cur.lastrowid


def update_server(con, sid, name, region):
    with con:
        con.execute('UPDATE servers SET name=?, region=? WHERE id=?', (name.strip(), (region or '').strip() or None, sid))


def delete_server(con, sid):
    if con.execute('SELECT 1 FROM captures WHERE server_id=? LIMIT 1', (sid,)).fetchone():
        return False
    with con:
        con.execute('DELETE FROM servers WHERE id=?', (sid,))
    return True


def set_capture_server(con, cid, sid):
    with con:
        con.execute('UPDATE captures SET server_id=? WHERE id=?', (sid, cid))


def import_decoded(con, decoded, meta, name=None, filename=None, blob=None, server_id=None):
    sha = hashlib.sha256(blob).hexdigest() if blob is not None else None
    if sha:
        row = con.execute('SELECT id, name FROM captures WHERE sha256=?', (sha,)).fetchone()
        if row:
            return dict(duplicate=True, capture_id=row['id'], name=row['name'])
    name = name or meta.get('name') or filename or 'Capture'
    errors = sum(r['errors'] for r in decoded['results'])
    if server_id is None:
        server_id = con.execute('SELECT id FROM servers ORDER BY sort, id LIMIT 1').fetchone()['id']
    with con:
        cur = con.execute(
            'INSERT INTO captures(name, filename, sha256, started_at, stopped_at, imported_at, errors, server_id) '
            'VALUES (?,?,?,?,?,?,?,?)',
            (name, filename, sha, meta.get('started_at_utc') or decoded['first_ts'],
             meta.get('stopped_at_utc') or decoded['last_ts'], now_iso(), errors, server_id))
        cid = cur.lastrowid
        n_contracts = 0
        for r in decoded['results']:
            req = r.get('request') or {}
            con.execute(
                'INSERT INTO searches(capture_id, time, filter, sort, descending, returned, total) VALUES (?,?,?,?,?,?,?)',
                (cid, r['time'], req.get('filter'), req.get('sort'), int(bool(req.get('descending'))),
                 len(r['contracts']), r.get('total')))
            for c in r['contracts']:
                if not c['category']:
                    c['category'] = (gamedata.item_info(c['item_id']) or {}).get('path') or ''
                cur = con.execute(
                    'INSERT OR IGNORE INTO observations(capture_id, seen_at, contract_id, item_id, category, tier, '
                    'gear_score, price, quantity, listed_at, perks, item_hash, location_field) '
                    'VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',
                    (cid, r['time'], c['contract_id'], c['item_id'], c['category'], c['tier'], c['gear_score'],
                     c['price'], c['quantity'], c['listed_at'], ' '.join(c['perks']), c['item_hash'],
                     c['location_field']))
                n_contracts += cur.rowcount
        con.execute('UPDATE captures SET searches=?, contracts=? WHERE id=?',
                    (len(decoded['results']), n_contracts, cid))
    started = con.execute('SELECT started_at FROM captures WHERE id=?', (cid,)).fetchone()['started_at']
    return dict(duplicate=False, capture_id=cid, name=name, started_at=started, searches=len(decoded['results']),
                contracts=n_contracts, errors=errors, server=(get_server(con, server_id) or {}).get('name'))


def delete_capture(con, cid):
    with con:
        con.execute('DELETE FROM captures WHERE id=?', (cid,))


# ---------------------------------------------------------------- Abfragen

def _since_clause(days, server_id=None, time_col='o.seen_at'):
    clause, args = '', ()
    if days:
        since = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)).isoformat()
        clause, args = f' AND {time_col} >= ?', (since,)
    if server_id:
        clause += ' AND o.capture_id IN (SELECT id FROM captures WHERE server_id = ?)'
        args += (server_id,)
    return clause, args


def _latest_observations(con, days=None, item_id=None, server_id=None, gs_min=None, gs_max=None):
    """Pro Contract und Server nur die juengste Beobachtung (Doppelzaehlungen ueber Captures vermeiden)."""
    clause, args = '', ()
    if days:
        since = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)).isoformat()
        clause, args = ' AND o.seen_at >= ?', (since,)
    if item_id is not None:
        clause += ' AND o.item_id = ?'
        args += (item_id,)
    if gs_min is not None:
        clause += ' AND o.gear_score >= ?'
        args += (gs_min,)
    if gs_max is not None:
        clause += ' AND o.gear_score <= ?'
        args += (gs_max,)
    inner, inner_args = '', ()
    if server_id:
        clause += ' AND c.server_id = ?'
        args += (server_id,)
        inner, inner_args = ' WHERE c2.server_id = ?', (server_id,)
    if item_id is not None:
        inner += (' AND' if inner else ' WHERE') + ' o2.item_id = ?'
        inner_args += (item_id,)
    sql = f"""
        SELECT o.*, c.server_id FROM observations o
        JOIN captures c ON c.id = o.capture_id
        JOIN (SELECT o2.contract_id AS cid, c2.server_id AS sid, MAX(o2.seen_at) AS m
              FROM observations o2 JOIN captures c2 ON c2.id = o2.capture_id{inner}
              GROUP BY o2.contract_id, c2.server_id) l
          ON l.cid = o.contract_id AND l.sid IS c.server_id AND l.m = o.seen_at
        WHERE 1=1 {clause}
        GROUP BY o.contract_id, c.server_id
    """
    return con.execute(sql, inner_args + args).fetchall()


def _quantile(sorted_vals, q):
    if not sorted_vals:
        return None
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    pos = (len(sorted_vals) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(sorted_vals) - 1)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (pos - lo)


def price_stats(rows):
    prices = sorted(r['price'] for r in rows)
    qty = sum((r['quantity'] or 0) for r in rows)
    wavg = (sum(r['price'] * (r['quantity'] or 0) for r in rows) / qty) if qty else None
    return dict(
        listings=len(rows), quantity=qty,
        min=prices[0] if prices else None, p25=_quantile(prices, .25),
        median=statistics.median(prices) if prices else None,
        avg_weighted=wavg, max=prices[-1] if prices else None)


def item_overview(con, days=None, server_id=None, gs_min=None, gs_max=None):
    rows = _latest_observations(con, days, server_id=server_id, gs_min=gs_min, gs_max=gs_max)
    gs_filtered = gs_min is not None or gs_max is not None
    shop = {r['item_id']: dict(r) for r in con.execute('SELECT * FROM shop_prices')}
    groups = {}
    for r in rows:
        groups.setdefault(r['item_id'], []).append(r)
    out = []
    for item_id, rs in groups.items():
        s = price_stats(rs)
        gs = [r['gear_score'] for r in rs if r['gear_score']]
        cheapest = min(rs, key=lambda r: r['price'])
        s.update(
            rep_gs=cheapest['gear_score'], rep_perks=cheapest['perks'] or '',
            item_id=item_id, category=rs[0]['category'], tier=max(r['tier'] or 0 for r in rs),
            gs_min=min(gs) if gs else None, gs_max=max(gs) if gs else None,
            last_seen=max(r['seen_at'] for r in rs),
            shop_price=shop.get(item_id, {}).get('price'), shop_note=shop.get(item_id, {}).get('note'))
        out.append(s)
    # Items ohne Angebote: im Spiel angeklickt, aber leer (Suche mit 0 Treffern) oder nur mit Shop-Preis
    empty = {}
    clause, args = _since_clause(days, server_id, time_col='o.time')
    for srow in ([] if gs_filtered else con.execute('SELECT filter, MAX(time) AS t FROM searches o WHERE returned = 0 AND filter != \'\''
                            + clause + ' GROUP BY filter', args)):
        for iid in gamedata.items_for_filter(srow['filter']):
            if iid not in groups and (iid not in empty or empty[iid] < srow['t']):
                empty[iid] = srow['t']
    for item_id in ([] if gs_filtered else set(empty) | (set(shop) - set(groups))):
        info = gamedata.item_info(item_id) or {}
        sp = shop.get(item_id, {})
        out.append(dict(item_id=item_id, category=info.get('path'), tier=info.get('tier') or None, listings=0,
                        quantity=0, min=None, p25=None, median=None, avg_weighted=None, max=None, gs_min=None,
                        gs_max=None, last_seen=empty.get(item_id), rep_gs=None, rep_perks='',
                        no_listings=item_id in empty, shop_price=sp.get('price'), shop_note=sp.get('note')))
    out.sort(key=lambda x: ((x['category'] or '~'), x['item_id']))
    return out


def item_detail(con, item_id, days=None, server_id=None):
    rows = [dict(r) for r in _latest_observations(con, days, item_id, server_id)]
    rows.sort(key=lambda r: r['price'])
    cap_server = {r['id']: r['server'] for r in con.execute(
        'SELECT c.id, s.name AS server FROM captures c LEFT JOIN servers s ON s.id = c.server_id')}
    for r in rows:
        r['server'] = cap_server.get(r['capture_id'])
    hist = con.execute(
        """SELECT c.id, c.name, s.name AS server, MIN(o.seen_at) AS seen_at, COUNT(*) AS n, MIN(o.price) AS min,
                  SUM(o.quantity) AS quantity, GROUP_CONCAT(o.price) AS prices
           FROM observations o JOIN captures c ON c.id=o.capture_id LEFT JOIN servers s ON s.id = c.server_id
           WHERE o.item_id=? AND (? IS NULL OR c.server_id = ?) GROUP BY c.id ORDER BY seen_at""",
        (item_id, server_id, server_id)).fetchall()
    history = []
    for h in hist:
        ps = sorted(float(x) for x in h['prices'].split(','))
        history.append(dict(capture_id=h['id'], capture=h['name'], server=h['server'], seen_at=h['seen_at'],
                            listings=h['n'], min=h['min'], median=statistics.median(ps), quantity=h['quantity']))
    # Vergleich ueber alle Server (unabhaengig vom gewaehlten Server)
    by_server = []
    for srv in list_servers(con):
        srows = _latest_observations(con, days, item_id, srv['id'])
        st = price_stats(srows)
        st.update(server_id=srv['id'], server=srv['name'], region=srv['region'],
                  last_seen=max((r['seen_at'] for r in srows), default=None), has_captures=srv['captures'] > 0)
        by_server.append(st)
    shop = con.execute('SELECT * FROM shop_prices WHERE item_id=?', (item_id,)).fetchone()
    return dict(item_id=item_id, stats=price_stats(rows), listings=rows, history=history, by_server=by_server,
                category=rows[0]['category'] if rows else (gamedata.item_info(item_id) or {}).get('path'),
                shop=dict(shop) if shop else None)


def set_shop_price(con, item_id, price, note=None):
    with con:
        if price is None and not note:
            con.execute('DELETE FROM shop_prices WHERE item_id=?', (item_id,))
        else:
            con.execute(
                'INSERT INTO shop_prices(item_id, price, note, updated_at) VALUES (?,?,?,?) '
                'ON CONFLICT(item_id) DO UPDATE SET price=excluded.price, note=excluded.note, '
                'updated_at=excluded.updated_at', (item_id, price, note, now_iso()))


def list_captures(con, server_id=None):
    caps = [dict(r) for r in con.execute(
        '''SELECT c.*, s.name AS server, s.region AS region FROM captures c LEFT JOIN servers s ON s.id = c.server_id
           WHERE (? IS NULL OR c.server_id = ?) ORDER BY c.started_at DESC''', (server_id, server_id))]
    for c in caps:
        c['search_list'] = [dict(s) for s in con.execute(
            'SELECT * FROM searches WHERE capture_id=? ORDER BY time', (c['id'],))]
    return caps


def summary(con, server_id=None):
    w = ' WHERE capture_id IN (SELECT id FROM captures WHERE server_id = ?)' if server_id else ''
    a = (server_id,) if server_id else ()
    q = lambda sql, args=(): con.execute(sql, args).fetchone()[0]
    return dict(captures=q('SELECT COUNT(*) FROM captures' + (' WHERE server_id = ?' if server_id else ''), a),
                contracts=q('SELECT COUNT(DISTINCT contract_id) FROM observations' + w, a),
                item_count=q('SELECT COUNT(DISTINCT item_id) FROM observations' + w, a),
                shop_prices=q('SELECT COUNT(*) FROM shop_prices WHERE price IS NOT NULL'),
                all_captures=q('SELECT COUNT(*) FROM captures'),
                last_capture=q('SELECT MAX(started_at) FROM captures' + (' WHERE server_id = ?' if server_id else ''), a))


def export_shop(con, server_id=None):
    over = {o['item_id']: o for o in item_overview(con, server_id=server_id)}
    out = []
    for r in con.execute('SELECT * FROM shop_prices ORDER BY item_id'):
        o = over.get(r['item_id'], {})
        info = gamedata.item_info(r['item_id']) or {}
        out.append(dict(item_id=r['item_id'], name_en=info.get('name', {}).get('en'),
                        name_de=info.get('name', {}).get('de'), shop_price=r['price'], note=r['note'],
                        category=o.get('category'), tier=o.get('tier'),
                        market_min=o.get('min'), market_median=o.get('median'), updated_at=r['updated_at']))
    return out
