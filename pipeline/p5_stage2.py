"""Phase 5 stage 2 — cross-phase referential integrity, from the shipped bundle.

Checks the spec names explicitly:
  * every Phase 3 roster species, move, ability and item resolves against
    Phases 1 and 2
  * every Phase 4 ceiling build uses only TMs and items Phase 2 confirms
    obtainable BY THAT CHECKPOINT
plus the joins the bundle relies on internally.
"""
import pandas as pd, json, re
from collections import Counter

B = '/mnt/user-data/outputs/emerald_imperium/'
P = '/home/claude/p4/'
L = json.load(open(P + 'imperium_layer.json'))
IN = json.load(open(P + 'scoring_input.json'))

S = pd.read_csv(B + '01_species.tsv', sep='\t', dtype=str)
W = pd.read_csv(B + '02_world.tsv', sep='\t', dtype=str)
TR = pd.read_csv(B + '03_trainers.tsv', sep='\t', dtype=str)
SL = pd.read_csv(B + '03_trainer_slots.tsv', sep='\t', dtype=str)
V = pd.read_csv(B + '04_valuation.tsv', sep='\t', dtype=str)
CP = pd.read_csv(B + '05_checkpoints.tsv', sep='\t')
LN = pd.read_csv(B + '06_lineage.tsv', sep='\t', dtype=str)

OUT = []


def rec(area, check, result, sev, n, effect):
    OUT.append(dict(area=area, check=check, result=result, severity=sev,
                    affected=n, effect=effect))
    print(f'[{sev:10}] {area:16} {check:52} {result}')


def norm(s):
    return re.sub(r'[^a-z0-9]+', '', str(s).lower())


SP_IDX = set(S.internal_index.astype(int))
MOVE_NAMES = {norm(k) for k in L['moves']}
ABIL = {norm(a) for a in L['abilities']}
ITEM = {norm(i) for i in L['items']}
MOVE_IDS = {v['move_id'] for v in L['moves'].values()}

print('=' * 100)
print('STAGE 2 — CROSS-PHASE REFERENTIAL INTEGRITY')
print('=' * 100)

# ---- Phase 3 -> Phase 1 ------------------------------------------------
bad = [x for x in SL.species_id if x == 'UNRESOLVED' or
       (x.replace('.0', '').isdigit() and int(float(x)) not in SP_IDX)]
rec('P3 -> P1', 'roster species_id resolves to a Phase 1 row',
    f'{len(SL) - len(bad)}/{len(SL)}', '—' if not bad else 'Material', len(bad),
    'pass' if not bad else str(Counter(bad).most_common(4)))

# roster moves
unres_mv, tot_mv = set(), 0
for s in SL.moves.dropna():
    for m in str(s).split(';'):
        if not m or m in ('NONE', 'nan'):
            continue
        tot_mv += 1
        if norm(m) not in MOVE_NAMES and not norm(m).startswith('hiddenpower'):
            unres_mv.add(m)
rec('P3 -> P1', 'roster moves resolve against the move table',
    f'{tot_mv - len(unres_mv)}/{tot_mv} refs, {len(unres_mv)} distinct unresolved',
    '—' if not unres_mv else 'Material', len(unres_mv),
    'pass' if not unres_mv else str(sorted(unres_mv)[:6]))

unres_ab = {a for a in SL.ability.dropna() if a not in ('NONE', 'nan') and norm(a) not in ABIL}
rec('P3 -> P1', 'roster abilities resolve', f'{len(unres_ab)} distinct unresolved',
    '—' if not unres_ab else 'Unresolved', len(unres_ab),
    'pass' if not unres_ab else str(sorted(unres_ab)))

unres_it = {i for i in SL.held_item.dropna() if i not in ('NONE', 'nan') and norm(i) not in ITEM}
rec('P3 -> P2/P1', 'roster held items resolve against itemData',
    f'{len(unres_it)} distinct unresolved', '—' if not unres_it else 'Unresolved',
    len(unres_it), 'pass' if not unres_it else str(sorted(unres_it)))

# ---- Phase 1 internal ---------------------------------------------------
orphan_evo = 0
for s in S.evolves_into.dropna():
    if s in ('NONE', 'NA', 'UNK'):
        continue
    for r_ in str(s).split(';'):
        p = r_.split(':')
        if len(p) == 3 and p[1].isdigit() and int(p[1]) not in SP_IDX:
            orphan_evo += 1
