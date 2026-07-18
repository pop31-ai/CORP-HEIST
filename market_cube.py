"""
market_cube.py - deterministic OLAP-style field for CORP HEIST.

The whole world is a virtual multi-dimensional cube: no cell is ever stored,
every value is COMPUTED from its coordinates. Axes:

    cube    - which sub-cube of the field (MARKET, BOSS, AUCTION, POWER, ...)
    entity  - symbol / entity id (ticker, boss, lot, ...)
    t       - time, seconds since Unix epoch (past & future computed alike)
    subject - whose slice (uid; 0 = shared/market)
    measure - which metric (price, spread, volume, robot_target, boss_hp, ...)
    epoch   - +1 axis: seed layer, shifts the whole grid AND all allowances

Design constraints (see docs/CUBE.md):
  * INTEGER-ONLY math (uint32). NO float, NO math.sin at runtime.
    This guarantees a JS twin computes bit-for-bit identical values.
  * Cells are clamped into an allowance cap(cube, measure, epoch) that grows
    by golden (phi) steps per epoch - the "exoskeleton" ceiling.
  * Neighbouring cubes agree on shared seams (computed, not stored).

Nothing here reads the network or the disk. Pure functions of coordinates.
"""

MASK = 0xFFFFFFFF

# ----------------------------------------------------------------------
# Integer hashing (mulberry32-style finalizer). Identical in Python & JS.
# In JS use Math.imul and >>> 0; here we mask to 32 bits after each step.
# ----------------------------------------------------------------------

def _imul(a, b):
    return (a * b) & MASK


def h32(x):
    """Finalize a 32-bit integer into a well-mixed 32-bit hash."""
    x &= MASK
    x ^= x >> 16
    x = _imul(x, 0x7FEB352D)
    x ^= x >> 15
    x = _imul(x, 0x846CA68B)
    x ^= x >> 16
    return x & MASK


def mix(*parts):
    """Fold several integer coordinates into one 32-bit seed."""
    acc = 0x9E3779B1  # 2^32 / phi  (golden constant)
    for p in parts:
        acc = (acc + (int(p) & MASK)) & MASK
        acc = h32(acc)
    return acc


def str_seed(s):
    """Stable 32-bit seed from a string (FNV-1a), same bytes in JS."""
    acc = 0x811C9DC5
    for ch in s.encode("utf-8"):
        acc ^= ch
        acc = _imul(acc, 0x01000193)
    return h32(acc)


# ----------------------------------------------------------------------
# Integer sine: input angle in [0, 65536) maps one full turn.
# Output in [-65536, 65536] (Q16 fixed-point). Table of 257 ints,
# constant so the JS twin uses the very same numbers. Built once here
# from math.sin at import; the values are deterministic integers.
# ----------------------------------------------------------------------

_SIN_BITS = 8               # 256 samples over a full turn
_SIN_N = 1 << _SIN_BITS
_SIN_SCALE = 65536

# 257 constant ints in [-65536, 65536], one full turn. IDENTICAL to the JS
# twin (market_cube.js). Hard-coded so runtime never calls math.sin and both
# languages use the exact same numbers -> bit-for-bit identical cells.
SIN_TABLE = [
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
    0,
]


def isin(angle):
    """Integer sine. angle: any int, 65536 == full turn. Returns Q16 int."""
    angle &= 0xFFFF                       # wrap to one turn (16-bit)
    idx = angle >> (16 - _SIN_BITS)       # high bits -> table index 0..255
    frac = angle & ((1 << (16 - _SIN_BITS)) - 1)
    a = SIN_TABLE[idx]
    b = SIN_TABLE[idx + 1]
    # linear interpolation in integers: a + (b-a)*frac/step
    step = 1 << (16 - _SIN_BITS)
    return a + ((b - a) * frac) // step


def icos(angle):
    return isin(angle + 16384)            # +90 degrees (65536/4)


# ----------------------------------------------------------------------
# Value noise: smoothstep interpolation between integer lattice hashes.
# Deterministic, reproducible, but not linearly extrapolable.
# ----------------------------------------------------------------------

def _lattice(seed, i):
    """Signed value at integer node i, in [-65536, 65536]."""
    v = h32(mix(seed, i & MASK))
    return (v & 0x1FFFF) - 65536          # 17-bit span -> [-65536, 65535]


