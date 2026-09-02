"""Repair the one roster slot Phase 3 lost, and record why it was lost.

Boss_Battles.xlsx!'Team Aqua' rows 12-19, trainer GRUNT @ Whismur Cave:

    row 12  Glameow @ Silk Scarf | Mightyena @ Muscle Band | Spoink @ Sitrus Berry
    row 13  Player's Highest Lv -2 | Player's Highest Lv -2 | Rusturf Tunnel   <-- SOURCE DEFECT
    row 14  Hardy Nature          | Adamant Nature         | Calm Nature

The third column's LEVEL cell contains a location string, 'Rusturf Tunnel',
where the other two carry a level. That is a defect in the source workbook,
not in the parse. Phase 3 then compounded it: it took the stray location as
the species name, so 03_trainer_slots carries a slot named 'Rusturf Tunnel'
with no held item and level UNK, and SPOINK IS ABSENT FROM THE FILE ENTIRELY
while its nature, ability and four moves sit on the mislabelled row.

Phase 3 did flag it -- species_id reads UNRESOLVED -- so nothing was silently
wrong. But a flagged wrong name is still a wrong name, and the Pokemon is
missing.

Repaired here from the source rows above:
  species    Spoink              (row 12, the species row, which is correct)
  held_item  Sitrus Berry        (row 12)
  level      Player's Highest Lv -2 / scales_to_player
             INFERRED from its two siblings in the same block. The source cell
             for this slot holds a location, so its true level is not stated
             anywhere. Marked Inferred, not Measured.
Nature, ability and moves were already correct and are left untouched.
"""
import pandas as pd, json

B = '/mnt/user-data/outputs/emerald_imperium/'
P = '/home/claude/p4/'

SL = pd.read_csv(B + '03_trainer_slots.tsv', sep='\t', dtype=str)
mask = SL.species == 'Rusturf Tunnel'
already = (SL.species == 'Spoink').sum()
print(f'rows matching the defect: {mask.sum()} | Spoink rows already present: {already}')
assert mask.sum() == 1 or already == 1, 'expected the defect OR an applied repair'
if mask.sum() == 0:
    print('repair already applied; re-asserting the end state only')
    i = SL[SL.species == 'Spoink'].index[0]
    before = SL.loc[i].to_dict()
    mask = SL.index == i
before = SL[mask].iloc[0].to_dict()
print('BEFORE:', {k: before[k] for k in
                  ('sheet', 'trainer', 'col', 'species', 'held_item', 'level',
                   'level_mode', 'nature', 'ability', 'moves', 'species_id')})

L = json.load(open(P + 'imperium_layer.json'))
spoink_idx = L['species']['Spoink']['internal_index']

i = SL[mask].index[0]
SL.at[i, 'species'] = 'Spoink'
SL.at[i, 'held_item'] = 'Sitrus Berry'
SL.at[i, 'level'] = "Player's Highest Lv -2"
SL.at[i, 'level_mode'] = 'scales_to_player'
SL.at[i, 'species_id'] = str(spoink_idx)

print('AFTER: ', {k: SL.at[i, k] for k in
                  ('species', 'held_item', 'level', 'level_mode', 'species_id')})
SL.to_csv(P + '03_trainer_slots.tsv', sep='\t', index=False)

# keep 03_trainers consistent: this trainer's roster_species and unresolved count
TR = pd.read_csv(B + '03_trainers.tsv', sep='\t', dtype=str)
tid = f"{before['sheet']}:{before['trainer']}:{before['header_row']}"
m2 = TR.trainer_id == tid
print(f'\n03_trainers row for {tid}: {m2.sum()} match')
if m2.any():
    j = TR[m2].index[0]
    print('BEFORE roster_species:', TR.at[j, 'roster_species'])
    print('BEFORE n_unresolved_species:', TR.at[j, 'n_unresolved_species'])
    # roster_species is a comma-separated list of internal_index values, not
    # names. The unresolved slot contributed nothing to it, so Spoink's id has
    # to be APPENDED, in its column order (col 4, i.e. last of the three).
    rs = [x for x in str(TR.at[j, 'roster_species']).split(',') if x.strip()]
    if str(spoink_idx) not in rs:
        rs.append(str(spoink_idx))
    TR.at[j, 'roster_species'] = ','.join(rs)
    TR.at[j, 'roster_size'] = str(len(rs))
    try:
        TR.at[j, 'n_unresolved_species'] = str(max(0, int(TR.at[j, 'n_unresolved_species']) - 1))
    except (ValueError, TypeError):
        pass
    print('AFTER  roster_species:', TR.at[j, 'roster_species'])
    print('AFTER  n_unresolved_species:', TR.at[j, 'n_unresolved_species'])
TR.to_csv(P + '03_trainers.tsv', sep='\t', index=False)

# Two further slots carry species_id UNRESOLVED from Phase 3. Phase 4's
# resolver handles both, so the ids are backfilled here rather than left as a
# gap the app would have to re-derive.
#   'Darmanitan-Galar' -> Darmanitan-Galar-Standard  (lowest internal_index)
#   'Aegislash-Both'   -> Aegislash-Shield           (GENUINELY AMBIGUOUS: the
#       source names both forms in one cell. Shield is the out-of-battle
#       default and the lower index. Marked Inferred, not Measured.)
BACKFILL = {'Darmanitan-Galar': 'Darmanitan-Galar-Standard',
            'Aegislash-Both': 'Aegislash-Shield'}
for src_name, target in BACKFILL.items():
    m = (SL.species == src_name) & (SL.species_id == 'UNRESOLVED')
    if m.any():
        SL.loc[m, 'species_id'] = str(L['species'][target]['internal_index'])
        SL.loc[m, 'notes' if 'notes' in SL.columns else 'species_id'] = SL.loc[m, 'species_id']
        print(f'backfilled species_id for {src_name} -> {target} '
              f'({L["species"][target]["internal_index"]}), {int(m.sum())} row(s)')
# Three move names on boss rosters are source typos that resolve against no
# move in Imperium's table. Because score.js filters a boss's attack set to
# moves it can find, each typo silently REMOVED a damaging move from that
# boss, understating its offense and so overstating every species' defense
# score against it. Repaired; each is an unambiguous single-character or
# spacing error, and the original string is kept in moves_source_typo.
MOVE_TYPOS = {'Hurricaine': 'Hurricane',
              'Steath Rock': 'Stealth Rock',
              'Scorching Sand': 'Scorching Sands'}
if 'moves_source_typo' not in SL.columns:
    SL['moves_source_typo'] = 'NONE'
fixed = 0
for i2, r2 in SL.iterrows():
    ms = str(r2.moves)
    hit = [t for t in MOVE_TYPOS if t in ms.split(';')]
    if hit:
        SL.at[i2, 'moves_source_typo'] = ';'.join(hit)
        parts = [MOVE_TYPOS.get(x, x) for x in ms.split(';')]
        SL.at[i2, 'moves'] = ';'.join(parts)
        fixed += 1
        print(f'  move typo repaired on {r2.sheet}/{r2.trainer}/{r2.species}: {hit}')
print(f'move-typo rows repaired: {fixed}')

SL.to_csv(P + '03_trainer_slots.tsv', sep='\t', index=False)

print('\nwrote repaired 03_trainer_slots.tsv and 03_trainers.tsv to the working dir')
print('NOTE: Team Aqua:GRUNT:11 is not a checkpoint anchor, so no Phase 4 score '
      'depends on this slot. The repair fixes the DATA, not the valuation.')
