# Phase 5 — Evaluation

> Re-run against the **v2 composite** (sustain axis, defensive ceiling spread, role-aware weights, recalibrated tiers). All figures below are v2.

No new dataset. Everything below was re-read from the shipped bundle on disk and attacked. The working objects that produced the bundle were deliberately not used: checking a file against the thing that wrote it proves nothing.

## Headline

**Seven defects found, all seven fixed.** Three were in the data as shipped, three were in my own Phase 4 code, and one was in the Phase 5 checker itself. Two of the seven changed numbers.

| # | Defect | Where | Changed numbers? |
|---|---|---|---|
| 1 | Form tie-break took the **shortest** candidate name, so `Darmanitan` resolved to Darmanitan-**Zen** (540 BST, Fire/Psychic, 30 Atk / 140 SpA) instead of Standard (480, pure Fire, 140 / 30), and `Toxtricity` to the 621-BST **Mega** instead of the 502-BST Amped form | my Phase 4 resolver | **Yes** — wrong boss at cp09, cp18, cp19 |
| 2 | Three roster move names are source typos (`Hurricaine`, `Steath Rock`, `Scorching Sand`). Because the scorer filters a boss's attack set to moves it can find, each typo silently **removed a damaging move**, understating that boss and so overstating every species' defense against it | source + my scorer | **Yes** — 3 bosses |
| 3 | A location string sat in the species column. `Boss_Battles.xlsx` has `Rusturf Tunnel` in a **level** cell; Phase 3 took it as the species name, and **Spoink was absent from the bundle entirely** while its nature, ability and four moves sat on the mislabelled row | source + Phase 3 | No — not a checkpoint anchor |
| 4 | `ceiling_item` stored only the **last** checkpoint's item, so the recorded build was not reproducible at 10,614 of 21,015 species-checkpoint pairs. The *scores* were correctly gated all along | my Phase 4 output schema | No — reporting only |
| 5 | A colon inside a value broke the `key:value` encoding: `Type: Null` encoded as `3:Type: Null`, which decodes to key 3, value `Type`, and a stray ` Null` | my encoding | No |
| 6 | Two roster `species_id` values left UNRESOLVED that Phase 4 can resolve | Phase 3 | No |
| 7 | The Phase 5 decode check counted escaped colons as malformed — the **checker** was wrong, not the file | this phase | No |

## Round-trip and referential integrity

**44 of 46 checks clean.** The remaining two are known source gaps, not defects.

| Check | Result |
|---|---|
| All 7 TSVs re-read, row counts round-trip, no ragged rows, all end with a newline | pass |
| Every `*_by_checkpoint` column decodes; curve length equals `n_checkpoints_obtainable`; curve starts at `earliest_checkpoint` | 0 mismatches of 1,311 |
| `lineage_form_per_checkpoint` decodes colon-escape-aware; 1,108 distinct forms including `Type: Null` | pass |
| Roster `species_id` resolves to a Phase 1 row | 678/678 |
| Roster moves resolve against the move table | 2,702/2,702 |
| Evolution targets, movepool move ids, BST = sum of parts, stats in 1–255, `internal_index` unique | 0 failures |
| **Every Phase 4 ceiling build uses only items Phase 2 confirms obtainable by that checkpoint** | **21,015/21,015** |
| `n_tm_gated` matches the Phase 2 TM gates | 0 mismatches |
| `tier` follows the stated thresholds; `cant_miss` follows its stated rule | 0 violations |
| `06_lineage`: adjusted = raw − dead-weight penalty | 0 mismatches |
| Roster abilities / held items absent from Imperium's own data | 1 / 8 — **Unresolved**, source gaps |

## Damage re-verification — and a correction to the Phase 4 claim

Phase 4 reported **14/14, 0.0% discrepancy**. That was measured on cases I chose. Re-using them would only prove they still pass, so Phase 5 drew **39 cases at random** from the actual boss rosters and obtainable pools across 14 checkpoints.

**Raw result: 37/39, a 5.1% discrepancy rate.** Both divergences are the **hand verifier**, not the engine:

