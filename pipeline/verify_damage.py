"""Hand-verification of the calc's damage rolls against the formula in
references/mechanics.md, extended with the Gen5+ multiplier ORDER
(randomize -> STAB -> type), which is what a Gen 9 engine applies.

This is deliberately a SECOND, independent implementation: if it agreed with
the calc because it called the calc, it would prove nothing.
"""
import json, math, subprocess, sys, re

LAYER = json.load(open('/home/claude/p4/imperium_layer.json'))
SP, MV, TY = LAYER['species'], LAYER['moves'], LAYER['types']

NATURES = {
    'Adamant': ('atk', 'spa'), 'Modest': ('spa', 'atk'), 'Jolly': ('spe', 'spa'),
    'Timid': ('spe', 'atk'), 'Impish': ('def', 'spa'), 'Bold': ('def', 'atk'),
    'Calm': ('spd', 'atk'), 'Careful': ('spd', 'spa'), 'Brave': ('atk', 'spe'),
    'Quiet': ('spa', 'spe'), 'Relaxed': ('def', 'spe'), 'Sassy': ('spd', 'spe'),
    'Serious': (None, None), 'Hardy': (None, None), 'Naive': ('spe', 'spd'),
    'Hasty': ('spe', 'def'), 'Lonely': ('atk', 'def'), 'Naughty': ('atk', 'spd'),
    'Mild': ('spa', 'def'), 'Rash': ('spa', 'spd'), 'Gentle': ('spd', 'def'),
    'Lax': ('def', 'spd'), 'Docile': (None, None), 'Bashful': (None, None),
    'Quirky': (None, None),
}
KEY = {'hp': 'hp', 'atk': 'atk', 'def': 'df', 'spa': 'spa', 'spd': 'spd', 'spe': 'spe'}


def poke_round(x):
    """Engine rounding: .5 rounds DOWN."""
    return math.floor(x) if (x - math.floor(x)) <= 0.5 else math.ceil(x)


