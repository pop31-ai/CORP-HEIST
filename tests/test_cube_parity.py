"""
test_cube_parity - guarantees market_cube.py and market_cube.js agree
bit-for-bit. Emits a vector of (coords -> value) that the Node twin verifies.

Run standalone:   python tests/test_cube_parity.py         (writes vector)
Run parity:       node tests/test_cube_parity.js           (checks vector)
CI runs both.
"""
import os
import sys
import json

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import market_cube as mc

SYMS = ["ALPHA", "BETA", "GAMMA", "OMEGA", "ZETA", "Акция"]
T0 = mc.GENESIS + 12345
TIMES = [T0 + i * 777 for i in range(60)] + \
        [mc.GENESIS + e * mc.EPOCH_LEN + 500 for e in range(0, 8)]


def build_vector():
    v = {"low_level": {}, "cells": []}
    # low-level primitives
    v["low_level"]["h32"] = [mc.h32(x) for x in
                             (0, 1, 2, 42, 65535, 0xFFFFFFFF, 123456789)]
    v["low_level"]["mix"] = [mc.mix(1, 2, 3), mc.mix(9, 9, 9, 9, 9),
                             mc.mix(0), mc.mix(0xFFFFFFFF, 1)]
    v["low_level"]["strSeed"] = {s: mc.str_seed(s) for s in SYMS}
    v["low_level"]["isin"] = [mc.isin(a) for a in
                              (0, 100, 16384, 32768, 49152, 65535, 130000)]
    v["low_level"]["valueNoise"] = [mc.value_noise(7, t, 180)
                                    for t in (0, 90, 179, 180, 5000)]
    v["low_level"]["epoch"] = [mc.epoch(t) for t in
                               (0, mc.GENESIS, mc.GENESIS + mc.EPOCH_LEN,
                                mc.GENESIS + 10 * mc.EPOCH_LEN)]
    v["low_level"]["cap"] = [mc.cap(mc.CUBE_MARKET, mc.M_PRICE, e)
                             for e in range(0, 10)] + \
                            [mc.cap(mc.CUBE_POWER, mc.M_CAPACITY, e)
                             for e in (0, 5, 14)]
    # full cells across measures
    measures = [("price", mc.price), ("spread", mc.spread),
                ("volume", mc.volume), ("robot", mc.robot_target)]
    for s in SYMS:
        for t in TIMES:
            for name, fn in measures:
                v["cells"].append([s, t, name, fn(s, t)])
    # boss + capacity + capital
    for t in TIMES[:10]:
        v["cells"].append(["#boss", t, "boss_hp", mc.boss_hp(3, t)])
        v["cells"].append(["#cap", t, "capacity", mc.capacity(42, t)])
        v["cells"].append(["#capital", t, "capital", mc.capital(1042, t)])
    # capital_series with scaling (carry params so JS reproduces exactly)
    v["capital_series"] = {
        "uid": 1042, "now_nw": 3_250_000, "t_now": T0, "step": 3600, "n": 24,
        "values": mc.capital_series(1042, 3_250_000, T0, 3600, 24),
    }
    # welfare: trends, tiers, floors, mishap, final welfare across uids/times
    WUIDS = [1000, 1042, 1077, 2500, 9999]
    WTIMES = [mc.GENESIS + w * mc.WEEK_LEN + off
              for w in (0, 1, 5, 40, 80) for off in (500, 3 * 24 * 3600)]
    wf = {"market_trend": [], "sector_trend": [], "living_tier": [],
          "welfare_floor": [], "mishap": [], "welfare": []}
    for t in WTIMES:
        wf["market_trend"].append([t, mc.market_trend(t)])
        for sec in range(4):
            wf["sector_trend"].append([sec, t, mc.sector_trend(sec, t)])
        for uid in WUIDS:
            wf["living_tier"].append([uid, t, mc.living_tier(uid, t)])
            wf["welfare_floor"].append([uid, t, mc.welfare_floor(uid, t)])
            wf["mishap"].append([uid, t, mc.mishap(uid, t)])
            wf["welfare"].append([uid, t, mc.welfare(uid, t)])
    v["welfare"] = wf
    # a full explain + a candle + quotes for one player/time
    v["welfare_explain"] = {"uid": 1042, "t": WTIMES[6],
                            "value": mc.welfare_explain(1042, WTIMES[6])}
    v["welfare_candle"] = {"uid": 1042, "t": WTIMES[6],
                           "value": mc.welfare_candle(1042, t=WTIMES[6])}
    v["welfare_quotes"] = {"uid": 1042, "t": WTIMES[6], "n": 8,
                           "value": mc.welfare_quotes(1042, WTIMES[6], 8)}
    return v


VECTOR_PATH = os.path.join(HERE, "cube_vector.json")


def write_vector():
    v = build_vector()
    with open(VECTOR_PATH, "w", encoding="utf-8") as f:
        json.dump(v, f, ensure_ascii=True)
    return v


def check():
    """Self-checks on the Python side (determinism, ranges, int-ness)."""
    v = write_vector()
    # determinism
    assert build_vector() == v, "python not deterministic"
    # everything integer
    for row in v["cells"]:
        assert isinstance(row[3], int), "non-int cell: %r" % (row,)
    # isin anchors
    assert mc.isin(0) == 0
    assert mc.isin(16384) == 65536
    assert mc.isin(32768) == 0
    # caps grow
    assert mc.cap(mc.CUBE_MARKET, mc.M_PRICE, 1) > \
           mc.cap(mc.CUBE_MARKET, mc.M_PRICE, 0)
    print("cube parity vector written: %d cells -> %s"
          % (len(v["cells"]), VECTOR_PATH))
    return True


def test_all():
    assert check()


if __name__ == "__main__":
    ok = check()
    sys.exit(0 if ok else 1)