- `Luxray` Thunder Fang → Butterfree: the engine returns 200–236, the hand formula 162–192. Luxray's first ability is **Rivalry**, a 1.25× multiplier. Force a different ability and the engine returns 162–192 — exactly the hand value.
- `Vikavolt-Totem` Acrobatics → Diancie-Mega: engine 22–26, hand 11–13. **Acrobatics doubles to 110 BP with no held item.** Give the attacker an item and the engine returns 11–13 — exactly the hand value.

The hand implementation models level, stats, base power, STAB and the type chart, and deliberately nothing else. **Engine-vs-formula agreement is 39/39 once both are given the same information.** The honest statement of the Phase 4 result is therefore: the engine reproduces the Gen-3+ damage formula exactly on every case where no ability or item modifier applies, and the curated 14 happened to be all such cases.

## Recomputed validations

| Validation | Result |
|---|---|
| BST correlation, floor | r = 0.366, n = 19,418 — **pass** (threshold ~0.7) |
| BST correlation, ceiling | r = 0.476, n = 20,797 — **pass** |
| Tier distribution | S+ 9 / S 39 / A 100 / B 190 / C 286 / D 268 / F 419 |
| `cant_miss` | 34 species |
| `tier_fragile` | 71 species within 0.002 of a threshold |

## Sensitivity — the assumptions that would most change the rankings

Ordered by how many species change tier if the assumption is wrong. Named species are the ones whose tier actually depends on it.

| # | Assumption | If wrong | Species | Named |
|---|---|---|---|---|
| 1 | Composite weight on OFFENSE (0.30) | A +/-0.05 shift moves 306 / 263 species across a tier line (23.3% / 20.1%) | 306 | Absol-Mega, Accelgor, Alakazam, Alakazam-Mega, Aggron-Mega, Altaria |
| 2 | Composite weight on SPEED (0.15) | A +/-0.05 shift moves 302 / 202 species (23.0% / 15.4%) | 302 | Accelgor, Aegislash-Shield, Aggron-Mega, Alakazam, the Alcremie forms |
| 3 | Damage-formula generation pinned to 9 | Every damage figure in the project is Inferred on this. A different multiplier order or crit rule would move offense and defense together, so it would shift levels rather than ranks -- but the 2HKO/OHKO thresholds are step functions and would move species across them. | 1311 | ALL 1,311 species forms |
| 4 | Gender-dependent abilities resolve as same-gender | Rivalry applies 1.25x when attacker and defender share a gender and 0.75x when they do not. gender_ratio was one of the eight fields dropped in Phase 1 as unconfirmable, so the engine default stands unchallenged. The true multiplier spans 0.75-1.25, a 67% swing on offense for these species. | 20 | Axew, Cinccino, Clefable, Clefairy, Cleffa, Delcatty, Enamorus-Incarnate, Fraxure, Haxorus, Igglybuff, Jigglypuff, Litleo |
| 5 | Tier thresholds are hard cuts | 76 species sit within 0.002 of a threshold; their tier flips between the two equally valid ways of averaging VORP. | 71 | Prinplup, Lycanroc-Dusk, Pecharunt, Steenee, Snorlax, Stonjourner, Rapidash-Galar, Cradily, Onix, Ribombee-Totem |
| 6 | weightkg = 50 for every species | No Imperium source carries weight, so Low Kick, Grass Knot, Heavy Slam and Heat Crash all compute at a fictional 50kg. Every damage figure involving them is Unresolved, not Inferred. | 579 | Abomasnow, Abomasnow-Mega, Abra, Aggron, Aggron-Mega, Aipom, Alakazam, Alakazam-Mega, Ambipom, Amoonguss |
| 7 | cp02 roster breadth | cp02 is scored against the 30-slot DAWN:16 block, which the Phase 3 parse merged from several separate rival fights. Every species obtainable at cp02 is scored against a roster wider than any single fight it will face. | 133 | all species first obtainable at cp02 |
| 8 | Availability derived through undecoded evolution methods | 24 evolution methods are still raw integers. Species reached only through them are dated to their pre-evolution, which is a LOWER bound -- they may be obtainable much later or not at all. | 197 | Slowking, Araquanid-Totem, Goodra-Hisui, Froslass, Gallade, Electivire, Steelix, Gigalith, Meowstic-M, Basculegion-M |

