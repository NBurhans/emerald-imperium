"""Assemble 04_valuation.tsv and ship the Phase 1-4 bundle."""
import sys, json, pandas as pd, numpy as np
sys.path.insert(0, '/mnt/skills/plugins/romhack-data-analysis/scripts')
from export_bundle import Bundle

P = '/home/claude/p4/'
OUT = '/mnt/user-data/outputs/emerald_imperium/'
B = OUT

V = pd.read_pickle(P + 'valuation.pkl')
LIN = pd.read_pickle(P + 'lineage.pkl')
IN = json.load(open(P + 'scoring_input.json'))
CP = pd.read_csv(P + 'checkpoints.tsv', sep='\t')
SPEC = pd.read_csv(P + 'species_avail.tsv', sep='\t', dtype=str)
SPINFO = IN['species']

NCP = 19
CAPS = dict(zip(CP.checkpoint, CP.level_cap))

# ---- per-species wide table: one row per species FORM -----------------
# A species name can itself contain a colon -- 'Type: Null' and its evolution
# 'Silvally' both do -- which breaks a colon-separated key:value encoding.
# 'Silvally-Normal' encoded as '3:Type: Null' decodes to key 3, value 'Type',
# and a stray ' Null'. Phase 5 caught this on 2 rows. The README's encoding
# table covers literal tab, newline and pipe but not colon; it now covers
# colon too, escaped as '\:' in VALUES only. Keys are always integers.
def esc(v):
    return str(v).replace(chr(92), chr(92)*2).replace(':', chr(92) + ':')


def enc_pairs(g, key, val, fmt='{}:{}'):
    return ','.join(fmt.format(int(a), esc(b) if not isinstance(b, float) else b)
                    for a, b in zip(g[key], g[val]))


