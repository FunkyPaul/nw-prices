"""
Decoder fuer New-World-Captures (ledger.bin aus dem nw_capture-Tool).

Reverse-engineertes Format:
  Datei   = Records: "NWDL" | u64 LE ts_ms | u32 dir | u32 | u32 | u32 LE len | payload
            dir 1 = Client->Server, dir 0 = Server->Client
  Payload = u8 (0x80 roh / 0x81 LZ4-Block) | u8 | u16 BE seq | body
  Body    = Chunks: u8 flags | u16 BE len | [u8 ch, 0x20] | [u16 frag, 0x04] | [u16 seq, nicht 0x08] | u16 | data
  Kanal 0 = RPCs, 1 = Replikation, 3 = ACKs. Fragmente (0x04) zaehlen bis 2 herunter.
  RPC     = 00 01 | u16 LE (index<<2 | flags) | u64 component | u64 entity | args
            864  = Trading-Post-Suche (Client->Server)
            2538 = ContractsComponentClientFacet_OnSearchContracts (Server->Client)
"""
import io
import struct
import zipfile
import datetime
import collections

try:  # optional, deutlich schneller
    import lz4.block as _lz4
except Exception:  # pragma: no cover
    _lz4 = None

RPC_SEARCH_REQUEST = 864
RPC_SEARCH_RESULT = 2538
CONTRACT_TAG = b'\x01\xaf\x2e'
TAIL_MARK = bytes.fromhex('00' 'ffffffff' '00000033' '0000')
SORT_FIELDS = {1: 'price', 7: 'gear_score'}


class DecodeError(Exception):
    """Fehler mit Uebersetzungsschluessel (siehe i18n.py) fuer die Anzeige."""

    def __init__(self, key, **params):
        self.key, self.params = key, params
        super().__init__(key)

    def message(self, lang='en'):
        from .i18n import t
        return t(self.key, lang, **self.params)

    def __str__(self):
        return self.message('en')


# ---------------------------------------------------------------- LZ4

def _lz4_py(src):
    i, out, n = 0, bytearray(), len(src)
    while i < n:
        t = src[i]; i += 1
        ll = t >> 4
        if ll == 15:
            while True:
                b = src[i]; i += 1; ll += b
                if b != 255:
                    break
        out += src[i:i + ll]; i += ll
        if i >= n:
            break
        off = src[i] | (src[i + 1] << 8); i += 2
        if off == 0 or off > len(out):
            raise ValueError('LZ4: invalid offset')
        ml = (t & 15)
        if ml == 15:
            while True:
                b = src[i]; i += 1; ml += b
                if b != 255:
                    break
        ml += 4
        start = len(out) - off
        if off >= ml:
            out += out[start:start + ml]
        else:
            for k in range(ml):
                out.append(out[start + k])
    return bytes(out)


def lz4_block(src):
    if _lz4 is not None:
        try:
            return _lz4.decompress(src, uncompressed_size=1 << 20)
        except Exception:
            pass
    return _lz4_py(src)


# ---------------------------------------------------------------- Transport

def read_records(data):
    off = 0
    while off + 28 <= len(data):
        if data[off:off + 4] != b'NWDL':
            if off == 0:
                raise DecodeError('err.not_capture')
            raise DecodeError('err.corrupt', off=f'{off:#x}')
        ts, direction, _a, _b, ln = struct.unpack_from('<QIIII', data, off + 4)
        yield dict(off=off, ts=ts, dir=direction, payload=data[off + 28:off + 28 + ln])
        off += 28 + ln


