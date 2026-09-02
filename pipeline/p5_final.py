"""Phase 5 deliverables: consolidated integrity log, sensitivity analysis with
named species, UNK recoverability judgment, and the audit TSV."""
import pandas as pd, json, numpy as np, os

P = '/home/claude/p4/'
B = '/mnt/user-data/outputs/emerald_imperium/'
S1 = json.load(open(P + 'p5_stage1.json'))
S2 = json.load(open(P + 'p5_stage2.json'))
SW = pd.read_csv(P + 'p5_unk_sweep.tsv', sep='\t')
SENS = pd.read_csv(P + 'p5_sensitivity.tsv', sep='\t')
IN = json.load(open(P + 'scoring_input.json'))
V = pd.read_csv(B + '04_valuation.tsv', sep='\t')
Vv = pd.read_pickle(P + 'valuation.pkl')
d = pd.read_pickle(P + 'archetypes.pkl')

# ---------------- consolidated audit table ----------------
AUD = pd.DataFrame(S1 + S2)
AUD['phase'] = 5

# ---------------- UNK recoverability judgment ----------------
JUDGE = {
    ('01_species.tsv', 'tutor_moves'):
        ('NOT recoverable from supplied data', 'Imperium speciesData has no tutor field. '
         'Needs a tutor table from the ROM or the online dex.'),
    ('01_species.tsv', 'event_moves'):
        ('NOT recoverable', 'No event-move field exists in any supplied source.'),
    ('01_species.tsv', 'evo_item_obtainable'):
        ('RECOVERABLE - superseded', 'Phase 4 derives the equivalent into '
         '04_valuation.availability_basis; the Phase 1 column was never backfilled.'),
    ('01_species.tsv', 'earliest_checkpoint'):
        ('RECOVERABLE - superseded', 'Phase 4 derives this for 1,311 of 1,534 forms into '
         '04_valuation.earliest_checkpoint. 223 remain genuinely unobtainable.'),
    ('01_species.tsv', 'earliest_level'):
        ('RECOVERABLE - superseded', 'Same as earliest_checkpoint; the cap of that checkpoint.'),
    ('01_species.tsv', 'missable'):
        ('PARTIALLY recoverable', 'Only meaningful for species with a one-time acquisition '
         'route; the 708 UNK are mostly species with no direct record at all.'),
    ('02_world.tsv', 'missable'):
        ('NOT recoverable', 'Source sheets do not state missability for most entities.'),
    ('02_world.tsv', 'prerequisites'):
        ('NOT recoverable', 'Badge/HM/flag prerequisites are not printed in the source sheets.'),
    ('02_world.tsv', 'internal_id'):
        ('PARTIALLY recoverable', '91 rows are services and trades, which are not items and '
         'have no id by definition. Not a gap.'),
    ('02_world.tsv', 'cost'):
        ('NOT recoverable', 'itemData carries no prices; only the PokeMarts sheet does.'),
    ('02_world.tsv', 'earliest_gate'):
        ('NOT recoverable', '18 rows carry no story anchor and no recognised place name. '
         'Deliberately not guessed.'),
    ('03_trainers.tsv', 'level_min'):
        ('NOT APPLICABLE', '117 trainers scale to the player, so they have no fixed level. '
         'UNK is the correct sentinel; NA would arguably be better.'),
    ('03_trainers.tsv', 'level_max'):
        ('NOT APPLICABLE', 'Same as level_min.'),
    ('03_trainers.tsv', 'speed_fastest'):
        ('RECOVERABLE', 'Derivable at parity for scaling trainers, as Phase 4 does when '
         'scoring them. Phase 3 left it UNK rather than pick a level.'),
    ('03_trainers.tsv', 'speed_slowest'): ('RECOVERABLE', 'Same as speed_fastest.'),
    ('03_trainers.tsv', 'speed_median'): ('RECOVERABLE', 'Same as speed_fastest.'),
    ('03_trainers.tsv', 'location'):
        ('PARTIALLY recoverable', '81 trainers have no location cell in the source; some are '
         'recoverable from the sheet header rows.'),
}
rows = []
for _, r in SW[SW.UNK > 0].iterrows():
    j = JUDGE.get((r.file, r.column), ('UNJUDGED', ''))
    rows.append(dict(file=r.file, column=r.column, unk=int(r.UNK), rows=int(r.rows),
                     verdict=j[0], note=j[1]))
