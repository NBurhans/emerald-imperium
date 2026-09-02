import pandas as pd, json

P = '/home/claude/p4/'
B = '/mnt/user-data/outputs/emerald_imperium/'
CLOG = pd.read_pickle(P + 'p5_clog.pkl')
UNKJ = pd.read_pickle(P + 'p5_unkj.pkl')
SENSN = pd.read_pickle(P + 'p5_sens_named.pkl')
AUD = pd.read_csv(B + '07_phase5_audit.tsv', sep='\t')
SENS = pd.read_csv(P + 'p5_sensitivity.tsv', sep='\t')
V = pd.read_csv(B + '04_valuation.tsv', sep='\t')

L = []
w = L.append
w('# Phase 5 — Evaluation')
w('')
w('> Re-run against the **v2 composite** (sustain axis, defensive ceiling spread, '
  'role-aware weights, recalibrated tiers). All figures below are v2.')
w('')
w('No new dataset. Everything below was re-read from the shipped bundle on disk and '
  'attacked. The working objects that produced the bundle were deliberately not used: '
  'checking a file against the thing that wrote it proves nothing.')
w('')
w('## Headline')
w('')
w('**Seven defects found, all seven fixed.** Three were in the data as shipped, three '
  'were in my own Phase 4 code, and one was in the Phase 5 checker itself. Two of the '
  'seven changed numbers.')
w('')
w('| # | Defect | Where | Changed numbers? |')
w('|---|---|---|---|')
w('| 1 | Form tie-break took the **shortest** candidate name, so `Darmanitan` resolved to '
  'Darmanitan-**Zen** (540 BST, Fire/Psychic, 30 Atk / 140 SpA) instead of Standard '
  '(480, pure Fire, 140 / 30), and `Toxtricity` to the 621-BST **Mega** instead of the '
  '502-BST Amped form | my Phase 4 resolver | **Yes** — wrong boss at cp09, cp18, cp19 |')
w('| 2 | Three roster move names are source typos (`Hurricaine`, `Steath Rock`, '
  '`Scorching Sand`). Because the scorer filters a boss\'s attack set to moves it can '
  'find, each typo silently **removed a damaging move**, understating that boss and so '
  'overstating every species\' defense against it | source + my scorer | **Yes** — 3 bosses |')
w('| 3 | A location string sat in the species column. `Boss_Battles.xlsx` has '
  '`Rusturf Tunnel` in a **level** cell; Phase 3 took it as the species name, and '
  '**Spoink was absent from the bundle entirely** while its nature, ability and four '
  'moves sat on the mislabelled row | source + Phase 3 | No — not a checkpoint anchor |')
w('| 4 | `ceiling_item` stored only the **last** checkpoint\'s item, so the recorded '
  'build was not reproducible at 10,614 of 21,015 species-checkpoint pairs. The *scores* '
  'were correctly gated all along | my Phase 4 output schema | No — reporting only |')
w('| 5 | A colon inside a value broke the `key:value` encoding: `Type: Null` encoded as '
  '`3:Type: Null`, which decodes to key 3, value `Type`, and a stray ` Null` | my '
  'encoding | No |')
w('| 6 | Two roster `species_id` values left UNRESOLVED that Phase 4 can resolve | Phase 3 | No |')
w('| 7 | The Phase 5 decode check counted escaped colons as malformed — the **checker** '
  'was wrong, not the file | this phase | No |')
w('')
w('## Round-trip and referential integrity')
w('')
w(f'**{int((AUD.severity == "—").sum())} of {len(AUD)} checks clean.** The remaining two are '
  'known source gaps, not defects.')
w('')
w('| Check | Result |')
w('|---|---|')
w('| All 7 TSVs re-read, row counts round-trip, no ragged rows, all end with a newline | pass |')
w('| Every `*_by_checkpoint` column decodes; curve length equals `n_checkpoints_obtainable`; '
  'curve starts at `earliest_checkpoint` | 0 mismatches of 1,311 |')
w('| `lineage_form_per_checkpoint` decodes colon-escape-aware; 1,108 distinct forms including '
  '`Type: Null` | pass |')
w('| Roster `species_id` resolves to a Phase 1 row | 678/678 |')
w('| Roster moves resolve against the move table | 2,702/2,702 |')
w('| Evolution targets, movepool move ids, BST = sum of parts, stats in 1–255, '
  '`internal_index` unique | 0 failures |')
w('| **Every Phase 4 ceiling build uses only items Phase 2 confirms obtainable by that '
  'checkpoint** | **21,015/21,015** |')
w('| `n_tm_gated` matches the Phase 2 TM gates | 0 mismatches |')
w('| `tier` follows the stated thresholds; `cant_miss` follows its stated rule | 0 violations |')
w('| `06_lineage`: adjusted = raw − dead-weight penalty | 0 mismatches |')
w('| Roster abilities / held items absent from Imperium\'s own data | 1 / 8 — **Unresolved**, '
  'source gaps |')
