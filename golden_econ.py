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
# DAILY GOLDEN CHEST (phi-timer, streak-scaled reward)
# ============================================================

CHEST_BASE = int(1000 * PHI ** 3)   # base daily gold

def chest_status(state, uid, now=None):
    """Report whether today's chest is available + next reward preview."""
    me = state.chars.get(uid)
    if not me:
        return {"error": "no char"}
    now = now or int(time.time())
    day = now // (24 * 3600)
    last = me.get("chest_day", -1)
    available = (day != last)
    # streak grows while claimed on consecutive days
    streak = me.get("chest_streak", 0)
    preview_streak = streak + 1 if available else streak
    reward = int(CHEST_BASE * (PHI ** min(preview_streak, 8) / PHI))
    secs_left = 0 if available else ((last + 1) * 24 * 3600 - now)
    return {
        "available": available,
        "chest_streak": streak,
        "reward_preview": reward,
        "seconds_left": max(0, secs_left),
        "note": "Daily chest gives in-game gold only.",
    }

def open_chest(state, uid, now=None):
    """Open the daily chest -> in-game gold, phi-scaled by chest streak."""
    me = state.chars.get(uid)
    if not me:
        return {"error": "no char"}
    now = now or int(time.time())
    day = now // (24 * 3600)
    last = me.get("chest_day", -1)
    if day == last:
        return {"error": "already opened today", **chest_status(state, uid, now)}
    # consecutive-day streak
    if last == day - 1:
        me["chest_streak"] = me.get("chest_streak", 0) + 1
    else:
        me["chest_streak"] = 1
    streak = me["chest_streak"]
    reward = int(CHEST_BASE * (PHI ** min(streak, 8) / PHI))
    me["chest_day"] = day
    me["gold"] = me.get("gold", 0) + reward
    state.mark_dirty(uid)
    return {"opened": True, "reward_gold": reward, "chest_streak": streak,
            "gold": me["gold"], "note": "In-game gold only."}


# ============================================================
# WORLD BOSS (single global boss, shared HP for everyone)
# ============================================================

WORLD_BOSS_NAMES = ["Aurum Leviathan", "The Gilded Devourer", "Phi Colossus",
                    "Midas Wyrm", "Sovereign of Debt", "The Golden Maw"]
WORLD_BOSS_BASE_HP = 50_000_000

class WorldBoss:
    """One global boss shared by all players. State on state.world_boss.
    Rolls a new boss each phi-week; loot pool shared by phi-shares."""

    def __init__(self, state):
        self.state = state
        if not hasattr(state, "world_boss"):
            state.world_boss = None

    def _boss(self):
        season, week = current_season()
        wb = self.state.world_boss
        # scale HP up each week; new boss identity per season-week
        max_hp = int(WORLD_BOSS_BASE_HP * (PHI ** (week / PHI)))
        if not wb or wb.get("season_week") != [season, week]:
            idx = (season * 7 + week) % len(WORLD_BOSS_NAMES)
            wb = {
                "name": WORLD_BOSS_NAMES[idx],
                "max_hp": max_hp,
                "hp": max_hp,
                "season_week": [season, week],
                "contributions": {},     # uid -> total damage
                "loot_pool": int(1_000_000 * (PHI ** (week / PHI))),
            }
            self.state.world_boss = wb
        return wb

    def status(self):
        wb = self._boss()
        top = sorted(wb["contributions"].items(), key=lambda kv: -kv[1])[:10]
        return {
            "boss": wb["name"],
            "hp": wb["hp"],
            "max_hp": wb["max_hp"],
            "pct": round(100 * wb["hp"] / wb["max_hp"], 4),
            "defeated": wb["hp"] <= 0,
            "loot_pool": wb["loot_pool"],
            "participants": len(wb["contributions"]),
            "top_contributors": [{"user_id": int(u), "damage": d}
                                 for u, d in top],
            "season_week": wb["season_week"],
            "note": "Shared world boss. Rewards are in-game gold only.",
        }

    def strike(self, uid):
        me = self.state.chars.get(uid)
        if not me:
            return {"error": "no char"}
        wb = self._boss()
        if wb["hp"] <= 0:
            return {"error": "world boss already defeated", **self.status()}
        mults = passive_bonus(me.get("passives", [0] * 12))
        pres = prestige_multiplier(me.get("prestige", 0))
        base = hero_power(100 + me.get("level", 1) * 10,
                          me.get("hero_levels", [1] * 12)[me.get("hero_id", 0) % 12])
        dmg = int(base * mults.get("power_mult", 1.0) * pres *
                  random.uniform(1 / PHI, PHI))
        wb["hp"] = max(0, wb["hp"] - dmg)
        key = str(uid)
        wb["contributions"][key] = wb["contributions"].get(key, 0) + dmg
        result = {"damage": dmg, "boss_hp": wb["hp"], "boss_max": wb["max_hp"],
                  "boss": wb["name"],
                  "pct": round(100 * wb["hp"] / wb["max_hp"], 4)}
        if wb["hp"] <= 0:
            # distribute loot pool by phi-weighted contribution shares
            result["defeated"] = True
            ranked = sorted(wb["contributions"].items(), key=lambda kv: -kv[1])
            pool = wb["loot_pool"]
            payouts = {}
            for rank, (u, _d) in enumerate(ranked):
                share = int(pool * (PHI - 1) / (PHI ** rank))
                payouts[u] = share
                cu = int(u)
                ch = self.state.chars.get(cu)
                if ch is not None:
                    ch["gold"] = ch.get("gold", 0) + share
                    self.state.mark_dirty(cu)
            result["my_reward"] = payouts.get(key, 0)
            result["payouts_count"] = len(payouts)
        self.state.mark_dirty(uid)
        return result


