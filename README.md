# Emerald Imperium — analysis bundle

Quantitative analysis of **Pokémon Emerald Imperium v1.3** for a Normal-difficulty
playthrough with level caps enforced and Minimal Grinding Mode off. Every one of the
1,534 species forms in the ROM was scored against every boss roster at each of nineteen
level caps, using real damage calculations rather than tier-list intuition.

**[Open the dex →](https://YOUR_GITHUB_USERNAME.github.io/emerald-imperium/)**

## What is here

| | |
|---|---|
| **[`data/`](data/)** | The analysis output as TSVs. `04_valuation.tsv` is the headline: 1,311 scored forms with VORP, floor/ceiling/ROI, sustain, roles and tiers |
| **[`index.html`](index.html)** | The dex — search, rankings, roles, boss matchups, party coverage. Self-contained, works offline |
| **[`workbook/`](workbook/)** | Excel workbook with live formulas. Change a weight on `Assumptions` and all 1,311 rows recalculate |
| **[`docs/`](docs/)** | READMEs, the Phase 5 audit, run settings, the original brief |
| **[`pipeline/`](pipeline/)** | Every script, in dependency order. The whole thing rebuilds from `data/` + the calc |
| **[`MANIFEST.md`](MANIFEST.md)** | Full index with raw URLs and fetch instructions |

## How a species is scored

Seven axes, weighted and stated on the workbook's `Assumptions` sheet:

| axis | weight | what it measures |
|---|---:|---|
| offense | .26 | Fraction of the boss roster 2HKO'd, from actual damage rolls |
| defense | .15 | Fraction of boss moves survived, single-hit |
| **sustain** | .16 (.24 for defensive roles) | Sweep depth on one lifebar with recovery, hazard chip and screens, minus the same species with no kit |
| speed | .12 (.04 for defensive roles) | Fraction of the roster outsped |
| utility | .10 | Breadth of non-damage tools |
| typing | .11 | Resistance profile against *that boss's* attacking types |
| niche fit | .10 | Best archetype fit, after binary gates |

**Floor** is zero investment: neutral nature, 0 EVs, first ability, no item, level-up
moves only. **Ceiling** is the best build using only what the world data says is
obtainable by that checkpoint — and it is the better of an offensive and a defensive EV
spread. **VORP** subtracts the third-best floor in the same role, so a species is measured
against what you would otherwise field, not against the whole dex.

## What is trustworthy and what is not

Every damage figure is **Inferred**, not Measured: the damage-formula generation is pinned
to 9 on evidence but Imperium's own routine is unconfirmed. The engine was verified against
an independent hand implementation of the formula and agrees on every case where no ability
or item modifier applies.

`docs/PHASE5_EVALUATION.md` is the adversarial audit of this work — seven defects found and
fixed, including two that changed numbers, plus the sensitivity analysis naming which
assumptions would most move the rankings if wrong. `docs/00_BUNDLE_README.md` carries the
data gotchas; read the join warnings before touching the TSVs.

Known limits, all stated in the app: 223 forms have no derivable acquisition route and are
unscored; weight is 50 kg for every species so weight-based moves are unresolved; move
priority is absent from the move table; Rivalry and Cute Charm assume same gender because
gender ratio is in no Imperium source.

## Rebuilding

```bash
cd pipeline
git clone --depth 1 https://github.com/RadicalRedShowdown/damage-calc calc
cd calc/calc && npm install && npx tsc -p . && cd ../..
python3 build_checkpoints.py && python3 build_availability.py && python3 prep_scoring.py
node --max-old-space-size=8192 score.js          # ~5 min, 63,045 rows
python3 archetypes.py && python3 valuation.py && python3 ship.py && python3 workbook.py
```

Paths at the top of each script assume the layout in `MANIFEST.md`.

## Sources

The level-cap ladder and every boss roster were parsed from two community-made
workbooks for Emerald Imperium — `Boss_Battles.xlsx` and `Battle_Rewards.xlsx`. Those
files are **not redistributed here**; they belong to their authors. Everything this
project derived from them is in `data/`: the measured 19-checkpoint ladder in
`05_checkpoints.tsv`, all 678 roster slots in `03_trainer_slots.tsv`, and the held-item
reward attribution in `02_world.tsv`.

Nothing in this repo needs those workbooks at runtime. Only `pipeline/audit_boss.py`,
which re-verifies the parse against the source, requires them; drop them into
`sources/` if you want to run that check.

## Credits

Sprites from [ydarissep/JwowSquared.github.io](https://github.com/ydarissep/JwowSquared.github.io)
(sprites only — none of its species or location data, which belong to a different hack),
with [PokeAPI/sprites](https://github.com/PokeAPI/sprites) as a network fallback. Damage
engine: [RadicalRedShowdown/damage-calc](https://github.com/RadicalRedShowdown/damage-calc)
at `7f35400`. Emerald Imperium is by its own authors; this repo is analysis, not the hack.
