"""Derive earliest_checkpoint for the 711 species Phase 1 left UNK.

Phase 1 filled earliest_checkpoint only for species with a DIRECT encounter or
gift record (823 of 826). Species reachable only by evolving something, or by
form-changing, were left UNK -- the README lists this as stale work. Phase 4
cannot define an obtainable pool without it, so it is derived here.

CORRECTION made while writing this (first pass shipped wrong item names):
layer['items'] is an ALPHABETICALLY SORTED list of names, not an id-indexed
array, so `items[param]` returned nonsense -- EVO_ITEM 211 resolved to
'Fire Gem' instead of 'Fire Stone'. The authoritative id source is
02_world.internal_id, the real ITEM_ enum value (211 Fire Stone, 212 Water
Stone, 213 Thunderstone, 214 Leaf Stone, 215 Ice Stone, 216 Sun Stone,
217 Moon Stone, 218 Shiny Stone, 219 Dusk Stone -- each confirmed against the
evolution it drives). Same polymorphic-parameter trap the Phase 1/2 README
already records once.

Rules, each labelled with its confidence:

  direct           -> Phase 1's own value.                         Measured
  EVO_LEVEL*       -> first checkpoint whose cap >= the evolution
                      level, never before the pre-evolution.        Inferred
  EVO_ITEM         -> max(pre-evo cp, item gate by internal_id).    Inferred
  EVO_FRIENDSHIP*  -> pre-evolution cp + 1. Friendship costs play
                      time; same-checkpoint would be wrong, but the
                      true cost is not measurable here.             Inferred
  EVO_MOVE / other -> the pre-evolution's checkpoint.               Inferred
  undecoded method -> the pre-evolution's checkpoint, flagged.      Unresolved
  mega form        -> max(base form cp, mega stone gate).           Inferred
  gigantamax       -> no G-Max mechanic or item in any source.      Unresolved
  no route at all  -> stays UNK; excluded from every pool.          Unresolved
"""
import pandas as pd, re
from collections import defaultdict

S = pd.read_csv('/home/claude/p4/01_species.tsv', sep='\t', dtype=str)
W = pd.read_csv('/home/claude/p4/02_world.tsv', sep='\t', dtype=str)
CP = pd.read_csv('/home/claude/p4/checkpoints.tsv', sep='\t')

CAP = dict(zip(CP.checkpoint, CP.level_cap))
LABEL = dict(zip(CP.checkpoint, CP.checkpoint_label))
LBL2NUM = {v: k for k, v in LABEL.items()}
NCP = len(CP)


def gate_num(g):
    if g in LBL2NUM:
        return LBL2NUM[g]
    if g == 'postgame':
        return NCP
    return None


# ---- item id -> earliest gate, from 02_world.internal_id (authoritative) ----
#
# 02_world.internal_id is POLYMORPHIC BY entity_type. For a TM or HM row it
# holds the MOVE id, not an item id -- 'TM001 Focus Punch' carries 264, which
# is Focus Punch's move id. Those collide head-on with the item enum: id 211
# is Fire Stone as an item and Steel Wing as a TM's move, and 214 is Leaf
# Stone against Sleep Talk. Including TM rows made EVO_ITEM 211 resolve to
# 'TM047 Steel Wing', which would have gated every Fire Stone evolution on the
# wrong checkpoint. TM/HM rows are therefore excluded from this map.
#
TM_TYPES = {'TM', 'HM'}
gate_by_item_id, name_by_item_id = {}, {}
tm_collisions = []
for _, r in W.iterrows():
    try:
        iid = int(r.internal_id)
    except (ValueError, TypeError):
        continue
    if r.entity_type in TM_TYPES:
        tm_collisions.append(iid)
        continue
    n = gate_num(r.earliest_gate)
    if n is None:
        continue
    if iid not in gate_by_item_id or n < gate_by_item_id[iid]:
        gate_by_item_id[iid] = n
        name_by_item_id[iid] = r.entity_name

_overlap = set(tm_collisions) & set(gate_by_item_id)
print(f'item ids with a derivable gate: {len(gate_by_item_id)} '
      f'(TM/HM rows excluded: {len(tm_collisions)}; '
      f'ids that collide with a real item: {len(_overlap)})')
for probe in (211, 212, 213, 214, 215, 216, 217, 218, 219):
    print(f'   spot-check id {probe}: {name_by_item_id.get(probe)} '
          f'@cp{gate_by_item_id.get(probe)}')

# ---- seed from Phase 1 direct records ---------------------------------
S['iidx'] = S.internal_index.astype(int)
by_idx = {r.iidx: r for r in S.itertuples()}

earliest, basis, conf = {}, {}, {}
for r in S.itertuples():
    if r.reachable == 'direct' and r.earliest_checkpoint in LBL2NUM:
        earliest[r.iidx] = LBL2NUM[r.earliest_checkpoint]
        basis[r.iidx] = 'phase1_direct'
        conf[r.iidx] = 'Measured'
print(f'\nseeded direct: {len(earliest)}')

# ---- evolution edges --------------------------------------------------
LEVEL_METHODS = {'EVO_LEVEL', 'EVO_LEVEL_NIGHT', 'EVO_LEVEL_DAY', 'EVO_LEVEL_FEMALE',
                 'EVO_LEVEL_MALE', 'EVO_LEVEL_ATK_GT_DEF', 'EVO_LEVEL_ATK_LT_DEF',
                 'EVO_LEVEL_ATK_EQ_DEF'}
FRIEND_METHODS = {'EVO_FRIENDSHIP', 'EVO_FRIENDSHIP_DAY', 'EVO_FRIENDSHIP_NIGHT'}

