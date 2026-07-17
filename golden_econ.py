#!/usr/bin/env python3
"""
CORP HEIST — Golden Economy Module
Everything scales by the golden ratio PHI = 1.618033988749...

This module is the connective tissue between:
  - GAMEPLAY  : phi-duel arena, hero progression, corp ranks
  - CONTENT   : corps, floors, Golden Artifact loot category
  - METAGAME  : guilds, leaderboard, market summary
  - VISUAL    : phi-spiral loot chains, fractal artifacts (see wealth_card.html)

Design rule: every reward/damage/threshold follows a phi curve so the
numbers feel "organic" and the UI can render them as golden spirals.
"""
import random
import math
import time

PHI = 1.618033988749
TAU = math.pi * 2.0


# ============================================================
# CONTENT DATA (corps, floors, artifacts)
# ============================================================

# 5 base corps + 3 new "golden" corps (7 total, a phi-friendly count)
CORPS = [
    "MERIDIAN", "APEX", "NOVA", "VERTEX", "PULSAR",
    "AUREATE", "SOLARIS",   # new golden corps
]

# 7 floors + 5 new "high-rise" floors (12 total: 12 = phi*phi*phi truncated-ish)
FLOORS = [
    "Lobby", "Trading Floor", "Vault", "Boardroom", "Data Center",
    "Sky Garden", "Penthouse",
    "Cloud Spire", "Gold Reserve", "Quantum Floor", "Throne Room", "Apex Atrium",
]

# New loot category: Golden Artifact (id 10) — drawn as fractal in client
ARTIFACT_BASE_VALUE = 50000
ARTIFACT_NAME_POOL = [
    "Golden Ratio", "Fib Spiral", "Phi Medallion", "Aurea Crown",
    "Midas Sigil", "Solar Compass", "Vault Key Prime", "Gilded Mandate",
]

# Hero power follows a phi curve per level
def hero_power(base, level):
    """Power grows as base * PHI^(level/10)."""
    return int(base * (PHI ** (level / 10.0)))

# Arena reward scales with opponent rank gap via phi
def duel_reward(base_reward, rank_gap):
    """Higher-ranked opponent beaten => bigger reward by phi^(gap)."""
    return int(base_reward * (PHI ** min(rank_gap, 6)))

# Progression threshold to next level: phi-weighted
def level_threshold(level):
    return int(1000 * (PHI ** (level / 5.0)))


# ============================================================
# META: GUILDS / CORP RANKS
# ============================================================

class GuildSystem:
    """Corp-based guilds. Players grouped by corp_id. Rank by total net worth.
    Info-only (no real money, no P2P)."""

    def __init__(self, state):
        self.state = state

    def corp_totals(self):
        totals = {i: {"net": 0, "members": 0, "name": CORPS[i % len(CORPS)]}
                  for i in range(len(CORPS))}
        for c in self.state.chars.values():
            cid = c["corp_id"] % len(CORPS)
            totals[cid]["net"] += c["net_worth"]
            totals[cid]["members"] += 1
        ranking = sorted(totals.values(), key=lambda x: -x["net"])
        for rank, g in enumerate(ranking, 1):
            g["rank"] = rank
        return ranking

    def leaderboard(self, top=50):
        items = []
        for uid, c in self.state.chars.items():
            items.append({
                "user_id": uid,
                "name": f"Player_{uid}",
                "net_worth": c["net_worth"],
                "level": c["level"],
                "corp": CORPS[c["corp_id"] % len(CORPS)],
                "floor": FLOORS[c["floor"] % len(FLOORS)],
                "tier": c.get("tier", 0),
            })
        items.sort(key=lambda x: -x["net_worth"])
        for rank, it in enumerate(items[:top], 1):
            it["rank"] = rank
        return items[:top]

    def market_summary(self):
        """Info-only market snapshot: top movers, phi-banded volatility."""
        stocks = sorted(self.state.stocks, key=lambda s: -abs(s["delta"]))[:8]
        return {
            "top_movers": [
                {"name": s["name"], "price": s["price"], "delta": s["delta"]}
                for s in stocks
            ],
            "phi_band": round(PHI, 4),
            "note": "Informational only. No trading advice. Rates set by system.",
        }


