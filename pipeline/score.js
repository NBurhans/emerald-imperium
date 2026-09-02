// Per-checkpoint scoring for every obtainable species form.
//
// All damage, KO-range and survivability figures come from @smogon/calc
// (RadicalRedShowdown fork, HEAD 7f35400) driven by the Imperium data layer.
// The whole loop runs in-process: marshalling ~2M individual calcs through a
// pipe would dominate the runtime.
//
// Two builds are scored per species per checkpoint:
//   FLOOR   neutral nature, 0 EVs, 31 IVs, first ability, no item,
//           level-up moves learned at or below the level cap.
//   CEILING best nature, 252/252 EVs on the two stats the role wants,
//           best of the species' abilities, best held item obtainable by
//           this checkpoint (passed in), level-up + TM + egg moves.
//
// Boss side follows RUN_CONFIG: 31 IVs unless the slot annotates otherwise
// (the nine 0-Spe Trick Room slots are honoured), roster EVs applied because
// Minimal Grinding Mode is OFF, and scaling levels set to the cap (parity).

const fs = require('fs');
const path = require('path');
const {build} = require(path.join(__dirname, 'imperium_gen.js'));
const A = require(path.join(__dirname, 'calc/calc/dist/adaptable.js'));

const IN = JSON.parse(fs.readFileSync(path.join(__dirname, 'scoring_input.json'), 'utf8'));
const gen = build(path.join(__dirname, 'imperium_layer.json'), 9);
const MOVES = IN.moves, TOOLS = IN.tools, SPECIES = IN.species;
const TYPES = IN.types, TYPE_ORDER = IN.type_order;

const NEUTRAL = 'Serious';
const PLUS_ATK = 'Adamant', PLUS_SPA = 'Modest', PLUS_SPE_PHYS = 'Jolly', PLUS_SPE_SPEC = 'Timid';
const FULL_IV = {hp: 31, atk: 31, def: 31, spa: 31, spd: 31, spe: 31};

const errors = [];

function movesUpTo(sp, cap) {
  const out = new Set();
  for (const [nm, lv] of sp.levelup) if (lv <= cap) out.add(nm);
  return [...out];
}

// Damaging-move shortlist: the calc is exact but not free, so for each species
// keep the strongest move per (type, category). That is the set a player would
// ever actually pick from; weaker same-type same-category moves cannot beat it
// on damage, so nothing is lost from the MAX we take per target.
function shortlist(names) {
  const best = new Map();
  for (const nm of names) {
    const m = MOVES[nm];
    if (!m || !m.basePower || m.category === 'Status') continue;
    const k = m.type + '|' + m.category;
    const cur = best.get(k);
    if (!cur || MOVES[cur].basePower < m.basePower) best.set(k, nm);
  }
  return [...best.values()];
}

function mkPoke(species, level, opts) {
  return new A.Pokemon(gen, species, {
    level,
    nature: opts.nature || NEUTRAL,
    evs: opts.evs || {},
    ivs: opts.ivs || FULL_IV,
    ability: opts.ability || undefined,
    item: opts.item || undefined,
    boosts: {},
  });
}

const FIELD = new A.Field({});

function dmgFrac(atk, def, moveName) {
  const mv = new A.Move(gen, moveName);
  const r = A.calculate(gen, atk, def, mv, FIELD);
  const d = r.damage;
  const rolls = Array.isArray(d) ? (Array.isArray(d[0]) ? d.flat() : d) : [d];
  const hp = def.maxHP();
  let lo = Infinity, hi = -Infinity;
  for (const x of rolls) { if (x < lo) lo = x; if (x > hi) hi = x; }
  return {lo: lo / hp, hi: hi / hp};
}

// ---- typing helpers ---------------------------------------------------
function effOf(atkType, defTypes) {
  let m = 1;
  const row = TYPES[atkType];
  if (!row) return 1;
  for (const t of defTypes) if (row[t] !== undefined) m *= row[t];
  return m;
}

// ---- toolkit ----------------------------------------------------------
const TOOL_CATS = ['recovery', 'drain', 'hazard', 'hazard_removal', 'pivot', 'screens',
                   'status', 'cleric', 'speed_control', 'trapping', 'weather',
                   'terrain', 'priority', 'setup'];
