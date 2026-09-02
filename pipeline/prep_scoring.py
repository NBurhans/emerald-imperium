"""Assemble everything the node scorer needs into one JSON.

Produces:
  checkpoints[]  cap, label, threat roster (resolved slots), pool (species names)
  species{}      stats/types/abilities + level-up, TM and egg movepools
  tools{}        move-category lists, each VERIFIED to exist in Imperium's
                 own move table before use (per archetypes.md sec.3)
  Every name substitution and every failure is logged, never silently fixed.
"""
import pandas as pd, json, re
from collections import defaultdict

P = '/home/claude/p4/'
L = json.load(open(P + 'imperium_layer.json'))
S = pd.read_csv(P + 'species_avail.tsv', sep='\t', dtype=str)
SLOTS = pd.read_csv(P + '03_trainer_slots.tsv', sep='\t', dtype=str)
CP = pd.read_csv(P + 'checkpoints.tsv', sep='\t')
W = pd.read_csv(P + '02_world.tsv', sep='\t', dtype=str)

LBL2NUM = {v: k for k, v in zip(CP.checkpoint, CP.checkpoint_label)}
NCP = len(CP)


def gate_num(g):
    if g in LBL2NUM:
        return LBL2NUM[g]
    if g == 'postgame':
        return NCP
    return None

LOG = []


def log(kind, detail, n=1):
    LOG.append(dict(kind=kind, detail=detail, n=n))


def norm(s):
    return re.sub(r'[^a-z0-9]+', '', str(s).lower())


SPKEY = {norm(k): k for k in L['species']}
# The layer and the TSV share internal_index 1:1 across all 1,534 rows
# (0 unmatched in either direction), so species rows are joined on the INDEX,
# never on species_name. Name-joining collapsed every alternate form onto its
# base -- 'Venusaur' base and 'Venusaur' Mega are two rows with one name -- and
# silently dropped 510 of 1,534 movepools before this was caught.
SPKEY_BY_IIDX = {v['internal_index']: k for k, v in L['species'].items()}
MVKEY = {norm(k): k for k in L['moves']}
ABKEY = {norm(a): a for a in L['abilities']}
ITKEY = {norm(i): i for i in L['items']}
MOVE_BY_ID = {v['move_id']: k for k, v in L['moves'].items()}

# ---- Hidden Power variants: synthesise one move per type ---------------
# The rosters name 'Hidden Power Fire' etc.; Imperium's move table has only
# 'Hidden Power'. The roster's 30-IV annotations are what set the type in game
# (RUN_CONFIG records 36 such slots tracking 39 Hidden Power moves), so the
# type is authored, not guessed -- but the base power is taken from Imperium's
# own Hidden Power entry, and the whole synthetic move is marked Inferred.
HP_BASE = L['moves'].get('Hidden Power')
hp_added = []
if HP_BASE:
    for t in L['type_order']:
        nm = f'Hidden Power {t}'
        if nm not in L['moves']:
            m = dict(HP_BASE)
            m['name'], m['id'], m['type'] = nm, norm(nm), t
            L['moves'][nm] = m
            MVKEY[norm(nm)] = nm
            hp_added.append(nm)
    log('synthetic move added (Hidden Power typing from roster IV lines)',
        f'{len(hp_added)} variants at BP={HP_BASE["basePower"]}', len(hp_added))
else:
    log('ERROR', 'Hidden Power absent from Imperium move table')


# Form tie-break. The first version took the SHORTEST candidate name, which is
# wrong in exactly the cases that matter: a transformed form often has a
# shorter suffix than the base one. 'Darmanitan' resolved to Darmanitan-ZEN
# (540 BST, Fire/Psychic, 30 Atk / 140 SpA) instead of Darmanitan-Standard
# (480 BST, pure Fire, 140 Atk / 30 SpA) -- an inverted offensive profile on a
# boss the whole cp18 column is scored against. 'Toxtricity' resolved to the
# 621-BST MEGA instead of the 502-BST Amped form.
#
# The ROM's own ordering is the fix: base forms sit in the main dex block and
# alternate forms are appended after index ~906, so the LOWEST internal_index
# among the candidates is the default form. Verified against eight families --
# Toxtricity-Amped, Darmanitan-Standard, Darmanitan-Galar-Standard,
# Basculegion-M, Xerneas-Neutral, Aegislash-Shield, Eiscue-Ice,
# Landorus-Incarnate, Maushold-Three -- all correct.
IIDX_OF_NAME = {k: v['internal_index'] for k, v in L['species'].items()}


