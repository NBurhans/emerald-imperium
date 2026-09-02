"""Trimmed dataset for the Pokédex-style dex, gzip+base64 for embedding.

What is dropped and why (the full detail lives in the TSVs, not here):
  egg moves       breeding is OFF in this run (RUN_CONFIG); listing them invites
                  building around moves the player cannot get
  6 axis curves   offense/defense/speed/typing/utility/replacement per
                  checkpoint -- the card keeps value, floor, VORP, role, item
  lineage forms   derived client-side from the evolution graph
  reasoning text  regenerated client-side from its components
Everything shown in the app is still exact to the bundle.
"""
import pandas as pd, json, re, gzip, base64

B = '/mnt/user-data/outputs/emerald_imperium/'
L = json.load(open('/mnt/user-data/uploads/imperium_layer.json'))
S = pd.read_csv(B + '01_species.tsv', sep='\t', dtype=str, keep_default_na=False)
W = pd.read_csv(B + '02_world.tsv', sep='\t', dtype=str, keep_default_na=False)
TR = pd.read_csv(B + '03_trainers.tsv', sep='\t', dtype=str, keep_default_na=False)
SL = pd.read_csv(B + '03_trainer_slots.tsv', sep='\t', dtype=str, keep_default_na=False)
V = pd.read_csv(B + '04_valuation.tsv', sep='\t', dtype=str, keep_default_na=False)
CP = pd.read_csv(B + '05_checkpoints.tsv', sep='\t', dtype=str, keep_default_na=False)
NA = ('NONE', 'NA', 'UNK', '')
nz = lambda v: '' if v in NA else v
ilist = lambda s: [] if s in NA else [int(x) for x in s.split(',') if x.strip()]
UNESC = re.compile(r'(?<!\\):')
def pairs(s):
    return [] if s in NA else [UNESC.split(p, 1)[1].replace('\\:', ':') for p in s.split(',')]
def i4(x):  # 4dp float -> int*10000
    return None if x in NA else int(round(float(x) * 10000))

name_by_idx = {v['internal_index']: k for k, v in L['species'].items()}
# category codes: P physical, S special, '-' status. The first draft used the
# first letter, which made Special and Status both 'S' -- special attacks then
# displayed with no power and were dropped from the party/boss type math.
CAT = {'Physical': 'P', 'Special': 'S', 'Status': '-'}
MOVES = {m['move_id']: [m['name'], m['type'], CAT[m['category']], m['basePower']] for m in L['moves'].values()}
TYPES = L['type_order']
CHART = [[L['types'][a][d] for d in TYPES] for a in TYPES]

NICHES = sorted(set(V.primary_niche) | set(V.niche_2) | set(V.niche_3) |
                {x for s in V.niche_by_checkpoint for x in pairs(s)})
NI = {n: i for i, n in enumerate(NICHES)}
ITEMS = sorted({x for s in V.ceiling_item_by_checkpoint for x in pairs(s)})
II = {n: i for i, n in enumerate(ITEMS)}

VAL = {}
for r in V.itertuples():
    VAL[int(r.internal_index)] = [
        r.tier, i4(r.value_mean), i4(r.value_floor_mean), i4(r.vorp_mean), i4(r.roi_mean),
        i4(r.investment_cost), NI[r.primary_niche], i4(r.primary_niche_fit),
        i4(r.niche_stat_S), i4(r.niche_tool_T), i4(r.niche_type_Y),
        NI[r.niche_2], i4(r.niche_2_fit), NI[r.niche_3], i4(r.niche_3_fit),
        int(r.earliest_checkpoint),
        [i4(x) for x in pairs(r.value_by_checkpoint)],
        [i4(x) for x in pairs(r.floor_by_checkpoint)],
        [i4(x) for x in pairs(r.vorp_by_checkpoint)],
        [NI[x] for x in pairs(r.niche_by_checkpoint)],
        [II[x] for x in pairs(r.ceiling_item_by_checkpoint)],
        r.ceiling_nature, r.ceiling_ability, r.floor_ability, r.ceiling_evs,
        i4(r.lineage_value), i4(r.lineage_dead_weight),
        i4(r.sustain_ceiling), i4(r.sustain_kit), int(float(r.sweep_depth)),
        1 if r.has_recovery == 'True' else 0, 1 if r.has_screens == 'True' else 0,
        int(float(r.n_hazards)), i4(r.heal_per_turn), i4(r.hazard_chip),
        [i4(x) for x in pairs(r.sustain_by_checkpoint)],
        [i4(x) for x in pairs(r.sustain_kit_by_checkpoint)],
        [1 if x == 'ceilingD' else 0 for x in pairs(r.spread_by_checkpoint)],
        r.modal_niche,
        1 if r.cant_miss == 'True' else 0, 1 if r.tier_fragile == 'True' else 0,
        i4(r.tier_edge_distance), r.confidence, r.availability_basis,
        i4(r.replacement_by_checkpoint and str(sum(float(x) for x in pairs(r.replacement_by_checkpoint) if x not in NA) /
                                              max(1, len([x for x in pairs(r.replacement_by_checkpoint) if x not in NA])))),
        int(r.n_niches_passed),
    ]

