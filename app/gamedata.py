"""Spieldaten (aus nw-buddy): Item-Namen und Perks inkl. ausgerechneter Werte."""
import ast
import gzip
import json
import math
import operator
import re
from functools import lru_cache
from pathlib import Path

DIR = Path(__file__).resolve().parent / 'gamedata'


@lru_cache(maxsize=None)
def _load(name):
    path = DIR / f'{name}.json.gz'
    if not path.exists():
        return {}
    with gzip.open(path, 'rt', encoding='utf-8') as f:
        return json.load(f)


def perks():
    return _load('perks')


def items():
    return _load('items')


def categories():
    return _load('categories')


def available():
    return bool(perks())


# ---------------------------------------------------------------- Items

def item_info(item_id):
    return items().get((item_id or '').lower())


@lru_cache(maxsize=1)
def _by_path():
    idx = {}
    for key, it in items().items():
        if it.get('path'):
            idx.setdefault(it['path'].lower(), []).append(it['id'])
    return idx


def items_for_filter(filter_path):
    """Item-IDs, die eine Trading-Post-Suche mit diesem Filter zeigen wuerde (Gruppe oder einzelnes Item)."""
    segs = [x for x in (filter_path or '').split('/') if x]
    if not segs:
        return []
    last = item_info(segs[-1])
    if last and len(segs) >= 2:
        return [last['id']]
    if len(segs) >= 3:   # nur Gruppen aufloesen, nicht ganze Kategorien
        return list(_by_path().get('/'.join(segs).lower(), []))
    return []


def item_name(item_id, lang):
    it = item_info(item_id)
    return (it['name'].get(lang) or it['name'].get('en')) if it else None


# ---------------------------------------------------------------- Perk-Multiplikator (wie nw-buddy / Spiel)

def _parse_scaling(value):
    out = []
    for i, part in enumerate(str(value).split(',')):
        if ':' in part:
            gs, rate = part.split(':', 1)
            out.append((float(gs), float(rate)))
        else:
            out.append((100.0, float(part)))
    return out


def perk_multiplier(perk, gear_score, gs_bonus=0):
    s = perk.get('scaling')
    if not s:
        return 1.0
    try:
        ranges = _parse_scaling(s)
    except ValueError:
        return 1.0
    gear_score = gear_score or 0
    result, bonus_rate = 0.0, 0.0
    for i, (start, rate) in enumerate(ranges):
        if start > gear_score:
            continue
        end = ranges[i + 1][0] if i + 1 < len(ranges) else gear_score
        result += max(0.0, min(gear_score, end) - start) * rate
        if rate:
            bonus_rate = rate
    return 1.0 + result + (gs_bonus or 0) * bonus_rate


def gs_bonus_for(perk, item_classes):
    for cls in item_classes or ():
        if cls in perk.get('gs_bonus', {}):
            return perk['gs_bonus'][cls]
    return 0


# ---------------------------------------------------------------- Ausdruecke {[0.01 * 100 * {perkMultiplier}]}

_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
        ast.USub: operator.neg, ast.UAdd: operator.pos, ast.Pow: operator.pow}


def _eval(node):
    if isinstance(node, ast.Expression):
        return _eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval(node.left), _eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval(node.operand))
    raise ValueError('unsupported expression')


def _fmt(v, lang):
    # Das Spiel schneidet auf eine Nachkommastelle ab (11.06 -> "11", 6.91 -> "6.9")
    v = math.floor(abs(v) * 10 + 1e-6) / 10 * (1 if v >= 0 else -1)
    s = f'{v:.1f}'.rstrip('0').rstrip('.')
    return s.replace('.', ',') if lang == 'de' else s


_EXPR = re.compile(r'\{\[(.*?)\]\}')
_TOKEN = re.compile(r'\{(perkMultiplier|perkmultiplier|attributePerkMultiplier)\}')


def render_description(text, multiplier, lang):
    def repl(m):
        expr = _TOKEN.sub(lambda _: repr(multiplier), m.group(1))
        try:
            return _fmt(_eval(ast.parse(expr, mode='eval')), lang)
        except Exception:
            return '?'
    return _EXPR.sub(repl, text or '')


