"""Phase 4 valuation: composite value, VORP, floor/ceiling/ROI, lineage credit,
tiers and the cant_miss flag.

COMPOSITE VALUE.  The five scoring axes are combined with fixed, stated
weights. They are not tuned to produce a pleasing ranking:

    value = 0.30*offense + 0.25*defense + 0.15*speed + 0.10*utility
          + 0.10*typing  + 0.10*primary_niche_fit

Offense and defense carry the most because they are the axes computed from
actual damage rolls; utility and typing are cheaper measures and are weighted
accordingly. The niche term is included so that a species which is a genuinely
good fit for SOME role is not flattened by a generalist average.

REPLACEMENT LEVEL (VORP). Per the project spec: for a (checkpoint, role) cell,
replacement is the THIRD-BEST obtainable species for that role at that
checkpoint under ZERO INVESTMENT -- i.e. the floor build. VORP is the species'
value minus that number. Where a role has fewer than three qualifying species
at a checkpoint, replacement falls back to the worst qualifier and the cell is
flagged, because 'third best of two' is not defined.

INVESTMENT COST. RUN_CONFIG drops EV-training time and breeding from the cost
model (the eight unconfirmable fields), so this is built only from what
remains. Each component is a stated, auditable charge:

    +1.0  nature differs from neutral            (mint or breeding needed)
    +1.0  held item required by the ceiling
    +1.0  ability differs from the common one    (capsule/patch needed)
    +1.0  the species itself needs an evolution ITEM to exist
    +0.5  per gated TM the ceiling actually uses, capped at 2.0
    +2.0  the ceiling uses an EGG move -- RUN_CONFIG says breeding is NOT
          used in this run, so an egg-move ceiling is out of reach and is
          charged as such rather than being handed over free
    floor of 0.5 so ROI never divides by zero

ROI = (ceiling_value - floor_value) / investment_cost.
"""
import pandas as pd, numpy as np, json

P = '/home/claude/p4/'
d = pd.read_pickle(P + 'archetypes.pkl')
IN = json.load(open(P + 'scoring_input.json'))
SPEC = pd.read_csv(P + 'species_avail.tsv', sep='\t', dtype=str)
CP = pd.read_csv(P + 'checkpoints.tsv', sep='\t')
SPINFO = IN['species']

# ---------------------------------------------------------------------------
# COMPOSITE v2. The five original axes are all SINGLE-HIT: they cannot see a
# species outlast anything, heal, or profit from hazards it set. A sixth axis,
# SUSTAIN, adds the turn dimension, and speed is re-weighted by role because a
# wall was paying 0.15 on a stat it does not want.
#
#   offense .26  defense .15  sustain .16  speed .12  utility .10  typing .11
#   defensive roles: sustain .24, speed .04, others as above
#
# SUSTAIN IS THE KIT DELTA, NOT RAW SUSTAIN. Raw sweep depth correlated 0.809
# with BST -- both turns-to-KO and damage-taken scale with stats, so it measured
# size, not kit. The axis used is the difference between the species with its
# sustain kit and the identical species with no recovery, screens or hazards.
# That correlates 0.463 with BST and 0.115 with offense, and is exactly zero for
# the 27% of rows with no sustain kit at all.
W = dict(offense=0.26, defense=0.15, sustain=0.16, speed=0.12, utility=0.10,
         typing=0.11, niche=0.10)
W_DEF = dict(offense=0.26, defense=0.15, sustain=0.24, speed=0.04, utility=0.10,
             typing=0.11, niche=0.10)
for _w in (W, W_DEF):
    assert abs(sum(_w.values()) - 1) < 1e-9
DEF_ROLES = {'physical_wall', 'special_wall', 'mixed_wall', 'bulky_pivot', 'tank',
             'cleric', 'hazard_setter', 'hazard_remover', 'status_spreader',
             'screen_setter', 'trapper'}
KMIN, KMAX = 0.0, 0.60          # observed range of the kit delta, rescaled to 0-1

for c in ('offense', 'defense', 'sustain', 'sustain_kit', 'sustain_bare',
          'speed_neutral', 'utility', 'typing'):
    d[c] = d[c].fillna(0)
