#!/bin/sh
# Refetch the sprites the build inlines, for every game in dist/. Run from the repo
# root after build.py has produced at least one file. Existing sprites are kept.
# Each game names its own sprite sets, tried in order — and each set's shiny/ beside
# it, into data/sprites/shiny/. A set with no shiny of its own falls through to the
# next set, the same way the normal sprites do.
set -e
S=https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon
mkdir -p data/sprites data/sprites/shiny
for f in dist/*.html; do
  python3 - "$f" <<'PY'
import json, re, sys
d = json.loads(re.search(r'const DATA=(\{.*?\});const SPR=', open(sys.argv[1]).read(), re.S).group(1))
ids = set(map(int, d['mon']))                        # every species the app can draw
for g in d['games'].values():
    for s in g['stops']:
        for m in s['mons']:
            ids |= {m['id'], m['finalId']} | {e['id'] for e in m['path']}
    for fight in g['fights']:
        ids |= {t['id'] for t in fight['team']} | {c['finalId'] for c in fight['counters']}
        for v in fight.get('variants', {}).values():
            ids |= {t['id'] for t in v}
for c in d['dex']['choices']:
    ids |= set(c['ids'])
print('\n'.join(f"{i} {' '.join(d['spriteSets'])}" for i in sorted(ids)))
PY
done | sort -u | while read -r id sets; do
  for shiny in "" shiny/; do
    out="data/sprites/$shiny$id.png"
    [ -s "$out" ] && continue
    for set in $sets; do
      curl -sfL -o "$out" "$S/$set/$shiny$id.png" && break
    done || echo "no ${shiny%/} sprite for $id" >&2
  done
done
find data/sprites -size 0 -delete
echo "data/sprites: $(ls data/sprites/*.png | wc -l) normal, $(ls data/sprites/shiny | wc -l) shiny"