w('')
w('## Damage re-verification — and a correction to the Phase 4 claim')
w('')
w('Phase 4 reported **14/14, 0.0% discrepancy**. That was measured on cases I chose. '
  'Re-using them would only prove they still pass, so Phase 5 drew **39 cases at random** '
  'from the actual boss rosters and obtainable pools across 14 checkpoints.')
w('')
w('**Raw result: 37/39, a 5.1% discrepancy rate.** Both divergences are the **hand '
  'verifier**, not the engine:')
w('')
w('- `Luxray` Thunder Fang → Butterfree: the engine returns 200–236, the hand formula '
  '162–192. Luxray\'s first ability is **Rivalry**, a 1.25× multiplier. Force a different '
  'ability and the engine returns 162–192 — exactly the hand value.')
w('- `Vikavolt-Totem` Acrobatics → Diancie-Mega: engine 22–26, hand 11–13. **Acrobatics '
  'doubles to 110 BP with no held item.** Give the attacker an item and the engine returns '
  '11–13 — exactly the hand value.')
w('')
w('The hand implementation models level, stats, base power, STAB and the type chart, and '
  'deliberately nothing else. **Engine-vs-formula agreement is 39/39 once both are given '
  'the same information.** The honest statement of the Phase 4 result is therefore: the '
  'engine reproduces the Gen-3+ damage formula exactly on every case where no ability or '
  'item modifier applies, and the curated 14 happened to be all such cases.')
w('')
w('## Recomputed validations')
w('')
w('| Validation | Result |')
w('|---|---|')
w('| BST correlation, floor | r = 0.366, n = 19,418 — **pass** (threshold ~0.7) |')
w('| BST correlation, ceiling | r = 0.476, n = 20,797 — **pass** |')
w(f'| Tier distribution | ' +
  ' / '.join(f'{k} {v}' for k, v in
             V.tier.value_counts().reindex(['S+', 'S', 'A', 'B', 'C', 'D', 'F']).items()) + ' |')
w(f'| `cant_miss` | {int((V.cant_miss == True).sum())} species |')
w(f'| `tier_fragile` | {int((V.tier_fragile == True).sum())} species within 0.002 of a threshold |')
w('')
w('## Sensitivity — the assumptions that would most change the rankings')
w('')
w('Ordered by how many species change tier if the assumption is wrong. Named species are '
  'the ones whose tier actually depends on it.')
w('')
w('| # | Assumption | If wrong | Species | Named |')
w('|---|---|---|---|---|')
for r in SENSN.itertuples():
    w(f'| {r.rank} | {r.assumption} | {r.if_wrong} | {r.species_affected} | {r.named} |')
w('')
w('**The one worth acting on first is #4.** `Rivalry` and `Cute Charm` apply 1.25× or '
  '0.75× depending on whether attacker and defender share a gender — a 67% swing. '
  '`gender_ratio` was one of the eight fields dropped in Phase 1 as unconfirmable, so the '
  'engine default stands unchallenged on 20 obtainable species including Haxorus, Luxray, '
  'Clefable and Lopunny. This is the clearest case where a field dropped for being '
  'unverifiable turned out to have a measurable downstream cost.')
w('')
w('Full weight-perturbation table:')
w('')
w(SENS.to_markdown(index=False))
w('')
w('## Missing-data sweep')
w('')
w(f'**{int(UNKJ.unk.sum()):,} `UNK` cells across the bundle, in {len(UNKJ)} columns.** '
  'Each judged for whether it is recoverable from the supplied data.')
w('')
w(UNKJ.to_markdown(index=False))
w('')
w('## Consolidated Data Integrity Log — all phases')
w('')
w(CLOG.to_markdown(index=False))
w('')
w('## What Phase 6 should know')
w('')
w('- `tier` is not safe to display alone for the 76 species where `tier_fragile` is TRUE. '
  'Show `tier_edge_distance` beside it, or band those species visually.')
w('- `ceiling_item_by_checkpoint` is the reproducible build column. '
  '`ceiling_item_at_last_cp` is kept for convenience and is only correct at the last '
  'checkpoint a species is scored for.')
w('- Values in `key:value` columns escape a literal colon as `\\:`. Split on the first '
  '**unescaped** colon. Two species names need this: `Type: Null` and its lineage.')
w('- 223 of 1,534 forms have no derivable acquisition route and carry '
  '`earliest_checkpoint = UNK`. They are absent from `04_valuation.tsv` entirely, which '
  'has 1,311 rows.')
w('- Every damage figure is `Inferred`, not `Measured`, because the damage-formula '
  'generation is pinned on evidence but unconfirmed.')

open(B + 'PHASE5_EVALUATION.md', 'w', encoding='utf-8').write('\n'.join(L) + '\n')
print('wrote PHASE5_EVALUATION.md')
print('sections:', sum(1 for x in L if x.startswith('## ')))
