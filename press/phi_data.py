"""
phi_data - deterministic synthetic market data on golden-section algorithms.

Everything is seeded so every issue is reproducible. Prices, candles, sectors,
magnate ladders, boss HP curves - all derived from PHI. No network, no server.
"""

import math
import os
import sys

PHI = 1.618033988749895
INV_PHI = 1.0 / PHI
TAU = math.pi * 2.0

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    import market_cube as _cube
except Exception:
    _cube = None

CUBE_PRICE_DIV = 5000.0  # keep in sync with server_consolidated.SharedState

TICKERS = [
    "ALPHA", "BETA", "GAMMA", "DELTA", "EPSILON",
    "ZETA", "ETA", "THETA", "IOTA", "KAPPA",
    "LAMBDA", "MU", "NU", "XI", "OMICRON",
    "SIGMA", "TAU", "UPSILON", "OMEGA", "PSI",
]

SECTORS = [
    {"name": "TECH",    "emoji": "TECH", "idx": [0, 1, 2, 3, 4]},
    {"name": "FINANCE", "emoji": "FIN",  "idx": [5, 6, 7, 8, 9]},
    {"name": "ENERGY",  "emoji": "ENR",  "idx": [10, 11, 12, 13, 14]},
    {"name": "LUXURY",  "emoji": "LUX",  "idx": [15, 16, 17, 18, 19]},
]

MAGNATE_NAMES = [
    "Aurelius Vane", "Cassia Gold", "Dorian Sterling", "Elara Voss",
    "Fabian Crest", "Greta Halcyon", "Hugo Marlowe", "Isolde Quinn",
    "Julian Roth", "Katarina Vale", "Leon Ashford", "Mirela Fenn",
]


class PhiRng:
    """A tiny deterministic PRNG woven from the golden ratio.

    x_{n+1} = frac((x_n + PHI) * PHI * (n+seed))  - low quality but stable,
    plenty for magazine visuals and reproducible 'srochny vypusk' numbers.
    """

    def __init__(self, seed):
        self.n = 0
        self.x = math.fmod((seed + 1) * PHI, 1.0)
        self.seed = seed

    def next(self):
        self.n += 1
        v = math.fmod((self.x + PHI) * PHI * (self.n + self.seed + 1.0), 1.0)
        # extra whirl to decorrelate
        v = math.fmod(v * 10000.0 * PHI + math.sin(self.n * PHI), 1.0)
        v = abs(v)
        self.x = v
        return v

    def rng(self, lo, hi):
        return lo + (hi - lo) * self.next()

    def rint(self, lo, hi):
        return int(self.rng(lo, hi + 0.9999))

    def pick(self, seq):
        return seq[self.rint(0, len(seq) - 1)]


def phi_walk(seed, n, start, vol=0.02):
    """A golden-drift random walk. Returns list of n prices."""
    r = PhiRng(seed)
    out = [start]
    trend = (r.next() - 0.5) * vol * PHI
    for i in range(1, n):
        # mean-revert toward a slowly rotating golden anchor
        anchor = start * (1.0 + 0.12 * math.sin(i / (n / TAU) + seed))
        drift = (anchor - out[-1]) * (INV_PHI * 0.08)
        shock = (r.next() - 0.5) * vol * out[-1] * PHI
        trend *= INV_PHI ** 0.02
        p = out[-1] + drift + shock + trend * out[-1] * 0.01
        out.append(max(0.01, p))
    return out


def candles(seed, n=34, start=100.0, vol=0.03):
    """OHLC candles from a phi walk. n defaults to a Fibonacci number."""
    prices = phi_walk(seed, n * 2, start, vol)
    r = PhiRng(seed + 777)
    out = []
    for i in range(n):
        o = prices[i * 2]
        c = prices[i * 2 + 1]
        hi = max(o, c) * (1.0 + r.next() * vol * INV_PHI)
        lo = min(o, c) * (1.0 - r.next() * vol * INV_PHI)
        vol_bar = int(r.rng(1000, 1000 * PHI ** 4))
        out.append({"o": o, "h": hi, "l": lo, "c": c, "v": vol_bar})
    return out