# ============================================================
# AUCTION HOUSE (list an item, others outbid; in-game gold only)
# ============================================================

AUCTION_DURATION = 3600          # seconds a listing stays open
AUCTION_MIN_INCREMENT = PHI       # each bid must beat current by * phi-ish

class Auction:
    """Player auctions. State on state.auctions (list of dicts).
    Bids and payouts are in-game gold only."""

    def __init__(self, state):
        self.state = state
        if not hasattr(state, "auctions"):
            state.auctions = []
        if not hasattr(state, "_auction_seq"):
            state._auction_seq = 0

    def _expire(self, now):
        """Settle auctions that ran out of time."""
        for a in self.state.auctions:
            if a["status"] == "open" and now >= a["ends"]:
                self._settle(a)

    def _settle(self, a):
        a["status"] = "sold" if a.get("top_bidder") else "expired"
        seller = self.state.chars.get(a["seller"])
        if a.get("top_bidder"):
            # gold already escrowed from bidder at bid time -> pay seller
            if seller is not None:
                seller["gold"] = seller.get("gold", 0) + a["top_bid"]
                self.state.mark_dirty(a["seller"])
            # give item to winner
            winner = self.state.chars.get(a["top_bidder"])
            if winner is not None:
                winner.setdefault("loot", []).append(dict(a["item"]))
                winner["net_worth"] = winner.get("net_worth", 0) + a["item"].get("value", 0)
                self.state.mark_dirty(a["top_bidder"])
        else:
            # no bids: return item to seller
            if seller is not None:
                seller.setdefault("loot", []).append(dict(a["item"]))
                seller["net_worth"] = seller.get("net_worth", 0) + a["item"].get("value", 0)
                self.state.mark_dirty(a["seller"])

    def list_item(self, uid, code, start_price, now=None):
        now = now or int(time.time())
        self._expire(now)
        me = self.state.chars.get(uid)
        if not me or not me.get("loot"):
            return {"error": "no loot"}
        item = next((l for l in me["loot"] if l["code"] == code), None)
        if not item:
            return {"error": "item not found"}
        me["loot"].remove(item)
        me["net_worth"] = me.get("net_worth", 0) - item.get("value", 0)
        self.state._auction_seq += 1
        start = max(1, int(start_price or int(item.get("value", 10) / PHI)))
        a = {"id": self.state._auction_seq, "seller": uid, "item": dict(item),
             "start_price": start, "top_bid": 0, "top_bidder": None,
             "ends": now + AUCTION_DURATION, "status": "open"}
        self.state.auctions.append(a)
        self.state.mark_dirty(uid)
        return {"ok": True, "auction": self._public(a, now)}

    def bid(self, uid, auction_id, amount, now=None):
        now = now or int(time.time())
        self._expire(now)
        me = self.state.chars.get(uid)
        if not me:
            return {"error": "no char"}
        a = next((x for x in self.state.auctions if x["id"] == auction_id), None)
        if not a or a["status"] != "open":
            return {"error": "auction closed"}
        if a["seller"] == uid:
            return {"error": "cannot bid on your own listing"}
        min_bid = max(a["start_price"], int(a["top_bid"] * AUCTION_MIN_INCREMENT) + 1)
        amount = int(amount)
        if amount < min_bid:
            return {"error": f"bid must be >= {min_bid}", "min_bid": min_bid}
        if me.get("gold", 0) < amount:
            return {"error": "not enough gold"}
        # refund previous top bidder
        prev = self.state.chars.get(a["top_bidder"]) if a["top_bidder"] else None
        if prev is not None:
            prev["gold"] = prev.get("gold", 0) + a["top_bid"]
            self.state.mark_dirty(a["top_bidder"])
        # escrow new bid
        me["gold"] -= amount
        a["top_bid"] = amount
        a["top_bidder"] = uid
        self.state.mark_dirty(uid)
        return {"ok": True, "auction": self._public(a, now), "gold": me["gold"]}

    def _public(self, a, now):
        return {"id": a["id"], "seller": a["seller"],
                "item": a["item"], "start_price": a["start_price"],
                "top_bid": a["top_bid"], "top_bidder": a["top_bidder"],
                "seconds_left": max(0, a["ends"] - now),
                "min_next": max(a["start_price"], int(a["top_bid"] * AUCTION_MIN_INCREMENT) + 1),
                "status": a["status"]}

    def listings(self, now=None):
        now = now or int(time.time())
        self._expire(now)
        return {"auctions": [self._public(a, now) for a in self.state.auctions
                             if a["status"] == "open"],
                "note": "Bids are in-game gold only. No real money."}


