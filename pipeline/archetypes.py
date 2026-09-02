"""Archetype classification: gates first, then a 0-1 fit for survivors only.

Method is archetypes.md sec.1: every archetype has BINARY gates encoding what
the role actually requires. Fail one and fit is 0 regardless of stats -- a wall
without recovery is not a wall. Only survivors get scored, and the score is

    fit = w_stat*S + w_tool*T + w_type*Y

with S, T and Y reported separately so the reason for a score is visible.

Stats are PERCENTILE-normalised within the obtainable pool AT THAT CHECKPOINT,
not min-maxed across the dex, or the legendaries compress everyone else into
the bottom third and the framework re-derives BST with extra steps.
"""
import json, os, pandas as pd, numpy as np
from collections import defaultdict

# archetypes.md validation 5: shift the component weights by +-0.1 and see
# whether primary niches churn. SHIFT moves weight from stat to toolkit
# (positive) or toolkit to stat (negative); weights are re-normalised and
# clipped to [0,1] so they always still sum to 1.
SHIFT = float(os.environ.get('WEIGHT_SHIFT', '0'))
OUT = os.environ.get('ARCH_OUT', 'archetypes.pkl')

P = '/home/claude/p4/'
IN = json.load(open(P + 'scoring_input.json'))
MOVES, TOOLS = IN['moves'], IN['tools']
ENABLERS = TOOLS['enabler_abilities']
SPECIES = IN['species']

rows = json.load(open(P + 'scores_raw.json'))
print(f'loaded {len(rows)} scored rows')

# =====================================================================
# Archetype definitions.  gates(ctx) -> True if the species QUALIFIES.
# weights are (stat, toolkit, typing) and must sum to 1.
# =====================================================================
def bp(ctx, cat, n, minbp):
    """>= n damaging moves of category `cat` with BP >= minbp."""
    return sum(1 for m in ctx['pool']
               if MOVES.get(m) and MOVES[m]['category'] == cat
               and MOVES[m]['basePower'] >= minbp) >= n


def atk_types(ctx, cat, n):
    ts = {MOVES[m]['type'] for m in ctx['pool']
          if MOVES.get(m) and MOVES[m]['category'] == cat and MOVES[m]['basePower'] > 0}
    return len(ts) >= n


def has(ctx, cat):
    return ctx['tools'].get(cat, 0) > 0


def setup_raising(ctx, stats):
    """A setup move that raises one of `stats`, checked against Imperium's own
    move table by name membership in the verified setup list."""
    RAISES = {
        'Swords Dance': {'atk'}, 'Dragon Dance': {'atk', 'spe'}, 'Nasty Plot': {'spa'},
        'Calm Mind': {'spa', 'spd'}, 'Bulk Up': {'atk', 'def'},
        'Quiver Dance': {'spa', 'spd', 'spe'}, 'Shell Smash': {'atk', 'spa', 'spe'},
        'Agility': {'spe'}, 'Rock Polish': {'spe'}, 'Iron Defense': {'def'},
        'Curse': {'atk', 'def'}, 'Growth': {'atk', 'spa'}, 'Work Up': {'atk', 'spa'},
        'Coil': {'atk', 'def'}, 'Hone Claws': {'atk'}, 'Autotomize': {'spe'},
        'Tail Glow': {'spa'}, 'Geomancy': {'spa', 'spd', 'spe'},
        'Clangorous Soul': {'atk', 'spa', 'spe'}, 'No Retreat': {'atk', 'spa', 'spe'},
        'Victory Dance': {'atk', 'def', 'spe'}, 'Take Heart': {'spa', 'spd'},
        'Torch Song': {'spa'}, 'Fillet Away': {'atk', 'spa', 'spe'},
        'Belly Drum': {'atk'}, 'Meditate': {'atk'}, 'Sharpen': {'atk'},
        'Howl': {'atk'}, 'Charge Beam': {'spa'}, 'Power-Up Punch': {'atk'},
        'Dragon Ascent': set(),
    }
    for m in ctx['tool_names'].get('setup', []):
        if RAISES.get(m, set()) & stats:
            return True
    return False


