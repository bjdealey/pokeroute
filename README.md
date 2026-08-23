# pokeroute

A run planner for Pokémon games. One game per file in `games/`; the build turns each
into a self-contained HTML page.

Shipping today: **FireRed / LeafGreen** (`games/frlg.json`).

Decides *what to do next* in a FRLG playthrough — for beating the game and for
filling the dex. Which Pokémon to catch at each stop and why, which to defer,
which you can skip evolving entirely, where every TM and HM is, and what beats
each of the 19 named fights.

Pick your **goal**, **cartridge** and **starter** in the header. All three change what
the app shows you. **✨ shiny** beside them redraws every sprite in the app in its
shiny colours, and stays that way until you turn it off.

    open dist/frlg.html

Or online: <https://bjdealey.github.io/pokeroute/>

One self-contained HTML file. Everything is kept in localStorage.

**On a phone** it's a five-tab app — **Map**, **Here**, **Team**, **Find**, **Dex** —
with a bottom tab bar, one screen at a time, and the cartridge/goal/starter settings
tucked behind the ⚙ in the header. Party slots go single-column, the PC drops to five
across, and every control is sized for a thumb. Dragging between party and PC is
desktop-only (HTML5 drag has no touch equivalent); the `party` / `PC` buttons on every
Pokémon do the same job.

**On a desktop** (wider than 860px) it's the two-column layout, and the sidebar carries
the navigation: the same **Here / Team / Find / Dex** buttons the phone puts in its tab
bar, then the search box, the town map and the stop list. One view at a time on the
right, so the party and the dexes are a click away rather than a scroll.

## Building

    python3 build.py            # every game in games/
    python3 build.py frlg       # just this one

    tools/sprites.sh            # fetch any sprites the built pages reference, shiny too
    tools/art.sh                # fetch the item, type and badge art they reference
    tools/learnsets.sh          # rebuild the move data from the PokeAPI dump
    tools/species.sh            # rebuild the abilities, egg groups and classifications

