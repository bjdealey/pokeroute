#!/bin/sh
# Rebuild data/learnset.csv, data/movedex.csv and data/hm_compat.csv — the FRLG
# level-up moves, TM/HM compatibility and move stats. Run from the repo root.
# pokemon_moves.csv is 10 MB and only needed here, so it is fetched and thrown away.
set -e
B=https://raw.githubusercontent.com/PokeAPI/pokeapi/master/data/v2/csv
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
for f in pokemon_moves moves move_damage_classes machines move_effect_prose; do
  curl -sSfL -o "$T/$f.csv" "$B/$f.csv"
done
python3 - "$T" <<'PY'
import csv, collections, os, sys
T = sys.argv[1]
rd = lambda f: csv.DictReader(open(os.path.join(T, f + '.csv')))
mv = {r['id']: r for r in rd('moves')}
dc = {r['id']: r['identifier'] for r in rd('move_damage_classes')}
fx = {r['move_effect_id']: r['short_effect'] for r in rd('move_effect_prose')
      if r['local_language_id'] == '9'}
mach = {r['move_id']: int(r['machine_number']) for r in rd('machines') if r['version_group_id'] == '7'}
hm_move = {m: n for m, n in mach.items() if n > 100}

lvl = collections.defaultdict(list)
tms = collections.defaultdict(set)
hms = collections.defaultdict(set)
used = set()
for r in rd('pokemon_moves'):
    if r['version_group_id'] != '7':
        continue
    if r['pokemon_move_method_id'] == '1':                       # level-up
        lvl[r['pokemon_id']].append((int(r['level']), r['move_id'])); used.add(r['move_id'])
    elif r['pokemon_move_method_id'] == '4' and r['move_id'] in mach:   # machine
        tms[r['pokemon_id']].add(mach[r['move_id']]); used.add(r['move_id'])
        if r['move_id'] in hm_move:
            hms[r['pokemon_id']].add(mv[r['move_id']]['identifier'])

with open('data/learnset.csv', 'w') as f:
    f.write('pokemon_id,levelup,machines\n')
    for p in sorted(set(lvl) | set(tms), key=int):
        ml = '|'.join(f'{l}:{m}' for l, m in sorted(set(lvl[p])))
        f.write(f"{p},{ml},{'|'.join(map(str, sorted(tms[p])))}\n")
with open('data/movedex.csv', 'w') as f:
    w = csv.writer(f)
    w.writerow(['id', 'name', 'type_id', 'power', 'accuracy', 'pp', 'class', 'priority', 'effect'])
    for i in sorted(used, key=int):
        r = mv[i]
        # "$effect_chance% chance to burn" — the table stores the placeholder, the move the number
        e = fx.get(r['effect_id'], '').replace('$effect_chance', r['effect_chance'] or '')
        w.writerow([i, r['identifier'], r['type_id'], r['power'], r['accuracy'], r['pp'],
                    dc[r['damage_class_id']], r['priority'], ' '.join(e.split())])
with open('data/hm_compat.csv', 'w') as f:
    f.write('pokemon_id,moves\n')
    for p in sorted(hms, key=int):
        f.write(f"{p},{'|'.join(sorted(hms[p]))}\n")
print(f"learnset {len(lvl)} species · movedex {len(used)} moves · hm_compat {len(hms)} species")
PY