def stab_ge(ctx, cat, minbp):
    return any(MOVES.get(m) and MOVES[m]['category'] == cat
               and MOVES[m]['basePower'] >= minbp and MOVES[m]['type'] in ctx['types']
               for m in ctx['pool'])


# Bonus tools each role actually WANTS. Scoring T as "fraction of all tool
# categories present" rewarded movepool breadth, which is itself a BST proxy
# (fully-evolved high-BST species learn more of everything). Restricting T to
# role-relevant tools is the first of the two rebalances made after the BST
# correlation failed its threshold -- see REBALANCE note at the bottom.
BONUS = {
 'physical_sweeper':['setup','priority','speed_control'],
 'special_sweeper':['setup','priority','speed_control'],
 'physical_wallbreaker':['setup','priority','status'],
 'special_wallbreaker':['setup','priority','status'],
 'mixed_attacker':['setup','priority','status'],
 'revenge_killer':['priority','speed_control','setup'],
 'trick_room_attacker':['speed_control','setup','recovery'],
 'physical_wall':['recovery','status','hazard','pivot','cleric'],
 'special_wall':['recovery','status','hazard','pivot','cleric'],
 'mixed_wall':['recovery','status','hazard','pivot','cleric'],
 'bulky_pivot':['pivot','recovery','hazard','status'],
 'tank':['recovery','status','priority','setup'],
 'hazard_setter':['hazard','status','recovery','priority'],
 'hazard_remover':['hazard_removal','recovery','pivot','status'],
 'cleric':['cleric','recovery','status','pivot'],
 'status_spreader':['status','recovery','hazard','pivot'],
 'screen_setter':['screens','speed_control','pivot','hazard'],
 'weather_terrain_setter':['weather','terrain','setup','recovery'],
 'trapper':['trapping','status','recovery','hazard'],
 'speed_control':['speed_control','screens','hazard','pivot'],
 'suicide_lead':['hazard','status','priority','screens'],
}