_kit = ((d.sustain_kit - KMIN) / (KMAX - KMIN)).clip(0, 1)
# The weight set is decided PER SPECIES by the role it holds at the most
# checkpoints, not per checkpoint. Switching weights mid-run made the species
# mean a blend of two formulas, which no single spreadsheet cell can reproduce
# -- the workbook disagreed with Python on the 350 species whose role changes.
# A species is one thing; it gets one weight set, chosen by what it mostly is.
_modal = (d[d.build == 'ceiling'].groupby('species').primary_niche
          .agg(lambda x: x.mode().iat[0] if len(x.mode()) else 'NONE'))
d['modal_niche'] = d.species.map(_modal).fillna('NONE')
_isdef = d.modal_niche.isin(DEF_ROLES)


def _comp(w):
    return (w['offense'] * d.offense + w['defense'] * d.defense + w['sustain'] * _kit
            + w['speed'] * d.speed_neutral + w['utility'] * d.utility
            + w['typing'] * d.typing + w['niche'] * d.primary_niche_fit)


d['value'] = np.where(_isdef, _comp(W_DEF), _comp(W)).round(4)
d['kit_scaled'] = _kit.round(4)

# ---- floor / ceiling side by side -------------------------------------
fl = d[d.build == 'floor'].set_index(['species', 'checkpoint'])
# The ceiling is now the BETTER of two spreads: the offensive one (252 in the
# higher attacking stat plus speed) and a defensive one (252 HP plus the better
# defence, bulk nature, Leftovers). Scoring a wall only as an attacker measured
# a build nobody fields. Taking the max means a defensive spread can help a
# species and never cost it.
_ce = d[d.build.isin(['ceiling', 'ceilingD'])]
ce = _ce.loc[_ce.groupby(['species', 'checkpoint']).value.idxmax()].set_index(
    ['species', 'checkpoint'])
print('ceiling spread chosen:',
      _ce.loc[_ce.groupby(['species', 'checkpoint']).value.idxmax()].build
      .value_counts().to_dict())
V = pd.DataFrame({
    'floor_value': fl.value, 'ceiling_value': ce.value,
    'floor_niche': fl.primary_niche, 'ceiling_niche': ce.primary_niche,
    'primary_niche_fit': ce.primary_niche_fit,
    'niche_S': ce.primary_S, 'niche_T': ce.primary_T, 'niche_Y': ce.primary_Y,
    'niche_2': ce.niche_2, 'niche_2_fit': ce.niche_2_fit,
    'niche_3': ce.niche_3, 'niche_3_fit': ce.niche_3_fit,
    'is_hybrid': ce.is_hybrid, 'n_niches_passed': ce.n_niches_passed,
    'ceiling_spread': ce.build, 'modal_niche': ce.modal_niche,
    'sustain_floor': fl.sustain, 'sustain_ceiling': ce.sustain,
    'kit_scaled_ceiling': ce.kit_scaled,
    'sustain_kit_floor': fl.sustain_kit, 'sustain_kit_ceiling': ce.sustain_kit,
    'sweep_depth_ceiling': ce.sweep_depth, 'duel_win_frac': ce.duel_win_frac,
    'heal_per_turn': ce.heal_per_turn, 'hazard_chip': ce.hazard_chip,
    'has_recovery': ce.has_recovery, 'has_screens': ce.has_screens,
    'n_hazards': ce.n_hazards,
    'offense_floor': fl.offense, 'defense_floor': fl.defense,
    'offense_ceiling': ce.offense, 'defense_ceiling': ce.defense,
    # speed and utility DIFFER between builds -- the ceiling carries 252 Spe
    # and a speed-positive nature -- so both are carried explicitly. Taking
    # speed from the floor row while computing a ceiling composite understated
    # every ceiling value by ~0.03-0.05 and moved tiers.
    'speed_neutral': fl.speed_neutral, 'speed_plus': fl.speed_plus,
    'speed_neutral_ceiling': ce.speed_neutral, 'speed_plus_ceiling': ce.speed_plus,
    'utility_floor': fl.utility, 'utility_ceiling': ce.utility,
    'typing': fl.typing, 'mean_incoming_eff': fl.mean_incoming_eff,
    'ohko_frac_ceiling': ce.ohko_frac, 'twohko_frac_ceiling': ce.twohko_frac,
    'survive1_frac': fl.survive1_frac, 'survive2_frac': fl.survive2_frac,
    'bst': fl.bst, 'level': fl.level,
    'ceiling_nature': ce.nature, 'ceiling_ability': ce.ability, 'ceiling_item': ce.item,
    'floor_ability': fl.ability,
    'n_tm_gated': ce.n_tm_gated, 'n_tm_total': ce.n_tm_total, 'n_egg': ce.n_egg,
}).reset_index()

