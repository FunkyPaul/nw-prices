#!/usr/bin/env python3
"""
Erzeugt app/gamedata/{perks,items,stats,labels,categories}.json.gz aus den Daten von nw-buddy
(github.com/giniedp/nw-buddy-data).

  git clone --depth 1 --filter=blob:none --sparse https://github.com/giniedp/nw-buddy-data
  cd nw-buddy-data && git sparse-checkout set --no-cone '/live/localization/en-us.json' \\
      '/live/localization/de-de.json' '/live/datatables/javelindata_perks*.json' \\
      '/live/datatables/javelindata_itemdefinitions_*.json' '/live/datatables/javelindata_weapontiers.json' \\
      '/live/datatables/javelindata_housingitems*.json' '/live/datatables/mtx/javelindata_housingitems_mtx.json'
  python tools/build_gamedata.py /pfad/zu/nw-buddy-data/live

Perks werden im Capture als CRC32 der kleingeschriebenen PerkID uebertragen.
"""
import gzip
import json
import os
import re
import sys
import zlib
from pathlib import Path

LANGS = {'en': 'en-us.json', 'de': 'de-de.json'}
OUT = Path(__file__).resolve().parent.parent / 'app' / 'gamedata'

# UI-Beschriftungen der Tooltip-Karte (Lokalisierungsschluessel des Spiels)
LABEL_KEYS = [
    'ui_tooltip_basedamage', 'ui_tooltip_critical_hit_chance', 'ui_tooltip_critical_damage_multiplier',
    'ui_tooltip_block_stamina_damage', 'ui_tooltip_blockingstability', 'ui_elemental', 'ui_physical',
    'ui_base_damage_multiplier', 'ui_health', 'ui_cooldown_reduction', 'ui_tier', 'ui_tooltip_weight',
    'ui_scales_with', 'ui_level_requirement', 'ui_bindonequip', 'ui_bindonpickup', 'ui_named',
    'ui_strength_short', 'ui_dexterity_short', 'ui_intelligence_short', 'ui_focus_short', 'ui_constitution_short',
]
WEAPON_FIELDS = ['BaseDamage', 'CritChance', 'CritDamageMultiplier', 'BlockStaminaDamage', 'BlockStability',
                 'ScalingStrength', 'ScalingDexterity', 'ScalingIntelligence', 'ScalingFocus',
                 'ElementalArmorSetScaleFactor', 'PhysicalArmorSetScaleFactor', 'ArmorRatingScaleFactor',
                 'WeightOverride']
ARMOR_FIELDS = ['ElementalArmorSetScaleFactor', 'PhysicalArmorSetScaleFactor', 'ArmorRatingScaleFactor',
                'ScaleDamagePerGS', 'ScaleHealthPerGS', 'ScaleCDRPerGS', 'WeightOverride']


RARITY_NAMES = {'common': 0, 'uncommon': 1, 'rare': 2, 'epic': 3, 'legendary': 4}


def trading_path(it):
    return '/'.join(x for x in (it.get('TradingCategory'), it.get('TradingFamily'), it.get('TradingGroup')) if x)


def find(src, pattern):
    return sorted(Path(src).rglob(pattern))


