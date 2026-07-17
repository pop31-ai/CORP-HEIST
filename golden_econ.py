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

# Arena reward scales with opponent rank gap via phi (softened for balance)
def duel_reward(base_reward, rank_gap):
    """Higher-ranked opponent beaten => bigger reward by phi^(gap/2).
    Softer than phi^gap so top ranks stay reachable (max ~4x at gap 6)."""
    return int(base_reward * (PHI ** (min(rank_gap, 6) / 2.0)))

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

    def season_rewards(self, top=10):
        """Top players by seasonal points. Prize pool split by phi:
        rank 1 gets a fraction, each next rank gets prev/phi (in-game gold)."""
        ranked = sorted(self.state.chars.values(),
                        key=lambda c: -season_points(c))[:top]
        season, week = current_season()
        # prize pool scales with number of players and season
        pool = int(1_000_000 * (PHI ** (week / SEASON_WEEKS)))
        # phi-decay shares: share_r = pool * (phi-1) / phi^r  (geometric, sums ~pool)
        rewards = []
        for r, c in enumerate(ranked, 1):
            share = int(pool * (PHI - 1) / (PHI ** r))
            rewards.append({
                "rank": r,
                "user_id": c["user_id"],
                "name": f"Player_{c['user_id']}",
                "points": season_points(c),
                "prize_gold": share,
                "corp": CORPS[c["corp_id"] % len(CORPS)],
            })
        return {
            "season": season,
            "week": week,
            "prize_pool": pool,
            "note": "Prizes are in-game gold only. No real money. Awarded at season end.",
            "top": rewards,
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

        # passive bonuses (phi-scaled multipliers)
        mults = passive_bonus(me.get("passives", [0] * 12))
        pow_mult = mults.get("power_mult", 1.0)
        gold_mult = mults.get("gold_mult", 1.0)

        # power = hero power * level scaling * passive power_mult
        my_pow = hero_power(100 + me["level"] * 10, me["hero_levels"][me["hero_id"] % 12])
        my_pow = int(my_pow * pow_mult)
        opp_pow = hero_power(100 + opp["level"] * 10, opp["hero_levels"][opp["hero_id"] % 12])
        # add a little randomness (phi-weighted swing)
        swing = random.uniform(1 / PHI, PHI)
        my_pow = int(my_pow * swing)

        win = my_pow >= opp_pow
        base = 500 * (me["level"] + 1)
        reward = duel_reward(base, gap) if win else -int(base / PHI)
        # gold_mult applies to positive rewards only
        if reward > 0:
            reward = int(reward * gold_mult)

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
            "power_mult": round(pow_mult, 3),
            "gold_mult": round(gold_mult, 3),
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
# PRESTIGE / ASCENSION (reset progress for a permanent phi-multiplier)
# ============================================================
# Ascending resets level/xp/gold to base but grants a permanent prestige rank.
# Every stat that reads prestige (season_points, gold gains) grows by phi^prestige.

PRESTIGE_BASE_LEVEL = 21      # min level to ascend (Fibonacci number)
PRESTIGE_BASE_NET = 100_000   # min net worth to ascend

def prestige_requirement(current_prestige):
    """Requirement scales by phi each ascension."""
    lvl = int(PRESTIGE_BASE_LEVEL * (PHI ** current_prestige))
    net = int(PRESTIGE_BASE_NET * (PHI ** current_prestige))
    return {"level": lvl, "net_worth": net}

def prestige_multiplier(prestige):
    """Permanent global gold/power multiplier from prestige ranks."""
    return round(PHI ** prestige, 4)


class Prestige:
    """Ascension system. Reset level/xp/gold; gain a permanent prestige rank.
    Purely in-game — no real money involved."""

    def __init__(self, state):
        self.state = state

    def status(self, uid):
        me = self.state.chars.get(uid)
        if not me:
            return {"error": "no char"}
        p = me.get("prestige", 0)
        req = prestige_requirement(p)
        eligible = me["level"] >= req["level"] and me.get("net_worth", 0) >= req["net_worth"]
        # pres_mult passive boosts the prestige reward multiplier
        mults = passive_bonus(me.get("passives", [0] * 12))
        pres_boost = mults.get("pres_mult", 1.0)
        return {
            "prestige": p,
            "current_mult": prestige_multiplier(p),
            "next_mult": round(prestige_multiplier(p + 1) * pres_boost, 4),
            "requirement": req,
            "level": me["level"],
            "net_worth": me.get("net_worth", 0),
            "eligible": eligible,
        }

    def ascend(self, uid):
        me = self.state.chars.get(uid)
        if not me:
            return {"error": "no char"}
        st = self.status(uid)
        if not st.get("eligible"):
            return {"error": "not eligible", **st}
        me["prestige"] = me.get("prestige", 0) + 1
        # reset progression (keep passives, prestige, corp identity)
        me["level"] = 1
        me["xp"] = 0
        me["gold"] = 1000
        me["net_worth"] = PRESTIGE_BASE_NET  # keep a phi-seed of net worth
        self.state.mark_dirty(uid)
        return {
            "ascended": True,
            "prestige": me["prestige"],
            "new_mult": prestige_multiplier(me["prestige"]),
            "note": "Progress reset. Permanent phi-multiplier gained (in-game only).",
        }


# ============================================================
# GUILD RAIDS (coop boss; phi-scaled HP; loot split by phi shares)
# ============================================================
# The whole corp attacks a shared boss. Each strike deals damage = hero power.
# Boss HP scales by phi with the season week. Loot pool splits by phi-decay.

RAID_BASE_HP = 5_000_000

class Raid:
    """Per-corp coop boss. State stored on GuildState.raids[corp_id]."""

    def __init__(self, state):
        self.state = state
        if not hasattr(state, "raids"):
            state.raids = {}

    def _boss(self, corp_id):
        season, week = current_season()
        max_hp = int(RAID_BASE_HP * (PHI ** (week / PHI)))
        r = self.state.raids.get(corp_id)
        if not r or r.get("season_week") != (season, week):
            r = {
                "corp_id": corp_id,
                "name": f"{CORPS[corp_id % len(CORPS)]} Titan",
                "max_hp": max_hp,
                "hp": max_hp,
                "season_week": (season, week),
                "contributions": {},   # uid -> total damage
            }
            self.state.raids[corp_id] = r
        return r

    def status(self, corp_id):
        r = self._boss(corp_id)
        top = sorted(r["contributions"].items(), key=lambda kv: -kv[1])[:10]
        return {
            "boss": r["name"],
            "hp": r["hp"],
            "max_hp": r["max_hp"],
            "pct": round(100 * r["hp"] / r["max_hp"], 2),
            "defeated": r["hp"] <= 0,
            "top_contributors": [
                {"user_id": u, "damage": d} for u, d in top
            ],
        }

    def strike(self, uid):
        me = self.state.chars.get(uid)
        if not me:
            return {"error": "no char"}
        corp_id = me["corp_id"] % len(CORPS)
        r = self._boss(corp_id)
        if r["hp"] <= 0:
            return {"error": "boss already defeated", **self.status(corp_id)}

        mults = passive_bonus(me.get("passives", [0] * 12))
        pres = prestige_multiplier(me.get("prestige", 0))
        base = hero_power(100 + me["level"] * 10,
                          me["hero_levels"][me["hero_id"] % 12])
        dmg = int(base * mults.get("power_mult", 1.0) * pres *
                  random.uniform(1 / PHI, PHI))
        r["hp"] = max(0, r["hp"] - dmg)
        r["contributions"][uid] = r["contributions"].get(uid, 0) + dmg
        self.state.mark_dirty(uid)

        result = {"damage": dmg, "boss_hp": r["hp"], "boss_max": r["max_hp"]}
        if r["hp"] <= 0:
            result["defeated"] = True
            result["loot"] = self._distribute(r)
        return result

    def _distribute(self, r):
        """Split a phi-scaled loot pool among contributors by phi-decay shares
        ordered by damage dealt. In-game gold only."""
        pool = int(r["max_hp"] // PHI)   # gold pool ~ boss HP / phi
        ranked = sorted(r["contributions"].items(), key=lambda kv: -kv[1])
        out = []
        for rank, (u, dmg) in enumerate(ranked, 1):
            share = int(pool * (PHI - 1) / (PHI ** rank))
            c = self.state.chars.get(u)
            if c:
                c["gold"] = c.get("gold", 0) + share
                self.state.mark_dirty(u)
            out.append({"rank": rank, "user_id": u, "damage": dmg,
                        "reward_gold": share})
        return {"pool": pool, "shares": out,
                "note": "Raid loot is in-game gold only. No real money."}


# ============================================================
# DAILY PHI-QUESTS (3/day; phi-scaled gold rewards)
# ============================================================
# Deterministic per (uid, day) so all clients agree without server storage.

QUEST_POOL = [
    ("Win {n} phi-duels", "duels"),
    ("Reach net worth {n}", "net"),
    ("Unlock {n} passive levels", "passives"),
    ("Deal {n} raid damage", "raid"),
    ("Earn {n} gold today", "gold"),
]

def _day_index(now=None):
    now = now or int(time.time())
    return now // (24 * 3600)

def daily_quests(uid, now=None):
    """Return 3 deterministic quests for the day, phi-scaled rewards."""
    day = _day_index(now)
    rng = random.Random(uid * 1_000_003 + day)
    picks = rng.sample(range(len(QUEST_POOL)), 3)
    quests = []
    for slot, idx in enumerate(picks):
        desc, kind = QUEST_POOL[idx]
        target = int(3 * (PHI ** (slot + rng.randint(1, 3))))
        reward = int(1000 * (PHI ** (slot + 2)))
        quests.append({
            "slot": slot,
            "kind": kind,
            "desc": desc.format(n=target),
            "target": target,
            "reward_gold": reward,
        })
    return {"day": day, "quests": quests,
            "note": "Rewards are in-game gold only."}

def claim_quest(state, uid, slot, now=None):
    """Claim a quest reward (server trusts client progress for this info-game).
    Prevents double-claim via char['quest_claims'] = {day: [slots]}."""
    me = state.chars.get(uid)
    if not me:
        return {"error": "no char"}
    day = _day_index(now)
    q = daily_quests(uid, now)["quests"]
    if slot < 0 or slot >= len(q):
        return {"error": "bad slot"}
    claims = me.setdefault("quest_claims", {})
    day_key = str(day)
    done = claims.setdefault(day_key, [])
    if slot in done:
        return {"error": "already claimed", "slot": slot}
    reward = q[slot]["reward_gold"]
    me["gold"] = me.get("gold", 0) + reward
    done.append(slot)
    # prune old days
    for k in list(claims.keys()):
        if k != day_key:
            del claims[k]
    state.mark_dirty(uid)
    return {"claimed": True, "slot": slot, "reward_gold": reward,
            "gold": me["gold"]}


# ============================================================
# ACHIEVEMENTS / BADGES (phi-thresholded milestones)
# ============================================================

# id, name, description, check(char)->bool, reward_gold (phi-scaled)
ACHIEVEMENTS = [
    ("first_loot",  "First Blood",     "Own at least 1 loot item",
        lambda c: len(c.get("loot", [])) >= 1,                       int(1000 * PHI**1)),
    ("collector",   "Collector",       "Own 13 loot items (Fib)",
        lambda c: len(c.get("loot", [])) >= 13,                      int(1000 * PHI**3)),
    ("hoarder",     "Golden Hoarder",  "Own 55 loot items (Fib)",
        lambda c: len(c.get("loot", [])) >= 55,                      int(1000 * PHI**5)),
    ("rising",      "Rising Star",     "Reach level 8",
        lambda c: c.get("level", 1) >= 8,                            int(1000 * PHI**2)),
    ("executive",   "Executive",       "Reach level 21 (phi tier)",
        lambda c: c.get("level", 1) >= 21,                           int(1000 * PHI**4)),
    ("magnate",     "Magnate",         "Net worth over 1,000,000",
        lambda c: c.get("net_worth", 0) >= 1_000_000,                int(1000 * PHI**6)),
    ("tycoon",      "Golden Tycoon",   "Net worth over 100,000,000",
        lambda c: c.get("net_worth", 0) >= 100_000_000,              int(1000 * PHI**8)),
    ("ascended",    "Ascended",        "Prestige at least once",
        lambda c: c.get("prestige", 0) >= 1,                         int(1000 * PHI**5)),
    ("transcend",   "Transcendent",    "Prestige 5 times",
        lambda c: c.get("prestige", 0) >= 5,                         int(1000 * PHI**7)),
    ("streaker",    "Devoted",         "13-day login streak (Fib)",
        lambda c: c.get("streak_days", 0) >= 13,                     int(1000 * PHI**4)),
    ("topfloor",    "Top Floor",       "Reach the Apex Atrium (floor 12)",
        lambda c: c.get("floor", 0) >= 11,                           int(1000 * PHI**5)),
    ("artifact",    "Artifact Bearer", "Own a Golden Artifact",
        lambda c: any(l.get("rarity", 0) >= 5 or l.get("cat") == 10 for l in c.get("loot", [])),
                                                                     int(1000 * PHI**6)),
]

def evaluate_achievements(char):
    """Return list of achievement states for a char (unlocked flag + reward)."""
    out = []
    for aid, name, desc, check, reward in ACHIEVEMENTS:
        try:
            done = bool(check(char))
        except Exception:
            done = False
        out.append({"id": aid, "name": name, "desc": desc,
                    "unlocked": done, "reward_gold": reward})
    return out

def claim_achievements(state, uid):
    """Grant gold for newly-unlocked achievements (once each).
    Tracks claimed ids in char['ach_claimed']."""
    me = state.chars.get(uid)
    if not me:
        return {"error": "no char"}
    claimed = me.setdefault("ach_claimed", [])
    total = 0
    newly = []
    for a in evaluate_achievements(me):
        if a["unlocked"] and a["id"] not in claimed:
            claimed.append(a["id"])
            total += a["reward_gold"]
            newly.append({"id": a["id"], "name": a["name"],
                          "reward_gold": a["reward_gold"]})
    if total:
        me["gold"] = me.get("gold", 0) + total
        state.mark_dirty(uid)
    return {"granted_gold": total, "newly_unlocked": newly,
            "achievements": evaluate_achievements(me),
            "note": "Rewards are in-game gold only."}


# ============================================================
# REFERRAL SYSTEM (invite a friend -> phi bonus, in-game gold only)
# ============================================================

REFERRAL_BONUS = int(1000 * PHI ** 4)   # bonus to referrer per accepted invite

def referral_code(uid):
    """Deterministic short code for a user id (base36-ish)."""
    n = (uid * 2654435761) & 0xFFFFFF
    alpha = "ACDEFGHJKLMNPQRSTUVWXYZ23456789"
    s = ""
    for _ in range(5):
        s = alpha[n % len(alpha)] + s
        n //= len(alpha)
    return "PHI-" + s

def _code_to_uid_map(state):
    return {referral_code(u): u for u in state.chars.keys()}

def accept_referral(state, uid, code):
    """New player redeems a referral code. Both sides get in-game gold.
    Guards: cannot self-refer, cannot redeem twice."""
    me = state.chars.get(uid)
    if not me:
        return {"error": "no char"}
    if me.get("referred_by"):
        return {"error": "already redeemed a code"}
    ref_uid = _code_to_uid_map(state).get(str(code).strip().upper())
    if ref_uid is None:
        return {"error": "invalid code"}
    if ref_uid == uid:
        return {"error": "cannot refer yourself"}
    # newcomer bonus (phi-scaled, slightly smaller than referrer's)
    newbie_bonus = int(REFERRAL_BONUS / PHI)
    me["referred_by"] = ref_uid
    me["gold"] = me.get("gold", 0) + newbie_bonus
    referrer = state.chars.get(ref_uid)
    if referrer is not None:
        referrer["gold"] = referrer.get("gold", 0) + REFERRAL_BONUS
        referrer["referrals"] = referrer.get("referrals", 0) + 1
        state.mark_dirty(ref_uid)
    state.mark_dirty(uid)
    return {"accepted": True, "referrer": ref_uid,
            "your_bonus": newbie_bonus, "referrer_bonus": REFERRAL_BONUS,
            "gold": me["gold"], "note": "In-game gold only. No real money."}

def referral_status(state, uid):
    me = state.chars.get(uid)
    if not me:
        return {"error": "no char"}
    return {"code": referral_code(uid),
            "referrals": me.get("referrals", 0),
            "earned_gold": me.get("referrals", 0) * REFERRAL_BONUS,
            "referred_by": me.get("referred_by"),
            "bonus_per_invite": REFERRAL_BONUS,
            "note": "Invite friends for in-game gold. No real-money reward."}


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
    st.chars[1000]["passives"] = [3,3,0,0,0,0,0,0,0,0,0,0]
    print("duel w/ passives:", ar.fight(1000))
    print("season_rewards:", g.season_rewards(2))
    pr = Prestige(st)
    st.chars[1000]["level"] = 30
    print("prestige status:", pr.status(1000))
    print("ascend:", pr.ascend(1000))
    rd = Raid(st)
    print("raid status:", rd.status(2)["pct"], rd.status(2)["boss"])
    for _ in range(3):
        s = rd.strike(1000)
    print("raid strike:", {k: s[k] for k in ("damage", "boss_hp")})
    print("daily_quests:", daily_quests(1000)["quests"][0])
    print("claim_quest:", claim_quest(st, 1000, 0))
    print("claim_again:", claim_quest(st, 1000, 0))
    st.chars[1000]["loot"] = [{"rarity": 5}]
    ach = evaluate_achievements(st.chars[1000])
    print("achievements unlocked:", sum(1 for a in ach if a["unlocked"]), "/", len(ach))
    print("claim_ach:", claim_achievements(st, 1000)["granted_gold"])
    print("ref code 1000:", referral_code(1000))
    print("accept_ref:", accept_referral(st, 1001, referral_code(1000)))
    print("ref_status:", referral_status(st, 1000)["referrals"])
    print("OK")