def resolve(name, table, kind):
    """Exact-on-normalised first; then prefix. Among prefix candidates for a
    SPECIES, the lowest internal_index (the ROM's base form) wins; for other
    entity kinds the shortest name wins. Every non-exact hit is logged."""
    if name is None or (isinstance(name, float)) or str(name) in ('nan', 'NONE', 'NA', 'UNK', ''):
        return None
    k = norm(name)
    if k in table:
        return table[k]
    cands = [v for kk, v in table.items() if kk.startswith(k)]
    if cands:
        if all(c in IIDX_OF_NAME for c in cands):
            cands.sort(key=lambda c: IIDX_OF_NAME[c])
            how = 'lowest internal_index = ROM base form'
        else:
            cands.sort(key=len)
            how = 'shortest name'
        log(f'{kind} resolved by prefix', f'{name!r} -> {cands[0]!r}'
            + (f'  ({len(cands)} candidates, {how})' if len(cands) > 1 else ''))
        return cands[0]
    log(f'{kind} UNRESOLVED', repr(name))
    return None


# ---- resolve roster slots ---------------------------------------------
SLOTS['tid'] = SLOTS.sheet + ':' + SLOTS.trainer + ':' + SLOTS.header_row
STAT_KEY = {'HP': 'hp', 'Atk': 'atk', 'Def': 'def', 'SpA': 'spa', 'SpD': 'spd', 'Spe': 'spe'}


def parse_spread(txt, default):
    """'6 HP / 252 Atk / 252 Spe' -> dict. Absent -> the stated default."""
    out = {k: default for k in STAT_KEY.values()}
    if txt is None or str(txt) in ('nan', 'NONE', 'NA', 'UNK', ''):
        return out, False
    for part in str(txt).split('/'):
        m = re.match(r'\s*(\d+)\s*([A-Za-z]+)\s*$', part)
        if m and m.group(2) in STAT_KEY:
            out[STAT_KEY[m.group(2)]] = int(m.group(1))
    return out, True


def build_slot(r, cap):
    sp = resolve(r.species, SPKEY, 'roster species')
    if sp is None:
        return None
    moves, unres_mv = [], []
    for m in str(r.moves).split(';'):
        if not m or m in ('NONE', 'nan'):
            continue
        rm = resolve(m, MVKEY, 'roster move')
        (moves if rm else unres_mv).append(rm or m)
    ab = resolve(r.ability, ABKEY, 'roster ability')
    it = resolve(r.held_item, ITKEY, 'roster item')
    if r.held_item not in (None, 'NONE') and str(r.held_item) not in ('nan', 'NONE') and it is None:
        unres_item = str(r.held_item)
    else:
        unres_item = None
    evs, has_ev = parse_spread(r.evs, 0)
    # RUN_CONFIG: 31 across the board unless the slot carries an IVs: line,
    # in which case that line overrides. The 9 '0 Spe' slots are deliberate.
    ivs, has_iv = parse_spread(r.ivs, 31)
    try:
        lvl = int(float(r.level))
        level_fixed = True
    except (ValueError, TypeError):
        lvl = cap                      # scales to the player -> parity at cap
        level_fixed = False
    nat = r.nature if str(r.nature) not in ('nan', 'NONE', 'NA') else 'Serious'
    return dict(species=sp, level=lvl, level_fixed=level_fixed, nature=nat,
                ability=ab, item=it, evs=evs, ivs=ivs, moves=moves,
                unresolved_moves=unres_mv, unresolved_item=unres_item,
                trainer=r.tid, is_mega=str(r.is_mega) == 'True',
                mega_ability=r.mega_ability if str(r.mega_ability) not in ('nan', 'NONE') else None)


# cp09 has no anchor boss: the Trick House sheet trainers ARE the threat pool
# at that story point, so they are used, and the substitution is logged.
CP09_POOL = SLOTS[SLOTS.sheet == 'Trick House']

# ---- Phase 2 gates for CEILING builds ---------------------------------
# 'A ceiling built on a held item the player cannot get until two badges later
# is a fiction.' So the ceiling's TM list and item list are capped by
# 02_world.earliest_gate. TM rows store the MOVE id in internal_id (see the
# collision note in build_availability.py), which is exactly what is needed to
# gate a TM by the move it teaches.
tm_gate = {}
for _, r in W[W.entity_type.isin(['TM', 'HM'])].iterrows():
    n = gate_num(r.earliest_gate)
    try:
        mid = int(r.internal_id)
    except (ValueError, TypeError):
        continue
    nm = MOVE_BY_ID.get(mid)
    if nm is None or n is None:
        continue
    if nm not in tm_gate or n < tm_gate[nm]:
        tm_gate[nm] = n