ARCHETYPES = {
    # ---------------- offensive ----------------
    'physical_sweeper': dict(
        stats=['atk', 'spe'], w=(0.38, 0.42, 0.20), enabler='sweeper',
        gates=lambda c: setup_raising(c, {'atk', 'spe'}) and stab_ge(c, 'Physical', 75)),
    'special_sweeper': dict(
        stats=['spa', 'spe'], w=(0.38, 0.42, 0.20), enabler='sweeper',
        gates=lambda c: setup_raising(c, {'spa', 'spe'}) and stab_ge(c, 'Special', 75)),
    'physical_wallbreaker': dict(
        stats=['atk'], w=(0.32, 0.48, 0.20), enabler='wallbreaker',
        gates=lambda c: bp(c, 'Physical', 2, 90) and atk_types(c, 'Physical', 3)),
    'special_wallbreaker': dict(
        stats=['spa'], w=(0.32, 0.48, 0.20), enabler='wallbreaker',
        gates=lambda c: bp(c, 'Special', 2, 90) and atk_types(c, 'Special', 3)),
    'mixed_attacker': dict(
        stats=['atk', 'spa'], w=(0.32, 0.48, 0.20), enabler='wallbreaker',
        gates=lambda c: stab_ge(c, 'Physical', 70) and stab_ge(c, 'Special', 70)),
    'revenge_killer': dict(
        stats=['spe', 'atk', 'spa'], w=(0.30, 0.50, 0.20), enabler='revenge',
        gates=lambda c: has(c, 'priority') or c['spe_pct'] >= 0.75),
    'trick_room_attacker': dict(
        stats=['atk', 'spa'], w=(0.32, 0.48, 0.20), enabler=None, invert_speed=True,
        gates=lambda c: c['spe_pct'] <= 0.25 and 'Trick Room' in MOVES
                        and max(c['base']['atk'], c['base']['spa']) >= 100),
    # ---------------- defensive ----------------
    'physical_wall': dict(
        stats=['hp', 'def'], w=(0.28, 0.47, 0.25), enabler='wall', product=('hp', 'def'),
        gates=lambda c: has(c, 'recovery')
                        and (has(c, 'status') or 'Intimidate' in c['abilities']
                             or any(m in c['pool'] for m in ('Whirlwind', 'Roar', 'Dragon Tail',
                                                             'Circle Throw')))),
    'special_wall': dict(
        stats=['hp', 'spd'], w=(0.28, 0.47, 0.25), enabler='wall', product=('hp', 'spd'),
        gates=lambda c: has(c, 'recovery') and (has(c, 'status') or has(c, 'cleric'))),
    'mixed_wall': dict(
        stats=['hp', 'def', 'spd'], w=(0.28, 0.47, 0.25), enabler='wall',
        gates=lambda c: has(c, 'recovery')
                        and c['def_pct'] >= 0.5 and c['spd_pct'] >= 0.5),
    'bulky_pivot': dict(
        stats=['hp', 'def', 'spd'], w=(0.25, 0.55, 0.20), enabler='pivot',
        gates=lambda c: has(c, 'pivot') and (c['def_pct'] >= 0.5 or c['spd_pct'] >= 0.5)),
    'tank': dict(
        stats=['hp', 'def', 'spd', 'atk', 'spa'], w=(0.35, 0.45, 0.20), enabler=None,
        gates=lambda c: c['hp_pct'] >= 0.5 and (c['def_pct'] >= 0.5 or c['spd_pct'] >= 0.5)
                        and max(c['atk_pct'], c['spa_pct']) >= 0.5),
    # ---------------- utility ----------------
    'hazard_setter': dict(
        stats=['hp', 'def', 'spe'], w=(0.18, 0.62, 0.20), enabler='hazard',
        gates=lambda c: has(c, 'hazard')),
    'hazard_remover': dict(
        stats=['hp', 'def', 'spd'], w=(0.20, 0.60, 0.20), enabler='pivot',
        gates=lambda c: has(c, 'hazard_removal')),
    'cleric': dict(
        stats=['hp', 'spd'], w=(0.20, 0.60, 0.20), enabler='wall',
        gates=lambda c: has(c, 'cleric')),
    'status_spreader': dict(
        stats=['hp', 'def', 'spd', 'spe'], w=(0.18, 0.62, 0.20), enabler='revenge',
        gates=lambda c: has(c, 'status')),
    'screen_setter': dict(
        stats=['spe', 'hp'], w=(0.18, 0.62, 0.20), enabler='revenge',
        gates=lambda c: len([m for m in c['tool_names'].get('screens', [])]) >= 2
                        or 'Aurora Veil' in c['pool']),
    'weather_terrain_setter': dict(
        stats=['hp', 'def'], w=(0.15, 0.65, 0.20), enabler=None,
        gates=lambda c: has(c, 'weather') or has(c, 'terrain')
                        or any(a in c['abilities'] for a in
                               ('Drought', 'Drizzle', 'Sand Stream', 'Snow Warning',
                                'Electric Surge', 'Grassy Surge', 'Psychic Surge',
                                'Misty Surge', 'Orichalcum Pulse', 'Hadron Engine'))),
    'trapper': dict(
        stats=['hp', 'def', 'spd'], w=(0.18, 0.62, 0.20), enabler=None,
        gates=lambda c: has(c, 'trapping')
                        or any(a in c['abilities'] for a in
                               ('Arena Trap', 'Shadow Tag', 'Magnet Pull'))),
    'speed_control': dict(
        stats=['spe'], w=(0.15, 0.65, 0.20), enabler='revenge',
        gates=lambda c: has(c, 'speed_control')),
    'suicide_lead': dict(
        stats=['spe'], w=(0.20, 0.60, 0.20), enabler='hazard',
        gates=lambda c: has(c, 'hazard') and c['spe_pct'] >= 0.75),
}
for k, v in ARCHETYPES.items():
    assert abs(sum(v['w']) - 1) < 1e-9, k

STATS = ['hp', 'atk', 'def', 'spa', 'spd', 'spe']