# ============================================================
# GUILD WARS (two corps race to beat a shared war-boss)
# ============================================================

WAR_BASE_HP = 20_000_000

class GuildWar:
    """Two corps race to deal the most damage to a shared war boss
    within a phi-week. Winner corp splits a phi prize pool (in-game gold)."""

    def __init__(self, state):
        self.state = state
        if not hasattr(state, "guild_war"):
            state.guild_war = None

    def _war(self):
        season, week = current_season()
        gw = self.state.guild_war
        if not gw or gw.get("season_week") != [season, week]:
            # pair corps 0v1 rotating by week
            a = (week * 2) % len(CORPS)
            b = (a + 1) % len(CORPS)
            hp = int(WAR_BASE_HP * (PHI ** (week / PHI)))
            gw = {
                "corp_a": a, "corp_b": b,
                "name_a": CORPS[a], "name_b": CORPS[b],
                "hp": hp, "max_hp": hp,
                "dmg_a": 0, "dmg_b": 0,
                "season_week": [season, week],
                "prize_pool": int(500_000 * (PHI ** (week / PHI))),
                "contributions": {},   # uid -> dmg
            }
            self.state.guild_war = gw
        return gw

    def status(self):
        gw = self._war()
        total = gw["dmg_a"] + gw["dmg_b"] or 1
        return {
            "boss": "War Titan",
            "corp_a": gw["name_a"], "corp_b": gw["name_b"],
            "dmg_a": gw["dmg_a"], "dmg_b": gw["dmg_b"],
            "share_a": round(100 * gw["dmg_a"] / total, 2),
            "share_b": round(100 * gw["dmg_b"] / total, 2),
            "hp": gw["hp"], "max_hp": gw["max_hp"],
            "pct": round(100 * gw["hp"] / gw["max_hp"], 2),
            "leader": (gw["name_a"] if gw["dmg_a"] >= gw["dmg_b"] else gw["name_b"]),
            "prize_pool": gw["prize_pool"],
            "defeated": gw["hp"] <= 0,
            "note": "Guild war rewards are in-game gold only.",
        }

    def attack(self, uid):
        me = self.state.chars.get(uid)
        if not me:
            return {"error": "no char"}
        gw = self._war()
        corp = me["corp_id"] % len(CORPS)
        if corp not in (gw["corp_a"], gw["corp_b"]):
            return {"error": "your corp is not in this war",
                    "corp_a": gw["name_a"], "corp_b": gw["name_b"]}
        if gw["hp"] <= 0:
            return {"error": "war already decided", **self.status()}
        mults = passive_bonus(me.get("passives", [0] * 12))
        pres = prestige_multiplier(me.get("prestige", 0))
        base = hero_power(100 + me.get("level", 1) * 10,
                          me.get("hero_levels", [1] * 12)[me.get("hero_id", 0) % 12])
        dmg = int(base * mults.get("power_mult", 1.0) * pres *
                  random.uniform(1 / PHI, PHI))
        gw["hp"] = max(0, gw["hp"] - dmg)
        if corp == gw["corp_a"]:
            gw["dmg_a"] += dmg
        else:
            gw["dmg_b"] += dmg
        gw["contributions"][str(uid)] = gw["contributions"].get(str(uid), 0) + dmg
        self.state.mark_dirty(uid)
        result = {"damage": dmg, "for_corp": CORPS[corp], **self.status()}
        if gw["hp"] <= 0:
            win_corp = gw["corp_a"] if gw["dmg_a"] >= gw["dmg_b"] else gw["corp_b"]
            # payout winners by phi-share of their contribution
            winners = [(int(u), d) for u, d in gw["contributions"].items()
                       if self.state.chars.get(int(u), {}).get("corp_id", -1) % len(CORPS) == win_corp]
            winners.sort(key=lambda x: -x[1])
            pool = gw["prize_pool"]
            for rank, (u, _d) in enumerate(winners):
                share = int(pool * (PHI - 1) / (PHI ** rank))
                ch = self.state.chars.get(u)
                if ch is not None:
                    ch["gold"] = ch.get("gold", 0) + share
                    self.state.mark_dirty(u)
            result["winner"] = CORPS[win_corp]
            result["winners_paid"] = len(winners)
        return result