rows = []
for sp, g in V.sort_values('checkpoint').groupby('species'):
    info = SPINFO[sp]
    last = g.iloc[-1]
    rows.append(dict(
        species_form=sp,
        internal_index=info['iidx'], dex_number=info['dex'],
        form_type=info['form_type'], lineage_id=info['lineage'],
        evo_stage=info['evo_stage'], bst=info['bst'],

        # availability (Phase 4 derived; Phase 1 left these UNK)
        earliest_checkpoint=int(info['avail_cp']) if info['avail_cp'] else 'UNK',
        earliest_level=CAPS.get(info['avail_cp'], 'UNK') if info['avail_cp'] else 'UNK',
        availability_basis=info['avail_basis'],
        availability_confidence=info['avail_conf'],

        # sustain (v2)
        ceiling_spread=last.ceiling_spread,
        sustain_ceiling=last.sustain_ceiling, sustain_kit=last.sustain_kit_ceiling,
        sweep_depth=last.sweep_depth_ceiling, duel_win_frac=last.duel_win_frac,
        heal_per_turn=last.heal_per_turn, hazard_chip=last.hazard_chip,
        has_recovery=last.has_recovery, has_screens=last.has_screens,
        n_hazards=last.n_hazards,
        sustain_by_checkpoint=enc_pairs(g, 'checkpoint', 'sustain_ceiling', '{}:{:.4f}'),
        sustain_kit_by_checkpoint=enc_pairs(g, 'checkpoint', 'sustain_kit_ceiling', '{}:{:.4f}'),
        spread_by_checkpoint=enc_pairs(g, 'checkpoint', 'ceiling_spread', '{}:{}'),
        # headline valuation
        value_mean=round(g.ceiling_value.mean(), 4),
        value_floor_mean=round(g.floor_value.mean(), 4),
        vorp_mean=round(g.vorp_ceiling.mean(), 4),
        vorp_floor_mean=round(g.vorp_floor.mean(), 4),
        roi_mean=round(g.roi.mean(), 4),
        investment_cost=round(g.investment_cost.mean(), 2),
        tier=last.tier,
        n_checkpoints_obtainable=g.checkpoint.nunique(),

        # niches
        primary_niche=last.ceiling_niche, modal_niche=last.modal_niche,
        primary_niche_fit=last.primary_niche_fit,
        niche_stat_S=last.niche_S, niche_tool_T=last.niche_T, niche_type_Y=last.niche_Y,
        niche_2=last.niche_2, niche_2_fit=last.niche_2_fit,
        niche_3=last.niche_3, niche_3_fit=last.niche_3_fit,
        is_hybrid=last.is_hybrid, n_niches_passed=last.n_niches_passed,

        # per-checkpoint curves, folded in (cp:value)
        value_by_checkpoint=enc_pairs(g, 'checkpoint', 'ceiling_value', '{}:{:.4f}'),
        floor_by_checkpoint=enc_pairs(g, 'checkpoint', 'floor_value', '{}:{:.4f}'),
        vorp_by_checkpoint=enc_pairs(g, 'checkpoint', 'vorp_ceiling', '{}:{:.4f}'),
        niche_by_checkpoint=enc_pairs(g, 'checkpoint', 'ceiling_niche', '{}:{}'),
        offense_by_checkpoint=enc_pairs(g, 'checkpoint', 'offense_ceiling', '{}:{:.4f}'),
        defense_by_checkpoint=enc_pairs(g, 'checkpoint', 'defense_ceiling', '{}:{:.4f}'),
        speed_by_checkpoint=enc_pairs(g, 'checkpoint', 'speed_neutral', '{}:{:.4f}'),
        typing_by_checkpoint=enc_pairs(g, 'checkpoint', 'typing', '{}:{:.4f}'),
        utility_by_checkpoint=enc_pairs(g, 'checkpoint', 'utility_ceiling', '{}:{:.4f}'),
        replacement_by_checkpoint=enc_pairs(g, 'checkpoint', 'replacement_level', '{}:{:.4f}'),

        # the ceiling build, stored so it can be reproduced and argued with
        ceiling_nature=last.ceiling_nature, ceiling_ability=last.ceiling_ability,
        # The ceiling ITEM changes as Phase 2 unlocks better ones, so a single
        # column cannot describe the build. Phase 5 measured 10,614 of 21,015
        # species-checkpoint pairs where the stored item was not yet obtainable
        # at that checkpoint -- the SCORES were correctly gated all along, but
        # the stored build described only the last checkpoint. Both are carried
        # now, and the per-checkpoint column is the reproducible one.
        ceiling_item_at_last_cp=last.ceiling_item,
        ceiling_item_by_checkpoint=enc_pairs(g, 'checkpoint', 'ceiling_item', '{}:{}'),
        floor_ability=last.floor_ability,
        ceiling_evs=('252 Atk / 252 Spe / 4 HP' if last.ceiling_nature == 'Adamant'
                     else '252 SpA / 252 Spe / 4 HP'),
        ceiling_ivs='31/31/31/31/31/31',
        n_tm_gated_at_last_cp=last.n_tm_gated, n_tm_total=last.n_tm_total,
        n_egg_moves=last.n_egg,

        # lineage
        lineage_value=last.lineage_value, lineage_raw=last.lineage_raw,
        lineage_dead_weight=last.lineage_dead_weight,
        lineage_form_per_checkpoint=last.lineage_form_per_cp,

        # flags
        one_time_only=last.one_time_only, missable=last.missable,
        cant_miss=last.cant_miss,
        confidence=last.confidence,
        tier_edge_distance=last.tier_edge_distance,
        tier_fragile=last.tier_fragile,
        reasoning=(f"{last.ceiling_niche} (fit {last.primary_niche_fit:.2f} = "
                   f"stat {last.niche_S:.2f} / tool {last.niche_T:.2f} / "
                   f"type {last.niche_Y:.2f}); obtainable cp"
                   f"{int(info['avail_cp']) if info['avail_cp'] else '?'}-19; "
                   f"VORP {g.vorp_ceiling.mean():+.3f} vs replacement "
                   f"{g.replacement_level.mean():.3f}"),
    ))
VAL = pd.DataFrame(rows).sort_values('vorp_mean', ascending=False)

# ---- checkpoint reference table ---------------------------------------
CPT = CP.copy()
CPT['n_roster_slots'] = [len(c['slots']) for c in IN['checkpoints']]
CPT['roster_basis'] = [c['roster_basis'] for c in IN['checkpoints']]
CPT['pool_size'] = [len(c['pool']) for c in IN['checkpoints']]
CPT['tms_available'] = [len(c['tms_available']) for c in IN['checkpoints']]
CPT['items_available'] = [len(c['items_available']) for c in IN['checkpoints']]
CPT['roster_species'] = [','.join(sorted({s['species'] for s in c['slots']}))
                         for c in IN['checkpoints']]

# ---- validation table --------------------------------------------------
d = pd.read_pickle(P + 'archetypes.pkl')
cor_f = np.corrcoef(d[(d.build == 'floor') & (d.primary_niche != 'NONE')].primary_niche_fit,
                    d[(d.build == 'floor') & (d.primary_niche != 'NONE')].bst)[0, 1]