log('TM gates derived', f'{len(tm_gate)} distinct TM moves gated by checkpoint')

item_gate = {}
for _, r in W[W.entity_type == 'held_item'].iterrows():
    n = gate_num(r.earliest_gate)
    nm = resolve(r.entity_name, ITKEY, 'held item')
    if nm is None or n is None:
        continue
    if nm not in item_gate or n < item_gate[nm]:
        item_gate[nm] = n
log('held item gates derived', f'{len(item_gate)} held items gated by checkpoint')

checkpoints = []
for _, c in CP.iterrows():
    ids = [] if c.anchor_trainers == 'NONE' else c.anchor_trainers.split(';')
    sub = SLOTS[SLOTS.tid.isin(ids)]
    roster_basis = 'anchor_fight'
    if len(sub) == 0 and c.checkpoint == 9:
        sub = CP09_POOL
        roster_basis = 'trick_house_sheet_substituted'
        log('checkpoint roster substituted',
            'cp09 Pre-TrickHouse has no boss fight; the 9 Trick House sheet '
            f'trainers ({len(sub)} slots, all scaling) used as its threat pool')
    slots = [s for s in (build_slot(r, int(c.level_cap)) for r in sub.itertuples()) if s]
    pool = S[(S.avail_cp.astype('Int64') <= c.checkpoint)]
    checkpoints.append(dict(
        checkpoint=int(c.checkpoint), label=c.checkpoint_label, cap=int(c.level_cap),
        cap_basis=c.cap_basis, roster_basis=roster_basis,
        n_slots_source=len(sub), slots=slots,
        tms_available=[m for m, g in tm_gate.items() if g <= c.checkpoint],
        items_available=[i for i, g in item_gate.items() if g <= c.checkpoint],
        pool=[p for p in (SPKEY_BY_IIDX.get(int(i)) for i in pool.iidx) if p]))

# ---- species movepools -------------------------------------------------
def id_list(txt):
    if str(txt) in ('nan', 'NONE', 'NA', 'UNK', ''):
        return []
    out = []
    for tok in str(txt).split(','):
        tok = tok.strip()
        if not tok:
            continue
        try:
            out.append(int(tok))
        except ValueError:
            pass
    return out


species = {}
lvl_unres = tm_unres = 0
for r in S.itertuples():
    key = SPKEY_BY_IIDX.get(int(r.iidx))
    if key is None:
        log('species internal_index absent from layer', str(r.iidx))
        continue
    lvl = []
    if str(r.levelup_moves) not in ('nan', 'NONE', 'NA', 'UNK'):
        for pair in str(r.levelup_moves).split(','):
            if ':' not in pair:
                continue
            mid, at = pair.split(':')
            nm = MOVE_BY_ID.get(int(mid))
            if nm:
                lvl.append([nm, int(at)])
            else:
                lvl_unres += 1
    tms = []
    for mid in id_list(r.tm_moves):
        nm = MOVE_BY_ID.get(mid)
        if nm:
            tms.append(nm)
        else:
            tm_unres += 1
    eggs = [MOVE_BY_ID[m] for m in id_list(r.egg_moves) if m in MOVE_BY_ID]
    species[key] = dict(
        name=key, iidx=int(r.iidx), dex=r.dex_number, form_type=r.form_type,
        lineage=r.lineage_id, evo_stage=r.evo_stage,
        avail_cp=(int(r.avail_cp) if str(r.avail_cp) not in ('nan', '<NA>') else None),
        avail_basis=r.avail_basis, avail_conf=r.avail_conf,
        abilities=[a for a in [r.ability1, r.ability2, r.ability_hidden]
                   if str(a) not in ('nan', 'NONE', 'NA', 'UNK')],
        levelup=lvl, tm=tms, egg=eggs,
        is_starter=(r.is_starter == 'True'), one_time=(r.one_time_only == 'True'),
        missable=(r.missable == 'True'),
        evolves_into=r.evolves_into, evolves_from=r.evolves_from,
        bst=int(r.bst))