# ---- investment cost ---------------------------------------------------
sp_meta = SPEC.set_index(SPEC.species_name)  # for avail_basis; index by layer name below
basis_by_name = {}
for k, v in SPINFO.items():
    basis_by_name[k] = v['avail_basis']
V['avail_basis'] = V.species.map(basis_by_name).fillna('UNK')

cost = np.zeros(len(V))
cost += (V.ceiling_nature != 'Serious').astype(float) * 1.0
cost += (V.ceiling_item != 'NONE').astype(float) * 1.0
cost += (V.ceiling_ability != V.floor_ability).astype(float) * 1.0
cost += V.avail_basis.str.startswith('evo_item').astype(float) * 1.0
cost += np.minimum(V.n_tm_gated.fillna(0) * 0.5, 2.0)
cost += (V.n_egg.fillna(0) > 0).astype(float) * 2.0
V['investment_cost'] = np.maximum(cost, 0.5).round(2)
V['roi'] = ((V.ceiling_value - V.floor_value) / V.investment_cost).round(4)

# ---- replacement level & VORP -----------------------------------------
repl, repl_flag = {}, {}
for (cp, role), g in V.groupby(['checkpoint', 'ceiling_niche']):
    if role == 'NONE':
        continue
    vals = g.floor_value.sort_values(ascending=False).tolist()
    if len(vals) >= 3:
        repl[(cp, role)] = vals[2]; repl_flag[(cp, role)] = 'third_best'
    elif vals:
        repl[(cp, role)] = vals[-1]
        repl_flag[(cp, role)] = f'fallback_worst_of_{len(vals)}'

# A species that fails every gate still has an opportunity cost: the player
# could have used the slot on something else. Rather than leaving its VORP
# null -- which silently changes the denominator of every downstream mean --
# it is measured against the POOL-WIDE replacement (third-best floor value at
# that checkpoint, any role). Flagged as 'pool_wide_no_role' so it is visible.
pool_repl = {}
for cp, g in V.groupby('checkpoint'):
    vals = g.floor_value.sort_values(ascending=False).tolist()
    pool_repl[cp] = vals[2] if len(vals) >= 3 else (vals[-1] if vals else np.nan)

V['replacement_level'] = [repl.get((c, r), pool_repl.get(c, np.nan))
                          for c, r in zip(V.checkpoint, V.ceiling_niche)]
V['replacement_basis'] = [repl_flag.get((c, r), 'pool_wide_no_role') for c, r in
                          zip(V.checkpoint, V.ceiling_niche)]
V['vorp_floor'] = (V.floor_value - V.replacement_level).round(4)
V['vorp_ceiling'] = (V.ceiling_value - V.replacement_level).round(4)

thin = sum(1 for k, v in repl_flag.items() if v != 'third_best')
print(f'replacement cells: {len(repl)} ({thin} fell back -- fewer than 3 qualifiers)')

# ---- lineage credit ----------------------------------------------------
# A species' value includes what it becomes: Mudkip is not scored as Mudkip.
# For each checkpoint, the lineage is credited with the value of the form it is
# REALISTICALLY IN at that point -- the most-evolved member whose own
# availability checkpoint has already been reached. Checkpoints where the line
# is stuck in a form scoring below the lineage's own median carry an explicit
# DEAD-WEIGHT PENALTY, stored separately so the adjustment is auditable.
name_to_lineage, name_to_stage = {}, {}
for r in SPEC.itertuples():
    k = None
    for kk, vv in SPINFO.items():
        if vv['iidx'] == int(r.iidx):
            k = kk; break
    if k:
        name_to_lineage[k] = r.lineage_id
        try:
            name_to_stage[k] = int(r.evo_stage)
        except (ValueError, TypeError):
            name_to_stage[k] = 1