def read_chunks(records, stats):
    last_ch = {}
    for r in records:
        p = r['payload']
        if len(p) < 4 or p[0] not in (0x80, 0x81):
            stats['skipped_packets'] += 1
            continue
        try:
            body = p[4:] if p[0] == 0x80 else lz4_block(p[4:])
        except Exception:
            stats['skipped_packets'] += 1
            continue
        j = 0
        while j + 5 <= len(body):
            t = body[j]
            ln = struct.unpack_from('>H', body, j + 1)[0]
            k = j + 3
            ch = frag = None
            if t & 0x20:
                ch = body[k]; k += 1
            if t & 0x04:
                frag = struct.unpack_from('>H', body, k)[0]; k += 2
            if not t & 0x08:
                k += 2
            k += 2
            if ch is None:
                ch = 0 if t & 0x01 else last_ch.get(r['dir'])
            last_ch[r['dir']] = ch
            data = body[k:k + ln]
            if len(data) != ln:
                stats['truncated_chunks'] += 1
                break
            yield dict(ts=r['ts'], dir=r['dir'], flags=t, ch=ch, frag=frag, data=data, off=r['off'])
            j = k + ln


def reassemble(chunks):
    pending = collections.defaultdict(list)
    for c in chunks:
        key = (c['dir'], c['ch'])
        if c['flags'] & 0x04:
            pending[key].append(c)
            continue
        parts = pending.pop(key, []) + [c]
        yield dict(dir=c['dir'], ch=c['ch'], ts=parts[0]['ts'], off=parts[0]['off'],
                   nfrag=len(parts), data=b''.join(x['data'] for x in parts))


def find_rpc(data, wanted=(RPC_SEARCH_REQUEST, RPC_SEARCH_RESULT), max_off=48):
    """RPC-Kopf '00 01 <u16 LE index<<2>' nahe am Nachrichtenanfang suchen."""
    for j in range(0, min(max_off, len(data) - 20)):
        if data[j] == 0 and data[j + 1] == 1:
            idx = struct.unpack_from('<H', data, j + 2)[0] >> 2
            if idx in wanted:
                return j, idx
    return None, None


# ---------------------------------------------------------------- Trading Post

def _ns_iso(ns):
    try:
        return datetime.datetime.fromtimestamp(ns / 1e9, datetime.timezone.utc).isoformat(timespec='seconds')
    except Exception:
        return None


def _ms_iso(ms):
    return datetime.datetime.fromtimestamp(ms / 1000, datetime.timezone.utc).isoformat(timespec='milliseconds')


def _read_strings(buf, k, limit=8):
    out = []
    while k < len(buf) and 0 < buf[k] < 96 and len(out) < limit:
        n = buf[k]
        s = buf[k + 1:k + 1 + n]
        if len(s) != n or not all(32 <= b < 127 for b in s):
            break
        out.append(s.decode()); k += 1 + n
    return out, k


def _read_fixed_strings(buf, k, count):
    out = []
    for _ in range(count):
        if k >= len(buf):
            return None, k
        n = buf[k]
        s = buf[k + 1:k + 1 + n]
        if n >= 96 or len(s) != n or not all(32 <= b < 127 for b in s):
            return None, k
        out.append(s.decode()); k += 1 + n
    return out, k


def parse_contract(rec):
    """rec beginnt mit '01 af 2e' + 16-Byte-Contract-GUID."""
    c = {'contract_id': rec[3:19].hex()}
    c['contract_field'] = struct.unpack_from('>I', rec, 0x13)[0]
    c['listed_at'] = _ns_iso(struct.unpack_from('>Q', rec, 0x1b)[0])
    c['location_field'] = rec[0x33:0x39].hex()
    # Immer 4 laengenpraefixierte Texte: Kategorie, Familie, Gruppe, Item-ID (einzelne koennen leer sein)
    strs, k = _read_fixed_strings(rec, 0x90, 4)
    if not strs or not strs[-1]:
        strs = None
        for start in range(0x40, min(len(rec) - 8, 0x200)):  # Layout weicht ab: Stringblock suchen
            cand, k2 = _read_strings(rec, start)
            if len(cand) >= 2:
                strs, k = cand, k2
                break
    if not strs or not strs[-1]:
        raise ValueError('no item strings')
    c['category'] = '/'.join(x for x in strs[:-1] if x)
    c['item_id'] = strs[-1]
    c['gear_score'], c['tier'] = struct.unpack_from('>II', rec, k)
    t = rec.rfind(TAIL_MARK)
    if t < 18:
        raise ValueError('price block not found')
    price, qty, ihash, gs2, qty2 = struct.unpack_from('>IIIHI', rec, t - 18)
    if gs2 != c['gear_score'] or qty2 != qty:
        raise ValueError('consistency check failed')
    c['price'] = price / 100           # pro Stueck, in Gold
    c['quantity'] = qty
    c['item_hash'] = f'{ihash:08x}'
    pk = t + len(TAIL_MARK)
    n = rec[pk] if pk < len(rec) else 0
    c['perks'] = [rec[pk + 1 + 4 * i: pk + 5 + 4 * i].hex() for i in range(min(n, 16))]
    return c