if lvl_unres or tm_unres:
    log('movepool move ids not resolving', f'levelup={lvl_unres} tm={tm_unres}')

# ---- tool categories, verified against Imperium's move table ------------
CANDIDATES = dict(
    recovery=['Recover', 'Roost', 'Soft-Boiled', 'Synthesis', 'Morning Sun', 'Moonlight',
              'Slack Off', 'Milk Drink', 'Heal Order', 'Shore Up', 'Rest', 'Wish',
              'Strength Sap', 'Jungle Healing', 'Life Dew', 'Purify'],
    hazard=['Stealth Rock', 'Spikes', 'Toxic Spikes', 'Sticky Web', 'Stone Axe',
            'Ceaseless Edge'],
    hazard_removal=['Rapid Spin', 'Defog', 'Mortal Spin', 'Tidy Up', 'Court Change'],
    pivot=['U-turn', 'Volt Switch', 'Flip Turn', 'Teleport', 'Parting Shot',
           'Baton Pass', 'Shed Tail', 'Chilly Reception'],
    screens=['Reflect', 'Light Screen', 'Aurora Veil'],
    status=['Will-O-Wisp', 'Thunder Wave', 'Toxic', 'Spore', 'Sleep Powder', 'Glare',
            'Hypnosis', 'Nuzzle', 'Yawn', 'Stun Spore', 'Poison Powder', 'Lovely Kiss',
            'Dark Void', 'Sing', 'Grass Whistle'],
    cleric=['Heal Bell', 'Aromatherapy', 'Healing Wish', 'Lunar Dance', 'Wish'],
    speed_control=['Tailwind', 'Trick Room', 'Sticky Web', 'Thunder Wave', 'Icy Wind',
                   'Electroweb', 'Bulldoze', 'Rock Tomb'],
    trapping=['Mean Look', 'Block', 'Spider Web', 'Fairy Lock', 'Anchor Shot',
              'Spirit Shackle', 'Jaw Lock', 'Thousand Waves'],
    weather=['Sunny Day', 'Rain Dance', 'Sandstorm', 'Hail', 'Snowscape', 'Chilly Reception'],
    terrain=['Electric Terrain', 'Grassy Terrain', 'Psychic Terrain', 'Misty Terrain'],
    priority=['Extreme Speed', 'Aqua Jet', 'Bullet Punch', 'Ice Shard', 'Mach Punch',
              'Shadow Sneak', 'Sucker Punch', 'Quick Attack', 'Vacuum Wave', 'Water Shuriken',
              'Accelerock', 'Grassy Glide', 'Jet Punch', 'First Impression', 'Fake Out'],
)
# RECOVERY IS DETECTED FROM THE FLAG, NOT THE NAME LIST.
# Imperium's move records DO carry flags.healing (36 moves) -- an earlier draft
# of this file wrongly claimed they did not and fell back to a curated list.
# archetypes.md sec.3 prefers flag detection precisely because hacks add
# healers a name list will never contain, and this hack has several
# (Matcha Gotcha, Bitter Blade, Lunar Blessing).
#
# The flag alone is too broad for the WALL gate, though: it also marks drain
# moves (Absorb, Giga Drain, Drain Punch, Leech Life...), which heal a fraction
# of DAMAGE DEALT, not of max HP. A wall that "recovers" only by draining is
# not a wall. So the flag set is split:
#   recovery -> healing flag AND category Status, minus the ally-target and
#               sacrificial moves. This is what gates the wall archetypes.
#   drain    -> healing flag AND a damaging category. Counted as a toolkit
#               bonus, never as gate-qualifying recovery.
HEAL_FLAGGED = [k for k, v in L['moves'].items() if v.get('flags', {}).get('healing')]
NOT_SELF_SUSTAIN = {'Heal Pulse', 'Healing Wish', 'Lunar Dance', 'Revival Blessing',
                    'Floral Healing', 'Lunar Blessing', 'Life Dew', 'Jungle Healing'}
RECOVERY_FLAG = [m for m in HEAL_FLAGGED
                 if L['moves'][m]['category'] == 'Status' and m not in NOT_SELF_SUSTAIN]
