"""The 19-checkpoint ladder, now MEASURED, and each checkpoint's boss roster.

SUPERSEDES the reconstruction that stood until Boss_Battles.xlsx was supplied.
The caps below are read directly from Boss_Battles.xlsx!Main rows 9-27, which
is the sheet RUN_CONFIG cited all along. The earlier reconstruction agreed on
18 of 19 caps; cp09 Pre-Trick House was interpolated at 53 and is actually 56.
Checkpoint 19 is labelled Pre-Champion in the source, not Pre-Elite4.

Why the sheet was missing before: the Phase 1/2 README declared this whole
workbook superseded because its content appeared verbatim inside
General_Documents___Locations.xlsx, on a check of "content-row counts
identical across all 11 boss sheets". The workbook has TWELVE sheets. The
twelfth is Main. A supersede check that enumerates only the sheets it already
knows about cannot detect one it does not, so the ladder was thrown away and
then reconstructed at a cost of one wrong cap.

The cap ladder itself is NOT in any supplied TSV. (superseded; see header)
"""
import pandas as pd, json

TR = pd.read_csv('/home/claude/p4/03_trainers.tsv', sep='\t', dtype=str)
SL = pd.read_csv('/home/claude/p4/03_trainer_slots.tsv', sep='\t', dtype=str)

# checkpoint -> (label, anchor trainer_ids, cap, cap_basis)
CHECKPOINTS = [
    (1,  '01_Pre-Roxanne',            ['Hoenn Leaders:ROXANNE:1'],                        15, 'measured'),
    (2,  '02_Pre-Rustboro-Rival',     ['Rivals:DAWN:16'],                                 20, 'measured'),
    (3,  '03_Pre-Brawly',             ['Hoenn Leaders:BRAWLY:13'],                        25, 'measured'),
    (4,  '04_Pre-Aqua-Museum',        ['Team Aqua:BACK TO BACK:24', 'Team Aqua:GRUNT1:24'], 30, 'measured'),
    (5,  '05_Pre-Route110-Rival',     ['Rivals:WALLY:99'],                                32, 'measured'),
    (6,  '06_Pre-Wattson',            ['Hoenn Leaders:WATTSON:26'],                       34, 'measured'),
    (7,  '07_Pre-MtChimney-Magma',    ['Team Magma:MAXIE:25'],                            44, 'measured'),
    (8,  '08_Pre-Flannery',           ['Hoenn Leaders:FLANNERY:39'],                      47, 'measured'),
    (9,  '09_Pre-TrickHouse',         [],                                                 56, 'measured'),
    (10, '10_Pre-Norman',             ['Hoenn Leaders:NORMAN:51'],                        59, 'measured'),
    (11, '11_Pre-Route119-Rival',     ['Team Aqua:GRUNT 2:37', 'Team Aqua:ADMIN MATT:37'], 64, 'measured'),
    (12, '12_Pre-Winona',             ['Hoenn Leaders:WINONA:63'],                        68, 'measured'),
    (13, '13_Pre-Dawn-Lilycove',      ['Rivals:DAWN:171'],                                71, 'measured'),
    (14, '14_Pre-Archie-AquaHideout', ['Team Aqua:ARCHIE:62'],                            74, 'measured'),
    (15, '15_Pre-Tate-and-Liza',      ['Hoenn Leaders:TATE:75', 'Hoenn Leaders:LIZA:75'], 76, 'measured'),
    (16, '16_Pre-Seafloor-Cavern',    ['Team Aqua:ARCHIE:88', 'Team Magma:MAXIE:51'],     80, 'measured'),
    (17, '17_Pre-Juan',               ['Hoenn Leaders:JUAN:87'],                          82, 'measured'),
    (18, '18_Pre-Wally-VictoryRoad',  ['Victory Road:WALLY:0'],                           84, 'measured'),
    (19, '19_Pre-Champion',             ['Elite 4:ELITE FOUR SIDNEY:13', 'Elite 4:ELITE FOUR PHOEBE:38',
                                       'Elite 4:ELITE FOUR GLACIA:63', 'Elite 4:ELITE FOUR DRAKE:1',
                                       'Elite 4:ELITE FOUR CYNTHIA:88', 'Elite 4:CHAMPION WALLACE:101',
                                       'Elite 4:CHAMPION STEVEN:101'],                    85, 'measured'),
]

known = set(TR.trainer_id)
log = []
rows = []
for num, label, anchors, cap, basis in CHECKPOINTS:
    missing = [a for a in anchors if a not in known]
    if missing:
        log.append(('checkpoint anchor not found in 03_trainers.tsv', label, missing))
    ok = [a for a in anchors if a in known]
    rows.append(dict(checkpoint=num, checkpoint_label=label, level_cap=cap,
                     cap_basis=basis, anchor_trainers=';'.join(ok) if ok else 'NONE',
                     n_anchors=len(ok)))

cp = pd.DataFrame(rows)

# ---- monotonicity + endpoint checks (the only cross-checks available) ----
caps = cp.level_cap.tolist()
mono = all(caps[i] < caps[i + 1] for i in range(len(caps) - 1))
print('checkpoints:', len(cp), '| caps 15->85:', caps[0], '->', caps[-1],
      '| strictly monotonic:', mono)
print(cp.to_string(index=False))
print()

# ---- attach anchor rosters -------------------------------------------
SL['tid'] = SL.sheet + ':' + SL.trainer + ':' + SL.header_row
tid_map = dict(zip(TR.trainer_id, TR.trainer_id))
anchor_slots = {}
for _, r in cp.iterrows():
    ids = [] if r.anchor_trainers == 'NONE' else r.anchor_trainers.split(';')
    sub = SL[SL.tid.isin(ids)]
    anchor_slots[r.checkpoint] = sub
    print(f"cp{r.checkpoint:02d} {r.checkpoint_label:26} cap={r.level_cap:2d} "
          f"slots={len(sub):3d} species={sub.species.nunique():3d} basis={r.cap_basis}")

for e in log:
    print('LOG:', e)

cp.to_csv('/home/claude/p4/checkpoints.tsv', sep='\t', index=False)
SL.to_csv('/home/claude/p4/slots_tid.tsv', sep='\t', index=False)
print('\nwrote checkpoints.tsv')