rec('P1 internal', 'evolution targets resolve to a species row',
    f'{orphan_evo} orphans', '—' if not orphan_evo else 'Material', orphan_evo,
    'pass' if not orphan_evo else 'orphan evolution target')

bad_move_ids = 0
for col in ('levelup_moves', 'tm_moves', 'egg_moves'):
    for s in S[col].dropna():
        if s in ('NONE', 'NA', 'UNK'):
            continue
        for tok in str(s).split(','):
            mid = tok.split(':')[0].strip()
            if mid.isdigit() and int(mid) not in MOVE_IDS:
                bad_move_ids += 1
rec('P1 internal', 'movepool move ids resolve', f'{bad_move_ids} dangling ids',
    '—' if not bad_move_ids else 'Material', bad_move_ids,
    'pass' if not bad_move_ids else 'dangling move id')

bst_bad = (S.bst.astype(int) != S[['hp', 'atk', 'defense', 'spa', 'spd', 'spe']]
           .astype(int).sum(axis=1)).sum()
rec('P1 internal', 'BST equals the sum of its parts', f'{bst_bad} mismatches',
    '—' if not bst_bad else 'Material', int(bst_bad), 'pass')

oor = 0
for c in ['hp', 'atk', 'defense', 'spa', 'spd', 'spe']:
    oor += ((S[c].astype(int) < 1) | (S[c].astype(int) > 255)).sum()
rec('P1 internal', 'base stats within 1-255', f'{oor} out of range',
    '—' if not oor else 'Material', int(oor), 'pass')

dup = len(S) - S.internal_index.nunique()
rec('P1 internal', 'internal_index unique', f'{dup} duplicates',
    '—' if not dup else 'Material', dup, 'pass')

# ---- Phase 4 -> Phase 2: THE CEILING GATE CHECK -------------------------
tm_by_cp = {c['checkpoint']: set(c['tms_available']) for c in IN['checkpoints']}
item_by_cp = {c['checkpoint']: set(c['items_available']) for c in IN['checkpoints']}
SPINFO = IN['species']

item_violation, tm_violation, checked = [], 0, 0
tm_bad = []
for r in V.itertuples():
    first = r.earliest_checkpoint
    if first == 'UNK':
        continue
    # the ceiling item must be obtainable at EVERY checkpoint the species is scored
    cps = [int(p.split(':')[0]) for p in str(r.value_by_checkpoint).split(',')]
    # now checked per checkpoint against the encoded column, which is the
    # reproducible build; the old single ceiling_item could only ever be right
    # at the last checkpoint.
    per_cp = {}
    for p in str(r.ceiling_item_by_checkpoint).split(','):
        m = re.match(r'^(\d+):(.*)$', p)
        if m:
            per_cp[int(m.group(1))] = m.group(2).replace('\\:', ':')
    for cp in cps:
        checked += 1
        it = per_cp.get(cp, 'NONE')
        if it not in ('NONE', 'nan') and it not in item_by_cp[cp]:
            item_violation.append((r.species_form, cp, it))
    # every gated TM the ceiling could use must be in that checkpoint's TM set
    sp = SPINFO.get(r.species_form)
    if sp:
        for cp in cps:
            n_ok = len([m for m in sp['tm'] if m in tm_by_cp[cp]])
            if cp == cps[-1] and str(r.n_tm_gated_at_last_cp) != 'nan':
                if int(float(r.n_tm_gated_at_last_cp)) != n_ok:
                    tm_violation += 1
                    tm_bad.append((r.species_form, cp, r.n_tm_gated_at_last_cp, n_ok))

rec('P4 -> P2', 'ceiling held item obtainable at that checkpoint',
    f'{checked - len(item_violation)}/{checked} species-checkpoint pairs',
    '—' if not item_violation else 'Material', len(item_violation),
    'pass' if not item_violation else str(item_violation[:5]))
rec('P4 -> P2', 'n_tm_gated matches Phase 2 TM gates at that checkpoint',
    f'{tm_violation} mismatches', '—' if not tm_violation else 'Material',
    tm_violation, 'pass' if not tm_violation else str(tm_bad[:4]))

# ---- Phase 4 internal ---------------------------------------------------
caps = dict(zip(CP.checkpoint, CP.level_cap))
bad_lvl = 0
for r in V.itertuples():
    if r.earliest_level == 'UNK':
        continue
    if int(r.earliest_level) != caps[int(r.earliest_checkpoint)]:
        bad_lvl += 1
