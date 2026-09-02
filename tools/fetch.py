#!/usr/bin/env python3
"""Pull the Emerald Imperium working set out of GitHub into a local folder.

    python3 tools/fetch.py                      # data + docs (the usual case)
    python3 tools/fetch.py --all                # everything including the app
    python3 tools/fetch.py --set pipeline       # one named set
    python3 tools/fetch.py --user X --repo Y    # if the repo moved

Written for a fresh session that has network access to raw.githubusercontent.com
but no local copy. Verifies every file against CHECKSUMS.txt and says loudly if
anything differs, because a silently truncated download is the failure mode that
has actually bitten this project before.
"""
import argparse, hashlib, os, sys, urllib.request, urllib.error

DEFAULT_USER = 'YOUR_GITHUB_USERNAME'
DEFAULT_REPO = 'emerald-imperium'
DEFAULT_REF = 'main'

SETS = {
    'data': ['data/01_species.tsv', 'data/02_world.tsv', 'data/03_trainers.tsv',
             'data/03_trainer_slots.tsv', 'data/04_valuation.tsv',
             'data/05_checkpoints.tsv', 'data/06_lineage.tsv',
             'data/07_phase5_audit.tsv', 'data/imperium_layer.json'],
    'docs': ['docs/00_BUNDLE_README.md', 'docs/PHASE5_EVALUATION.md',
             'docs/PHASE6_NOTES.md', 'docs/RUN_CONFIG.md', 'docs/PROJECT_PROMPT.md'],
    'app': ['index.html', 'app/emerald_imperium_survey.html',
            'app/emerald_imperium_sprites.js'],
    'pipeline': [],      # filled from CHECKSUMS.txt
    'workbook': ['workbook/Phase4_Valuation.xlsx'],
}


def raw(user, repo, ref, path):
    return f'https://raw.githubusercontent.com/{user}/{repo}/{ref}/{path}'


def get(url, timeout=60):
    req = urllib.request.Request(url, headers={'User-Agent': 'emerald-imperium-fetch'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--user', default=DEFAULT_USER)
    ap.add_argument('--repo', default=DEFAULT_REPO)
    ap.add_argument('--ref', default=DEFAULT_REF)
    ap.add_argument('--out', default='./imperium')
    ap.add_argument('--set', action='append', dest='sets')
    ap.add_argument('--all', action='store_true')
    a = ap.parse_args()

    if a.user == DEFAULT_USER:
        sys.exit('Set --user, or edit DEFAULT_USER at the top of this file.')

    try:
        sums = get(raw(a.user, a.repo, a.ref, 'CHECKSUMS.txt')).decode()
    except urllib.error.HTTPError as e:
        sys.exit(f'Could not read CHECKSUMS.txt ({e.code}). Check --user/--repo/--ref, '
                 'and that the repo is public.')
    want = {}
    for line in sums.splitlines():
        if '  ' in line and not line.startswith('#'):
            h, p = line.split('  ', 1)
            want[p.strip()] = h
    SETS['pipeline'] = [p for p in want if p.startswith('pipeline/')]

    if a.all:
        paths = sorted(want)
    else:
        names = a.sets or ['data', 'docs']
        paths = [p for n in names for p in SETS.get(n, [])]
        unknown = [n for n in names if n not in SETS]
        if unknown:
            sys.exit(f'Unknown set(s) {unknown}. Choose from {sorted(SETS)}.')

    os.makedirs(a.out, exist_ok=True)
    ok = bad = 0
    for p in paths:
        dest = os.path.join(a.out, p)
        os.makedirs(os.path.dirname(dest) or '.', exist_ok=True)
        try:
            data = get(raw(a.user, a.repo, a.ref, p))
        except Exception as e:
            print(f'  [FAIL] {p}  {e}'); bad += 1; continue
        h = hashlib.sha256(data).hexdigest()
        if p in want and h != want[p]:
            print(f'  [HASH] {p}  got {h[:12]} expected {want[p][:12]} — NOT WRITTEN')
            bad += 1; continue
        open(dest, 'wb').write(data)
        print(f'  [OK  ] {p}  {len(data):,} bytes')
        ok += 1
    print(f'\n{ok} file(s) verified into {a.out}' + (f', {bad} FAILED' if bad else ''))
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