V['lineage'] = V.species.map(name_to_lineage)
V['evo_stage'] = V.species.map(name_to_stage).fillna(1).astype(int)
avail_cp = {k: v['avail_cp'] for k, v in SPINFO.items()}
V['avail_cp'] = V.species.map(avail_cp)

lin_rows = []
for (lin, cp), g in V.groupby(['lineage', 'checkpoint']):
    reached = g[g.avail_cp <= cp]
    if reached.empty:
        continue
    best = reached.sort_values(['evo_stage', 'ceiling_value'],
                               ascending=[False, False]).iloc[0]
    lin_rows.append(dict(lineage=lin, checkpoint=cp, form_used=best.species,
                         form_stage=best.evo_stage,
                         raw=best.ceiling_value, floor=best.floor_value,
                         vorp=best.vorp_ceiling))
LIN = pd.DataFrame(lin_rows)
med = LIN.groupby('lineage').raw.median().rename('lin_median')
LIN = LIN.join(med, on='lineage')
# dead weight: checkpoints where the line is stuck below its own median form
LIN['dead_weight_penalty'] = np.where(LIN.raw < LIN.lin_median,
                                      (LIN.lin_median - LIN.raw).round(4), 0.0)
LIN['adjusted'] = (LIN.raw - LIN.dead_weight_penalty).round(4)
lin_agg = LIN.groupby('lineage').agg(
    lineage_value=('adjusted', 'mean'),
    lineage_raw=('raw', 'mean'),
    lineage_dead_weight=('dead_weight_penalty', 'mean'),
    lineage_n_checkpoints=('checkpoint', 'nunique')).round(4)
V = V.merge(lin_agg, left_on='lineage', right_index=True, how='left')
# Species names can contain a colon -- 'Type: Null' does -- which breaks a
# colon-separated key:value encoding. Phase 5 caught '3:Type: Null' decoding to
# key 3, value 'Type', plus a stray ' Null'. Values are escaped; keys are always
# integers so they never need it.
def _esc(v):
    return str(v).replace(chr(92), chr(92) * 2).replace(':', chr(92) + ':')


V['lineage_form_per_cp'] = V.lineage.map(
    LIN.groupby('lineage').apply(
        lambda g: ','.join(f'{int(r.checkpoint)}:{_esc(r.form_used)}' for r in g.itertuples()),
        include_groups=False).to_dict())

# ---- global (aggregated from checkpoints, never a shortcut around them) --
glob_raw = V.groupby('species').agg(
    value_mean=('ceiling_value', 'mean'), value_floor_mean=('floor_value', 'mean'),
    vorp_mean=('vorp_ceiling', 'mean'), vorp_floor_mean=('vorp_floor', 'mean'),
    roi_mean=('roi', 'mean'), n_checkpoints=('checkpoint', 'nunique'),
    first_cp=('checkpoint', 'min'))
# Tier from the UNROUNDED mean. Rounding to 4dp first promoted Crobat across
# the A/B line: its true mean VORP is 0.089995, which rounds to 0.0900 and so
# read as >= the 0.09 threshold. The workbook computes from unrounded axis
# means and disagreed on exactly that one row -- the disagreement was right.
glob = glob_raw.round(4)

# ---- tiers -------------------------------------------------------------
# Thresholds on mean VORP at ceiling, stated numerically and NOT curve-forced.
# RECALIBRATED for the v2 composite. Adding a sixth positive axis shifted the
# VORP distribution up (median -0.010 -> +0.045) and widened it (sd ratio 1.09),
# so the published thresholds would have read 878 of 1,311 species into a
# different tier on scale drift alone. The cutoffs are the ORIGINAL ones mapped
# affinely onto the new scale, so a tier keeps its old meaning relative to the
# field. The band populations are NOT forced to match: they land where they
# land, and they do not match exactly (S+ 2 -> 10, C 221 -> 282).
TH = [('S+', 0.2740), ('S', 0.2085), ('A', 0.1538), ('B', 0.0991),
      ('C', 0.0555), ('D', -0.0102), ('F', -9e9)]