def _smooth(frac, scale):
    """smoothstep 3f^2 - 2f^3 on integers; frac,scale integers, ret /scale."""
    # returns weight in [0, scale]
    f = frac
    # 3f^2 - 2f^3 done with scale normalisation
    f2 = (f * f) // scale
    f3 = (f2 * f) // scale
    return (3 * f2 - 2 * f3)


def value_noise(seed, t, period):
    """Smooth noise: t in ticks, period = node spacing. Returns Q16 int."""
    if period < 1:
        period = 1
    node = t // period
    frac = t - node * period              # 0..period-1
    a = _lattice(seed, node)
    b = _lattice(seed, node + 1)
    w = _smooth(frac, period)             # 0..period
    return a + ((b - a) * w) // period


# ----------------------------------------------------------------------
# Epochs and allowances (caps). Caps grow by phi steps per epoch.
# phi in Q16: round(1.618033988749 * 65536) = 106039.
# ----------------------------------------------------------------------

GENESIS = 1_780_000_000       # ~2026 launch origin; epoch 0 starts here
EPOCH_LEN = 90 * 24 * 3600    # one epoch = 90 days ("technological upgrade")
WEEK_LEN = 7 * 24 * 3600      # one week: the "free" window, tidied at the seam
PHI_Q16 = 106039              # phi * 65536, integer
TREND_WEEKS = 4               # K: how many weeks the living-tier trend looks back


def epoch(t):
    """Deterministic epoch index from time t (seconds)."""
    if t < GENESIS:
        return 0
    return (t - GENESIS) // EPOCH_LEN


def week(t):
    """Deterministic week index from time t (seconds)."""
    if t < GENESIS:
        return 0
    return (t - GENESIS) // WEEK_LEN


def week_anchor(t):
    """Start-of-week seam time. Values are 'tidied' (consolidated) here."""
    if t < GENESIS:
        return GENESIS
    return GENESIS + week(t) * WEEK_LEN


def _phi_pow_q16(tier):
    """phi^tier as integer multiplier scaled by 65536 (Q16). tier >= 0."""
    acc = 65536                            # 1.0 in Q16
    for _ in range(tier):
        acc = (acc * PHI_Q16) >> 16
    return acc


def cap(cube, measure, ep):
    """Allowance ceiling for a (cube, measure) at epoch ep. Integer."""
    base = _BASE_CAP.get((cube, measure), 100000)
    return (base * _phi_pow_q16(ep)) >> 16


def clamp(v, lo, hi):
    if v < lo:
        return lo
    if v > hi:
        return hi
    return v


# ----------------------------------------------------------------------
# Cube / measure registry
# ----------------------------------------------------------------------

CUBE_MARKET = 1
CUBE_BOSS = 2
CUBE_AUCTION = 3
CUBE_POWER = 4
CUBE_PLAYER = 5

M_PRICE = 1
M_SPREAD = 2
M_VOLUME = 3
M_ROBOT = 4          # robot_target: the "answer" robots already know
M_BOSS_HP = 5
M_CAPACITY = 6       # the exoskeleton example: liftable weight
M_CAPITAL = 7        # a player's net-worth curve over time
M_WELFARE = 8        # a player's welfare / standard-of-living level

# base caps (epoch 0). integers. HARD/SOFT/BONUS behaviour is in cell().
_BASE_CAP = {
    (CUBE_MARKET, M_PRICE):    1_000_000,   # SOFT
    (CUBE_MARKET, M_SPREAD):      50_000,   # SOFT
    (CUBE_MARKET, M_VOLUME):  10_000_000,   # SOFT
    (CUBE_MARKET, M_ROBOT):    1_000_000,   # tracks price cap
    (CUBE_BOSS,   M_BOSS_HP):  1_000_000,   # HARD
    (CUBE_POWER,  M_CAPACITY):         5,   # HARD: 5 kg at epoch 0 -> phi growth
    (CUBE_PLAYER, M_CAPITAL): 100_000_000, # SOFT: personal net-worth ceiling
    (CUBE_PLAYER, M_WELFARE):   1_000_000, # SOFT: welfare reference ceiling
}

