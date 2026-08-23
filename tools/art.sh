#!/bin/sh
# Fetch every piece of art the built pages ask for: item icons, type labels, badges.
# An art key IS its path in the PokeAPI sprite repo ("items/poke-ball", "badges/3"),
# so this needs no table of kinds — it fetches what the build says it wants.
# Anything with no art is listed, which is fine: "Rescue Lostelle" is an errand.
set -e
S=https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites
for f in dist/*.html; do
  python3 - "$f" <<'PY'
import json, re, sys
h = open(sys.argv[1]).read()
d = json.loads(re.search(r'const DATA=(\{.*?\});const SPR=', h, re.S).group(1))
keys = {c.get('icon') for c in d['catalogue']} | set(d['typeArt'].values()) \
     | set(d['methodArt'].values()) | set(d['badgeArt'].values())
for g in d['games'].values():
    for s in g['stops']:
        keys |= {i.get('icon') for i in s['items']}
for m in d['mon'].values():                       # the evolution stones
    keys |= {'items/' + o['item'] for o in m['evo'] if o.get('item')}
print('\n'.join(sorted(k for k in keys if k and not k.startswith('pkm-'))))
PY
done | sort -u | while read -r k; do
  [ -s "data/art/$k.png" ] && continue
  mkdir -p "data/art/$(dirname "$k")"
  curl -sfL -o "data/art/$k.png" "$S/${k%/*}/gen3/${k##*/}.png" \
    || curl -sfL -o "data/art/$k.png" "$S/$k.png" \
    || echo "no art for $k" >&2
done
find data/art -size 0 -delete
echo "data/art: $(find data/art -name '*.png' | wc -l) files"
