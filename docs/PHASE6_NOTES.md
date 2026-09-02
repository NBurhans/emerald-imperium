# Phase 6 — species survey (companion dex)

`emerald_imperium_survey.html` — 896 KB (+ sprites), or 1,981 KB as one file. Data is embedded
gzip-compressed and inflated in the browser with the native DecompressionStream API
(Chrome 80+, Safari 16.4+, Firefox 113+). No network, no localStorage. Party and
selections live in memory.

## Design

Pokédex-style dossier in the Species Survey identity: Newsreader display over Archivo
data, conifer ink and specimen paper, brass for standouts, verdigris for good, oxide for
unusable. The search box is the masthead. Species are dossier cards; opening one gives a
page with a six-axis stat signature, incoming-damage chart by attacking type, lineage
navigation, the full Phase 4 performance record, movepools with TMs faded until their
Phase 2 gate, and where to get it.

The checkpoint control is **on the species page**, not global: "Show this species at …"
with ‹ › steppers. It drives value, VORP, role, ceiling item, and which level-up moves
are learned. Rankings, Roles and Party carry their own copy of the same control. The
Dex grid remembers the last checkpoint set and marks it in gold on every curve.

## v2 composite (sustain)

The dex now runs on the v2 Phase 4 numbers. Each species page carries a **Sustain** block:
sweep depth on one lifebar, sustain at this checkpoint, the kit contribution, healing per
turn, hazard chip, screens, and which EV spread won the ceiling here. Grid cards flag
species with a strong kit. Tier thresholds are the recalibrated v2 cutoffs.

## Sprites

Species art comes from `ydarissep/JwowSquared.github.io` → `data/sprites.js`. That
project is the **Radical Red** dex (its caps page opens with "Pre-Brock"), so only the
sprites are taken from it — none of its species, cap, or location data, all of which
belong to a different hack. Sprites are 64×64 PNG keyed by the same `SPECIES_*` ROM
labels the Phase 1 table carries, which makes the join exact rather than fuzzy.

Coverage of 1,534 forms: 1,112 by exact label, 71 after normalising RR's short regional
suffixes (`_A`/`_G`/`_H` for Alola/Galar/Hisui), 350 by the nearest form of the same
species (cosmetic forms, Totems, and the nine Imperium-only megas — Slaking, Torterra,
Infernape, Empoleon ×2, Luxray, Roserade, Dusknoir, Grimmsnarl — for which no art exists
anywhere). One row, labelled `GEN9_START`, is a sentinel constant aliased to Alcremie in
the Phase 1 label map and has no label of its own; PokeAPI covers it by dex number.

Re-encoded from unpalettised RGBA PNG to lossless WebP: 2.05 MB → 0.8 MB. 1,188 unique
images. The species page states which case applies to its art.

`ydarissep/radical-red-tool` holds no sprite files (a React shell with `src/` empty on
the default branch). `PokeAPI/pokeapi` is data only; its sprites live in `PokeAPI/sprites`,
which the app uses as a network fallback by national-dex number when the companion file
is absent.

## Files

| File | Size | Use |
|---|---:|---|
| `emerald_imperium_survey.html` + `emerald_imperium_sprites.js` | 808 + 1,085 KB | Keep both in one folder. The page loads sprites from its sibling; with the sibling missing it falls back to PokeAPI over the network |
| `emerald_imperium_survey_onefile.html` | 1,893 KB | Everything inlined. Try this first if your viewer allows it; it is a fifth the size of the file that failed |
| `emerald_imperium_survey_pair.zip` | 1,350 KB | The pair, for download |

## Build-move highlighting

On every species page, moves the scorer actually leaned on at the selected checkpoint are
marked. Gold: the ceiling build used it, with how many of that checkpoint's boss slots it
was the best answer to (Swampert at Pre-Winona: Stone Edge 3/6, Earthquake, Ice Punch,
Iron Tail 1/6 each). Dashed: the zero-investment floor used it. This comes straight from
the Phase 4 scoring record — for each boss slot the scorer took the single best damaging
move from the build's pool — not from a hand-picked moveset. The scorer keeps the
strongest move of each type and category, so a weaker same-type move is never the pick.

Adding this record cost 257 KB compressed (548 → 805 KB).

Caught while adding it: the app payload had encoded move category by first letter, so
Special and Status were both "S". Special attacks displayed with no power and were being
dropped from the Party and Boss type math. Fixed; category is now P / S / -.

## What changed from the previous file, and why

The first Phase 6 file was 3.26 MB with the data embedded raw; it rendered in a real
browser but not in the viewer the user has. This version trims what the full TSVs already
hold — egg moves (breeding is off in this run), six per-checkpoint axis curves, lineage
strings, reasoning text — and compresses the rest: 3.26 MB → 548 KB. Nothing shown is
approximated; every number is exact to the bundle.

## Verified

Headless Chromium: 1,534 cards, search, dossier open, checkpoint toggle and steppers
recompute the page (Swampert-Mega: unobtainable at cp9, 0.644 with Choice Band at cp19),
all six tabs, boss picker, add-to-party carries into Party, responsive to 400 px.
0 runtime errors. The only console entry is the Google Fonts request being refused
offline, which falls back to Georgia and Arial.