# ---------------------------------------------------------------- Oeffentliche Funktion

def resolve_perks(hashes, gear_score, item_id, lang):
    """Liste von Perk-Hashes -> [{hash, id, type, name, text}] (unbekannte Perks: nur hash)."""
    info = item_info(item_id) or {}
    out = []
    for h in hashes:
        p = perks().get(h)
        if not p:
            out.append({'hash': h, 'id': None, 'type': '', 'name': h, 'text': ''})
            continue
        mult = perk_multiplier(p, gear_score, gs_bonus_for(p, info.get('classes')))
        desc = p['desc'].get(lang) or p['desc'].get('en') or ''
        out.append({'hash': h, 'id': p['id'], 'type': p['type'],
                    'name': p['name'].get(lang) or p['name'].get('en') or p['id'],
                    'text': render_description(desc, mult, lang)})
    return out


# ---------------------------------------------------------------- Tooltip-Karte (wie im Spiel / nw-buddy)

RARITY_MAX_PERKS = (0, 2, 3, 4, 5)        # NW_ITEM_RARITY_DATA
RARITY_KEYS = ('common', 'uncommon', 'rare', 'epic', 'legendary')
ARMOR_SET_RATING_EXPONENT = 1.2
ROMAN = ('', 'I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X')
ATTRS = (('Strength', 'ui_strength_short'), ('Dexterity', 'ui_dexterity_short'),
         ('Intelligence', 'ui_intelligence_short'), ('Focus', 'ui_focus_short'))


def stats_table():
    return _load('stats')


def labels():
    return _load('labels')


def _label(key, lang, **params):
    L = labels().get(lang) or labels().get('en') or {}
    text = re.sub(r'<[^>]+>', '', L.get(key) or labels().get('en', {}).get(key) or key)
    for k, v in params.items():
        text = text.replace('{' + k + '}', str(v))
    return text.strip()


def _num(v, digits, lang):
    s = f'{v:,.{digits}f}'
    if lang == 'de':
        s = s.replace(',', ' ').replace('.', ',').replace(' ', '.')
    return s


def item_rarity(info, perk_count):
    if 'artifact' in (info.get('classes') or []):
        return 'artifact'
    if info.get('force_rarity'):
        return RARITY_KEYS[min(int(info['force_rarity']), 4)]
    upgradable = (info.get('tier') or 0) >= 5 and (info.get('gs_max') or 0) >= 590
    if not upgradable:
        perk_count = min(perk_count, 4)
    for i, max_count in enumerate(RARITY_MAX_PERKS):
        if perk_count <= max_count:
            return RARITY_KEYS[i]
    return RARITY_KEYS[-1]


def _weapon_stats(s, gs, lang):
    rows = []
    if s.get('BaseDamage'):
        rows.append((_num(s['BaseDamage'], 0, lang), _label('ui_tooltip_basedamage', lang)))
    if s.get('CritChance') is not None and 'CritChance' in s:
        rows.append((_num(s['CritChance'] * 100, 1, lang) + '%', _label('ui_tooltip_critical_hit_chance', lang)))
    if s.get('CritDamageMultiplier'):
        rows.append((_num(s['CritDamageMultiplier'], 2, lang), _label('ui_tooltip_critical_damage_multiplier', lang)))
    if s.get('BlockStaminaDamage'):
        rows.append((_num(s['BlockStaminaDamage'], 1, lang), _label('ui_tooltip_block_stamina_damage', lang)))
    rows += _armor_rows(s, gs, lang)
    if s.get('BlockStability'):
        rows.append((_num(s['BlockStability'], 0, lang) + '%', _label('ui_tooltip_blockingstability', lang)))
    return rows


def _armor_rows(s, gs, lang):
    rows = []
    if not gs or not s.get('ArmorRatingScaleFactor'):
        return rows
    base = math.pow(gs, ARMOR_SET_RATING_EXPONENT) * s['ArmorRatingScaleFactor']
    if s.get('ElementalArmorSetScaleFactor'):
        rows.append((_num(base * s['ElementalArmorSetScaleFactor'], 1, lang), _label('ui_elemental', lang)))
    if s.get('PhysicalArmorSetScaleFactor'):
        rows.append((_num(base * s['PhysicalArmorSetScaleFactor'], 1, lang), _label('ui_physical', lang)))
    return rows