edges = []
for r in S.itertuples():
    ei = r.evolves_into
    if not isinstance(ei, str) or ei in ('NONE', 'NA', 'UNK', 'nan'):
        continue
    for rec in ei.split(';'):
        p = rec.split(':')
        if len(p) != 3:
            continue
        try:
            edges.append((r.iidx, int(p[1]), p[0], int(p[2])))
        except ValueError:
            continue
print(f'evolution edges: {len(edges)}')


def first_cp_with_cap(lv):
    for n in range(1, NCP + 1):
        if CAP[n] >= lv:
            return n
    return None


undecoded = defaultdict(int)
item_miss = defaultdict(int)
above_cap = []

for _ in range(15):
    changed = False
    for src, tgt, meth, param in edges:
        if src not in earliest or tgt not in by_idx:
            continue
        base = earliest[src]
        if meth in LEVEL_METHODS:
            need = first_cp_with_cap(param)
            if need is None:
                above_cap.append((by_idx[tgt].species_name, param)); continue
            cand, b, c = max(base, need), f'evo_level:{param}', 'Inferred'
        elif meth == 'EVO_ITEM':
            g = gate_by_item_id.get(param)
            if g is None:
                item_miss[param] += 1; continue
            cand, b, c = max(base, g), f'evo_item:{name_by_item_id[param]}', 'Inferred'
        elif meth in FRIEND_METHODS:
            cand, b, c = min(base + 1, NCP), 'evo_friendship', 'Inferred'
        elif meth.startswith('EVO_'):
            cand, b, c = base, f'evo_other:{meth}', 'Inferred'
        else:
            undecoded[meth] += 1
            cand, b, c = base, f'evo_undecoded:{meth}', 'Unresolved'
        if tgt not in earliest or cand < earliest[tgt]:
            earliest[tgt], basis[tgt], conf[tgt] = cand, b, c
            changed = True
    if not changed:
        break
print(f'after evolution propagation: {len(earliest)}')

# ---- mega / other form changes ----------------------------------------
def norm(s):
    return re.sub(r'[^a-z0-9]+', '', str(s).lower())


stone_gate = {}
for _, r in W[W.entity_type == 'mega_stone'].iterrows():
    n = gate_num(r.earliest_gate)
    if n is None:
        continue
    stone_gate[norm(r.entity_name)] = (n, r.entity_name)

# Mega forms carry their OWN lineage_id (906, 907...), distinct from the base
# form's, so the lineage key cannot find the base row -- match on species_name.
base_by_name = {}
for r in S.itertuples():
    if r.form_type == 'base':
        base_by_name.setdefault(r.species_name, r.iidx)


def find_stone(species_name, form_name):
    sn = norm(species_name)
    best = None
    for sk, (g, orig) in stone_gate.items():
        stem = sk[:-3] if sk.endswith('ite') else sk
        if len(stem) < 4:
            continue
        probe = stem[:max(4, len(stem) - 2)]
        if not sn.startswith(probe):
            continue
        if isinstance(form_name, str) and form_name.startswith('Mega-'):
            suffix = form_name.split('-')[-1].lower()
            if suffix in ('x', 'y') and suffix != sk[-1:]:
                continue
        if best is None or len(stem) > len(best[2]):
            best = (g, orig, stem)
    return best


gmax_unres, mega_no_stone, other_form = [], [], []
for r in S.itertuples():
    if r.iidx in earliest or r.reachable != 'via_form_change':
        continue
    b = base_by_name.get(r.species_name)
    base_cp = earliest.get(b) if b is not None else None
    if r.form_type == 'gigantamax':
        gmax_unres.append(r.species_name); continue      # stays UNK
    if base_cp is None:
        continue
    if r.form_type == 'mega':
        hit = find_stone(r.species_name, r.form_name)
        if hit:
            earliest[r.iidx] = max(base_cp, hit[0])
            basis[r.iidx] = f'form_change:{hit[1]}'
            conf[r.iidx] = 'Inferred'
        else:
            mega_no_stone.append(r.species_name)
    else:
        other_form.append(r.species_name)
        earliest[r.iidx] = base_cp
        basis[r.iidx] = 'form_change:mechanism_unknown'
        conf[r.iidx] = 'Unresolved'
print(f'after form-change propagation: {len(earliest)}')

# ---- emit -------------------------------------------------------------
S['avail_cp'] = S.iidx.map(earliest).astype('Int64')
S['avail_basis'] = S.iidx.map(basis).fillna('no_route')
S['avail_conf'] = S.iidx.map(conf).fillna('Unresolved')

print('\n--- availability confidence ---')
print(S.avail_conf.value_counts().to_string())
print(f'\nstill UNK: {S.avail_cp.isna().sum()}   '
      f'(Phase 1 reachable=none: {((S.avail_cp.isna()) & (S.reachable == "none")).sum()})')
print('remaining UNK by reachable:')
print(S[S.avail_cp.isna()].reachable.value_counts().to_string())

print('\n--- cumulative obtainable pool ---')
for n in range(1, NCP + 1):
    print(f'  cp{n:02d} cap={CAP[n]:2d}  pool={(S.avail_cp <= n).sum()}')

print('\n--- integrity notes ---')
print(f'undecoded evolution methods: {dict(undecoded)}')
print(f'EVO_ITEM ids with no gate: {len(item_miss)} -> {sorted(item_miss)[:15]}')
print(f'evolution level above cap 85: n={len(above_cap)}')
print(f'gigantamax left UNK (no G-Max item/mechanic in any source): {len(gmax_unres)}')
print(f'mega forms with no matching stone: {len(mega_no_stone)} -> {mega_no_stone[:10]}')
print(f'"other" forms, mechanism unknown, dated to base form: {len(other_form)}')

S.to_csv('/home/claude/p4/species_avail.tsv', sep='\t', index=False)
print('\nwrote species_avail.tsv')