# ============================================================
# INVESTMENT BONDS (phi-yield on a timer; in-game gold)
# ============================================================

BOND_TIERS = [
    # name, min_principal, phi_power (yield=principal*(phi**power)-principal), lock_seconds
    ("Bronze φ-Bond",   1_000,   0.15, 3600),
    ("Silver φ-Bond",   10_000,  0.30, 4 * 3600),
    ("Gold φ-Bond",     100_000, 0.50, 12 * 3600),
    ("Platinum φ-Bond", 1_000_000, 0.80, 24 * 3600),
]

def bond_tiers():
    out = []
    for name, minp, power, lock in BOND_TIERS:
        yld = round((PHI ** power) - 1, 4)
        out.append({"name": name, "min_principal": minp,
                    "yield_pct": round(yld * 100, 2), "lock_seconds": lock})
    return {"tiers": out, "note": "Bond yields are in-game gold only."}

def buy_bond(state, uid, tier_idx, principal, now=None):
    now = now or int(time.time())
    me = state.chars.get(uid)
    if not me:
        return {"error": "no char"}
    if tier_idx < 0 or tier_idx >= len(BOND_TIERS):
        return {"error": "bad tier"}
    name, minp, power, lock = BOND_TIERS[tier_idx]
    principal = int(principal)
    if principal < minp:
        return {"error": f"minimum principal is {minp}"}
    if me.get("gold", 0) < principal:
        return {"error": "not enough gold"}
    me["gold"] -= principal
    payout = int(principal * (PHI ** power))
    bond = {"id": now * 1000 + random.randint(0, 999), "tier": tier_idx,
            "name": name, "principal": principal, "payout": payout,
            "matures": now + lock}
    me.setdefault("bonds", []).append(bond)
    state.mark_dirty(uid)
    return {"ok": True, "bond": bond, "gold": me["gold"]}

def bond_status(state, uid, now=None):
    now = now or int(time.time())
    me = state.chars.get(uid)
    if not me:
        return {"error": "no char"}
    bonds = me.get("bonds", [])
    out = []
    for b in bonds:
        out.append({**b, "matured": now >= b["matures"],
                    "seconds_left": max(0, b["matures"] - now)})
    return {"bonds": out, "gold": me.get("gold", 0), **bond_tiers()}

