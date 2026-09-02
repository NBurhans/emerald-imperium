// Batch damage-calc runner over the Imperium data layer.
// stdin:  JSON array of jobs (see makeJob below for the full input set)
// stdout: JSON array of results, each carrying its inputs back so any number
//         is reproducible. A damage range without its inputs is not evidence.

const path = require('path');
const {build} = require(path.join(__dirname, 'imperium_gen.js'));
const A = require(path.join(__dirname, 'calc/calc/dist/adaptable.js'));

const GEN_NUM = parseInt(process.env.IMP_GEN || '9', 10);
const gen = build(path.join(__dirname, 'imperium_layer.json'), GEN_NUM);

function mkPoke(spec) {
  return new A.Pokemon(gen, spec.species, {
    level: spec.level,
    nature: spec.nature || 'Serious',
    evs: spec.evs || {},
    ivs: spec.ivs || {hp: 31, atk: 31, def: 31, spa: 31, spd: 31, spe: 31},
    ability: spec.ability || undefined,
    item: spec.item || undefined,
    boosts: spec.boosts || {},
    status: spec.status || '',
    teraType: undefined,
  });
}

function run(job) {
  const out = {id: job.id, inputs: job};
  try {
    const atk = mkPoke(job.attacker);
    const def = mkPoke(job.defender);
    const move = new A.Move(gen, job.move, {
      useMax: false,
      isCrit: !!job.isCrit,
    });
    const field = new A.Field(job.field || {});
    const res = A.calculate(gen, atk, def, move, field);
    const dmg = res.damage;
    const rolls = Array.isArray(dmg) ? (Array.isArray(dmg[0]) ? dmg.flat() : dmg) : [dmg];
    const maxHP = def.maxHP();
    out.rolls = rolls;
    out.min = Math.min(...rolls);
    out.max = Math.max(...rolls);
    out.defender_maxhp = maxHP;
    out.pct_min = out.min / maxHP;
    out.pct_max = out.max / maxHP;
    out.attacker_stats = atk.stats;
    out.defender_stats = def.stats;
    out.move_bp = move.bp;
    out.move_type = move.type;
    out.move_category = move.category;
    try { out.desc = res.desc(); } catch (e) { out.desc = null; }
    out.ok = true;
  } catch (e) {
    out.ok = false;
    out.error = String(e && e.message ? e.message : e);
  }
  return out;
}

let buf = '';
process.stdin.on('data', d => { buf += d; });
process.stdin.on('end', () => {
  const jobs = JSON.parse(buf);
  const results = jobs.map(run);
  process.stdout.write(JSON.stringify(results));
});
