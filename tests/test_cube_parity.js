/*
 * test_cube_parity.js - verifies market_cube.js matches the Python vector
 * bit-for-bit. Run: node tests/test_cube_parity.js
 * (requires tests/cube_vector.json, produced by test_cube_parity.py)
 */
'use strict';
var path = require('path');
var fs = require('fs');

var ROOT = path.dirname(__dirname);
var MC = require(path.join(ROOT, 'market_cube.js'));
var VECTOR = path.join(__dirname, 'cube_vector.json');

if (!fs.existsSync(VECTOR)) {
  console.error('missing ' + VECTOR + ' -- run python tests/test_cube_parity.py first');
  process.exit(2);
}

var v = JSON.parse(fs.readFileSync(VECTOR, 'utf-8'));
var fails = 0;
var checks = 0;

function eq(label, got, want) {
  checks++;
  if (got !== want) {
    fails++;
    if (fails <= 20) console.error('MISMATCH ' + label + ' got=' + got + ' want=' + want);
  }
}

// low-level
var ll = v.low_level;
[0, 1, 2, 42, 65535, 0xFFFFFFFF, 123456789].forEach(function (x, i) {
  eq('h32(' + x + ')', MC.h32(x), ll.h32[i]);
});
eq('mix123', MC.mix(1, 2, 3), ll.mix[0]);
eq('mix99999', MC.mix(9, 9, 9, 9, 9), ll.mix[1]);
eq('mix0', MC.mix(0), ll.mix[2]);
eq('mixFF1', MC.mix(0xFFFFFFFF, 1), ll.mix[3]);
Object.keys(ll.strSeed).forEach(function (s) {
  eq('strSeed(' + s + ')', MC.strSeed(s), ll.strSeed[s]);
});
[0, 100, 16384, 32768, 49152, 65535, 130000].forEach(function (a, i) {
  eq('isin(' + a + ')', MC.isin(a), ll.isin[i]);
});
[0, 90, 179, 180, 5000].forEach(function (t, i) {
  eq('valueNoise(' + t + ')', MC.valueNoise(7, t, 180), ll.valueNoise[i]);
});

// full cells
var FN = { price: MC.price, spread: MC.spread, volume: MC.volume, robot: MC.robotTarget };
v.cells.forEach(function (row) {
  var sym = row[0], t = row[1], name = row[2], want = row[3];
  var got;
  if (name === 'boss_hp') got = MC.bossHp(3, t);
  else if (name === 'capacity') got = MC.capacity(42, t);
  else if (name === 'capital') got = MC.capital(1042, t);
  else got = FN[name](sym, t);
  eq(name + '(' + sym + ',' + t + ')', got, want);
});

if (v.capital_series) {
  var p = v.capital_series;
  var cs = MC.capitalSeries(p.uid, p.now_nw, p.t_now, p.step, p.n);
  for (var k = 0; k < p.n; k++) eq('capital_series[' + k + ']', cs[k], p.values[k]);
}

if (v.welfare) {
  var wf = v.welfare;
  wf.market_trend.forEach(function (r) {
    eq('market_trend(' + r[0] + ')', MC.marketTrend(r[0]), r[1]);
  });
  wf.sector_trend.forEach(function (r) {
    eq('sector_trend(' + r[0] + ',' + r[1] + ')', MC.sectorTrend(r[0], r[1]), r[2]);
  });
  wf.living_tier.forEach(function (r) {
    eq('living_tier(' + r[0] + ',' + r[1] + ')', MC.livingTier(r[0], r[1]), r[2]);
  });
  wf.welfare_floor.forEach(function (r) {
    eq('welfare_floor(' + r[0] + ',' + r[1] + ')', MC.welfareFloor(r[0], r[1]), r[2]);
  });
  wf.mishap.forEach(function (r) {
    eq('mishap(' + r[0] + ',' + r[1] + ')', MC.mishap(r[0], r[1]), r[2]);
  });
  wf.welfare.forEach(function (r) {
    eq('welfare(' + r[0] + ',' + r[1] + ')', MC.welfare(r[0], r[1]), r[2]);
  });
}

if (v.welfare_explain) {
  var we = v.welfare_explain, gx = MC.welfareExplain(we.uid, we.t);
  Object.keys(we.value).forEach(function (key) {
    eq('explain.' + key, gx[key], we.value[key]);
  });
}

if (v.welfare_candle) {
  var wc = v.welfare_candle, gc = MC.welfareCandle(wc.uid, null, wc.t);
  Object.keys(wc.value).forEach(function (key) {
    eq('candle.' + key, gc[key], wc.value[key]);
  });
}

if (v.welfare_quotes) {
  var wq = v.welfare_quotes, gq = MC.welfareQuotes(wq.uid, wq.t, wq.n);
  for (var qi = 0; qi < wq.value.length; qi++) {
    var want = wq.value[qi], got = gq[qi];
    Object.keys(want).forEach(function (key) {
      eq('quote[' + qi + '].' + key, got[key], want[key]);
    });
  }
}

if (fails === 0) {
  console.log('cube parity OK: ' + checks + ' checks, Python == JS bit-for-bit');
  process.exit(0);
} else {
  console.error('cube parity FAILED: ' + fails + '/' + checks + ' mismatches');
  process.exit(1);
}
