// Imperium data layer -> @smogon/calc Generation adapter.
//
// Implements calc/src/data/interface.ts against imperium_layer.json so every
// calculation runs on Imperium's own base stats, types, abilities, moves and
// TYPE CHART, never the fork's bundled Radical Red data.
//
// CORRECTION (this phase): imperium_layer.json exports the Defense base stat
// under the key `df` (the fork's *compressed internal* key, seen in
// src/data/species.ts `bs: {hp, at, df, sa, sd, sp}`). The public Specie
// interface requires `def`. Passing `df` straight through leaves
// baseStats.def === undefined, which yields NaN damage rather than an error.
// Remapped explicitly below; see REMAP_STATS.

const fs = require('fs');
const path = require('path');

const NATURES = require(path.join(__dirname, 'calc/calc/dist/data/natures.js'));

function toID(s) {
  return ('' + s).toLowerCase().replace(/[^a-z0-9]+/g, '');
}

// Types the calc may probe for that Imperium's 18-type chart does not carry.
const EXTRA_TYPES = ['???', 'Stellar'];

class Store {
  constructor(map) { this.map = map; }
  get(id) { return this.map.get(id); }
  [Symbol.iterator]() { return this.map.values(); }
}

function REMAP_STATS(bs) {
  // Explicit, not a spread: an unexpected key must not silently survive.
  const out = {
    hp: bs.hp,
    atk: bs.atk,
    def: bs.def !== undefined ? bs.def : bs.df,
    spa: bs.spa,
    spd: bs.spd,
    spe: bs.spe,
  };
  for (const k of ['hp', 'atk', 'def', 'spa', 'spd', 'spe']) {
    if (typeof out[k] !== 'number' || !isFinite(out[k])) {
      throw new Error(`base stat ${k} missing/non-numeric: ${JSON.stringify(bs)}`);
    }
  }
  return out;
}

function build(layerPath, genNum) {
  const layer = JSON.parse(fs.readFileSync(layerPath, 'utf8'));

  // ---- species -------------------------------------------------------
  const species = new Map();
  const dupes = [];
  for (const [name, s] of Object.entries(layer.species)) {
    const id = toID(name);
    if (species.has(id)) dupes.push(name);
    const types = s.types.filter(t => typeof t === 'string' && t.length);
    const abilities = {};
    if (s.abilities) for (const [k, v] of Object.entries(s.abilities)) abilities[k] = v;
    species.set(id, {
      id, name, kind: 'Species',
      types: types.length ? types : ['Normal'],
      baseStats: REMAP_STATS(s.baseStats),
      weightkg: s.weightkg,
      abilities,
      internal_index: s.internal_index,
      bst: s.bst,
    });
  }

  // ---- moves ---------------------------------------------------------
  const moves = new Map();
  for (const [name, m] of Object.entries(layer.moves)) {
    moves.set(toID(name), {
      id: toID(name), name, kind: 'Move',
      basePower: m.basePower,
      type: m.type,
      category: m.category,
      accuracy: m.accuracy,
      flags: m.flags || {},
      target: m.target || 'normal',
      priority: m.priority || 0,
      secondaries: m.secondaries,
      multihit: m.multihit,
      drain: m.drain,
      recoil: m.recoil,
      move_id: m.move_id,
    });
  }

  // ---- types (Imperium's own chart) ----------------------------------
  const types = new Map();
  const order = layer.type_order;
  for (const atk of order) {
    const row = layer.types[atk];
    const eff = {};
    for (const def of order) eff[def] = row[def];
    for (const t of EXTRA_TYPES) eff[t] = 1;   // neutral, never 0/2
    types.set(toID(atk), {id: toID(atk), name: atk, kind: 'Type', effectiveness: eff});
  }
  // '???' and Stellar as ATTACKING types: fully neutral rows.
  for (const t of EXTRA_TYPES) {
    const eff = {};
    for (const def of order.concat(EXTRA_TYPES)) eff[def] = 1;
    types.set(toID(t) || '???', {id: toID(t), name: t, kind: 'Type', effectiveness: eff});
  }
  types.set('', {id: '', name: '???', kind: 'Type',
    effectiveness: Object.fromEntries(order.concat(EXTRA_TYPES).map(t => [t, 1]))});

  // ---- abilities / items ---------------------------------------------
  const abilities = new Map();
  for (const a of layer.abilities) abilities.set(toID(a), {id: toID(a), name: a, kind: 'Ability'});
  const items = new Map();
  for (const it of layer.items) items.set(toID(it), {id: toID(it), name: it, kind: 'Item'});

  // ---- natures (game-generic; reused from the fork, not Imperium-specific)
  const natures = new Map();
  for (const n of new NATURES.Natures(genNum)) natures.set(toID(n.name), n);

  return {
    num: genNum,
    species: new Store(species),
    moves: new Store(moves),
    types: new Store(types),
    abilities: new Store(abilities),
    items: new Store(items),
    natures: new Store(natures),
    _dupes: dupes,
    _counts: {
      species: species.size, moves: moves.size, types: order.length,
      abilities: abilities.size, items: items.size,
    },
  };
}

module.exports = {build, toID};
