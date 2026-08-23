"""Build one game's planner: the PokeAPI CSV dump + games/<name>.json -> dist/<name>.html.

    python3 build.py            # every game in games/
    python3 build.py frlg       # just this one

Two models live here:
  value(mon, from_stop)  - how much the mon is worth for the fights that remain,
                           scored against real rosters, not gym type labels.
  effort(mon, at_stop)   - what it costs to get it battle-ready: finding it,
                           the EXP to reach the next ace's level, and the
                           evolution method (stone money, trade partner, ...).
"""
import csv, json, os, re, sys, base64, collections, statistics, unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
D = os.path.join(HERE, "data")
rows = lambda f: list(csv.DictReader(open(os.path.join(D, f + ".csv"))))

GAMES_DIR = os.path.join(HERE, "games")
if len(sys.argv) < 2:                         # no argument: build every game there is
    import subprocess
    built = sorted(f[:-5] for f in os.listdir(GAMES_DIR) if f.endswith(".json"))
    for g in built:
        subprocess.run([sys.executable, __file__, g], check=True)
    # the front page, so GitHub Pages has something at the root
    links = "".join(
        f'<li><a href="dist/{g}.html">{json.load(open(os.path.join(GAMES_DIR, g + ".json")))["game"]}</a></li>'
        for g in built)
    open(os.path.join(HERE, "index.html"), "w").write(
        '<!doctype html><meta charset="utf-8"><title>pokeroute</title>'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<style>body{background:#0e1117;color:#e6e9f0;font:16px system-ui;padding:40px;line-height:1.6}'
        'a{color:#7ec4ff}li{font-size:20px;margin:6px 0}</style>'
        f'<h1>pokeroute</h1><p>A run planner for Pok\u00e9mon games.</p><ul>{links}</ul>'
        '<p><a href="https://github.com/bjdealey/pokeroute">Source on GitHub</a></p>')
    raise SystemExit
GAME = sys.argv[1].removesuffix(".json")
route = json.load(open(os.path.join(GAMES_DIR, GAME + ".json")))
OUT = os.path.join(HERE, "dist", GAME + ".html")
UI = os.path.join(HERE, "ui.html")

CFG = route["build"]
VERSIONS = {k: str(v) for k, v in CFG["versions"].items()}
VER = set(VERSIONS.values())
VGROUP = str(CFG["versionGroup"])
GEN = CFG["generation"]
MAXDEX = CFG["maxDex"]

# --- lookups -----------------------------------------------------------------
types = {r["id"]: r["identifier"] for r in rows("types")}
type_id = {v: k for k, v in types.items()}
efficacy = {(r["damage_type_id"], r["target_type_id"]): int(r["damage_factor"]) for r in rows("type_efficacy")}
triggers = {r["id"]: r["identifier"] for r in rows("evolution_triggers")}
items = {r["id"]: r["identifier"] for r in rows("items")}
methods = {r["id"]: r["identifier"] for r in rows("encounter_methods")}
slots = {r["id"]: r for r in rows("encounter_slots")}
exp_at = {(r["growth_rate_id"], int(r["level"])): int(r["experience"]) for r in rows("experience")}

species = {}
for r in rows("pokemon_species"):
    if int(r["id"]) <= MAXDEX:
        species[r["id"]] = {"id": int(r["id"]), "name": r["identifier"],
                            "from": r["evolves_from_species_id"] or None,
                            "growth": r["growth_rate_id"]}
by_name = {s["name"]: sid for sid, s in species.items()}

poke_of = {r["species_id"]: r["id"] for r in rows("pokemon") if r["is_default"] == "1"}
base_exp = {r["species_id"]: int(r["base_experience"] or 60) for r in rows("pokemon") if r["is_default"] == "1"}
stats = collections.defaultdict(dict)
for r in rows("pokemon_stats"):
    stats[r["pokemon_id"]][r["stat_id"]] = int(r["base_stat"])
ptypes = collections.defaultdict(list)
for r in sorted(rows("pokemon_types"), key=lambda r: int(r["slot"])):
    ptypes[r["pokemon_id"]].append(types[r["type_id"]])
# The bare CSVs are current-gen: Clefable and friends read as Fairy, a type FRLG
# does not have. pokemon_types_past holds the types in force up to each gen.
past = collections.defaultdict(list)
for r in rows("pokemon_types_past"):
    past[r["pokemon_id"]].append(r)
for pid, rs in past.items():
    gens = sorted({int(x["generation_id"]) for x in rs if int(x["generation_id"]) >= GEN})
    if gens:
        ptypes[pid] = [types[x["type_id"]] for x in sorted(rs, key=lambda x: int(x["slot"]))
                       if int(x["generation_id"]) == gens[0]]
# ...and the chart itself moved (Ghost/Dark vs Steel were resisted until gen 6).
for r in rows("type_efficacy_past"):
    if int(r["generation_id"]) >= GEN:
        efficacy[(r["damage_type_id"], r["target_type_id"])] = int(r["damage_factor"])
for sid, s in species.items():
    pid = poke_of.get(sid)
    s["bst"] = sum(stats[pid].values()) if pid else 0
    s["types"] = ptypes.get(pid, [])
    s["off"] = (stats[pid].get("2", 0) + stats[pid].get("4", 0)) if pid else 0

# how each species is made
evo = {}
for r in rows("pokemon_evolution"):
    sid = r["evolved_species_id"]
    if sid in species and sid not in evo:
        evo[sid] = {"trigger": triggers[r["evolution_trigger_id"]],
                    "level": int(r["minimum_level"]) if r["minimum_level"] else None,
                    "item": items.get(r["trigger_item_id"]),
                    "held": items.get(r["held_item_id"]),
                    "happiness": int(r["minimum_happiness"]) if r["minimum_happiness"] else None,
                    "time": r["time_of_day"] or None}

def evo_text(sid):
    e = evo.get(sid)
    if not e: return None
    if e["trigger"] == "level-up":
        return f"level {e['level']}" if e["level"] else ("high friendship" if e["happiness"] else "level up")
    if e["trigger"] == "use-item": return (e["item"] or "item").replace("-", " ")
    if e["trigger"] == "trade": return "trade" + (f" holding {e['held'].replace('-',' ')}" if e["held"] else "")
    return e["trigger"].replace("-", " ")

children = collections.defaultdict(list)
for sid, sp in species.items():
    if sp["from"] in species and not evo.get(sid, {}).get("time"):
        children[sp["from"]].append(sid)

def final_form(sid, seen=()):
    best, path = species[sid], []
    for c in children.get(sid, []):
        if c in seen: continue
        f, p = final_form(c, seen + (sid,))
        if f["bst"] > best["bst"]: best, path = f, [(c, evo_text(c))] + p
    return best, path

# --- type maths --------------------------------------------------------------
def mult(atk_type, def_types):
    m = 1.0
    for d in def_types:
        m *= efficacy.get((type_id[atk_type], type_id[d]), 100) / 100
    return m

def best_mult(atk_types, def_types):
    return max([mult(a, def_types) for a in atk_types] or [1.0])

# --- FRLG encounters by location --------------------------------------------
la = {r["id"]: r for r in rows("location_areas")}
loc_name = {r["id"]: r["identifier"] for r in rows("locations")}

def encounters(vers):
    e_map = collections.defaultdict(lambda: collections.defaultdict(
        lambda: {"m": {}, "lo": 99, "hi": 0, "slots": set()}))
    for r in rows("encounters"):
        if r["version_id"] not in vers or r["pokemon_id"] not in species: continue
        key = loc_name[la[r["location_area_id"]]["location_id"]]
        sl = slots[r["encounter_slot_id"]]
        e = e_map[key][r["pokemon_id"]]
        m = methods[sl["encounter_method_id"]]
        if r["encounter_slot_id"] not in e["slots"]:
            e["slots"].add(r["encounter_slot_id"])
            e["m"][m] = e["m"].get(m, 0) + int(sl["rarity"] or 0)
        e["lo"] = min(e["lo"], int(r["min_level"]))
        e["hi"] = max(e["hi"], int(r["max_level"]))
    return e_map

enc_of = {k: encounters({v}) for k, v in VERSIONS.items()}
# which game each species can be caught in at all — the exclusives list
in_version = collections.defaultdict(list)
for tag, em in enc_of.items():
    for pool in em.values():
        for sid in pool: 
            if tag not in in_version[sid]: in_version[sid].append(tag)

# --- fights ------------------------------------------------------------------
stops = route["stops"]
idx_of = {s["id"]: i for i, s in enumerate(stops)}

def mk_team(pairs):
    return [{"id": int(by_name[n]), "name": n, "level": lv, "types": species[by_name[n]]["types"]}
            for n, lv in pairs]

def mk_fights():
    out = []
    for f in route["fights"]:
        g = {"id": f["id"], "name": f["name"], "kind": f["kind"], "stop": idx_of[f["stop"]],
             "team": mk_team(f["team"])}
        if "variants" in f:
            g["variants"] = {k: mk_team(v) for k, v in f["variants"].items()}
        out.append(g)
    return out

fights = mk_fights()

hm_moves = {r["pokemon_id"]: r["moves"].split("|") for r in rows("hm_compat")}

def descendants(sid, seen=()):
    """Everything owning this species eventually registers, by just evolving it."""
    out = [int(sid)]
    for c in children.get(sid, []):
        if c not in seen: out += descendants(c, seen + (sid,))
    return out

def family(sid):
    """The whole evolution family, root first — what a living dex needs one each of."""
    root = sid
    while species.get(root, {}).get("from") in species:
        root = species[root]["from"]
    return descendants(root)

def forms_at(sid, level, seen=()):
    """Every form you could plausibly be holding at this level. Stones are assumed
    buyable; trades are followed but flagged, since most players can't do them."""
    out = [(species[sid], False)]
    for c in children.get(sid, []):
        if c in seen: continue
        ev = evo.get(c, {})
        if ev.get("trigger") == "level-up" and (ev.get("level") or 99) > level: continue
        for f, tr in forms_at(c, level, seen + (sid,)):
            out.append((f, tr or ev.get("trigger") == "trade"))
    return out

def matchup(my_types, team):
    """One number for how a mon fares against a roster. + is good for me."""
    if not team: return 0.0
    tot = 0.0
    ace = max(t["level"] for t in team)
    for t in team:
        off = best_mult(my_types, t["types"])
        o = {4.0: 1.5, 2.0: 1.0, 1.0: 0.0, 0.5: -0.6, 0.25: -1.0, 0.0: -1.5}.get(off, 0.0)
        inc = best_mult(t["types"], my_types)          # their STAB into me
        d = {4.0: -1.0, 2.0: -0.5, 1.0: 0.0, 0.5: 0.4, 0.25: 0.7, 0.0: 0.9}.get(inc, 0.0)
        tot += (o + d) * (2 if t["level"] == ace else 1)
    return tot / (len(team) + 1)

def fight_teams(f):
    """Every roster this fight can present (rival varies with your starter)."""
    if "variants" not in f: return [f["team"]]
    return [f["team"] + v for v in f["variants"].values()]

def value_from(my_types, i, fs):
    """Worth of a mon for everything still ahead of stop i. Next fight counts most."""
    ahead = [f for f in fs if f["stop"] >= i]
    if not ahead: return 0.0, []
    total, notes = 0.0, []
    for n, f in enumerate(ahead):
        m = sum(matchup(my_types, t) for t in fight_teams(f)) / len(fight_teams(f))
        m = max(m, -0.3)          # you just don't send it in; a bad fit costs a slot, not the run
        w = 3.0 if n == 0 else 1.4 if n == 1 else 1.0 / (1 + 0.12 * n)
        total += m * w
        if m >= 0.55: notes.append((m, f["name"]))
    notes.sort(reverse=True)
    return total, [n for _, n in notes]

SHOP = CFG["stoneShop"]                       # where evolution stones go on sale
STONE_STOP = idx_of[SHOP["stop"]]
gate_idx = {m: idx_of[sid] for m, sid in CFG["methodGates"].items()}
ONE_SHOT = {"gift", "gift-egg", "static", "npc-trade"}

def effort(sid, e, method, rate, at, path, grind, fs):
    """Cost to make this thing battle-ready, in plain terms. Returns (score, notes)."""
    sp = species[sid]
    notes, cost = [], 0.0

    if method in ONE_SHOT:
        notes.append("handed to you — no hunting")
    elif rate and rate < 100:
        tries = round(100 / rate)
        cost += min(3.0, tries / 8.0)
        if tries >= 8: notes.append(f"~{tries} encounters to even find one ({rate}%)")

    ahead = [f for f in fs if f["stop"] >= at]
    target = round(statistics.median([t["level"] for t in fight_teams(ahead[0])[0]])) if ahead else None
    catch_lv = e["hi"] if method != "npc-trade" else 20
    if target and target > catch_lv:
        need = exp_at[(sp["growth"], min(100, target))] - exp_at[(sp["growth"], max(1, catch_lv))]
        per = grind[at] * 1.6 * (1.5 if method == "npc-trade" else 1.0)
        battles = max(0, round(need / per))
        cost += min(6.0, battles / 30.0)
        notes.append(f"≈{battles} battles' worth of EXP to reach Lv {target}")
        if battles > 120: notes.append("that is a serious grind")

    if sp["off"] < 55 and path:
        cost *= 2.0
        notes.append("can't fight for its own EXP — needs Exp. Share babysitting")

    for c, how in path:
        ev = evo.get(c, {})
        if ev.get("trigger") == "trade":
            cost += 4.0
            notes.append(f"{species[c]['name'].title()} needs a TRADE — not obtainable solo")
            break
        if ev.get("trigger") == "use-item":
            cost += 1.2 if at >= STONE_STOP else 2.2
            notes.append(f"needs a {(ev.get('item') or 'stone').replace('-',' ')}"
                         + (f" (₽{SHOP['cost']} at {SHOP['where']})" if at >= STONE_STOP
                            else f" — none until {SHOP['where']}"))
        elif ev.get("happiness"):
            cost += 1.5
            notes.append("friendship evolution — lots of walking")
        elif ev.get("level") and target and ev["level"] > target:
            cost += 0.8
            notes.append(f"still unevolved at the next fight (evolves at {ev['level']})")
            break
    return cost, notes

# --- build one game ----------------------------------------------------------
def build(tag):
    enc = enc_of[tag]
    fs = mk_fights()

    def area_exp(locid):
        pool = enc.get(locid, {})
        vals = [base_exp[sid] * ((e["lo"] + e["hi"]) / 2) / 7 for sid, e in pool.items()
                if "walk" in e["m"] or "surf" in e["m"]]
        return sum(vals) / len(vals) if vals else 60.0

    grind, seen_locs = [], []
    for st in stops:
        seen_locs += st["locations"]
        grind.append(max([area_exp(l) for l in seen_locs] + [60.0]))

    # every place-and-time a species can be got, earliest first
    spots = collections.defaultdict(list)
    for i, stop in enumerate(stops):
        for locid in stop["locations"]:
            for sid, e in enc.get(locid, {}).items():
                for m, rate in e["m"].items():
                    spots[sid].append({"at": max(i, gate_idx.get(m, 0)), "where": locid,
                                       "method": m, "rate": rate, "e": e})
    for v in spots.values():
        v.sort(key=lambda x: (x["at"], -x["rate"]))

    by_stop = collections.defaultdict(list)
    for sid, v in spots.items():
        by_stop[v[0]["at"]].append(sid)

    def build_mon(sid, i):
        v = spots[sid]
        b = v[0]
        sp, e = species[sid], b["e"]
        fin, path = final_form(sid)
        val, covers = value_from(fin["types"], i, fs)
        eff, enotes = effort(sid, e, b["method"], b["rate"], i, path, grind, fs)
        trade = b["method"] == "npc-trade"

        # --- dex planning: can this wait, and can you skip the evolving? ------
        later = sorted({x["at"] for x in v if x["at"] > i})
        also = [{"stop": j, "name": stops[j]["name"],
                 "where": next(x["where"] for x in v if x["at"] == j)} for j in later[:3]]
        wild_evo = None
        for c, how in path:
            cv = spots.get(c)
            if cv:
                wild_evo = {"id": int(c), "name": species[c]["name"], "how": how,
                            "stop": stops[cv[0]["at"]]["name"], "where": cv[0]["where"],
                            "method": cv[0]["method"], "at": cv[0]["at"],
                            "levels": [cv[0]["e"]["lo"], cv[0]["e"]["hi"]]}
                break
        return {
            "id": sp["id"], "name": sp["name"], "types": sp["types"],
            "where": b["where"], "levels": None if trade else [e["lo"], e["hi"]],
            "rate": b["rate"], "method": b["method"], "vers": in_version[sid],
            "final": fin["name"], "finalId": fin["id"], "finalBst": fin["bst"],
            "path": [{"id": int(c), "name": species[c]["name"], "how": how} for c, how in path],
            "value": round(val, 2), "effort": round(eff, 2),
            "score": round(val - 0.55 * eff + fin["bst"] / 700.0, 2),
            "covers": covers[:4], "cost": enotes, "fromStop": stops[i]["name"],
            "spots": [{"at": x["at"], "stop": stops[x["at"]]["name"], "where": x["where"],
                       "method": x["method"], "rate": x["rate"],
                       "levels": [x["e"]["lo"], x["e"]["hi"]]} for x in v[:6]],
            "also": also, "onlyChance": not also and b["method"] in ONE_SHOT,
            "wildEvo": wild_evo,
            "hms": hm_moves.get(str(poke_of.get(sid, "")), []),
            "fills": descendants(sid),      # national dex: owning this registers these
            "family": family(sid),          # living dex: you need one of each of these
        }

    out, pool = [], []
    for i, stop in enumerate(stops):
        mons = sorted((build_mon(sid, i) for sid in by_stop.get(i, [])), key=lambda m: -m["score"])
        pool += mons
        here = [f for f in fs if f["stop"] == i]
        for f in here:
            ace = max(t["level"] for t in fight_teams(f)[0])
            cands = {}
            for m in pool:
                options = [(sum(matchup(fm["types"], t) for t in fight_teams(f)) / len(fight_teams(f)), fm, tr)
                           for fm, tr in forms_at(str(m["id"]), ace)]
                pick = lambda tr: max([o for o in options if o[2] == tr] or [None],
                                      key=lambda o: (o[0], o[1]["bst"]) if o else ())
                # keep the best form you can reach alone, and the best trade form only
                # if trading actually buys you something
                solo, traded = pick(False), pick(True)
                take = [solo] if solo else []
                if traded and (not solo or traded[0] > solo[0]): take.append(traded)
                for sc, form, needs_trade in take:
                    prev = cands.get(form["id"])
                    if prev is None or sc > prev["m"]:
                        cands[form["id"]] = {"id": m["id"], "name": m["name"], "finalId": form["id"],
                                             "final": form["name"], "types": form["types"],
                                             "from": m["fromStop"], "trade": needs_trade, "m": round(sc, 2)}
            # ponytail: types + levels only — no movepool or ability modelling.
            # Upgrade path is pokemon_moves.csv if the rankings ever feel wrong.
            f["counters"] = sorted(cands.values(),
                                   key=lambda c: (-c["m"], -species[str(c["finalId"])]["bst"]))[:8]
        out.append({
            "machines": [c for c in route.get("catalogue", []) if c["stop"] == stop["id"]],
            "id": stop["id"], "name": stop["name"],
            "boss": stop.get("boss"), "notes": stop.get("notes", ""),
            "items": stop.get("items", []),
            "badge": stop.get("badge"), "unlock": route["badgeHm"].get(stop.get("badge") or ""),
            "mons": mons, "fights": [f["id"] for f in here],
        })
    return {"stops": out, "fights": fs, "_grind": grind}

games = {tag: build(tag) for tag in VERSIONS}

# --- moves, learnsets and the EXP curve, for the party planner ---------------
movedex = {}
for r in rows("movedex"):
    movedex[int(r["id"])] = {"n": r["name"], "t": types[r["type_id"]],
                             "p": int(r["power"]) if r["power"] else 0,
                             "a": int(r["accuracy"]) if r["accuracy"] else 100,
                             "pp": int(r["pp"] or 0), "c": r["class"]}
learn = {}
for r in rows("learnset"):
    lv = [[int(x.split(":")[0]), int(x.split(":")[1])] for x in r["levelup"].split("|") if x]
    tm = [int(x) for x in r["machines"].split("|") if x]
    learn[r["pokemon_id"]] = {"lv": lv, "tm": tm}

# the curated per-stop items are searchable too, not just the machines
full_catalogue = list(route.get("catalogue", []))
machine_names = {c["name"][:4] for c in full_catalogue}
for st in route["stops"]:
    for it in st.get("items", []):
        if it["name"][:4] in machine_names:      # the machine list already has it
            continue
        full_catalogue.append({"name": it["name"], "where": it["where"], "stop": st["id"],
                               "kind": "item", "why": it["why"]})

# machine number -> its catalogue entry, carrying the real move id. Matching TMs to
# moves by name silently fails on things like "SolarBeam" vs "solar-beam".
mach_move = {int(r["machine_number"]): int(r["move_id"]) for r in rows("machines")
             if r["version_group_id"] == VGROUP}
for n in route.get("npcs", []):
    full_catalogue.append({"name": n["name"], "where": n["where"], "stop": n["stop"],
                           "kind": "npc", "why": n["why"]})

# --- item art ----------------------------------------------------------------
# The catalogue is hand-written prose ("Gold Teeth -> HM04 Strength", "Snorlax x2"),
# so an icon is found by slugging the first thing named and looking it up as an item,
# then as a species. A TM's art is its move's type, which is how the games draw them.
item_ids = {r["identifier"] for r in rows("items")}

def slugify(name):
    n = re.split(r"\s*/\s*|\s+or\s+|\s*\+\s*|\s*(?:->|\u2192)\s*|\(", name)[0]
    n = unicodedata.normalize("NFKD", n).encode("ascii", "ignore").decode().lower()
    n = re.sub(r"\bx\s?\d+\b", " ", n)
    return re.sub(r"[^a-z0-9]+", "-", n).strip("-")

ITEM = "items/"                                    # every art key is a path in the
TYPE = f"types/generation-{'iii' if GEN == 3 else GEN}/{CFG['spriteSets'][0].split('/')[-1]}/"
BADGE = "badges/"                                  # PokeAPI sprite repo, fetched as-is

def icon_for(name):
    m = re.match(r"^(TM|HM)(\d\d)", name)
    if m:
        n = int(m.group(2)) + (100 if m.group(1) == "HM" else 0)
        mv = movedex.get(mach_move.get(n))
        return ITEM + (f"{m.group(1).lower()}-{mv['t']}" if mv else "tm-case")
    if name.startswith(("TM", "HM")):
        return ITEM + "tm-case"
    s = slugify(name)
    if s in by_name:
        return "pkm-" + by_name[s]                  # "Snorlax x2" — draw the Pokémon
    if s.endswith("s") and s[:-1] in item_ids:
        return ITEM + s[:-1]                        # "Poké Balls x5" -> poke-ball
    return ITEM + s if s else None

# how you get a thing, drawn with the item that gets it — the rods, the HM discs,
# the flute. Walking and trading stay text; an icon on 90% of rows says nothing.
METHOD_ART = {"surf": "hm-water", "rock-smash": "hm-fighting", "pokeflute": "poke-flute",
              "old-rod": "old-rod", "good-rod": "good-rod", "super-rod": "super-rod",
              "gift": "poke-ball", "gift-egg": "lucky-egg", "static": "ultra-ball"}
method_art = {k: ITEM + v for k, v in METHOD_ART.items()}
type_art = {n: TYPE + i for i, n in types.items() if int(i) <= 17}
badge_art = {b: BADGE + str(i) for b, i in route.get("badges", {}).items()}

for st in route["stops"]:
    for it in st.get("items", []):
        it["icon"] = ITEM + it["icon"] if it.get("icon") else icon_for(it["name"])
# the catalogue holds a copy of each stop item, so it takes the same icon
stop_icon = {it["name"]: it["icon"] for st in route["stops"] for it in st.get("items", [])}
for c in full_catalogue:
    c["icon"] = (ITEM + c["icon"] if c.get("icon") else stop_icon.get(c["name"])
                 or (icon_for(c["name"]) if c["kind"] != "npc" else None))

machine_name = {}
for c in route.get("catalogue", []):
    if c["kind"] not in ("TM", "HM"): continue
    n = int(c["name"][2:4]) + (100 if c["kind"] == "HM" else 0)
    machine_name[n] = dict(c, move=mach_move.get(n))
missing = [n for n, c in machine_name.items() if not c["move"]]
assert not missing, f"machines with no move id: {missing}"

# --- what stands between you and a complete dex ------------------------------
exclusives = {tag: sorted(species[sid]["name"] for sid, vs in in_version.items() if vs == [tag])
              for tag in VERSIONS}
trade_evos = sorted({species[sid]["name"] for sid in species
                     if evo.get(sid, {}).get("trigger") == "trade" and sid in in_version
                     or (evo.get(sid, {}).get("trigger") == "trade"
                         and species[sid]["from"] in in_version)})
# one table for every species the app can mention, so party members that were
# evolved into (and never caught) still have stats, a learnset and an EXP curve
def species_row(sid):
    sp, pid = species[sid], poke_of.get(sid)
    opts = []
    for c in children.get(sid, []):
        ev = evo.get(c, {})
        opts.append({"id": int(c), "name": species[c]["name"], "how": evo_text(c),
                     "trigger": ev.get("trigger"), "level": ev.get("level"),
                     "item": ev.get("item")})
    # ponytail: current-gen base stats — a handful moved in gen 6+ and there is no
    # pokemon_stats_past.csv in the dump to correct them with.
    return {"name": sp["name"], "types": sp["types"], "bst": sp["bst"],
            "stats": [stats[pid].get(str(i), 0) for i in range(1, 7)] if pid else [0] * 6,
            "growth": int(sp["growth"]), "baseExp": base_exp.get(sid, 60),
            "hms": hm_moves.get(str(pid), []), "evo": opts,
            "from": int(sp["from"]) if sp["from"] in species else None,
            "learn": learn.get(str(pid), {"lv": [], "tm": []})}

blockers = {"exclusives": exclusives, "tradeEvos": trade_evos,
            "choices": route.get("dexBlockers", [])}
# owning a species eventually registers everything downstream of it — needed for the
# National Dex view, including forms that never appear in the wild (Butterfree etc.)
in_family = {i for g in games.values() for st in g["stops"] for m in st["mons"] for i in m["family"]}
evo_down = {i: descendants(str(i)) for i in sorted(in_family)}
names = {i: species[str(i)]["name"] for i in sorted(in_family)}
for b in blockers["choices"]:
    b["ids"] = [int(by_name[n]) for n in b["pick"] if n in by_name]
fights = games["FR"]["fights"] + games["LG"]["fights"]

# --- sprites -----------------------------------------------------------------
sprite_ids = set()
for g in games.values():
    for st in g["stops"]:
        for m in st["mons"]:
            sprite_ids |= {m["id"], m["finalId"]} | {e["id"] for e in m["path"]}
            if m["wildEvo"]: sprite_ids.add(m["wildEvo"]["id"])
for b in blockers["choices"]: sprite_ids |= set(b["ids"])
sprite_ids |= in_family
for f in fights:
    sprite_ids |= {t["id"] for t in f["team"]}
    for v in f.get("variants", {}).values(): sprite_ids |= {t["id"] for t in v}
    sprite_ids |= {c["finalId"] for c in f.get("counters", [])}
spr, miss = {}, []
for i in sorted(sprite_ids):
    p = os.path.join(D, "sprites", f"{i}.png")
    if os.path.exists(p) and os.path.getsize(p):
        spr[i] = "data:image/png;base64," + base64.b64encode(open(p, "rb").read()).decode()
    else:
        miss.append(i)
assert not miss, f"{len(miss)} sprites missing — run tools/sprites.sh: {miss[:10]}"

stones = {ITEM + o["item"] for r in (species_row(str(i)) for i in sorted(in_family))
          for o in r["evo"] if o["item"]}
img, no_art = {}, []
for k in sorted({c["icon"] for c in full_catalogue if c["icon"]}
                | {i["icon"] for st in route["stops"] for i in st.get("items", []) if i["icon"]}
                | stones | set(method_art.values()) | set(type_art.values()) | set(badge_art.values())):
    if k.startswith("pkm-"):
        continue                                   # already in SPR, drawn from there
    p = os.path.join(D, "art", k + ".png")
    if os.path.exists(p) and os.path.getsize(p):
        img[k] = "data:image/png;base64," + base64.b64encode(open(p, "rb").read()).decode()
    else:
        no_art.append(k)
if no_art:
    print(f"  no art for {len(no_art)} — run tools/art.sh: {' '.join(no_art[:6])}")

mon_table = {i: species_row(str(i)) for i in sorted(in_family)}
# the UI ranks moves by coverage, so it needs the same chart build.py already has
se_chart = {a: sorted(b for b in types.values()
                      if efficacy.get((type_id[a], type_id[b]), 100) > 100)
            for a in types.values()}
growths = sorted({m["growth"] for m in mon_table.values()})
exp_table = {g: [exp_at[(str(g), l)] for l in range(1, 101)] for g in growths}
for tag, g in games.items():
    g["grind"] = [round(x) for x in g.pop("_grind")]

payload = ("const DATA=" + json.dumps({"game": route["game"], "region": route["region"],
                                       "map": route["map"],
                                       "mon": mon_table, "moves": movedex, "exp": exp_table, "se": se_chart,
                                       "machines": machine_name, "stoneStop": STONE_STOP,
                                       "typeArt": type_art, "methodArt": method_art, "badgeArt": badge_art, "spriteSets": CFG["spriteSets"], "npcs": {n["id"]: dict(n, at=idx_of[n["stop"]]) for n in route.get("npcs", [])},
                                       "games": games, "rivalStarter": route["rivalStarter"],
                                       "dex": blockers, "evoDown": evo_down, "names": names, "catalogue": full_catalogue,
                                       "stopNames": {st["id"]: st["name"] for st in stops}},
                                      separators=(",", ":"))
           + ";const SPR=" + json.dumps(spr, separators=(",", ":"))
           + ";const IMG=" + json.dumps(img, separators=(",", ":")) + ";")
os.makedirs(os.path.dirname(OUT), exist_ok=True)
html = open(UI).read()
assert "/*DATA*/" in html, "ui.html lost its /*DATA*/ marker"
open(OUT, "w").write(html.replace("/*DATA*/", payload))

for tag, g in games.items():
    n = sum(len(s["mons"]) for s in g["stops"])
    miss_v = sorted({m["name"] for s in g["stops"] for m in s["mons"] if tag not in m["vers"]})
    print(f"  {tag}: {n} species obtainable, {len(g['fights'])} fights")
    assert n > 100 and not miss_v, f"{tag} leaked unobtainable species: {miss_v[:5]}"
    assert all(f.get("counters") for f in g["fights"]), f"{tag} has a fight with no counters"
print(f"{len(stops)} stops -> {OUT} ({os.path.getsize(OUT)//1024} KB)")