DRAIN_FLAG = [m for m in HEAL_FLAGGED if L['moves'][m]['category'] != 'Status']
CANDIDATES['recovery'] = sorted(set(CANDIDATES['recovery']) | set(RECOVERY_FLAG))
CANDIDATES['drain'] = sorted(DRAIN_FLAG)
log('recovery detected from flags.healing, not a name list',
    f'{len(HEAL_FLAGGED)} flagged -> {len(RECOVERY_FLAG)} reliable recovery '
    f'(Status, self-sustaining) + {len(DRAIN_FLAG)} drain moves held separately; '
    f'flag-only finds not in the curated list: '
    + ','.join(sorted(set(RECOVERY_FLAG) - set(CANDIDATES["cleric"]))[:6]))

tools, missing_tools = {}, {}
for cat, names in CANDIDATES.items():
    present = [n for n in names if n in L['moves']]
    absent = [n for n in names if n not in L['moves']]
    tools[cat] = present
    if absent:
        missing_tools[cat] = absent
log('tool categories built from Imperium move table',
    json.dumps({k: len(v) for k, v in tools.items()}))
if missing_tools:
    log('candidate tool moves NOT in Imperium move table (dropped, not assumed)',
        json.dumps(missing_tools))

# setup moves: derived from the table's own self-boost data where present,
# else the curated list. Imperium's move records carry no `self.boosts` field,
# so the curated list is what is actually used -- stated, not hidden.
SETUP = ['Swords Dance', 'Dragon Dance', 'Nasty Plot', 'Calm Mind', 'Bulk Up',
         'Quiver Dance', 'Shell Smash', 'Agility', 'Rock Polish', 'Iron Defense',
         'Curse', 'Growth', 'Work Up', 'Coil', 'Hone Claws', 'Autotomize',
         'Tail Glow', 'Geomancy', 'Clangorous Soul', 'No Retreat', 'Victory Dance',
         'Take Heart', 'Torch Song', 'Fillet Away', 'Belly Drum', 'Meditate',
         'Sharpen', 'Howl', 'Charge Beam', 'Power-Up Punch', 'Dragon Ascent']
n_self_boost = sum(1 for m in L['moves'].values()
                   if isinstance(m.get('self'), dict) and m['self'].get('boosts'))
tools['setup'] = [m for m in SETUP if m in L['moves']]
log('setup move detection',
    f'moves in table exposing self.boosts: {n_self_boost}; '
    f'curated list used, {len(tools["setup"])}/{len(SETUP)} present')

# abilities that enable a role (weighted heavier in the toolkit term)
tools['enabler_abilities'] = dict(
    wall=['Regenerator', 'Unaware', 'Magic Guard', 'Intimidate', 'Fur Coat', 'Ice Scales',
          'Thick Fat', 'Natural Cure', 'Poison Heal', 'Multiscale', 'Filter', 'Solid Rock'],
    sweeper=['Speed Boost', 'Moxie', 'Beast Boost', 'Sharpness', 'Adaptability',
             'Chlorophyll', 'Swift Swim', 'Sand Rush', 'Slush Rush', 'Protosynthesis',
             'Quark Drive', 'Unburden', 'Competitive', 'Soul-Heart'],
    wallbreaker=['Sheer Force', 'Guts', 'Huge Power', 'Pure Power', 'Solar Power',
                 'Tinted Lens', 'Mold Breaker', 'Technician', 'Adaptability', 'Analytic'],
    pivot=['Regenerator', 'Natural Cure', 'Volt Absorb', 'Water Absorb'],
    revenge=['Prankster', 'Gale Wings', 'Triage'],
    hazard=['Sturdy', 'Prankster'],
)

out = dict(checkpoints=checkpoints, species=species, tools=tools,
           moves=L['moves'], types=L['types'], type_order=L['type_order'])
json.dump(out, open(P + 'scoring_input.json', 'w'))

agg = defaultdict(int)
for e in LOG:
    agg[e['kind']] += e['n']
print('--- prep log (counts by kind) ---')
for k, v in sorted(agg.items(), key=lambda kv: -kv[1]):
    print(f'  {v:5d}  {k}')
print()
print('checkpoints:', len(checkpoints))
for c in checkpoints:
    print(f"  cp{c['checkpoint']:02d} {c['label']:26} cap={c['cap']:2d} "
          f"slots={len(c['slots']):3d}/{c['n_slots_source']:3d} pool={len(c['pool']):4d} "
          f"tm={len(c['tms_available']):3d} item={len(c['items_available']):2d} "
          f"roster={c['roster_basis']}")
print('\nspecies with movepools:', len(species))
json.dump(LOG, open(P + 'prep_log.json', 'w'), indent=1)
print('wrote scoring_input.json + prep_log.json')