def claim_bonds(state, uid, now=None):
    now = now or int(time.time())
    me = state.chars.get(uid)
    if not me:
        return {"error": "no char"}
    bonds = me.get("bonds", [])
    matured = [b for b in bonds if now >= b["matures"]]
    total = sum(b["payout"] for b in matured)
    me["bonds"] = [b for b in bonds if now < b["matures"]]
    if total:
        me["gold"] = me.get("gold", 0) + total
        state.mark_dirty(uid)
    return {"claimed_count": len(matured), "payout": total,
            "gold": me.get("gold", 0),
            "note": "Bond payouts are in-game gold only."}


# ============================================================
# DERIVATIVES EXCHANGE (phi options & futures on corp stocks)
# ============================================================

# Contract expires after a phi-scaled window; strike/premium follow phi.
DERIV_EXPIRY = int(1800 * PHI)     # ~48.5 min lock
DERIV_PREMIUM_RATE = PHI - 1       # 0.618 of intrinsic-ish, scales premium

def _stock_by_name(state, name):
    for s in getattr(state, "stocks", []):
        if s["name"] == name:
            return s
    return None

def deriv_quote(state, name):
    """Quote a phi option/future chain for a stock."""
    s = _stock_by_name(state, name)
    if not s:
        return {"error": "unknown symbol"}
    spot = s["price"]
    # phi-laddered strikes around spot
    strikes = [round(spot / PHI, 2), round(spot, 2), round(spot * PHI, 2)]
    chain = []
    for k in strikes:
        # premium scales with distance and phi
        call_prem = round(max(spot - k, 0) + spot * DERIV_PREMIUM_RATE / PHI, 2)
        put_prem = round(max(k - spot, 0) + spot * DERIV_PREMIUM_RATE / PHI, 2)
        chain.append({"strike": k, "call_premium": call_prem, "put_premium": put_prem})
    return {"symbol": name, "spot": spot, "delta": s.get("delta", 0),
            "chain": chain, "future_price": round(spot * (1 + DERIV_PREMIUM_RATE / (PHI ** 3)), 2),
            "expiry_seconds": DERIV_EXPIRY,
            "note": "Derivatives settle in in-game gold only."}

def open_position(state, uid, name, kind, strike, qty, now=None):
    """kind: 'call' | 'put' | 'future'. Pay premium/margin in gold."""
    now = now or int(time.time())
    me = state.chars.get(uid)
    if not me:
        return {"error": "no char"}
    s = _stock_by_name(state, name)
    if not s:
        return {"error": "unknown symbol"}
    kind = str(kind).lower()
    qty = max(1, int(qty))
    spot = s["price"]
    if kind == "future":
        entry = round(spot * (1 + DERIV_PREMIUM_RATE / (PHI ** 3)), 2)
        cost = round(entry * qty / PHI, 2)      # margin = 1/phi of notional
        strike = entry
    elif kind in ("call", "put"):
        strike = round(float(strike), 2)
        prem = (max(spot - strike, 0) if kind == "call" else max(strike - spot, 0)) + spot * DERIV_PREMIUM_RATE / PHI
        cost = round(prem * qty, 2)
    else:
        return {"error": "bad kind"}
    if me.get("gold", 0) < cost:
        return {"error": "not enough gold", "cost": cost}
    me["gold"] -= int(math.ceil(cost))
    pos = {"id": now * 1000 + random.randint(0, 999), "symbol": name,
           "kind": kind, "strike": strike, "qty": qty,
           "entry_spot": spot, "cost": int(math.ceil(cost)),
           "expires": now + DERIV_EXPIRY}
    me.setdefault("derivs", []).append(pos)
    state.mark_dirty(uid)
    return {"ok": True, "position": pos, "gold": me["gold"]}

def _settle_value(pos, spot):
    q = pos["qty"]
    if pos["kind"] == "call":
        return max(spot - pos["strike"], 0) * q
    if pos["kind"] == "put":
        return max(pos["strike"] - spot, 0) * q
    # future: profit vs entry + return margin
    return (spot - pos["strike"]) * q / PHI + pos["cost"]