SP = []
for r in S.itertuples():
    ii = int(r.internal_index)
    into = []
    if r.evolves_into not in NA:
        for rec in r.evolves_into.split(';'):
            p = rec.split(':')
            if len(p) == 3:
                into.append([p[0], int(p[1]), p[2]])
    lvl = [[int(a), int(b)] for a, b in (p.split(':') for p in r.levelup_moves.split(','))] if r.levelup_moves not in NA else []
    av = [x.split(':')[:4] for x in r.availability.split('|')] if r.availability not in NA else []
    SP.append([ii, name_by_idx.get(ii, r.species_name), nz(r.form_name), r.form_type,
               int(r.evo_stage) if r.evo_stage.isdigit() else 1,
               int(r.dex_number) if r.dex_number.isdigit() else 0, r.type1, nz(r.type2),
               [int(r.hp), int(r.atk), int(r.defense), int(r.spa), int(r.spd), int(r.spe)],
               [nz(r.ability1), nz(r.ability2), nz(r.ability_hidden)],
               lvl, ilist(r.tm_moves), int(r.evolves_from) if r.evolves_from.isdigit() else 0, into, av,
               (1 if r.is_starter == 'True' else 0) | (2 if r.one_time_only == 'True' else 0) | (4 if r.missable == 'True' else 0)])

CPS = [[int(r.checkpoint), r.checkpoint_label.split('_', 1)[1].replace('-', ' '), int(r.level_cap),
        [] if r.anchor_trainers == 'NONE' else r.anchor_trainers.split(';'), int(r.pool_size)] for r in CP.itertuples()]
SL['tid'] = SL.sheet + ':' + SL.trainer + ':' + SL.header_row
TRS = [[r.trainer_id, r.trainer_name, r.role, r.level_mode, nz(r.level_min), nz(r.level_max),
        [[s.species, nz(s.level), nz(s.held_item), nz(s.ability), [m for m in s.moves.split(';') if m and m not in NA], 1 if s.is_mega == 'True' else 0]
         for s in SL[SL.tid == r.trainer_id].itertuples()]] for r in TR.itertuples()]
TMGATE = {}
for r in W.itertuples():
    if r.entity_type in ('TM', 'HM') and r.internal_id.isdigit():
        m = re.match(r'^(\d+)', r.earliest_gate)
        g = int(m.group(1)) if m else (19 if r.earliest_gate == 'postgame' else 99)
        TMGATE[int(r.internal_id)] = min(g, TMGATE.get(int(r.internal_id), 99))
EVOITEM = {r.internal_id: r.entity_name for r in W.itertuples() if r.entity_type not in ('TM', 'HM') and r.internal_id.isdigit()}

PICKS = json.load(open('/home/claude/app/picks.json'))
D = dict(pk=PICKS, sp=SP, val={str(k): v for k, v in VAL.items()}, mv={str(k): v for k, v in MOVES.items()},
         ty=TYPES, ch=CHART, cp=CPS, tr=TRS, tm=TMGATE, ei=EVOITEM, ni=NICHES, it=ITEMS,
         th=[['S+', 27.40], ['S', 20.85], ['A', 15.38], ['B', 9.91], ['C', 5.55],
             ['D', -1.02], ['F', -99900]])
raw = json.dumps(D, separators=(',', ':'), ensure_ascii=False).encode()
gz = gzip.compress(raw, 9)
b64 = base64.b64encode(gz).decode()
open('/home/claude/app/data2.b64', 'w').write(b64)
print(f'json {len(raw)/1e6:.2f} MB -> gzip {len(gz)/1e3:.0f} KB -> base64 {len(b64)/1e3:.0f} KB')