def load_json(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def clean(text):
    if not text:
        return ''
    text = text.replace('\\n', '\n')
    text = re.sub(r'<[^>]+>', '', text)
    return re.sub(r'[ \t]+', ' ', text).strip()


def icon(path):
    p = (path or '').strip().lower().lstrip('/')
    if not p.startswith('lyshineui/'):
        return ''
    return p if p.endswith(('.webp', '.png')) else p + '.webp'


def compact(d, fields):
    out = {}
    for f in fields:
        v = d.get(f)
        if isinstance(v, (int, float)) and not isinstance(v, bool) and v != 0:
            out[f] = v
    return out


def category_names(items, loc):
    """Namen der Trading-Post-Kategorien je Pfad (klein geschrieben): {'resources/rawresources': {'en': ..., 'de': ...}}.

    Kategorie und Familie stehen im Spiel unter categorydata_<id>, Gruppen unter <id>_groupname.
    """
    def name(seg, depth, lang):
        s = seg.lower()
        keys = (f'categorydata_{s}', f'{s}_groupname') if depth < 2 else (f'{s}_groupname', f'categorydata_{s}')
        for L in (loc[lang], loc['en']):
            for k in keys:
                if L.get(k):
                    # Zeilenumbruch nach Bindestrich: Trennstrich ("Gesundheits-\nerholung") entfaellt vor Kleinbuchstaben
                    text = re.sub(r'-\n(?=[a-zäöüß])', '', clean(L[k]))
                    return text.replace('-\n', '-').replace('\n', ' ')
        return seg

    out = {}
    for it in items.values():
        segs = [x for x in (it.get('path') or '').split('/') if x]
        for d in range(len(segs)):
            key = '/'.join(segs[:d + 1]).lower()
            if key not in out:
                out[key] = {lang: name(segs[d], d, lang) for lang in LANGS}
    return dict(sorted(out.items()))


def main(src):
    loc = {}
    for lang, fname in LANGS.items():
        files = find(src, fname)
        if not files:
            sys.exit(f'{fname} nicht gefunden unter {src}')
        loc[lang] = {k.lower(): v for k, v in load_json(files[0]).items()}

    def tr(key, lang, raw=False):
        if not key:
            return ''
        k = key.lstrip('@').lower()
        v = loc[lang].get(k) or loc['en'].get(k) or ''
        return v if raw else clean(v)

    # ------------------------------------------------------------ Perks
    perks = {}
    for f in find(src, 'javelindata_perks*.json'):
        for p in load_json(f):
            pid = p.get('PerkID')
            if not pid:
                continue
            h = f'{zlib.crc32(pid.lower().encode()):08x}'
            bonus = {}
            for spec in str(p.get('ItemClassGSBonus') or '').split(','):
                if ':' in spec:
                    cls, val = spec.split(':', 1)
                    try:
                        bonus[cls.strip().lower()] = float(val)
                    except ValueError:
                        pass
            name_key = p.get('DisplayName') or p.get('SecondaryEffectDisplayName')
            entry = {
                'id': pid,
                'type': p.get('PerkType') or '',
                'icon': icon(p.get('IconPath')),
                'scaling': p.get('ScalingPerGearScore') or p.get('ScalingPerGearScoreAttributes') or '',
                'gs_bonus': bonus,
                'name': {}, 'desc': {},
            }
            for lang in LANGS:
                entry['name'][lang] = tr(name_key, lang) or pid
                entry['desc'][lang] = tr(p.get('Description'), lang)
            if h in perks and perks[h]['id'] != pid:
                print(f'Warnung: Hash-Kollision {h}: {perks[h]["id"]} / {pid}')
            perks[h] = entry

    # ------------------------------------------------------------ Waffen-/Ruestungswerte
    stats = {}
    for f in find(src, 'javelindata_itemdefinitions_weapons*.json'):
        for w in load_json(f):
            if w.get('WeaponID'):
                stats.setdefault(w['WeaponID'].lower(), dict(kind='weapon', **compact(w, WEAPON_FIELDS)))
    for f in find(src, 'javelindata_itemdefinitions_armor*.json'):
        for a in load_json(f):
            if a.get('WeaponID'):
                stats.setdefault(a['WeaponID'].lower(), dict(kind='armor', **compact(a, ARMOR_FIELDS)))
    tiers = []
    for f in find(src, 'javelindata_weapontiers.json'):
        tiers = sorted(({'tier': t['Tier'], 'start': t['ScalingStart']} for t in load_json(f)),
                       key=lambda x: -x['start'])

    # ------------------------------------------------------------ Items
    items = {}
    used_stats = set()
    for f in find(src, 'javelindata_itemdefinitions_master_*.json'):
        for it in load_json(f):
            iid = it.get('ItemID')
            if not iid or iid.lower() in items:
                continue
            names = {lang: tr(it.get('Name'), lang) for lang in LANGS}
            if not names['en']:
                continue
            entry = {'id': iid, 'name': names, 'classes': [c.lower() for c in (it.get('ItemClass') or [])],
                     'path': trading_path(it)}
            # Details fuer die Tooltip-Karte nur fuer handelbare Items (haelt die Datei klein)
            if it.get('TradingCategory'):
                ref = (it.get('ItemStatsRef') or '').lower()
                entry.update({
                    'icon': icon(it.get('IconPath')),
                    'tier': it.get('Tier') or 0,
                    'type': {lang: tr(it.get('ItemTypeDisplayName'), lang) for lang in LANGS},
                    'desc': {lang: tr(it.get('Description'), lang) for lang in LANGS},
                    'stats': ref if ref in stats else '',
                    'weight': it.get('Weight') or 0,
                    'req_level': it.get('RequiredLevel') or 0,
                    'boe': bool(it.get('BindOnEquip')),
                    'bop': bool(it.get('BindOnPickup')),
                    'force_rarity': it.get('ForceRarity') or 0,
                    'gs_max': it.get('GearScoreOverride') or it.get('MaxGearScore') or 0,
                    'scaling': {k: it.get(f'OverrideScaling{k}') or 0
                                for k in ('Strength', 'Dexterity', 'Intelligence', 'Focus')}
                    if it.get('OverrideAttributeScaling') else None,
                })
                if ref in stats:
                    used_stats.add(ref)
            items[iid.lower()] = entry

    # Housing-Items stehen in eigenen Tabellen
    for f in find(src, 'javelindata_housingitems*.json'):
        for it in load_json(f):
            iid = it.get('HouseItemID')
            if not iid or iid.lower() in items:
                continue
            names = {lang: tr(it.get('Name'), lang) for lang in LANGS}
            if not names['en']:
                continue
            items[iid.lower()] = {
                'id': iid, 'name': names, 'classes': ['housingitem'], 'path': trading_path(it),
                'icon': icon(it.get('IconPath')), 'tier': it.get('Tier') or 0,
                'type': {lang: tr(it.get('ItemTypeDisplayName'), lang) for lang in LANGS},
                'desc': {lang: tr(it.get('Description'), lang) for lang in LANGS},
                'stats': '', 'weight': it.get('Weight') or 0, 'req_level': 0, 'boe': False, 'bop': False,
                'force_rarity': RARITY_NAMES.get(str(it.get('ItemRarity') or '').lower(), 0),
                'gs_max': 0, 'scaling': None,
            }

    stats = {k: v for k, v in stats.items() if k in used_stats}
    labels = {lang: {k: tr(k, lang, raw=True) for k in LABEL_KEYS} for lang in LANGS}
    labels['weapon_tiers'] = tiers

    OUT.mkdir(parents=True, exist_ok=True)
    categories = category_names(items, loc)
    for name, data in (('perks', perks), ('items', items), ('stats', stats), ('labels', labels),
                       ('categories', categories)):
        path = OUT / f'{name}.json.gz'
        with gzip.open(path, 'wt', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, separators=(',', ':'))
        print(f'{path}: {len(data)} Eintraege, {os.path.getsize(path) // 1024} KB')


if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
