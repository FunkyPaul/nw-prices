"""Kategoriebaum des Trading Posts: Namen aus den Spieldaten, Reihenfolge wie in der Spieloberflaeche."""
import json
from functools import lru_cache
from pathlib import Path

from . import gamedata

# Reihenfolge der Eintraege je Ebene (Schluessel = Elternpfad, klein geschrieben; '' = oberste Ebene).
# Quelle: Klickverlauf eines Captures (jeweils erster Klick) plus Screenshots; die Rohstoff-Familien
# stammen aus einem Screenshot. Nicht aufgefuehrte Eintraege folgen alphabetisch dahinter.
ORDER = {
    '': ('weapons', 'tools', 'apparel', 'resources', 'utilities', 'furnishings'),
    'apparel': ('armorheavy', 'armormedium', 'armorlight', 'earrings', 'rings', 'amulets', 'bags', 'mountskin', 'apparelskin'),
    'resources': ('rawresources', 'arcanaresources', 'alchemyresources', 'cookingingredients', 'dyeingredients', 'refinedresources', 'components', 'specialresources', 'azoth', 'perkcharmfamily', 'runeglassfamily'),
    'tools': ('gatheringtools', 'instruments'),
    'utilities': ('potion', 'tincture', 'coating', 'enhancements', 'foodattribute', 'foodtradeskill', 'foodrecovery', 'eventconsumables', 'bait', 'dyes', 'cookingrecipes', 'musicsheets'),
    'weapons': ('1handed', '2handed', 'shields', 'magical'),
    'apparel/amulets': ('droppedamulet', 'craftedamulet'),
    'apparel/apparelskin': ('slothead', 'slotchest', 'slothands', 'slotlegs', 'slotfeet'),
    'apparel/armorheavy': ('slothead', 'slotchest', 'slothands', 'slotlegs', 'slotfeet'),
    'apparel/armorlight': ('slothead', 'slotchest', 'slothands', 'slotlegs', 'slotfeet'),
    'apparel/armormedium': ('slothead', 'slotchest', 'slothands', 'slotlegs', 'slotfeet'),
    'apparel/earrings': ('craftedearring', 'droppedearring'),
    'apparel/rings': ('craftedring', 'droppedring'),
    'furnishings/housingtrdf_trophies': ('housingtrdg_buffgathering', 'housingtrdg_buffcrafting', 'housingtrdg_buffother', 'housingtrdg_buffcombat'),
    'resources/alchemyresources': ('alchemyprotective', 'alchemymagical', 'alchemyoffensive', 'alchemymedicinal'),
    'resources/arcanaresources': ('arcanadeath', 'arcanafire', 'arcanaspirit', 'arcanawater', 'arcanaair', 'arcanaearth', 'arcanalife'),
    'resources/components': ('stone', 'craftingcomponents', 'craftingpatterns', 'refiningcomponents', 'trinketcomponents', 'instrumentcomponents'),
    'resources/cookingingredients': ('meat', 'fishlarge', 'fishmedium', 'fishsmall', 'vegetable', 'fruit', 'berry', 'grain', 'nut', 'honey', 'egg', 'cookingcomponents', 'water', 'seasonings'),
    'resources/perkcharmfamily': ('perkcharms', 'perkcharmmats'),
    'resources/rawresources': ('wood', 'fiber', 'cloth', 'stone', 'ore', 'oreprecious', 'rawgem', 'oil', 'rawhide', 'feather', 'beeswax', 'fishingsalvage', 'craftingcomponents', 'salvage'),
    'resources/refinedresources': ('cutgem', 'block', 'gunpowder', 'charcoal', 'ingotprecious'),
    'resources/specialresources': ('conditional', 'utility', 'defensive', 'offensive'),
    'tools/gatheringtools': ('2haxe', '1hsickle', '2hpick', '1hskinningknife', 'fishingpoles'),
    'tools/instruments': ('drums', 'uprightbass', 'flutes', 'guitars', 'mandolins'),
    'utilities/bait': ('baitfresh', 'baitsalt', 'bait'),
    'utilities/coating': ('coatingaeternian', 'coatingcorrupted', 'coatingancient', 'coatingbeast', 'coatinglost', 'coatingangryearth'),
    'utilities/dyes': ('dyered', 'dyebrown', 'dyeorange', 'dyeyellow', 'dyegreen', 'dyeturquoise', 'dyecyan', 'dyeblue', 'dyepurple', 'dyemagenta', 'dyegrey'),
    'utilities/eventconsumables': ('consumableluck', 'foodattribute'),
    'utilities/foodattribute': ('foodattribute', 'foodstr', 'foodfoc', 'fooddex', 'foodint', 'foodcon'),
    'utilities/foodrecovery': ('foodhealthrecovery', 'foodmana'),
    'utilities/foodtradeskill': ('foodlumberjack', 'foodengineer', 'foodarcanist', 'foodweaponsmith', 'foodharvester', 'foodminer', 'foodjewelcrafter', 'foodhunter', 'foodarmorer'),
    'utilities/musicsheets': ('uprightbass', 'drums', 'guitars', 'flutes', 'mandolins'),
    'utilities/potion': ('potionhealth', 'potionmana', 'potionfocus', 'potionelemdefense', 'potionencumbrance', 'potionwellness'),
    'utilities/tincture': ('potionpurifyb', 'potionwellness'),
    'weapons/1handed': ('rapiers', 'swords', 'flail', 'hatchets'),
    'weapons/2handed': ('greataxes', 'spears', 'warhammers', 'blunderbuss', 'bows', 'muskets', 'greatsword'),
    'weapons/magical': ('staveslife', 'stavesfire', 'gauntletice', 'gauntletvoid'),
    'weapons/shields': ('shieldskite', 'shieldsround', 'shieldstower'),
}
TOP = frozenset(ORDER[''])


@lru_cache(maxsize=None)
def _item_order():
    """Item-ID (klein) -> Position innerhalb der Gruppe, aus dem Klickverlauf (item_order.json)."""
    path = Path(__file__).resolve().parent / 'item_order.json'
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}


def item_rank(item_id):
    """Position eines Items in seiner Gruppe wie im Spiel; unbekannte Items kommen hinten."""
    return _item_order().get((item_id or '').lower(), 1 << 20)


def _rank(parent, key):
    order = ORDER.get(parent, ())
    return (order.index(key) if key in order else len(order), key)


@lru_cache(maxsize=None)
def tree(lang):
    """Verschachtelte Liste [{p: Pfad, n: Name, c: [Kinder]}] fuer die Kategorie-Seitenleiste."""
    kids = {}
    for it in gamedata.items().values():
        segs = [x for x in (it.get('path') or '').split('/') if x]
        if not segs or segs[0].lower() not in TOP:
            continue
        for d in range(len(segs)):
            parent = '/'.join(segs[:d]).lower()
            kids.setdefault(parent, {}).setdefault('/'.join(segs[:d + 1]).lower(), '/'.join(segs[:d + 1]))
    names = gamedata.categories()

    def build(parent):
        out = []
        for key in sorted(kids.get(parent, ()), key=lambda k: _rank(parent, k.rsplit('/', 1)[-1])):
            path = kids[parent][key]
            node = {'p': path, 'n': (names.get(key) or {}).get(lang) or (names.get(key) or {}).get('en') or path.rsplit('/', 1)[-1]}
            children = build(key)
            if children:
                node['c'] = children
            out.append(node)
        return out

    return build('')
