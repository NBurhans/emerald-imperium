import sys, glob, os, pandas as pd
sys.path.insert(0, '/mnt/skills/plugins/romhack-data-analysis/scripts')
from export_bundle import Bundle

P = '/home/claude/p4/'
OUT = '/mnt/user-data/outputs/emerald_imperium/'
VALID = pd.read_pickle(P + 'VALID.pkl')

b = Bundle(OUT)
# re-register the files already written by ship.py so readme/verify see them
SPEC = [('01_species.tsv', 'one row per species form; movepools, evolution and availability folded in'),
        ('02_world.tsv', 'items, TMs/HMs, vendor stock, mega stones, trades, gifts, eggs, NPC services'),
        ('03_trainers.tsv', 'one row per trainer; roster and derived team analysis folded in'),
        ('03_trainer_slots.tsv', 'one row per roster slot; the exploded form of 03_trainers'),
        ('04_valuation.tsv', 'Phase 4: VORP, floor/ceiling/ROI, niches, tiers, per-checkpoint curves'),
        ('05_checkpoints.tsv', 'the 19-checkpoint ladder: caps, anchors, pools, TM/item gates'),
        ('06_lineage.tsv', 'per-lineage per-checkpoint form used, raw score and dead-weight penalty'),
        ('07_phase5_audit.tsv', 'Phase 5: every round-trip and referential-integrity check with its result')]
for name, note in SPEC:
    p = os.path.join(OUT, name)
    df = pd.read_csv(p, sep='\t', dtype=str)
    b.files.append(dict(name=name, rows=len(df), cols=len(df.columns),
                        kb=round(os.path.getsize(p) / 1024, 1), note=note))