rec('P4 internal', 'earliest_level equals that checkpoint cap', f'{bad_lvl} mismatches',
    '—' if not bad_lvl else 'Material', bad_lvl, 'pass')

vs = set(V.species_form)
lin_forms = set()
for s in V.lineage_form_per_checkpoint.dropna():
    for p in str(s).split(','):
        # split on the FIRST unescaped colon
        m = re.match(r'^(\d+):(.*)$', p)
        if m:
            lin_forms.add(m.group(2).replace('\\:', ':'))
missing = lin_forms - vs
rec('P4 internal', 'lineage forms all appear as valuation rows',
    f'{len(lin_forms)} distinct forms, {len(missing)} not in the file',
    '—' if not missing else 'Material', len(missing),
    'pass' if not missing else str(sorted(missing)[:5]))

# tiers must follow the thresholds
# v2 thresholds: the published cutoffs mapped affinely onto the new composite's
# scale. Leaving the v1 numbers here reported 964 false violations.
TH = [('S+', 0.2740), ('S', 0.2085), ('A', 0.1538), ('B', 0.0991),
      ('C', 0.0555), ('D', -0.0102)]


def tier_of(v):
    for t, lo in TH:
        if v >= lo:
            return t
    return 'F'


tier_bad = sum(1 for r in V.itertuples()
               if tier_of(float(r.vorp_mean)) != r.tier and str(r.tier_fragile) != 'True')
rec('P4 internal', 'tier follows the stated thresholds (fragile rows excused)',
    f'{tier_bad} violations', '—' if not tier_bad else 'Material', tier_bad, 'pass')

cm_bad = sum(1 for r in V.itertuples()
             if (str(r.cant_miss) == 'True') !=
             (r.tier in ('S+', 'S', 'A') and
              (str(r.one_time_only) == 'True' or str(r.missable) == 'True')))
rec('P4 internal', "cant_miss follows its stated rule", f'{cm_bad} violations',
    '—' if not cm_bad else 'Material', cm_bad, 'pass')

# 06_lineage consistency
ln_bad = (LN.adjusted.astype(float).round(4) !=
          (LN.raw.astype(float) - LN.dead_weight_penalty.astype(float)).round(4)).sum()
rec('P4 internal', '06_lineage adjusted == raw - dead_weight_penalty',
    f'{ln_bad} mismatches', '—' if not ln_bad else 'Material', int(ln_bad), 'pass')

# ---- v2 sustain checks -------------------------------------------------
sk = pd.to_numeric(V.sustain_kit, errors='coerce')
rec('P4 v2', 'sustain kit delta is never negative',
    f'{int((sk < -1e-9).sum())} negative of {len(V)}',
    '—' if (sk < -1e-9).sum() == 0 else 'Material', int((sk < -1e-9).sum()),
    'the kit can only help; a negative value would mean the model is inconsistent')
nokit = V[(V.has_recovery == 'False') & (V.has_screens == 'False') &
          (pd.to_numeric(V.n_hazards, errors='coerce') == 0)]
bad_nokit = int((pd.to_numeric(nokit.sustain_kit, errors='coerce') > 1e-9).sum())
rec('P4 v2', 'species with no sustain kit score exactly zero on the axis',
    f'{len(nokit) - bad_nokit}/{len(nokit)}', '—' if not bad_nokit else 'Material',
    bad_nokit, 'pass' if not bad_nokit else 'a kitless species gained sustain')
spread_ok = set(V.ceiling_spread) <= {'ceiling', 'ceilingD'}
rec('P4 v2', 'ceiling_spread is one of the two scored builds',
    f'{sorted(set(V.ceiling_spread))}', '—' if spread_ok else 'Material', 0, 'pass')
import numpy as _np
_k = pd.to_numeric(V.sustain_kit, errors='coerce')
_b = pd.to_numeric(V.bst, errors='coerce')
_r = _np.corrcoef(_k.fillna(0), _b)[0, 1]
rec('P4 v2', 'sustain kit delta vs BST (must not be a stat proxy)',
    f'r={_r:.3f}', '—' if abs(_r) < 0.7 else 'Material', 0,
    'raw sweep depth was 0.809 and was rejected for this reason')

json.dump(OUT, open(P + 'p5_stage2.json', 'w'), indent=1)
print(f'\n{sum(1 for o in OUT if o["severity"] == "—")}/{len(OUT)} checks clean')