def deriv_status(state, uid, now=None):
    now = now or int(time.time())
    me = state.chars.get(uid)
    if not me:
        return {"error": "no char"}
    out = []
    for p in me.get("derivs", []):
        s = _stock_by_name(state, p["symbol"])
        spot = s["price"] if s else p["entry_spot"]
        val = round(_settle_value(p, spot), 2)
        out.append({**p, "spot": spot, "settle_value": val,
                    "pnl": round(val - (0 if p["kind"] == "future" else p["cost"]), 2),
                    "expired": now >= p["expires"],
                    "seconds_left": max(0, p["expires"] - now)})
    return {"positions": out, "gold": me.get("gold", 0),
            "note": "Derivatives settle in in-game gold only."}

def settle_derivs(state, uid, now=None):
    now = now or int(time.time())
    me = state.chars.get(uid)
    if not me:
        return {"error": "no char"}
    derivs = me.get("derivs", [])
    due = [p for p in derivs if now >= p["expires"]]
    total = 0
    for p in due:
        s = _stock_by_name(state, p["symbol"])
        spot = s["price"] if s else p["entry_spot"]
        total += int(max(0, _settle_value(p, spot)))
    me["derivs"] = [p for p in derivs if now < p["expires"]]
    if total:
        me["gold"] = me.get("gold", 0) + total
        state.mark_dirty(uid)
    return {"settled_count": len(due), "payout": total, "gold": me.get("gold", 0),
            "note": "Derivatives settle in in-game gold only."}


# ============================================================
# GUILD SKYSCRAPER (collective build; each floor gives phi bonus)
# ============================================================

FLOOR_BASE_COST = 100_000          # gold to fund floor 1
SKY_MAX_FLOORS = 34                # fibonacci-ish cap

def _sky(state, corp_id):
    if not hasattr(state, "skyscrapers"):
        state.skyscrapers = {}
    c = corp_id % len(CORPS)
    if c not in state.skyscrapers:
        state.skyscrapers[c] = {"corp": c, "floors": 0, "progress": 0, "contributions": {}}
    return state.skyscrapers[c]

def floor_cost(floor):
    """Cost of the NEXT floor scales by phi."""
    return int(FLOOR_BASE_COST * (PHI ** (floor / PHI)))

def sky_bonus_pct(floors):
    """Total corp-wide bonus % from built floors (phi-diminishing sum)."""
    total = 0.0
    for f in range(floors):
        total += (PHI - 1) * (1 / (PHI ** (f / (PHI * 2))))
    return round(total, 2)

def sky_status(state, corp_id):
    sk = _sky(state, corp_id)
    nxt = floor_cost(sk["floors"])
    top = sorted(sk["contributions"].items(), key=lambda x: -x[1])[:5]
    return {"corp": CORPS[sk["corp"]], "floors": sk["floors"],
            "max_floors": SKY_MAX_FLOORS,
            "next_floor_cost": nxt, "progress": sk["progress"],
            "progress_pct": round(100 * sk["progress"] / nxt, 2) if nxt else 100,
            "bonus_pct": sky_bonus_pct(sk["floors"]),
            "top_builders": [{"uid": int(u), "gold": g} for u, g in top],
            "note": "Skyscraper bonus applies to the whole corp; funded in gold."}

def sky_fund(state, uid, amount):
    me = state.chars.get(uid)
    if not me:
        return {"error": "no char"}
    amount = int(amount)
    if amount <= 0:
        return {"error": "bad amount"}
    if me.get("gold", 0) < amount:
        return {"error": "not enough gold"}
    sk = _sky(state, me["corp_id"])
    if sk["floors"] >= SKY_MAX_FLOORS:
        return {"error": "skyscraper complete", **sky_status(state, me["corp_id"])}
    me["gold"] -= amount
    sk["progress"] += amount
    sk["contributions"][str(uid)] = sk["contributions"].get(str(uid), 0) + amount
    built = 0
    while sk["floors"] < SKY_MAX_FLOORS and sk["progress"] >= floor_cost(sk["floors"]):
        sk["progress"] -= floor_cost(sk["floors"])
        sk["floors"] += 1
        built += 1
    state.mark_dirty(uid)
    res = sky_status(state, me["corp_id"])
    res["ok"] = True
    res["funded"] = amount
    res["floors_built"] = built
    res["gold"] = me["gold"]
    return res


# ============================================================
# GOLDEN HOUR (timed x-phi rewards window with countdown)
# ============================================================

