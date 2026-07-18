/*
 * market_cube.js - JS twin of market_cube.py (see docs/CUBE.md).
 *
 * MUST produce bit-for-bit identical integers to the Python core.
 * Rules that guarantee parity:
 *   - 32-bit hashing uses Math.imul + (x >>> 0)  (never plain * for hashes).
 *   - Big values (price/cap up to ~1e12) stay < 2^53, so plain * / Math.floor
 *     are exact; we use Math.floor(x / 2**n) instead of >> for those.
 *   - SIN_TABLE is the SAME hard-coded array as Python.
 *
 * Works both in the browser (window.MarketCube) and Node (module.exports).
 */
(function (root) {
  'use strict';

  var MASK = 0xFFFFFFFF;

  function u32(x) { return x >>> 0; }

  function imul(a, b) { return Math.imul(a | 0, b | 0) >>> 0; }

  function h32(x) {
    x = u32(x);
    x ^= x >>> 16;
    x = imul(x, 0x7FEB352D);
    x ^= x >>> 15;
    x = imul(x, 0x846CA68B);
    x ^= x >>> 16;
    return u32(x);
  }

  function mix() {
    var acc = 0x9E3779B1;
    for (var i = 0; i < arguments.length; i++) {
      acc = u32(acc + u32(arguments[i] >>> 0));
      acc = h32(acc);
    }
    return acc;
  }

  function strSeed(s) {
    var acc = 0x811C9DC5;
    var bytes = unescape(encodeURIComponent(s)); // UTF-8 bytes
    for (var i = 0; i < bytes.length; i++) {
      acc = u32(acc ^ bytes.charCodeAt(i));
      acc = imul(acc, 0x01000193);
    }
    return h32(acc);
  }

  var SIN_TABLE = [
    0, 1608, 3216, 4821, 6424, 8022, 9616, 11204, 12785, 14359, 15924, 17479, 19024, 20557, 22078, 23586,
    25080, 26558, 28020, 29466, 30893, 32303, 33692, 35062, 36410, 37736, 39040, 40320, 41576, 42806, 44011, 45190,
    46341, 47464, 48559, 49624, 50660, 51665, 52639, 53581, 54491, 55368, 56212, 57022, 57798, 58538, 59244, 59914,
    60547, 61145, 61705, 62228, 62714, 63162, 63572, 63944, 64277, 64571, 64827, 65043, 65220, 65358, 65457, 65516,
    65536, 65516, 65457, 65358, 65220, 65043, 64827, 64571, 64277, 63944, 63572, 63162, 62714, 62228, 61705, 61145,
    60547, 59914, 59244, 58538, 57798, 57022, 56212, 55368, 54491, 53581, 52639, 51665, 50660, 49624, 48559, 47464,
    46341, 45190, 44011, 42806, 41576, 40320, 39040, 37736, 36410, 35062, 33692, 32303, 30893, 29466, 28020, 26558,
    25080, 23586, 22078, 20557, 19024, 17479, 15924, 14359, 12785, 11204, 9616, 8022, 6424, 4821, 3216, 1608,
    0, -1608, -3216, -4821, -6424, -8022, -9616, -11204, -12785, -14359, -15924, -17479, -19024, -20557, -22078, -23586,
    -25080, -26558, -28020, -29466, -30893, -32303, -33692, -35062, -36410, -37736, -39040, -40320, -41576, -42806, -44011, -45190,
    -46341, -47464, -48559, -49624, -50660, -51665, -52639, -53581, -54491, -55368, -56212, -57022, -57798, -58538, -59244, -59914,
    -60547, -61145, -61705, -62228, -62714, -63162, -63572, -63944, -64277, -64571, -64827, -65043, -65220, -65358, -65457, -65516,
    -65536, -65516, -65457, -65358, -65220, -65043, -64827, -64571, -64277, -63944, -63572, -63162, -62714, -62228, -61705, -61145,
    -60547, -59914, -59244, -58538, -57798, -57022, -56212, -55368, -54491, -53581, -52639, -51665, -50660, -49624, -48559, -47464,
    -46341, -45190, -44011, -42806, -41576, -40320, -39040, -37736, -36410, -35062, -33692, -32303, -30893, -29466, -28020, -26558,
    -25080, -23586, -22078, -20557, -19024, -17479, -15924, -14359, -12785, -11204, -9616, -8022, -6424, -4821, -3216, -1608,
    0
  ];

  var SIN_BITS = 8;

  // integer floor-division that matches Python // for our (mostly positive)
  // and mixed-sign small integers. Python floors toward -inf.
  function fdiv(a, b) { return Math.floor(a / b); }

  function isin(angle) {
    angle = angle & 0xFFFF;
    var idx = angle >>> (16 - SIN_BITS);
    var frac = angle & ((1 << (16 - SIN_BITS)) - 1);
    var a = SIN_TABLE[idx];
    var b = SIN_TABLE[idx + 1];
    var step = 1 << (16 - SIN_BITS);
    return a + fdiv((b - a) * frac, step);
  }

  function icos(angle) { return isin(angle + 16384); }

  function lattice(seed, i) {
    var v = h32(mix(seed, i >>> 0));
    return (v & 0x1FFFF) - 65536;
  }

  function smooth(frac, scale) {
    var f = frac;
    var f2 = fdiv(f * f, scale);
    var f3 = fdiv(f2 * f, scale);
    return 3 * f2 - 2 * f3;
  }

  function valueNoise(seed, t, period) {
    if (period < 1) period = 1;
    var node = fdiv(t, period);
    var frac = t - node * period;
    var a = lattice(seed, node);
    var b = lattice(seed, node + 1);
    var w = smooth(frac, period);
    return a + fdiv((b - a) * w, period);
  }

  // ---- epochs & caps ----
  var GENESIS = 1780000000;
  var EPOCH_LEN = 90 * 24 * 3600;
  var WEEK_LEN = 7 * 24 * 3600;
  var PHI_Q16 = 106039;
  var TREND_WEEKS = 4;

  function epoch(t) {
    if (t < GENESIS) return 0;
    return fdiv(t - GENESIS, EPOCH_LEN);
  }

  function week(t) {
    if (t < GENESIS) return 0;
    return fdiv(t - GENESIS, WEEK_LEN);
  }

  function weekAnchor(t) {
    if (t < GENESIS) return GENESIS;
    return GENESIS + week(t) * WEEK_LEN;
  }

  function phiPowQ16(tier) {
    var acc = 65536;
    for (var i = 0; i < tier; i++) acc = Math.floor((acc * PHI_Q16) / 65536);
    return acc;
  }

  // cubes / measures
  var CUBE_MARKET = 1, CUBE_BOSS = 2, CUBE_AUCTION = 3, CUBE_POWER = 4, CUBE_PLAYER = 5;
  var M_PRICE = 1, M_SPREAD = 2, M_VOLUME = 3, M_ROBOT = 4, M_BOSS_HP = 5, M_CAPACITY = 6, M_CAPITAL = 7, M_WELFARE = 8;

  var BASE_CAP = {};
  BASE_CAP[CUBE_MARKET + ':' + M_PRICE] = 1000000;
  BASE_CAP[CUBE_MARKET + ':' + M_SPREAD] = 50000;
  BASE_CAP[CUBE_MARKET + ':' + M_VOLUME] = 10000000;
  BASE_CAP[CUBE_MARKET + ':' + M_ROBOT] = 1000000;
  BASE_CAP[CUBE_BOSS + ':' + M_BOSS_HP] = 1000000;
  BASE_CAP[CUBE_POWER + ':' + M_CAPACITY] = 5;
  BASE_CAP[CUBE_PLAYER + ':' + M_CAPITAL] = 100000000;
  BASE_CAP[CUBE_PLAYER + ':' + M_WELFARE] = 1000000;

  var SECTOR_TICKERS = {
    0: ['ALPHA', 'BETA', 'GAMMA', 'DELTA', 'EPSILON'],
    1: ['ZETA', 'ETA', 'THETA', 'IOTA', 'KAPPA'],
    2: ['LAMBDA', 'MU', 'NU', 'XI', 'OMICRON'],
    3: ['SIGMA', 'TAU', 'UPSILON', 'OMEGA', 'PSI']
  };
  var N_SECTORS = 4;
  var ALL_TICKERS = [];
  (function () {
    for (var si = 0; si < N_SECTORS; si++)
      ALL_TICKERS = ALL_TICKERS.concat(SECTOR_TICKERS[si]);
  })();

  function cap(cube, measure, ep) {
    var key = cube + ':' + measure;
    var base = (key in BASE_CAP) ? BASE_CAP[key] : 100000;
    return Math.floor((base * phiPowQ16(ep)) / 65536);
  }

  function clamp(v, lo, hi) {
    if (v < lo) return lo;
    if (v > hi) return hi;
    return v;
  }

  var WAVES = [
    [7 * 24 * 3600, 26214],
    [24 * 3600, 16384],
    [3600, 9830],
    [600, 4915]
  ];

  function cell(cube, entity, t, subject, measure, ep) {
    if (ep === undefined || ep === null) ep = epoch(t);
    var seed = mix(cube, entity, subject, measure, ep);
    var ceil = cap(cube, measure, ep);
    var base = Math.floor(ceil / 2);

    var acc = 0, i;
    for (i = 0; i < WAVES.length; i++) {
      var period = WAVES[i][0], weight = WAVES[i][1];
      var phase = h32(mix(seed, i)) & 0xFFFF;
      var ang = fdiv((t % period) * 65536, period) + phase;
      acc += fdiv(isin(ang) * weight, 65536);
    }

    var n1 = valueNoise(mix(seed, 101), t, 1800);
    var n2 = valueNoise(mix(seed, 202), t, 180);
    var noise = fdiv(n1 * 13107, 65536) + fdiv(n2 * 6553, 65536);

    var corp = 0;
    var inj = h32(mix(seed, 909, fdiv(t, 12 * 3600)));
    if ((inj & 0xFF) < 24) {
      var local = fdiv((t % (12 * 3600)) * 65536, 12 * 3600);
      corp = fdiv(isin(local) * 13107, 65536);
    }

    var bots = fdiv(valueNoise(mix(seed, 303), t, 30), 8);

    var total = acc + noise + corp + bots;
    var val = base + fdiv(base * total, 131072);
    return clamp(val, 1, ceil);
  }

  function price(sym, t, ep) { return cell(CUBE_MARKET, strSeed(sym), t, 0, M_PRICE, ep); }
  function spread(sym, t, ep) { return cell(CUBE_MARKET, strSeed(sym), t, 0, M_SPREAD, ep); }
  function volume(sym, t, ep) { return cell(CUBE_MARKET, strSeed(sym), t, 0, M_VOLUME, ep); }
  function robotTarget(sym, t, ep) { return cell(CUBE_MARKET, strSeed(sym), t, 0, M_ROBOT, ep); }
  function bossHp(id, t, ep) { return cell(CUBE_BOSS, id | 0, t, 0, M_BOSS_HP, ep); }
  function capacity(subject, t, ep) { return cell(CUBE_POWER, 0, t, subject | 0, M_CAPACITY, ep); }
  function capital(uid, t, ep) { return cell(CUBE_PLAYER, 0, t, uid | 0, M_CAPITAL, ep); }

  function capitalSeries(uid, nowNw, tNow, step, n, ep) {
    var t0 = tNow - (n - 1) * step;
    var raw = [];
    for (var i = 0; i < n; i++) raw.push(capital(uid, t0 + i * step, ep));
    var last = raw[n - 1] ? raw[n - 1] : 1;
    if (nowNw <= 0) return raw;
    var out = [];
    for (i = 0; i < n; i++) out.push(Math.floor((raw[i] * nowNw) / last));
    return out;
  }

  function series(sym, t0, step, n, ep, fn) {
    fn = fn || price;
    var out = [];
    for (var i = 0; i < n; i++) out.push(fn(sym, t0 + i * step, ep));
    return out;
  }

  // ---- welfare / standard-of-living (JS twin, see market_cube.py) ----
  function aggPrice(tickers, t) {
    var s = 0;
    for (var i = 0; i < tickers.length; i++) s += price(tickers[i], t);
    var n = tickers.length ? tickers.length : 1;
    return fdiv(s, n);
  }

  function trendQ16(tickers, t) {
    var a = weekAnchor(t);
    var now = aggPrice(tickers, a);
    var prev = aggPrice(tickers, a - WEEK_LEN);
    if (prev <= 0) return 0;
    var slope = fdiv((now - prev) * 65536, prev);
    return clamp(slope, -32768, 32768);
  }

  function marketTrend(t) { return trendQ16(ALL_TICKERS, t); }
  function sectorOf(uid) { return (uid | 0) % N_SECTORS; }
  function sectorTrend(sec, t) {
    return trendQ16(SECTOR_TICKERS[((sec | 0) % N_SECTORS + N_SECTORS) % N_SECTORS], t);
  }

  function trendBump(uid, t) {
    var sec = sectorOf(uid), acc = 0;
    for (var k = 0; k < TREND_WEEKS; k++) {
      var tw = t - k * WEEK_LEN;
      var both = marketTrend(tw) + sectorTrend(sec, tw);
      if (both > 6553) acc += 1;
      else if (both < -6553) acc -= 1;
    }
    var step = acc;
    if (step > 0) { step = fdiv(step + 1, 2); step = clamp(step, 0, 2); }
    else { step = -fdiv(-step + 1, 2); step = clamp(step, -1, 0); }
    return step;
  }

  function livingTier(uid, t) { return Math.max(0, epoch(t) + trendBump(uid, t)); }

  function welfareFloor(uid, t) {
    var base = Math.floor(BASE_CAP[CUBE_PLAYER + ':' + M_WELFARE] / 4);
    return Math.floor((base * phiPowQ16(livingTier(uid, t))) / 65536);
  }

  function welfareBase(uid, t) { return cell(CUBE_PLAYER, 0, t, uid | 0, M_WELFARE); }

  function mishap(uid, t) {
    var seam = weekAnchor(t);
    var into = t - seam;
    var half = Math.floor(WEEK_LEN / 2);
    var w;
    if (into <= half) w = fdiv(into * 65536, half);
    else w = fdiv((WEEK_LEN - into) * 65536, half);
    var wob = valueNoise(mix(strSeed('mishap'), (uid | 0) >>> 0), t, 3 * 3600);
    var amp = Math.floor(welfareBase(uid, t) / 8);
    var signed = fdiv(wob * amp, 65536);
    return fdiv(signed * w, 65536);
  }

  function welfareRaw(uid, t) {
    var sec = sectorOf(uid);
    var m = 65536 + marketTrend(t);
    var s = 65536 + sectorTrend(sec, t);
    var v = welfareBase(uid, t);
    v = fdiv(v * m, 65536);
    v = fdiv(v * s, 65536);
    return v;
  }

  function welfare(uid, t) {
    var seam = weekAnchor(t);
    var consolidated = welfareRaw(uid, seam);
    var live = welfareRaw(uid, t) + mishap(uid, t);
    var val = fdiv(consolidated + live, 2);
    var floor = welfareFloor(uid, t);
    var ceil = cap(CUBE_PLAYER, M_WELFARE, epoch(t));
    return clamp(Math.max(val, floor), 1, ceil);
  }

  var CANDLE_SAMPLES = 12;

  function welfareCandle(uid, wk, t) {
    if (wk === undefined || wk === null) wk = week(t === undefined ? GENESIS : t);
    var tOpen = GENESIS + wk * WEEK_LEN;
    var tClose = tOpen + WEEK_LEN;
    var o = welfare(uid, tOpen);
    var c = welfare(uid, tClose);
    var hi = o > c ? o : c;
    var lo = o < c ? o : c;
    var step = Math.floor(WEEK_LEN / CANDLE_SAMPLES);
    for (var i = 1; i < CANDLE_SAMPLES; i++) {
      var w = welfare(uid, tOpen + i * step);
      if (w > hi) hi = w;
      if (w < lo) lo = w;
    }
    return { week: wk, t_open: tOpen, t_close: tClose,
      o: o, h: hi, l: lo, c: c, tier: livingTier(uid, tClose),
      floor: welfareFloor(uid, tClose), up: c >= o ? 1 : 0 };
  }

  function welfareQuotes(uid, t, n) {
    if (!n) n = 8;
    var wk = week(t), out = [];
    for (var i = 0; i < n; i++) out.push(welfareCandle(uid, wk - (n - 1 - i)));
    return out;
  }

  function welfareSaldo(uid, t0, t1) { return welfare(uid, t1) - welfare(uid, t0); }

  function welfareReport(uid, t, periods, span) {
    if (!periods) periods = 8;
    if (!span) span = WEEK_LEN;
    var rows = [];
    for (var k = periods - 1; k >= 0; k--) {
      var t1 = t - k * span, t0 = t1 - span;
      var w0 = welfare(uid, t0), w1 = welfare(uid, t1);
      rows.push({ start: t0, end: t1, mean: fdiv(w0 + w1, 2),
        saldo: w1 - w0, tier: livingTier(uid, t1), floor: welfareFloor(uid, t1) });
    }
    return rows;
  }

  function welfareExplain(uid, t) {
    var sec = sectorOf(uid), seam = weekAnchor(t);
    return {
      uid: uid | 0, t: t | 0, epoch: epoch(t), week: week(t), week_anchor: seam,
      sector: sec, market_trend_q16: marketTrend(t), sector_trend_q16: sectorTrend(sec, t),
      trend_bump: trendBump(uid, t), living_tier: livingTier(uid, t),
      welfare_base: welfareBase(uid, t), welfare_raw: welfareRaw(uid, t),
      welfare_raw_seam: welfareRaw(uid, seam), mishap: mishap(uid, t),
      welfare_floor: welfareFloor(uid, t), welfare: welfare(uid, t)
    };
  }

  var API = {
    h32: h32, mix: mix, strSeed: strSeed, isin: isin, icos: icos,
    valueNoise: valueNoise, epoch: epoch, cap: cap, cell: cell,
    price: price, spread: spread, volume: volume, robotTarget: robotTarget,
    bossHp: bossHp, capacity: capacity, capital: capital,
    capitalSeries: capitalSeries, series: series,
    week: week, weekAnchor: weekAnchor, marketTrend: marketTrend,
    sectorOf: sectorOf, sectorTrend: sectorTrend, trendBump: trendBump,
    livingTier: livingTier, welfareFloor: welfareFloor, welfareRaw: welfareRaw,
    mishap: mishap, welfare: welfare, welfareCandle: welfareCandle,
    welfareQuotes: welfareQuotes, welfareSaldo: welfareSaldo,
    welfareReport: welfareReport, welfareExplain: welfareExplain,
    CUBE_MARKET: CUBE_MARKET, CUBE_BOSS: CUBE_BOSS, CUBE_AUCTION: CUBE_AUCTION, CUBE_POWER: CUBE_POWER,
    M_PRICE: M_PRICE, M_SPREAD: M_SPREAD, M_VOLUME: M_VOLUME, M_ROBOT: M_ROBOT,
    M_BOSS_HP: M_BOSS_HP, M_CAPACITY: M_CAPACITY, M_CAPITAL: M_CAPITAL,
    M_WELFARE: M_WELFARE, GENESIS: GENESIS, EPOCH_LEN: EPOCH_LEN,
    WEEK_LEN: WEEK_LEN, SIN_TABLE: SIN_TABLE
  };

  if (typeof module !== 'undefined' && module.exports) module.exports = API;
  root.MarketCube = API;
})(typeof window !== 'undefined' ? window : this);