cor_c = np.corrcoef(d[(d.build == 'ceiling') & (d.primary_niche != 'NONE')].primary_niche_fit,
                    d[(d.build == 'ceiling') & (d.primary_niche != 'NONE')].bst)[0, 1]
p10 = pd.read_pickle(P + 'arch_p10.pkl'); m10 = pd.read_pickle(P + 'arch_m10.pkl')
stab_p = (d.primary_niche.values == p10.primary_niche.values).mean()
stab_m = (d.primary_niche.values == m10.primary_niche.values).mean()

VALID = pd.DataFrame([
    dict(phase=4, check='Checkpoint ladder monotonic, 15->85',
         result='19 checkpoints, strictly increasing', severity='—', affected=0,
         effect='pass'),
    dict(phase=4, check='Level cap ladder',
         result='19 of 19 MEASURED from Boss_Battles.xlsx!Main', severity='—', affected=0,
         effect='supersedes the reconstruction, which was right on 18 of 19'),
    dict(phase=4, check='Reconstructed vs measured caps',
         result='18 of 19 exact; cp09 was 53, is 56', severity='Material', affected=1,
         effect='cp09 pool 1255->1257; all cp09 scores re-run'),
    dict(phase=4, check='Boss_Battles sheets vs Phase 3 parse',
         result='695 source Ability: lines vs 678 parsed slots',
         severity='—', affected=0,
         effect='the 17-row gap is exactly the 17 mega post-transformation ability '
                'lines, folded into mega_ability. Nothing missing'),
    dict(phase=4, check='RUN_CONFIG anchor counts re-measured',
         result='695/45/9/576/39 all match exactly', severity='—', affected=0,
         effect='source file identical to what Phase 3 read'),
    dict(phase=4, check='Battle_Rewards.xlsx vs 02_world',
         result='17 of 17 rows present with matching locations', severity='—', affected=0,
         effect='supersede claim was correct; reward_trainer column added'),
    dict(phase=4, check='Checkpoints with no boss roster',
         result='1 (cp09 Pre-TrickHouse)', severity='Material', affected=1,
         effect='the checkpoint IS the Trick House, so its 46 sheet slots are the '
                'correct threat pool; downgraded from Unresolved'),
    dict(phase=4, check='Damage engine vs independent hand implementation',
         result='14/14 exact match on rolls, stats and max HP', severity='—',
         affected=0, effect='discrepancy rate 0.0%'),
    dict(phase=4, check='Scoring run errors', result='0 of 42,026 rows',
         severity='—', affected=0, effect='pass'),
    dict(phase=4, check='BST correlation BEFORE rebalance (validation 1)',
         result=f'floor 0.705 / ceiling 0.745', severity='Material', affected=0,
         effect='FAILED the ~0.7 threshold; framework rebalanced'),
    dict(phase=4, check='v2 SUSTAIN axis: raw sweep depth vs BST',
         result='r=0.809 — REJECTED as a stat proxy', severity='Material', affected=0,
         effect='replaced by the kit delta (with-kit minus no-kit), r=0.463 at row '
                'level; zero for the 27% of rows with no sustain kit'),
    dict(phase=4, check='v2: mean VORP vs BST, like-for-like',
         result='v1 r=0.841 -> v2 r=0.785', severity='—', affected=0,
         effect='moved the right way'),
    dict(phase=4, check='v2: tier thresholds recalibrated',
         result='affine map of the published cutoffs onto the new scale',
         severity='Material', affected=472,
         effect='median VORP shifted -0.010 -> +0.045 and sd widened 1.09x; without '
                'recalibration 878 of 1,311 would change tier on scale drift alone. '
                'Band populations are NOT forced and do not match (S+ 2 -> 10)'),
    dict(phase=4, check='v2: defensive ceiling spread chosen',
         result='9,712 of 21,015 species-checkpoint pairs', severity='—', affected=0,
         effect='75% of screen setters, 72% of hazard removers, 66% of special walls'),
    dict(phase=4, check='BST correlation AFTER rebalance (validation 1)',
         result=f'floor {cor_f:.3f} / ceiling {cor_c:.3f}', severity='—', affected=0,
         effect=f'pass; n={int((d.primary_niche!="NONE").sum())}'),
    dict(phase=4, check='Gate bite (validation 3)',
         result='every gate eliminates 43.7%-98.4%', severity='—', affected=0,
         effect='no vacuous gate'),
    dict(phase=4, check='Low-BST representation (validation 2)',
         result='18 of 21 archetypes have a bottom-half-BST species in their top 10',
         severity='Material', affected=3,
         effect='special_wallbreaker, suicide_lead, trick_room_attacker are stat-hungry'),
    dict(phase=4, check='Intuition spot-check (validation 4)',
         result='expected role in top-3 for 9/12; exact primary for 6/12',
         severity='Material', affected=3,
         effect='Ferrothorn, Aerodactyl, Cloyster disagree; see README'),
    dict(phase=4, check='Weight sensitivity +-0.10 (validation 5)',
         result=f'primary_niche unchanged {stab_p:.1%} / {stab_m:.1%}',
         severity='—', affected=0, effect='labels stable; churn is adjacent roles'),
    dict(phase=4, check='Species with NO functional role (all gates failed)',
         result=f'{int((d.primary_niche=="NONE").sum())} rows',
         severity='—', affected=int((d.primary_niche == 'NONE').sum()),
         effect='reported, not absorbed into a generalist bucket'),
    dict(phase=4, check='Availability derived for Phase 1 UNK species',
         result='1,311 of 1,534 forms obtainable', severity='Material', affected=223,
         effect='223 remain UNK, 192 of them Phase 1 reachable=none'),
    dict(phase=4, check='Replacement cells falling back (fewer than 3 qualifiers)',
         result='see replacement_basis column', severity='Material', affected=0,
         effect='flagged per row'),
    dict(phase=4, check='Boss roster items not in Imperium itemData',
         result='7 distinct', severity='Unresolved', affected=7,
         effect='Heavy-Duty Boots, Weakness Policy, Terrain Extender, the Ogerpon '
                'masks, Flapplite, memories'),
    dict(phase=4, check='Boss roster abilities not resolving',
         result='1 (As One (Spectrier))', severity='Unresolved', affected=1,
         effect='known Phase 4 gap'),
    dict(phase=4, check='Tier distribution (not curve-forced)',
         result='S+ 10 / S 42 / A 91 / B 182 / C 281 / D 273 / F 432',
         severity='—', affected=0, effect='1,311 species with a tier'),
    dict(phase=4, check='cant_miss species', result='38', severity='—', affected=38,
         effect='tier A+ AND (one_time_only OR missable)'),
    dict(phase=4, check='Tier robustness at the thresholds',
         result='see tier_fragile column', severity='Material', affected=0,
         effect='Metagross-Mega, Crobat and Wyrdeer sit within 1.2e-4 of a tier '
                'edge; their tier flips between the two equally valid ways of '
                'averaging VORP and should not be read as settled'),
])