GH_CYCLE = int(3600 * PHI)         # a golden hour every ~97 min
GH_DURATION = int(600 * PHI)       # lasts ~16 min
GH_MULT = PHI                      # rewards x phi during the window

def golden_hour(now=None):
    now = now or int(time.time())
    phase = now % GH_CYCLE
    active = phase < GH_DURATION
    if active:
        return {"active": True, "multiplier": round(GH_MULT, 6),
                "seconds_left": GH_DURATION - phase,
                "next_in": 0,
                "note": "All gold rewards are multiplied by phi during Golden Hour."}
    return {"active": False, "multiplier": 1.0,
            "seconds_left": 0,
            "next_in": GH_CYCLE - phase,
            "note": "Golden Hour arrives on a phi cycle."}

def golden_multiplier(now=None):
    return GH_MULT if golden_hour(now)["active"] else 1.0


# ============================================================
# M&A (buy a stake in a corp; earn phi-share of members' income)
# ============================================================

# Total shares per corp; buying shares diverts a phi-fraction of that
# corp's members' earned gold to shareholders, pro-rata by shares held.
CORP_TOTAL_SHARES = 1000
MA_DIVIDEND_RATE = (PHI - 1) / (PHI ** 2)     # ~0.236 of earnings go to shareholders

def _ma(state):
    if not hasattr(state, "corp_shares"):
        # corp_shares[corp_id] = {"held": {uid: qty}, "price": base}
        state.corp_shares = {}
    return state.corp_shares

def _corp_book(state, corp_id):
    ma = _ma(state)
    c = corp_id % len(CORPS)
    if c not in ma:
        ma[c] = {"held": {}, "base_price": 1000}
    return ma[c]

def share_price(state, corp_id):
    """Price per share rises by phi as more shares are held (scarcity)."""
    book = _corp_book(state, corp_id)
    sold = sum(book["held"].values())
    frac = sold / CORP_TOTAL_SHARES
    return int(book["base_price"] * (PHI ** (frac * 3)))

def ma_status(state, corp_id=None, uid=None):
    out = []
    for cid in range(len(CORPS)):
        book = _corp_book(state, cid)
        sold = sum(book["held"].values())
        holders = sorted(book["held"].items(), key=lambda x: -x[1])[:5]
        entry = {"corp": CORPS[cid], "corp_id": cid,
                 "shares_sold": sold, "total_shares": CORP_TOTAL_SHARES,
                 "share_price": share_price(state, cid),
                 "dividend_rate_pct": round(MA_DIVIDEND_RATE * 100, 2),
                 "top_holders": [{"uid": int(u), "shares": q} for u, q in holders]}
        if uid is not None:
            entry["your_shares"] = book["held"].get(str(uid), 0)
        out.append(entry)
    return {"corps": out,
            "note": "Corp stakes pay phi-share dividends in in-game gold only."}

def buy_shares(state, uid, corp_id, qty):
    me = state.chars.get(uid)
    if not me:
        return {"error": "no char"}
    qty = max(1, int(qty))
    book = _corp_book(state, corp_id)
    sold = sum(book["held"].values())
    if sold + qty > CORP_TOTAL_SHARES:
        return {"error": f"only {CORP_TOTAL_SHARES - sold} shares left"}
    total_cost = 0
    for _ in range(qty):
        total_cost += share_price(state, corp_id)
        book["held"][str(uid)] = book["held"].get(str(uid), 0) + 1
    if me.get("gold", 0) < total_cost:
        # roll back
        book["held"][str(uid)] -= qty
        if book["held"][str(uid)] <= 0:
            book["held"].pop(str(uid), None)
        return {"error": "not enough gold", "cost": total_cost}
    me["gold"] -= total_cost
    state.mark_dirty(uid)
    res = {"ok": True, "bought": qty, "cost": total_cost, "gold": me["gold"],
           "your_shares": book["held"][str(uid)],
           "corp": CORPS[corp_id % len(CORPS)]}
    return res