def stat(base, iv, ev, level, natmod, is_hp):
    if is_hp:
        return math.floor((2 * base + iv + ev // 4) * level / 100) + level + 10
    return math.floor((math.floor((2 * base + iv + ev // 4) * level / 100) + 5) * natmod)


def stats_of(spec):
    s = SP[spec['species']]
    bs = s['baseStats']
    lvl = spec['level']
    evs = spec.get('evs', {})
    ivs = spec.get('ivs', {})
    plus, minus = NATURES[spec.get('nature', 'Serious')]
    out = {}
    for k in ['hp', 'atk', 'def', 'spa', 'spd', 'spe']:
        nm = 1.1 if k == plus else (0.9 if k == minus else 1.0)
        out[k] = stat(bs[KEY[k]], ivs.get(k, 31), evs.get(k, 0), lvl, nm, k == 'hp')
    return out, s['types']


def type_mult(move_type, def_types):
    m = 1.0
    for t in def_types:
        if isinstance(t, str) and t in TY[move_type]:
            m *= TY[move_type][t]
    return m


def hand_rolls(job):
    a_stats, a_types = stats_of(job['attacker'])
    d_stats, d_types = stats_of(job['defender'])
    mv = MV[job['move']]
    lvl = job['attacker']['level']
    if mv['category'] == 'Physical':
        A, D = a_stats['atk'], d_stats['def']
    else:
        A, D = a_stats['spa'], d_stats['spd']
    P = mv['basePower']
    base = math.floor(math.floor(math.floor(2 * lvl / 5 + 2) * P * A / 50) / D) + 2
    stab = 1.5 if mv['type'] in [t for t in a_types if isinstance(t, str)] else 1.0
    eff = type_mult(mv['type'], d_types)
    rolls = []
    for r in range(85, 101):
        d = math.floor(base * r / 100)
        if stab != 1.0:
            d = poke_round(d * stab)
        d = math.floor(d * eff)
        rolls.append(max(d, 1) if eff > 0 else 0)
    return rolls, d_stats['hp'], dict(base=base, stab=stab, eff=eff, A=A, D=D, P=P)


CASES = [
    # id, attacker, defender, move  -- spanning types, levels, natures, EVs, STAB/none, resist/SE/immune
    ('v01', dict(species='Swampert', level=50), dict(species='Sceptile', level=50), 'Earthquake'),
    ('v02', dict(species='Blaziken', level=50, nature='Adamant', evs={'atk': 252}),
     dict(species='Skarmory', level=50, nature='Impish', evs={'hp': 252, 'def': 252}), 'Close Combat'),
    ('v03', dict(species='Pikachu', level=15), dict(species='Gyarados', level=15), 'Thunderbolt'),
    ('v04', dict(species='Gengar', level=85, nature='Modest', evs={'spa': 252}),
     dict(species='Snorlax', level=85, evs={'hp': 252, 'spd': 252}, nature='Careful'), 'Shadow Ball'),
    ('v05', dict(species='Aggron', level=34), dict(species='Manectric', level=34), 'Iron Head'),
    ('v06', dict(species='Milotic', level=68, nature='Modest'), dict(species='Camerupt', level=68), 'Surf'),
    ('v07', dict(species='Salamence', level=82, nature='Adamant', evs={'atk': 252}),
     dict(species='Metagross', level=82, evs={'hp': 252}), 'Dragon Claw'),
    ('v08', dict(species='Alakazam', level=25), dict(species='Machoke', level=25), 'Psychic'),
    ('v09', dict(species='Tyranitar', level=76, nature='Brave'), dict(species='Latios', level=76), 'Crunch'),
    ('v10', dict(species='Ludicolo', level=47), dict(species='Groudon', level=47), 'Giga Drain'),
    ('v11', dict(species='Sableye', level=30), dict(species='Gardevoir', level=30), 'Shadow Sneak'),
    ('v12', dict(species='Rhydon', level=59), dict(species='Zapdos', level=59), 'Earthquake'),  # immune
    ('v13', dict(species='Weavile', level=80, nature='Jolly', evs={'atk': 252}),
     dict(species='Dragonite', level=80), 'Ice Punch'),
    ('v14', dict(species='Registeel', level=64, evs={'atk': 252}, nature='Adamant'),
     dict(species='Gardevoir', level=64), 'Iron Head'),
]

jobs = [dict(id=i, attacker=a, defender=d, move=m) for i, a, d, m in CASES]
proc = subprocess.run(['node', '/home/claude/p4/calc_batch.js'],
                      input=json.dumps(jobs), capture_output=True, text=True,
                      cwd='/home/claude/p4')
if proc.returncode != 0:
    print(proc.stderr[:3000]); sys.exit(1)
res = {r['id']: r for r in json.loads(proc.stdout)}

print(f"{'id':5} {'matchup':44} {'calc':>10} {'hand':>10} {'stats':>6} {'verdict'}")
mismatch = 0
for j in jobs:
    r = res[j['id']]
    hr, hp, dbg = hand_rolls(j)
    if not r['ok']:
        print(f"{j['id']:5} ERROR {r['error'][:60]}"); mismatch += 1; continue
    calc = (r['min'], r['max'])
    hand = (min(hr), max(hr))
    hs, _ = stats_of(j['attacker'])
    stats_ok = (r['attacker_stats']['atk'] == hs['atk'] and r['attacker_stats']['spa'] == hs['spa']
                and r['attacker_stats']['spe'] == hs['spe'] and r['attacker_stats']['def'] == hs['def'])
    ok = (calc == hand) and stats_ok and (r['defender_maxhp'] == hp)
    if not ok:
        mismatch += 1
    label = f"{j['attacker']['species']} L{j['attacker']['level']} {j['move']} -> {j['defender']['species']}"
    print(f"{j['id']:5} {label:44} {str(calc):>10} {str(hand):>10} "
          f"{'ok' if stats_ok else 'DIFF':>6} {'MATCH' if ok else '*** MISMATCH'}  "
          f"[eff={dbg['eff']} stab={dbg['stab']} base={dbg['base']}]")

print(f"\n{len(jobs) - mismatch}/{len(jobs)} match. discrepancy rate = {mismatch/len(jobs):.1%}")