function toolsOf(moveNames) {
  const s = new Set(moveNames);
  const out = {};
  for (const c of TOOL_CATS) out[c] = TOOLS[c].filter(m => s.has(m));
  return out;
}

function hasEnabler(abilities, role) {
  const list = TOOLS.enabler_abilities[role] || [];
  return abilities.some(a => list.includes(a));
}

// ---- score one species at one checkpoint ------------------------------
function scoreOne(spName, cp, threat, build) {
  const sp = SPECIES[spName];
  const cap = cp.cap;
  const learned = movesUpTo(sp, cap);
  // CEILING is gated by Phase 2: only TMs whose earliest_gate is at or before
  // this checkpoint count. Egg moves are included -- RUN_CONFIG says breeding
  // is not used in this run, so they are charged in investment_cost as
  // unreachable rather than being silently free. See ceiling_gate below.
  const tmOK = build === 'floor' ? [] : sp.tm.filter(m => cp.tmSet.has(m));
  const pool = build === 'floor'
    ? learned
    : [...new Set([...learned, ...tmOK, ...sp.egg])];
  const dmgMoves = shortlist(pool);
  const ability = sp.abilities.length ? sp.abilities[0] : undefined;

  const st = gen.species.get(spName.toLowerCase().replace(/[^a-z0-9]+/g, ''));
  if (!st) { errors.push(`no layer species ${spName}`); return null; }
  const bs = st.baseStats;
  const physOff = bs.atk >= bs.spa;

  let nature = NEUTRAL, evs = {}, item, useAbility = ability;
  // A wall scored with 252 Atk / 252 Spe and a speed nature is not the thing the
  // player would field. 'ceilingD' is the same ceiling with a DEFENSIVE spread:
  // 252 HP plus the better defence, a bulk-raising nature, and Leftovers if
  // Phase 2 has it. Both spreads are scored; the valuation keeps whichever wins,
  // so a defensive build can only ever help a species, never cost it.
  if (build === 'ceilingD') {
    const physSide = bs.def >= bs.spd;
    nature = physSide ? 'Bold' : 'Calm';
    evs = physSide ? {hp: 252, def: 252, spd: 4} : {hp: 252, spd: 252, def: 4};
    for (const role of ['wall', 'pivot', 'sweeper', 'wallbreaker']) {
      const hit = sp.abilities.find(a => (TOOLS.enabler_abilities[role] || []).includes(a));
      if (hit) { useAbility = hit; break; }
    }
    item = ['Leftovers', 'Eviolite', 'Rocky Helmet'].find(i => cp.itemSet.has(i));
  }
  if (build === 'ceiling') {
    nature = physOff ? PLUS_ATK : PLUS_SPA;
    evs = physOff ? {atk: 252, spe: 252, hp: 4} : {spa: 252, spe: 252, hp: 4};
    // best ability = the first that enables ANY role, else ability 1
    for (const role of ['sweeper', 'wallbreaker', 'wall', 'pivot', 'revenge']) {
      const hit = sp.abilities.find(a => (TOOLS.enabler_abilities[role] || []).includes(a));
      if (hit) { useAbility = hit; break; }
    }
    // best held item AMONG THOSE PHASE 2 SAYS ARE OBTAINABLE BY NOW
    const want = physOff ? ['Choice Band', 'Expert Belt', 'Leftovers']
                         : ['Choice Specs', 'Expert Belt', 'Leftovers'];
    item = want.find(i => cp.itemSet.has(i));
  }
  const me = mkPoke(spName, cap, {nature, evs, ability: useAbility, item});

  // ---- OFFENSE ----
  let offNum = 0, offDen = 0, ohko = 0, twohko = 0;
  const perSlot = [];
  for (let i = 0; i < threat.mons.length; i++) {
    const t = threat.mons[i];
    const w = threat.weight[i];
    let best = {lo: 0, hi: 0}, bestMove = null;
    for (const mv of dmgMoves) {
      const d = dmgFrac(me, t, mv);
      if (d.hi > best.hi) { best = d; bestMove = mv; }
    }
    const isOHKO = best.lo >= 1;
    const is2HKO = best.lo * 2 >= 1;
    if (isOHKO) ohko++;
    if (is2HKO) twohko++;
    offNum += w * (isOHKO ? 1 : (is2HKO ? 0.75 : Math.min(best.hi * 1.5, 0.5)));
    offDen += w;
    perSlot.push({t: threat.names[i], mv: bestMove, lo: +best.lo.toFixed(3), hi: +best.hi.toFixed(3)});
  }

  // ---- STALL / SUSTAIN MODEL ----
  // The five axes are all single-hit. This adds the turn dimension the old
  // defense axis could not see: how long the species lasts against the boss's
  // best move once its own recovery is counted, against how long it needs to
  // KO. Deliberately a proxy, not a battle engine -- no PP, no AI switching, no
  // status on the boss beyond Toxic chip, no crits.
  const poolSet = new Set(pool);
  const hasRecovery = TOOLS.recovery.some(m => poolSet.has(m));
  const hasScreens = TOOLS.screens.filter(m => poolSet.has(m)).length > 0;
  const hasToxic = poolSet.has('Toxic') || poolSet.has('Toxic Spikes');
  const hazards = TOOLS.hazard.filter(m => poolSet.has(m));
  const regen = sp.abilities.includes('Regenerator');
  // heal per turn as a fraction of max HP. Reliable recovery restores ~50% but
  // costs the turn, so it nets ~25% per turn over a heal/attack cycle.
  let healPerTurn = 0;
  if (hasRecovery) healPerTurn += 0.25;
  if (regen) healPerTurn += 0.11;                 // a third of max HP per switch, amortised
  if (item === 'Leftovers') healPerTurn += 0.0625;
  // hazard chip on the boss side: one-time, applied to what the species must chew
  // through. Stealth Rock averages ~12.5% across a roster, Spikes ~8%.
  let hazChip = 0;
  if (hazards.includes('Stealth Rock')) hazChip += 0.125;
  if (hazards.includes('Spikes')) hazChip += 0.08;
  if (hazards.includes('Toxic Spikes')) hazChip += 0.06;
  hazChip = Math.min(hazChip, 0.25);
  const screenMult = hasScreens ? 0.67 : 1;

  // ---- DEFENSE ----
  let defNum = 0, defDen = 0, surv1 = 0, surv2 = 0, nHit = 0;
  let duelWins = 0, tsSum = 0;
  const seq = [];
  for (let i = 0; i < threat.mons.length; i++) {
    const t = threat.mons[i], w = threat.weight[i];
    let worst = 0;
    for (const mv of threat.moves[i]) {
      const d = dmgFrac(t, me, mv);
      if (d.hi > worst) worst = d.hi;
    }
    nHit++;
    const s1 = worst < 1, s2 = worst * 2 < 1;
    if (s1) surv1++;
    if (s2) surv2++;
    defNum += w * (s2 ? 1 : (s1 ? 0.6 : Math.max(0, 0.4 * (1 - Math.min(worst, 2) / 2))));
    defDen += w;

    // per-slot bookkeeping for the sequential pass below
    const best = perSlot[i] ? perSlot[i].lo : 0;
    const tgtTypes = t.species && t.species.types ? t.species.types : [];
    const poisonable = !tgtTypes.includes('Steel') && !tgtTypes.includes('Poison');
    const toxPerTurn = (hasToxic && poisonable) ? 0.0938 : 0;   // avg over ~4 turns
    const need = Math.max(0.05, 1 - hazChip);
    const tk = (best + toxPerTurn) <= 0 ? 99 : Math.min(99, need / (best + toxPerTurn));
    const inPerTurn = worst * screenMult;
    const net = inPerTurn - healPerTurn;
    const ts = net <= 0 ? 99 : Math.min(99, 1 / net);
    tsSum += ts;
    if (ts >= tk) duelWins++;
    // counterfactual: the same species with NO sustain kit. Subtracting this
    // from the real figure isolates what the KIT contributes, which is the
    // thing the axis is supposed to measure. Raw sustain correlated 0.809 with
    // BST -- it was measuring size, since both turns-to-KO and damage-taken
    // scale with stats. The delta does not.
    const tkBare = best <= 0 ? 99 : Math.min(99, 1 / best);
    seq.push({tk, inPerTurn, w, tr: threat.trainerOf[i], tkBare, inBare: worst});
  }

  // ---- SUSTAIN (sweep depth on one lifebar) ----
  // The per-slot version of this saturated: almost everything beats an
  // individual slot, so the axis read 0.82-0.99 for wall and glass cannon alike
  // and discriminated nothing. This runs the roster SEQUENTIALLY on a single
  // lifebar instead. Damage taken accumulates across fights; healing pays it
  // back per turn. How deep the species gets before fainting is the number that
  // separates a wall from an attacker who merely survives one hit.
  // Roster order, as the fight presents it. Sorting hardest-first was a
  // worst-case ordering that zeroed several genuine walls on their first slot;
  // the player does not choose to lead into the ace.
  // The lifebar resets at every TRAINER boundary, because the player heals
  // between fights. A checkpoint like the Elite Four is seven separate rosters,
  // not one 36-slot marathon; carrying damage across all of them scored every
  // species 1-3 and discriminated nothing, the mirror of the saturation problem
  // the per-slot version had. Within a trainer, damage accumulates.
  function walk(useKit) {
    let hp = 1.0, dep = 0, cur = null;
    for (const x of seq) {
      if (x.tr !== cur) { cur = x.tr; hp = 1.0; }
      const tk = useKit ? x.tk : x.tkBare;
      const inc = useKit ? x.inPerTurn : x.inBare;
      const heal = useKit ? healPerTurn : 0;
      const loss = Math.max(0, tk * inc - tk * heal);
      if (hp - loss <= 0) continue;        // faints here; next trainer is a fresh bar
      hp -= loss;
      dep++;
    }
    return dep;
  }
  const depth = walk(true), depthBare = walk(false);
  const sustain = depth / Math.max(1, seq.length);
  const sustainBare = depthBare / Math.max(1, seq.length);
  const sustainKit = sustain - sustainBare;

  // ---- SPEED ----
  const meFast = mkPoke(spName, cap, {
    nature: physOff ? PLUS_SPE_PHYS : PLUS_SPE_SPEC, evs: {spe: 252}, ability: useAbility});
  let outNeutral = 0, outFast = 0;
  for (const t of threat.mons) {
    if (me.stats.spe > t.stats.spe) outNeutral++;
    if (meFast.stats.spe > t.stats.spe) outFast++;
  }
  const nT = threat.mons.length || 1;

  // ---- TYPING (against THIS boss's actual attacking types) ----
  let tsum = 0, tw = 0;
  for (const [ty, cnt] of Object.entries(threat.typeFreq)) {
    const e = effOf(ty, st.types);
    tsum += cnt * e; tw += cnt;
  }
  const meanEff = tw ? tsum / tw : 1;
  const typingScore = Math.max(0, Math.min(1, (2 - meanEff) / 2));

  // STAB quality on the side the higher attacking stat sits on
  const stabSide = st.types.some(ty => dmgMoves.some(
    m => MOVES[m].type === ty && MOVES[m].category === (physOff ? 'Physical' : 'Special')));

  // ---- UTILITY ----
  const tk = toolsOf(pool);
  const utilCats = TOOL_CATS.filter(c => c !== 'setup' && tk[c].length > 0).length;
  const utility = utilCats / (TOOL_CATS.length - 1);

  return {
    species: spName, checkpoint: cp.checkpoint, build,
    level: cap, nature, ability: useAbility || 'NONE', item: item || 'NONE',
    // both ceiling spreads draw on the same gated TM pool; testing only for
    // 'ceiling' zeroed this on every ceilingD row, which zeroed the TM component
    // of investment_cost for the 568 species whose defensive spread wins.
    n_tm_gated: build === 'floor' ? 0 : sp.tm.filter(m => cp.tmSet.has(m)).length,
    n_tm_total: sp.tm.length, n_egg: sp.egg.length,
    n_damaging_moves: dmgMoves.length, n_moves_pool: pool.length,
    offense: offDen ? +(offNum / offDen).toFixed(4) : null,
    ohko_frac: +(ohko / nT).toFixed(4), twohko_frac: +(twohko / nT).toFixed(4),
    defense: defDen ? +(defNum / defDen).toFixed(4) : null,
    sustain: +sustain.toFixed(4), sustain_bare: +sustainBare.toFixed(4),
    sustain_kit: +sustainKit.toFixed(4), sweep_depth: depth,
    duel_win_frac: +(duelWins / nT).toFixed(4),
    turns_survived_mean: +(tsSum / Math.max(1, nHit)).toFixed(2),
    has_recovery: hasRecovery, has_screens: hasScreens, regen: regen,
    hazard_chip: +hazChip.toFixed(3), heal_per_turn: +healPerTurn.toFixed(4),
    n_hazards: hazards.length,
    survive1_frac: +(surv1 / nT).toFixed(4), survive2_frac: +(surv2 / nT).toFixed(4),
    speed_neutral: +(outNeutral / nT).toFixed(4), speed_plus: +(outFast / nT).toFixed(4),
    typing: +typingScore.toFixed(4), mean_incoming_eff: +meanEff.toFixed(3),
    stab_on_main_side: stabSide,
    utility: +utility.toFixed(4),
    tools: Object.fromEntries(TOOL_CATS.map(c => [c, tk[c].length])),
    tool_names: Object.fromEntries(TOOL_CATS.map(c => [c, tk[c]])),
    stats: me.stats, base: bs, types: st.types, bst: sp.bst,
    best_vs: perSlot,
  };
}

