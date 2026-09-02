# Run Configuration (locked 2026-09-01)

Everything in Phases 3–4 inherits these. Changing any of them invalidates the calcs.

## Player-side

| Setting | Value | Source |
|---|---|---|
| Difficulty mode | **NORMAL** | User |
| Minimal Grinding Mode | **OFF** | User |
| Player EVs | In play | User |
| Player IVs | In play | User |
| Level caps | Enforced, 19 checkpoints, 15 → 85 | `Measured` — Boss Battles `Main` tab |
| Run style | Standard playthrough (not nuzlocke); breeding not used | User |

Because MGM is off, the EV spreads printed on the boss rosters **do** apply — the sheet's
note ("Only copy EVs for calcing if you are not in Minimal Grinding Mode") is an
instruction to use them in this mode. 576 EV spreads are present across the rosters.

## Boss-side stats — user assumption corrected

The assumption was "boss Pokémon have perfect stats." That is the **default**, but the
rosters carry 45 explicit exceptions, and two of them change scoring materially.

| Finding | Count | Consequence |
|---|---|---|
| Total roster slots (`Ability:` lines) | **695** | `Measured` |
| Slots with no IV annotation | **650** | Treat as 31/31/31/31/31/31 (`Inferred`) |
| Slots annotated with 30s in specific stats | **36** | Hidden Power typing. 39 Hidden Power moves appear on rosters; the 30-IV lines track them |
| Slots annotated **`IVs: 0 Spe`** | **9** | **Deliberate minimum Speed** — Trick Room / Gyro Ball users |

The nine `0 Spe` slots are the ones that matter. Scoring them at 31 Spe inverts the
speed tier and produces exactly the wrong answer about what outspeeds what. Every IV
annotation in the data uses only the values 30 and 0 — never a number between — which is
the signature of deliberate authoring, not noise.

Working rule: **31 across the board unless the slot carries an `IVs:` line, in which case
that line overrides.** Confidence `Inferred`, since the sheet never states the default
explicitly; it only annotates departures from it.

## Boss levels are not all fixed

Of 695 roster slots, only **263** carry a fixed `Level: N`. Another **419** read
`Player's Highest Lv -1` or similar — they **scale to the player's party**. The remaining
13 carry neither and need manual inspection.

This changes how those fights are scored. A scaling boss cannot be beaten by
over-levelling, so for those checkpoints the level term drops out of the damage calc
entirely and the comparison becomes stats, typing, and toolkit at parity. The fixed-level
fights (gym leaders, Elite Four) behave the other way — the level cap is the binding
constraint. Phase 3 will carry a `level_mode` column (`fixed` / `scales_to_player`)
per slot so Phase 4 can treat the two kinds differently instead of averaging them.

Only **576** of 695 slots carry EV spreads, so 119 slots are either EV-less by design or
unannotated. That distinction is `Unresolved` and flagged for Phase 3.

## Fields deliberately excluded (user decision)

Dropped rather than shipped as all-`UNK` columns: EXP growth curve, base EXP yield, EV
yield, catch rate, base friendship, hatch cycles, gender ratio, egg groups.

None of these exist in any Imperium-supplied source. They were available only by borrowing
from Radical Red or PokeAPI, which could not be validated against an Imperium reading —
there is nothing to compare against. Per the user's instruction, unconfirmable figures are
omitted entirely rather than carried as inferences.

**Consequence, stated so it is not rediscovered later:** `investment_cost` in Phase 4 loses
its EV-training-time and breeding components. It will be built from the components that
remain — evolution items, TMs, held items, nature — and the README will say so. ROI figures
are therefore not comparable to a version of this analysis that had the full cost model.

**Retained from the Radical Red dex:** the evolution-method enum only (9 methods decoded
cleanly plus `4 = EVO_LEVEL` at 315/318). This is a decode key for Imperium's own integers,
not borrowed content, and each mapping is verified against Imperium's own evolution rows.

## Source demoted

`Walkthrough` sheet → **`Speculative`, not usable for checkpoint ordering.** It names
Wallace as Gym 8 (Imperium's cap ladder says Juan), omits Team Magma entirely despite a
populated Magma roster tab, and omits the Sinnoh leaders despite a populated tab. It reads
as vanilla-Emerald boilerplate rather than an Imperium document.

Checkpoint ordering will therefore be derived from the level-cap ladder plus encounter
level ranges, not from this sheet.