# =====================================================================
df = pd.DataFrame([{k: r[k] for k in
                    ('species', 'checkpoint', 'build', 'offense', 'defense',
                     'sustain', 'sustain_kit', 'sustain_bare', 'sweep_depth',
                     'duel_win_frac', 'heal_per_turn', 'hazard_chip', 'has_recovery',
                     'has_screens', 'n_hazards',
                     'speed_neutral', 'speed_plus', 'typing', 'utility', 'bst',
                     'ohko_frac', 'twohko_frac', 'survive1_frac', 'survive2_frac',
                     'mean_incoming_eff', 'stab_on_main_side', 'ability', 'item',
                     'nature', 'level', 'n_damaging_moves', 'n_tm_gated', 'n_tm_total',
                     'n_egg')} for r in rows])
print('frame:', df.shape)

# percentile ranks are computed WITHIN (checkpoint, build) -- i.e. within the
# pool the player can actually field at that point in the game.
base = pd.DataFrame([r['base'] for r in rows])
for s in STATS:
    df['base_' + s] = base[s].values
df['hp_def'] = df.base_hp * df.base_def
df['hp_spd'] = df.base_hp * df.base_spd

grp = df.groupby(['checkpoint', 'build'])
for s in STATS + ['hp_def', 'hp_spd']:
    df[s + '_pct'] = grp['base_' + s if s in STATS else s].rank(pct=True)

# ---- role-shape percentiles, one column per archetype -----------------
for name, spec in ARCHETYPES.items():
    core = spec['stats']
    share = sum(df['base_' + c] for c in core) / df[[
        'base_' + x for x in STATS]].sum(axis=1)
    if spec.get('invert_speed'):
        share = share * (1 - df.base_spe / df[['base_' + x for x in STATS]].sum(axis=1) * 6 / 5)
    df['shape_' + name] = df.groupby(['checkpoint', 'build'])[
        share.rename('s')].rank(pct=True) if False else share.groupby(
        [df.checkpoint, df.build]).rank(pct=True)

gate_bite = defaultdict(int)
gate_total = defaultdict(int)
results = []

pct_cols = {s: (s + '_pct') for s in STATS}