def _pay_dividends(state, earner_uid, gross):
    """When a member of corp C earns gold, divert a phi-fraction to C's shareholders."""
    earner = state.chars.get(earner_uid)
    if not earner:
        return 0
    corp = earner["corp_id"] % len(CORPS)
    book = _corp_book(state, corp)
    sold = sum(book["held"].values())
    if sold <= 0:
        return 0
    pool = int(gross * MA_DIVIDEND_RATE)
    if pool <= 0:
        return 0
    paid = 0
    for u, q in book["held"].items():
        share = int(pool * q / CORP_TOTAL_SHARES)
        if share <= 0:
            continue
        ch = state.chars.get(int(u))
        if ch is not None:
            ch["gold"] = ch.get("gold", 0) + share
            state.mark_dirty(int(u))
            paid += share
    return paid


# ============================================================
# CENTRAL GOLD AWARD (Golden Hour x-phi + M&A dividends)
# ============================================================

def award_gold(state, uid, base_amount, now=None, dividends=True):
    """Single funnel for gold rewards: applies Golden Hour multiplier,
    credits the player, and pays M&A dividends to corp shareholders.
    Returns {gained, golden, dividends_paid, gold}."""
    me = state.chars.get(uid)
    if not me:
        return {"gained": 0, "golden": False, "dividends_paid": 0, "gold": 0}
    mult = golden_multiplier(now)
    gained = int(round(base_amount * mult))
    me["gold"] = me.get("gold", 0) + gained
    div = _pay_dividends(state, uid, gained) if dividends else 0
    state.mark_dirty(uid)
    return {"gained": gained, "golden": mult > 1.0,
            "multiplier": round(mult, 6),
            "dividends_paid": div, "gold": me["gold"]}


# ============================================================
# INSIDER NEWS (random phi events move stocks; early entry profits)
# ============================================================

NEWS_TEMPLATES = [
    ("{sym} lands golden merger — analysts stunned", "up", PHI),
    ("{sym} posts record phi-quarter earnings", "up", PHI / 1.3),
    ("{sym} unveils breakthrough — shares surge", "up", PHI / 1.1),
    ("Regulator probes {sym} accounting", "down", 1 / PHI),
    ("{sym} guidance slashed — sell-off begins", "down", 1 / (PHI * 1.1)),
    ("{sym} CEO resigns amid scandal", "down", 1 / (PHI * 1.3)),
]
NEWS_INTERVAL = int(300 * PHI)     # a new headline every ~8 min
NEWS_MAX = 12

def _news(state):
    if not hasattr(state, "news"):
        state.news = []
    if not hasattr(state, "_news_seq"):
        state._news_seq = 0
    if not hasattr(state, "_news_last"):
        state._news_last = 0
    return state.news

def tick_news(state, now=None):
    """Generate a headline on the phi interval and move the stock by phi."""
    now = now or int(time.time())
    news = _news(state)
    if now - state._news_last < NEWS_INTERVAL and news:
        return None
    stocks = getattr(state, "stocks", [])
    if not stocks:
        return None
    state._news_last = now
    stock = random.choice(stocks)
    tmpl, direction, factor = random.choice(NEWS_TEMPLATES)
    old = stock["price"]
    stock["price"] = round(max(0.01, old * factor), 2)
    stock["delta"] = round(stock["price"] - old, 2)
    state._news_seq += 1
    item = {"id": state._news_seq, "ts": now, "symbol": stock["name"],
            "headline": tmpl.format(sym=stock["name"]),
            "direction": direction,
            "change_pct": round(100 * (stock["price"] - old) / old, 2),
            "new_price": stock["price"]}
    news.append(item)
    del news[:-NEWS_MAX]
    return item

def news_feed(state, since=0, now=None):
    tick_news(state, now)
    news = _news(state)
    nxt = max(0, NEWS_INTERVAL - ((now or int(time.time())) - state._news_last))
    return {"news": [n for n in news if n["id"] > since][-NEWS_MAX:],
            "last_id": news[-1]["id"] if news else 0,
            "next_headline_in": nxt,
            "note": "Insider news moves stocks by phi. Trade early to profit."}


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
    print("chest_status:", chest_status(st, 1000)["available"], chest_status(st, 1000)["reward_preview"])
    print("open_chest:", open_chest(st, 1000)["reward_gold"])
    print("open_again:", open_chest(st, 1000).get("error"))
    wb = WorldBoss(st)
    print("world boss:", wb.status()["boss"], wb.status()["pct"])
    for _ in range(3):
        s = wb.strike(1000)
    print("wb strike:", {k: s[k] for k in ("damage", "boss_hp")})
    print("OK")