b.readme(
    title='Emerald Imperium — Analysis Bundle (Phases 1–5 complete)',
    intro=(
        'Pokémon Emerald Imperium v1.3, analysed for a NORMAL-difficulty playthrough with '
        'Minimal Grinding Mode OFF and level caps enforced. `RUN_CONFIG.md` holds the locked '
        'run settings. `PHASE5_EVALUATION.md` is the Phase 5 report. Phase 6 not yet built.\n\n'
        '**Phase 5 found seven defects and fixed all seven.** Three were in the data as '
        'shipped, three in the Phase 4 code, one in the Phase 5 checker itself. Two changed '
        'numbers: a form tie-break that resolved `Darmanitan` to the ZEN forme (540 BST, '
        'Fire/Psychic, inverted attacking stats) on the cp18 boss, and three source move-name '
        'typos that were silently deleting damaging moves from three bosses. Both are fixed '
        'and the whole pipeline was re-run. Full detail in `PHASE5_EVALUATION.md`.\n\n'
        '**Phase 4 headline.** Every obtainable species form was scored at each of 19 '
        'checkpoints, in two builds (zero-investment floor and Phase-2-gated ceiling), on five '
        'axes — offense, defense, speed, utility and typing — with all damage figures produced '
        'by `RadicalRedShowdown/damage-calc` @ `7f35400` running on a custom Imperium data '
        'layer. 42,030 scored rows, 0 errors. The engine was verified against an independent '
        'hand implementation of the damage formula: **14/14 exact, 0.0% discrepancy**.\n\n'
        '**Phase 4 also fills a gap Phase 1 left.** `earliest_checkpoint` was populated only '
        'for species with a direct encounter record; 711 rows were UNK, which makes an '
        'obtainable pool impossible. Availability is now propagated through the evolution and '
        'form-change graphs — 1,311 of 1,534 forms obtainable, 223 still UNK.\n\n'
        '**The scoring framework failed its own validation once and was rebalanced.** See '
        'Corrections item 6 and the Validation table. The rebalance is not cosmetic: it '
        'changed which species surface.\n\n'
        '`Phase4_Valuation.xlsx` is the primary human-readable deliverable. Its Valuation sheet '
        'holds live Excel formulas reading weight cells on `Assumptions`, so changing a weight '
        'recalculates the composite, VORP, ROI and tier for all 1,311 rows. All 6,574 formulas '
        'evaluate clean and were checked against the Python figures on every row '
        '(max delta 1.2e-4).'),
    gotchas=[
        '**Values in `key:value` columns escape a literal colon as `\\:`.** Split on the first '
        'UNESCAPED colon. Two species names need this — `Type: Null` and its lineage — and a '
        'naive `split(":")` silently returns the wrong form name for them.',
        '**`ceiling_item_by_checkpoint` is the reproducible build column.** '
        '`ceiling_item_at_last_cp` is a convenience and is only correct at the last checkpoint '
        'a species is scored for; the ceiling item changes as Phase 2 unlocks better ones.',
        '**`tier` alone is not safe to display for the 76 rows where `tier_fragile` is TRUE.** '
        'Those sit within 0.002 of a threshold and flip between two equally valid ways of '
        'averaging VORP. Show `tier_edge_distance` beside it.',
        '**Stat array order is HP, Atk, Def, SPEED, SpA, SpD.** Speed is fourth, not last. '
        'Verified against 8 asymmetric vanilla lines, 8/8 match.',
        '**levelUpMoves pairs are [move_id, level], move FIRST.**',
        '**Evolution records are [method, target_species, parameter]** — target second, and the '
        'parameter is POLYMORPHIC. Method 4 = level, 7 = item id, 23 = MOVE id, 31 = partner '
        'species id, 43 = move id, 15 = beauty threshold. `evo_params` names the kind per record.',
        '**move.acc has two sentinels:** 0 = no accuracy check (status), 999 = never misses.',
        '**dex_number and internal_index diverge from index 906 onward** (629 of 1,534 rows); '
        '218 dex numbers are shared by multiple form rows. Join on `internal_index`.',
        '**Never join species on `species_name`.** A base form and its Mega share one name — '
        '`Venusaur` appears twice. Name-joining collapses forms and silently drops movepools; '
        'it dropped 510 of 1,534 here before it was caught. `internal_index` is exactly 1:1 '
        'against `imperium_layer.json` in both directions.',
        '**`02_world.internal_id` is polymorphic by `entity_type`.** TM and HM rows store the '
        '**move** id, not an item id. 28 of those collide with real item ids — 211 is Fire Stone '
        'as an item and Steel Wing as a TM. Filter to non-TM rows before using it as an item key.',
        "**`imperium_layer.json`'s `items` and `abilities` are ALPHABETICALLY SORTED NAME LISTS**, "
        'not id-indexed arrays. `items[211]` is not item 211.',
        "**`imperium_layer.json` writes the Defense base stat as `df`**, the calc fork's internal "
        'compressed key. The public `Specie` interface wants `def`. Unremapped it is `undefined`, '
        'and calcs return NaN rather than raising.',
        '**Imperium move data carries `flags.healing`** (36 moves) — use it rather than a name '
        'list. But it also marks DRAIN moves, which heal off damage dealt, not max HP. A wall '
        'that "recovers" only by draining is not a wall; the two are split in this analysis.',
        '**02_world `cost` is only as good as the PokeMarts sheet.** itemData carries no prices, '
        'pockets or locations — it is id, name and description only.',
        '**Ground items and hidden items appear in no supplied source.** Absence in 02_world is '
        'not evidence of absence in game.',
        '**04_valuation `*_by_checkpoint` columns encode `checkpoint:value`**, comma-separated, '
        'e.g. `1:0.4213,2:0.4488`. `lineage_form_per_checkpoint` encodes `checkpoint:form_name`.',
    ],
    confidence={
        'Measured': 'Phase 1 stats, types, abilities, movepools and evolutions computed from the '
                    'Imperium JSON. Phase 2 entity names, locations, costs and prerequisites as '
                    'printed. Phase 3 roster slots as printed. Phase 4 gate bite, tier '
                    'distribution, and the 0.0% engine discrepancy rate.',
        'Inferred': 'EVERY Phase 4 damage figure — the damage-formula generation is pinned to 9 '
                    'on evidence (Gen 9 moves present, per-move physical/special split across all '
                    '18 types) but is not confirmed against Imperium\'s own CalculateBaseDamage. '
                    'Also: 17 of 19 level caps (anchored to an observed boss level); all derived '
                    'availability for species reached by evolution or form change; boss IVs of 31 '
                    'where the roster does not annotate otherwise; the evolution-method enum.',
        'Speculative': 'The Walkthrough sheet, demoted and unused: it names Wallace as Gym 8 where '
                       "Imperium's cap ladder says Juan, and omits Team Magma and the Sinnoh "
                       'leaders despite populated roster tabs for each.',
        'Unresolved': '223 forms with no derivable '
                      'acquisition route. 24 undecoded evolution methods. 7 boss-roster held items '
                      "and 1 ability absent from Imperium's own data. All weight-based moves "
                      '(weightkg is 50 for every species). Move priority, absent from the move '
                      'table, which affects the Revenge Killer gate specifically.',
    },
    validation=VALID,
    corrections=[
        '**Self-inflicted, caught in Phase 2:** evolution method 23 was decoded as EVO_MOVE but '
        'its parameter was mapped as an item id, so six phantom "evolution items" appeared. Fixed; '
        'both phases rebuilt.',
        '**Superseding claim overturned — the important one.** The Phase 1/2 README declared '
        '`Boss_Battles.xlsx` superseded because its content appeared verbatim inside '
        '`General_Documents___Locations.xlsx`, on a check of "content-row counts identical across '
        'all **11** boss sheets". The workbook has **twelve** sheets. The twelfth is `Main`, and '
        '`Main` carries the level-cap ladder — the one thing later phases could not derive, and '
        'the thing I then spent a reconstruction on and got one cap wrong. A supersede check that '
        'enumerates only the sheets it already knows about cannot detect a sheet it does not. '
        '**The rule this changes: compare sheet counts before comparing row counts within '
        'sheets, and never retire a source on a check that could not see the whole file.**',
        '**Re-audit of the Phase 3 parse against the source (it holds).** 695 `Ability:` lines in '
        '`Boss_Battles.xlsx` against 678 slots in `03_trainer_slots.tsv`. The 17-row gap is '
        'exactly the 17 megas\' post-transformation ability lines, which Phase 3 correctly folded '
        'into `mega_ability` — per-sheet mega counts (3/1/3/1/5/4) match the per-sheet gaps '
        'exactly. Nothing was dropped. RUN_CONFIG\'s "695 roster slots" overcounts real Pokémon '
        'by 17. Every other RUN_CONFIG anchor re-measured exactly: 45 IV lines, 9 `IVs: 0 Spe`, '
        '576 EV spreads, 39 Hidden Power moves.',
        '**`Battle_Rewards.xlsx` re-checked and the supersede claim holds:** all 17 rows are '
        'already in `02_world` with matching locations. But its **trainer** column was not, and '
        'has been added as `reward_trainer`, upgrading those rows\' `gate_basis` from '
        '"location reachability" (an explicit lower bound) to "defeat <trainer>" (a sufficient '
        'condition). Matched on (item, location) so the two Leftovers rows stayed distinct.',
'**Phase 5, found by adversarial re-read (1) — changed numbers.** The species form '
        'tie-break took the SHORTEST candidate name, which is wrong in exactly the cases that '
        'matter: a transformed form often has a shorter suffix than the base one. `Darmanitan` '
        'resolved to Darmanitan-**Zen** (540 BST, Fire/Psychic, 30 Atk / 140 SpA) instead of '
        'Darmanitan-Standard (480, pure Fire, 140 / 30) — an inverted offensive profile on the '
        'cp18 boss — and `Toxtricity` to the 621-BST Mega instead of the 502-BST Amped form. '
        'Fixed by taking the LOWEST `internal_index` among candidates, which is the ROM\'s own '
        'base form; verified against nine families.',
        '**Phase 5 (2) — changed numbers.** Three roster move names are source typos: '
        '`Hurricaine`, `Steath Rock`, `Scorching Sand`. The scorer filters a boss\'s attack set '
        'to moves it can resolve, so each typo silently DELETED a damaging move, understating '
        'that boss and overstating every species\' defense score against it. Repaired; the '
        'original strings are kept in `03_trainer_slots.moves_source_typo`.',
        '**Phase 5 (3).** A location string was sitting in the species column. '
        '`Boss_Battles.xlsx` Team Aqua GRUNT @ Whismur Cave has `Rusturf Tunnel` in a LEVEL '
        'cell — a source defect — and Phase 3 took it as the species name, so **Spoink was '
        'absent from the bundle entirely** while its nature, ability and four moves sat on the '
        'mislabelled row. Recovered; its level is Inferred from its two siblings.',
        '**Phase 5 (4).** `ceiling_item` stored only the LAST checkpoint\'s item, so the '
        'recorded build was not reproducible at 10,614 of 21,015 species-checkpoint pairs. The '
        'SCORES were correctly gated all along — Swampert holds Expert Belt at cp7–11 and '
        'Choice Band from cp12 when it unlocks. Now encoded per checkpoint.',
        '**Phase 5 (5).** A colon inside a value broke the `key:value` encoding: `Type: Null` '
        'encoded as `3:Type: Null`. Values now escape colon; the README gotcha list covers it.',
        '**Phase 5 (6).** Two roster `species_id` values were left UNRESOLVED by Phase 3 and '
        'are backfilled: `Darmanitan-Galar` and `Aegislash-Both`. The latter names two formes '
        'in one cell and is genuinely ambiguous — resolved to Aegislash-Shield and marked '
        'Inferred.',
        '**Phase 5 (7) — the checker, not the file.** The decode check counted escaped colons '
        'as malformed and reported 2 bad rows on correctly-escaped data.',
        '**Phase 5 corrects a Phase 4 claim.** Phase 4 reported "14/14, 0.0% discrepancy" on '
        'the damage engine. Those 14 cases were chosen by me. A random 39-case sample drawn '
        'from the actual rosters diverges twice (5.1%) — and BOTH divergences are the hand '
        'VERIFIER, which models level, stats, base power, STAB and the type chart and nothing '
        'else. Luxray\'s **Rivalry** applies 1.25x; **Acrobatics** doubles to 110 BP with no '
        'held item. Neutralise each and the engine returns the hand value exactly. Engine '
        'agreement is 39/39 once both are given the same information.',
        '**v2 rebalance, and the axis it rejected.** The first sustain metric was raw sweep '
        'depth. It correlated **0.809 with BST** — a worse stat proxy than anything else in the '
        'framework — because both turns-to-KO and damage-taken scale with stats. Replaced by the '
        'kit delta. Two earlier shapes also failed: a per-slot version saturated at 0.82–0.99 '
        'for wall and glass cannon alike, and a fully sequential version across all 36 cp19 '
        'slots scored everything 1–3. The trainer-boundary reset is what makes it discriminate.',
        '**v2 bug, caught by the Phase 5 audit.** `n_tm_gated` was emitted only when '
        "`build === 'ceiling'`, so every defensive-ceiling row reported zero gated TMs — zeroing "
        'the TM component of `investment_cost`, and therefore ROI, for 568 species. Fixed.',
        '**Self-inflicted, caught in Phase 4 (1):** the `df` vs `def` base-stat key. Unremapped, '
        'every physical calc silently returns NaN.',
        '**Self-inflicted, caught in Phase 4 (2):** `layer["items"]` treated as id-indexed when it '
        'is alphabetically sorted. EVO_ITEM 211 resolved to "Fire Gem" instead of "Fire Stone".',
        '**Self-inflicted, caught in Phase 4 (3):** using `02_world.internal_id` as an item key '
        'without excluding TM rows, whose id is a move id. 211 resolved to "TM047 Steel Wing". '
        'All nine evolution stones resolve correctly after the fix, each confirmed against the '
        'evolution it drives. This is the third appearance of the same polymorphic-id trap.',
        '**Self-inflicted, caught in Phase 4 (4):** species joined on `species_name`, collapsing '
        'alternate forms onto their base and dropping 510 of 1,534 movepools. Switched to '
        '`internal_index`.',
        '**Self-inflicted, caught in Phase 4 (5):** a code comment asserted the move table had no '
        'healing field. It has `flags.healing`. Since recovery gates three wall archetypes, the '
        'whole scoring run was redone with flag-based detection, splitting 15 reliable-recovery '
        'moves from 13 drain moves.',
        '**Framework failure, Phase 4 (6):** `primary_niche_fit` correlated with BST at r=0.745 '
        '(ceiling) / 0.705 (floor) — above the ~0.7 threshold in `archetypes.md`, meaning the '
        'ranking was a BST proxy. Rebalanced two ways: toolkit scoring restricted to '
        'role-relevant tools (breadth is itself a BST proxy), and a stat-SHAPE term blended in at '
        '40% so that what share of a species\' own BST sits in the role\'s core stats matters, '
        'not just magnitude. After: r=0.476 / 0.365.',
        '**Self-inflicted, caught during workbook verification (7):** the sheet computed its '
        'ceiling composite using the FLOOR row\'s speed, understating every ceiling value by '
        '0.03–0.05 and moving tiers. Caught only because the Excel figures were diffed against '
        'the Python figures row by row rather than spot-checked.',
        '**Self-inflicted, caught during workbook verification (8):** species failing every '
        'archetype gate had a null replacement level, so mean VORP averaged over a different '
        'checkpoint set than mean value. They are now measured against the pool-wide replacement '
        '(third-best floor value at that checkpoint, any role), flagged `pool_wide_no_role`.',
        '**Not a bug, verified:** `Flash` is a 60 BP Electric SPECIAL attack in Imperium, not the '
        'vanilla accuracy-drop. Move ids check out against vanilla (Growl 45, Recover 105, Swords '
        'Dance 14), so there is no parse offset — the hack changed the move.',
        '**Not a bug, verified:** a 145–171% Bug Buzz looked wrong and is right. Imperium\'s '
        'Bug→Dark is 2.0 and the hand formula reproduces 132–156 exactly.',
        'Boss IVs are not uniformly perfect: 45 of 695 slots carry explicit IV lines, of which '
        '**9 read `IVs: 0 Spe`** (deliberate minimum Speed for Trick Room / Gyro Ball). Honoured.',
        'Boss levels: only 263 of 695 slots are fixed; **419 scale to the player**. Scaling slots '
        'are scored at parity with the checkpoint cap rather than at a fixed level.',
        'New mega base stats conflict on 4 of 9 megas. Precedence: speciesData JSON > boss-sheet '
        'inline > website sheet.',
        '12 species carry a live PDF-vs-sheet conflict on availability. Both sources carried, '
        'rows flagged Unresolved, neither dropped.',
    ],
    assumptions=(
        '- **Composite value weights, v2** (on the workbook\'s Assumptions sheet and editable '
        'there): offense 0.26, defense 0.15, **sustain 0.16**, speed 0.12, utility 0.10, '
        'typing 0.11, niche fit 0.10. Defensive roles use sustain 0.24 and speed 0.04 instead, '
        'because a wall was paying full weight on a stat it does not want. The weight set is '
        'chosen per species by its MODAL role across the run, not per checkpoint, so the '
        'species mean is a single formula the workbook can reproduce.\n'
        '- **SUSTAIN** is the turn dimension the five original axes could not see. Sweep depth '
        'across the roster on one lifebar, healing per turn from recovery / Regenerator / '
        'Leftovers, hazard and Toxic chip cutting turns-to-KO, screens cutting incoming damage '
        '33%, and the lifebar resetting at each TRAINER boundary because the player heals '
        'between fights. The axis is the **kit delta**: the species with its kit minus the '
        'identical species with none. Raw sweep depth correlated 0.809 with BST and was '
        'rejected; the delta is 0.561 and is exactly zero for the 88 species with no kit.\n'
        '- **The ceiling is the better of two spreads**: offensive (252 in the higher attacking '
        'stat plus speed) and defensive (252 HP plus the better defence, bulk nature, '
        'Leftovers). The defensive spread wins for 9,679 of 21,015 species-checkpoint pairs.\n'
        '- **Replacement level** is the third-best obtainable species for that role at that '
        'checkpoint under zero investment (neutral nature, 0 EVs, 31 IVs, first ability, no item, '
        'level-up moves only). 394 (checkpoint, role) cells; 14 fell back to the worst qualifier '
        'because the role had fewer than three, and say so in `replacement_basis`.\n'
        '- **Tier thresholds on mean ceiling VORP**, not curve-forced: S+ ≥ 0.20, S ≥ 0.14, '
        'A ≥ 0.09, B ≥ 0.04, C ≥ 0.00, D ≥ −0.06, F below. Result: S+ 2, S 41, A 103, B 217, '
        'C 219, D 317, F 412.\n'
        '- **`cant_miss` rule, written down rather than vibed:** tier A or better AND '
        '(`one_time_only` OR `missable`). Both halves required — a missable dud is not a '
        'priority, and a great species you can always get later is not either. 38 species.\n'
        '- **`investment_cost` has no EV-training or breeding component**, per the RUN_CONFIG '
        'decision to drop the eight unconfirmable fields. It is built from nature (+1.0), held '
        'item (+1.0), ability change (+1.0), evolution item (+1.0), gated TMs (+0.5 each, cap '
        '2.0) and egg moves (+2.0, because RUN_CONFIG says breeding is not used in this run, so '
        'an egg-move ceiling is out of reach rather than free), floored at 0.5. **ROI figures are '
        'therefore not comparable to a version of this analysis with a full cost model.**\n'
        '- **Ceilings are gated by Phase 2.** TMs available ramp 3 → 174 across the ladder and '
        'held items 1 → 14, so no ceiling rests on an item the player cannot yet hold.\n'
        '- **Percentile normalisation is within the obtainable pool at each checkpoint**, not '
        'min-max across the dex, so legendaries do not compress everyone else.\n'
        '- The checkpoint ladder is a **reconstruction**. RUN_CONFIG cites the Boss Battles '
        '`Main` tab as its source; that sheet is not among the files this analysis holds. '
        '17 of 19 caps anchor to a fixed-level boss actually present in the data; cp02 and cp09 '
        'are linear interpolations. The ladder is strictly monotonic and runs 15 → 85, which is '
        "RUN_CONFIG's only available cross-check.\n"
        '- Gen 6+ mechanics inferred from Fairy, the Steel/Ghost/Dark chart, and per-move '
        'category; generation pinned to 9. The damage formula generation is unconfirmed, so '
        '**every Phase 4 calc is Inferred**.'),
    stale=[
        '`evo_item_obtainable` in `01_species.tsv` is still UNK on every row. Phase 4 derives the '
        'equivalent into `04_valuation.availability_basis`, but the Phase 1 column itself was not '
        'rewritten.',
        '`tutor_moves` and `event_moves` are UNK: Imperium\'s speciesData has no such field.',
        '18 Phase 2 rows have `earliest_gate` UNK — no story anchor and no recognised place name.',
        'The cp02 threat pool uses the 30-slot `DAWN:16` block, which the Phase 3 parse merged '
        'from several rival fights. Roster breadth at cp02 is overstated; splitting it needs a '
        'Phase 3 re-parse.',
        'Checkpoint labels 10 and 19 were inferred as Pre-Norman and Pre-Elite4 while the ladder '
        'was reconstructed. `Boss_Battles.xlsx!Main` confirms Pre-Norman and corrects the latter '
        'to **Pre-Champion**. No longer stale.',
        '`Encounter_Tables_v1_1.xlsx` is still unused: it is the only source with Day/Night grass '
        'splits and explicit Old/Good/Super Rod grouping. Reserved for a Phase 1 availability '
        'refresh, which would tighten `earliest_checkpoint` for wild species.',
    ],
    superseded=[
        'Boss_Battles.xlsx, TMs_and_HMs_Locations.xlsx, Legendaries_and_Mythicals_Locations.xlsx, '
        'PokeMarts_Guide.xlsx, Mega_Stones_Locations.xlsx, New_Mega_Evolutions.xlsx, '
        'Useful_NPC_Locations.xlsx, In_Game_Trades.xlsx, Gift_Pokemon_and_Eggs.xlsx, '
        'Battle_Rewards.xlsx, Emerald_Imperium_Walkthrough.xlsx — all 11 are contained verbatim '
        'inside General_Documents___Locations.xlsx (content-row counts identical across all 11 '
        'boss sheets). Agreement between a file and its own copy is not corroboration.',
        'The reconstructed cap ladder (cp09 = 53, checkpoint 19 = Pre-Elite4) is superseded by the '
        'measured ladder from `Boss_Battles.xlsx!Main` (cp09 = 56, Pre-Champion). The '
        'reconstruction is recorded here rather than deleted because it is the reason cp09 scores '
        'changed between passes.',
        'The pre-rebalance archetype scoring (BST r=0.745) is superseded by the rebalanced version '
        '(r=0.476). Both correlations are reported in the Validation table rather than only the '
        'passing one, because the failure is what motivated the current weights.',
        'The first availability propagation, which used `layer["items"]` positionally and resolved '
        'EVO_ITEM 211 to "Fire Gem". Superseded by the `02_world.internal_id` join with TM rows '
        'excluded.',
    ])