def _armor_stats(s, gs, lang):
    rows = _armor_rows(s, gs, lang)
    for field, key in (('ScaleDamagePerGS', 'ui_base_damage_multiplier'), ('ScaleHealthPerGS', 'ui_health'),
                       ('ScaleCDRPerGS', 'ui_cooldown_reduction')):
        if s.get(field) and gs:
            rows.append(('+' + _num(s[field] * gs / 100, 2, lang) + '%', _label(key, lang)))
    return rows


def _scales_with(info, s, lang):
    scaling = info.get('scaling') or {a: s.get('Scaling' + a, 0) for a, _ in ATTRS}
    tiers = labels().get('weapon_tiers') or []
    parts = []
    for attr, key in sorted(ATTRS, key=lambda a: -(scaling.get(a[0]) or 0)):
        v = scaling.get(attr) or 0
        if not v:
            continue
        tier = next((t['tier'] for t in tiers if v >= t['start']), None)
        if tier:
            parts.append(f"{_label(key, lang)} ({tier})")
    return ', '.join(parts)


def card(item_id, gear_score, perk_hashes, lang):
    """Alle Daten fuer eine Tooltip-Karte im Spielstil."""
    info = item_info(item_id) or {}
    perk_list = resolve_perks(perk_hashes or [], gear_score, item_id, lang)
    for p, h in zip(perk_list, perk_hashes or []):
        meta = perks().get(h) or {}
        p['icon'] = meta.get('icon') or ''
        p['socket'] = p['type'] == 'Gem'
    rarity = item_rarity(info, len(perk_list))
    s = stats_table().get(info.get('stats') or '') or {}
    # Gear Score nur bei Ausruestung (Verbrauchsgueter haben im Capture auch einen, das Spiel zeigt ihn nicht)
    classes = info.get('classes') or []
    is_gear = bool(s) or any(c.startswith('equippable') or c == 'bag' for c in classes)
    gs = (gear_score or None) if is_gear or not info else None
    if s.get('kind') == 'weapon':
        stat_rows = _weapon_stats(s, gs, lang)
    elif s.get('kind') == 'armor':
        stat_rows = _armor_stats(s, gs, lang)
    else:
        stat_rows = []
    weight = (s.get('WeightOverride') or info.get('weight') or 0) / 10
    tier = info.get('tier') or 0
    info_rows = []  # Reihenfolge wie im Trading-Post-Tooltip; (art, text_vorher, fett, text_nachher)
    if tier:
        info_rows.append(('tier', _label('ui_tier', lang) + ' ', ROMAN[tier] if tier < len(ROMAN) else str(tier), ''))
    if s.get('kind') == 'weapon':
        sw = _scales_with(info, s, lang)
        if sw:
            info_rows.append(('scales', _label('ui_scales_with', lang) + ' ', sw, ''))
    if weight:
        tpl = re.sub(r'<[^>]+>', '', (labels().get(lang) or {}).get('ui_tooltip_weight') or '{value} Weight')
        pre, _, post = tpl.partition('{value}')
        info_rows.append(('weight', pre, _num(weight, 1, lang), post))
    if info.get('req_level'):
        info_rows.append(('level', _label('ui_level_requirement', lang) + ': ', str(info['req_level']), ''))
    return {
        'item_id': item_id,
        'name': item_name(item_id, lang) or item_id,
        'type': (info.get('type') or {}).get(lang) or (info.get('type') or {}).get('en') or '',
        'icon': info.get('icon') or '',
        'tier': ROMAN[tier] if 0 < tier < len(ROMAN) else '',
        'rarity': rarity,
        'named': 'named' in (info.get('classes') or []),
        'gear_score': gs,
        'stats': [{'value': v, 'label': lbl} for v, lbl in stat_rows],
        'perks': perk_list,
        'description': (info.get('desc') or {}).get(lang) or (info.get('desc') or {}).get('en') or '',
        'info': [{'kind': k, 'pre': a, 'bold': b, 'post': c} for k, a, b, c in info_rows],
    }
