#!/bin/sh
# Rebuild the species reference data the dexes show but the planner never needed:
# abilities (with their gen-3 forms), egg groups and the "Seed Pokémon" genus.
# Run from the repo root. The prose tables are multilingual and large, so they are
# fetched, reduced to English, and thrown away.
set -e
B=https://raw.githubusercontent.com/PokeAPI/pokeapi/master/data/v2/csv
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
for f in abilities ability_prose pokemon_abilities pokemon_abilities_past \
         egg_groups pokemon_egg_groups pokemon_species_names; do
  curl -sSfL -o "$T/$f.csv" "$B/$f.csv"
done
python3 - "$T" <<'PY'
import csv, collections, os, sys
T = sys.argv[1]
rd = lambda f: csv.DictReader(open(os.path.join(T, f + '.csv')))
EN = '9'

# abilities, with the one-line effect. A Pokémon's ability is half of what it is,
# and the dump keeps the text in a separate multilingual table.
text = {r['ability_id']: r['short_effect'] for r in rd('ability_prose') if r['local_language_id'] == EN}
with open('data/abilities.csv', 'w', newline='') as f:
    w = csv.writer(f); w.writerow(['id', 'identifier', 'generation_id', 'text'])
    n = 0
    for r in rd('abilities'):
        if r['is_main_series'] != '1': continue
        w.writerow([r['id'], r['identifier'], r['generation_id'], text.get(r['id'], '')]); n += 1

# who has what — kept raw, with the past table beside it, because which abilities a
# Pokémon had is generation-dependent and only build.py knows which generation it wants.
def copy(src, dst, cols):
    with open(dst, 'w', newline='') as f:
        w = csv.writer(f); w.writerow(cols)
        rows = [[r[c] for c in cols] for r in rd(src)]
        w.writerows(rows)
        return len(rows)
a = copy('pokemon_abilities', 'data/pokemon_abilities.csv', ['pokemon_id', 'ability_id', 'is_hidden', 'slot'])
copy('pokemon_abilities_past', 'data/pokemon_abilities_past.csv',
     ['pokemon_id', 'generation_id', 'ability_id', 'is_hidden', 'slot'])

groups = {r['id']: r['identifier'] for r in rd('egg_groups')}
by_species = collections.defaultdict(list)
for r in rd('pokemon_egg_groups'):
    by_species[r['species_id']].append(groups[r['egg_group_id']])
with open('data/egg_groups.csv', 'w', newline='') as f:
    w = csv.writer(f); w.writerow(['species_id', 'groups'])
    for s in sorted(by_species, key=int):
        w.writerow([s, '|'.join(by_species[s])])

with open('data/species_genera.csv', 'w', newline='') as f:
    w = csv.writer(f); w.writerow(['species_id', 'genus'])
    g = [(r['pokemon_species_id'], r['genus']) for r in rd('pokemon_species_names')
         if r['local_language_id'] == EN and r['genus']]
    w.writerows(sorted(g, key=lambda x: int(x[0])))
print(f"abilities {n} · {a} pairings · egg groups {len(by_species)} species · genera {len(g)}")
PY