// ---- main -------------------------------------------------------------
const out = [];
const t0 = Date.now();
for (const cp of IN.checkpoints) {
  // build the threat side once per checkpoint
  const mons = [], names = [], moveSets = [], weight = [], trainerOf = [];
  const typeFreq = {};
  for (const s of cp.slots) {
    let p;
    try {
      p = mkPoke(s.species, s.level, {
        nature: s.nature, evs: s.evs, ivs: s.ivs,
        ability: s.ability || undefined, item: s.item || undefined});
    } catch (e) { errors.push(`slot ${s.species}: ${e.message}`); continue; }
    const dmg = s.moves.filter(m => MOVES[m] && MOVES[m].basePower > 0
                                    && MOVES[m].category !== 'Status');
    mons.push(p); names.push(s.species); moveSets.push(dmg.length ? dmg : ['Struggle']);
    trainerOf.push(s.trainer);
    for (const m of dmg) {
      const ty = MOVES[m] ? MOVES[m].type : null;
      if (ty) typeFreq[ty] = (typeFreq[ty] || 0) + 1;
    }
  }
  // threat weight: how dangerous this slot is, from its own offensive stat and
  // level, normalised within the checkpoint. A boss's ace should count more
  // than its lead filler.
  const raw = mons.map(p => Math.max(p.stats.atk, p.stats.spa) * p.level);
  const mx = Math.max(...raw, 1);
  for (const r of raw) weight.push(0.5 + 0.5 * (r / mx));

  const threat = {mons, names, moves: moveSets, weight, typeFreq, trainerOf};
  cp.tmSet = new Set(cp.tms_available);
  cp.itemSet = new Set(cp.items_available);

  for (const spName of cp.pool) {
    for (const b of ['floor', 'ceiling', 'ceilingD']) {
      const r = scoreOne(spName, cp, threat, b);
      if (r) out.push(r);
    }
  }
  process.stderr.write(`cp${String(cp.checkpoint).padStart(2, '0')} `
    + `slots=${mons.length} pool=${cp.pool.length} rows=${out.length} `
    + `${((Date.now() - t0) / 1000).toFixed(0)}s\n`);
}

fs.writeFileSync(path.join(__dirname, 'scores_raw.json'), JSON.stringify(out));
fs.writeFileSync(path.join(__dirname, 'scorer_errors.json'), JSON.stringify(errors, null, 1));
process.stderr.write(`\ndone: ${out.length} rows, ${errors.length} errors, `
  + `${((Date.now() - t0) / 1000).toFixed(0)}s\n`);