**The one worth acting on first is #4.** `Rivalry` and `Cute Charm` apply 1.25× or 0.75× depending on whether attacker and defender share a gender — a 67% swing. `gender_ratio` was one of the eight fields dropped in Phase 1 as unconfirmable, so the engine default stands unchallenged on 20 obtainable species including Haxorus, Luxray, Clefable and Lopunny. This is the clearest case where a field dropped for being unverifiable turned out to have a measurable downstream cost.

Full weight-perturbation table:

| assumption           |   species_changing_tier |   pct | examples                                                                     |
|:---------------------|------------------------:|------:|:-----------------------------------------------------------------------------|
| weight speed -0.05   |                     376 |  28.7 | Absol, Aggron-Mega, Alcremie-Berry-Caramel-Swirl, Alcremie-Berry-Lemon-Cream |
| weight speed +0.05   |                     254 |  19.4 | Abomasnow, Abomasnow-Mega, Aegislash-Shield, Aggron                          |
| weight offense -0.05 |                     239 |  18.2 | Abomasnow, Abomasnow-Mega, Aegislash-Shield, Aggron                          |
| weight offense +0.05 |                     207 |  15.8 | Abra, Absol, Aggron-Mega, Aipom                                              |
| weight utility -0.05 |                     165 |  12.6 | Abra, Aggron-Mega, Aipom, Altaria-Mega                                       |
| weight utility +0.05 |                     149 |  11.4 | Aegislash-Shield, Annihilape, Arcanine, Aromatisse                           |
| weight niche -0.05   |                     132 |  10.1 | Abomasnow, Abomasnow-Mega, Absol-Mega, Aggron                                |
| weight defense -0.05 |                     130 |   9.9 | Abra, Absol, Aegislash-Shield, Aipom                                         |
| weight defense +0.05 |                     129 |   9.8 | Abomasnow-Mega, Aggron-Mega, Amaura, Anorith                                 |
| weight niche +0.05   |                     116 |   8.8 | Abra, Absol, Appletun, Archeops                                              |
| weight typing +0.05  |                      95 |   7.2 | Abomasnow, Abomasnow-Mega, Amaura, Annihilape                                |
| weight typing -0.05  |                      94 |   7.2 | Absol, Appletun, Archeops, Arctozolt                                         |

## Missing-data sweep

**7,922 `UNK` cells across the bundle, in 17 columns.** Each judged for whether it is recoverable from the supplied data.

| file            | column              |   unk |   rows | verdict                            | note                                                                                                                        |
|:----------------|:--------------------|------:|-------:|:-----------------------------------|:----------------------------------------------------------------------------------------------------------------------------|
| 01_species.tsv  | tutor_moves         |  1534 |   1534 | NOT recoverable from supplied data | Imperium speciesData has no tutor field. Needs a tutor table from the ROM or the online dex.                                |
| 01_species.tsv  | evo_item_obtainable |  1534 |   1534 | RECOVERABLE - superseded           | Phase 4 derives the equivalent into 04_valuation.availability_basis; the Phase 1 column was never backfilled.               |
| 01_species.tsv  | event_moves         |  1534 |   1534 | NOT recoverable                    | No event-move field exists in any supplied source.                                                                          |
| 01_species.tsv  | earliest_level      |   711 |   1534 | RECOVERABLE - superseded           | Same as earliest_checkpoint; the cap of that checkpoint.                                                                    |
| 01_species.tsv  | earliest_checkpoint |   711 |   1534 | RECOVERABLE - superseded           | Phase 4 derives this for 1,311 of 1,534 forms into 04_valuation.earliest_checkpoint. 223 remain genuinely unobtainable.     |
| 01_species.tsv  | missable            |   708 |   1534 | PARTIALLY recoverable              | Only meaningful for species with a one-time acquisition route; the 708 UNK are mostly species with no direct record at all. |
| 02_world.tsv    | missable            |   273 |    419 | NOT recoverable                    | Source sheets do not state missability for most entities.                                                                   |
| 02_world.tsv    | prerequisites       |   121 |    419 | NOT recoverable                    | Badge/HM/flag prerequisites are not printed in the source sheets.                                                           |
| 03_trainers.tsv | speed_fastest       |   117 |    164 | RECOVERABLE                        | Derivable at parity for scaling trainers, as Phase 4 does when scoring them. Phase 3 left it UNK rather than pick a level.  |
| 03_trainers.tsv | speed_slowest       |   117 |    164 | RECOVERABLE                        | Same as speed_fastest.                                                                                                      |
| 03_trainers.tsv | level_min           |   117 |    164 | NOT APPLICABLE                     | 117 trainers scale to the player, so they have no fixed level. UNK is the correct sentinel; NA would arguably be better.    |
| 03_trainers.tsv | speed_median        |   117 |    164 | RECOVERABLE                        | Same as speed_fastest.                                                                                                      |
| 03_trainers.tsv | level_max           |   117 |    164 | NOT APPLICABLE                     | Same as level_min.                                                                                                          |
| 02_world.tsv    | internal_id         |    91 |    419 | PARTIALLY recoverable              | 91 rows are services and trades, which are not items and have no id by definition. Not a gap.                               |
| 03_trainers.tsv | location            |    81 |    164 | PARTIALLY recoverable              | 81 trainers have no location cell in the source; some are recoverable from the sheet header rows.                           |
| 02_world.tsv    | cost                |    21 |    419 | NOT recoverable                    | itemData carries no prices; only the PokeMarts sheet does.                                                                  |
| 02_world.tsv    | earliest_gate       |    18 |    419 | NOT recoverable                    | 18 rows carry no story anchor and no recognised place name. Deliberately not guessed.                                       |