def parse_search_result(data, rpc_off):
    p = rpc_off + 4 + 8 + 8
    out = dict(request_guid=data[p:p + 16].hex(), count=data[p + 16], contracts=[], errors=0)
    try:
        out['total'] = struct.unpack_from('>I', data, len(data) - 13)[0]
    except struct.error:
        out['total'] = None
    starts, j = [], p + 17
    while (j := data.find(CONTRACT_TAG, j)) >= 0:
        starts.append(j); j += 3
    ends = starts[1:] + [len(data) - 13]
    seen = set()
    for a, b in zip(starts, ends):
        try:
            c = parse_contract(data[a:b])
        except Exception:
            out['errors'] += 1
            continue
        if c['contract_id'] not in seen:
            seen.add(c['contract_id'])
            out['contracts'].append(c)
    return out


def parse_search_request(data, rpc_off):
    p = rpc_off + 4 + 8 + 8
    r = dict(request_guid=data[-16:].hex(), filter='', sort=None, descending=None, page_size=None, paged=False)
    try:
        # u32 Sortierung | u16 Laenge + Blaetter-Token (ab Seite 2) | u16 | u16 Seitengroesse | u8 absteigend | 9 Bytes | Filter
        sort_id, clen = struct.unpack_from('>IH', data, p)
        q = p + 6 + clen
        _z, page_size, desc = struct.unpack_from('>HHB', data, q)
        strs, _ = _read_strings(data, q + 14)
        r.update(filter='/'.join(strs), sort=SORT_FIELDS.get(sort_id, str(sort_id)),
                 descending=bool(desc), page_size=page_size, paged=clen > 0)
    except Exception:
        pass
    return r


def decode_ledger(data):
    stats = collections.Counter()
    records = list(read_records(data))
    if not records:
        raise DecodeError('err.empty')
    requests, results = {}, []
    for m in reassemble(read_chunks(records, stats)):
        stats['messages'] += 1
        if m['ch'] != 0:
            continue
        off, idx = find_rpc(m['data'])
        if idx == RPC_SEARCH_REQUEST and m['dir'] == 1:
            r = parse_search_request(m['data'], off)
            r['time'] = _ms_iso(m['ts'])
            requests[r['request_guid']] = r
        elif idx == RPC_SEARCH_RESULT and m['dir'] == 0:
            r = parse_search_result(m['data'], off)
            r.update(time=_ms_iso(m['ts']), ledger_offset=m['off'], size=len(m['data']))
            stats['contract_errors'] += r['errors']
            results.append(r)
    for r in results:
        r['request'] = requests.get(r['request_guid'])
    return dict(
        first_ts=_ms_iso(records[0]['ts']), last_ts=_ms_iso(records[-1]['ts']),
        records=len(records), requests=len(requests), results=results, stats=dict(stats))


def decode_upload(blob, filename=''):
    """Akzeptiert Capture-ZIP oder nackte ledger.bin. Gibt (decoded, metadata) zurueck."""
    meta = {}
    if blob[:4] == b'PK\x03\x04':
        with zipfile.ZipFile(io.BytesIO(blob)) as z:
            names = {n.rsplit('/', 1)[-1]: n for n in z.namelist()}
            if 'ledger.bin' not in names:
                raise DecodeError('err.zip_no_ledger')
            if 'metadata.json' in names:
                import json
                try:
                    meta = json.loads(z.read(names['metadata.json']))
                except Exception:
                    meta = {}
            ledger = z.read(names['ledger.bin'])
    else:
        ledger = blob
    return decode_ledger(ledger), meta