## Layout

    build.py          the whole build: joins the CSVs to a game file
    index.html        the front page, rewritten on a full build (GitHub Pages)
    ui.html           the shared template; the build inlines data at /*DATA*/
    games/frlg.json   one file per game — the part no API has
    data/*.csv        the PokeAPI/veekun dump, shared by every game
    data/sprites/     sprite PNGs, base64-inlined at build time
    data/sprites/shiny/  the same species again, in their shiny colours
    data/art/         item, type and badge art, mirroring the sprite repo's layout
    dist/frlg.html    the build output. Don't edit it.

**`games/<name>.json` is the whole per-game surface.** Nothing about a cartridge lives
in `build.py` or `ui.html` — a game file carries its own progression order, gym and
rival rosters, badge→HM map, town map layout, TM/HM catalogue, NPCs, dex blockers, and
a `build` block with the generation, dex cutoff, version group, version ids, where the
stone shop is, which HM gates which encounter method, and which sprite sets to pull.
Adding a game is adding a file.

## Goals

- **Beat the game** — rank by battle value; every catch is shown.
- **National Dex** — you need one *entry* per species, and evolving fills the rest of
  the line. Own a Caterpie and Metapod greys out: *"already covered — evolving your
  Caterpie registers it. Only catch it if you want it for a fight."* The wild-evolution
  advice inverts too: *"evolving this one fills all 3 dex entries."*
- **Living Dex** — you need one of every species held simultaneously, so nothing covers
  anything else. Each line shows its own tally (*"Caterpie, Metapod, Butterfree all need
  their own slot — 1/3 so far"*) and the shortcut becomes *"catch a Metapod in the grass
  rather than raising a second Caterpie."*

## Party and PC

Six party slots, everything else in the PC — drawn as the in-game screens and
**draggable between the two** on desktop. A full party bounces the next drop into the
PC and says so. The `party` / `PC` buttons on every catch row do the same thing for
touch, where HTML5 drag isn't available.

Each slot is a single line — sprite, name, level, and the one thing that matters right
now ("needs Lv 38 — ≈25 battles", "ready to become Ivysaur", "tap to set its level").
**Tapping it opens that Pokémon's sheet**, which is where the detail lives:

- **Level.** Type it in and the estimates go concrete: how many levels until it evolves,
  and *"Lv 38 for Rival — ≈25 battles"*, computed from its real Gen 3 EXP curve against
  what a battle is worth at the best grinding spot you can currently reach.
- **Evolution.** Buttons for every option — green once the condition is met, greyed with
  the reason when not (*"Kadabra at Lv 16"*, *"thunder stone — none yet"*). Eevee shows
  all three. Nothing evolves on its own; evolving carries the level and moveset across
  and switches the sheet to the new form.
- **Moves.** Four dropdowns listing everything it could legally be holding right now —
  moves learnt by its level, plus TMs and HMs it is compatible with *that you could
  already have picked up*. Set what it knows, or hit **use recommended**. Once a set is
  stored the sheet tells you what to change: *"Teach Razor Leaf over Vine Whip — level
  22"*, naming the move, its source and the slot it should replace. Ranked on power x
  accuracy, x1.5 for STAB, plus a bonus for hitting the types in the next four fights;
  the recommended set takes the best damaging move per type, then status moves, and only
  doubles up on a type as a last resort.
- **Relearning and undoing.** A level-up move whose level you have already passed is
  marked `· relearn`, and the advice says so: *"Skipped it? The Move Relearner on Two
  Island has it."* Before you get there it reads *"nothing brings it back until Two
  Island"* instead. HM moves get a lock note naming the Move Deleter in Fuchsia City,
  and are excluded from swap suggestions — the app will not tell you to overwrite a move
  you cannot overwrite. All three NPCs (Relearner, Deleter, and the Cape Brink tutor for
  the starters' ultimate moves) are in the searchable catalogue and appear at their stops.

- **Field moves — who carries what.** For each of the seven HMs, in the order the game
  hands them to you, the app picks the carrier it costs least. That is a real trade-off:
  Surf, Strength, Fly and Waterfall are strong attacks, so on the right Pokémon an HM is
  free or an upgrade, while Flash is pure dead weight. So it says *"HM03 Surf → Lapras,
  free — Surf earns its slot here anyway"* but *"HM05 Flash → Venusaur, costs it Poison
  Powder"*, and spreads the load rather than stacking every HM on one Pokémon. Each row has a **teach it** button that drops the HM straight into that
  Pokémon's set — first empty slot, otherwise over its weakest non-HM move — and then
  reads "✓ carrying it". It also flags when the only compatible carrier is sitting in
  your PC, and when nobody you own can learn it at all, with the "from Fuchsia onward"
  lead time for HMs you can't use yet. You can equally pick an HM by hand from any of
  the four moveset dropdowns, where they show up marked `· HM`.
- **Swap advice for the next fight.** It names who in your party does nothing against
  what's coming and which boxed Pokémon to withdraw, respecting your free slots
  ("Withdraw Graveler — you have a free slot") versus a straight trade ("Box Bulbasaur
  and withdraw Graveler in its place"). Trade-only forms are never suggested when a
  trade-free form of the same line does the job.

**Dex planning.** Every species carries every place and time you can get it, so the
app can tell you when *not* to bother:
- *"also at Rock Tunnel, Seafoam — safe to skip"* — it comes back, catch it when convenient.
- *"only chance in the game"* — one-time gifts, statics and trades that become
  trade-only if you walk past them.
- *"no need to evolve it — Golbat is catchable in the grass at Seafoam, Lv 26–30"* —
  39 of the 40-odd evolution lines have the evolved form available wild somewhere. For a
  dex entry that is strictly cheaper than grinding the baby form up.

**Item art.** Every item, TM and HM the app names is drawn with its own icon. The
catalogue is hand-written prose, so the icon is worked out from it: `TM26 Earthquake`
takes the disc in its move's type (which is how the games colour them), `Snorlax x2`
draws the Pokémon, and everything else is slugged and looked up — `Poké Balls x5` →
`poke-ball`. Where the prose names no single item (`Vitamins (Protein, Carbos…)`), the
game file can say which icon to use:

    { "name": "Vitamins (Protein, Carbos, HP Up...)", "icon": "protein", ... }

**Shiny.** Every species is inlined twice, ordinary and shiny, from the same
generation-III sprite sets — `versions/generation-iii/firered-leafgreen/shiny/` first,
Emerald behind it, exactly the fallback the ordinary sprites use. The ✨ button in the
header swaps the lot; the Pokédex's Shiny column always shows the shiny form regardless,
which is the point of having a column. A species with no shiny art draws its ordinary
self rather than a hole. It costs about 230 KB on the page.

**Type labels, badges and how you get it.** The type pills are the real FireRed labels
(`sprites/types/generation-iii/firered-leafgreen/`), the gym stops and the stop list
carry their badge, an evolution that wants a stone shows the stone on its button, and
each catch row is marked with the item that gets it — the three rods, the Surf and Rock
Smash discs, the Poké Flute, a Poké Ball for gifts. Walking and trading stay text: an
icon on 90% of the rows says nothing.

**One fetcher for all of it.** An art key *is* its path in the PokeAPI sprite repo —
`items/poke-ball`, `badges/3`, `types/generation-iii/firered-leafgreen/12` — so
`tools/art.sh` needs no table of kinds. It fetches whatever the built pages ask for into
`data/art/<key>.png` and lists what it couldn't find, which is not an error: "Rescue
Lostelle" is an errand, not an item. A new game's art needs no change to the script.

The badge art is numbered globally by the sprite repo, so a game file says which is
which:

    "badges": { "boulder": 1, "cascade": 2, ... }

**The reference dexes.** The **Dex** tab is four sub-tabs, and the first three are the
same table: **sortable, filterable column by column, and yours to configure.** Click a
heading to sort by it, type under a heading to filter on that column alone — number
columns take `>100`, `<40` or `80-120`, type and class columns become a dropdown — and
the `columns` button opens everything the table *could* show, to tick on and off. The
search box above still matches every column at once. Your sort, your filters and your
columns are remembered per dex, so the table you built is the one you come back to.

- **Pokédex** — every species the game can give you. Out of the box: number, sprite,
  types, the six base stats, BST, abilities and where it first turns up. A tick away:
  classification, EV yield, egg groups and how many steps they hatch in, the gender
  split, catch rate, base friendship, EXP growth and base EXP, height and weight, what
  it is weak to, resists and is immune to, how many moves it can hold, what it evolves
  from, and whether it is in your party, your PC, registered, or covered by evolving
  something you already have. A **Shiny** column draws the shiny form beside the ordinary
  one, whichever way the header's ✨ is set, so you can compare the two. Tap a row for its
  sheet — the learnset, and the same facts folded away under **Dex data**, including the
  full damage-taken chart and both forms side by side.
- **Movedex** — every move in the generation: type, class, power, accuracy, PP, what it
  actually does, and the machine that teaches it. Priority, where that machine is, and
  how many species in the game can hold the move are a tick away.
- **Itemdex** — the machine and key-item catalogue: what it is, what it teaches, the stop
  it belongs to (sorted the way you walk it), where exactly, and why it matters.
- **Blockers** — what stands between you and a full dex.

Each is built from that game's own file, so a new `games/<name>.json` gets its own three
dexes for free.

**Counters.** For each fight, everything obtainable up to that point is scored against
that roster — using the form you'd realistically be holding at that level, not the
final evolution. Trade-only forms are shown but dimmed and don't count as coverage.
If nothing on your tagged team answers a fight, it says so.

## Version exclusives

Encounters are baked separately for FireRed and LeafGreen — 17 species each side —
so the catch lists, the ranking and the per-fight counters only ever contain things
you can actually get on your cartridge. `build.py` asserts this. The "Dex completion
blockers" panel lists the other game's 17, the ten trade-only evolutions, and the
one-of-two choices (starter, fossil, Hitmon) that permanently cost dex entries.

## Generation 3 corrections

The bare CSVs are current-generation and would quietly ruin the type maths:

- `pokemon_types_past.csv` restores Gen 3 types — Clefable, Wigglytuff, Mr. Mime and
  Marill read as Fairy otherwise, a type FireRed does not have.
- `type_efficacy_past.csv` restores Ghost and Dark being resisted by Steel.
- Time-of-day evolutions (Espeon, Umbreon) are pruned — FRLG has no clock.
- `pokemon_abilities_past.csv` restores the gen 3 ability line-ups, and the hidden slot
  (a gen 5 idea) is dropped: Clefable is Cute Charm here, not Magic Guard, and Pikachu
  has Static and nothing else.

## Progress is worked out, not ticked off

There is no "mark this cleared" checkbox. How far you've got is inferred from evidence
the app already holds:

- **What you own.** Every species knows the earliest stop any member of its family can
  be obtained at. Holding a Lapras means you reached Silph Co.; a Magikarp from the
  Route 4 salesman means you got past Mt. Moon. The furthest of those is your floor.
- **What your Pokémon know.** A move that only comes off a TM or HM proves you picked
  that machine up — a Bulbasaur that knows Surf puts you at Fuchsia at the earliest,
  whatever else you're carrying.

The stop card shows its reasoning (*"worked out from: you have Lapras"*), and the
inference only ever moves you forward — it can't demote you. Two buttons handle the
cases it can't see: **I've cleared this stop** when you're further along than your
catches let on, and **I haven't got this far** to pull the manual floor back.

## Resetting

"Reset all progress" in the sidebar clears everything the app remembers — party, PC,
levels, movesets, registered dex entries, the manual progress floor, goal, cartridge and
starter — behind a confirm.

## Known gaps

- Party and PC hold one of each species, so you can't track two Caterpies. A full
  Living Dex run would want per-Pokémon instances rather than a set of species ids.

- Item coverage is all 50 TMs, all 7 HMs and the key items, hand-listed in
  `games/frlg.json` (`catalogue` and the per-stop `items`). Ordinary ground items —
  Potions and Poké Balls lying in the grass — are in no dataset and are not covered.
- Movepools now drive the "moves to teach" panel, but *not* the catch ranking or the
  fight counters — those are still types, levels, base stats and EXP curves, so a
  Pokémon with the right type and no move to use it can still rank well.
- Status moves are offered but not ranked: `movedex.csv` now carries each move's effect
  in words, and the Movedex prints it, but the ranking still sees only power, accuracy,
  type and class. So it can't tell you Sleep Powder beats Growl, and 140+ power moves get
  a flat damping for their drawback rather than a real model. Modelling those effects,
  rather than printing them, is the fix.
- Abilities are shown, not modelled. The dex knows Gengar has Levitate; the fight
  counters do not, and will still credit a Ground move against it.
- `base_experience` in the dump is the Gen 5+ value, so the battle counts are
  proportionally right but not exact Gen 3 numbers.
- Ordinary trainer battles along routes aren't modelled — only the 19 named fights.
- FireRed/LeafGreen is the only game file so far. The build is game-agnostic;
  the work of adding one is authoring its progression, rosters and map.