def market_snapshot(seed):
    """20 tickers with price + phi change%.

    Prices come from the shared market cube (single source of truth). The seed
    selects a deterministic point in cube-time, so each issue stays fully
    reproducible while matching the game's own prices. Falls back to the phi
    walk if the cube module is unavailable."""
    r = PhiRng(seed)
    if _cube is not None:
        t = _cube.GENESIS + (int(seed) % 90) * 86400
        rows = []
        for tk in TICKERS:
            price = _cube.price(tk, t) / CUBE_PRICE_DIV
            now = _cube.price(tk, t)
            prev = _cube.price(tk, t - 3600)
            chg = ((now - prev) * 100.0 / prev) if prev else 0.0
            rows.append({"sym": tk, "price": round(price, 2),
                         "chg": round(chg, 2), "vol": int(_cube.volume(tk, t))})
        return rows
    rows = []
    for i, t in enumerate(TICKERS):
        base = 10.0 * (PHI ** (i % 6)) * r.rng(INV_PHI, PHI)
        chg = (r.next() - INV_PHI) * 100.0 * (PHI - 1)
        rows.append({"sym": t, "price": round(base, 2),
                     "chg": round(chg, 2), "vol": int(r.rng(5e3, 5e5))})
    return rows


def sector_snapshot(seed):
    mk = market_snapshot(seed)
    out = []
    for s in SECTORS:
        vals = [mk[i]["price"] for i in s["idx"]]
        chg = sum(mk[i]["chg"] for i in s["idx"]) / len(s["idx"])
        spark = phi_walk(seed + hash(s["name"]) % 9999, 24,
                         sum(vals) / len(vals), 0.04)
        out.append({"name": s["name"], "value": round(sum(vals), 2),
                    "chg": round(chg, 2), "spark": spark,
                    "members": [mk[i]["sym"] for i in s["idx"]]})
    hot = max(out, key=lambda x: x["chg"])["name"]
    cold = min(out, key=lambda x: x["chg"])["name"]
    return {"sectors": out, "hot": hot, "cold": cold}


def magnate_ladder(seed, n=8):
    r = PhiRng(seed + 4242)
    names = list(MAGNATE_NAMES)
    rows = []
    worth = 10_000_000.0 * PHI ** 3
    for i in range(n):
        nm = names[r.rint(0, len(names) - 1)]
        names.remove(nm)
        rows.append({"rank": i + 1, "name": nm,
                     "worth": int(worth),
                     "corp": r.pick(["ALPHA CORP", "GOLDEN LLC", "VANE HOLD",
                                     "PHI CAPITAL", "SIGMA GROUP"])})
        worth *= INV_PHI * r.rng(0.9, 1.05)
    return rows


def boss_curve(seed, phases=8):
    """World-boss HP thresholds descending by phi bands."""
    hp = 1_000_000
    out = []
    for i in range(phases):
        out.append({"phase": i + 1, "hp": int(hp),
                    "reward": int(hp * (PHI - 1) / PHI)})
        hp = int(hp * INV_PHI)
    return out


def phi_series(seed, n=13):
    """A simple ascending phi-power ladder for infographics."""
    return [round(PHI ** i, 3) for i in range(n)]


if __name__ == "__main__":
    print("market", market_snapshot(1)[:3])
    print("sectors hot/cold", sector_snapshot(1)["hot"], sector_snapshot(1)["cold"])
    print("magnates", magnate_ladder(1)[0])
    print("candles[0]", candles(1)[0])
    print("boss", boss_curve(1)[0])
    print("phi ladder", phi_series(1)[:6])
    # determinism check
    a = market_snapshot(7)
    b = market_snapshot(7)
    assert a == b, "RNG not deterministic!"
    print("determinism OK")