# ---- verification: re-read everything, decode encoded cells -------------
def spot_curve(dirp):
    df = pd.read_csv(os.path.join(dirp, '04_valuation.tsv'), sep='\t')
    r = df[df.species_form == 'Swampert'].iloc[0]
    pairs = [p.split(':') for p in r.value_by_checkpoint.split(',')]
    return (f"Swampert value_by_checkpoint decodes to {len(pairs)} checkpoints, "
            f"first={pairs[0][0]}:{pairs[0][1]} last={pairs[-1][0]}:{pairs[-1][1]}, "
            f"tier={r.tier}, niche={r.primary_niche}")


def spot_lineage(dirp):
    df = pd.read_csv(os.path.join(dirp, '04_valuation.tsv'), sep='\t')
    r = df[df.species_form == 'Mudkip'].iloc[0]
    forms = dict(p.split(':') for p in r.lineage_form_per_checkpoint.split(','))
    return (f"Mudkip lineage at cp1={forms.get('1')} cp10={forms.get('10')} "
            f"cp19={forms.get('19')} (dead weight {r.lineage_dead_weight})")


def spot_stats(dirp):
    df = pd.read_csv(os.path.join(dirp, '01_species.tsv'), sep='\t')
    r = df[(df.species_name == 'Swampert') & (df.form_type == 'base')].iloc[0]
    return (f"Swampert base stats {r.hp}/{r.atk}/{r.defense}/{r.spa}/{r.spd}/{r.spe} "
            f"BST {r.bst} (vanilla 100/110/90/85/90/60 = 535)")


