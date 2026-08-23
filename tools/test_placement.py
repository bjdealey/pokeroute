#!/usr/bin/env python3
"""Guards the living-dex placement contract the Team view relies on.

box/slot is a pure function of a species' index in the dex-ordered obtainable
list (id === national dex no). If a rebuild reshapes DATA.mon or the ordering,
this fails loudly. Run: python3 tools/test_placement.py
"""
import json, os, re

BOX_SIZE = 30
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_data():
    h = open(os.path.join(ROOT, "dist", "frlg.html")).read()
    raw = re.search(r"const DATA\s*=\s*(\{.*?\})\s*(?:;|\n)", h, re.S).group(1)
    depth = 0
    for i, c in enumerate(raw):                 # balanced-brace slice
        depth += (c == "{") - (c == "}")
        if depth == 0:
            return json.loads(raw[: i + 1])
    raise ValueError("DATA not balanced")


def home_of(spine, id):                          # mirrors homeOf() in ui.html
    i = spine.index(id)
    return {"box": i // BOX_SIZE + 1, "slot": i % BOX_SIZE + 1}


def slot_root(mon, id):                           # mirrors slotRoot() in ui.html
    cur = id
    while True:
        sp = mon[str(cur)]
        p = sp.get("from")
        fwd = mon[str(p)].get("evo", []) if p is not None and str(p) in mon else []
        if p is None or str(p) not in mon or len(fwd) != 1 or fwd[0]["id"] != cur:
            return cur
        cur = p


def national_units(mon, spine):                   # mirrors NAT_UNITS
    g = {}
    for id in spine:
        g.setdefault(slot_root(mon, id), []).append(id)
    return [sorted(g[r]) for r in sorted(g)]


def check_national(mon, spine):
    units = national_units(mon, spine)
    flat = [id for u in units for id in u]
    assert sorted(flat) == spine, "national units lost/duplicated a species"
    assert len(units) < len(spine), "collapse did nothing"

    # a linear line shares one slot; a branch (Eevee) splits into a slot per child
    def unit_of(id):
        return next(u for u in units if id in u)
    if all(str(x) in mon for x in (1, 2, 3)):
        assert unit_of(1) == unit_of(2) == unit_of(3), "Bulbasaur line not collapsed"
    if all(str(x) in mon for x in (133, 134, 135, 136)):   # Eevee + 3 eeveelutions
        eev = {133: unit_of(133), 134: unit_of(134), 135: unit_of(135), 136: unit_of(136)}
        assert len({id(v) for v in eev.values()}) == 4, "Eevee branch wrongly merged"
    return units


def main():
    mon = load_data()["mon"]
    spine = sorted(int(k) for k in mon)

    # the spine is the whole obtainable dex, in national order, no dups
    assert len(spine) == len(mon), "spine dropped species"
    assert spine == sorted(set(spine)), "spine not sorted/unique"

    # first species lands in Box 1 Slot 1; index 30 rolls to Box 2 Slot 1
    assert home_of(spine, spine[0]) == {"box": 1, "slot": 1}
    assert home_of(spine, spine[BOX_SIZE]) == {"box": 2, "slot": 1}
    assert home_of(spine, spine[BOX_SIZE - 1]) == {"box": 1, "slot": 30}

    # every species has a valid, in-bounds, unique home; round-trips back to index
    seen = set()
    for i, id in enumerate(spine):
        h = home_of(spine, id)
        assert 1 <= h["slot"] <= BOX_SIZE, f"{id} slot out of range"
        assert (h["box"] - 1) * BOX_SIZE + (h["slot"] - 1) == i, f"{id} home != index"
        assert (h["box"], h["slot"]) not in seen, f"{id} collides"
        seen.add((h["box"], h["slot"]))

    boxes = (len(spine) + BOX_SIZE - 1) // BOX_SIZE
    assert home_of(spine, spine[-1])["box"] == boxes, "last species in wrong box"

    units = check_national(mon, spine)

    print(f"ok — living: {len(spine)} species / {boxes} boxes; "
          f"national: {len(units)} obtain-once lines; #1 "
          f"{mon[str(spine[0])]['name']} -> Box 1 Slot 1")


if __name__ == "__main__":
    main()