for i, r in enumerate(rows):
    d = df.iloc[i]
    ctx = dict(
        pool=set(sum(r['tool_names'].values(), [])) | set(),  # placeholder, replaced below
        tools=r['tools'], tool_names=r['tool_names'],
        types=r['types'], base=r['base'],
        abilities=SPECIES[r['species']]['abilities'],
    )
    # the real move pool for gate tests: level-up (<=cap) + gated TMs + eggs.
    sp = SPECIES[r['species']]
    learned = [m for m, lv in sp['levelup'] if lv <= r['level']]
    if r['build'] in ('ceiling', 'ceilingD'):
        cpobj = next(c for c in IN['checkpoints'] if c['checkpoint'] == r['checkpoint'])
        tmok = [m for m in sp['tm'] if m in set(cpobj['tms_available'])]
        ctx['pool'] = set(learned) | set(tmok) | set(sp['egg'])
    else:
        ctx['pool'] = set(learned)
    for s in STATS:
        ctx[s + '_pct'] = d[pct_cols[s]]

    fits = {}
    for name, spec in ARCHETYPES.items():
        gate_total[name] += 1
        try:
            passed = spec['gates'](ctx)
        except Exception:
            passed = False
        if not passed:
            gate_bite[name] += 1
            fits[name] = dict(fit=0.0, S=None, T=None, Y=None, gated=True)
            continue
        # ---- S : stat fit, percentiles inside the obtainable pool ----
        if spec.get('product') == ('hp', 'def'):
            S = d['hp_def_pct']
        elif spec.get('product') == ('hp', 'spd'):
            S = d['hp_spd_pct']
        else:
            vals = [d[pct_cols[s]] for s in spec['stats']]
            S = float(np.mean(vals))
        if spec.get('invert_speed'):
            S = float(np.mean([d[pct_cols[s]] for s in spec['stats']] + [1 - d['spe_pct']]))
        # ---- T : toolkit, bonus tools + enabling ability (weighted heavier)
        bonus_cats = BONUS[name]
        got = sum(1 for c in bonus_cats if r['tools'].get(c, 0) > 0)
        T_moves = got / len(bonus_cats)
        ab_list = ENABLERS.get(spec['enabler'], []) if spec['enabler'] else []
        T_abil = 1.0 if any(a in ab_list for a in ctx['abilities']) else 0.0
        T = min(1.0, 0.6 * T_moves + 0.4 * T_abil)
        # ---- Y : typing.  defensive roles use the resistance profile against
        # this boss; offensive roles use STAB quality on the main side.
        defensive = name in ('physical_wall', 'special_wall', 'mixed_wall',
                             'bulky_pivot', 'tank', 'hazard_remover', 'cleric')
        Y = r['typing'] if defensive else (0.75 if r['stab_on_main_side'] else 0.25)
        # SHAPE: what share of this species' own BST sits in the role's core
        # stats, percentile-ranked in the pool. A 480-BST species with 130 Atk
        # is more sweeper-SHAPED than a 600-BST species with 100 across the
        # board, and only the shape term can see that. Blended 60/40 with the
        # magnitude percentile. Second of the two post-failure rebalances.
        shape_key = 'shape_' + name
        S = 0.60 * S + 0.40 * float(d[shape_key])
        ws, wt, wy = spec['w']
        if SHIFT:
            ws2 = min(max(ws - SHIFT, 0.0), 1.0)
            wt2 = min(max(wt + SHIFT, 0.0), 1.0)
            tot = ws2 + wt2 + wy
            ws, wt, wy = ws2 / tot, wt2 / tot, wy / tot
        fits[name] = dict(fit=round(ws * S + wt * T + wy * Y, 4),
                          S=round(float(S), 4), T=round(T, 4), Y=round(float(Y), 4),
                          gated=False)
    ranked = sorted(fits.items(), key=lambda kv: -kv[1]['fit'])
    top3 = [k for k, v in ranked[:3] if v['fit'] > 0]
    prim = ranked[0][0] if ranked[0][1]['fit'] > 0 else 'NONE'
    hybrid = (len(ranked) > 1 and ranked[0][1]['fit'] > 0
              and ranked[0][1]['fit'] - ranked[1][1]['fit'] <= 0.05)
    results.append(dict(
        species=r['species'], checkpoint=r['checkpoint'], build=r['build'],
        primary_niche=prim,
        primary_niche_fit=ranked[0][1]['fit'],
        primary_S=ranked[0][1]['S'], primary_T=ranked[0][1]['T'], primary_Y=ranked[0][1]['Y'],
        niche_2=(ranked[1][0] if len(ranked) > 1 and ranked[1][1]['fit'] > 0 else 'NONE'),
        niche_2_fit=(ranked[1][1]['fit'] if len(ranked) > 1 else 0.0),
        niche_3=(ranked[2][0] if len(ranked) > 2 and ranked[2][1]['fit'] > 0 else 'NONE'),
        niche_3_fit=(ranked[2][1]['fit'] if len(ranked) > 2 else 0.0),
        is_hybrid=hybrid, n_niches_passed=sum(1 for v in fits.values() if not v['gated']),
        all_fits={k: v['fit'] for k, v in fits.items() if v['fit'] > 0}))

R = pd.DataFrame(results)
out = df.join(R.drop(columns=['species', 'checkpoint', 'build']))
out.to_parquet(P + 'archetypes.parquet') if False else None
out.to_pickle(P + OUT)

print('\n--- GATE BITE (archetypes.md validation 3) ---')
print(f'{"archetype":26} {"eliminated":>10} {"of":>7} {"%":>7}')
for k in ARCHETYPES:
    b, t = gate_bite[k], gate_total[k]
    print(f'{k:26} {b:10d} {t:7d} {100*b/t:6.1f}%')

print('\nrows where EVERY gate failed (no functional role):',
      int((out.primary_niche == 'NONE').sum()), 'of', len(out))
print('\nprimary_niche distribution (ceiling builds):')
print(out[out.build == 'ceiling'].primary_niche.value_counts().to_string())
print('\nwrote archetypes.pkl')