# Sector grouping: which tickers belong to which sector. Kept identical to
# press/phi_data.SECTORS so market/sector trends agree everywhere.
SECTOR_TICKERS = {
    0: ("ALPHA", "BETA", "GAMMA", "DELTA", "EPSILON"),   # TECH
    1: ("ZETA", "ETA", "THETA", "IOTA", "KAPPA"),        # FINANCE
    2: ("LAMBDA", "MU", "NU", "XI", "OMICRON"),          # ENERGY
    3: ("SIGMA", "TAU", "UPSILON", "OMEGA", "PSI"),      # LUXURY
}
ALL_TICKERS = tuple(s for grp in SECTOR_TICKERS.values() for s in grp)


# ----------------------------------------------------------------------
# The one cell function. Everything else is a thin wrapper.
# ----------------------------------------------------------------------

# wave periods (in seconds) and their amplitude weights (Q16 fractions)
_WAVES = (
    (7 * 24 * 3600, 26214),   # weekly-ish big swing, 0.40
    (24 * 3600,     16384),   # daily, 0.25
    (3600,           9830),   # hourly, 0.15
    (600,            4915),   # 10-min ripple, 0.075
)


def cell(cube, entity, t, subject, measure, ep=None):
    """Compute one field cell as an integer, clamped to its allowance."""
    if ep is None:
        ep = epoch(t)
    seed = mix(cube, entity, subject, measure, ep)

    # base level: mid of the allowance, personalised by seed
    ceil = cap(cube, measure, ep)
    base = ceil >> 1

    # sum of deterministic waves (volatile but readable trend)
    acc = 0
    for i, (period, weight) in enumerate(_WAVES):
        phase = (h32(mix(seed, i)) & 0xFFFF)
        ang = ((t % period) * 65536) // period + phase
        acc += (isin(ang) * weight) >> 16          # each in ~[-weight, weight]

    # deterministic value-noise (reproducible, not extrapolable)
    n1 = value_noise(mix(seed, 101), t, 1800)      # 30-min noise
    n2 = value_noise(mix(seed, 202), t, 180)       # 3-min finer noise
    noise = (n1 * 13107 >> 16) + (n2 * 6553 >> 16)  # 0.20 + 0.10 weights

    # corporate injections: rare smooth impulses
    corp = 0
    inj = h32(mix(seed, 909, t // (12 * 3600)))
    if (inj & 0xFF) < 24:                            # ~9% of 12h windows
        local = (t % (12 * 3600)) * 65536 // (12 * 3600)
        corp = (isin(local) * 13107) >> 16          # 0.20 hump

    # robot / bot high-frequency jitter
    bots = value_noise(mix(seed, 303), t, 30) >> 3  # tiny, 30s jitter

    total = acc + noise + corp + bots               # in ~[-65536, 65536] units
    # map fluctuation onto [~0.5*base ... ~1.5*base]
    val = base + ((base * total) >> 17)             # base * total/131072

    return clamp(val, 1, ceil)


# ----------------------------------------------------------------------
# Thin measure wrappers (public API)
# ----------------------------------------------------------------------

def price(sym, t, ep=None):
    return cell(CUBE_MARKET, str_seed(sym), t, 0, M_PRICE, ep)


def spread(sym, t, ep=None):
    return cell(CUBE_MARKET, str_seed(sym), t, 0, M_SPREAD, ep)


def volume(sym, t, ep=None):
    return cell(CUBE_MARKET, str_seed(sym), t, 0, M_VOLUME, ep)


def robot_target(sym, t, ep=None):
    """What the robots already 'know' - the answer they trade toward."""
    return cell(CUBE_MARKET, str_seed(sym), t, 0, M_ROBOT, ep)


def boss_hp(boss_id, t, ep=None):
    return cell(CUBE_BOSS, int(boss_id), t, 0, M_BOSS_HP, ep)


def capacity(subject, t, ep=None):
    """Exoskeleton example: liftable weight, HARD cap grows per epoch."""
    return cell(CUBE_POWER, 0, t, int(subject), M_CAPACITY, ep)


def capital(uid, t, ep=None):
    """Raw net-worth curve shape for a player from the cube."""
    return cell(CUBE_PLAYER, 0, t, int(uid), M_CAPITAL, ep)


def capital_series(uid, now_nw, t_now, step, n, ep=None):
    """History-of-capital curve, shape from the cube, scaled so the LAST point
    equals the player's real current net worth (now_nw). Zero storage: the
    curve is computed; only the single scalar now_nw is the player's own state.
    Returns list of n ints ending at now_nw."""
    t0 = t_now - (n - 1) * step
    raw = [capital(uid, t0 + i * step, ep) for i in range(n)]
    last = raw[-1] if raw[-1] else 1
    if now_nw <= 0:
        return raw
    return [(r * now_nw) // last for r in raw]


def series(sym, t0, step, n, ep=None, fn=price):
    """Sample a measure over n points -> list of ints. For history curves."""
    return [fn(sym, t0 + i * step, ep) for i in range(n)]


# ----------------------------------------------------------------------
# Welfare / standard-of-living. A player's well-being is NOT isolated: it is
# a convolution of the whole economy's tendency and their sector's tendency.
#
#   market_trend  -> sector_trend  -> welfare(uid)
#
# Everything is a closed-form pure function of (uid, t): no stored history,
# no iteration over past weeks (a "diligent" player can plug in uid & t and
# reproduce every term). Local weekly volatility rides on top of a strictly
# defined living-tier that only steps at week seams.
# Trend units are Q16 fixed point (65536 == 1.0). See docs/CUBE.md.
# ----------------------------------------------------------------------

def _agg_price(tickers, t):
    """Integer mean price of a group of tickers at time t."""
    s = 0
    for sym in tickers:
        s += price(sym, t)
    n = len(tickers) if tickers else 1
    return s // n


def _trend_q16(tickers, t):
    """Weekly slope of a group's mean price, in Q16. Compares this week's
    seam to last week's seam: (now - prev) / prev. Clipped to +-0.5 so a
    single week can never swing welfare more than half. Closed form in t."""
    a = week_anchor(t)
    now = _agg_price(tickers, a)
    prev = _agg_price(tickers, a - WEEK_LEN)
    if prev <= 0:
        return 0
    slope = ((now - prev) * 65536) // prev
    return clamp(slope, -32768, 32768)


def market_trend(t):
    """Tendency of the whole economy this week, Q16 (65536 == +100%)."""
    return _trend_q16(ALL_TICKERS, t)


def sector_of(uid):
    """Which sector a player belongs to (mirrors corp/sector grouping)."""
    return int(uid) % len(SECTOR_TICKERS)


def sector_trend(sec, t):
    """Tendency of one sector this week, Q16."""
    return _trend_q16(SECTOR_TICKERS.get(int(sec) % len(SECTOR_TICKERS)), t)


def trend_bump(uid, t):
    """Closed-form living-tier delta from the last TREND_WEEKS windows.
    A sustained positive market*sector tendency lifts the standard of living;
    a sustained negative one lowers it. Result is a small integer step in
    [-1 .. +2] (living improves more easily than it collapses)."""
    sec = sector_of(uid)
    acc = 0
    for k in range(TREND_WEEKS):
        tw = t - k * WEEK_LEN
        m = market_trend(tw)
        s = sector_trend(sec, tw)
        # combined sign-weighted contribution, each week in ~[-2..2]
        both = m + s                     # Q16 sum of two slopes
        if both > 6553:                  # > +0.10 -> good week
            acc += 1
        elif both < -6553:               # < -0.10 -> bad week
            acc -= 1
    # scale by weeks, then clip: living rises to +2, falls to -1
    step = acc  # already an int count in [-K..K]
    if step > 0:
        step = (step + 1) // 2           # +K -> +2 at K=4 (rounded)
        step = clamp(step, 0, 2)
    else:
        step = -((-step + 1) // 2)
        step = clamp(step, -1, 0)
    return step


def living_tier(uid, t):
    """Standard-of-living tier: epoch baseline + trend bump. Steps only at
    week seams (trend_bump reads week-anchored values), constant within a
    week. Closed form in (uid, t)."""
    return max(0, epoch(t) + trend_bump(uid, t))


def welfare_floor(uid, t):
    """The floor of the CURRENT living tier: base * phi^tier. A drop in the
    market cannot take a player below their tier's floor - but a sustained
    downturn can lower the tier itself (a real change of living standard)."""
    # floor is a QUARTER of the reference ceiling at the tier, so intra-week
    # readings normally sit above it and the floor is a real safety net (not a
    # cap). A sustained downturn lowers the tier -> lowers this floor.
    base = _BASE_CAP[(CUBE_PLAYER, M_WELFARE)] >> 2
    return (base * _phi_pow_q16(living_tier(uid, t))) >> 16


def _welfare_base(uid, t):
    """The player's own deterministic welfare shape (before trend & floor)."""
    return cell(CUBE_PLAYER, 0, t, int(uid), M_WELFARE)


def mishap(uid, t):
    """A player's 'small life ups and downs' within the week - the 'сыр-бор'.

    This is a PRIVATE, self-damping term: it can be negative (a bad trade, a
    lost duel) or positive intra-week, but its weight fades to ZERO at the
    week seam ('by the end of the week it is forgotten'). It never feeds the
    market/sector trend or the robots' answer - the experts don't see it.
    Returned as a Q16-ish signed integer to add onto welfare_raw."""
    seam = week_anchor(t)
    into = t - seam                       # 0 .. WEEK_LEN-1 seconds into the week
    # weight peaks mid-week, is 0 at both seams (start & end) -> forgotten
    # triangular window in Q16: 0 at 0, 65536 at mid, 0 at end
    half = WEEK_LEN >> 1
    if into <= half:
        w = (into * 65536) // half
    else:
        w = ((WEEK_LEN - into) * 65536) // half
    # the raw private wobble, personal & deterministic, ~[-1..1] scaled
    wob = value_noise(mix(str_seed("mishap"), int(uid) & MASK), t, 3 * 3600)
    amp = _welfare_base(uid, t) >> 3      # up to ~12% of personal shape
    signed = (wob * amp) >> 16            # signed, ~[-amp..amp]
    return (signed * w) >> 16             # faded by the weekly window


def welfare_raw(uid, t):
    """'Free' intra-week welfare: personal shape modulated by the economy's
    and the sector's tendency. This is the volatile line that breathes with
    the market; it is tidied to the seam by welfare()."""
    sec = sector_of(uid)
    m = 65536 + market_trend(t)          # 1.0 +- trend, Q16
    s = 65536 + sector_trend(sec, t)     # 1.0 +- trend, Q16
    v = _welfare_base(uid, t)
    v = (v * m) >> 16
    v = (v * s) >> 16
    return v


def welfare(uid, t):
    """Final, audit-safe welfare. Intra-week the raw value is allowed to move
    freely; on the weekly seam it is consolidated to the seam's raw value
    ('tidied at the end of the week'). Never below the current tier floor."""
    seam = week_anchor(t)
    consolidated = welfare_raw(uid, seam)     # tidy point for this week (clean)
    live = welfare_raw(uid, t) + mishap(uid, t)  # intra-week + private wobble
    # blend: the seam anchors the level, the intra-week ripple rides on it.
    # mishap fades to 0 at the seam, so a bad 'сыр-бор' is forgotten by week's
    # end; the floor guarantees a negative episode can never lower the tier.
    val = (consolidated + live) >> 1
    floor = welfare_floor(uid, t)
    ceil = cap(CUBE_PLAYER, M_WELFARE, epoch(t))
    return clamp(max(val, floor), 1, ceil)


_CANDLE_SAMPLES = 12          # intra-week probes for high/low (integer, cheap)


def welfare_candle(uid, wk=None, t=None):
    """Quote a player's welfare for ONE week as an OHLC candle - like a stock.

        open  = welfare at the week's opening seam  (clean expert reading)
        close = welfare at the closing seam         (tidied, positive finish)
        high  = best intra-week welfare (incl. lucky mishaps)
        low   = worst intra-week welfare (a bad 'сыр-бор' dip - but forgotten)

    close never drops below the tier floor, so a red week can dip (low) yet
    still close green-enough; the experts/robots quote it deterministically.
    Give either a week index `wk` or any time `t` inside the week."""
    if wk is None:
        wk = week(t if t is not None else GENESIS)
    t_open = GENESIS + wk * WEEK_LEN
    t_close = t_open + WEEK_LEN
    o = welfare(uid, t_open)
    c = welfare(uid, t_close)
    hi = o if o > c else c
    lo = o if o < c else c
    step = WEEK_LEN // _CANDLE_SAMPLES
    for i in range(1, _CANDLE_SAMPLES):
        w = welfare(uid, t_open + i * step)
        if w > hi:
            hi = w
        if w < lo:
            lo = w
    return {"week": wk, "t_open": t_open, "t_close": t_close,
            "o": o, "h": hi, "l": lo, "c": c,
            "tier": living_tier(uid, t_close),
            "floor": welfare_floor(uid, t_close),
            "up": 1 if c >= o else 0}


def welfare_quotes(uid, t, n=8):
    """A tape of the last n weekly welfare candles ending at time t (oldest
    first). This is the 'interesting quote' feed for the card & the PDF."""
    wk = week(t)
    return [welfare_candle(uid, wk - (n - 1 - i)) for i in range(n)]


def welfare_saldo(uid, t0, t1):
    """Balance (saldo) of welfare over a period: end minus start. Positive =
    the player's standard of living rose over [t0, t1]."""
    return welfare(uid, t1) - welfare(uid, t0)


def welfare_report(uid, t, periods=8, span=None):
    """Ledger of welfare over the last `periods` windows ending at t.
    span defaults to one week. Each row is fully recomputable. Returns a list
    of dicts (oldest first): {start, end, mean, saldo, tier, floor}."""
    if span is None:
        span = WEEK_LEN
    rows = []
    for k in range(periods - 1, -1, -1):
        t1 = t - k * span
        t0 = t1 - span
        w0 = welfare(uid, t0)
        w1 = welfare(uid, t1)
        rows.append({
            "start": t0, "end": t1,
            "mean": (w0 + w1) // 2,
            "saldo": w1 - w0,
            "tier": living_tier(uid, t1),
            "floor": welfare_floor(uid, t1),
        })
    return rows


def welfare_explain(uid, t):
    """Full transparency: every term that produces welfare(uid, t). For the
    'diligent' player/regulator - plug in uid & t, verify each member."""
    sec = sector_of(uid)
    seam = week_anchor(t)
    return {
        "uid": int(uid), "t": int(t),
        "epoch": epoch(t), "week": week(t), "week_anchor": seam,
        "sector": sec,
        "market_trend_q16": market_trend(t),
        "sector_trend_q16": sector_trend(sec, t),
        "trend_bump": trend_bump(uid, t),
        "living_tier": living_tier(uid, t),
        "welfare_base": _welfare_base(uid, t),
        "welfare_raw": welfare_raw(uid, t),
        "welfare_raw_seam": welfare_raw(uid, seam),
        "mishap": mishap(uid, t),
        "welfare_floor": welfare_floor(uid, t),
        "welfare": welfare(uid, t),
    }


# ----------------------------------------------------------------------
if __name__ == "__main__":
    import time as _time
    now = int(_time.time())
    print("epoch(now):", epoch(now))
    print("cap price e0:", cap(CUBE_MARKET, M_PRICE, 0))
    print("cap price e5:", cap(CUBE_MARKET, M_PRICE, 5))
    print("capacity e0/e14:",
          cap(CUBE_POWER, M_CAPACITY, 0), "->", cap(CUBE_POWER, M_CAPACITY, 14))
    print("ALPHA price now:", price("ALPHA", now))
    print("ALPHA robot now:", robot_target("ALPHA", now))
    print("market_trend now:", market_trend(now))
    print("welfare uid1042:", welfare(1042, now),
          "tier", living_tier(1042, now), "floor", welfare_floor(1042, now))
    ex = welfare_explain(1042, now)
    print("explain:", {k: ex[k] for k in ("living_tier", "welfare_raw",
          "mishap", "welfare_floor", "welfare")})
    cndl = welfare_candle(1042, t=now)
    print("candle O/H/L/C:", cndl["o"], cndl["h"], cndl["l"], cndl["c"],
          "up" if cndl["up"] else "down")
    # determinism
    assert price("ALPHA", now) == price("ALPHA", now)
    assert welfare(1042, now) == welfare(1042, now)
    assert welfare(1042, now) >= welfare_floor(1042, now)
    assert isin(0) == 0 and isin(16384) == 65536
    assert all(isinstance(x, int) for x in series("BETA", now, 3600, 24))
    assert all(isinstance(v, int) for v in welfare_explain(1042, now).values())
    print("isin(16384) =", isin(16384), "(expect 65536)")
    print("determinism OK; all ints OK")