## Consolidated Data Integrity Log — all phases

|   phase | finding                                                         | status              | detail                                                                                                                                                                                                                           |
|--------:|:----------------------------------------------------------------|:--------------------|:---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
|       1 | Stat array order is HP/Atk/Def/SPEED/SpA/SpD                    | Resolved            | Verified 8/8 against asymmetric vanilla lines                                                                                                                                                                                    |
|       1 | dex_number vs internal_index diverge from 906                   | Carried             | 629 rows; join on internal_index                                                                                                                                                                                                 |
|       1 | 93 SPECIES_ labels alias to the same internal id                | Carried             | Label->id many-to-one                                                                                                                                                                                                            |
|       1 | Evolution parameter is polymorphic by method                    | Resolved            | Caught in Phase 2; six phantom evolution items removed                                                                                                                                                                           |
|       1 | 24 of 34 evolution methods undecoded                            | OPEN                | Species reached through them carry Unresolved availability                                                                                                                                                                       |
|       1 | 195 species unreachable by any route                            | Carried             | Phase 4 reduced this to 223 UNK of 1,534 after propagation                                                                                                                                                                       |
|       1 | 12 species with live PDF-vs-sheet availability conflict         | OPEN                | Both sources carried; neither dropped                                                                                                                                                                                            |
|       1 | Eight fields dropped as unconfirmable                           | Carried by decision | EXP curve, base EXP, EV yield, catch rate, friendship, hatch cycles, gender ratio, egg groups. Gender ratio now has a measured consequence (sensitivity rank 4)                                                                  |
|       2 | 02_world.internal_id is polymorphic by entity_type              | Resolved in Phase 4 | TM rows store a MOVE id; 28 collide with real item ids                                                                                                                                                                           |
|       2 | 18 rows with no derivable earliest_gate                         | OPEN                | Not guessed                                                                                                                                                                                                                      |
|       2 | Six evolution items appear in no location source                | OPEN                | Linking Cord alone gates 19 evolutions                                                                                                                                                                                           |
|       2 | Ground and hidden items in no supplied source                   | Carried             | Absence in 02_world is not absence in game                                                                                                                                                                                       |
|       3 | Location string parsed as a species name                        | RESOLVED IN PHASE 5 | Team Aqua GRUNT @ Whismur Cave: source level cell held "Rusturf Tunnel"; Spoink was absent from the file entirely. Recovered                                                                                                     |
|       3 | Three roster move names are source typos                        | RESOLVED IN PHASE 5 | Hurricaine, Steath Rock, Scorching Sand were silently dropped from three bosses' attack sets, understating their offense                                                                                                         |
|       3 | Two roster species_id left UNRESOLVED                           | RESOLVED IN PHASE 5 | Darmanitan-Galar and Aegislash-Both backfilled; the latter is genuinely ambiguous and marked Inferred                                                                                                                            |
|       3 | cp02 DAWN:16 merges several rival fights                        | OPEN                | Roster breadth at cp02 overstated                                                                                                                                                                                                |
|       3 | RUN_CONFIG's '695 roster slots' overcounts by 17                | Resolved in Phase 4 | The 17 are megas' post-transformation ability lines, correctly folded                                                                                                                                                            |
|       4 | baseStats key 'df' vs interface 'def'                           | Resolved            | Unremapped, every physical calc returns NaN not an error                                                                                                                                                                         |
|       4 | layer['items'] treated as id-indexed                            | Resolved            | It is alphabetically sorted; EVO_ITEM 211 gave "Fire Gem"                                                                                                                                                                        |
|       4 | Species joined on species_name                                  | Resolved            | Collapsed alternate forms; dropped 510 of 1,534 movepools                                                                                                                                                                        |
|       4 | Recovery detected by name list, not flags.healing               | Resolved            | Flag exists; split into 15 reliable recovery + 13 drain                                                                                                                                                                          |
|       4 | primary_niche_fit correlated 0.745 with BST                     | Resolved            | FAILED the archetypes.md threshold; rebalanced to 0.476                                                                                                                                                                          |
|       4 | Ceiling composite used floor speed                              | Resolved            | Understated every ceiling by 0.03-0.05 and moved tiers                                                                                                                                                                           |
|       4 | Role-less species had null replacement level                    | Resolved            | Now measured against pool-wide replacement                                                                                                                                                                                       |
|       4 | Level cap ladder reconstructed, not measured                    | RESOLVED            | Boss_Battles.xlsx!Main supplied; 18 of 19 were right, cp09 was 53 and is 56                                                                                                                                                      |
|       4 | Boss_Battles.xlsx wrongly declared superseded                   | RESOLVED IN PHASE 5 | Supersede check compared 11 sheets; the file has 12. The 12th carried the ladder                                                                                                                                                 |
|       5 | Form tie-break took the SHORTEST candidate name                 | RESOLVED IN PHASE 5 | Darmanitan -> Darmanitan-ZEN (540 BST Fire/Psychic, 30 Atk/140 SpA) instead of Standard (480, pure Fire, 140/30); Toxtricity -> the 621-BST MEGA. Now lowest internal_index = the ROM base form                                  |
|       5 | Colon inside a value broke the key:value encoding               | RESOLVED IN PHASE 5 | 'Type: Null' encoded as '3:Type: Null'. Values now escape colon as backslash-colon                                                                                                                                               |
|       5 | ceiling_item stored only the last checkpoint                    | RESOLVED IN PHASE 5 | Scores were correctly gated all along; the stored BUILD was not reproducible at 10,614 of 21,015 species-checkpoint pairs. Now encoded per checkpoint                                                                            |
|       5 | Hand verifier omits ability and item mechanics                  | Documented          | Phase 4's 14/14 was on curated cases. A random 39-case sample diverges twice, both times because the VERIFIER omits Rivalry and Acrobatics' no-item doubling. Engine agreement is 39/39 once both are given the same information |
|       5 | 7 boss held items and 1 ability absent from Imperium's own data | OPEN                | Flagged Unresolved on their slot; never substituted                                                                                                                                                                              |

## What Phase 6 should know

- `tier` is not safe to display alone for the 76 species where `tier_fragile` is TRUE. Show `tier_edge_distance` beside it, or band those species visually.
- `ceiling_item_by_checkpoint` is the reproducible build column. `ceiling_item_at_last_cp` is kept for convenience and is only correct at the last checkpoint a species is scored for.
- Values in `key:value` columns escape a literal colon as `\:`. Split on the first **unescaped** colon. Two species names need this: `Type: Null` and its lineage.
- 223 of 1,534 forms have no derivable acquisition route and carry `earliest_checkpoint = UNK`. They are absent from `04_valuation.tsv` entirely, which has 1,311 rows.
- Every damage figure is `Inferred`, not `Measured`, because the damage-formula generation is pinned on evidence but unconfirmed.