UNKJ = pd.DataFrame(rows).sort_values('unk', ascending=False)

# ---------------- sensitivity: named species per assumption ----------------
def tier_of(v):
    for t, lo in [('S+', .20), ('S', .14), ('A', .09), ('B', .04), ('C', 0.0), ('D', -.06)]:
        if v >= lo:
            return t
    return 'F'


base_tier = dict(zip(V.species_form, V.tier))

# 1. gender-dependent abilities
GENDER_DEP = {'Rivalry', 'Cute Charm'}
gender_species = sorted(k for k in V.species_form
                        if IN['species'].get(k) and IN['species'][k]['abilities']
                        and IN['species'][k]['abilities'][0] in GENDER_DEP)
# 2. tier-fragile
frag = V[V.tier_fragile == True].nsmallest(12, 'tier_edge_distance')
# 3. cp09 dependent (roster substituted + interpolated before)
cp09_only = V[V.earliest_checkpoint.astype(str) == '9']
# 4. weight-based moves (weightkg = 50 for everything)
WEIGHT_MOVES = {'Low Kick', 'Grass Knot', 'Heavy Slam', 'Heat Crash'}
wm = []
for k, sp in IN['species'].items():
    if k not in base_tier:
        continue
    pool = set(m for m, _ in sp['levelup']) | set(sp['tm']) | set(sp['egg'])
    if pool & WEIGHT_MOVES:
        wm.append(k)
# 5. species whose tier rests on an Unresolved availability basis
unres_avail = V[V.availability_confidence == 'Unresolved']

SENS_NAMED = [
    dict(rank=1, assumption='Composite weight on OFFENSE (0.30)',
         if_wrong='A +/-0.05 shift moves 306 / 263 species across a tier line (23.3% / 20.1%)',
         species_affected=306,
         named='Absol-Mega, Accelgor, Alakazam, Alakazam-Mega, Aggron-Mega, Altaria',
         mitigation='The weight is a lever cell on the workbook Assumptions sheet; '
                    'changing it recalculates all 1,311 rows live.'),
    dict(rank=2, assumption='Composite weight on SPEED (0.15)',
         if_wrong='A +/-0.05 shift moves 302 / 202 species (23.0% / 15.4%)',
         species_affected=302,
         named='Accelgor, Aegislash-Shield, Aggron-Mega, Alakazam, the Alcremie forms',
         mitigation='Same lever cell. Speed is the axis with the most tier churn per unit '
                    'of weight because it is near-binary per matchup.'),
    dict(rank=3, assumption='Damage-formula generation pinned to 9',
         if_wrong='Every damage figure in the project is Inferred on this. A different '
                  'multiplier order or crit rule would move offense and defense together, '
                  'so it would shift levels rather than ranks -- but the 2HKO/OHKO '
                  'thresholds are step functions and would move species across them.',
         species_affected=len(V),
         named='ALL 1,311 species forms',
         mitigation="Confirm against Imperium's own CalculateBaseDamage. Until then no "
                    'damage figure is Measured.'),
    dict(rank=4, assumption='Gender-dependent abilities resolve as same-gender',
         if_wrong='Rivalry applies 1.25x when attacker and defender share a gender and 0.75x '
                  'when they do not. gender_ratio was one of the eight fields dropped in '
                  'Phase 1 as unconfirmable, so the engine default stands unchallenged. The '
                  'true multiplier spans 0.75-1.25, a 67% swing on offense for these species.',
         species_affected=len(gender_species),
         named=', '.join(gender_species[:12]),
         mitigation='Supply a gender-ratio table, or set these species\' ability to their '
                    'second option and re-score.'),
    dict(rank=5, assumption='Tier thresholds are hard cuts',
         if_wrong='76 species sit within 0.002 of a threshold; their tier flips between the '
                  'two equally valid ways of averaging VORP.',
         species_affected=int((V.tier_fragile == True).sum()),
         named=', '.join(frag.species_form.head(10)),
         mitigation='Read tier_edge_distance alongside tier. Already a column.'),
    dict(rank=6, assumption='weightkg = 50 for every species',
         if_wrong='No Imperium source carries weight, so Low Kick, Grass Knot, Heavy Slam and '
                  'Heat Crash all compute at a fictional 50kg. Every damage figure involving '
                  'them is Unresolved, not Inferred.',
         species_affected=len(wm),
         named=', '.join(sorted(wm)[:10]),
         mitigation='Supply a weight table. Until then treat these four moves as absent.'),
    dict(rank=7, assumption='cp02 roster breadth',
         if_wrong='cp02 is scored against the 30-slot DAWN:16 block, which the Phase 3 parse '
                  'merged from several separate rival fights. Every species obtainable at '
                  'cp02 is scored against a roster wider than any single fight it will face.',
         species_affected=int((V.earliest_checkpoint.astype(str) == '2').sum()),
         named='all species first obtainable at cp02',
         mitigation='Re-parse the Rivals sheet to split DAWN:16 into its constituent fights.'),
    dict(rank=8, assumption='Availability derived through undecoded evolution methods',
         if_wrong='24 evolution methods are still raw integers. Species reached only through '
                  'them are dated to their pre-evolution, which is a LOWER bound -- they may '
                  'be obtainable much later or not at all.',
         species_affected=len(unres_avail),
         named=', '.join(unres_avail.species_form.head(10)),
         mitigation='Decode the remaining methods against the ROM evolution enum.'),
]
SENSN = pd.DataFrame(SENS_NAMED)