def tier_of(v):
    if pd.isna(v):
        return 'UNK'
    for t, lo in TH:
        if v >= lo:
            return t
    return 'F'


glob['tier'] = glob_raw.vorp_mean.map(tier_of)

# Tier fragility. Python averages per-checkpoint VORPs (each rounded to 4dp);
# the workbook computes composite-of-means minus mean-replacement. Both are
# defensible and they agree to ~1e-4 -- which is still enough to flip a species
# sitting exactly on a threshold. Rather than force the two to agree, flag the
# species whose tier is not robust, so nobody reads a boundary case as settled.
def dist_to_edge(v):
    if pd.isna(v):
        return np.nan
    edges = [lo for _, lo in TH if lo > -1e8]
    return min(abs(v - e) for e in edges)


glob['tier_edge_distance'] = glob_raw.vorp_mean.map(dist_to_edge).round(5)
glob['tier_fragile'] = glob.tier_edge_distance < 0.002
print(f"\ntier-fragile species (within 0.002 of a threshold): "
      f"{int(glob.tier_fragile.sum())}")
print(glob[glob.tier_fragile][['vorp_mean', 'tier', 'tier_edge_distance']]
      .sort_values('tier_edge_distance').to_string())
V = V.merge(glob[['value_mean', 'vorp_mean', 'roi_mean', 'tier', 'n_checkpoints',
                  'tier_edge_distance', 'tier_fragile']],
            left_on='species', right_index=True, how='left', suffixes=('', '_glob'))

# ---- cant_miss ---------------------------------------------------------
# Rule, written down rather than vibed: tier A or better AND (one_time_only OR
# missable) in Phase 1. Both halves are required -- a missable dud is not a
# priority, and a great species you can always get later is not either.
onetime = {k: v['one_time'] for k, v in SPINFO.items()}
missable = {k: v['missable'] for k, v in SPINFO.items()}
V['one_time_only'] = V.species.map(onetime).fillna(False)
V['missable'] = V.species.map(missable).fillna(False)
V['cant_miss'] = (V.tier.isin(['S+', 'S', 'A'])
                  & (V.one_time_only | V.missable))

V['confidence'] = np.where(
    V.avail_basis == 'phase1_direct', 'Inferred', 'Inferred')
V.loc[V.avail_basis.str.contains('undecoded|mechanism_unknown|stone_not_located',
                                 na=False), 'confidence'] = 'Unresolved'
# cp09 was Unresolved while its cap was interpolated and its roster substituted
# on a guess. Boss_Battles!Main confirms cap 56 AND names the checkpoint
# 'Pre-Trick House', which makes the Trick House sheet the right threat pool
# rather than a stand-in. No longer Unresolved.

V.to_pickle(P + 'valuation.pkl')
LIN.to_pickle(P + 'lineage.pkl')

print(f'\nvaluation rows: {len(V)}  species: {V.species.nunique()}  '
      f'lineages: {V.lineage.nunique()}')
print('\n--- tier distribution (per species, not per row) ---')
print(glob.tier.value_counts().reindex([t for t, _ in TH]).to_string())
print(f'\ncant_miss species: {V[V.cant_miss].species.nunique()}')
print('\n--- top 15 by mean VORP (ceiling) ---')
top = glob.sort_values('vorp_mean', ascending=False).head(15)
print(top[['value_mean', 'vorp_mean', 'roi_mean', 'tier', 'n_checkpoints']].to_string())
print('\n--- top 12 by ROI (specialists: modest floor, high ceiling) ---')
roi = glob[glob.n_checkpoints >= 5].sort_values('roi_mean', ascending=False).head(12)
print(roi[['value_floor_mean', 'value_mean', 'roi_mean', 'tier']].to_string())
print('\nwrote valuation.pkl + lineage.pkl')
