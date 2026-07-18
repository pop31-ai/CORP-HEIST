# -*- coding: utf-8 -*-
"""
live_data - data source with a live-server front and phi-synthetic fallback.

If the CORP HEIST server (default http://localhost:9000) answers, real numbers
from /api/* are shaped into the same structures phi_data produces. Otherwise we
transparently fall back to deterministic phi synthetics, so the magazine always
builds - online or offline.

Set env CORP_HEIST_API to point elsewhere, or pass base=... to LiveData().
"""

import os
import json
import urllib.request

import phi_data as D

DEFAULT_BASE = os.environ.get("CORP_HEIST_API", "http://localhost:9000")


class LiveData:
    def __init__(self, base=DEFAULT_BASE, timeout=4, force_synth=False):
        self.base = base.rstrip("/")
        self.timeout = timeout
        self.force_synth = force_synth
        self.online = False
        self._cache = {}
        if not force_synth:
            self.online = self._probe()

    # -- transport ------------------------------------------------------
    def _get(self, path):
        if path in self._cache:
            return self._cache[path]
        try:
            with urllib.request.urlopen(self.base + path, timeout=self.timeout) as r:
                data = json.loads(r.read().decode("utf-8"))
                self._cache[path] = data
                return data
        except Exception:
            return None

    def _probe(self):
        return self._get("/api/stats") is not None or \
               self._get("/api/market") is not None

    @property
    def source(self):
        return "LIVE" if self.online else "SYNTH"

    # -- structured feeds (same shapes as phi_data) ---------------------
    def market_snapshot(self, seed):
        if self.online:
            m = self._get("/api/market")
            if isinstance(m, list) and m:
                rows = []
                for x in m[:20]:
                    rows.append({
                        "sym": x.get("name", "?")[:8],
                        "price": round(float(x.get("price", 0)), 2),
                        "chg": round(float(x.get("delta", x.get("chg", 0))), 2),
                        "vol": int(x.get("vol", x.get("volume", 0)) or 0),
                    })
                if rows:
                    return rows
        return D.market_snapshot(seed)

    def sector_snapshot(self, seed):
        if self.online:
            s = self._get("/api/sectors")
            if isinstance(s, dict) and s.get("sectors"):
                out = []
                for sec in s["sectors"]:
                    spark = sec.get("spark") or []
                    if len(spark) < 2:
                        spark = D.phi_walk(seed + len(out), 24,
                                           float(sec.get("value", 100)) or 100, 0.04)
                    out.append({
                        "name": sec.get("name", "?"),
                        "value": round(float(sec.get("value", 0)), 2),
                        "chg": round(float(sec.get("change_pct",
                                     sec.get("chg", 0))), 2),
                        "spark": spark,
                        "members": [m.get("name", "") if isinstance(m, dict) else m
                                    for m in sec.get("members", [])],
                    })
                if out:
                    return {"sectors": out,
                            "hot": s.get("rotation", {}).get("hot")
                                   or max(out, key=lambda z: z["chg"])["name"],
                            "cold": s.get("rotation", {}).get("cold")
                                   or min(out, key=lambda z: z["chg"])["name"]}
        return D.sector_snapshot(seed)

    def magnate_ladder(self, seed, n=8):
        if self.online:
            m = self._get("/api/magnates")
            rows = m.get("magnates") if isinstance(m, dict) else m
            if isinstance(rows, list) and rows:
                out = []
                for i, r in enumerate(rows[:n]):
                    out.append({
                        "rank": i + 1,
                        "name": (r.get("name") or "Magnate")[:16],
                        "worth": int(r.get("net_worth", r.get("worth", 0)) or 0),
                        "corp": r.get("corp", r.get("corp_name", "CORP")),
                    })
                if out and any(x["worth"] for x in out):
                    return out
        return D.magnate_ladder(seed, n)

    def liquidation_stages(self, seed):
        """Funnel stages from live liq feed, else synthetic phi funnel."""
        if self.online:
            f = self._get("/api/liqfeed")
            events = f.get("events") if isinstance(f, dict) else None
            if events:
                total = len(events)
                calls = sum(1 for e in events if e.get("type") in
                            ("call", "margin_call", "liquidated", "squeezed"))
                liq = sum(1 for e in events if e.get("type") in
                          ("liquidated", "squeezed"))
                return [("События", max(total, 1)),
                        ("Под риском", max(int(total * 0.62), calls, 1)),
                        ("Маржин-колл", max(calls, 1)),
                        ("Ликвидация", max(liq, 1))]
        base = 1000
        return [("Позиции", base), ("Под риском", int(base / D.PHI)),
                ("Маржин-колл", int(base / D.PHI ** 2)),
                ("Ликвидация", int(base / D.PHI ** 3))]

    # unchanged synthetic feeds (no clean live equivalent yet)
    def candles(self, seed, n=34, start=100.0, vol=0.03):
        if self.online:
            m = self._get("/api/market")
            if isinstance(m, list) and m:
                idx = seed % len(m)
                sym = m[idx].get("name")
                cc = self._get("/api/candles/%s" % sym)
                arr = cc.get("candles") if isinstance(cc, dict) else None
                if arr and len(arr) >= 5:
                    return [{"o": float(a.get("o", a.get("open", 0))),
                             "h": float(a.get("h", a.get("high", 0))),
                             "l": float(a.get("l", a.get("low", 0))),
                             "c": float(a.get("c", a.get("close", 0))),
                             "v": int(a.get("v", a.get("vol", 0)) or 0)}
                            for a in arr[-n:]]
        return D.candles(seed, n, start, vol)

    def boss_curve(self, seed, phases=8):
        return D.boss_curve(seed, phases)

    def phi_series(self, seed, n=13):
        return D.phi_series(seed, n)

    def phi_walk(self, seed, n, start, vol=0.02):
        return D.phi_walk(seed, n, start, vol)


if __name__ == "__main__":
    ld = LiveData()
    print("source:", ld.source)
    print("market[0]:", ld.market_snapshot(1)[0])
    sc = ld.sector_snapshot(1)
    print("sectors hot/cold:", sc["hot"], sc["cold"])
    print("magnate[0]:", ld.magnate_ladder(1)[0])
    print("funnel:", ld.liquidation_stages(1))