# ---------------- consolidated integrity log ----------------
LOG = [
    (1, 'Stat array order is HP/Atk/Def/SPEED/SpA/SpD', 'Resolved',
     'Verified 8/8 against asymmetric vanilla lines'),
    (1, 'dex_number vs internal_index diverge from 906', 'Carried',
     '629 rows; join on internal_index'),
    (1, '93 SPECIES_ labels alias to the same internal id', 'Carried', 'Label->id many-to-one'),
    (1, 'Evolution parameter is polymorphic by method', 'Resolved',
     'Caught in Phase 2; six phantom evolution items removed'),
    (1, '24 of 34 evolution methods undecoded', 'OPEN',
     'Species reached through them carry Unresolved availability'),
    (1, '195 species unreachable by any route', 'Carried',
     'Phase 4 reduced this to 223 UNK of 1,534 after propagation'),
    (1, '12 species with live PDF-vs-sheet availability conflict', 'OPEN',
     'Both sources carried; neither dropped'),
    (1, 'Eight fields dropped as unconfirmable', 'Carried by decision',
     'EXP curve, base EXP, EV yield, catch rate, friendship, hatch cycles, '
     'gender ratio, egg groups. Gender ratio now has a measured consequence '
     '(sensitivity rank 4)'),
    (2, '02_world.internal_id is polymorphic by entity_type', 'Resolved in Phase 4',
     'TM rows store a MOVE id; 28 collide with real item ids'),
    (2, '18 rows with no derivable earliest_gate', 'OPEN', 'Not guessed'),
    (2, 'Six evolution items appear in no location source', 'OPEN',
     'Linking Cord alone gates 19 evolutions'),
    (2, 'Ground and hidden items in no supplied source', 'Carried',
     'Absence in 02_world is not absence in game'),
    (3, 'Location string parsed as a species name', 'RESOLVED IN PHASE 5',
     'Team Aqua GRUNT @ Whismur Cave: source level cell held "Rusturf Tunnel"; '
     'Spoink was absent from the file entirely. Recovered'),
    (3, 'Three roster move names are source typos', 'RESOLVED IN PHASE 5',
     'Hurricaine, Steath Rock, Scorching Sand were silently dropped from three '
     "bosses' attack sets, understating their offense"),
    (3, 'Two roster species_id left UNRESOLVED', 'RESOLVED IN PHASE 5',
     'Darmanitan-Galar and Aegislash-Both backfilled; the latter is genuinely '
     'ambiguous and marked Inferred'),
    (3, 'cp02 DAWN:16 merges several rival fights', 'OPEN',
     'Roster breadth at cp02 overstated'),
    (3, "RUN_CONFIG's '695 roster slots' overcounts by 17", 'Resolved in Phase 4',
     "The 17 are megas' post-transformation ability lines, correctly folded"),
    (4, "baseStats key 'df' vs interface 'def'", 'Resolved',
     'Unremapped, every physical calc returns NaN not an error'),
    (4, "layer['items'] treated as id-indexed", 'Resolved',
     'It is alphabetically sorted; EVO_ITEM 211 gave "Fire Gem"'),
    (4, 'Species joined on species_name', 'Resolved',
     'Collapsed alternate forms; dropped 510 of 1,534 movepools'),
    (4, 'Recovery detected by name list, not flags.healing', 'Resolved',
     'Flag exists; split into 15 reliable recovery + 13 drain'),
    (4, 'primary_niche_fit correlated 0.745 with BST', 'Resolved',
     'FAILED the archetypes.md threshold; rebalanced to 0.476'),
    (4, 'Ceiling composite used floor speed', 'Resolved',
     'Understated every ceiling by 0.03-0.05 and moved tiers'),
    (4, 'Role-less species had null replacement level', 'Resolved',
     'Now measured against pool-wide replacement'),
    (4, 'Level cap ladder reconstructed, not measured', 'RESOLVED',
     'Boss_Battles.xlsx!Main supplied; 18 of 19 were right, cp09 was 53 and is 56'),
    (4, 'Boss_Battles.xlsx wrongly declared superseded', 'RESOLVED IN PHASE 5',
     'Supersede check compared 11 sheets; the file has 12. The 12th carried the ladder'),
    (5, 'Form tie-break took the SHORTEST candidate name', 'RESOLVED IN PHASE 5',
     "Darmanitan -> Darmanitan-ZEN (540 BST Fire/Psychic, 30 Atk/140 SpA) instead of "
     'Standard (480, pure Fire, 140/30); Toxtricity -> the 621-BST MEGA. Now lowest '
     'internal_index = the ROM base form'),
    (5, "Colon inside a value broke the key:value encoding", 'RESOLVED IN PHASE 5',
     "'Type: Null' encoded as '3:Type: Null'. Values now escape colon as backslash-colon"),
    (5, 'ceiling_item stored only the last checkpoint', 'RESOLVED IN PHASE 5',
     'Scores were correctly gated all along; the stored BUILD was not reproducible at '
     '10,614 of 21,015 species-checkpoint pairs. Now encoded per checkpoint'),
    (5, 'Hand verifier omits ability and item mechanics', 'Documented',
     "Phase 4's 14/14 was on curated cases. A random 39-case sample diverges twice, "
     "both times because the VERIFIER omits Rivalry and Acrobatics' no-item doubling. "
     'Engine agreement is 39/39 once both are given the same information'),
    (5, "7 boss held items and 1 ability absent from Imperium's own data", 'OPEN',
     'Flagged Unresolved on their slot; never substituted'),
]
CLOG = pd.DataFrame(LOG, columns=['phase', 'finding', 'status', 'detail'])

os.makedirs(B, exist_ok=True)
AUD.to_csv(B + '07_phase5_audit.tsv', sep='\t', index=False)
UNKJ.to_csv(P + 'p5_unk_judged.tsv', sep='\t', index=False)
SENSN.to_pickle(P + 'p5_sens_named.pkl')
CLOG.to_pickle(P + 'p5_clog.pkl')
UNKJ.to_pickle(P + 'p5_unkj.pkl')

print('checks run:', len(AUD))
print('clean:', int((AUD.severity == '—').sum()), '| material:',
      int((AUD.severity == 'Material').sum()), '| unresolved:',
      int((AUD.severity == 'Unresolved').sum()))
print()
print('--- UNK recoverability ---')
print(UNKJ[['file', 'column', 'unk', 'verdict']].to_string(index=False))
print()
print('--- consolidated integrity log by status ---')
print(CLOG.status.value_counts().to_string())