# ============================================================
# GAMEPLAY: PHI-DUEL ARENA
# ============================================================

class Arena:
    """One-shot pulse duel. Opponent chosen by rank proximity (phi gap).
    Winner gains gold + xp scaled by phi; loser loses a fraction.
    No P2P, no real money — purely in-game economy."""

    def __init__(self, state):
        self.state = state

    def _rank_list(self):
        return sorted(self.state.chars.values(), key=lambda c: -c["net_worth"])

    def find_opponent(self, uid):
        ranked = self._rank_list()
        me = self.state.chars.get(uid)
        if not me:
            return None
        my_rank = next((i for i, c in enumerate(ranked) if c["user_id"] == uid), 0)
        # opponent at a phi-gap distance (1, 2, 3, 5, 8...) for fair-ish match
        gaps = [1, 2, 3, 5, 8, 13]
        gap = random.choice(gaps)
        opp_idx = min(len(ranked) - 1, my_rank + gap)
        return ranked[opp_idx], gap

    def fight(self, uid):
        me = self.state.chars.get(uid)
        if not me:
            return {"error": "no char"}
        opp, gap = self.find_opponent(uid)
        if not opp:
            return {"error": "no opponent"}

        # power = hero power * level scaling
        my_pow = hero_power(100 + me["level"] * 10, me["hero_levels"][me["hero_id"] % 12])
        opp_pow = hero_power(100 + opp["level"] * 10, opp["hero_levels"][opp["hero_id"] % 12])
        # add a little randomness (phi-weighted swing)
        swing = random.uniform(1 / PHI, PHI)
        my_pow = int(my_pow * swing)

        win = my_pow >= opp_pow
        base = 500 * (me["level"] + 1)
        reward = duel_reward(base, gap) if win else -int(base / PHI)

        me["gold"] = max(0, me["gold"] + reward)
        me["xp"] += reward if win else 0
        # level up check (phi threshold)
        while me["xp"] >= level_threshold(me["level"]):
            me["xp"] -= level_threshold(me["level"])
            me["level"] += 1
        self.state.mark_dirty(uid)

        return {
            "win": win,
            "my_power": my_pow,
            "opp_power": opp_pow,
            "opp_name": f"Player_{opp['user_id']}",
            "reward_gold": reward,
            "level": me["level"],
            "phi_swing": round(swing, 3),
            "gap": gap,
        }


# ============================================================
# CONTENT: GOLDEN ARTIFACT LOOT
# ============================================================

def roll_artifact():
    """Generate a Golden Artifact loot entry (category 10)."""
    code = random.randint(0, 65535)
    value = int(ARTIFACT_BASE_VALUE * (PHI ** random.uniform(0, 3)))
    return {
        "code": code,
        "rarity": 5,            # artifact is top rarity
        "cat": 10,              # 10 = golden artifact (client renders fractal)
        "name": random.choice(ARTIFACT_NAME_POOL),
        "qty": 1,
        "value": value,
        "phi_seed": round(random.uniform(0, TAU), 4),
    }


def maybe_drop_artifact(chance=0.02):
    if random.random() < chance:
        return roll_artifact()
    return None


# ============================================================
# SEASONS (phi-weeks: a season = PHI * 7 ≈ 11.3 weeks)
# ============================================================

SEASON_WEEKS = int(PHI * 7)          # ~11 weeks per season
SEASON_EPOCH = 1700000000            # arbitrary fixed epoch (unix-ish)
WEEK_SEC = 7 * 24 * 3600

