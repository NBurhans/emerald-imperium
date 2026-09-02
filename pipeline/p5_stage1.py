"""Phase 5 stage 1 — round-trip and missing-data sweep.

Everything is re-read from the SHIPPED bundle on disk. The working pickles in
/home/claude are deliberately not touched: if the bundle is wrong, checking it
against the objects that produced it proves nothing.
"""
import pandas as pd, json, re, os
from collections import Counter, defaultdict

B = '/mnt/user-data/outputs/emerald_imperium/'
OUT = []


def rec(area, check, result, severity, affected, effect):
    OUT.append(dict(area=area, check=check, result=result, severity=severity,
                    affected=affected, effect=effect))
    print(f'[{severity:10}] {area:14} {check:46} {result}')


FILES = {'01_species.tsv': 1534, '02_world.tsv': 419, '03_trainers.tsv': 164,
         '03_trainer_slots.tsv': 678, '04_valuation.tsv': 1311,
         '05_checkpoints.tsv': 19, '06_lineage.tsv': None}

print('=' * 100)
print('STAGE 1a — ROUND-TRIP')
print('=' * 100)
D = {}
for f, expect in FILES.items():
    path = B + f
    raw = open(path, encoding='utf-8').read()
    df = pd.read_csv(path, sep='\t', dtype=str)
    D[f] = df
    # a file that lost its last line to truncation still parses; check the bytes
    ends_nl = raw.endswith('\n')
    nl = raw.count('\n')
    ok = (expect is None or len(df) == expect)
    rec('round-trip', f, f'{len(df)} rows, {len(df.columns)} cols, ends with newline={ends_nl}',
        '—' if ok and ends_nl else 'Material', 0 if ok else 1,
        'pass' if ok else f'EXPECTED {expect}')
    # ragged rows: pandas silently pads
    hdr = raw.split('\n', 1)[0].count('\t') + 1
    bad = sum(1 for ln in raw.split('\n')[1:] if ln and ln.count('\t') + 1 != hdr)
    if bad:
        rec('round-trip', f + ' ragged rows', f'{bad} rows with wrong field count',
            'Material', bad, 'pandas pads silently; investigate')

print()
print('=' * 100)
print('STAGE 1b — ENCODED COLUMN DECODE')
print('=' * 100)
V = D['04_valuation.tsv']
S = D['01_species.tsv']

# cp:value pair columns
pair_cols = [c for c in V.columns if c.endswith('_by_checkpoint')]
for c in pair_cols:
    bad, ncp = 0, Counter()
    for s in V[c].dropna():
        parts = str(s).split(',')
        for p in parts:
            if p.count(':') != 1:
                bad += 1
        ncp[len(parts)] += 1
    rec('decode', f'04_valuation.{c}',
        f'{len(V[c].dropna())} non-null, {bad} malformed pairs, '
        f'checkpoint-counts seen {sorted(ncp)[:6]}',
        '—' if bad == 0 else 'Material', bad, 'pass' if bad == 0 else 'malformed')

# every curve must have exactly as many entries as the species is obtainable for
mismatch = []
for r in V.itertuples():
    try:
        n = len(str(r.value_by_checkpoint).split(','))
        if n != int(r.n_checkpoints_obtainable):
            mismatch.append((r.species_form, n, r.n_checkpoints_obtainable))
    except (ValueError, TypeError):
        mismatch.append((r.species_form, 'ERR', r.n_checkpoints_obtainable))
rec('decode', 'curve length == n_checkpoints_obtainable',
    f'{len(mismatch)} mismatches of {len(V)}',
    '—' if not mismatch else 'Material', len(mismatch),
    'pass' if not mismatch else str(mismatch[:5]))

# curve start must equal earliest_checkpoint
bad_start = []
for r in V.itertuples():
    if r.earliest_checkpoint == 'UNK':
        continue
    first = str(r.value_by_checkpoint).split(',')[0].split(':')[0]
    if first != str(r.earliest_checkpoint):
        bad_start.append((r.species_form, first, r.earliest_checkpoint))
rec('decode', 'curve starts at earliest_checkpoint',
    f'{len(bad_start)} mismatches', '—' if not bad_start else 'Material',
    len(bad_start), 'pass' if not bad_start else str(bad_start[:5]))

# lineage encoding. Values escape a literal colon as backslash-colon, so a
# naive p.count(':') == 1 test fails on correctly-escaped data -- it did, on the
# two 'Type: Null' rows, and that was the CHECKER being wrong, not the file.
# The test splits on the first UNESCAPED colon and requires the rest to contain
# no unescaped colon.
UNESC = re.compile(r'(?<!\\):')
badlin = 0
decoded = []
for s in V.lineage_form_per_checkpoint.dropna():
    for p in str(s).split(','):
        parts = UNESC.split(p)
        if len(parts) != 2 or not parts[0].strip().isdigit():
            badlin += 1
        else:
            decoded.append(parts[1].replace(chr(92) + ':', ':'))
rec('decode', '04_valuation.lineage_form_per_checkpoint (colon-escape aware)',
    f'{badlin} malformed; {len(set(decoded))} distinct forms decode, '
    f"including {'Type: Null' in set(decoded) and 'Type: Null' or 'n/a'}",
    '—' if badlin == 0 else 'Material', badlin,
    'pass' if badlin == 0 else 'malformed')

# Phase 1 movepool encodings
badlv = 0
for s in S.levelup_moves.dropna():
    if s in ('NONE', 'NA', 'UNK'):
        continue
    for p in str(s).split(','):
        if p.count(':') != 1 or not all(x.strip().isdigit() for x in p.split(':')):
            badlv += 1
rec('decode', '01_species.levelup_moves (move:level)', f'{badlv} malformed pairs',
    '—' if badlv == 0 else 'Material', badlv, 'pass' if badlv == 0 else 'malformed')

badtm = 0
for s in S.tm_moves.dropna():
    if s in ('NONE', 'NA', 'UNK'):
        continue
    for p in str(s).split(','):
        if not p.strip().isdigit():
            badtm += 1
rec('decode', '01_species.tm_moves (id list)', f'{badtm} malformed ids',
    '—' if badtm == 0 else 'Material', badtm, 'pass' if badtm == 0 else 'malformed')

print()
print('=' * 100)
print('STAGE 1c — MISSING-DATA SWEEP (UNK / NA / NONE by column)')
print('=' * 100)
SENT = ('UNK', 'NA', 'NONE')
sweep = []
for f, df in D.items():
    for c in df.columns:
        vc = df[c].astype(str).value_counts()
        counts = {s: int(vc.get(s, 0)) for s in SENT}
        nulls = int(df[c].isna().sum())
        if sum(counts.values()) or nulls:
            sweep.append(dict(file=f, column=c, UNK=counts['UNK'], NA=counts['NA'],
                              NONE=counts['NONE'], blank=nulls, rows=len(df)))
SW = pd.DataFrame(sweep).sort_values('UNK', ascending=False)
print('\ncolumns with UNK > 0 (the only sentinel that means "the source does not say"):')
print(SW[SW.UNK > 0][['file', 'column', 'UNK', 'rows']].to_string(index=False))
print(f'\ntotal UNK cells across the bundle: {SW.UNK.sum()}')
print(f'columns carrying any UNK: {(SW.UNK > 0).sum()}')

SW.to_csv('/home/claude/p4/p5_unk_sweep.tsv', sep='\t', index=False)
json.dump(OUT, open('/home/claude/p4/p5_stage1.json', 'w'), indent=1)
print('\nwrote p5_unk_sweep.tsv + p5_stage1.json')