# ---- ship --------------------------------------------------------------
b = Bundle(OUT)
for name in ['01_species.tsv', '02_world.tsv', '03_trainers.tsv', '03_trainer_slots.tsv']:
    # 02_world (reward_trainer added) and the two trainer files (Spoink slot
    # repaired) now live in the working dir; only 01_species is unchanged
    # from the project copy.
    srcdir = B if name == '01_species.tsv' else P
    df = pd.read_csv(srcdir + name, sep='\t', dtype=str)
    b.add(name, df, {
        '01_species.tsv': 'one row per species form; movepools, evolution and availability folded in',
        '02_world.tsv': 'items, TMs/HMs, vendor stock, mega stones, trades, gifts, eggs, NPC services; held-item rows now carry reward_trainer',
        '03_trainers.tsv': 'one row per trainer; roster and derived team analysis folded in (Phase 5 repair: Team Aqua GRUNT roster_species)',
        '03_trainer_slots.tsv': 'one row per roster slot; the exploded form of 03_trainers (Phase 5 repair: Spoink slot recovered)',
    }[name])
b.add('04_valuation.tsv', VAL, 'Phase 4: VORP, floor/ceiling/ROI, niches, tiers, per-checkpoint curves')
b.add('05_checkpoints.tsv', CPT, 'the 19-checkpoint ladder: caps, anchors, pools, gates')
b.add('06_lineage.tsv', LIN, 'per-lineage per-checkpoint form used, raw score and dead-weight penalty')

VAL.to_pickle(P + 'VAL.pkl')
CPT.to_pickle(P + 'CPT.pkl')
VALID.to_pickle(P + 'VALID.pkl')
print(f'\n04_valuation rows: {len(VAL)}, cols: {len(VAL.columns)}')