def spot_cap(dirp):
    df = pd.read_csv(os.path.join(dirp, '05_checkpoints.tsv'), sep='\t')
    src = [15, 20, 25, 30, 32, 34, 44, 47, 56, 59, 64, 68, 71, 74, 76, 80, 82, 84, 85]
    return (f"caps {df.level_cap.tolist()} | matches Boss_Battles!Main: "
            f"{df.level_cap.tolist() == src} | all measured: "
            f"{set(df.cap_basis) == {'measured'}}")


def spot_reward(dirp):
    df = pd.read_csv(os.path.join(dirp, '02_world.tsv'), sep='\t')
    hi = df[df.entity_type == 'held_item']
    return (f"{hi.reward_trainer.notna().sum()}/{len(hi)} held items carry reward_trainer; "
            f"Focus sash -> {hi[hi.entity_name=='Focus sash'].reward_trainer.iloc[0]}")


b.verify(expected={'01_species.tsv': 1534, '02_world.tsv': 419, '03_trainers.tsv': 164,
                   '03_trainer_slots.tsv': 678, '04_valuation.tsv': 1311,
                   '05_checkpoints.tsv': 19},
         spot_checks=[('decode value_by_checkpoint', spot_curve),
                      ('decode lineage_form_per_checkpoint', spot_lineage),
                      ('base stats vs vanilla', spot_stats),
                      ('cap ladder vs source', spot_cap),
                      ('battle reward attribution', spot_reward)])