def current_season(now=None):
    now = now or int(time.time())
    weeks = (now - SEASON_EPOCH) // WEEK_SEC
    return weeks // SEASON_WEEKS, (weeks % SEASON_WEEKS) + 1

def season_progress(now=None):
    now = now or int(time.time())
    weeks = (now - SEASON_EPOCH) // WEEK_SEC
    return round((weeks % SEASON_WEEKS + 1) / SEASON_WEEKS, 3)

def season_points(char):
    """Seasonal rating points scale with phi: net_worth^0.5 * phi^(prestige)."""
    base = math.sqrt(max(1, char.get("net_worth", 0)))
    return int(base * (PHI ** char.get("prestige", 0)))


# ============================================================
# PASSIVE TREE (phi-cost nodes, phi-scaled bonuses)
# ============================================================
# 12 nodes; unlock cost scales by phi^(depth). Each node multiplies a stat.

PASSIVE_NODES = [
    {"id": i, "name": n, "stat": s, "depth": i // 3,
     "cost": int(50 * (PHI ** (i // 3))),
     "mult": round(PHI ** (0.25 + (i % 3) * 0.1), 3)}
    for i, (n, s) in enumerate([
        ("Gold Yield", "gold_mult"), ("Duel Power", "power_mult"),
        ("Loot Luck", "luck_mult"), ("Trade Edge", "trade_mult"),
        ("Vault Cap", "cap_mult"), ("Prestige Gain", "pres_mult"),
        ("Floor Reach", "floor_mult"), ("Market Sense", "market_mult"),
        ("Guild Bond", "guild_mult"), ("Artifact Find", "art_mult"),
        ("Net Worth", "net_mult"), ("Phi Mastery", "phi_mult"),
    ])
]

def passive_bonus(passives):
    """passives = list of 12 ints (levels per node). Return aggregated mults."""
    mults = {}
    for node, lvl in zip(PASSIVE_NODES, passives):
        mults[node["stat"]] = round(mults.get(node["stat"], 1.0) * (node["mult"] ** lvl), 4)
    return mults

def unlock_cost(node_id, current_lvl):
    node = PASSIVE_NODES[node_id]
    return int(node["cost"] * (PHI ** current_lvl))


# ============================================================
# SELF-TEST (run: python golden_econ.py)
# ============================================================

if __name__ == "__main__":
    class FakeState:
        def __init__(self):
            self.chars = {
                1000: {"user_id":1000,"gold":1000,"xp":500,"level":3,
                       "hero_id":1,"corp_id":2,"floor":4,"net_worth":200000,
                       "hero_levels":[10,20,5,8,12,3,7,9,4,6,11,2],
                       "stocks":[]},
                1001: {"user_id":1001,"gold":800,"xp":200,"level":2,
                       "hero_id":0,"corp_id":0,"floor":1,"net_worth":150000,
                       "hero_levels":[5,5,5,5,5,5,5,5,5,5,5,5],"stocks":[]},
            }
        def mark_dirty(self, uid):
            pass
        stocks = [{"name":"ALPHA","price":50.0,"delta":1.2},
                  {"name":"PHI","price":161.8,"delta":-2.1}]
    st = FakeState()
    g = GuildSystem(st)
    print("corp totals:", g.corp_totals()[0])
    print("leaderboard top:", g.leaderboard(2)[0])
    print("market:", g.market_summary()["phi_band"])
    ar = Arena(st)
    print("duel:", ar.fight(1000))
    print("artifact:", roll_artifact())
    print("level_threshold(3):", level_threshold(3))
    print("hero_power(100,20):", hero_power(100, 20))
    print("season:", current_season(), "progress:", season_progress())
    print("season_points:", season_points(st.chars[1000]))
    print("passive_bonus:", passive_bonus([1,0,2,0,0,0,0,0,0,0,0,0]))
    print("unlock_cost(0,1):", unlock_cost(0, 1))
    print("OK")
